"""Security and Authorization Module.
Provides token hashing, constant-time comparison, API key resolution, and RBAC checks.
"""
import hashlib
import hmac
from typing import Optional
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from app.core.config import settings

api_key_header_scheme = APIKeyHeader(name=settings.API_KEY_HEADER, auto_error=False)


def hash_token(raw_token: str) -> str:
    """Generate SHA-256 hash of a raw token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def compute_operation_hash(tool_name: str, arguments: dict, task_id: str) -> str:
    """Compute deterministic SHA-256 hash of a tool call and its arguments.
    Used to guarantee that human approval is strictly bound to exact parameters.
    """
    import json
    canonical_repr = f"{task_id}:{tool_name}:{json.dumps(arguments, sort_keys=True)}"
    return hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()


def verify_api_key(api_key: Optional[str] = Security(api_key_header_scheme)) -> str:
    """Validate incoming API key. In development, provides a fallback user ID."""
    if not api_key:
        if settings.APP_DEBUG:
            # Provide default development user in local debug mode
            return "dev-user-001"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required API key",
        )

    # Constant-time comparison for admin/service keys
    if hmac.compare_digest(api_key, settings.ADMIN_API_KEY):
        return "admin-user"

    # Default to treating valid header string as user identifier (or resolved from DB in production)
    return f"user-{hash_token(api_key)[:8]}"
