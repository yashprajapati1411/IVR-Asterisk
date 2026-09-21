"""
Unit & Integration Tests for DatabaseService.
Tests concurrency, slot booking, doctor availability, and patient upserts.
"""
import os
import pytest
import datetime
from services.db_service import DatabaseService

TEST_DB_PATH = "test_ivr.db"

@pytest.fixture
def test_db():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    db = DatabaseService(db_path=TEST_DB_PATH)
    db.seed_initial_data(reset=True)
    yield db
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

def test_doctors_and_schedules_seeded(test_db):
    doc1 = test_db.get_doctor(1)
    assert doc1 is not None
    assert "Dr. Shaishav" in doc1["name_en"]
    assert "શૈશવ" in doc1["name_gu"]

    doc2 = test_db.get_doctor(2)
    assert doc2 is not None
    assert "Dr. Jaydeep" in doc2["name_en"]
    assert "જયદીપ" in doc2["name_gu"]

def test_check_availability(test_db):
    avail1 = test_db.check_availability(1)
    assert avail1["available"] is True
    assert len(avail1["slots"]) == 3
    assert "સાંજે" in avail1["slots"][0]["slot_time_gu"]

    avail2 = test_db.check_availability(2)
    assert avail2["available"] is True
    assert len(avail2["slots"]) == 4
    assert "સવારે" in avail2["slots"][0]["slot_time_gu"]

def test_booking_transaction_success(test_db):
    mobile = "9825012345"
    patient_name = "ભાવેશભાઈ પટેલ"
    result = test_db.book_appointment(
        doctor_id=1,
        mobile_number=mobile,
        patient_name_gu=patient_name
    )
    assert result["success"] is True
    assert "APT-" in result["appointment_code"]
    assert result["patient_name_gu"] == patient_name
    assert result["mobile_number"] == mobile

    # Check that slot count decreased by 1
    avail_after = test_db.check_availability(1)
    assert avail_after["slots"][0]["slots_left"] == 7

def test_patient_upsert(test_db):
    mobile = "9876543210"
    # Booking 1
    res1 = test_db.book_appointment(1, mobile, "પહેલું નામ")
    assert res1["success"] is True

    # Booking 2 with same mobile should update patient name, not fail
    res2 = test_db.book_appointment(1, mobile, "બીજું નામ")
    assert res2["success"] is True

    conn = test_db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count, name_gu FROM patients WHERE mobile_number = ?", (mobile,))
    row = cursor.fetchone()
    assert row["count"] == 1
    assert row["name_gu"] == "બીજું નામ"
    conn.close()

def test_slots_exhaustion_concurrency(test_db):
    # Set doctor 2 to have max 2 slots per hour
    test_db.set_doctor_slots(doctor_id=2, max_slots=2)

    # Book slot 1
    r1 = test_db.book_appointment(2, "9800000001", "દર્દી ૧")
    assert r1["success"] is True

    # Book slot 2
    r2 = test_db.book_appointment(2, "9800000002", "દર્દી ૨")
    assert r2["success"] is True

    # First hourly slot (10:00 to 11:00) is now full, so check_availability returns 3 remaining slots
    avail = test_db.check_availability(2)
    assert len(avail["slots"]) == 3
    assert all("10:00" not in s["slot_time_gu"] for s in avail["slots"])

    # Attempt to book third appointment in same slot should fail
    r3 = test_db.book_appointment(2, "9800000003", "દર્દી ૩", slot_time_gu="સવારે 10:00 થી 11:00")
    assert r3["success"] is False
    assert r3["error"] == "SLOTS_FULL"
