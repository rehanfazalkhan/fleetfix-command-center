"""JWT authentication for production callers; development roles are isolated from production."""

from __future__ import annotations

from typing import Any

from .config import Settings
from .models import Principal
from .policy import VALID_ROLES


class AuthenticationError(ValueError):
    pass


def authenticate(authorization: str | None, settings: Settings, development_role: str) -> Principal:
    if not settings.is_production:
        role = development_role if development_role in VALID_ROLES else "technician"
        return Principal(subject="local-development-user", role=role)
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationError("A bearer token is required in production mode.")
    try:
        import jwt
        token = authorization.removeprefix("Bearer ").strip()
        key = jwt.PyJWKClient(settings.jwt_issuer + "/.well-known/jwks.json").get_signing_key_from_jwt(token)
        claims: dict[str, Any] = jwt.decode(token, key.key, algorithms=["RS256", "ES256"], audience=settings.jwt_audience, issuer=settings.jwt_issuer)
    except Exception as error:  # Do not expose verifier detail to callers.
        raise AuthenticationError("The supplied bearer token is invalid.") from error
    raw_role = claims.get(settings.jwt_role_claim) or claims.get("role")
    roles = raw_role if isinstance(raw_role, list) else [raw_role]
    role = next((candidate for candidate in ("admin", "fleet_manager", "dispatcher", "technician") if candidate in roles), None)
    if not claims.get("sub") or role not in VALID_ROLES:
        raise AuthenticationError("The token lacks an approved FleetFix role.")
    return Principal(subject=str(claims["sub"]), role=role)
