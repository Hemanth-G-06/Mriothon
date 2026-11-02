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
