"""
Unit Tests for Dashboard REST APIs, Manual Walk-in Bookings, and Dynamic Slot Token Allocation.
"""
import os
import pytest
from fastapi.testclient import TestClient

TEST_DB_PATH = "test_dashboard.db"

@pytest.fixture
def setup_dashboard_env():
    from services.db_service import DatabaseService
    db = DatabaseService()
    db.seed_initial_data(reset=True)
    
    from backend.app import app
    client = TestClient(app)
    
    yield db, client

def test_manual_booking_and_slot_token_ranges(setup_dashboard_env):
    db, client = setup_dashboard_env
    
    # 1. Manual Walk-in Booking in Slot 1 (10-11 AM for Dr. Jaydeep, doctor_id=2)
    res1 = client.post("/api/appointments/manual", json={
        "doctor_id": 2,
        "patient_name_gu": "મનોજ પટેલ",
        "mobile_number": "9825099991",
        "target_date": "2026-09-24",
        "slot_time_gu": "સવારે 10:00 થી 11:00"
    })
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["success"] is True
    assert data1["token_number"] == 1
    assert data1["appointment_code"] == "APT-1"
    assert data1["source"] == "MANUAL"

    # 2. Manual Walk-in Booking in Slot 2 (11-12 PM for Dr. Jaydeep, doctor_id=2)
    # Slot 1 has 8 max slots (tokens 1 to 8). Slot 2 starts at token 9!
    res2 = client.post("/api/appointments/manual", json={
        "doctor_id": 2,
        "patient_name_gu": "રમેશ શાહ",
        "mobile_number": "9825099992",
        "target_date": "2026-09-24",
        "slot_time_gu": "સવારે 11:00 થી 12:00"
    })
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["success"] is True
    assert data2["token_number"] == 9
    assert data2["appointment_code"] == "APT-9"

def test_dashboard_appointments_list_and_search(setup_dashboard_env):
    db, client = setup_dashboard_env
    
    # Create booking
    client.post("/api/appointments/manual", json={
        "doctor_id": 1,
        "patient_name_gu": "ભાવેશ પટેલ",
        "mobile_number": "9898011223",
        "target_date": "2026-09-25",
        "slot_time_gu": "સાંજે 5:00 થી 6:00"
    })

    # Fetch list for 2026-09-25
    res = client.get("/api/appointments?date=2026-09-25")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert len(data["appointments"]) == 1
    assert data["appointments"][0]["patient_name_gu"] == "ભાવેશ પટેલ"

    # Search query filter
    res_search = client.get("/api/appointments?search=ભાવેશ")
    assert res_search.status_code == 200
    assert len(res_search.json()["appointments"]) >= 1

def test_save_custom_slot_and_capacity_update(setup_dashboard_env):
    db, client = setup_dashboard_env
    
    # Save a custom slot for tomorrow
    res = client.post("/api/schedules/slot", json={
        "doctor_id": 2,
        "schedule_date": "2026-09-24",
        "start_time": "14:00",
        "end_time": "15:00",
        "slot_time_gu": "બપોરે 2:00 થી 3:00",
        "slot_time_en": "2:00 PM to 3:00 PM",
        "max_slots": 10,
        "is_active": 1
    })
    assert res.status_code == 200
    assert res.json()["success"] is True

    # Fetch schedules for tomorrow
    res_sched = client.get("/api/schedules?doctor_id=2&date=2026-09-24")
    assert res_sched.status_code == 200
    schedules = res_sched.json()["schedules"]
    assert any(s["slot_time_gu"] == "બપોરે 2:00 થી 3:00" for s in schedules)
