from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.users import get_current_user
from backend.models.database import get_connection

router = APIRouter(
    prefix="/api/bookmarks",
    tags=["Bookmarks"],
)


class BookmarkRequest(BaseModel):
    title: str
    url: str


@router.post("")
def create_bookmark(
    data: BookmarkRequest,
    current_user=Depends(get_current_user),
):
    title = data.title.strip()
    url = data.url.strip()

    if not title or not url:
        raise HTTPException(
            status_code=400,
            detail="Title and URL are required",
        )

    connection = get_connection()

    existing = connection.execute(
        """
        SELECT id, title, url, created_at
        FROM bookmarks
        WHERE user_id = ? AND url = ?
        """,
        (current_user["id"], url),
    ).fetchone()

    if existing:
        connection.close()

        return {
            "message": "Bookmark already exists",
            "bookmark": dict(existing),
        }

    cursor = connection.execute(
        """
        INSERT INTO bookmarks (user_id, title, url)
        VALUES (?, ?, ?)
        """,
        (current_user["id"], title, url),
    )

    connection.commit()

    bookmark_id = cursor.lastrowid

    bookmark = connection.execute(
        """
        SELECT id, title, url, created_at
        FROM bookmarks
        WHERE id = ?
        """,
        (bookmark_id,),
    ).fetchone()

    connection.close()

    return {
        "message": "Bookmark saved",
        "bookmark": dict(bookmark),
    }


@router.get("")
def get_bookmarks(
    current_user=Depends(get_current_user),
):
    connection = get_connection()

    rows = connection.execute(
        """
        SELECT id, title, url, created_at
        FROM bookmarks
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (current_user["id"],),
    ).fetchall()

    connection.close()

    return {
        "bookmarks": [dict(row) for row in rows]
    }


@router.delete("/{bookmark_id}")
def delete_bookmark(
    bookmark_id: int,
    current_user=Depends(get_current_user),
):
    connection = get_connection()

    row = connection.execute(
        """
        SELECT id
        FROM bookmarks
        WHERE id = ? AND user_id = ?
        """,
        (bookmark_id, current_user["id"]),
    ).fetchone()

    if not row:
        connection.close()

        raise HTTPException(
            status_code=404,
            detail="Bookmark not found",
        )

    connection.execute(
        """
        DELETE FROM bookmarks
        WHERE id = ? AND user_id = ?
        """,
        (bookmark_id, current_user["id"]),
    )

    connection.commit()
    connection.close()

    return {
        "message": "Bookmark deleted"
    }