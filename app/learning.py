from datetime import datetime, timezone

from app.storage import connect


def get_learned_weights(reader_id):
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT topic, SUM(value) AS total
            FROM feedback
            WHERE reader_id = %s
            GROUP BY topic
            """,
            (reader_id,),
        ).fetchall()

    return {
        row["topic"]: max(
            -4.0,
            min(4.0, float(row["total"]) * 1.5),
        )
        for row in rows
    }


def record_feedback(reader_id, article, action):
    value = 1 if action == "more" else -1
    updated_at = datetime.now(timezone.utc).isoformat()

    with connect() as connection:
        connection.execute(
            """
            INSERT INTO feedback (
                reader_id,
                article_id,
                topic,
                value,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT(reader_id, article_id)
            DO UPDATE SET
                topic = EXCLUDED.topic,
                value = EXCLUDED.value,
                updated_at = EXCLUDED.updated_at
            """,
            (
                reader_id,
                article["id"],
                article["topic"],
                value,
                updated_at,
            ),
        )

    return get_learned_weights(reader_id)