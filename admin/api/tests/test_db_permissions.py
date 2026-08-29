"""admin-dashboard change, task 1.6 — the direct, database-level proof
that `govassist_admin_readonly` cannot write to a live table, per
admin-data-access spec's "Attempted write against a live table fails".

Deliberately connects with plain psycopg2 using the role's own
credentials rather than going through the app's ORM/session layer —
the guarantee under test is that Postgres itself rejects the write,
independent of whatever the application code does or doesn't attempt.
"""

import os

import psycopg2
import pytest
from dotenv import load_dotenv

load_dotenv()

ADMIN_DATABASE_URL = os.environ["ADMIN_DATABASE_URL"]


def _connect():
    return psycopg2.connect(ADMIN_DATABASE_URL)


def test_readonly_role_cannot_insert_into_a_live_table():
    conn = _connect()
    try:
        conn.autocommit = False
        cur = conn.cursor()
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute(
                "INSERT INTO service (id, code, name, category) "
                "VALUES (gen_random_uuid(), 'test', 'test', 'test')"
            )
    finally:
        conn.rollback()
        conn.close()


def test_readonly_role_cannot_update_a_live_table():
    conn = _connect()
    try:
        conn.autocommit = False
        cur = conn.cursor()
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute("UPDATE service SET name = 'tampered' WHERE true")
    finally:
        conn.rollback()
        conn.close()


def test_readonly_role_cannot_delete_from_a_live_table():
    conn = _connect()
    try:
        conn.autocommit = False
        cur = conn.cursor()
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute("DELETE FROM service WHERE true")
    finally:
        conn.rollback()
        conn.close()


def test_readonly_role_can_select_from_a_live_table():
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM service")
        (count,) = cur.fetchone()
        assert count >= 0
    finally:
        conn.close()


def test_readonly_role_can_write_to_an_admin_owned_table():
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO admin_overlay (id, target_type, operation, payload, created_at) "
            "VALUES (gen_random_uuid(), 'service', 'create', '{}', now())"
        )
        conn.commit()
    finally:
        conn.rollback()
        conn.close()
