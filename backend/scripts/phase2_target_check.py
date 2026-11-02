"""READ-ONLY: verify DB target (no credentials printed) and extension permissions. Test DB probe is rolled back."""
import os, sys
sys.path.insert(0, os.path.abspath('backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.conf import settings
from django.db import connection, connections
import psycopg

db = settings.DATABASES['default']
host = str(db.get('HOST', ''))
print("NAME:", db.get('NAME'))
print("HOST (masked):", host[:8] + "..." + host[-14:], "| pooler endpoint:", "-pooler" in host)
print("PORT:", db.get('PORT'), "| sslmode:", (db.get('OPTIONS') or {}).get('sslmode'))
print("TEST config:", db.get('TEST'))
with connection.cursor() as c:
    c.execute("select current_database(), current_user is not null, version()")
    cd, _, ver = c.fetchone(); print("current_database():", cd); print("version:", ver[:40])
    c.execute("select rolcreatedb, rolsuper, rolcreaterole from pg_roles where rolname=current_user")
    print("role (createdb, super, createrole):", c.fetchone())
    c.execute("select datname from pg_database where datname like %s order by 1", ['%'+ (db.get('NAME') or '') +'%'])
    print("databases matching name:", [r[0] for r in c.fetchall()])
    c.execute("select count(*) from pg_extension where extname='vector'"); print("vector installed in live DB:", c.fetchone()[0])
    c.execute("select pg_is_in_recovery()"); print("read-only replica:", c.fetchone()[0])

# Probe the isolated test database (if it exists): CREATE EXTENSION inside a transaction, then ROLLBACK
test_name = 'test_' + db['NAME']
try:
    conn_kwargs = dict(host=db['HOST'], port=db.get('PORT') or 5432, user=db['USER'], password=db['PASSWORD'],
                       dbname=test_name, sslmode=(db.get('OPTIONS') or {}).get('sslmode', 'require'))
    with psycopg.connect(**conn_kwargs, autocommit=False) as conn:
        cur = conn.cursor()
        cur.execute("select count(*) from pg_extension where extname='vector'"); print(test_name, "vector installed before probe:", cur.fetchone()[0])
        cur.execute("create extension if not exists vector")
        cur.execute("select extversion from pg_extension where extname='vector'"); print("probe: CREATE EXTENSION succeeded in test DB, version", cur.fetchone()[0])
        cur.execute("create table _probe_vec (v vector(768))")
        cur.execute("insert into _probe_vec values (%s::vector)", ['[' + ','.join(['0.1'] * 768) + ']'])
        cur.execute("select v <=> %s::vector from _probe_vec", ['[' + ','.join(['0.1'] * 768) + ']'])
        print("probe: cosine distance of identical vectors:", cur.fetchone()[0])
        conn.rollback()
        cur.execute("select count(*) from pg_extension where extname='vector'"); print("after ROLLBACK, vector installed in test DB:", cur.fetchone()[0])
except psycopg.OperationalError as e:
    print("test DB probe skipped/failed (connect):", str(e).split('\n')[0][:120])
except Exception as e:
    print("test DB probe error:", type(e).__name__, str(e).split('\n')[0][:160])

