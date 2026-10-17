from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.feeds import collect_news

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


@app.get("/news")
def news_page():
    return FileResponse(STATIC_DIR / "news.html")


@app.get("/")
def home():
    return FileResponse(STATIC_DIR / "index.html")