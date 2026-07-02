from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
import time
from collections import defaultdict, deque

app = FastAPI(title="X-Request-ID Service")

# ==================== Request Context Middleware ====================
class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Get or create request_id
        request_id = request.headers.get("X-Request-ID") or \
                     request.headers.get("x-request-id") or \
                     str(uuid.uuid4())
        
        request.state.request_id = request_id
        
        response = await call_next(request)
        
        # CRITICAL: Always echo in header
        response.headers["X-Request-ID"] = request_id
        return response

# ==================== Rate Limiter ====================
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests=9, window=10):
        super().__init__(app)
        self.max_requests = max_requests
        self.window = window
        self.clients = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        client_id = request.headers.get("X-Client-Id") or request.headers.get("x-client-id")
        
        if client_id:
            now = time.time()
            times = self.clients[client_id]
            cutoff = now - self.window
            while times and times[0] < cutoff:
                times.popleft()
            
            if len(times) >= self.max_requests:
                req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
                return JSONResponse(
                    {"detail": "Rate limit exceeded"},
                    status_code=429,
                    headers={"X-Request-ID": req_id}
                )
            times.append(now)
        
        return await call_next(request)

# Middleware Registration - Order Matters!
app.add_middleware(RequestContextMiddleware)
app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app-rtkqna.example.com", "https://exam.sanand.workers.dev"],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

@app.get("/ping")
async def ping(request: Request):
    request_id = getattr(request.state, "request_id", "missing")
    return {"email": "23f3003587@ds.study.iitm.ac.in", "request_id": request_id}

@app.get("/")
async def root():
    return {"status": "ok"}
