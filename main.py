#!/usr/bin/env python3
"""
FastAPI service with three middleware layers for the exam.
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
    """Middleware 1 — Request context propagator"""
    async def dispatch(self, request: Request, call_next: Any):
        # Get or generate request_id
        request_id = (
            request.headers.get("X-Request-ID")
            or request.headers.get("x-request-id")
            or str(uuid.uuid4())
        )
        
        request.state.request_id = request_id
        
        # Process request
        response = await call_next(request)
        
        # ALWAYS echo it back in response header (this is the key requirement)
        response.headers["X-Request-ID"] = request_id
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware 3 — Per-client rate limiting"""
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
            
            # Clean old requests
            while times and times[0] < cutoff:
                times.popleft()
            
            if len(times) >= self.max_requests:
                request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded"},
                    headers={"X-Request-ID": request_id},   # Important: still return header
                )
            
            times.append(now)
        
        response = await call_next(request)
        return response


# ====================== APP SETUP ======================
app = FastAPI(
    title="RTKQNA Middleware Exam Service",
    version="1.0.0",
)

ALLOWED_ORIGINS = [
    "https://app-rtkqna.example.com",
    "https://exam.sanand.workers.dev",
]

# ====================== MIDDLEWARE ORDER (Critical) ======================
# Correct order: RequestContext should run before RateLimit so it can set request.state
app.add_middleware(RequestContextMiddleware)           # Runs early
app.add_middleware(RateLimitMiddleware, max_requests=9, window_seconds=10)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/ping")
async def ping(request: Request):
    request_id: str = getattr(request.state, "request_id", "missing-request-id")
    email = "23f3003587@ds.study.iitm.ac.in"
    return {"email": email, "request_id": request_id}


@app.get("/")
async def root():
    return {"status": "ok", "service": "middleware-exam", "endpoint": "/ping"}
