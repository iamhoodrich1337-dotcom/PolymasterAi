from fastapi import Header, HTTPException
from app.config import get_settings
from app.core.security import constant_time_compare


async def require_admin(
    authorization: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
) -> None:
    """Protects the API. Token is sent as 'X-Admin-Token: <token>' or 'Authorization: Bearer <token>'."""
    expected = get_settings().admin_token
    if not expected:
        raise HTTPException(status_code=503, detail="ADMIN_TOKEN is not configured on the server")
    supplied = x_admin_token or ""
    if not supplied and authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    if not supplied or not constant_time_compare(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing token")
