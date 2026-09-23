"""
Pydantic Schemas for Dashboard API Requests & Responses.
"""
from pydantic import BaseModel, Field
from typing import Optional, List

class ManualBookingRequest(BaseModel):
    doctor_id: int
    patient_name_gu: str
    mobile_number: str
    target_date: str
    slot_time_gu: str

class StatusUpdateRequest(BaseModel):
    status: str # 'CONFIRMED', 'CHECKED_IN', 'COMPLETED', 'CANCELLED'

class SlotSaveRequest(BaseModel):
    slot_id: Optional[int] = None
    doctor_id: int
    schedule_date: str # 'YYYY-MM-DD' or 'DEFAULT'
    start_time: str # '10:00'
    end_time: str # '11:00'
    slot_time_gu: str # 'સવારે 10:00 થી 11:00'
    slot_time_en: str # '10:00 AM to 11:00 AM'
    max_slots: int = 8
    is_active: int = 1
