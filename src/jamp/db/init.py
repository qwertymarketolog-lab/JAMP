"""Idempotent initializer for the PostgreSQL schema."""

from pathlib import Path

from jamp.db.connection import get_connection, release_connection


def init_schema() -> None:
    schema_path = Path(__file__).with_name("schema.sql")
    schema_sql = schema_path.read_text(encoding="utf-8")
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(schema_sql)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        release_connection(connection)
