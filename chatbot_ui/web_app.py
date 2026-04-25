"""
ERP Chatbot Web UI - FastAPI server for the modern web interface
Serves the HTML/CSS/JS chatbot UI and provides API endpoints.
"""

import hmac
import os
import secrets
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

# Resolve current directory and load environment variables from local .env
current_dir = Path(__file__).parent
load_dotenv(current_dir / ".env", override=True)

LANGGRAPH_URL = os.getenv("LANGGRAPH_URL", "http://localhost:5001").rstrip("/")
API_KEY = os.getenv("API_KEY")

# Auth configuration.
# If SITE_PASSWORD is unset, the gate is disabled entirely (useful for local dev).
# SESSION_SECRET is required when SITE_PASSWORD is set; it signs the session cookie.
SITE_PASSWORD = os.getenv("SITE_PASSWORD") or None
SESSION_SECRET = os.getenv("SESSION_SECRET") or None
# 30 days by default; user won't be asked to log in again within this window.
SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", "2592000"))
SESSION_COOKIE_NAME = "erp_chatbot_session"

_serializer: URLSafeTimedSerializer | None = None
if SITE_PASSWORD:
    if not SESSION_SECRET:
        # Auto-generate a per-process secret so deployments never silently run with a predictable key.
        # Operators should set SESSION_SECRET explicitly so cookies survive restarts.
        SESSION_SECRET = secrets.token_urlsafe(32)
        print(
            "WARNING: SITE_PASSWORD is set but SESSION_SECRET is not. "
            "Generated an ephemeral secret — users will be logged out on every restart. "
            "Set SESSION_SECRET to a stable value to persist sessions.",
            file=sys.stderr,
        )
    _serializer = URLSafeTimedSerializer(SESSION_SECRET, salt="erp-chatbot-session")

# Database configuration (for UI status only – read directly from .env)
raw_dialect = (os.getenv("DB_DIALECT") or "").strip()
DB_DIALECT = raw_dialect.lower()
POSTGRES_DATABASE = os.getenv("POSTGRES_DATABASE")
MSSQL_DATABASE = os.getenv("MSSQL_DATABASE")

DB_DATABASE = None
if DB_DIALECT.startswith("mssql"):
    DB_DATABASE = MSSQL_DATABASE
elif DB_DIALECT.startswith("postgres"):
    DB_DATABASE = POSTGRES_DATABASE
else:
    # Fallback: try either explicit database vars or legacy DB_NAME
    DB_DATABASE = POSTGRES_DATABASE or MSSQL_DATABASE or os.getenv("DB_NAME")


def _is_authenticated(request: Request) -> bool:
    """Return True when the request carries a valid, unexpired session cookie."""
    if not SITE_PASSWORD or _serializer is None:
        return True  # gate disabled
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return False
    try:
        _serializer.loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return False
    return True


def _issue_session_cookie(response: Response) -> None:
    """Mint a signed session cookie and attach it to the response."""
    if _serializer is None:
        return
    token = _serializer.dumps("ok")
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


# Paths that don't require auth: the login flow itself and static UI assets
# needed to render the login page. We also leave /health open so platform
# liveness checks work without credentials.
_PUBLIC_PATHS: set[str] = {
    "/login",
    "/logout",
    "/styles.css",
    "/script.js",
    "/health",
}
_PUBLIC_PREFIXES: tuple[str, ...] = ("/static/",)


class AuthMiddleware(BaseHTTPMiddleware):
    """Block every route except explicit public ones when SITE_PASSWORD is set."""

    async def dispatch(self, request: Request, call_next):
        if not SITE_PASSWORD:
            return await call_next(request)

        path = request.url.path
        if path in _PUBLIC_PATHS or path.startswith(_PUBLIC_PREFIXES):
            return await call_next(request)

        if _is_authenticated(request):
            return await call_next(request)

        # HTML navigation → redirect to the login page.
        # XHR / API calls → 401 JSON so the frontend can handle it cleanly.
        accept = request.headers.get("accept", "")
        if request.method == "GET" and "text/html" in accept:
            return RedirectResponse(url="/login", status_code=303)
        return Response(
            content='{"detail":"Authentication required"}',
            status_code=401,
            media_type="application/json",
        )


# Create FastAPI app
app = FastAPI(
    title="ERP Chatbot Web UI",
    description="Modern web interface for the ERP Chatbot",
    version="2.0.0"
)

# Order matters: AuthMiddleware runs before CORS for the blocking logic,
# but CORS must still apply to allowed requests.
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (CSS, JS, images)
app.mount("/static", StaticFiles(directory=current_dir), name="static")


_LOGIN_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign in — ERP Assistant</title>
    <link rel="stylesheet" href="/styles.css">
    <link rel="icon" href="/static/icons/app-icon.png">
</head>
<body class="login-body">
    <main class="login-card" role="main">
        <img src="/static/icons/app-icon.png" alt="" class="login-logo">
        <h1>ERP Assistant</h1>
        <p class="login-subtitle">Enter the access passphrase to continue.</p>
        {error_block}
        <form method="post" action="/login" class="login-form">
            <label for="password" class="visually-hidden">Password</label>
            <input
                id="password"
                name="password"
                type="password"
                placeholder="Passphrase"
                autocomplete="current-password"
                autofocus
                required
            >
            <button type="submit" class="btn-primary login-submit">Sign in</button>
        </form>
        <p class="login-footnote">
            This demo is password-protected to prevent abuse of the underlying LLM API.
        </p>
    </main>
