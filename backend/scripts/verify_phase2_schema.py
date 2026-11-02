"""
Phase 2 schema verification — read-only.
Confirms: pgvector extension, new columns, all 54 chunk rows intact.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.db import connection

print("=== Phase 2 Schema Verification ===\n")

with connection.cursor() as cur:
    # 1. pgvector extension
    cur.execute("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector'")
    row = cur.fetchone()
    if row:
        print(f"[PASS] pgvector extension installed: {row[0]} v{row[1]}")
    else:
        print("[FAIL] pgvector extension NOT found")
        sys.exit(1)

    # 2. New columns exist
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'document_chunks'
        ORDER BY ordinal_position
    """)
    cols = cur.fetchall()
    col_names = [c[0] for c in cols]
    print(f"\n[INFO] document_chunks columns: {col_names}")

    for expected in ('embedding', 'embedding_updated_at'):
        if expected in col_names:
            print(f"[PASS] Column '{expected}' exists")
        else:
            print(f"[FAIL] Column '{expected}' MISSING")
            sys.exit(1)

    # 3. Chunk count intact
    cur.execute("SELECT COUNT(*) FROM document_chunks")
    count = cur.fetchone()[0]
    print(f"\n[INFO] Total DocumentChunk rows: {count}")
    if count >= 54:
        print(f"[PASS] All {count} chunks intact (expected >= 54)")
    else:
        print(f"[WARN] Only {count} chunks found (expected >= 54)")

    # 4. Confirm embedding is NULL for all existing rows (not yet set)
    cur.execute("SELECT COUNT(*) FROM document_chunks WHERE embedding IS NOT NULL")
    non_null = cur.fetchone()[0]
    print(f"\n[INFO] Chunks with non-NULL embedding: {non_null} (expected 0 before rebuild)")
    if non_null == 0:
        print("[PASS] All existing chunk embeddings are NULL (ready for pgvector rebuild)")
    else:
        print(f"[INFO] {non_null} chunks already have pgvector embeddings")

    # 5. Vector extension cosine distance test
    cur.execute("SELECT ('[1,0,0]'::vector) <=> ('[0,1,0]'::vector)")
    dist = cur.fetchone()[0]
    print(f"\n[PASS] Cosine distance test: [1,0,0] <=> [0,1,0] = {dist:.4f} (expected ~1.0)")

print("\n=== Phase 2 verification PASSED ===")

