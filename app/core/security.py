import hashlib, hmac
from datetime import datetime, timedelta, timezone
from app.config import get_settings

def constant_time_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())

def create_access_token(subject: str, expires_minutes: int = 60) -> str:
    settings = get_settings()
    expire = int((datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)).timestamp())
    message = f"{subject}.{expire}"
    sig = hmac.new(settings.secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()
    return f"{message}.{sig}"

def decode_access_token(token: str) -> str | None:
    settings = get_settings()
    try:
        subject, expire_str, sig = token.rsplit(".", 2)
        if datetime.now(timezone.utc).timestamp() > int(expire_str): return None
        expected = hmac.new(settings.secret_key.encode(), f"{subject}.{expire_str}".encode(), hashlib.sha256).hexdigest()
        return subject if hmac.compare_digest(sig, expected) else None
    except (ValueError, AttributeError): return None
