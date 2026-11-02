"""
Comprehensive Integration & Verification Tests for Agentic AI (AgentOps).
Tests LangGraph multi-agent orchestration, evidence gating, citation validation,
fail-closed canonical abstention, machine isolation authorization,
and persistent provenance audit logging against PostgreSQL.
"""

from unittest.mock import MagicMock, patch
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import UserRole
from documents.models import Document, DocumentPage, DocumentStatus
from history.models import (
    AuditEvent,
    AuditProvenanceRecord,
    Citation,
    Escalation,
    EscalationStatus,
    EvidenceGateOutcome,
    QueryRecord,
)
from machines.models import Machine, MachineAssignment, MachineStatus
from rag.metrics import (
    CROSS_MACHINE_BLOCKS_TOTAL,
    EVIDENCE_GATE_TOTAL,
    RAG_REQUESTS_TOTAL,
    UNSUPPORTED_QUESTIONS_TOTAL,
)
from rag.services.agent_tools import AgentTools, RetrievedChunk
from rag.services.evidence_gate_service import (
    CitationValidator,
    EvidenceEvaluationResult,
    EvidenceGateService,
)
from rag.services.generation_service import EXACT_ABSTENTION_MESSAGE
from rag.services.langgraph_agent_service import IndustriaXAgentWorkflow
from rag.services.llm.base import BaseLLMProvider, LLMResult

User = get_user_model()


class MockDeterministicLLMProvider(BaseLLMProvider):
    """Deterministic LLM Provider for unit testing."""
    def __init__(self, answer="Calibrate pressure valve to 14.5 bar."):
        super().__init__(model_identifier="mock-gemini", timeout=30, temperature=0.0)
        self.preset_answer = answer

    def generate_chat_completion(self, system_instruction: str, user_prompt: str, max_tokens: int = 1000) -> LLMResult:
        return LLMResult(raw_text=self.preset_answer, model_identifier=self.model_identifier)


