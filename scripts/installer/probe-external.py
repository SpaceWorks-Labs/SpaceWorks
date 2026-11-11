#!/usr/bin/env python3
"""Connection checks for outside services, run before setup starts anything (decision 239).

Runs inside the backend image (psycopg2, redis and boto3 are installed there) with the settings in
SW_PROBE_* environment variables, never on the command line. Every check prints one plain-language
line; a failure says what is wrong and how to fix it. Credentials and URLs are never printed.
Exit status 0 means every selected check passed.
"""
import os
import smtplib
import ssl
import sys
import uuid
from email.message import EmailMessage
from pathlib import Path
import urllib.error
import urllib.request

PAYLOAD = b"Space Works installer storage check\n"
PRIVATE_NETS = ("localhost", "127.", "10.", "192.168.", "db", "redis")


class Fail(Exception):
    pass


def env(name, default=""):
    return os.environ.get("SW_PROBE_" + name, default)


def is_private(host):
    return host == "::1" or host.startswith(PRIVATE_NETS) or any(host.startswith(f"172.{n}.") for n in range(16, 32))


def check_database():
    import psycopg2
    from psycopg2.extensions import parse_dsn
    url = env("DB_URL")
    try:
        host = parse_dsn(url).get("host", "")
    except Exception:
        raise Fail("The database URL could not be read. Fix: use postgresql://user:password@host:5432/database?sslmode=require.")
    try:
        conn = psycopg2.connect(url, connect_timeout=10)
    except Exception:
        raise Fail("Could not connect to the database. Fix: check the host, port, password and that this server's address is allowed "
                   "by the provider's network rules (Supabase: Database settings, Network restrictions).")
    try:
        cur = conn.cursor()
        cur.execute("SHOW server_version_num")
        major = int(cur.fetchone()[0]) // 10000
        if major not in (16, 17):
            raise Fail(f"The database is PostgreSQL {major}. Fix: use a PostgreSQL 16 or 17 server (change the version in the provider's dashboard).")
        if not Path(f"/usr/lib/postgresql/{major}/bin/pg_dump").is_file():
            raise Fail(f"This release has no pg_dump for PostgreSQL {major}, so backups would not work. Fix: use PostgreSQL 16 or 17.")
        if not is_private(host):
            cur.execute("SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()")
            row = cur.fetchone()
            if not row or not row[0]:
                raise Fail("The connection is not encrypted. Fix: add ?sslmode=require to the database URL.")
        cur.execute("SELECT rolcreaterole OR rolsuper FROM pg_roles WHERE rolname = current_user")
        if not cur.fetchone()[0]:
            raise Fail("This login cannot create the limited login Space Works uses. Fix: use the owner login "
                       "(Supabase: the postgres user; Neon: the project owner role).")
        cur.execute("SELECT name FROM pg_available_extensions WHERE name IN ('pgcrypto', 'pg_trgm')")
        missing = {"pgcrypto", "pg_trgm"} - {row[0] for row in cur.fetchall()}
        if missing:
            raise Fail(f"The server does not offer the extension(s) {', '.join(sorted(missing))}. Fix: choose a provider plan or region that includes them.")
        table = "sw_probe_" + uuid.uuid4().hex[:12]
        try:
            cur.execute(f"CREATE TABLE public.{table} (id integer)")
            cur.execute(f"INSERT INTO public.{table} VALUES (1)")
            cur.execute(f"DROP TABLE public.{table}")
            conn.commit()
        except psycopg2.Error:
            conn.rollback()
            raise Fail("This login cannot create a table in the public schema. Fix: use the owner login, or run GRANT CREATE ON SCHEMA public TO <login>.")
        if env("EXPECT_EMPTY") == "1":
            cur.execute("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                        "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')")
            if cur.fetchone()[0]:
                raise Fail("The database already contains tables. A new install adopts only an empty database. Fix: point at a new empty "
                           "database; to bring existing data, restore a backup into it after setup.")
    finally:
        conn.close()
    return f"Database reachable, PostgreSQL {major}, matching pg_dump present, a table can be created."


def check_redis():
    import redis
    key = "sw-probe:" + uuid.uuid4().hex
    try:
        client = redis.Redis.from_url(env("REDIS_URL"), socket_connect_timeout=8, socket_timeout=8)
        if not client.ping():
            raise Fail("Redis did not answer PING.")
        client.set(key, "1", ex=30)
        ok = client.get(key) == b"1"
        client.delete(key)
    except Fail:
        raise
    except Exception:
        raise Fail("Could not reach Redis. Fix: check the rediss:// address and password, and that the provider allows this server.")
    if not ok:
        raise Fail("Redis accepted the connection but did not store a value. Fix: use a read-write password.")
    return "Redis answers PING and stores a value."


def fetch(url, data=None, headers=None, method=None):
    request = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, response.read(65537)
    except urllib.error.HTTPError as error:
        return error.code, b""


def post_upload(form):
    boundary = "sw" + uuid.uuid4().hex
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in form["fields"].items()]
    parts += [f'--{boundary}\r\nContent-Disposition: form-data; name="file"\r\n\r\n'.encode(), PAYLOAD, f"\r\n--{boundary}--\r\n".encode()]
    return fetch(form["url"], b"".join(parts), {"Content-Type": "multipart/form-data; boundary=" + boundary}, "POST")[0]


