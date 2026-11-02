"""
Comprehensive test suite for RAG application:
- Document chunking service (short/long, overlap, headings, technical terms, page isolation)
- Embedding provider architecture (Hugging Face, LM Studio, factory, error handling, no silent fallback)
- ChromaDB vector service (client, collection, metadata, deterministic IDs, machine isolation)
- Indexing lifecycle service (orchestration, verification, idempotent retry, failure recovery)
- API endpoints (RBAC, machine-level authorization, validation)
- Management command (reindex_documents)
"""

import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User, UserRole
from documents.models import Document, DocumentPage, DocumentStatus
from machines.models import Machine, MachineAssignment, MachineStatus
from rag.models import DocumentChunk, DocumentIndex, IndexingStatus
from rag.services.chunking_service import ChunkData, ChunkingService
from rag.services.chroma_service import ChromaModelMismatchError, ChromaService
from rag.services.indexing_service import (
    DocumentIndexingError,
    DocumentIndexingService,
    DocumentNotReadyForIndexingError,
)
from rag.services.providers.base import (
    BaseEmbeddingProvider,
    EmbeddingAuthenticationError,
    EmbeddingConfigurationError,
    EmbeddingDimensionMismatchError,
    EmbeddingProviderError,
    EmbeddingRateLimitError,
    EmbeddingTimeoutError,
)
from rag.services.providers.factory import get_embedding_provider
from rag.services.providers.huggingface import HuggingFaceEmbeddingProvider
from rag.services.providers.lm_studio import LMStudioEmbeddingProvider


# ==============================================================================
# Mock Embedding Provider for Isolated Testing
# ==============================================================================

class MockEmbeddingProvider(BaseEmbeddingProvider):
    """
    In-memory mock embedding provider producing deterministic vectors of dimension 8.
    """

    def __init__(self, model_identifier="mock-model-v1", dimension=8):
        super().__init__(model_identifier=model_identifier, timeout=5, expected_dimension=dimension)

    def embed_text(self, text: str) -> list[float]:
        return [0.123] * self.expected_dimension

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.123] * self.expected_dimension for _ in texts]


# ==============================================================================
# 1. Chunking Service Tests
# ==============================================================================

class ChunkingServiceTestCase(TestCase):
    """
    Tests text chunking rules: page isolation, token estimation, overlap,
    heading preservation, and technical specifications.
    """

    def setUp(self):
        self.chunker = ChunkingService(
            target_tokens=50,
            max_tokens=80,
            overlap_tokens=15,
            min_tokens=10
        )
        self.user = User.objects.create_user(email="chunker@test.com", password="password123", role="ADMIN")
        self.machine = Machine.objects.create(machine_code="CNC-01", name="CNC Mill", created_by=self.user)
        self.doc = Document.objects.create(
            machine=self.machine,
            title="Manual",
            original_filename="manual.pdf",
            checksum="a" * 64,
            status=DocumentStatus.READY
        )

    def test_short_page_produces_single_chunk(self):
        """Pages with content below max_tokens should produce exactly one chunk."""
        page = DocumentPage.objects.create(
            document=self.doc,
            page_number=1,
            text="General Safety Warning: Always wear protective eye goggles and steel-toed boots.",
            character_count=78
        )
        chunks = self.chunker.chunk_page(page)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].chunk_index, 0)
        self.assertEqual(chunks[0].page_number, 1)
        self.assertEqual(chunks[0].text, page.text)
        self.assertEqual(chunks[0].character_start_offset, 0)
        self.assertEqual(chunks[0].character_end_offset, len(page.text))

    def test_empty_or_trivial_page_ignored(self):
        """Pages with no extractable text or whitespace-only should return 0 chunks."""
        page_empty = DocumentPage.objects.create(document=self.doc, page_number=2, text="", character_count=0)
        page_spaces = DocumentPage.objects.create(document=self.doc, page_number=3, text="   \n\t  ", character_count=6)

        self.assertEqual(self.chunker.chunk_page(page_empty), [])
        self.assertEqual(self.chunker.chunk_page(page_spaces), [])

    def test_long_page_sliding_window_with_overlap(self):
        """Long pages should be broken into multiple overlapping chunks."""
        long_text = (
            "Section 1: Operating Procedures. Ensure power switch is set to 24 VDC. "
            "Inspect hydraulic oil levels before starting spindle motor. "
            "Calibrate axes X, Y, and Z to zero position before loading workpiece. "
            "Verify coolant flow rate is maintained at 15 L/min during high-speed cutting. "
            "In case of spindle vibration, immediately hit emergency stop switch E-STOP. "
            "Consult maintenance schedule for grease lubrication every 200 operational hours. "
            "Report any deviation in positional tolerance exceeding 0.005 mm to the supervisor. "
            "Shutdown sequence requires parking table at home coordinate X0 Y0 Z100."
        )
        page = DocumentPage.objects.create(
            document=self.doc,
            page_number=4,
            text=long_text,
            character_count=len(long_text)
        )
        chunks = self.chunker.chunk_page(page)
        self.assertGreater(len(chunks), 1)

        # Check chunk indexes and page number preservation
        for idx, chunk in enumerate(chunks):
            self.assertEqual(chunk.chunk_index, idx)
            self.assertEqual(chunk.page_number, 4)
            self.assertEqual(chunk.page_id, page.id)
            self.assertGreater(chunk.token_count, 0)
            # Verify text slice matches offsets
            self.assertEqual(chunk.text, page.text[chunk.character_start_offset:chunk.character_end_offset])

    def test_preserves_technical_units_and_error_codes(self):
        """Technical specifications and error codes must not be mangled."""
        tech_text = (
            "Error Code E-401: Spindle Overheat. "
            "Operating threshold: 85.5 °C at 12000 RPM. "
            "Check thermocouple sensor RTD-2 and 24 VDC relay K-10."
        )
        page = DocumentPage.objects.create(
            document=self.doc,
            page_number=5,
            text=tech_text,
            character_count=len(tech_text)
        )
        chunks = self.chunker.chunk_page(page)
        self.assertEqual(len(chunks), 1)
        self.assertIn("E-401", chunks[0].text)
        self.assertIn("85.5 °C", chunks[0].text)
        self.assertIn("24 VDC", chunks[0].text)

    def test_document_chunking_maintains_page_isolation(self):
        """Chunks from different pages must never be merged."""
        DocumentPage.objects.create(document=self.doc, page_number=1, text="Page 1 Content on Safety Rules.", character_count=32)
        DocumentPage.objects.create(document=self.doc, page_number=2, text="Page 2 Content on Maintenance.", character_count=30)

        all_chunks = self.chunker.chunk_document(self.doc)
        self.assertEqual(len(all_chunks), 2)
        self.assertEqual(all_chunks[0].page_number, 1)
        self.assertEqual(all_chunks[1].page_number, 2)


# ==============================================================================
# 2. Embedding Provider Tests
# ==============================================================================

