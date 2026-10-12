from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.users import get_current_user
from backend.models.database import get_connection


router = APIRouter(
    prefix="/api/notes",
    tags=["Notes"],
)


class NoteRequest(BaseModel):
    title: str
    content: str = ""
    url: str = ""


class NoteUpdate(BaseModel):
    title: str
    content: str = ""
    url: str = ""


@router.post("")
def create_note(
    data: NoteRequest,
    current_user=Depends(get_current_user),
):
    title = data.title.strip()
    content = data.content
    url = data.url.strip()

    if not title:
        raise HTTPException(
            status_code=400,
            detail="Note title is required",
        )

    connection = get_connection()

    cursor = connection.execute(
        """
        INSERT INTO notes (
            user_id,
            title,
            content,
            url,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            current_user["id"],
            title,
            content,
            url,
        ),
    )

    connection.commit()

    note_id = cursor.lastrowid

    note = connection.execute(
        """
        SELECT id, title, content, url, created_at, updated_at
        FROM notes
        WHERE id = ? AND user_id = ?
        """,
        (note_id, current_user["id"]),
    ).fetchone()

    connection.close()

    return {
        "message": "Note created",
        "note": dict(note),
    }


@router.get("")
def get_notes(
    current_user=Depends(get_current_user),
):
    connection = get_connection()

    rows = connection.execute(
        """
        SELECT id, title, content, url, created_at, updated_at
        FROM notes
        WHERE user_id = ?
        ORDER BY updated_at DESC
        """,
        (current_user["id"],),
    ).fetchall()

    connection.close()

    return {
        "notes": [dict(row) for row in rows]
    }


@router.get("/{note_id}")
def get_note(
    note_id: int,
    current_user=Depends(get_current_user),
):
    connection = get_connection()

    row = connection.execute(
        """
        SELECT id, title, content, url, created_at, updated_at
        FROM notes
        WHERE id = ? AND user_id = ?
        """,
        (note_id, current_user["id"]),
    ).fetchone()

    connection.close()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Note not found",
        )

    return {
        "note": dict(row)
    }


@router.put("/{note_id}")
def update_note(
    note_id: int,
    data: NoteUpdate,
    current_user=Depends(get_current_user),
):
    title = data.title.strip()
    content = data.content
    url = data.url.strip()

    if not title:
        raise HTTPException(
            status_code=400,
            detail="Note title is required",
        )

    connection = get_connection()

    existing = connection.execute(
        """
        SELECT id
        FROM notes
        WHERE id = ? AND user_id = ?
        """,
        (note_id, current_user["id"]),
    ).fetchone()

    if not existing:
        connection.close()

        raise HTTPException(
            status_code=404,
            detail="Note not found",
        )

    connection.execute(
        """
        UPDATE notes
        SET title = ?,
            content = ?,
            url = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
        """,
        (
            title,
            content,
            url,
            note_id,
            current_user["id"],
        ),
    )

    connection.commit()

    note = connection.execute(
        """
        SELECT id, title, content, url, created_at, updated_at
        FROM notes
        WHERE id = ? AND user_id = ?
        """,
        (note_id, current_user["id"]),
    ).fetchone()

    connection.close()

    return {
        "message": "Note updated",
        "note": dict(note),
    }


@router.delete("/{note_id}")
def delete_note(
    note_id: int,
    current_user=Depends(get_current_user),
):
    connection = get_connection()

    existing = connection.execute(
        """
        SELECT id
        FROM notes
        WHERE id = ? AND user_id = ?
        """,
        (note_id, current_user["id"]),
    ).fetchone()

    if not existing:
        connection.close()

        raise HTTPException(
            status_code=404,
            detail="Note not found",
        )

    connection.execute(
        """
        DELETE FROM notes
        WHERE id = ? AND user_id = ?
        """,
        (note_id, current_user["id"]),
    )

    connection.commit()
    connection.close()

    return {
        "message": "Note deleted"
    }