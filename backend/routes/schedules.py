"""
API Routes for Doctor Schedules & Dynamic Slot Capacity Management.
"""
from fastapi import APIRouter, HTTPException, Query
from backend.models.schemas import SlotSaveRequest
from services.db_service import DatabaseService

router = APIRouter(prefix="/api/schedules", tags=["Schedules"])
db = DatabaseService()

@router.get("")
def get_schedules(
    doctor_id: int = Query(..., description="Doctor ID (1 or 2)"),
    date: str = Query(..., description="Date YYYY-MM-DD")
):
    """Fetches doctor schedules & slot capacities for a date."""
    try:
        schedules = db.get_schedules_for_date(doctor_id=doctor_id, target_date=date)
        return {"success": True, "doctor_id": doctor_id, "date": date, "schedules": schedules}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/slot")
def save_slot(req: SlotSaveRequest):
    """Creates or updates a time slot (including custom slots and max_slots capacity)."""
    try:
        res = db.save_or_update_slot(
            doctor_id=req.doctor_id,
            schedule_date=req.schedule_date,
            start_time=req.start_time,
            end_time=req.end_time,
            slot_time_gu=req.slot_time_gu,
            slot_time_en=req.slot_time_en,
            max_slots=req.max_slots,
            is_active=req.is_active,
            slot_id=req.slot_id
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