class EmbeddingProviderTestCase(TestCase):
    """
    Tests provider factory, Hugging Face client, LM Studio client,
    and strict error handling (no silent fallback).
    """

    def test_factory_selects_huggingface(self):
        provider = get_embedding_provider(
            provider_name='huggingface',
            api_key='hf_test_token',
            model_identifier='Qwen/Qwen3-Embedding-0.6B'
        )
        self.assertIsInstance(provider, HuggingFaceEmbeddingProvider)
        self.assertEqual(provider.get_model_identifier(), 'Qwen/Qwen3-Embedding-0.6B')
        self.assertEqual(provider.get_dimension(), 1024)

    def test_factory_selects_lm_studio(self):
        provider = get_embedding_provider(
            provider_name='lm_studio',
            base_url='http://127.0.0.1:1234/v1',
            model_identifier='nomic-ai/nomic-embed-text-v1.5-GGUF'
        )
        self.assertIsInstance(provider, LMStudioEmbeddingProvider)
        self.assertEqual(provider.get_dimension(), 768)

    def test_factory_strictly_refuses_unsupported_provider(self):
        """Must raise EmbeddingConfigurationError; silent fallback is prohibited."""
        with self.assertRaises(EmbeddingConfigurationError):
            get_embedding_provider(provider_name='cohere')

    def test_huggingface_missing_token_raises_configuration_error(self):
        with self.assertRaises(EmbeddingConfigurationError):
            HuggingFaceEmbeddingProvider(api_key="")

    @patch('rag.services.providers.huggingface.requests.post')
    def test_huggingface_successful_embedding(self, mock_post):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = [[0.05] * 1024]
        mock_post.return_value = mock_response

        provider = HuggingFaceEmbeddingProvider(api_key="hf_test_key")
        embedding = provider.embed_text("Sample technical manual text")
        self.assertEqual(len(embedding), 1024)

    @patch('rag.services.providers.huggingface.requests.post')
    def test_huggingface_dimension_mismatch_raises_error(self, mock_post):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        # Return 512 instead of 1024
        mock_response.json.return_value = [[0.05] * 512]
        mock_post.return_value = mock_response

        provider = HuggingFaceEmbeddingProvider(api_key="hf_test_key")
        with self.assertRaises(EmbeddingDimensionMismatchError):
            provider.embed_text("Sample text")

    @patch('rag.services.providers.huggingface.requests.post')
    def test_huggingface_rate_limit_handling(self, mock_post):
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 429
        mock_post.return_value = mock_response

        provider = HuggingFaceEmbeddingProvider(api_key="hf_test_key")
        with self.assertRaises(EmbeddingRateLimitError):
            provider.embed_text("Sample text")

    @patch('rag.services.providers.huggingface.requests.post')
    def test_huggingface_auth_error_handling(self, mock_post):
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        provider = HuggingFaceEmbeddingProvider(api_key="invalid_key")
        with self.assertRaises(EmbeddingAuthenticationError):
            provider.embed_text("Sample text")

    @patch('rag.services.providers.lm_studio.requests.post')
    def test_lm_studio_applies_nomic_document_prefix(self, mock_post):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"embedding": [0.01] * 768, "index": 0}]
        }
        mock_post.return_value = mock_response

        provider = LMStudioEmbeddingProvider(model_identifier="nomic-ai/nomic-embed-text-v1.5-GGUF")
        provider.embed_text("Machine manual instructions")

        # Verify search_document: prefix was applied
        call_kwargs = mock_post.call_args[1]
        self.assertTrue(call_kwargs["json"]["input"].startswith("search_document: "))


# ==============================================================================
# 3. ChromaDB Integration Tests
# ==============================================================================

