import os, sys
sys.path.insert(0, os.path.abspath('backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.conf import settings
from django.db import connection
for k in ['EMBEDDING_PROVIDER','EMBEDDING_MODEL','LM_STUDIO_EMBEDDING_MODEL','LM_STUDIO_BASE_URL','CHROMA_PERSIST_DIRECTORY','CHROMA_COLLECTION_NAME','RAG_TOP_K','LLM_PROVIDER','GEMINI_MODEL']:
    print(k, '=', getattr(settings, k))
print('GEMINI_API_KEY set:', bool(settings.GEMINI_API_KEY))
with connection.cursor() as c:
    c.execute("select name, version, trusted, superuser from pg_available_extension_versions where name='vector'")
    print('vector versions (name, version, trusted, superuser):', c.fetchall())
    c.execute("select indexname from pg_indexes where tablename='document_chunks'")
    print('document_chunks indexes:', [r[0] for r in c.fetchall()])
    c.execute("select column_name, data_type from information_schema.columns where table_name='document_chunks' order by ordinal_position")
    print('document_chunks columns:', c.fetchall())
    c.execute("select app, name from django_migrations where app in ('rag','documents','machines','history') order by id")
    print('applied migrations:', c.fetchall())
from rag.services.providers.factory import get_embedding_provider
p = get_embedding_provider()
print('active embedding provider:', type(p).__name__, '| model id:', p.get_model_identifier())

