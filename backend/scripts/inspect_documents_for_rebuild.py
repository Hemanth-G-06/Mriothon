"""
Inspect all documents and machines in the database and compare with the 3 genuine PDFs.
"""
import os
import sys
import hashlib
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from machines.models import Machine
from documents.models import Document, DocumentPage
from rag.models import DocumentIndex, DocumentChunk

GENUINE_DIR = Path(r"C:\Users\jayan\Downloads\Round 1 Student Pack\Manuals")
print("=== Genuine Source PDFs ===")
for p in sorted(GENUINE_DIR.glob("*.pdf")):
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    print(f"  {p.name}: {p.stat().st_size} bytes | sha256={h}")

print("\n=== Active Documents in PostgreSQL ===")
for doc in Document.objects.filter(is_active=True).select_related('machine').order_by('machine__machine_code', 'created_at'):
    idx = DocumentIndex.objects.filter(document=doc).first()
    idx_status = idx.status if idx else "NONE"
    pages = DocumentPage.objects.filter(document=doc).count()
    chunks = DocumentChunk.objects.filter(document=doc).count()
    emb_chunks = DocumentChunk.objects.filter(document=doc, embedding__isnull=False).count()
    file_exists = False
    file_size = 0
    file_hash = ""
    try:
        if doc.file and os.path.exists(doc.file.path):
            file_exists = True
            file_size = os.path.getsize(doc.file.path)
            file_hash = hashlib.sha256(Path(doc.file.path).read_bytes()).hexdigest()[:16]
    except Exception as e:
        file_hash = f"err:{e}"
    print(
        f"  [{doc.machine.machine_code}] id={doc.id} | title='{doc.title}' | "
        f"orig='{doc.original_filename}' | status={doc.status} | idx={idx_status} | "
        f"pages={pages} | chunks={chunks} (pgvec={emb_chunks}) | "
        f"file_exists={file_exists} ({file_size}B, sha256={file_hash}...)"
    )