class ChromaServiceTestCase(TestCase):
    """
    Tests persistent ChromaDB client, collection creation, cosine space,
    metadata enrichment, deterministic vector IDs, and machine isolation.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.chroma_service = ChromaService(
            persist_directory=Path(self.temp_dir.name),
            collection_name="test_collection_v1"
        )

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_collection_creation_with_cosine_space(self):
        collection = self.chroma_service.get_or_create_collection(embedding_model="test-model")
        self.assertEqual(collection.name, "test_collection_v1")
        self.assertEqual(collection.metadata.get("hnsw:space"), "cosine")

    def test_upsert_and_deterministic_ids(self):
        doc_id = str(uuid.uuid4())
        machine_id = str(uuid.uuid4())

        records = [
            {
                "id": self.chroma_service.generate_vector_id(doc_id, 1, 0),
                "text": "Chunk 0 text content",
                "embedding": [0.1, 0.2, 0.3, 0.4],
                "metadata": {
                    "document_id": doc_id,
                    "machine_id": machine_id,
                    "document_page_id": 1,
                    "page_number": 1,
                    "chunk_index": 0,
                    "embedding_model": "test-model",
                }
            }
        ]

        count = self.chroma_service.upsert_chunks(records, embedding_model="test-model")
        self.assertEqual(count, 1)

        # Idempotency / duplicate prevention check
        count_repeat = self.chroma_service.upsert_chunks(records, embedding_model="test-model")
        self.assertEqual(count_repeat, 1)
        self.assertEqual(self.chroma_service.count_document_vectors(doc_id), 1)

    def test_machine_level_filtering_isolation(self):
        """Vectors must be filterable by machine_id to guarantee manual isolation."""
        doc1_id = str(uuid.uuid4())
        doc2_id = str(uuid.uuid4())
        mach1_id = str(uuid.uuid4())
        mach2_id = str(uuid.uuid4())

        records = [
            {
                "id": "v1",
                "text": "CNC text",
                "embedding": [0.1, 0.1],
                "metadata": {"document_id": doc1_id, "machine_id": mach1_id}
            },
            {
                "id": "v2",
                "text": "Lathe text",
                "embedding": [0.2, 0.2],
                "metadata": {"document_id": doc2_id, "machine_id": mach2_id}
            }
        ]
        self.chroma_service.upsert_chunks(records, embedding_model="test-model")

        coll = self.chroma_service.get_or_create_collection()
        mach1_results = coll.get(where={"machine_id": mach1_id})
        self.assertEqual(len(mach1_results["ids"]), 1)
        self.assertEqual(mach1_results["ids"][0], "v1")

    def test_model_consistency_enforcement(self):
        """Mixing different embedding models in one collection must raise ChromaModelMismatchError."""
        self.chroma_service.get_or_create_collection(embedding_model="model-A")

        with self.assertRaises(ChromaModelMismatchError):
            self.chroma_service.get_or_create_collection(embedding_model="model-B")


# ==============================================================================
# 4. Indexing Lifecycle Service Tests
# ==============================================================================

class IndexingLifecycleTestCase(TestCase):
    """
    Tests complete document indexing pipeline, database transaction safety,
    verification, and failure handling.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.chroma_service = ChromaService(
            persist_directory=Path(self.temp_dir.name),
            collection_name="test_indexing_lifecycle"
        )
        self.mock_provider = MockEmbeddingProvider()
        self.indexing_service = DocumentIndexingService(
            embedding_provider=self.mock_provider,
            chroma_service=self.chroma_service,
        )

        self.user = User.objects.create_user(email="admin@test.com", password="password123", role=UserRole.ADMIN)
        self.machine = Machine.objects.create(machine_code="ROBOT-01", name="Welding Robot", created_by=self.user)
        self.doc = Document.objects.create(
            machine=self.machine,
            title="Welding Manual",
            original_filename="welding.pdf",
            checksum="b" * 64,
            status=DocumentStatus.READY
        )
        DocumentPage.objects.create(
            document=self.doc,
            page_number=1,
            text="Step 1: Check power cabling. Step 2: Calibrate torch angle to 45 degrees.",
            character_count=74
        )

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_rejects_document_not_ready_for_indexing(self):
        """Documents with status UPLOADED or PROCESSING cannot be indexed."""
        unready_doc = Document.objects.create(
            machine=self.machine,
            title="Unready Doc",
            checksum="c" * 64,
            status=DocumentStatus.UPLOADED
        )
        with self.assertRaises(DocumentNotReadyForIndexingError):
            self.indexing_service.index_document(unready_doc)

    def test_successful_indexing_lifecycle(self):
        """Verifies chunk creation in Neon, vector insertion in ChromaDB, and index status READY."""
        index_record = self.indexing_service.index_document(self.doc)

        self.assertEqual(index_record.status, IndexingStatus.READY)
        self.assertEqual(index_record.chunk_count, 1)
        self.assertEqual(index_record.embedding_model, "mock-model-v1")
        self.assertEqual(index_record.error_message, "")

        # Verify Neon PostgreSQL DocumentChunk records
        db_chunks = DocumentChunk.objects.filter(document=self.doc)
        self.assertEqual(db_chunks.count(), 1)
        chunk = db_chunks.first()
        self.assertEqual(chunk.chunk_index, 0)
        self.assertEqual(chunk.embedding_model, "mock-model-v1")
        self.assertTrue(chunk.chroma_vector_id.startswith(f"doc_{self.doc.id}"))

        # Verify ChromaDB vectors
        vector_count = self.chroma_service.count_document_vectors(str(self.doc.id))
        self.assertEqual(vector_count, 1)

    def test_idempotent_reindexing(self):
        """Re-indexing must update chunks and vectors without creating duplicates."""
        self.indexing_service.index_document(self.doc)
        self.assertEqual(DocumentChunk.objects.filter(document=self.doc).count(), 1)

        # Re-index
        index_record = self.indexing_service.index_document(self.doc, force=True)
        self.assertEqual(index_record.status, IndexingStatus.READY)
        self.assertEqual(DocumentChunk.objects.filter(document=self.doc).count(), 1)
        self.assertEqual(self.chroma_service.count_document_vectors(str(self.doc.id)), 1)

    def test_embedding_failure_rolls_back_safely(self):
        """If embedding generation fails, status must become FAILED without corrupted records."""
        failing_provider = MagicMock(spec=BaseEmbeddingProvider)
        failing_provider.get_model_identifier.return_value = "failing-model"
        failing_provider.embed_batch.side_effect = EmbeddingTimeoutError("Gateway timeout")

        failing_service = DocumentIndexingService(
            embedding_provider=failing_provider,
            chroma_service=self.chroma_service
        )

        with self.assertRaises(DocumentIndexingError):
            failing_service.index_document(self.doc)

        index_record = DocumentIndex.objects.get(document=self.doc)
        self.assertEqual(index_record.status, IndexingStatus.FAILED)
        self.assertIn("Gateway timeout", index_record.error_message)
        # Original document and page are intact
        self.assertEqual(self.doc.pages.count(), 1)
        self.assertEqual(self.doc.status, DocumentStatus.READY)


# ==============================================================================
# 5. Indexing API & Authorization Tests
# ==============================================================================

