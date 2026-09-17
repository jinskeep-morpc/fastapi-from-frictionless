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


def admin_key() -> str:
    return os.getenv("ADMIN_API_KEY", "")


def admin_emails() -> set[str]:
    return {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}


def is_admin(request) -> bool:
    """Whether this caller may see fields marked sensitive in the schema.

    Two mechanisms, matching the generated API's /admin routes, so adopting
    per-person identity later changes no templates:

      1. An identity proxy: UI_PROXY_IDENTITY_HEADER names the header, and the
         address must appear in ADMIN_EMAILS.
      2. Signing in with ADMIN_API_KEY instead of the ordinary API_KEY.

    With neither configured nobody is an admin, which is the safe default: the
    sensitive columns are simply not rendered.
    """
    header = proxy_identity_header()
    if header:
        who = (request.headers.get(header) or "").strip().lower()
        if who and who in admin_emails():
            return True

    key = admin_key()
    if key:
        presented = request.cookies.get(COOKIE_NAME) or request.headers.get("X-Admin-Key")
        if presented and _equal(presented, key):
            return True
    return False


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
    # The admin key is also a valid sign-in, so an administrator does not need to
    # hold both secrets to use the UI.
    if presented and admin_key() and _equal(presented, admin_key()):
        return "signed in (admin)"
    return None


def _equal(a: str, b: str) -> bool:
    import hmac

    return hmac.compare_digest(a, b)
