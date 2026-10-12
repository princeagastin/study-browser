from fastapi import FastAPI

from backend.api.auth import router as auth_router
from backend.api.users import router as users_router
from backend.models.database import init_db
from backend.api.bookmarks import router as bookmarks_router
from backend.models.bookmarks import init_bookmarks_table

app = FastAPI(
    title="StudyBrowse API",
    version="2.0.0",
    description="Backend API for StudyBrowse",
)

init_db()
init_bookmarks_table()
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(bookmarks_router)


@app.get("/")
def root():
    return {
        "app": "StudyBrowse",
        "version": "2.0.0",
        "status": "running",
    }


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "StudyBrowse Backend",
    }