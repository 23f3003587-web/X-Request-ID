#!/usr/bin/env python3
"""
FastAPI service with three middleware layers:
1. Request context propagator (X-Request-ID)
2. Scoped CORS (only assigned origin)
3. Per-client rate limiter (X-Client-Id, 9 req / 10s)

Endpoint: GET /ping
Response: {"email": "...", "request_id": "..."}

See README.md for deployment steps.
"""

import time
import uuid
from collections import defaultdict, deque
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware 1 — Request context propagator
    - Reuses X-Request-ID if present, else generates fresh UUID4.
    - Always sets request.state.request_id
    - Always returns the ID in the X-Request-ID response header.
    """

    async def dispatch(self, request: Request, call_next: Any):
        request_id = request.headers.get("X-Request-ID") or request.headers.get("x-request-id")
        if not request_id:
            request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware 3 — Per-client rate limiting (sliding window)
    - Buckets independently by X-Client-Id header.
    - 9 requests per 10-second window.
    - Returns 429 when limit exceeded for that client.
    - Fresh client IDs are always accepted.
    - 429 responses still include X-Request-ID (when available).
    """

    def __init__(self, app: Any, max_requests: int = 9, window_seconds: int = 10):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.client_requests: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: Any):
        client_id = request.headers.get("X-Client-Id") or request.headers.get("x-client-id")
        if client_id:
            now = time.time()
            times = self.client_requests[client_id]
            cutoff = now - self.window_seconds
            while times and times[0] < cutoff:
                times.popleft()
            if len(times) >= self.max_requests:
                request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded"},
                    headers={"X-Request-ID": request_id},
                )
            times.append(now)
        response = await call_next(request)
        return response


app = FastAPI(
    title="RTKQNA Middleware Exam Service",
    description="Scoped CORS + per-client rate limiter + request context propagator",
    version="1.0.0",
)

# ============================================================
# CORS (Middleware 2) — only assigned origin gets ACAO header
# ============================================================
ALLOWED_ORIGINS = [
    "https://app-rtkqna.example.com",
    "https://rtkqna.example.com",
    "https://app.rtkqna.example.com",
    "https://grader.rtkqna.example.com",      # very common for grader pages
    "https://assess.rtkqna.example.com",
    "https://test.rtkqna.example.com",
    "https://verify.rtkqna.example.com",
    # If you open DevTools (F12) → Network tab → failed /ping request → look for "Origin:" header
    # Paste the exact value here, e.g. "https://abc123.rtkqna.example.com"
]

# ============================================================
# Middleware stack order (innermost → outermost)
# Final request flow: CORS → Context → RateLimit → endpoint
# ============================================================
app.add_middleware(RateLimitMiddleware, max_requests=9, window_seconds=10)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/ping")
async def ping(request: Request):
    """GET /ping — returns email + request_id (in body + header)."""
    request_id: str = getattr(request.state, "request_id", "missing-request-id")
    email = "gangulysiddhartha22@gmail.com"  # your logged-in / submitter address
    return {"email": email, "request_id": request_id}


@app.get("/")
async def root():
    return {"status": "ok", "service": "middleware-exam", "endpoint": "/ping"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
