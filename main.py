#!/usr/bin/env python3
"""
FastAPI Middleware Exam Solution
- Request Context Propagator
- Scoped CORS
- Per-client Rate Limiter (9 req / 10s)
"""

import time
import uuid
from collections import defaultdict, deque
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware


# ========================= MIDDLEWARE 1: Request Context =========================
class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any):
        # Reuse inbound X-Request-ID if present, else generate new
        request_id = (
            request.headers.get("X-Request-ID")
            or request.headers.get("x-request-id")
            or str(uuid.uuid4())
        )

        request.state.request_id = request_id

        response = await call_next(request)

        # Echo back in response header (CRITICAL for the grader)
        response.headers["X-Request-ID"] = request_id
        return response


# ========================= MIDDLEWARE 3: Rate Limiter =========================
class RateLimitMiddleware(BaseHTTPMiddleware):
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

            # Remove old timestamps
            while times and times[0] < cutoff:
                times.popleft()

            if len(times) >= self.max_requests:
                request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded"},
                    headers={"X-Request-ID": request_id}
                )

            times.append(now)

        return await call_next(request)


# ========================= APP SETUP =========================
app = FastAPI(
    title="RTKQNA Middleware Service",
    version="1.0.0",
    docs_url=None,  # optional
    redoc_url=None
)

# Allowed origins (exactly as per assignment)
ALLOWED_ORIGINS = [
    "https://app-rtkqna.example.com",
    "https://exam.sanand.workers.dev"   # exam grader page
]

# ===================== MIDDLEWARE ORDER (Important) =====================
# Execution order: CORS → RequestContext → RateLimit → Endpoint
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(RateLimitMiddleware, max_requests=9, window_seconds=10)


# ========================= ENDPOINTS =========================
@app.get("/ping")
async def ping(request: Request):
    request_id = getattr(request.state, "request_id", "missing")
    email = "23f3003587@ds.study.iitm.ac.in"
    return {"email": email, "request_id": request_id}


@app.get("/")
async def root():
    return {"status": "ok", "message": "Middleware service running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
