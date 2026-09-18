"""
Data models and schema definitions for Asterisk Doctor Appointment IVR.
"""
from dataclasses import dataclass
from typing import Optional

@dataclass
class Doctor:
    id: int
    name_en: str
    name_gu: str
    specialty_en: str
    specialty_gu: str
    is_active: bool = True

@dataclass
class DoctorSchedule:
    id: int
    doctor_id: int
    day_of_week: int  # 0=Monday, 6=Sunday
    start_time: str   # "17:00"
    end_time: str     # "20:00"
    slot_time_gu: str # e.g. "સાંજે 5:00 વાગ્યે"
    slot_time_en: str # e.g. "5:00 PM"
    max_slots: int
    is_active: bool = True

@dataclass
class Patient:
    id: int
    mobile_number: str
    name_gu: str
    created_at: str

@dataclass
class Appointment:
    id: int
    appointment_code: str  # e.g. "APT-1001"
    doctor_id: int
    patient_id: int
    appointment_date: str  # YYYY-MM-DD
    slot_time: str
    status: str            # "CONFIRMED", "CANCELLED"
    created_at: str
