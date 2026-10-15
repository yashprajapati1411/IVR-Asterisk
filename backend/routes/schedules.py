"""
API Routes for Doctor Schedules & Dynamic Slot Capacity Management.
"""
from fastapi import APIRouter, HTTPException, Query
from backend.models.schemas import SlotSaveRequest
from services.db_service import DatabaseService

router = APIRouter(prefix="/api/schedules", tags=["Schedules"])
db = DatabaseService()

from typing import Optional

@router.get("")
def get_schedules(
    doctor_id: int = Query(..., description="Doctor ID (1 or 2)"),
    date: str = Query(..., description="Date YYYY-MM-DD"),
    shift: Optional[str] = Query(None, description="Filter by shift: MORNING or EVENING")
):
    """Fetches doctor schedules & slot capacities for a date."""
    try:
        schedules = db.get_schedules_for_date(doctor_id=doctor_id, target_date=date, shift=shift)
        return {"success": True, "doctor_id": doctor_id, "date": date, "shift": shift, "schedules": schedules}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/slot")
def save_slot(req: SlotSaveRequest):
    """Creates or updates a time slot with collision validation."""
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
            slot_id=req.slot_id,
            shift=req.shift
        )
        if not res.get("success", False):
            raise HTTPException(status_code=400, detail=res.get("error", "Failed to save slot"))
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/slot/{slot_id}")
def delete_slot(slot_id: int):
    """Deletes a schedule slot if no active appointments exist."""
    try:
        res = db.delete_slot(slot_id=slot_id)
        if not res.get("success", False):
            raise HTTPException(status_code=400, detail=res.get("error", "Failed to delete slot"))
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

