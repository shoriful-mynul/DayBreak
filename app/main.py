from pathlib import Path
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.feeds import collect_news
from app.personalization import (
    ReaderPreferences,
    personalize_articles,
)
from app.storage import (
    get_edition,
    list_editions,
    save_edition,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Daybreak")

app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static",
)


def current_reader(
    x_reader_id: str = Header(...),
):
    try:
        return str(UUID(x_reader_id))
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid reader identifier.",
        )


async def build_paper(preferences):
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

    result["preferences"] = preferences.model_dump()

    return result


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
async def personalized_news(
    preferences: ReaderPreferences,
):
    return await build_paper(preferences)


@app.post("/api/editions")
async def create_edition(
    preferences: ReaderPreferences,
    reader_id: str = Depends(current_reader),
):
    paper = await build_paper(preferences)

    # Do not save an empty edition when feeds fail.
    if not paper["count"]:
        return paper

    return save_edition(reader_id, paper)


@app.get("/api/editions")
def edition_archive(
    reader_id: str = Depends(current_reader),
):
    return {
        "editions": list_editions(reader_id),
    }


@app.get("/api/editions/{edition_id}")
def read_edition(
    edition_id: str,
    reader_id: str = Depends(current_reader),
):
    paper = get_edition(reader_id, edition_id)

    if paper is None:
        raise HTTPException(
            status_code=404,
            detail="Edition not found.",
        )

    return paper


@app.get("/news")
def news_page():
    return FileResponse(STATIC_DIR / "news.html")


@app.get("/")
def home():
    return FileResponse(STATIC_DIR / "index.html")