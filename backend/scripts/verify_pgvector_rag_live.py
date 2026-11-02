"""
FINAL ACCEPTANCE AUDIT — Live Verification Script (Read-Only on Corpus + Live RAG Queries)

Verifies:
- Section 3: Citation regression verification (every explicit DOC-*-P*-C* source ID in Gemini's
  answer is present in returned citations, maps to canonical DocumentChunk & DocumentPage.page_number,
  no cited page is dropped, no chunk_index=0 mistaken for page_number, unsupported answers have 0 citations).
- Section 4: ChromaDB retirement audit (VECTOR_BACKEND='pgvector', PgvectorRetrievalService active,
  DocumentIndexingService resolves to 'pgvector', no fallback to ChromaDB, archive directory untouched).
- Section 5: Final data integrity reconciliation (read-only audit of all machines, documents,
  pages, chunks, 768-dim pgvector embeddings, DocumentIndex records, and ineligible test documents).
"""
import hashlib
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.conf import settings
from rest_framework.test import APIClient

from accounts.models import User, UserRole
from machines.models import Machine, MachineAssignment
from machines.serializers import MachineListSerializer
from documents.models import Document, DocumentPage, DocumentStatus
from documents.services import get_accessible_documents_queryset
from rag.models import DocumentChunk, DocumentIndex, IndexingStatus
from rag.services.indexing_service import DocumentIndexingService
from rag.services.retrieval_service import get_retrieval_service
from rag.services.pgvector_retrieval_service import PgvectorRetrievalService
from rag.services.generation_service import EXACT_ABSTENTION_MESSAGE
from rag.services.chroma_service import ChromaService

print("======================================================================")
print("  FINAL ACCEPTANCE AUDIT: DATA INTEGRITY, CHROMA RETIREMENT & CITATIONS")
print("======================================================================\n")

# ==============================================================================
# SECTION 4: CHROMADB RETIREMENT AUDIT
# ==============================================================================
print("--- [Section 4] ChromaDB Retirement & Active Runtime Audit ---")
assert settings.VECTOR_BACKEND == 'pgvector', f"Expected VECTOR_BACKEND='pgvector', got {settings.VECTOR_BACKEND!r}"
retrieval_svc = get_retrieval_service()
indexing_svc = DocumentIndexingService()
assert isinstance(retrieval_svc, PgvectorRetrievalService), f"Expected PgvectorRetrievalService, got {type(retrieval_svc).__name__}"
assert indexing_svc._resolve_vector_backend() == 'pgvector', "DocumentIndexingService did not resolve to 'pgvector'"

# Verify PgvectorRetrievalService does not reference ChromaService
import inspect
pgv_source = inspect.getsource(PgvectorRetrievalService)
assert "ChromaService" not in pgv_source and "chroma_service" not in pgv_source, (
    "PgvectorRetrievalService must not reference ChromaService or fallback to ChromaDB!"
)

# Verify Chroma persistence directory remains untouched as an inactive archive
chroma_dir = Path(settings.CHROMA_PERSIST_DIRECTORY)
assert chroma_dir.exists(), f"Chroma archive directory missing: {chroma_dir}"
chroma_archive_count = ChromaService().get_or_create_collection().count()
print(f"[PASS] settings.VECTOR_BACKEND = '{settings.VECTOR_BACKEND}'")
print(f"[PASS] get_retrieval_service() -> {type(retrieval_svc).__name__} (no ChromaDB fallback)")
print(f"[PASS] DocumentIndexingService._resolve_vector_backend() -> '{indexing_svc._resolve_vector_backend()}'")
print(f"[PASS] Inactive Chroma archive directory preserved at '{chroma_dir}' ({chroma_archive_count} archived vectors)")

