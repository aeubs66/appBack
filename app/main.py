"""
FastAPI application entry point for Chat with PDF backend.
"""

from fastapi import FastAPI, Request, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from app.routes import auth, documents, teams, subscriptions, billing

# Note: Import models to ensure they're registered with SQLAlchemy
from app.models import PDFDocument, PDFChunk, Team, TeamMember, Subscription, UsagePersonal, UsageTeam

# Note: Database tables should be created via migrations, not on startup
# Run: python run_migration.py or use Supabase Dashboard SQL Editor

app = FastAPI(
    title="Chat with PDF API",
    description="Backend API for PDF chat application",
    version="0.2.0",
)

# Request logging middleware
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Log request details
        auth_header = request.headers.get("authorization", "NOT PROVIDED")
        print(f"\n[REQUEST] {request.method} {request.url.path}")
        print(f"[AUTH] Authorization header: {auth_header[:50] if auth_header != 'NOT PROVIDED' else 'NOT PROVIDED'}...")
        
        response = await call_next(request)
        print(f"[RESPONSE] {response.status_code}\n")
        return response

app.add_middleware(LoggingMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],  # Expose all headers for debugging
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(teams.router, prefix="/api/teams", tags=["teams"])
app.include_router(subscriptions.router, prefix="/api/subscriptions", tags=["subscriptions"])
app.include_router(billing.router, prefix="/api/billing", tags=["billing"])


# Exception handler for HTTPException (including 401 from auth)
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions (like 401 Unauthorized) with proper CORS headers."""
    print(f"[HTTP ERROR] {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

# Global exception handler to ensure all errors return JSON with CORS headers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Ensure all exceptions return JSON responses with CORS headers."""
    from fastapi import HTTPException
    import traceback
    
    # Don't handle HTTPException here (handled above)
    if isinstance(exc, HTTPException):
        raise exc
    
    error_detail = str(exc)
    # Log the full traceback for debugging
    print(f"[UNHANDLED EXCEPTION] {error_detail}")
    print(traceback.format_exc())
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"Internal server error: {error_detail}"},
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )


@app.get("/")
async def root():
    return {"message": "Chat with PDF API", "status": "ok", "version": "0.2.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}