class IndexingAPITestCase(APITestCase):
    """
    Tests API endpoints:
    - POST /api/documents/{id}/index/ (Admin only)
    - GET /api/documents/{id}/index-status/ (Admin, Supervisor, Assigned Engineer)
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.chroma_service = ChromaService(
            persist_directory=Path(self.temp_dir.name),
            collection_name="test_api_indexing"
        )
        self.mock_provider = MockEmbeddingProvider()

        # Users
        self.admin = User.objects.create_user(email="admin@mman.com", password="password123", role=UserRole.ADMIN)
        self.supervisor = User.objects.create_user(email="sup@mman.com", password="password123", role=UserRole.SUPERVISOR)
        self.eng_assigned = User.objects.create_user(email="eng1@mman.com", password="password123", role=UserRole.ENGINEER)
        self.eng_unassigned = User.objects.create_user(email="eng2@mman.com", password="password123", role=UserRole.ENGINEER)

        # Machine & Assignment
        self.machine = Machine.objects.create(machine_code="PRESS-01", name="Stamping Press", created_by=self.admin)
        MachineAssignment.objects.create(machine=self.machine, user=self.eng_assigned, is_active=True, assigned_by=self.admin)

        # Documents
        self.ready_doc = Document.objects.create(
            machine=self.machine,
            title="Press Operations Manual",
            original_filename="press.pdf",
            checksum="d" * 64,
            status=DocumentStatus.READY
        )
        DocumentPage.objects.create(document=self.ready_doc, page_number=1, text="Operating instructions for press.", character_count=33)

        self.unready_doc = Document.objects.create(
            machine=self.machine,
            title="Unextracted Manual",
            checksum="e" * 64,
            status=DocumentStatus.UPLOADED
        )

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_admin_can_trigger_indexing(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('documents:document-index', kwargs={'document_id': self.ready_doc.id})

        with patch('rag.views.DocumentIndexingService') as MockService:
            mock_inst = MockService.return_value
            mock_inst.index_document.return_value = DocumentIndex.objects.create(
                document=self.ready_doc,
                status=IndexingStatus.READY,
                chunk_count=3,
                embedding_model="mock-model"
            )
            response = self.client.post(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["index"]["status"], IndexingStatus.READY)

    def test_supervisor_cannot_trigger_indexing(self):
        self.client.force_authenticate(user=self.supervisor)
        url = reverse('documents:document-index', kwargs={'document_id': self.ready_doc.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_engineer_cannot_trigger_indexing(self):
        self.client.force_authenticate(user=self.eng_assigned)
        url = reverse('documents:document-index', kwargs={'document_id': self.ready_doc.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_trigger_indexing_rejects_unready_document(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('documents:document-index', kwargs={'document_id': self.unready_doc.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("READY", response.data["error"])

    def test_check_index_status_access_matrix(self):
        url = reverse('documents:document-index-status', kwargs={'document_id': self.ready_doc.id})

        # Admin: allowed
        self.client.force_authenticate(user=self.admin)
        resp_admin = self.client.get(url)
        self.assertEqual(resp_admin.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_admin.data["status"], IndexingStatus.PENDING)

        # Supervisor: allowed
        self.client.force_authenticate(user=self.supervisor)
        resp_sup = self.client.get(url)
        self.assertEqual(resp_sup.status_code, status.HTTP_200_OK)

        # Assigned Engineer: allowed
        self.client.force_authenticate(user=self.eng_assigned)
        resp_eng_ok = self.client.get(url)
        self.assertEqual(resp_eng_ok.status_code, status.HTTP_200_OK)

        # Unassigned Engineer: forbidden
        self.client.force_authenticate(user=self.eng_unassigned)
        resp_eng_denied = self.client.get(url)
        self.assertEqual(resp_eng_denied.status_code, status.HTTP_403_FORBIDDEN)


# ==============================================================================
# 6. Reindex Management Command Tests
# ==============================================================================

class ReindexManagementCommandTestCase(TestCase):
    """
    Tests administrative management command `python manage.py reindex_documents`.
    """

    def setUp(self):
        from io import StringIO
        self.out = StringIO()
        self.user = User.objects.create_user(email="cmd_admin@test.com", password="password123", role=UserRole.ADMIN)
        self.machine = Machine.objects.create(machine_code="CMD-01", name="Command Machine", created_by=self.user)
        self.ready_doc = Document.objects.create(
            machine=self.machine,
            title="Command Manual",
            original_filename="cmd.pdf",
            checksum="f" * 64,
            status=DocumentStatus.READY
        )
        DocumentPage.objects.create(document=self.ready_doc, page_number=1, text="Instructions for command test.", character_count=30)

    def test_command_requires_document_id_or_all(self):
        from django.core.management import call_command, CommandError
        with self.assertRaises(CommandError):
            call_command('reindex_documents')

    def test_command_reindex_single_document(self):
        from django.core.management import call_command
        with patch('rag.management.commands.reindex_documents.DocumentIndexingService') as MockService:
            mock_inst = MockService.return_value
            mock_inst.index_document.return_value = DocumentIndex.objects.create(
                document=self.ready_doc,
                status=IndexingStatus.READY,
                chunk_count=2,
                embedding_model="mock-model"
            )
            call_command(
                'reindex_documents',
                document_id=str(self.ready_doc.id),
                force=True,
                stdout=self.out
            )
            output = self.out.getvalue()
            self.assertIn("Successfully indexed: 1", output)

    def test_command_reindex_all_documents(self):
        from django.core.management import call_command
        with patch('rag.management.commands.reindex_documents.DocumentIndexingService') as MockService:
            mock_inst = MockService.return_value
            mock_inst.index_document.return_value = DocumentIndex.objects.create(
                document=self.ready_doc,
                status=IndexingStatus.READY,
                chunk_count=1,
                embedding_model="mock-model"
            )
            call_command('reindex_documents', all=True, force=True, stdout=self.out)
            output = self.out.getvalue()
            self.assertIn("Successfully indexed: 1", output)


# ==============================================================================
# 7. Semantic Retrieval & Grounded Generation Tests (TASK 06)
# ==============================================================================

from rag.services.llm.base import BaseLLMProvider, LLMResult
from rag.services.retrieval_service import (
    SemanticRetrievalService,
    RetrievedChunkContext,
    MachineAccessDeniedError,
    MachineInactiveError,
    MachineNotFoundError,
)
from rag.services.generation_service import (
    GroundedAnswerGenerationService,
    EXACT_ABSTENTION_MESSAGE,
)


class MockLLMProvider(BaseLLMProvider):
    """
    Mock LLM provider returning predetermined answer text.
    """
    def __init__(self, answer_text="Grounding verified answer.", model_identifier="mock-llm"):
        super().__init__(model_identifier=model_identifier, timeout=5)
        self.answer_text = answer_text

    def generate_chat_completion(self, system_instruction: str, user_prompt: str, max_tokens: int = 1000) -> LLMResult:
        return LLMResult(raw_text=self.answer_text, model_identifier=self.model_identifier)


class SemanticRetrievalTestCase(TestCase):
    """
    Tests machine-isolated semantic retrieval, Neon record resolution,
    and access boundary enforcement.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.chroma_service = ChromaService(
            persist_directory=Path(self.temp_dir.name),
            collection_name="test_retrieval_service"
        )
        self.mock_provider = MockEmbeddingProvider()
        self.retrieval_service = SemanticRetrievalService(
            embedding_provider=self.mock_provider,
            chroma_service=self.chroma_service,
        )

        self.admin = User.objects.create_user(email="admin_ret@test.com", password="pass", role=UserRole.ADMIN)
        self.engineer = User.objects.create_user(email="eng_ret@test.com", password="pass", role=UserRole.ENGINEER)
        self.unassigned_engineer = User.objects.create_user(email="uneng_ret@test.com", password="pass", role=UserRole.ENGINEER)

        self.machine1 = Machine.objects.create(machine_code="ROBOT-M1", name="Robot 1", created_by=self.admin)
        self.machine2 = Machine.objects.create(machine_code="ROBOT-M2", name="Robot 2", created_by=self.admin)
        self.inactive_machine = Machine.objects.create(
            machine_code="INACT-01",
            name="Inactive Machine",
            status=MachineStatus.INACTIVE,
            created_by=self.admin
        )

        MachineAssignment.objects.create(machine=self.machine1, user=self.engineer, is_active=True, assigned_by=self.admin)

        # Document and Chunks for Machine 1
        self.doc1 = Document.objects.create(
            machine=self.machine1,
            title="Robot 1 Manual",
            original_filename="r1.pdf",
            checksum="1" * 64,
            status=DocumentStatus.READY
        )
        self.page1 = DocumentPage.objects.create(
            document=self.doc1,
            page_number=5,
            text="Hydraulic filter replacement procedure: Unscrew cap with 24mm wrench.",
            character_count=71
        )
        self.chunk1 = DocumentChunk.objects.create(
            document=self.doc1,
            page=self.page1,
            chunk_index=0,
            text=self.page1.text,
            token_count=10,
            chroma_vector_id=f"doc_{self.doc1.id}_p5_c0",
            embedding_model="mock-model-v1"
        )

        # Index chunk in ChromaDB
        self.chroma_service.upsert_chunks(
            chunk_records=[{
                "id": self.chunk1.chroma_vector_id,
                "text": self.chunk1.text,
                "embedding": [0.123] * 8,
                "metadata": {
                    "document_id": str(self.doc1.id),
                    "machine_id": str(self.machine1.id),
                    "document_page_id": self.page1.id,
                    "page_number": 5,
                    "chunk_index": 0,
                    "embedding_model": "mock-model-v1",
                }
            }],
            embedding_model="mock-model-v1"
        )

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_successful_retrieval_for_assigned_engineer(self):
        results = self.retrieval_service.retrieve_context(
            user=self.engineer,
            machine_id=str(self.machine1.id),
            question="How do I replace the hydraulic filter?"
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].document_title, "Robot 1 Manual")
        self.assertEqual(results[0].page_number, 5)
        self.assertIn("24mm wrench", results[0].chunk_text)

    def test_unassigned_engineer_denied(self):
        from rag.services.retrieval_service import MachineAccessDeniedError
        with self.assertRaises(MachineAccessDeniedError):
            self.retrieval_service.retrieve_context(
                user=self.unassigned_engineer,
                machine_id=str(self.machine1.id),
                question="Filter replacement"
            )

    def test_inactive_machine_rejected(self):
        from rag.services.retrieval_service import MachineInactiveError
        with self.assertRaises(MachineInactiveError):
            self.retrieval_service.retrieve_context(
                user=self.admin,
                machine_id=str(self.inactive_machine.id),
                question="Filter replacement"
            )

    def test_machine_isolation_returns_empty_when_no_manuals_for_machine(self):
        """Querying Machine 2 must not return chunks belonging to Machine 1."""
        results = self.retrieval_service.retrieve_context(
            user=self.admin,
            machine_id=str(self.machine2.id),
            question="How do I replace the hydraulic filter?"
        )
        self.assertEqual(len(results), 0)


