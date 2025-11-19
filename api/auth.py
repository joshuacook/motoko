"""
JWT authentication with bcrypt password hashing.
Single-user authentication with secure token management.
"""
import os
import jwt
import bcrypt
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, Cookie, Response
from fastapi.security import HTTPBearer


# Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "")
PASSWORD_HASH = os.getenv("PASSWORD_HASH", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24 * 7  # 7 days

security = HTTPBearer()


def verify_password(password: str) -> bool:
    """Verify password against stored bcrypt hash."""
    if not PASSWORD_HASH:
        raise ValueError("PASSWORD_HASH environment variable not set")

    return bcrypt.checkpw(
        password.encode('utf-8'),
        PASSWORD_HASH.encode('utf-8')
    )


def create_jwt_token() -> str:
    """Create a JWT token."""
    if not JWT_SECRET:
        raise ValueError("JWT_SECRET environment variable not set")

    payload = {
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.utcnow(),
        "sub": "user"  # Single user
    }

    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt_token(token: str) -> bool:
    """Verify a JWT token."""
    if not JWT_SECRET:
        raise ValueError("JWT_SECRET environment variable not set")

    try:
        jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return True
    except jwt.ExpiredSignatureError:
        return False
    except jwt.InvalidTokenError:
        return False


def set_jwt_cookie(response: Response, token: str):
    """Set JWT token as HTTP-only cookie."""
    response.set_cookie(
        key="auth_token",
        value=token,
        httponly=True,  # Prevent JavaScript access (XSS protection)
        secure=True,     # HTTPS only
        samesite="strict",  # CSRF protection
        max_age=JWT_EXPIRATION_HOURS * 3600
    )


def clear_jwt_cookie(response: Response):
    """Clear JWT cookie (logout)."""
    response.delete_cookie(key="auth_token")


def get_current_user(auth_token: Optional[str] = Cookie(None)):
    """
    Dependency to verify JWT token from cookie.
    Raises HTTPException if not authenticated.
    """
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not verify_jwt_token(auth_token):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return "user"  # Single user


def hash_password(password: str) -> str:
    """
    Helper function to generate bcrypt hash for a password.
    Use this to generate PASSWORD_HASH for .env file.

    Example:
        python -c "from auth import hash_password; print(hash_password('mypassword'))"
    """
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
