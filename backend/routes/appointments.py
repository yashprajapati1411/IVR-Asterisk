"""
API Routes for Appointments Management & Manual Walk-in Bookings.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from backend.models.schemas import ManualBookingRequest, StatusUpdateRequest
from services.db_service import DatabaseService

router = APIRouter(prefix="/api/appointments", tags=["Appointments"])
db = DatabaseService()

@router.get("")
def list_appointments(
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    doctor_id: Optional[int] = Query(None, description="Filter by doctor ID"),
    search: Optional[str] = Query(None, description="Search by name, mobile, or token")
):
    """Fetches real-time appointments list with search and filters."""
    try:
        appts = db.get_appointments_list(date_str=date, doctor_id=doctor_id, search_query=search)
        return {"success": True, "count": len(appts), "appointments": appts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/manual")
def book_manual_appointment(req: ManualBookingRequest):
    """Manually books an appointment for walk-in patients."""
    res = db.book_appointment(
        doctor_id=req.doctor_id,
        mobile_number=req.mobile_number,
        patient_name_gu=req.patient_name_gu,
        target_date=req.target_date,
        slot_time_gu=req.slot_time_gu,
        source="MANUAL"
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Booking failed"))
    return res

@router.put("/{appointment_id}/status")
def update_status(appointment_id: int, req: StatusUpdateRequest):
    """Updates appointment status: CONFIRMED, CHECKED_IN, COMPLETED, CANCELLED."""
    if req.status not in ("CONFIRMED", "CHECKED_IN", "COMPLETED", "CANCELLED"):
        raise HTTPException(status_code=400, detail="Invalid status value")
    
    updated = db.update_appointment_status(appointment_id, req.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return {"success": True, "appointment_id": appointment_id, "status": req.status}
