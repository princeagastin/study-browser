from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.models.database import get_connection
from backend.services.auth import (
    create_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/register")
def register(data: RegisterRequest):
    username = data.username.strip()

    if len(username) < 3:
        raise HTTPException(
            status_code=400,
            detail="Username must contain at least 3 characters",
        )

    if len(data.password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least 8 characters",
        )

    connection = get_connection()

    existing = connection.execute(
        "SELECT id FROM users WHERE username = ?",
        (username,),
    ).fetchone()

    if existing:
        connection.close()
        raise HTTPException(
            status_code=409,
            detail="Username already exists",
        )

    password_hash = hash_password(data.password)

    cursor = connection.execute(
        """
        INSERT INTO users (username, password_hash)
        VALUES (?, ?)
        """,
        (username, password_hash),
    )

    connection.commit()

    user_id = cursor.lastrowid

    connection.close()

    token = create_access_token(user_id, username)

    return {
        "message": "Account created successfully",
        "user": {
            "id": user_id,
            "username": username,
        },
        "access_token": token,
        "token_type": "bearer",
    }


@router.post("/login")
def login(data: LoginRequest):
    connection = get_connection()

    user = connection.execute(
        """
        SELECT id, username, password_hash
        FROM users
        WHERE username = ?
        """,
        (data.username.strip(),),
    ).fetchone()

    connection.close()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
        )

    if not verify_password(data.password, user["password_hash"]):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
        )

    token = create_access_token(
        user["id"],
        user["username"],
    )

    return {
        "message": "Login successful",
        "user": {
            "id": user["id"],
            "username": user["username"],
        },
        "access_token": token,
        "token_type": "bearer",
    }