import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

PROJECT_DIR = Path(__file__).resolve().parent.parent

# Read local secrets. Hosting environment variables take precedence.
load_dotenv(PROJECT_DIR / ".env", override=False)

_schema_lock = Lock()
_schema_ready = False


def open_database():
    database_url = os.environ.get("DATABASE_URL", "").strip()

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is missing. "
            "Set it in the project-root .env file "
            "or the hosting environment."
        )

    return psycopg.connect(
        database_url,
        row_factory=dict_row,
        connect_timeout=15,
        prepare_threshold=None,
    )


def ensure_schema():
    global _schema_ready

    with _schema_lock:
        if _schema_ready:
            return

        with open_database() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS editions (
                    id TEXT PRIMARY KEY,
                    reader_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    content TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS editions_by_reader
                ON editions(reader_id, created_at)
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    reader_id TEXT NOT NULL,
                    article_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    value INTEGER NOT NULL
                        CHECK(value IN (-1, 1)),
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (reader_id, article_id)
                )
                """
            )

        _schema_ready = True


def connect():
    ensure_schema()
    return open_database()


def save_edition(reader_id, paper):
    edition_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    saved_paper = {
        **paper,
        "edition_id": edition_id,
        "created_at": created_at,
    }

    with connect() as connection:
        connection.execute(
            """
            INSERT INTO editions
                (id, reader_id, created_at, content)
            VALUES (%s, %s, %s, %s)
            """,
            (
                edition_id,
                reader_id,
                created_at,
                json.dumps(saved_paper, ensure_ascii=False),
            ),
        )

    return saved_paper


def list_editions(reader_id):
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT id, created_at, content
            FROM editions
            WHERE reader_id = %s
            ORDER BY created_at DESC
            LIMIT 100
            """,
            (reader_id,),
        ).fetchall()

    editions = []

    for row in rows:
        paper = json.loads(row["content"])

        editions.append(
            {
                "edition_id": row["id"],
                "created_at": row["created_at"],
                "count": paper["count"],
                "topics": paper.get(
                    "preferences", {}
                ).get("topics", []),
            }
        )

    return editions


def get_edition(reader_id, edition_id):
    with connect() as connection:
        row = connection.execute(
            """
            SELECT content
            FROM editions
            WHERE reader_id = %s AND id = %s
            """,
            (reader_id, edition_id),
        ).fetchone()

    return json.loads(row["content"]) if row else None