"""
Concurrency and Atomic Transaction Stress Tests.
Tests 2+ callers accessing the IVR and booking appointments simultaneously.
Verifies SQLite WAL isolation, atomic locking (BEGIN IMMEDIATE), and race-condition safety.
"""
import asyncio
import os
import pytest
from services.db_service import DatabaseService

TEST_CONCURRENT_DB = "test_concurrent.db"

@pytest.fixture
def concurrent_db():
    if os.path.exists(TEST_CONCURRENT_DB):
        try:
            os.remove(TEST_CONCURRENT_DB)
        except OSError:
            pass
    db = DatabaseService(db_path=TEST_CONCURRENT_DB)
    db.seed_initial_data(reset=True)
    yield db
    if os.path.exists(TEST_CONCURRENT_DB):
        try:
            os.remove(TEST_CONCURRENT_DB)
        except OSError:
            pass

@pytest.mark.asyncio
async def test_simultaneous_callers_booking_same_slot(concurrent_db):
    """
    Simulates 2 callers submitting appointment bookings at the EXACT SAME instant.
    Both should succeed with unique token numbers and appointment codes without collision.
    """
    db = concurrent_db
    target_date = "2026-10-15"
    slot_time = "સાંજે 5:00 થી 6:00"

    async def book_caller(caller_name: str, mobile: str):
        # Run synchronous DB booking in thread executor to simulate concurrent FastAGI / WebSocket workers
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: db.book_appointment(
                doctor_id=1,
                mobile_number=mobile,
                patient_name_gu=caller_name,
                target_date=target_date,
                slot_time_gu=slot_time,
                source="IVR"
            )
        )

    # Launch Caller 1 and Caller 2 concurrently
    res1, res2 = await asyncio.gather(
        book_caller("રમેશભાઈ પટેલ", "9825012345"),
        book_caller("સુરેશભાઈ શાહ", "9898012345")
    )

    assert res1["success"] is True
    assert res2["success"] is True

    # Tokens must be sequential and distinct
    assert res1["token_number"] != res2["token_number"]
    assert set([res1["token_number"], res2["token_number"]]) == {1, 2}
    assert res1["appointment_code"] != res2["appointment_code"]

    # Verify both are written cleanly to the DB
    appts = db.get_appointments_list(date_str=target_date, doctor_id=1)
    assert len(appts) == 2
    names = [a["patient_name_gu"] for a in appts]
    assert "રમેશભાઈ પટેલ" in names
    assert "સુરેશભાઈ શાહ" in names

@pytest.mark.asyncio
async def test_simultaneous_callers_slot_capacity_limit(concurrent_db):
    """
    Sets slot limit to 2.
    Launches 3 concurrent callers attempting to book the 2 remaining spots.
    Exactly 2 must succeed, and 1 must receive SLOT_FULL (no double booking).
    """
    db = concurrent_db
    target_date = "2026-10-16"
    slot_time = "સાંજે 6:00 થી 7:00"

    # Set max_slots to 2 for this schedule
    conn = db.get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE doctor_schedules SET max_slots = 2 WHERE doctor_id = 1 AND slot_time_gu = ?",
        (slot_time,)
    )
    conn.commit()
    conn.close()

    async def book_caller(name: str, mobile: str):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: db.book_appointment(
                doctor_id=1,
                mobile_number=mobile,
                patient_name_gu=name,
                target_date=target_date,
                slot_time_gu=slot_time,
                source="IVR"
            )
        )

    results = await asyncio.gather(
        book_caller("દર્દી ૧", "9800000001"),
        book_caller("દર્દી ૨", "9800000002"),
        book_caller("દર્દી ૩", "9800000003")
    )

    success_count = sum(1 for r in results if r["success"] is True)
    failed_count = sum(1 for r in results if r["success"] is False)

    assert success_count == 2
    assert failed_count == 1
    failed_result = [r for r in results if not r["success"]][0]
    assert failed_result["error"] == "SLOTS_FULL"
