from datetime import datetime, timezone

from app.storage import connect


def learning_connection():
    connection = connect()

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback (
            reader_id TEXT NOT NULL,
            article_id TEXT NOT NULL,
            topic TEXT NOT NULL,
            value INTEGER NOT NULL CHECK(value IN (-1, 1)),
            updated_at TEXT NOT NULL,
            PRIMARY KEY (reader_id, article_id)
        )
        """
    )

    connection.commit()
    return connection


def get_learned_weights(reader_id):
    connection = learning_connection()

    try:
        rows = connection.execute(
            """
            SELECT topic, SUM(value) AS total
            FROM feedback
            WHERE reader_id = ?
            GROUP BY topic
            """,
            (reader_id,),
        ).fetchall()

        return {
            row["topic"]: max(
                -4.0,
                min(4.0, row["total"] * 1.5),
            )
            for row in rows
        }
    finally:
        connection.close()


def record_feedback(reader_id, article, action):
    value = 1 if action == "more" else -1
    updated_at = datetime.now(timezone.utc).isoformat()

    connection = learning_connection()

    try:
        with connection:
            connection.execute(
                """
                INSERT INTO feedback (
                    reader_id,
                    article_id,
                    topic,
                    value,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(reader_id, article_id)
                DO UPDATE SET
                    topic = excluded.topic,
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (
                    reader_id,
                    article["id"],
                    article["topic"],
                    value,
                    updated_at,
                ),
            )
    finally:
        connection.close()

    return get_learned_weights(reader_id)