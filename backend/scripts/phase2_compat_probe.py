"""
Phase 2 compatibility verification. NO live-DB writes.
 (1) Collect (not execute) the SQL of the proposed migration against the live connection.
 (2) End-to-end ORM probe of VectorField + CosineDistance on the ISOLATED test DB inside a rolled-back transaction.
"""
import os, sys, copy
sys.path.insert(0, os.path.abspath('backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.conf import settings
from django.db import connection, connections, models, transaction
from django.db.migrations import Migration, operations
from django.db.migrations.loader import MigrationLoader
import pgvector, importlib.metadata as md
from pgvector.django import VectorExtension, VectorField, CosineDistance

print("pgvector pkg:", md.version('pgvector'), "| django:", django.get_version(), "| psycopg:", md.version('psycopg'))
print("python:", sys.version.split()[0])

# ---- (1) SQL collection for the live connection ----
ops = [
    VectorExtension(),
    operations.AddField('documentchunk', 'embedding', VectorField(dimensions=768, null=True, blank=True)),
    operations.AddField('documentchunk', 'embedding_updated_at', models.DateTimeField(null=True, blank=True)),
]
mig = Migration('0002_documentchunk_embedding', 'rag')
mig.operations = ops
mig.dependencies = [('rag', '0001_initial')]
loader = MigrationLoader(connection)
state = loader.project_state(('rag', '0001_initial'))
print("\nLive-DB migration plan pending for rag:", [k for k in loader.graph.leaf_nodes() if k[0] == 'rag'])
with connection.schema_editor(collect_sql=True, atomic=True) as editor:
    mig.apply(state, editor, collect_sql=True)
print("\n=== SQL the migration would execute (COLLECTED ONLY, NOT RUN) ===")
for s in editor.collected_sql:
    print(s)

# ---- (2) ORM probe on test DB, rolled back ----
db = copy.deepcopy(settings.DATABASES['default'])
db['NAME'] = 'test_' + db['NAME']
connections.databases['probe'] = db

class ProbeVec(models.Model):
    v = VectorField(dimensions=768, null=True, blank=True)
    class Meta:
        app_label = 'probe_app'
        db_table = '_probe_vec_orm'
        managed = False

class _Rollback(Exception):
    pass

a = [0.1] * 768
b = [0.1] * 767 + [0.9]
try:
    with transaction.atomic(using='probe'):
        with connections['probe'].cursor() as c:
            c.execute("create extension if not exists vector")
            c.execute("create table _probe_vec_orm (id serial primary key, v vector(768))")
        ProbeVec.objects.using('probe').create(v=a)
        ProbeVec.objects.using('probe').create(v=b)
        ProbeVec.objects.using('probe').create(v=None)
        rows = list(ProbeVec.objects.using('probe').filter(v__isnull=False)
                    .annotate(d=CosineDistance('v', a)).order_by('d').values_list('id', 'd'))
        print("\nORM cosine ordering (id, distance):", [(i, round(d, 6)) for i, d in rows])
        got = ProbeVec.objects.using('probe').filter(v__isnull=False).first().v
        print("round-trip type/len/first:", type(got).__name__, len(got), round(got[0], 4))
        print("null row preserved:", ProbeVec.objects.using('probe').filter(v__isnull=True).count() == 1)
        try:
            with transaction.atomic(using='probe'):
                ProbeVec.objects.using('probe').create(v=[0.1] * 10)
        except Exception as e:
            print("wrong-dimension insert rejected:", type(e).__name__)
        raise _Rollback()
except _Rollback:
    print("probe transaction ROLLED BACK")
with connections['probe'].cursor() as c:
    c.execute("select count(*) from pg_extension where extname='vector'"); print("test DB vector ext after probe:", c.fetchone()[0])
    c.execute("select to_regclass('_probe_vec_orm')"); print("probe table after rollback:", c.fetchone()[0])
with connection.cursor() as c:
    c.execute("select count(*) from pg_extension where extname='vector'"); print("LIVE DB vector ext (must be 0):", c.fetchone()[0])
    c.execute("select count(*) from information_schema.columns where table_name='document_chunks' and column_name in ('embedding','embedding_updated_at')")
    print("LIVE DB new columns present (must be 0):", c.fetchone()[0])

