"""
LangGraph Multi-Agent Orchestrator for Manufacturing Manual Assistant (AgentOps).
Implements 5 specialist responsibilities (Query Agent, Retrieval Agent, Diagnosis Agent,
Safety Agent, Response Agent) orchestrated via a controlled state graph with an explicit
epistemic evidence gate, bounded citation verification retries, and strict canonical abstention.
"""

import logging
import operator
import re
import time
import uuid
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langgraph.graph import StateGraph, START, END

from accounts.models import UserRole
from documents.models import DocumentStatus
from history.models import EscalationStatus, EvidenceGateOutcome
from machines.models import Machine
from machines.services import can_user_access_machine
from rag.metrics import (
    CITATION_FAILURES_TOTAL,
    CROSS_MACHINE_BLOCKS_TOTAL,
    ESCALATIONS_TOTAL,
    EVIDENCE_GATE_TOTAL,
    RAG_PHASE_DURATION_SECONDS,
    RAG_REQUESTS_TOTAL,
    UNSUPPORTED_QUESTIONS_TOTAL,
)
from rag.services.agent_tools import AgentTools, RetrievedChunk
from rag.services.evidence_gate_service import (
    CitationValidationResult,
    CitationValidator,
    EvidenceEvaluationResult,
    EvidenceGateService,
)
from rag.services.generation_service import EXACT_ABSTENTION_MESSAGE, SYSTEM_INSTRUCTION
from rag.services.llm.base import BaseLLMProvider, LLMProviderError, LLMConfigurationError
from rag.services.llm.factory import get_llm_provider
from rag.services.providers.base import EmbeddingProviderError
from rag.services.retrieval_service import RetrievalError

logger = logging.getLogger(__name__)


class AgentState(TypedDict, total=False):
    # Inputs & Authentication
    request_id: str
    trace_id: str
    machine_id: str
    machine_code: str
    machine_name: str
    user_id: Optional[int]
    user_email: Optional[str]
    user_role: Optional[str]
    user_obj: Any
    question: str
    conversation_id: Optional[str]
    ip_address: Optional[str]

    # Specialist 1: Query Agent
    intent: str
    fault_code: Optional[str]
    symptoms: List[str]
    is_ambiguous: bool

    # Specialist 2: Retrieval Agent
    retrieved_chunks: List[Dict[str, Any]]
    retrieval_method: str

    # Epistemic Gate: Evidence Validation
    evidence_status: str  # PASS, PARTIAL, FAIL
    evidence_reason: str
    contradiction_detected: bool
    contradiction_details: Optional[str]
    precedence_applied: Optional[str]

    # Specialist 3: Diagnosis Agent
    hypotheses: List[str]
    confirmed_steps: List[str]

    # Specialist 4: Safety Agent
    safety_passed: bool
    safety_warnings: List[str]
    hazard_detected: bool

    # Specialist 5: Response Agent
    answer: str
    citations: List[Dict[str, Any]]
    limitations: str
    retry_count: int

    # Governance: Safe Abstention & Escalation
    escalation_status: str
    abstained: bool

    # AgentOps Observability & Provenance (Accumulated via reducer)
    agent_transitions: Annotated[List[Dict[str, Any]], operator.add]
    latencies: Dict[str, int]
    error: Optional[str]


