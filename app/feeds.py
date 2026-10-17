import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

import feedparser
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

FEEDS = [
    {
        "source": "BBC News",
        "topic": "technology",
        "url": "https://feeds.bbci.co.uk/news/technology/rss.xml",
    },
    {
        "source": "The Guardian",
        "topic": "technology",
        "url": "https://www.theguardian.com/technology/rss",
    },
    {
        "source": "BBC News",
        "topic": "science",
        "url": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
    },
    {
        "source": "The Guardian",
        "topic": "science",
        "url": "https://www.theguardian.com/science/rss",
    },
    {
        "source": "BBC News",
        "topic": "world",
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
    },
    {
        "source": "The Guardian",
        "topic": "world",
        "url": "https://www.theguardian.com/world/rss",
    },
    {
        "source": "NPR",
        "topic": "world",
        "url": "https://feeds.npr.org/1004/rss.xml",
    },
]


def clean_text(value):
    """Convert feed HTML into plain text."""
    return BeautifulSoup(
        value or "",
        "html.parser",
    ).get_text(" ", strip=True)


def safe_url(value):
    """Allow only ordinary web links."""
    try:
        parts = urlsplit(value or "")

        if parts.scheme not in {"http", "https"} or not parts.netloc:
            return None

        # Remove fragments for consistent duplicate checking.
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, parts.query, "")
        )
    except ValueError:
        return None


def publication_date(entry):
    """Use the publisher's date when available."""
    parsed = (
        entry.get("published_parsed")
        or entry.get("updated_parsed")
    )

    if not parsed:
        return None

    try:
        return datetime(
            *parsed[:6],
            tzinfo=timezone.utc,
        ).isoformat()
    except (TypeError, ValueError):
        return None


async def fetch_one_feed(client, feed):
    try:
        response = await client.get(feed["url"])
        response.raise_for_status()

        parsed = feedparser.parse(response.content)
        articles = []

        for entry in parsed.entries[:12]:
            title = clean_text(entry.get("title"))
            url = safe_url(entry.get("link"))

            if not title or not url:
                continue

            excerpt = clean_text(entry.get("summary"))

            articles.append(
                {
                    "id": hashlib.sha256(
                        url.encode("utf-8")
                    ).hexdigest()[:16],
                    "title": title,
                    "url": url,
                    "source": feed["source"],
                    "topic": feed["topic"],
                    "published_at": publication_date(entry),
                    "excerpt": excerpt[:1200],
                    "content_basis": "publisher_feed_excerpt",
                }
            )

        if not articles:
            return {
                "articles": [],
                "warning": (
                    f"{feed['source']} ({feed['topic']}): no usable stories returned."
                ),
            }

        return {
            "articles": articles,
            "warning": None,
        }

    except Exception as error:
        logger.warning(
            "Feed failed for %s: %s",
            feed["source"],
            error,
        )

        return {
            "articles": [],
            "warning": (
                f"{feed['source']} ({feed['topic']}): could not load this feed."
            ),
        }


async def collect_news():
    async with httpx.AsyncClient(
        timeout=12.0,
        follow_redirects=True,
        headers={
            "User-Agent": "Daybreak-Hackathon/0.1",
        },
    ) as client:
        results = await asyncio.gather(
            *(fetch_one_feed(client, feed) for feed in FEEDS)
        )

    articles = []
    warnings = []
    seen_urls = set()
    seen_titles = set()

    for result in results:
        if result["warning"]:
            warnings.append(result["warning"])

        for article in result["articles"]:
            normalized_title = " ".join(
                article["title"].casefold().split()
            )

            if (
                article["url"] in seen_urls
                or normalized_title in seen_titles
            ):
                continue

            seen_urls.add(article["url"])
            seen_titles.add(normalized_title)
            articles.append(article)

    articles.sort(
        key=lambda article: article["published_at"] or "",
        reverse=True,
    )

    return {
        "articles": articles,
        "count": len(articles),
        "sources_loaded": sorted(
            {article["source"] for article in articles}
        ),
        "warnings": warnings,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }