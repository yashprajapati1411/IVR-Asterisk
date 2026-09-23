"""
FastAPI Server Application for Trinay Orthopedic Hospital Receptionist Dashboard.
Hosts REST APIs and serves static frontend files.
"""
import os
import sys
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

# Insert project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from backend.routes.appointments import router as appointments_router
from backend.routes.schedules import router as schedules_router
from backend.routes.doctors import router as doctors_router
from services.db_service import DatabaseService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DashboardBackend")

app = FastAPI(title="Trinay Hospital Receptionist Dashboard API", version="2.0.0")

# Seed initial database structure
db = DatabaseService()
db.seed_initial_data()

# Register API routers
app.include_router(appointments_router)
app.include_router(schedules_router)
app.include_router(doctors_router)

# Mount frontend static directory
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)
