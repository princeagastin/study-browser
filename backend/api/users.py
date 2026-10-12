from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

from backend.services.auth import JWT_SECRET, JWT_ALGORITHM

router = APIRouter(prefix="/api/users", tags=["Users"])

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )

        user_id = payload.get("sub")
        username = payload.get("username")

        if not user_id or not username:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication token",
            )

        return {
            "id": int(user_id),
            "username": username,
        }

    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        )


@router.get("/me")
def get_me(current_user=Depends(get_current_user)):
    return {
        "user": current_user
    }