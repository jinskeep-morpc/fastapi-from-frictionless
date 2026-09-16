"""Browser authentication for the generated UI.

The API authenticates with an ``X-API-Key`` header, which a form post cannot
send. The UI therefore accepts the same key from an HttpOnly cookie, set by a
small login page, so it is never unauthenticated by default.

Where an identity-aware proxy sits in front (Cloudflare Access, Tailscale,
oauth2-proxy), set ``UI_PROXY_IDENTITY_HEADER`` to the header it injects. The
UI will then trust that header and show the authenticated user's name, which a
single shared key cannot provide. Only do this where the proxy is the ONLY
route to the app; anything that can reach it directly can forge the header.
"""

import os

COOKIE_NAME = "ffui_session"


def proxy_identity_header() -> str:
    return os.getenv("UI_PROXY_IDENTITY_HEADER", "").strip()


def expected_key() -> str:
    return os.getenv("API_KEY", "")


def auth_disabled() -> bool:
    """Mirrors the generated app: no key configured and explicitly allowed."""
    return not expected_key() and os.getenv("ALLOW_NO_AUTH", "").lower() in ("1", "true")


def identify(request) -> str | None:
    """Return a display name for the caller, or None if not authenticated."""
    header = proxy_identity_header()
    if header:
        who = request.headers.get(header)
        if who:
            return who
        # A proxy header is configured but absent: fall through to the cookie
        # rather than locking everyone out of a misconfigured deployment.

    if auth_disabled():
        return "anonymous"

    key = expected_key()
    if not key:
        return None
    presented = request.cookies.get(COOKIE_NAME) or request.headers.get("X-API-Key")
    # Constant-time comparison: this is a shared secret checked on every request.
    if presented and _equal(presented, key):
        return "signed in"
    return None


def _equal(a: str, b: str) -> bool:
    import hmac

    return hmac.compare_digest(a, b)