# ==============================================================================
# SECTION 5: FINAL DATA INTEGRITY RECONCILIATION (READ-ONLY)
# ==============================================================================
print("\n--- [Section 5] Final Data Integrity Reconciliation (Read-Only) ---")
GENUINE_SHA256 = {
    "8c36c6332ce1523572bc11f525dca831f9ad539a292847127901294777860bdb": ("M-HP200", "HP200_Operations_Rev1_0.pdf", 91891),
    "8562da78dad91c495d79c777ea7d119bb29de39471eee53db112d941a9529f17": ("M-HP200", "HP200_Maintenance_Rev1_0.pdf", 91341),
    "0415298deabaa451ba676cbc2db5ae54ed36b2f7dfe67e02e91661d3f90ed43b": ("M-AC90", "AC90_Operations_Maintenance_Rev1_0.pdf", 98988),
}

hp200 = Machine.objects.get(machine_code="M-HP200")
ac90 = Machine.objects.get(machine_code="M-AC90")

all_active_docs = Document.objects.filter(is_active=True).select_related('machine').order_by('machine__machine_code', 'title')
genuine_ready_ids = []
ineligible_docs = []

for doc in all_active_docs:
    idx = DocumentIndex.objects.filter(document=doc).first()
    idx_status = idx.status if idx else "NONE"
    pages = list(DocumentPage.objects.filter(document=doc).order_by('page_number'))
    chunks = list(DocumentChunk.objects.filter(document=doc).select_related('page').order_by('page__page_number', 'chunk_index'))
    emb_chunks = [c for c in chunks if c.embedding is not None]

    if doc.machine_id in (hp200.id, ac90.id):
        file_bytes = Path(doc.file.path).read_bytes()
        sha = hashlib.sha256(file_bytes).hexdigest()
        assert sha in GENUINE_SHA256, f"Unexpected file SHA-256 on {doc.machine.machine_code}: {sha}"
        exp_code, exp_name, exp_size = GENUINE_SHA256[sha]
        assert doc.machine.machine_code == exp_code
        assert len(file_bytes) == exp_size
        assert doc.status == DocumentStatus.READY
        assert idx_status == IndexingStatus.READY
        assert [p.page_number for p in pages] == [1, 2, 3], f"Expected pages [1,2,3], got {[p.page_number for p in pages]}"
        assert len(chunks) == 3 and len(emb_chunks) == 3
        for c in chunks:
            assert len(c.embedding) == 768, f"Expected 768 dims, got {len(c.embedding)}"
            assert c.embedding_model == "text-embedding-nomic-embed-text-v1.5"
            assert c.embedding_updated_at is not None
            assert c.page.page_number in (1, 2, 3)
            assert c.chunk_index == 0
        genuine_ready_ids.append(str(doc.id))
        print(
            f"[PASS] Genuine Doc [{doc.machine.machine_code}] id={doc.id} | title='{doc.title}' | "
            f"status={doc.status} | index={idx_status} | pages=3 (1..3) | chunks=3 | "
            f"pgvector=3x768d | sha256={sha[:12]}..."
        )
    else:
        assert idx_status == IndexingStatus.FAILED, f"Non-genuine doc {doc.id} has index status {idx_status}, expected FAILED"
        assert len(emb_chunks) == 0, f"Non-genuine doc {doc.id} has {len(emb_chunks)} embeddings, expected 0"
        ineligible_docs.append((doc.machine.machine_code, str(doc.id), idx_status, len(chunks), len(emb_chunks)))

assert len(genuine_ready_ids) == 3, f"Expected 3 genuine READY documents, found {len(genuine_ready_ids)}"
print(f"[PASS] Reconciled {len(genuine_ready_ids)} genuine READY documents (9 pages, 9 chunks, 9 x 768-dim pgvector embeddings)")
print(f"[PASS] Reconciled {len(ineligible_docs)} legacy/test documents: all {len(ineligible_docs)} have DocumentIndex=FAILED and 0 pgvector embeddings (ineligible for retrieval)")

# ==============================================================================
# SECTION 3: CITATION REGRESSION & LIVE PGVECTOR + GEMINI RAG VERIFICATION
# ==============================================================================
print("\n--- [Section 3] Citation Regression & Live RAG Verification ---")

eng_hp200 = User.objects.filter(
    role=UserRole.ENGINEER,
    machine_assignments__machine=hp200,
    machine_assignments__is_active=True,
).first()
assert eng_hp200 is not None
assert not MachineAssignment.objects.filter(machine=ac90, user=eng_hp200, is_active=True).exists()
admin_user = User.objects.filter(role=UserRole.ADMIN, is_active=True).first()

