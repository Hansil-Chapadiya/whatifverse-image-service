from fastapi import Header, HTTPException, status

from app.core.config import settings


async def validate_internal_token(token: str = Header(default="")) -> None:
    if not settings.internal_token or token != settings.internal_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_INTERNAL_TOKEN",
                    "message": "Invalid token header",
                }
            },
        )
