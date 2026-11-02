"""READ-ONLY audit for Chroma -> pgvector migration. No writes, no credentials printed."""
import os, sys, math
sys.path.insert(0, os.path.abspath('backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.db import connection
from django.conf import settings

db = settings.DATABASES['default']
print("DB engine:", db['ENGINE'])
print("DB host is neon.tech:", 'neon.tech' in str(db.get('HOST', '')))
print("DB sslmode option:", (db.get('OPTIONS') or {}).get('sslmode'))

with connection.cursor() as c:
    c.execute("show server_version"); print("server_version:", c.fetchone()[0])
    c.execute("select name, default_version, installed_version from pg_available_extensions where name='vector'")
    print("pg_available_extensions[vector]:", c.fetchall())
    c.execute("select extname, extversion from pg_extension order by 1"); print("installed extensions:", c.fetchall())
    c.execute("select rolsuper from pg_roles where rolname = current_user"); print("current role superuser:", c.fetchone()[0])
    c.execute("select has_database_privilege(current_user, current_database(), 'CREATE')"); print("can CREATE in db:", c.fetchone()[0])
    c.execute("select count(*) from document_chunks"); print("document_chunks rows:", c.fetchone()[0])
    c.execute("select count(*), count(distinct document_id) from document_chunks"); print("chunks/docs:", c.fetchone())
    c.execute("select count(*), count(distinct chroma_vector_id) from document_chunks"); print("chunk rows / distinct chroma ids:", c.fetchone())
    c.execute("select embedding_model, count(*) from document_chunks group by 1"); print("chunk embedding_model:", c.fetchall())
    c.execute("select status, count(*) from document_indexes group by 1"); print("index statuses:", c.fetchall())
    c.execute("select pg_size_pretty(pg_database_size(current_database()))"); print("db size:", c.fetchone()[0])

import chromadb
cs = settings.CHROMA_PERSIST_DIRECTORY
print("Chroma persist dir exists:", os.path.isdir(cs), "| collection:", settings.CHROMA_COLLECTION_NAME)
client = chromadb.PersistentClient(path=str(cs))
col = client.get_collection(settings.CHROMA_COLLECTION_NAME)
print("collection metadata:", col.metadata)
total = col.count(); print("chroma vector count:", total)

from rag.models import DocumentChunk
db_ids = dict(DocumentChunk.objects.values_list('chroma_vector_id', 'id'))
seen, bad_dim, bad_val, orphans, models_seen, dims = set(), 0, 0, [], {}, set()
off = 0
while off < total:
    r = col.get(limit=100, offset=off, include=["embeddings", "metadatas"])
    for vid, emb, meta in zip(r["ids"], r["embeddings"], r["metadatas"]):
        dims.add(len(emb))
        if len(emb) != 768: bad_dim += 1
        if not all(math.isfinite(x) for x in emb): bad_val += 1
        if vid not in db_ids: orphans.append(vid)
        seen.add(vid)
        m = (meta or {}).get("embedding_model"); models_seen[m] = models_seen.get(m, 0) + 1
    off += 100
print("chroma dims seen:", dims, "| bad_dim:", bad_dim, "| non-finite:", bad_val)
print("chroma embedding_model metadata:", models_seen)
print("orphan vectors (in Chroma, no chunk):", len(orphans), orphans[:5])
missing = [v for v in db_ids if v not in seen]
print("chunks missing a vector:", len(missing), missing[:5])