def check_storage():
    import boto3
    from botocore.config import Config
    options = dict(region_name=env("S3_REGION"), aws_access_key_id=env("S3_ACCESS"), aws_secret_access_key=env("S3_SECRET"),
                   config=Config(signature_version="s3v4", s3={"addressing_style": "path"}, retries={"max_attempts": 2},
                                 connect_timeout=10, read_timeout=15))
    backend = boto3.client("s3", endpoint_url=env("S3_ENDPOINT"), **options)
    browser = boto3.client("s3", endpoint_url=env("S3_PUBLIC_ENDPOINT") or env("S3_ENDPOINT"), **options)
    private, public = env("PRIVATE_BUCKET"), env("IMAGE_BUCKET")
    key = "installer-probes/" + uuid.uuid4().hex
    made = []
    try:
        for bucket in (private, public):
            try:
                backend.head_bucket(Bucket=bucket)
            except Exception:
                raise Fail(f"Cannot open the bucket '{bucket}'. Fix: create it, check the endpoint and region, and give the access key read and write on it.")
        try:
            backend.put_object(Bucket=private, Key=key, Body=PAYLOAD)
            made.append((private, key))
            if backend.get_object(Bucket=private, Key=key)["Body"].read() != PAYLOAD:
                raise Fail("The private bucket returned different bytes than were written.")
        except Fail:
            raise
        except Exception:
            raise Fail("Could not write and read an object in the private bucket. Fix: the access key needs read, write and delete on both buckets.")
        if env("PROFILE") == "full":
            if backend.get_bucket_versioning(Bucket=private).get("Status") != "Enabled":
                raise Fail("The 'full' profile needs versioning on the private bucket. Fix: turn bucket versioning on, or choose the limited profile.")
        browser_key = key + "-upload"
        made.append((private, browser_key))
        if env("PRESIGN") == "post":
            form = browser.generate_presigned_post(private, browser_key, ExpiresIn=120, Conditions=[["content-length-range", 1, 1048576]])
            status = post_upload(form)
        else:
            url = browser.generate_presigned_url("put_object", Params={"Bucket": private, "Key": browser_key}, ExpiresIn=120)
            status = fetch(url, PAYLOAD, method="PUT")[0]
        if status not in (200, 201, 204):
            raise Fail("A signed browser upload was refused. Fix: the browser-facing address must be reachable from the internet and match the endpoint "
                       "the keys are for; add a CORS rule on the private bucket for your website.")
        status, body = fetch(browser.generate_presigned_url("get_object", Params={"Bucket": private, "Key": browser_key}, ExpiresIn=120))
        if status != 200 or body != PAYLOAD:
            raise Fail("A signed download did not return the uploaded bytes. Fix: check the browser-facing address and the bucket's CORS rule.")
        public_key = key + "-public"
        backend.put_object(Bucket=public, Key=public_key, Body=PAYLOAD)
        made.append((public, public_key))
        status, body = fetch(env("IMAGE_BASE_URL").rstrip("/") + "/" + public_key)
        if status != 200 or body != PAYLOAD:
            raise Fail("The public image address does not serve the public bucket. Fix: make the public bucket readable without a key, or "
                       "serve it from the public image base URL you entered.")
    finally:
        for bucket, name in made:
            try:
                backend.delete_object(Bucket=bucket, Key=name)
            except Exception:
                pass
    return "Storage: both buckets open, write/read/delete and a signed browser upload and download worked, public images are served."


def check_email():
    host, port = env("SMTP_HOST"), int(env("SMTP_PORT", "587"))
    try:
        smtp = smtplib.SMTP(host, port, timeout=15)
        if env("SMTP_TLS") == "1":
            smtp.starttls(context=ssl.create_default_context())
        if env("SMTP_USER"):
            smtp.login(env("SMTP_USER"), env("SMTP_PASSWORD"))
        if env("TEST_EMAIL_TO"):
            message = EmailMessage()
            message["From"], message["To"], message["Subject"] = env("SMTP_FROM"), env("TEST_EMAIL_TO"), "Space Works test email"
            message.set_content("This confirms the email settings entered during setup work.")
            smtp.send_message(message)
        smtp.quit()
    except Exception:
        raise Fail("The mail server refused the connection or the login. Fix: check host, port (587 with STARTTLS), user, password, "
                   "and that the sender address is verified with the provider.")
    return "Email server accepted the login" + (f" and sent a test message to {env('TEST_EMAIL_TO')}." if env("TEST_EMAIL_TO") else ".")


CHECKS = {"database": check_database, "redis": check_redis, "storage": check_storage, "email": check_email}


def main():
    failed = 0
    for name in [item for item in env("COMPONENTS").split(",") if item]:
        try:
            print(f"[ok] {CHECKS[name]()}")
        except Fail as error:
            failed += 1
            print(f"[FAILED] {name}: {error}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
