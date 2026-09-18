"""
Call Session State container for Asterisk IVR.
Tracks user inputs, selected doctor, captured details, and appointment status.
"""
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class CallSession:
    unique_id: str = ""
    caller_id: str = ""
    selected_doctor_id: Optional[int] = None
    selected_doctor_name_gu: str = ""
    selected_doctor_name_en: str = ""
    selected_slot_time_gu: str = ""
    selected_date: str = ""
    mobile_number: str = ""
    patient_name_gu: str = ""
    appointment_id: Optional[int] = None
    appointment_code: Optional[str] = None
    retry_count: int = 0
    state: str = "WELCOME"
    data: dict = field(default_factory=dict)
