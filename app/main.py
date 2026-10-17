from pathlib import Path
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from app.pdf_export import create_newspaper_pdf

from typing import Literal

from pydantic import BaseModel, Field

from app.learning import (
    get_learned_weights,
    record_feedback,
)

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


async def build_paper(preferences, reader_id=None):
    news_data = await collect_news()

    learned_weights = (
        get_learned_weights(reader_id)
        if reader_id
        else {}
    )

    result = personalize_articles(
        news_data["articles"],
        preferences,
        learned_weights,
    )

    result["learned_weights"] = learned_weights

    # Keep the candidate pool for a controlled updated revision.
    result["candidate_articles"] = news_data["articles"]

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
    paper = await build_paper(preferences, reader_id)

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


@app.get("/api/editions/{edition_id}/pdf")
def download_edition_pdf(
    edition_id: str,
    reader_id: str = Depends(current_reader),
):
    paper = get_edition(reader_id, edition_id)

    if paper is None:
        raise HTTPException(
            status_code=404,
            detail="Edition not found.",
        )

    pdf_bytes = create_newspaper_pdf(paper)

    filename = f"daybreak-{paper['edition_id'][:8]}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}"'
            ),
            "Cache-Control": "private, no-store",
        },
    )
    
    
class FeedbackRequest(BaseModel):
    edition_id: str = Field(max_length=64)
    article_id: str = Field(max_length=64)
    action: Literal["more", "less"]


@app.get("/api/learning")
def learning_status(
    reader_id: str = Depends(current_reader),
):
    return {
        "weights": get_learned_weights(reader_id),
    }


@app.post("/api/feedback")
def submit_feedback(
    feedback: FeedbackRequest,
    reader_id: str = Depends(current_reader),
):
    paper = get_edition(
        reader_id,
        feedback.edition_id,
    )

    if paper is None:
        raise HTTPException(
            status_code=404,
            detail="Edition not found.",
        )

    article = next(
        (
            item
            for item in paper["articles"]
            if item["id"] == feedback.article_id
        ),
        None,
    )

    if article is None:
        raise HTTPException(
            status_code=404,
            detail="Article not found in this edition.",
        )

    weights = record_feedback(
        reader_id,
        article,
        feedback.action,
    )

    return {
        "topic": article["topic"],
        "action": feedback.action,
        "weights": weights,
    }


@app.post("/api/editions/{edition_id}/revise")
def revise_edition(
    edition_id: str,
    reader_id: str = Depends(current_reader),
):
    original = get_edition(reader_id, edition_id)

    if original is None:
        raise HTTPException(
            status_code=404,
            detail="Edition not found.",
        )

    candidates = original.get("candidate_articles")

    if not candidates:
        raise HTTPException(
            status_code=409,
            detail=(
                "Create a new paper first. "
                "This older edition has no saved candidate pool."
            ),
        )

    preferences = ReaderPreferences(
        **original["preferences"]
    )

    weights = get_learned_weights(reader_id)

    result = personalize_articles(
        candidates,
        preferences,
        weights,
    )

    result.update(
        {
            "preferences": original["preferences"],
            "candidate_articles": candidates,
            "learned_weights": weights,
            "warnings": original.get("warnings", []),
            "fetched_at": original["fetched_at"],
            "sources_loaded": original.get(
                "sources_loaded", []
            ),
            "sources_in_paper": sorted(
                {
                    article["source"]
                    for article in result["articles"]
                }
            ),
            "revision_of": edition_id,
        }
    )

    return save_edition(reader_id, result)