# Map all canonical source_ids in PostgreSQL to (document_id, page_number, chunk_index)
canonical_source_map = {}
for c in DocumentChunk.objects.filter(document_id__in=genuine_ready_ids).select_related('document', 'page'):
    src_id = RetrievalServiceClass = SemanticRetrievalService = None
    from rag.services.retrieval_service import SemanticRetrievalService as _SRS
    sid = _SRS.format_source_id(str(c.document_id), c.page.page_number, c.chunk_index)
    canonical_source_map[sid] = {
        "chunk_uuid": str(c.id),
        "document_id": str(c.document_id),
        "document_title": c.document.title,
        "page_number": c.page.page_number,
        "chunk_index": c.chunk_index,
    }
print(f"[INFO] Canonical source IDs in pgvector corpus ({len(canonical_source_map)}):")
for sid, meta in sorted(canonical_source_map.items()):
    print(f"       {sid} -> doc={meta['document_title']} | page_number={meta['page_number']} | chunk_index={meta['chunk_index']}")

client = APIClient()

def verify_citation_and_pdf_stream(auth_user, citation, machine):
    doc_id = str(citation['document_id'])
    page_num = int(citation['page_number'])
    src_id = citation.get('source_id') or citation.get('chunk_id')

    assert src_id in canonical_source_map, f"Citation source_id {src_id!r} not in canonical_source_map!"
    expected = canonical_source_map[src_id]
    assert doc_id == expected["document_id"], f"doc_id mismatch for {src_id}: {doc_id} != {expected['document_id']}"
    assert page_num == expected["page_number"], f"page_number mismatch for {src_id}: {page_num} != {expected['page_number']}"
    assert page_num >= 1, f"page_number must be 1-based (>=1), got {page_num} (chunk_index={expected['chunk_index']})"
    assert DocumentPage.objects.filter(document_id=doc_id, page_number=page_num).exists()
    assert Document.objects.filter(id=doc_id, machine=machine).exists()

    client.force_authenticate(user=auth_user)
    resp = client.get(f"/api/documents/{doc_id}/pdf/", HTTP_HOST="localhost")
    assert resp.status_code in (200, 206), f"PDF stream returned {resp.status_code} for {doc_id}"
    content = b"".join(resp.streaming_content) if getattr(resp, 'streaming_content', None) else resp.content
    assert content.startswith(b"%PDF-"), f"Invalid PDF header for {doc_id}"

test_cases = [
    {
        "name": "Q1 (Supported - HP-200 Operations: Pressure & E17 Alarm)",
        "user": eng_hp200,
        "machine": hp200,
        "question": "What is the normal operating hydraulic pressure range for the HP-200 press, and when does the E17 low hydraulic pressure alarm trigger?",
        "expect_status": 200,
        "expect_abstained": False,
        "expect_substrings": ["120", "140", "110"],
    },
    {
        "name": "Q2 (Supported - HP-200 Maintenance: Oil Grade & Temperature Thresholds)",
        "user": eng_hp200,
        "machine": hp200,
        "question": "Which hydraulic fluid grade is specified for the HP-200, and what are the oil temperature warning and high-stop thresholds?",
        "expect_status": 200,
        "expect_abstained": False,
        "expect_substrings": ["H46", "60", "65"],
    },
    {
        "name": "Q3 (Supported - AC-90 Operations & Maintenance: Pressure & High-Temp Stop)",
        "user": admin_user,
        "machine": ac90,
        "question": "What are the normal operating discharge pressure range and high discharge temperature shutdown threshold for the AC-90 air compressor?",
        "expect_status": 200,
        "expect_abstained": False,
        "expect_substrings": ["7.0", "8.0", "105"],
    },
    {
        "name": "Q4 (Unsupported - Out-of-Scope Question on HP-200)",
        "user": eng_hp200,
        "machine": hp200,
        "question": "What is the exact copper wire gauge for rewinding the main drive electric motor stator and the ladder logic rung number for the safety relay?",
        "expect_status": 200,
        "expect_abstained": True,
        "expect_substrings": [EXACT_ABSTENTION_MESSAGE],
    },
]