class GroundedAnswerGenerationTestCase(TestCase):
    """
    Tests strict prompt grounding, citation validation, and canonical abstention.
    """

    def setUp(self):
        from rag.services.retrieval_service import RetrievedChunkContext
        self.chunk_ctx = RetrievedChunkContext(
            source_id="DOC-9B1DEB-P5-C0",
            document_id=str(uuid.uuid4()),
            document_title="Hydraulic Manual",
            original_filename="manual.pdf",
            machine_id=str(uuid.uuid4()),
            page_number=5,
            chunk_index=0,
            chunk_text="Turn clockwise to open valve V-1.",
            similarity_score=0.95,
            chroma_vector_id="v1"
        )

    def test_supported_question_generates_grounded_answer(self):
        from rag.services.generation_service import GroundedAnswerGenerationService
        mock_llm = MockLLMProvider(
            answer_text="ANSWER: To open the valve, turn clockwise [DOC-9B1DEB-P5-C0].\nSOURCES: [DOC-9B1DEB-P5-C0]"
        )
        service = GroundedAnswerGenerationService(llm_provider=mock_llm)
        result = service.generate_answer(
            machine_name="Robot",
            machine_code="ROB-1",
            question="How to open valve?",
            retrieved_chunks=[self.chunk_ctx]
        )
        self.assertFalse(result.abstained)
        self.assertIn("turn clockwise", result.answer)
        self.assertEqual(len(result.citations), 1)
        self.assertEqual(result.citations[0]["page_number"], 5)
        self.assertEqual(result.citations[0]["document_title"], "Hydraulic Manual")

    def test_unsupported_question_abstains_with_exact_canonical_message(self):
        from rag.services.generation_service import GroundedAnswerGenerationService, EXACT_ABSTENTION_MESSAGE
        mock_llm = MockLLMProvider(
            answer_text=f"ANSWER: {EXACT_ABSTENTION_MESSAGE}\nSOURCES: []"
        )
        service = GroundedAnswerGenerationService(llm_provider=mock_llm)
        result = service.generate_answer(
            machine_name="Robot",
            machine_code="ROB-1",
            question="What is the tire pressure?",
            retrieved_chunks=[self.chunk_ctx]
        )
        self.assertTrue(result.abstained)
        self.assertEqual(result.answer, EXACT_ABSTENTION_MESSAGE)
        self.assertEqual(result.citations, [])

    def test_empty_retrieved_context_abstains_immediately(self):
        from rag.services.generation_service import GroundedAnswerGenerationService, EXACT_ABSTENTION_MESSAGE
        service = GroundedAnswerGenerationService(llm_provider=MockLLMProvider())
        result = service.generate_answer(
            machine_name="Robot",
            machine_code="ROB-1",
            question="Any question?",
            retrieved_chunks=[]
        )
        self.assertTrue(result.abstained)
        self.assertEqual(result.answer, EXACT_ABSTENTION_MESSAGE)
        self.assertEqual(result.citations, [])

    def test_filters_hallucinated_citations(self):
        """Hallucinated source IDs not present in retrieved context must be discarded."""
        from rag.services.generation_service import GroundedAnswerGenerationService
        mock_llm = MockLLMProvider(
            answer_text="ANSWER: Procedure.\nSOURCES: [DOC-9B1DEB-P5-C0, DOC-FABRICATED-P99-C9]"
        )
        service = GroundedAnswerGenerationService(llm_provider=mock_llm)
        result = service.generate_answer(
            machine_name="Robot",
            machine_code="ROB-1",
            question="Procedure?",
            retrieved_chunks=[self.chunk_ctx]
        )
        self.assertEqual(len(result.citations), 1)
        self.assertEqual(result.citations[0]["source_id"], "DOC-9B1DEB-P5-C0")


