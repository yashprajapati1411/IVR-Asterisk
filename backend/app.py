"""
FastAPI Server Application for Trinay Orthopedic Hospital Receptionist Dashboard.
Hosts REST APIs and serves static frontend files.
"""
import os
import sys
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

# Insert project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
sys.path.insert(0, PROJECT_ROOT)

from backend.routes.appointments import router as appointments_router
from backend.routes.schedules import router as schedules_router
from backend.routes.doctors import router as doctors_router
from backend.routes.exotel_ws import router as exotel_router
from backend.routes.auth import router as auth_router, AUTH_TOKEN
from services.db_service import DatabaseService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DashboardBackend")

app = FastAPI(title="Trinay Hospital Receptionist Dashboard API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def verify_receptionist_auth(request: Request, call_next):
    """
    Security gate: Protects hospital appointment and schedule data from internet strangers.
    Allows public access to Exotel Voicebot, health check, login, and static assets.
    """
    path = request.url.path

    # Public paths
    if (
        path.startswith("/exotel") or
        path.startswith("/css") or
        path.startswith("/js") or
        path.startswith("/static") or
        path in ("/", "/health", "/docs", "/openapi.json", "/api/auth/login", "/api/auth/verify")
    ):
        return await call_next(request)

    # Protected administrative API routes
    if path.startswith("/api/"):
        auth_header = request.headers.get("authorization", "")
        token_header = request.headers.get("x-auth-token", "")
        token = token_header
        if not token and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()

        if token != AUTH_TOKEN:
            return JSONResponse(
                status_code=401,
                content={"success": False, "detail": "Unauthorized: Receptionist login required"}
            )

    return await call_next(request)

# Seed initial database structure
db = DatabaseService()
db.seed_initial_data()

# Register API routers
app.include_router(auth_router)
app.include_router(appointments_router)
app.include_router(schedules_router)
app.include_router(doctors_router)
app.include_router(exotel_router, prefix="/exotel")

@app.get("/")
def read_root():
    """Serves the Receptionist Dashboard UI."""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse({"message": "Receptionist Dashboard API active. Frontend index.html not found."})

@app.get("/health")
def health_check():
    return {"status": "ok", "app": "Trinay Hospital Dashboard"}

# Mount frontend static directories
if os.path.exists(FRONTEND_DIR):
    css_dir = os.path.join(FRONTEND_DIR, "css")
    js_dir = os.path.join(FRONTEND_DIR, "js")
    if os.path.exists(css_dir):
        app.mount("/css", StaticFiles(directory=css_dir), name="css")
    if os.path.exists(js_dir):
        app.mount("/js", StaticFiles(directory=js_dir), name="js")
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)