for idx, tc in enumerate(test_cases):
    if idx > 0:
        print("  [Pacing 25s for Gemini Free Tier rate limits...]")
        time.sleep(25)

    print(f"\n-> {tc['name']}")
    client.force_authenticate(user=tc["user"])
    resp = client.post(
        "/api/rag/query/",
        {"machine_id": str(tc["machine"].id), "question": tc["question"]},
        format="json",
        HTTP_HOST="localhost",
    )
    assert resp.status_code == tc["expect_status"], f"Expected {tc['expect_status']}, got {resp.status_code}"
    data = resp.data
    answer = data.get("answer", "")
    abstained = data.get("abstained", False)
    citations = data.get("citations", [])

    # Extract explicit DOC-XXXXXX-PX-CX IDs referenced in answer text
    explicit_ids_in_answer = sorted(set(re.findall(r'DOC-[A-Z0-9]+-P\d+-C\d+', answer)))
    returned_source_ids = sorted(set((c.get('source_id') or c.get('chunk_id')) for c in citations))

    print(f"   HTTP {resp.status_code} | Abstained: {abstained} | Citations: {len(citations)}")
    print(f"   Explicit IDs in Answer: {explicit_ids_in_answer}")
    print(f"   Returned Citation IDs:  {returned_source_ids}")
    print(f"   Answer: {answer[:260]}{'...' if len(answer) > 260 else ''}")

    assert abstained == tc["expect_abstained"]
    for sub in tc["expect_substrings"]:
        assert sub.lower() in answer.lower(), f"Expected '{sub}' in answer: {answer}"

    if tc["expect_abstained"]:
        assert answer.strip() == EXACT_ABSTENTION_MESSAGE
        assert len(citations) == 0, f"Expected 0 citations on abstention, got {len(citations)}"
        print("   [PASS] Unsupported question abstained with exact canonical message and 0 citations.")
    else:
        assert len(citations) >= 1
        # Verify NO explicit source ID mentioned in the answer was dropped
        for exp_id in explicit_ids_in_answer:
            assert exp_id in returned_source_ids, (
                f"REGRESSION: Explicit source ID {exp_id} in answer was dropped from citations ({returned_source_ids})!"
            )
        for cit in citations:
            sid = cit.get('source_id') or cit.get('chunk_id')
            print(
                f"     * Citation: '{cit['document_title']}' | page_number={cit['page_number']} | "
                f"source_id={sid} | doc_id={cit['document_id']}"
            )
            verify_citation_and_pdf_stream(tc["user"], cit, tc["machine"])
        print("   [PASS] Every explicit source ID mapped to canonical DocumentChunk & DocumentPage.page_number, no cited page dropped, PDF stream verified.")

# Q5: Cross-machine authorization check
print("\n-> Q5 (Cross-Machine Authorization Enforcement: HP-200 Engineer querying AC-90)")
client.force_authenticate(user=eng_hp200)
resp_cross = client.post(
    "/api/rag/query/",
    {"machine_id": str(ac90.id), "question": "What is the normal operating pressure for AC-90?"},
    format="json",
    HTTP_HOST="localhost",
)
assert resp_cross.status_code == 403
print(f"   HTTP {resp_cross.status_code} Forbidden — Cross-machine query blocked.")

# Also verify Engineer cannot access AC-90 PDF stream directly
ac90_doc = Document.objects.get(machine=ac90, is_active=True)
resp_pdf_cross = client.get(f"/api/documents/{ac90_doc.id}/pdf/", HTTP_HOST="localhost")
assert resp_pdf_cross.status_code == 403, f"Expected 403 on cross-machine PDF stream, got {resp_pdf_cross.status_code}"
print(f"   HTTP {resp_pdf_cross.status_code} Forbidden — Cross-machine PDF stream blocked.")

print("\n======================================================================")
print("  SECTIONS 3, 4 & 5 LIVE AUDIT VERIFICATIONS PASSED!")
print("======================================================================")
