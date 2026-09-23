"""
API Routes for Doctors Information.
"""
from fastapi import APIRouter
from services.db_service import DatabaseService

router = APIRouter(prefix="/api/doctors", tags=["Doctors"])
db = DatabaseService()

@router.get("")
def list_doctors():
    """Lists active doctors."""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name_en, name_gu, specialty_en, specialty_gu FROM doctors WHERE is_active = 1")
    doctors = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"success": True, "doctors": doctors}