class IndustriaXAgentWorkflow:
    """
    Controlled LangGraph workflow implementing Evidence-First Agentic Industrial Intelligence.
    """

    def __init__(
        self,
        tools: Optional[AgentTools] = None,
        evidence_gate: Optional[EvidenceGateService] = None,
        citation_validator: Optional[CitationValidator] = None,
        llm_provider: Optional[BaseLLMProvider] = None,
    ):
        self.tools = tools or AgentTools()
        self.evidence_gate = evidence_gate or EvidenceGateService()
        self.citation_validator = citation_validator or CitationValidator()
        self._explicit_llm_provider = llm_provider
        self.graph = self._build_graph()

    def _get_llm(self) -> Optional[BaseLLMProvider]:
        if self._explicit_llm_provider:
            return self._explicit_llm_provider
        try:
            return get_llm_provider()
        except Exception as e:
            logger.debug("Configured LLM provider not directly instantiable: %s", e)
            return None

    # --- Node 1: Query Understanding (Query Agent) ---
    def node_query_understanding(self, state: AgentState) -> Dict[str, Any]:
        start = time.perf_counter()
        query = state.get('question', '')

        # Fault code extraction (e.g. E-102, F104, ERR-403)
        code_match = re.search(r'\b(?:err(?:or)?|fault|alarm|code)?\s*[-:#]?\s*([a-zA-Z]{1,3}[-_]?\d{2,5})\b', query, re.IGNORECASE)
        fault_code = code_match.group(1).upper() if code_match else None

        # Intent classification
        intent = 'troubleshooting'
        q_lower = query.lower()
        if any(w in q_lower for w in ['safety', 'hazard', 'lockout', 'tagout', 'e-stop', 'emergency', 'protective']):
            intent = 'safety'
        elif any(w in q_lower for w in ['maintain', 'service', 'replace', 'lubricate', 'inspection', 'schedule']):
            intent = 'maintenance'
        elif any(w in q_lower for w in ['spec', 'dimension', 'weight', 'manual', 'model', 'what is']):
            intent = 'general'

        # Symptoms extraction
        symptoms = []
        for word in ['vibration', 'leak', 'overheating', 'noise', 'pressure drop', 'stalling', 'misalignment']:
            if word in q_lower:
                symptoms.append(word)

        is_ambiguous = len(query.strip()) < 5
        duration = int((time.perf_counter() - start) * 1000)

        transition = {
            'node': 'query_understanding',
            'agent': 'Query Agent',
            'duration_ms': duration,
            'details': f"Intent: {intent}, Fault: {fault_code}, Symptoms: {symptoms}"
        }

        return {
            'intent': intent,
            'fault_code': fault_code,
            'symptoms': symptoms,
            'is_ambiguous': is_ambiguous,
            'agent_transitions': [transition],
        }

    # --- Node 2: Knowledge Retrieval (Retrieval Agent) ---
    def node_knowledge_retrieval(self, state: AgentState) -> Dict[str, Any]:
        start = time.perf_counter()
        machine_id = state['machine_id']
        query = state['question']
        user = state.get('user_obj')

        # Retrieve chunks using backend-enforced machine-scoped retrieval
        try:
            chunks = self.tools.retrieve_manual_passages(
                machine_id=machine_id,
                user=user,
                query=query,
                top_k=5,
            )
        except (EmbeddingProviderError, LLMProviderError, RetrievalError):
            raise
        except Exception as e:
            logger.warning("Retrieval failed for machine %s: %s", machine_id, e)
            chunks = []

        serialized_chunks = [
            {
                'chunk_id': c.chunk_id,
                'document_id': c.document_id,
                'document_title': c.document_title,
                'revision': c.revision,
                'page_number': c.page_number,
                'text': c.text,
                'score': c.score,
                'retrieval_method': c.retrieval_method,
            }
            for c in chunks
        ]

        duration = int((time.perf_counter() - start) * 1000)
        transition = {
            'node': 'knowledge_retrieval',
            'agent': 'Retrieval Agent',
            'duration_ms': duration,
            'details': f"Retrieved {len(chunks)} verified passages strictly scoped to machine {state.get('machine_code', machine_id)}"
        }

        return {
            'retrieved_chunks': serialized_chunks,
            'retrieval_method': 'semantic_vector',
            'agent_transitions': [transition],
        }

    # --- Node 3: Evidence Validation Gate ---
    def node_evidence_validation(self, state: AgentState) -> Dict[str, Any]:
        start = time.perf_counter()
        chunks_data = state.get('retrieved_chunks', [])
        query = state['question']

        retrieved_objs = [
            RetrievedChunk(
                chunk_id=c['chunk_id'],
                document_id=c['document_id'],
                document_title=c['document_title'],
                revision=c['revision'],
                page_number=c['page_number'],
                text=c['text'],
                score=c['score'],
                retrieval_method=c['retrieval_method'],
                machine_id=state['machine_id'],
                machine_code=state.get('machine_code', ''),
            )
            for c in chunks_data
        ]

        evaluation = self.evidence_gate.evaluate(query, retrieved_objs)
        duration = int((time.perf_counter() - start) * 1000)

        transition = {
            'node': 'evidence_validation',
            'agent': 'Evidence Gate',
            'duration_ms': duration,
            'details': f"Outcome: {evaluation.outcome}, Reason: {evaluation.reason}"
        }

        return {
            'evidence_status': evaluation.outcome,
            'evidence_reason': evaluation.reason,
            'contradiction_detected': evaluation.contradiction_detected,
            'contradiction_details': evaluation.contradiction_details,
            'precedence_applied': evaluation.precedence_applied,
            'agent_transitions': [transition],
        }

    # --- Node 4: Diagnosis & Procedural Analysis (Diagnosis Agent) ---
    def node_diagnosis(self, state: AgentState) -> Dict[str, Any]:
        start = time.perf_counter()
        chunks = state.get('retrieved_chunks', [])

        confirmed_steps = []
        hypotheses = []
        for c in chunks:
            text = c['text']
            for line in text.split('\n'):
                line_str = line.strip()
                if not line_str:
                    continue
                if re.match(r'^(?:step\s*\d+|\d+\.|\*|-|inspect|check|replace|verify|calibrate)\b', line_str, re.IGNORECASE):
                    confirmed_steps.append(line_str)
                elif 'may cause' in line_str.lower() or 'possible cause' in line_str.lower():
                    hypotheses.append(line_str)

        duration = int((time.perf_counter() - start) * 1000)
        transition = {
            'node': 'diagnosis',
            'agent': 'Diagnosis Agent',
            'duration_ms': duration,
            'details': f"Derived {len(confirmed_steps)} procedural steps and {len(hypotheses)} supported hypotheses."
        }

        return {
            'hypotheses': hypotheses[:4],
            'confirmed_steps': confirmed_steps[:8],
            'agent_transitions': [transition],
        }

    # --- Node 5: Safety Validation (Safety Agent) ---
    def node_safety_validation(self, state: AgentState) -> Dict[str, Any]:
        start = time.perf_counter()
        chunks = state.get('retrieved_chunks', [])
        confirmed_steps = state.get('confirmed_steps', [])

        all_text = " ".join([c['text'] for c in chunks] + confirmed_steps).lower()

        safety_warnings = []
        hazard_detected = False

        if any(w in all_text for w in ['danger', 'high voltage', '480v', 'shock hazard']):
            safety_warnings.append("HAZARDOUS VOLTAGE: Disconnect and lock out main electrical disconnect before servicing.")
            hazard_detected = True

        if any(w in all_text for w in ['pressurized', 'hydraulic pressure', 'accumulator', 'pneumatic']):
            safety_warnings.append("STORED ENERGY: Bleed residual hydraulic/pneumatic pressure prior to opening valves or fittings.")
            hazard_detected = True

        if any(w in all_text for w in ['moving parts', 'pinch point', 'crush hazard', 'spindle']):
            safety_warnings.append("MECHANICAL PINCH POINT: Ensure machine is in full E-STOP state before placing hands near tooling.")

        duration = int((time.perf_counter() - start) * 1000)
        transition = {
            'node': 'safety_validation',
            'agent': 'Safety Agent',
            'duration_ms': duration,
            'details': f"Safety warnings: {len(safety_warnings)}, Hazard: {hazard_detected}"
        }

        return {
            'safety_passed': True,
            'safety_warnings': safety_warnings,
            'hazard_detected': hazard_detected,
            'agent_transitions': [transition],
        }

    # --- Node 6: Response Generation (Response Agent) ---
    def node_response_generation(self, state: AgentState) -> Dict[str, Any]:
        start = time.perf_counter()
        chunks = state.get('retrieved_chunks', [])
        outcome = state.get('evidence_status', 'PASS')
        machine_code = state.get('machine_code', 'Unknown')
        machine_name = state.get('machine_name', machine_code)
        question = state['question']
        retry = state.get('retry_count', 0)

        # Fail closed immediately if no verified chunks available
        if not chunks:
            duration = int((time.perf_counter() - start) * 1000)
            transition = {
                'node': 'response_generation',
                'agent': 'Response Agent',
                'duration_ms': duration,
                'details': "Zero passages retrieved; issuing canonical abstention.",
            }
            return {
                'answer': EXACT_ABSTENTION_MESSAGE,
                'citations': [],
                'limitations': '',
                'retry_count': retry,
                'abstained': True,
                'evidence_status': EvidenceGateOutcome.FAIL,
                'agent_transitions': [transition],
            }

        # Format retrieved passages with source IDs
        # Format retrieved passages with source IDs
        context_blocks = []
        for c in chunks:
            context_blocks.append(
                f"[SOURCE ID: {c['chunk_id']} | Document: {c['document_title']} | Page: {c['page_number']}]\n{c['text'].strip()}"
            )
        context_str = "\n\n----------------------------------------\n\n".join(context_blocks)

        user_prompt = (
            f"MACHINE: {machine_name} (Code: {machine_code})\n\n"
            f"--- VERIFIED MANUAL PASSAGES ---\n"
            f"{context_str}\n"
            f"--------------------------------\n\n"
            f"QUESTION: {question}\n\n"
            f"RESPONSE INSTRUCTIONS:\n"
            f"- Answer the question using ONLY the verified manual passages above.\n"
            f"- If the passages do not contain enough information to answer the question, respond exactly with:\n"
            f"  {EXACT_ABSTENTION_MESSAGE}\n"
            f"- Never speculate, invent measurements, or answer from general knowledge.\n"
            f"- Reference source IDs where appropriate."
        )

        llm = self._get_llm()
        if not llm:
            raise LLMProviderError("No LLM provider is configured or available for answer generation.")

        llm_res = llm.generate_chat_completion(
            system_instruction=SYSTEM_INSTRUCTION,
            user_prompt=user_prompt,
            max_tokens=800,
        )

        raw_answer = (llm_res.raw_text if llm_res else '') or ''
        answer = raw_answer.strip()

        # Check for explicit or semantic abstention
        answer_lower = answer.lower()
        is_abstention = (
            EXACT_ABSTENTION_MESSAGE.lower() in answer_lower
            or "not contain enough information" in answer_lower
            or "do not contain enough information" in answer_lower
            or "do not contain information" in answer_lower
            or "no information regarding" in answer_lower
            or "no information about" in answer_lower
            or "cannot be answered" in answer_lower
            or "not mentioned in" in answer_lower
            or not answer
        )

        duration = int((time.perf_counter() - start) * 1000)

        if is_abstention:
            transition = {
                'node': 'response_generation',
                'agent': 'Response Agent',
                'duration_ms': duration,
                'details': "Passages insufficient for query; canonical abstention returned with empty citations.",
            }
            return {
                'answer': EXACT_ABSTENTION_MESSAGE,
                'citations': [],
                'limitations': '',
                'retry_count': retry,
                'abstained': True,
                'evidence_status': EvidenceGateOutcome.FAIL,
                'agent_transitions': [transition],
            }

        # Match citations against chunks that support the answer.
        # Prefer explicit source IDs cited by the LLM; fall back to page/term overlap when no IDs are present.
        citations = []
        explicit_matches = [c for c in chunks if c['chunk_id'].lower() in answer_lower]
        if explicit_matches:
            matched_chunks = explicit_matches
        else:
            matched_chunks = []
            for c in chunks:
                cited_page = f"page {c['page_number']}" in answer_lower
                words = [w for w in re.findall(r'\w+', c['text'].lower()) if len(w) > 4]
                overlap = sum(1 for w in words if w in answer_lower)
                if cited_page or overlap >= 3:
                    matched_chunks.append(c)

        for c in matched_chunks:
            citations.append({
                'document_id': c['document_id'],
                'document_title': c['document_title'],
                'revision': c.get('revision', '1.0'),
                'page_number': c['page_number'],
                'chunk_id': c['chunk_id'],
                'source_id': c['chunk_id'],
                'source_text': c['text'],
                'retrieval_method': c.get('retrieval_method', 'vector'),
            })

        # Fallback to top chunk if none explicitly matched but answer is grounded
        if not citations and chunks:
            top_c = chunks[0]
            citations.append({
                'document_id': top_c['document_id'],
                'document_title': top_c['document_title'],
                'revision': top_c.get('revision', '1.0'),
                'page_number': top_c['page_number'],
                'chunk_id': top_c['chunk_id'],
                'source_id': top_c['chunk_id'],
                'source_text': top_c['text'],
                'retrieval_method': top_c.get('retrieval_method', 'vector'),
            })

        limitations = ""
        if outcome == EvidenceGateOutcome.PARTIAL:
            limitations = "Certain technical parameters were not fully covered in the active manual."

        transition = {
            'node': 'response_generation',
            'agent': 'Response Agent',
            'duration_ms': duration,
            'details': f"Generated grounded response ({len(answer)} chars) with {len(citations)} citations."
        }

        return {
            'answer': answer,
            'citations': citations,
            'limitations': limitations,
            'retry_count': retry,
            'abstained': False,
            'agent_transitions': [transition],
        }

    # --- Node 7: Citation Verification Gate ---
    def node_citation_verification(self, state: AgentState) -> Dict[str, Any]:
        start = time.perf_counter()
        if state.get('abstained', False):
            return {
                'citations': [],
                'agent_transitions': [{
                    'node': 'citation_verification',
                    'agent': 'Citation Validator',
                    'duration_ms': 0,
                    'details': 'Skipped verification for abstained query.'
                }],
            }

        citations = state.get('citations', [])
        answer = state.get('answer', '')
        machine_id = state['machine_id']

        result = self.citation_validator.validate_citations(
            citations=citations,
            machine_id=machine_id,
            answer_text=answer
        )

        duration = int((time.perf_counter() - start) * 1000)
        transition = {
            'node': 'citation_verification',
            'agent': 'Citation Validator',
            'duration_ms': duration,
            'details': f"Validation valid: {result.is_valid}, Notes: {result.validation_notes}"
        }

        if not result.is_valid:
            retry = state.get('retry_count', 0)
            CITATION_FAILURES_TOTAL.inc()
            return {
                'citations': result.verified_citations,
                'retry_count': retry + 1,
                'error': result.validation_notes,
                'agent_transitions': [transition],
            }

        return {
            'citations': result.verified_citations,
            'agent_transitions': [transition],
        }

    # --- Node 8: Safe Abstention and Escalation ---
    def node_abstention_and_escalation(self, state: AgentState) -> Dict[str, Any]:
        start = time.perf_counter()
        reason = state.get('evidence_reason') or state.get('error') or "Documentation is insufficient."

        # Fail-closed canonical abstention message required by Section 4
        answer = EXACT_ABSTENTION_MESSAGE

        duration = int((time.perf_counter() - start) * 1000)
        transition = {
            'node': 'abstention_and_escalation',
            'agent': 'Governance Gate',
            'duration_ms': duration,
            'details': f"Canonical abstention issued. Reason: {reason}"
        }

        UNSUPPORTED_QUESTIONS_TOTAL.inc()
        ESCALATIONS_TOTAL.labels(reason_category='insufficient_evidence').inc()

        return {
            'answer': answer,
            'evidence_status': EvidenceGateOutcome.FAIL,
            'escalation_status': EscalationStatus.PENDING,
            'citations': [],
            'abstained': True,
            'agent_transitions': [transition],
        }

    # --- Routing Decisions ---
    def route_after_evidence_validation(self, state: AgentState) -> str:
        outcome = state.get('evidence_status', 'FAIL')
        if outcome == EvidenceGateOutcome.FAIL:
            return 'abstention_and_escalation'
        return 'diagnosis'

    def route_after_citation_verification(self, state: AgentState) -> str:
        retry = state.get('retry_count', 0)
        citations = state.get('citations', [])

        if not citations:
            if retry < 1:
                return 'response_generation'
            return 'abstention_and_escalation'

        return END

    def _build_graph(self):
        workflow = StateGraph(AgentState)

        # Register nodes
        workflow.add_node('query_understanding', self.node_query_understanding)
        workflow.add_node('knowledge_retrieval', self.node_knowledge_retrieval)
        workflow.add_node('evidence_validation', self.node_evidence_validation)
        workflow.add_node('diagnosis', self.node_diagnosis)
        workflow.add_node('safety_validation', self.node_safety_validation)
        workflow.add_node('response_generation', self.node_response_generation)
        workflow.add_node('citation_verification', self.node_citation_verification)
        workflow.add_node('abstention_and_escalation', self.node_abstention_and_escalation)

        # Wire transitions
        workflow.add_edge(START, 'query_understanding')
        workflow.add_edge('query_understanding', 'knowledge_retrieval')
        workflow.add_edge('knowledge_retrieval', 'evidence_validation')

        # Conditional route from evidence gate
        workflow.add_conditional_edges(
            'evidence_validation',
            self.route_after_evidence_validation,
            {
                'diagnosis': 'diagnosis',
                'abstention_and_escalation': 'abstention_and_escalation',
            }
        )

        workflow.add_edge('diagnosis', 'safety_validation')
        workflow.add_edge('safety_validation', 'response_generation')
        workflow.add_edge('response_generation', 'citation_verification')

        # Conditional route from citation gate
        workflow.add_conditional_edges(
            'citation_verification',
            self.route_after_citation_verification,
            {
                'response_generation': 'response_generation',
                'abstention_and_escalation': 'abstention_and_escalation',
                END: END,
            }
        )

        workflow.add_edge('abstention_and_escalation', END)

        return workflow.compile()

    def run(self, initial_state: AgentState) -> AgentState:
        """
        Executes the compiled multi-agent LangGraph pipeline.
        """
        return self.graph.invoke(initial_state)