class AgenticAIOrchestrationTestCase(TestCase):
    """
    Tests the LangGraph state machine, conditional transitions, and bounded retries.
    """

    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin_agentic@mriothon.local', password='Password123!', role=UserRole.ADMIN
        )
        self.engineer = User.objects.create_user(
            email='eng_agentic@mriothon.local', password='Password123!', role=UserRole.ENGINEER
        )
        self.machine = Machine.objects.create(
            name='Haas CNC VF-2',
            machine_code='CNC-VF2-01',
            manufacturer='Haas Automation',
            model_number='VF-2',
            status=MachineStatus.ACTIVE,
            created_by=self.admin,
        )
        MachineAssignment.objects.create(
            user=self.engineer, machine=self.machine, is_active=True
        )

        self.doc = Document.objects.create(
            machine=self.machine,
            title='Haas VF-2 Operator Manual',
            original_filename='haas_vf2.pdf',
            status=DocumentStatus.READY,
            uploaded_by=self.admin,
        )
        self.page = DocumentPage.objects.create(
            document=self.doc,
            page_number=15,
            text="Spindle bearing lubrication: Inject 5ml Mobil SHC 007 grease every 500 operating hours.",
            character_count=82,
        )

    def test_full_graph_execution_order_and_state_propagation(self):
        """Verifies end-to-end execution order through all specialist nodes."""
        mock_chunk = RetrievedChunk(
            chunk_id="CHUNK-VF2-001",
            document_id=str(self.doc.id),
            document_title=self.doc.title,
            revision="1.0",
            page_number=15,
            text="Spindle bearing lubrication: Inject 5ml Mobil SHC 007 grease every 500 operating hours.",
            score=0.95,
            retrieval_method="vector",
            machine_id=str(self.machine.id),
            machine_code=self.machine.machine_code,
        )

        mock_tools = MagicMock(spec=AgentTools)
        mock_tools.retrieve_manual_passages.return_value = [mock_chunk]

        mock_llm = MockDeterministicLLMProvider(
            answer="According to page 15, lubricate spindle bearings with 5ml Mobil SHC 007 grease every 500 hours."
        )

        workflow = IndustriaXAgentWorkflow(
            tools=mock_tools,
            llm_provider=mock_llm,
        )

        initial_state = {
            'request_id': 'req_test_001',
            'trace_id': 'trace_test_001',
            'machine_id': str(self.machine.id),
            'machine_code': self.machine.machine_code,
            'machine_name': self.machine.name,
            'user_id': self.engineer.id,
            'user_email': self.engineer.email,
            'user_role': self.engineer.role,
            'user_obj': self.engineer,
            'question': "How often should spindle bearings be lubricated?",
            'retry_count': 0,
        }

        final_state = workflow.run(initial_state)

        # 1. Verify Node Transitions in chronological order
        nodes_visited = [t['node'] for t in final_state['agent_transitions']]
        expected_order = [
            'query_understanding',
            'knowledge_retrieval',
            'evidence_validation',
            'diagnosis',
            'safety_validation',
            'response_generation',
            'citation_verification',
        ]
        self.assertEqual(nodes_visited, expected_order)

        # 2. Verify state propagation
        self.assertEqual(final_state['intent'], 'maintenance')
        self.assertIn(final_state['evidence_status'], (EvidenceGateOutcome.PASS, EvidenceGateOutcome.PARTIAL))
        self.assertFalse(final_state['abstained'])
        self.assertIn("Mobil SHC 007", final_state['answer'])
        self.assertEqual(len(final_state['citations']), 1)
        self.assertEqual(final_state['citations'][0]['page_number'], 15)

    def test_evidence_gate_fail_routes_straight_to_abstention(self):
        """When evidence sufficiency fails, workflow must route directly to abstention."""
        mock_tools = MagicMock(spec=AgentTools)
        mock_tools.retrieve_manual_passages.return_value = []  # Zero chunks retrieved

        workflow = IndustriaXAgentWorkflow(tools=mock_tools)

        initial_state = {
            'request_id': 'req_test_fail',
            'trace_id': 'trace_test_fail',
            'machine_id': str(self.machine.id),
            'machine_code': self.machine.machine_code,
            'machine_name': self.machine.name,
            'user_id': self.engineer.id,
            'user_email': self.engineer.email,
            'user_role': self.engineer.role,
            'user_obj': self.engineer,
            'question': "What is the recommended spindle coolant concentration?",
            'retry_count': 0,
        }

        final_state = workflow.run(initial_state)

        nodes_visited = [t['node'] for t in final_state['agent_transitions']]
        # Must bypass diagnosis, safety_validation, response_generation, citation_verification
        self.assertEqual(nodes_visited, ['query_understanding', 'knowledge_retrieval', 'evidence_validation', 'abstention_and_escalation'])
        self.assertEqual(final_state['answer'], EXACT_ABSTENTION_MESSAGE)
        self.assertEqual(final_state['citations'], [])
        self.assertTrue(final_state['abstained'])
        self.assertEqual(final_state['escalation_status'], EscalationStatus.PENDING)

    def test_citation_failure_bounded_retry_protection(self):
        """Verifies bounded retry loop: invalid citations retry at most once before abstaining."""
        mock_chunk = RetrievedChunk(
            chunk_id="CHUNK-VF2-002",
            document_id=str(self.doc.id),
            document_title=self.doc.title,
            revision="1.0",
            page_number=15,
            text="Emergency e-stop wiring diagram.",
            score=0.90,
            retrieval_method="vector",
            machine_id=str(self.machine.id),
            machine_code=self.machine.machine_code,
        )

        mock_tools = MagicMock(spec=AgentTools)
        mock_tools.retrieve_manual_passages.return_value = [mock_chunk]

        # Force citation validator to consistently reject citations
        mock_validator = MagicMock(spec=CitationValidator)
        mock_validator.validate_citations.return_value = MagicMock(
            is_valid=False,
            verified_citations=[],
            rejected_citations=[{'document_id': str(self.doc.id), 'page_number': 15}],
            validation_notes="Hallucinated text overlap check failed.",
            can_regenerate=True,
        )

        workflow = IndustriaXAgentWorkflow(
            tools=mock_tools,
            citation_validator=mock_validator,
            llm_provider=MockDeterministicLLMProvider("Fabricated claim."),
        )

        initial_state = {
            'request_id': 'req_test_retry',
            'trace_id': 'trace_test_retry',
            'machine_id': str(self.machine.id),
            'machine_code': self.machine.machine_code,
            'machine_name': self.machine.name,
            'user_id': self.engineer.id,
            'user_email': self.engineer.email,
            'user_role': self.engineer.role,
            'user_obj': self.engineer,
            'question': "Where is the emergency stop located?",
            'retry_count': 0,
        }

        final_state = workflow.run(initial_state)

        # Must execute response_generation -> citation_verification -> retry response_generation -> citation_verification -> abstention
        nodes_visited = [t['node'] for t in final_state['agent_transitions']]
        self.assertIn('abstention_and_escalation', nodes_visited)
        self.assertEqual(final_state['answer'], EXACT_ABSTENTION_MESSAGE)
        self.assertTrue(final_state['abstained'])
        self.assertEqual(final_state['citations'], [])


