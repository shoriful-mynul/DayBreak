import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

PROJECT_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = Path(
    os.environ.get("DAYBREAK_DATA_DIR", str(PROJECT_DIR / "data"))
)

DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "daybreak.db"


def connect():
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row

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

    connection.commit()
    return connection


def save_edition(reader_id, paper):
    edition_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    saved_paper = {
        **paper,
        "edition_id": edition_id,
        "created_at": created_at,
    }

    connection = connect()

    try:
        with connection:
            connection.execute(
                """
                INSERT INTO editions
                    (id, reader_id, created_at, content)
                VALUES (?, ?, ?, ?)
                """,
                (
                    edition_id,
                    reader_id,
                    created_at,
                    json.dumps(saved_paper, ensure_ascii=False),
                ),
            )
    finally:
        connection.close()

    return saved_paper


def list_editions(reader_id):
    connection = connect()

    try:
        rows = connection.execute(
            """
            SELECT id, created_at, content
            FROM editions
            WHERE reader_id = ?
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
    finally:
        connection.close()


def get_edition(reader_id, edition_id):
    connection = connect()

    try:
        row = connection.execute(
            """
            SELECT content
            FROM editions
            WHERE reader_id = ? AND id = ?
            """,
            (reader_id, edition_id),
        ).fetchone()

        return json.loads(row["content"]) if row else None
    finally:
        connection.close()