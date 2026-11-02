import os
import sys

sys.path.insert(0, os.path.abspath('backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from machines.models import Machine
from documents.models import Document, DocumentPage
from rag.models import DocumentIndex, DocumentChunk, IndexingStatus
from rag.services.chroma_service import ChromaService

def inspect_hp200_consistency():
    print("=" * 80)
    print("  HP-200 CONSISTENCY VERIFICATION (POSTGRESQL & CHROMADB)")
    print("=" * 80)

    machine = Machine.objects.filter(machine_code='M-HP200').first()
    assert machine, "Machine M-HP200 not found"

    print(f"Machine: {machine.name} (Code: {machine.machine_code}, ID: {machine.id})")
    print(f"Status: {machine.status}")

    active_docs = list(Document.objects.filter(machine=machine, is_active=True))
    print(f"\nActive Document Count: {len(active_docs)}")

    chroma_service = ChromaService()
    collection = chroma_service.get_or_create_collection(embedding_model="text-embedding-nomic-embed-text-v1.5")
    assert collection is not None, "Chroma collection could not be loaded"

    total_chunks_across_machine = 0
    total_vectors_across_machine = 0

    for doc in active_docs:
        print(f"\n--- Document: '{doc.title}' (ID: {doc.id}) ---")
        print(f"  Filename: {doc.original_filename} | File Size: {doc.file_size} bytes | SHA-256: {doc.checksum}")
        print(f"  Document Status: {doc.status} | Active: {doc.is_active}")

        # 1. Extracted page count
        pages = list(DocumentPage.objects.filter(document=doc).order_by('page_number'))
        print(f"  Extracted Page Count: {len(pages)} (Reported page_count: {doc.page_count})")
        for p in pages:
            print(f"    Page {p.page_number}: {p.character_count} chars | First 40: '{p.text[:40].strip()}'")

        # 2. DocumentIndex status
        index_rec = getattr(doc, 'index_record', None)
        if index_rec:
            print(f"  DocumentIndex Status: {index_rec.status} | Recorded Chunks: {index_rec.chunk_count} | Model: {index_rec.embedding_model}")
        else:
            print(f"  DocumentIndex Status: NO RECORD")

        # 3. PostgreSQL DocumentChunk count
        chunks = list(DocumentChunk.objects.filter(document=doc).order_by('page__page_number', 'chunk_index'))
        print(f"  PostgreSQL DocumentChunk Count: {len(chunks)}")
        total_chunks_across_machine += len(chunks)

        # 4. ChromaDB vector count
        chroma_res = collection.get(where={"document_id": str(doc.id)}, include=["metadatas", "embeddings", "documents"])
        chroma_ids = chroma_res.get("ids", [])
        print(f"  ChromaDB Vector Count: {len(chroma_ids)}")
        total_vectors_across_machine += len(chroma_ids)

        # 5. Matching PostgreSQL chunk IDs and ChromaDB vector IDs
        neon_v_ids = set(c.chroma_vector_id for c in chunks)
        chroma_v_ids = set(chroma_ids)
        ids_match = (neon_v_ids == chroma_v_ids)
        print(f"  Chunk/Vector IDs Match: {ids_match} (Neon: {len(neon_v_ids)}, Chroma: {len(chroma_v_ids)})")
        if not ids_match:
            print(f"    Difference (Neon - Chroma): {neon_v_ids - chroma_v_ids}")
            print(f"    Difference (Chroma - Neon): {chroma_v_ids - neon_v_ids}")

        # 6. Correct machine ID, document ID, and canonical 1-based page number for every chunk
        all_metadata_valid = True
        for c in chunks:
            if c.page.page_number not in [1, 2, 3]:
                all_metadata_valid = False
                print(f"    INVALID Page Number in Chunk {c.id}: {c.page.page_number}")
            if str(c.document_id) != str(doc.id):
                all_metadata_valid = False
                print(f"    INVALID Document ID in Chunk {c.id}: {c.document_id}")
            if str(c.document.machine_id) != str(machine.id):
                all_metadata_valid = False
                print(f"    INVALID Machine ID in Chunk {c.id}: {c.document.machine_id}")

        for meta in chroma_res.get("metadatas", []):
            if str(meta.get("machine_id")) != str(machine.id):
                all_metadata_valid = False
                print(f"    INVALID Chroma Machine ID: {meta.get('machine_id')}")
            if str(meta.get("document_id")) != str(doc.id):
                all_metadata_valid = False
                print(f"    INVALID Chroma Document ID: {meta.get('document_id')}")
            if meta.get("page_number") not in [1, 2, 3]:
                all_metadata_valid = False
                print(f"    INVALID Chroma Page Number: {meta.get('page_number')}")

        print(f"  Canonical Metadata Integrity (Machine, Document, 1-based Pages): {'VALID' if all_metadata_valid else 'INVALID'}")

        # 7. Embedding dimension
        embeddings = chroma_res.get("embeddings", [])
        if embeddings is not None and len(embeddings) > 0:
            dim = len(embeddings[0])
            print(f"  Vector Embedding Dimension: {dim} (Expected: 768 for Nomic Embed Text v1.5)")
        else:
            print(f"  Vector Embedding Dimension: N/A (embeddings omitted in get query)")

    print("\n" + "=" * 80)
    print(f"  TOTALS FOR M-HP200: {len(active_docs)} Active Docs | {total_chunks_across_machine} DB Chunks | {total_vectors_across_machine} Chroma Vectors")
    print("=" * 80)

if __name__ == "__main__":
    inspect_hp200_consistency()