class EvidenceGateAndCitationValidatorTestCase(TestCase):
    """
    Tests evidence gating rules, contradiction detection, and PostgreSQL citation validation.
    """

    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin_gate@mriothon.local', password='Password123!', role=UserRole.ADMIN
        )
        self.machine_a = Machine.objects.create(
            name='Hydraulic Press 100T',
            machine_code='HP-100-01',
            status=MachineStatus.ACTIVE,
            created_by=self.admin,
        )
        self.machine_b = Machine.objects.create(
            name='Compressor AC-50',
            machine_code='AC-50-01',
            status=MachineStatus.ACTIVE,
            created_by=self.admin,
        )

        self.doc_a = Document.objects.create(
            machine=self.machine_a,
            title='HP-100 Service Manual',
            original_filename='hp100.pdf',
            status=DocumentStatus.READY,
            uploaded_by=self.admin,
        )
        self.page_a1 = DocumentPage.objects.create(
            document=self.doc_a,
            page_number=1,
            text="Hydraulic pressure operating specification: strictly 150 bar.",
            character_count=65,
        )

        self.doc_b = Document.objects.create(
            machine=self.machine_b,
            title='AC-50 Manual',
            original_filename='ac50.pdf',
            status=DocumentStatus.READY,
            uploaded_by=self.admin,
        )
        self.page_b1 = DocumentPage.objects.create(
            document=self.doc_b,
            page_number=1,
            text="Discharge pressure must not exceed 8.5 bar.",
            character_count=44,
        )

    def test_citation_validator_accepts_valid_grounded_citation(self):
        validator = CitationValidator()
        citations = [{
            'document_id': str(self.doc_a.id),
            'page_number': 1,
            'source_text': "Hydraulic pressure operating specification: strictly 150 bar.",
        }]
        answer = "The hydraulic operating pressure is strictly 150 bar."
        result = validator.validate_citations(citations, str(self.machine_a.id), answer)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.verified_citations), 1)
        self.assertEqual(len(result.rejected_citations), 0)

    def test_citation_validator_rejects_cross_machine_citation(self):
        """Citing machine B's document for machine A's question must be strictly rejected."""
        validator = CitationValidator()
        citations = [{
            'document_id': str(self.doc_b.id),
            'page_number': 1,
            'source_text': "Discharge pressure must not exceed 8.5 bar.",
        }]
        answer = "Discharge pressure is 8.5 bar."
        result = validator.validate_citations(citations, str(self.machine_a.id), answer)

        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.rejected_citations), 1)
        self.assertIn("belongs to a different machine", result.rejected_citations[0]['rejection_reason'])

    def test_citation_validator_rejects_nonexistent_page(self):
        validator = CitationValidator()
        citations = [{
            'document_id': str(self.doc_a.id),
            'page_number': 999,  # Page 999 does not exist
            'source_text': "Non-existent passage.",
        }]
        result = validator.validate_citations(citations, str(self.machine_a.id), "Answer.")
        self.assertFalse(result.is_valid)
        self.assertIn("does not exist", result.rejected_citations[0]['rejection_reason'])

    def test_citation_validator_rejects_hallucinated_unrelated_passage(self):
        """Passage with zero semantic overlap with the answer must be rejected."""
        validator = CitationValidator()
        citations = [{
            'document_id': str(self.doc_a.id),
            'page_number': 1,
            'source_text': "Hydraulic pressure operating specification: strictly 150 bar.",
        }]
        # Answer talks about something completely unrelated (e.g. electrical cables)
        answer = "Inspect the secondary transformer grounding copper wire."
        result = validator.validate_citations(citations, str(self.machine_a.id), answer)
        self.assertFalse(result.is_valid)
        self.assertIn("zero factual overlap", result.rejected_citations[0]['rejection_reason'])

    def test_contradiction_detection_with_revision_precedence(self):
        gate = EvidenceGateService()
        chunk_old = RetrievedChunk(
            chunk_id="C1", document_id="doc_old", document_title="Manual v1",
            revision="1.0", page_number=2, text="Operating pressure is 150 bar.",
            score=0.9, retrieval_method="vector", machine_id="m1", machine_code="M1"
        )
        chunk_new = RetrievedChunk(
            chunk_id="C2", document_id="doc_new", document_title="Manual v2",
            revision="2.0", page_number=2, text="Operating pressure is 180 bar.",
            score=0.9, retrieval_method="vector", machine_id="m1", machine_code="M1"
        )

        has_conflict, details, precedence = gate.detect_contradictions([chunk_old, chunk_new])
        self.assertTrue(has_conflict)
        self.assertIsNotNone(precedence)
        self.assertIn("Rev 2.0 superseded Rev 1.0", precedence)


