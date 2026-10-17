import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class ReaderPreferences(BaseModel):
    topics: list[
        Literal["technology", "science", "world"]
    ] = Field(min_length=1, max_length=3)

    keywords: str = Field(default="", max_length=200)

    reading_minutes: Literal[5, 10, 15] = 5


def personalize_articles(
    articles,
    preferences,
    learned_weights=None,
):
    learned_weights = learned_weights or {}
    
    selected_topics = set(preferences.topics)

    keywords = list(
        dict.fromkeys(
            word.strip().casefold()
            for word in preferences.keywords.split(",")
            if word.strip()
        )
    )[:10]

    now = datetime.now(timezone.utc)
    ranked = []

    for original in articles:
        article = dict(original)
        score = 0.0
        reasons = []

        if article["topic"] in selected_topics:
            score += 5.0
            reasons.append(
                f"You follow {article['topic']}."
            )

        searchable_text = (
            article["title"] + " " + article.get("excerpt", "")
        ).casefold()

        matched_keywords = []

        for keyword in keywords:
            pattern = r"(?<!\w)" + re.escape(keyword) + r"(?!\w)"

            if re.search(pattern, searchable_text):
                matched_keywords.append(keyword)

        if matched_keywords:
            score += min(len(matched_keywords), 3) * 2.0
            reasons.append(
                "Matches your interests: "
                + ", ".join(matched_keywords)
                + "."
            )

        published_at = article.get("published_at")

        if published_at:
            try:
                published = datetime.fromisoformat(
                    published_at.replace("Z", "+00:00")
                )

                if published.tzinfo is None:
                    published = published.replace(
                        tzinfo=timezone.utc
                    )

                age_hours = max(
                    0.0,
                    (now - published).total_seconds() / 3600,
                )

                # A small freshness bonus, declining over 72 hours.
                score += max(0.0, 1.0 - age_hours / 72)

            except (TypeError, ValueError):
                pass

        learned_bonus = learned_weights.get(
            article["topic"], 0.0
        )

        score += learned_bonus

        if learned_bonus > 0:
            reasons.append(
                "Boosted by your positive feedback on this topic."
            )
        elif learned_bonus < 0:
            reasons.append(
                "Lower priority after your feedback on this topic."
            )

        article["learning_adjustment"] = learned_bonus
        
        if not reasons:
            reasons.append(
                "Additional coverage outside your selected topics."
            )

        article["relevance_score"] = round(score, 3)
        article["selection_reason"] = " ".join(reasons)
        article["matches_preferences"] = bool(
            article["topic"] in selected_topics
            or matched_keywords
        )

        ranked.append(article)

    ranked.sort(
        key=lambda article: (
            article["relevance_score"],
            article.get("published_at") or "",
        ),
        reverse=True,
    )

    target_count = {
        5: 5,
        10: 8,
        15: 12,
    }[preferences.reading_minutes]

    selected = []
    remaining = list(ranked)
    source_counts = {}

    while remaining and len(selected) < target_count:
        best = max(
            remaining,
            key=lambda article: (
                article["relevance_score"]
                - 1.25 * source_counts.get(article["source"], 0)
            ),
        )

        selected.append(best)
        remaining.remove(best)

        source_counts[best["source"]] = (
            source_counts.get(best["source"], 0) + 1
        )

    word_count = sum(
        len(
            (
                article["title"]
                + " "
                + article.get("excerpt", "")
            ).split()
        )
        for article in selected
    )

    estimated_minutes = (
        max(1, (word_count + 199) // 200)
        if selected
        else 0
    )

    return {
        "articles": selected,
        "count": len(selected),
        "reading_budget": preferences.reading_minutes,
        "estimated_reading_minutes": estimated_minutes,
        "matched_count": sum(
            article["matches_preferences"]
            for article in selected
        ),
    }