</body>
</html>
"""


def _render_login_page(error: str | None = None) -> str:
    error_block = (
        f'<p class="login-error" role="alert">{error}</p>' if error else ""
    )
    return _LOGIN_PAGE_TEMPLATE.format(error_block=error_block)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve the login form. If the user is already authenticated, send them home."""
    if _is_authenticated(request):
        return RedirectResponse(url="/", status_code=303)
    return HTMLResponse(content=_render_login_page())


@app.post("/login")
async def login_submit(request: Request, password: str = Form(...)):
    """Validate the submitted password and mint a session cookie."""
    if not SITE_PASSWORD:
        # Gate disabled — just send them home.
        return RedirectResponse(url="/", status_code=303)

    # Constant-time comparison to avoid leaking timing info about the password.
    if not hmac.compare_digest(password.encode("utf-8"), SITE_PASSWORD.encode("utf-8")):
        return HTMLResponse(
            content=_render_login_page(error="Incorrect passphrase. Please try again."),
            status_code=401,
        )

    response = RedirectResponse(url="/", status_code=303)
    _issue_session_cookie(response)
    return response


@app.post("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve the main HTML page."""
    index_path = current_dir / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Index file not found")

    with open(index_path, 'r', encoding='utf-8') as f:
        content = f.read()

    return HTMLResponse(content=content)

@app.get("/styles.css")
async def serve_styles():
    """Serve the CSS file."""
    css_path = current_dir / "styles.css"
    if not css_path.exists():
        raise HTTPException(status_code=404, detail="CSS file not found")

    return FileResponse(css_path, media_type="text/css")

@app.get("/script.js")
async def serve_script():
    """Serve the JavaScript file."""
    js_path = current_dir / "script.js"
    if not js_path.exists():
        raise HTTPException(status_code=404, detail="JavaScript file not found")

    return FileResponse(js_path, media_type="application/javascript")

@app.get("/health")
async def health_check():
    """Health check endpoint for the web UI."""
    return {
        "status": "healthy",
        "service": "ERP Chatbot Web UI",
        "version": "2.0.0"
    }

@app.get("/config")
async def get_config():
    """Get configuration for the frontend."""
    return {
        "langgraph_url": LANGGRAPH_URL,
        "api_key_set": bool(API_KEY),
        "version": "2.0.0",
        "db_dialect": DB_DIALECT,
        "db_database": DB_DATABASE,
        "auth_enabled": bool(SITE_PASSWORD),
    }


@app.get("/backend_health")
async def backend_health():
    """Health check endpoint for the backend LangGraph/agent service."""
    target_url = f"{LANGGRAPH_URL}/health"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(target_url)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Backend health check failed: {exc}") from exc

    content_type = resp.headers.get("content-type", "")
    try:
        payload = resp.json() if "application/json" in content_type else {"raw": resp.text}
    except ValueError:
        payload = {"raw": resp.text}

    return {
        "status": "online" if resp.status_code == 200 else "degraded",
        "backend_status_code": resp.status_code,
        "backend_response": payload,
    }


@app.post("/process_conversation")
async def proxy_process_conversation(request: Request):
    """
    Proxy /process_conversation requests to the LangGraph/agent service.

    The API key is attached server-side so it never lives in the browser.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Invalid request payload")

    messages = body.get("messages")
    if not messages:
        raise HTTPException(status_code=400, detail="messages cannot be empty")

    forward_body = dict(body)
    if API_KEY:
        forward_body["api_key"] = API_KEY

    target_url = f"{LANGGRAPH_URL}/process_conversation"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(target_url, json=forward_body)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Error contacting backend service: {exc}") from exc

    content_type = resp.headers.get("content-type", "")
    try:
        data = resp.json() if "application/json" in content_type else {"error": resp.text}
    except ValueError:
        data = {"error": resp.text}

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=data)

    return data


@app.post("/stream_conversation")
async def stream_conversation(request: Request):
    """
    Proxy streaming conversation requests to the LangGraph/agent service.

    Returns a Server-Sent Events (SSE) stream of agent execution events.
    The API key is attached server-side so it never lives in the browser.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Invalid request payload")

    messages = body.get("messages")
    if not messages:
        raise HTTPException(status_code=400, detail="messages cannot be empty")

    forward_body = {"messages": messages}
    if API_KEY:
        forward_body["api_key"] = API_KEY

    target_url = f"{LANGGRAPH_URL}/stream"

    async def event_generator():
        """Stream events from the backend."""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    target_url,
                    json=forward_body,
                    headers={"Accept": "text/event-stream"}
                ) as resp:
                    if resp.status_code >= 400:
                        error_text = await resp.aread()
                        yield f"data: {{\"type\": \"error\", \"error\": \"Backend error: {resp.status_code}\"}}\n\n"
                        return

                    async for line in resp.aiter_lines():
                        if line:
                            yield f"{line}\n"
                        else:
                            yield "\n"
        except httpx.RequestError as exc:
            yield f"data: {{\"type\": \"error\", \"error\": \"Connection error: {str(exc)}\"}}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


if __name__ == "__main__":
    print("Starting ERP Chatbot Web UI...")
    print("Make sure the following are running:")
    print("   - LangGraph Service (http://localhost:5001)")
    print("   - MCP Server (http://localhost:8000)")
    print("   - PostgreSQL database")
    if SITE_PASSWORD:
        print("   - Authentication: ENABLED (SITE_PASSWORD set)")
    else:
        print("   - Authentication: DISABLED (SITE_PASSWORD not set)")
    print()
    print("Web UI will be available at: http://localhost:3000")
    print()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=3000,
        log_level="info"
    )