class RagQueryAPITestCase(APITestCase):
    """
    Tests POST /api/rag/query/ endpoint across roles, validations, and failures.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.chroma_service = ChromaService(
            persist_directory=Path(self.temp_dir.name),
            collection_name="test_api_query"
        )
        self.mock_provider = MockEmbeddingProvider()

        self.admin = User.objects.create_user(email="admin_q@test.com", password="password123", role=UserRole.ADMIN)
        self.supervisor = User.objects.create_user(email="sup_q@test.com", password="password123", role=UserRole.SUPERVISOR)
        self.eng_assigned = User.objects.create_user(email="eng_ass@test.com", password="password123", role=UserRole.ENGINEER)
        self.eng_unassigned = User.objects.create_user(email="eng_unass@test.com", password="password123", role=UserRole.ENGINEER)

        self.machine = Machine.objects.create(machine_code="CNC-Q01", name="CNC Machine", created_by=self.admin)
        self.inactive_machine = Machine.objects.create(
            machine_code="CNC-INACT",
            name="CNC Inactive",
            status=MachineStatus.INACTIVE,
            created_by=self.admin
        )
        MachineAssignment.objects.create(machine=self.machine, user=self.eng_assigned, is_active=True, assigned_by=self.admin)

        self.doc = Document.objects.create(
            machine=self.machine,
            title="CNC Technical Guide",
            original_filename="guide.pdf",
            checksum="9" * 64,
            status=DocumentStatus.READY
        )
        self.page = DocumentPage.objects.create(
            document=self.doc,
            page_number=12,
            text="Lubricate spindle every 40 hours using ISO VG 68 synthetic oil.",
            character_count=67
        )
        self.chunk = DocumentChunk.objects.create(
            document=self.doc,
            page=self.page,
            chunk_index=0,
            text=self.page.text,
            token_count=12,
            chroma_vector_id=f"doc_{self.doc.id}_p12_c0",
            embedding_model="mock-model-v1"
        )

        self.chroma_service.upsert_chunks(
            chunk_records=[{
                "id": self.chunk.chroma_vector_id,
                "text": self.chunk.text,
                "embedding": [0.1] * 8,
                "metadata": {
                    "document_id": str(self.doc.id),
                    "machine_id": str(self.machine.id),
                    "document_page_id": self.page.id,
                    "page_number": 12,
                    "chunk_index": 0,
                    "embedding_model": "mock-model-v1",
                }
            }],
            embedding_model="mock-model-v1"
        )
        self.url = reverse('rag:rag-query')

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_unauthenticated_request_rejected(self):
        response = self.client.post(self.url, {"machine_id": str(self.machine.id), "question": "Lubrication?"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_empty_question_rejected(self):
        self.client.force_authenticate(user=self.eng_assigned)
        response = self.client.post(self.url, {"machine_id": str(self.machine.id), "question": "  "})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inactive_machine_rejected(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(self.url, {"machine_id": str(self.inactive_machine.id), "question": "Lubrication?"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unassigned_engineer_forbidden(self):
        self.client.force_authenticate(user=self.eng_unassigned)
        response = self.client.post(self.url, {"machine_id": str(self.machine.id), "question": "Lubrication?"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch('rag.views.get_retrieval_service')
    @patch('rag.views.GroundedAnswerGenerationService')
    def test_assigned_engineer_receives_grounded_answer(self, MockGen, MockGetSvc):
        MockRet = MockGetSvc.return_value
        from rag.services.generation_service import GroundedAnswer
        from rag.services.retrieval_service import RetrievedChunkContext

        MockRet.return_value.retrieve_context.return_value = [
            RetrievedChunkContext(
                source_id="DOC-999999-P12-C0",
                document_id=str(self.doc.id),
                document_title="CNC Technical Guide",
                original_filename="guide.pdf",
                machine_id=str(self.machine.id),
                page_number=12,
                chunk_index=0,
                chunk_text="Lubricate spindle every 40 hours using ISO VG 68.",
                similarity_score=0.98,
                chroma_vector_id="v1"
            )
        ]
        MockGen.return_value.generate_answer.return_value = GroundedAnswer(
            answer="Lubricate the spindle every 40 hours with ISO VG 68 oil.",
            citations=[{
                "document_id": str(self.doc.id),
                "document_title": "CNC Technical Guide",
                "page_number": 12,
                "source_id": "DOC-999999-P12-C0"
            }],
            abstained=False
        )

        self.client.force_authenticate(user=self.eng_assigned)
        response = self.client.post(self.url, {
            "machine_id": str(self.machine.id),
            "question": "How often should I lubricate the spindle?"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["abstained"])
        self.assertIn("40 hours", response.data["answer"])
        self.assertEqual(len(response.data["citations"]), 1)
        self.assertEqual(response.data["citations"][0]["page_number"], 12)

    @patch('rag.views.get_retrieval_service')
    @patch('rag.views.GroundedAnswerGenerationService')
    def test_supervisor_and_admin_can_query_any_machine(self, MockGen, MockGetSvc):
        MockRet = MockGetSvc.return_value
        from rag.services.generation_service import GroundedAnswer
        MockGen.return_value.generate_answer.return_value = GroundedAnswer(
            answer="Answer.", citations=[], abstained=False
        )
        MockRet.return_value.retrieve_context.return_value = []

        # Supervisor
        self.client.force_authenticate(user=self.supervisor)
        resp_sup = self.client.post(self.url, {"machine_id": str(self.machine.id), "question": "Question?"})
        self.assertEqual(resp_sup.status_code, status.HTTP_200_OK)

        # Admin
        self.client.force_authenticate(user=self.admin)
        resp_admin = self.client.post(self.url, {"machine_id": str(self.machine.id), "question": "Question?"})
        self.assertEqual(resp_admin.status_code, status.HTTP_200_OK)

    @patch('rag.views.get_retrieval_service')
    def test_provider_failure_returns_503(self, MockGetSvc):
        from rag.services.providers.base import EmbeddingTimeoutError
        mock_svc = MockGetSvc.return_value
        mock_svc.retrieve_context.side_effect = EmbeddingTimeoutError("Embedding service timed out")

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(self.url, {"machine_id": str(self.machine.id), "question": "Question?"})
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn("RAG pipeline service error", response.data["error"])

    @patch('rag.views.get_retrieval_service')
    @patch('rag.views.GroundedAnswerGenerationService')
    def test_llm_rate_limit_returns_503_with_category(self, MockGen, MockGetSvc):
        from rag.services.llm.base import LLMRateLimitError
        MockGetSvc.return_value.retrieve_context.return_value = []
        MockGen.return_value.generate_answer.side_effect = LLMRateLimitError("Rate limit 429")

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(self.url, {"machine_id": str(self.machine.id), "question": "Question?"})
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn("RAG pipeline service error", response.data["error"])
        self.assertEqual(response.data.get("error_type"), "llm_rate_limit")


# ==============================================================================
# 8. Google Gemini LLM Provider & Architecture Tests (TASK 1)
# ==============================================================================

from unittest.mock import patch, MagicMock
from django.conf import settings
from google.genai import errors
from rag.services.llm.base import (
    BaseLLMProvider,
    LLMProviderError,
    LLMConfigurationError,
    LLMAuthenticationError,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMQuotaExhaustedError,
    LLMModelUnavailableError,
    LLMResponseMalformedError,
    LLMResult,
)
from rag.services.llm.gemini import GeminiLLMProvider
from rag.services.llm.factory import get_llm_provider
from rag.services.llm.lm_studio import LMStudioLLMProvider
from rag.services.generation_service import (
    GroundedAnswerGenerationService,
    EXACT_ABSTENTION_MESSAGE,
)


class GeminiLLMProviderTestCase(TestCase):
    """
    Tests Google Gemini API adapter configuration, error translations,
    and structured output extraction.
    """

    def setUp(self):
        self.api_key = "AIzaSyFakeTestGeminiApiKey_12345678"
        self.provider = GeminiLLMProvider(
            api_key=self.api_key,
            model_identifier="gemini-2.5-flash",
            timeout=30,
            temperature=0.2,
        )

    def test_gemini_adapter_configuration_success(self):
        """Adapter correctly initializes with explicit configuration."""
        self.assertEqual(self.provider.get_model_identifier(), "gemini-2.5-flash")
        self.assertEqual(self.provider.timeout, 30)
        self.assertEqual(self.provider.temperature, 0.2)
        self.assertEqual(self.provider.api_key, self.api_key)

    def test_missing_api_key_raises_configuration_error(self):
        """Missing or blank API key must raise LLMConfigurationError."""
        with self.assertRaises(LLMConfigurationError) as ctx:
            GeminiLLMProvider(api_key="")
        self.assertIn("GEMINI_API_KEY is not configured", str(ctx.exception))

        with self.assertRaises(LLMConfigurationError):
            GeminiLLMProvider(api_key="   ")

    @patch('google.genai.Client')
    def test_successful_gemini_completion(self, MockClient):
        """Standard successful completion returns normalized LLMResult."""
        mock_instance = MockClient.return_value
        mock_response = MagicMock()
        mock_response.text = "ANSWER: Turn the emergency valve clockwise.\nSOURCES: [DOC-A1-P2-C0]"
        mock_instance.models.generate_content.return_value = mock_response

        result = self.provider.generate_chat_completion(
            system_instruction="System rules",
            user_prompt="User question",
            max_tokens=500,
        )

        self.assertIsInstance(result, LLMResult)
        self.assertEqual(result.model_identifier, "gemini-2.5-flash")
        self.assertIn("emergency valve clockwise", result.raw_text)

    @patch('google.genai.Client')
    def test_invalid_api_key_handling(self, MockClient):
        """403 or invalid API key error from Gemini translates to LLMAuthenticationError."""
        mock_instance = MockClient.return_value
        mock_instance.models.generate_content.side_effect = errors.APIError(
            403, {"error": {"message": "API key not valid. Please pass a valid API key."}}
        )

        with self.assertRaises(LLMAuthenticationError) as ctx:
            self.provider.generate_chat_completion(
                system_instruction="Rules", user_prompt="Question"
            )
        self.assertIn("authentication failed", str(ctx.exception).lower())

    @patch('google.genai.Client')
    def test_provider_timeout_handling(self, MockClient):
        """Timeout during Gemini call translates to LLMTimeoutError."""
        mock_instance = MockClient.return_value
        mock_instance.models.generate_content.side_effect = TimeoutError("Request timed out")

        with self.assertRaises(LLMTimeoutError) as ctx:
            self.provider.generate_chat_completion(
                system_instruction="Rules", user_prompt="Question"
            )
        self.assertIn("timed out", str(ctx.exception).lower())

    @patch('google.genai.Client')
    def test_provider_rate_limit_handling(self, MockClient):
        """429 rate limit translates to LLMRateLimitError."""
        mock_instance = MockClient.return_value
        mock_instance.models.generate_content.side_effect = errors.APIError(
            429, {"error": {"message": "Rate limit exceeded. Please try again later."}}
        )

        with self.assertRaises(LLMRateLimitError) as ctx:
            self.provider.generate_chat_completion(
                system_instruction="Rules", user_prompt="Question"
            )
        self.assertIn("rate limit exceeded", str(ctx.exception).lower())

    @patch('google.genai.Client')
    def test_provider_quota_exhausted_handling(self, MockClient):
        """429 quota exhaustion translates to LLMQuotaExhaustedError."""
        mock_instance = MockClient.return_value
        mock_instance.models.generate_content.side_effect = errors.APIError(
            429, {"error": {"message": "Quota exceeded for quota metric 'GenerateContentRequests'."}}
        )

        with self.assertRaises(LLMQuotaExhaustedError) as ctx:
            self.provider.generate_chat_completion(
                system_instruction="Rules", user_prompt="Question"
            )
        self.assertIn("quota has been exhausted", str(ctx.exception).lower())

    @patch('google.genai.Client')
    def test_model_unavailable_error_handling(self, MockClient):
        """404 model not found translates to LLMModelUnavailableError."""
        mock_instance = MockClient.return_value
        mock_instance.models.generate_content.side_effect = errors.APIError(
            404, {"error": {"message": "models/nonexistent-model is not found for API version v1beta"}}
        )

        with self.assertRaises(LLMModelUnavailableError) as ctx:
            self.provider.generate_chat_completion(
                system_instruction="Rules", user_prompt="Question"
            )
        self.assertIn("unavailable or not found", str(ctx.exception).lower())

    @patch('google.genai.Client')
    def test_malformed_empty_model_response_handling(self, MockClient):
        """Empty or None text response translates to LLMResponseMalformedError."""
        mock_instance = MockClient.return_value
        mock_response = MagicMock()
        mock_response.text = None
        mock_instance.models.generate_content.return_value = mock_response

        with self.assertRaises(LLMResponseMalformedError) as ctx:
            self.provider.generate_chat_completion(
                system_instruction="Rules", user_prompt="Question"
            )
        self.assertIn("empty or unparseable", str(ctx.exception).lower())


class LLMProviderArchitectureTestCase(TestCase):
    """
    Tests provider resolution, environment configuration, citation integrity,
    and ensures NO implicit fallback to LM Studio / Qwen occurs.
    """

    def test_provider_factory_defaults_to_gemini(self):
        """Default provider in get_llm_provider is Gemini."""
        with patch.object(settings, 'LLM_PROVIDER', 'gemini'), \
             patch.object(settings, 'GEMINI_API_KEY', 'fake_key_123'), \
             patch.object(settings, 'GEMINI_MODEL', 'gemini-2.5-flash'):
            provider = get_llm_provider()
            self.assertIsInstance(provider, GeminiLLMProvider)
            self.assertEqual(provider.get_model_identifier(), "gemini-2.5-flash")

    def test_provider_factory_rejects_missing_gemini_key(self):
        """Factory raises LLMConfigurationError if GEMINI_API_KEY is missing when selecting Gemini."""
        with patch.object(settings, 'LLM_PROVIDER', 'gemini'),              patch.object(settings, 'GEMINI_API_KEY', ''):
            with self.assertRaises(LLMConfigurationError):
                get_llm_provider()

    def test_ensuring_qwen_lm_studio_is_not_implicit_fallback(self):
        """
        When Gemini fails (e.g. network timeout or invalid key), the error must be propagated.
        The system must NEVER silently fallback to LM Studio / Qwen.
        """
        mock_gemini = MagicMock(spec=GeminiLLMProvider)
        mock_gemini.generate_chat_completion.side_effect = LLMAuthenticationError(
            "Gemini authentication failed"
        )

        service = GroundedAnswerGenerationService(llm_provider=mock_gemini)

        chunk = MagicMock()
        chunk.source_id = "DOC-A-P1-C0"
        chunk.document_id = "doc-1"
        chunk.document_title = "Title"
        chunk.page_number = 1
        chunk.chunk_text = "Content"

        with self.assertRaises(LLMAuthenticationError):
            service.generate_answer(
                machine_name="Press",
                machine_code="P-01",
                question="Operating pressure?",
                retrieved_chunks=[chunk]
            )

    def test_explicit_lm_studio_only_when_requested(self):
        """LM Studio is only instantiated when explicitly requested by name."""
        provider = get_llm_provider(provider_name="lm_studio")
        self.assertIsInstance(provider, LMStudioLLMProvider)

    def test_unsupported_provider_raises_configuration_error(self):
        """Requesting an unknown provider raises LLMConfigurationError."""
        with self.assertRaises(LLMConfigurationError):
            get_llm_provider(provider_name="unsupported_provider_xyz")

    def test_fabricated_citations_are_strictly_rejected(self):
        """Fabricated citations return empty citations and never attach arbitrary fallbacks."""
        mock_llm = MagicMock(spec=BaseLLMProvider)
        mock_llm.generate_chat_completion.return_value = LLMResult(
            raw_text="ANSWER: Pressure is 10 bar.\nSOURCES: [DOC-FAKE-P99-C99]",
            model_identifier="gemini-2.5-flash"
        )
        service = GroundedAnswerGenerationService(llm_provider=mock_llm)

        real_chunk = MagicMock()
        real_chunk.source_id = "DOC-REAL-P1-C0"
        real_chunk.document_id = "doc-real"
        real_chunk.document_title = "Real Manual"
        real_chunk.page_number = 1
        real_chunk.chunk_text = "Real content."

        result = service.generate_answer(
            machine_name="Robot",
            machine_code="ROB-01",
            question="Pressure?",
            retrieved_chunks=[real_chunk]
        )
        self.assertFalse(result.abstained)
        self.assertEqual(result.citations, [], "Fabricated citation must not be attached!")

    def test_abstention_strict_zero_citations(self):
        """When LLM abstains, citations must strictly be empty."""
        mock_llm = MagicMock(spec=BaseLLMProvider)
        mock_llm.generate_chat_completion.return_value = LLMResult(
            raw_text=f"ANSWER: {EXACT_ABSTENTION_MESSAGE}\nSOURCES: [DOC-REAL-P1-C0]",
            model_identifier="gemini-2.5-flash"
        )
        service = GroundedAnswerGenerationService(llm_provider=mock_llm)

        real_chunk = MagicMock()
        real_chunk.source_id = "DOC-REAL-P1-C0"
        real_chunk.document_id = "doc-real"
        real_chunk.document_title = "Real Manual"
        real_chunk.page_number = 1
        real_chunk.chunk_text = "Real content."

        result = service.generate_answer(
            machine_name="Robot",
            machine_code="ROB-01",
            question="Unsupported question?",
            retrieved_chunks=[real_chunk]
        )
        self.assertTrue(result.abstained)
        self.assertEqual(result.answer, EXACT_ABSTENTION_MESSAGE)
        self.assertEqual(result.citations, [], "Abstention must have zero citations!")



# ==============================================================================
# 9. PostgreSQL + pgvector Indexing & Retrieval Tests
# ==============================================================================

from django.test import override_settings
from rag.services.pgvector_retrieval_service import PgvectorRetrievalService
from rag.services.retrieval_service import get_retrieval_service


@override_settings(VECTOR_BACKEND='pgvector')
class PgvectorIndexingAndRetrievalTestCase(TestCase):
    """
    Tests end-to-end pgvector indexing, exact cosine-distance retrieval,
    machine isolation, and exclusion of invalidated/unembedded chunks.
    """

    def setUp(self):
        self.admin = User.objects.create_user(
            email="pgv_admin@test.com", password="password123", role=UserRole.ADMIN
        )
        self.eng1 = User.objects.create_user(
            email="pgv_eng1@test.com", password="password123", role=UserRole.ENGINEER
        )
        self.eng2 = User.objects.create_user(
            email="pgv_eng2@test.com", password="password123", role=UserRole.ENGINEER
        )

        self.machine_hp200 = Machine.objects.create(
            machine_code="PGV-HP200", name="HP-200 Hydraulic Press", created_by=self.admin
        )
        self.machine_ac90 = Machine.objects.create(
            machine_code="PGV-AC90", name="AC-90 Air Compressor", created_by=self.admin
        )

        MachineAssignment.objects.create(
            machine=self.machine_hp200, user=self.eng1, is_active=True, assigned_by=self.admin
        )
        MachineAssignment.objects.create(
            machine=self.machine_ac90, user=self.eng2, is_active=True, assigned_by=self.admin
        )

        self.doc_hp200 = Document.objects.create(
            machine=self.machine_hp200,
            title="HP 200 Operations Manual",
            original_filename="HP200_Operations_Rev1_0.pdf",
            checksum="1" * 64,
            status=DocumentStatus.READY,
        )
        DocumentPage.objects.create(
            document=self.doc_hp200,
            page_number=2,
            text="Nominal operating hydraulic pressure is 120 to 140 bar. E17 low-pressure alarm triggers below 110 bar.",
            character_count=102,
        )

        self.doc_ac90 = Document.objects.create(
            machine=self.machine_ac90,
            title="AC 90 Operations Manual",
            original_filename="AC90_Operations_Maintenance_Rev1_0.pdf",
            checksum="2" * 64,
            status=DocumentStatus.READY,
        )
        DocumentPage.objects.create(
            document=self.doc_ac90,
            page_number=1,
            text="AC-90 discharge air pressure is 7.5 to 8.5 bar. High discharge temperature shutdown at 110 C.",
            character_count=93,
        )

        self.provider_768 = MockEmbeddingProvider(
            model_identifier="text-embedding-nomic-embed-text-v1.5",
            dimension=768,
        )

    def test_factory_returns_pgvector_retrieval_service(self):
        svc = get_retrieval_service(embedding_provider=self.provider_768)
        self.assertIsInstance(svc, PgvectorRetrievalService)

    def test_pgvector_indexing_and_cosine_retrieval(self):
        indexing_svc = DocumentIndexingService(
            embedding_provider=self.provider_768,
            vector_backend='pgvector',
        )
        idx_hp = indexing_svc.index_document(self.doc_hp200)
        idx_ac = indexing_svc.index_document(self.doc_ac90)

        self.assertEqual(idx_hp.status, IndexingStatus.READY)
        self.assertEqual(idx_ac.status, IndexingStatus.READY)

        hp_chunk = DocumentChunk.objects.get(document=self.doc_hp200)
        self.assertIsNotNone(hp_chunk.embedding)
        self.assertEqual(len(hp_chunk.embedding), 768)
        self.assertIsNotNone(hp_chunk.embedding_updated_at)

        retrieval_svc = get_retrieval_service(embedding_provider=self.provider_768)

        # Assigned engineer retrieves HP-200 chunk with canonical page 2
        results = retrieval_svc.retrieve_context(
            user=self.eng1,
            machine_id=str(self.machine_hp200.id),
            question="What is the nominal operating hydraulic pressure?",
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].document_id, str(self.doc_hp200.id))
        self.assertEqual(results[0].page_number, 2)
        self.assertGreaterEqual(results[0].similarity_score, 0.99)

        # Cross-machine authorization blocked for eng1 on AC-90
        with self.assertRaises(MachineAccessDeniedError):
            retrieval_svc.retrieve_context(
                user=self.eng1,
                machine_id=str(self.machine_ac90.id),
                question="What is the discharge air pressure?",
            )

        # Invalidating DocumentIndex excludes chunks from pgvector retrieval
        idx_hp.status = IndexingStatus.FAILED
        idx_hp.save(update_fields=['status'])
        results_after_invalidation = retrieval_svc.retrieve_context(
            user=self.eng1,
            machine_id=str(self.machine_hp200.id),
            question="What is the nominal operating hydraulic pressure?",
        )
        self.assertEqual(results_after_invalidation, [])
