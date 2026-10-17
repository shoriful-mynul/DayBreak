from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.feeds import collect_news
from app.personalization import (
    ReaderPreferences,
    personalize_articles,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Daybreak")

app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static",
)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "project": "Daybreak",
    }


@app.get("/api/news")
async def news():
    return await collect_news()


@app.post("/api/personalize")
async def personalized_news(preferences: ReaderPreferences):
    news_data = await collect_news()

    result = personalize_articles(
        news_data["articles"],
        preferences,
    )

    result["warnings"] = news_data["warnings"]
    result["fetched_at"] = news_data["fetched_at"]

    result["sources_loaded"] = news_data["sources_loaded"]

    result["sources_in_paper"] = sorted(
        {
            article["source"]
            for article in result["articles"]
        }
    )

    return result


@app.get("/news")
def news_page():
    return FileResponse(STATIC_DIR / "news.html")


@app.get("/")
def home():
    return FileResponse(STATIC_DIR / "index.html")