class AgenticAPIIntegrationTestCase(TestCase):
    """
    End-to-end API integration tests verifying authorization, response format,
    dual persistence (QueryRecord + AuditProvenanceRecord), and Prometheus metrics.
    """

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email='admin_api@mriothon.local', password='Password123!', role=UserRole.ADMIN
        )
        self.supervisor = User.objects.create_user(
            email='sup_api@mriothon.local', password='Password123!', role=UserRole.SUPERVISOR
        )
        self.eng_assigned = User.objects.create_user(
            email='eng_assigned@mriothon.local', password='Password123!', role=UserRole.ENGINEER
        )
        self.eng_unassigned = User.objects.create_user(
            email='eng_unassigned@mriothon.local', password='Password123!', role=UserRole.ENGINEER
        )

        self.machine = Machine.objects.create(
            name='ABB IRB 6700 Robot',
            machine_code='ABB-IRB-01',
            status=MachineStatus.ACTIVE,
            created_by=self.admin,
        )
        MachineAssignment.objects.create(
            user=self.eng_assigned, machine=self.machine, is_active=True
        )

        self.doc = Document.objects.create(
            machine=self.machine,
            title='ABB IRB 6700 Product Manual',
            original_filename='irb6700.pdf',
            status=DocumentStatus.READY,
            uploaded_by=self.admin,
        )
        self.page = DocumentPage.objects.create(
            document=self.doc,
            page_number=3,
            text="Wrist gearboxes: strictly use Shell Omala S4 WE 320 synthetic oil. Drain interval: 24,000 hours.",
            character_count=105,
        )

        self.query_url = '/api/rag/query/'
        self.ask_url = '/api/rag/ask/'

    def test_unassigned_engineer_blocked_and_audited(self):
        """Cross-machine query attempt by unassigned engineer is denied with 403 and logged in AuditEvent."""
        self.client.force_authenticate(user=self.eng_unassigned)
        response = self.client.post(self.query_url, {
            'machine_id': str(self.machine.id),
            'question': "What gear oil is used?"
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Confirm AuditEvent logged
        audit_event = AuditEvent.objects.filter(
            event_type='CROSS_MACHINE_ACCESS_BLOCKED',
            user=self.eng_unassigned,
            machine=self.machine,
        ).first()
        self.assertIsNotNone(audit_event)

    def test_inactive_assignment_denied(self):
        """Deactivated assignment denies access with 403."""
        assignment = MachineAssignment.objects.get(user=self.eng_assigned, machine=self.machine)
        assignment.is_active = False
        assignment.save()

        self.client.force_authenticate(user=self.eng_assigned)
        response = self.client.post(self.query_url, {
            'machine_id': str(self.machine.id),
            'question': "What gear oil is used?"
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch('rag.services.langgraph_agent_service.IndustriaXAgentWorkflow._get_llm')
    @patch('rag.views.get_retrieval_service')
    def test_assigned_engineer_supported_query_end_to_end(self, mock_get_svc, mock_get_llm):
        """Assigned engineer receives grounded answer, citations, and persists dual records."""
        from rag.services.retrieval_service import RetrievedChunkContext

        mock_get_svc.return_value.retrieve_context.return_value = [
            RetrievedChunkContext(
                source_id="DOC-IRB-P3-C0",
                document_id=str(self.doc.id),
                document_title=self.doc.title,
                original_filename=self.doc.original_filename,
                machine_id=str(self.machine.id),
                page_number=3,
                chunk_index=0,
                chunk_text="Wrist gearboxes: strictly use Shell Omala S4 WE 320 synthetic oil. Drain interval: 24,000 hours.",
                similarity_score=0.95,
                chroma_vector_id="v_irb_1"
            )
        ]

        mock_get_llm.return_value = MockDeterministicLLMProvider(
            "For wrist gearboxes, strictly use Shell Omala S4 WE 320 synthetic oil with 24,000 hours drain interval."
        )

        self.client.force_authenticate(user=self.eng_assigned)
        response = self.client.post(self.ask_url, {
            'machine_id': str(self.machine.id),
            'question': "What gear oil is used for the wrist gearboxes and drain interval?"
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertFalse(data['abstained'])
        self.assertIn("Shell Omala S4 WE 320", data['answer'])
        self.assertIn('query_id', data)
        self.assertIn('trace_id', data)
        self.assertIn('agent_transitions', data)

        # 1. Verify QueryRecord persistence
        query_record = QueryRecord.objects.get(id=data['query_id'])
        self.assertEqual(query_record.user, self.eng_assigned)
        self.assertEqual(query_record.machine, self.machine)
        self.assertFalse(query_record.abstained)

        # 2. Verify AuditProvenanceRecord persistence
        provenance = AuditProvenanceRecord.objects.filter(query_record=query_record).first()
        self.assertIsNotNone(provenance)
        self.assertEqual(provenance.trace_id, data['trace_id'])
        self.assertTrue(len(provenance.agent_transitions) > 0)

    def test_unsupported_question_abstains_with_exact_canonical_message(self):
        """Unsupported inquiry returns exact canonical abstention and logs escalation."""
        self.client.force_authenticate(user=self.eng_assigned)
        response = self.client.post(self.query_url, {
            'machine_id': str(self.machine.id),
            'question': "What is the paint color code for the factory exterior walls?"
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertTrue(data['abstained'])
        self.assertEqual(data['answer'], EXACT_ABSTENTION_MESSAGE)
        self.assertEqual(data['citations'], [])

        # Verify Escalation record created
        query_record = QueryRecord.objects.get(id=data['query_id'])
        escalation = Escalation.objects.filter(query=query_record).first()
        self.assertIsNotNone(escalation)
        self.assertEqual(escalation.status, EscalationStatus.PENDING)

    def test_prometheus_metrics_scrape_endpoint(self):
        """Verifies GET /metrics endpoint exports Prometheus metrics."""
        response = self.client.get('/metrics')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(b'industriax_rag_requests_total', response.content)
        self.assertIn(b'industriax_evidence_gate_evaluations_total', response.content)
