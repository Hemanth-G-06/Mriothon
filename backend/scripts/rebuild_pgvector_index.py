"""
Phase 4: Re-index ONLY the 3 genuine canonical PDFs for M-HP200 and M-AC90 into pgvector.
"""
import os
import sys
import hashlib
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ['VECTOR_BACKEND'] = 'pgvector'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.conf import settings
from documents.models import Document, DocumentStatus, DocumentPage
from rag.models import DocumentChunk, DocumentIndex, IndexingStatus
from rag.services.indexing_service import DocumentIndexingService

GENUINE_HASHES = {
    "8c36c6332ce1523572bc11f525dca831f9ad539a292847127901294777860bdb": ("M-HP200", "HP200_Operations_Rev1_0.pdf"),
    "8562da78dad91c495d79c777ea7d119bb29de39471eee53db112d941a9529f17": ("M-HP200", "HP200_Maintenance_Rev1_0.pdf"),
    "0415298deabaa451ba676cbc2db5ae54ed36b2f7dfe67e02e91661d3f90ed43b": ("M-AC90", "AC90_Operations_Maintenance_Rev1_0.pdf"),
}

assert settings.VECTOR_BACKEND == 'pgvector', f"Expected pgvector, got {settings.VECTOR_BACKEND}"

print("=== Phase 4: Rebuilding pgvector Knowledge Base from Genuine PDFs ===")
print(f"VECTOR_BACKEND = {settings.VECTOR_BACKEND}")
print(f"EMBEDDING_PROVIDER = {settings.EMBEDDING_PROVIDER}")
print(f"LM_STUDIO_EMBEDDING_MODEL = {settings.LM_STUDIO_EMBEDDING_MODEL}\n")

target_docs = Document.objects.filter(
    is_active=True,
    status=DocumentStatus.READY,
    machine__machine_code__in=["M-HP200", "M-AC90"],
).select_related("machine").order_by("machine__machine_code", "title")

service = DocumentIndexingService()
indexed_docs = []

for doc in target_docs:
    file_bytes = Path(doc.file.path).read_bytes()
    sha256 = hashlib.sha256(file_bytes).hexdigest()
    if sha256 not in GENUINE_HASHES:
        print(f"  [SKIP] {doc.title} ({doc.id}) does not match genuine SHA-256 ({sha256})")
        continue
    expected_machine, canonical_name = GENUINE_HASHES[sha256]
    assert doc.machine.machine_code == expected_machine, (
        f"Machine mismatch for {doc.id}: {doc.machine.machine_code} != {expected_machine}"
    )

    print(f"Indexing [{doc.machine.machine_code}] '{doc.title}' ({canonical_name}, {len(file_bytes)} bytes)...")
    idx_record = service.index_document(doc, force=True)

    pages = DocumentPage.objects.filter(document=doc).order_by('page_number')
    chunks = DocumentChunk.objects.filter(document=doc).select_related('page').order_by('page__page_number', 'chunk_index')
    non_null_Count = chunks.filter(embedding__isnull=False).count()

    print(f"  -> Index Status: {idx_record.status}")
    print(f"  -> Pages: {pages.count()} (page numbers: {[p.page_number for p in pages]})")
    print(f"  -> Chunks: {chunks.count()} | Non-null pgvector embeddings: {non_null_Count}")
    for c in chunks:
        emb_len = len(c.embedding) if c.embedding is not None else 0
        print(
            f"     Chunk id={c.id} | page={c.page.page_number} | idx={c.chunk_index} | "
            f"tokens={c.token_count} | dim={emb_len} | model={c.embedding_model} | "
            f"updated_at={c.embedding_updated_at}"
        )
        assert emb_len == 768, f"Expected 768 dims, got {emb_len}"
    assert idx_record.status == IndexingStatus.READY
    assert chunks.count() == non_null_Count and non_null_Count > 0
    indexed_docs.append(doc.id)

print(f"\n=== Summary ===")
print(f"Total genuine documents indexed into pgvector: {len(indexed_docs)}")
total_pgvec = DocumentChunk.objects.filter(embedding__isnull=False).count()
print(f"Total DocumentChunk rows in DB with non-null embedding: {total_pgvec}")
non_genuine_pgvec = DocumentChunk.objects.exclude(document_id__in=indexed_docs).filter(embedding__isnull=False).count()
print(f"Non-genuine chunks with non-null embedding: {non_genuine_pgvec} (must be 0)")
assert non_genuine_pgvec == 0
print("[PASS] Phase 4 knowledge base rebuild verified!")
