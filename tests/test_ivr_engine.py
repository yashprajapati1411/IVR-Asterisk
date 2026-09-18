"""
Unit and Integration Tests for Asterisk IVR Engine.
Covers all branches: Welcome menu, Dr. Shaishav, Dr. Jaydeep, Other info,
Availability checks, Mobile validation and retries, Name STT capture and re-prompting,
Final confirmation, DB booking, and returning to Main Menu.
"""
import os
import pytest
from agi.agi_channel import AGIChannel
from agi.ivr_engine import IVREngine
from services.db_service import DatabaseService
from services.stt_service import SarvamSTTService
from services.tts_service import TTSService

TEST_DB_PATH = "test_ivr_engine.db"

class MockAGIChannel(AGIChannel):
    """Programmatic mock of AGIChannel that feeds pre-scripted DTMF inputs and records commands."""
    def __init__(self, inputs=None):
        super().__init__()
        self.inputs = list(inputs or [])
        self.input_idx = 0
        self.command_log = []
        self.files_streamed = []
        self.files_recorded = []

    async def init_session(self):
        return {"agi_callerid": "9825000000", "agi_uniqueid": "test_unique_1"}

    async def answer(self):
        self.command_log.append("ANSWER")
        return True

    async def verbose(self, message: str, level: int = 1):
        self.command_log.append(f"VERBOSE: {message}")

    async def stream_file(self, filename: str, escape_digits: str = ""):
        self.command_log.append(f"STREAM: {os.path.basename(filename)}")
        self.files_streamed.append(os.path.basename(filename))
        return None

    async def get_data(self, filename: str, timeout_ms: int = 5000, max_digits: int = 1):
        self.command_log.append(f"GET_DATA: {os.path.basename(filename)} (max={max_digits})")
        self.files_streamed.append(os.path.basename(filename))
        if self.input_idx < len(self.inputs):
            val = str(self.inputs[self.input_idx])
            self.input_idx += 1
            return val
        return ""

    async def record_file(self, filename: str, format_type: str = "wav", escape_digits: str = "#", timeout_ms: int = 5000, beep: bool = True, silence_sec: int = 2):
        self.command_log.append(f"RECORD: {os.path.basename(filename)}")
        self.files_recorded.append(filename)
        return True

    async def hangup(self):
        self.command_log.append("HANGUP")
        self.is_hungup = True

@pytest.fixture
def setup_env():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    db = DatabaseService(db_path=TEST_DB_PATH)
    db.seed_initial_data(reset=True)
    stt = SarvamSTTService(api_key="mock_key")
    tts = TTSService(api_key="mock_key", cache_dir="test_engine_cache")
    yield db, stt, tts
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

@pytest.mark.asyncio
async def test_happy_path_dr_shaishav(setup_env):
    db, stt, tts = setup_env
    stt.set_mock_name("રમેશભાઈ પટેલ")

    # Inputs:
    # 1: Welcome Menu -> 1 (Dr. Shaishav)
    # 2: Slot Announcement -> 1 (Booking)
    # 3: Enter Mobile -> "9825012345"
    # 4: Mobile Confirm -> 1 (Confirm)
    # 5: Name Confirm -> 1 (Confirm recognized name)
    # 6: Final Confirm -> 1 (Confirm booking)
    inputs = ["1", "1", "9825012345#", "1", "1", "1"]
    channel = MockAGIChannel(inputs=inputs)
    engine = IVREngine(channel=channel, db_service=db, stt_service=stt, tts_service=tts)

    await engine.run()

    assert engine.session.state == "DONE"
    assert engine.session.selected_doctor_id == 1
    assert engine.session.mobile_number == "9825012345"
    assert engine.session.patient_name_gu == "રમેશભાઈ પટેલ"
    assert engine.session.appointment_code is not None
    assert "APT-" in engine.session.appointment_code

    # Check DB record
    conn = db.get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM appointments WHERE appointment_code = ?", (engine.session.appointment_code,))
    row = c.fetchone()
    assert row is not None
    assert row["status"] == "CONFIRMED"
    conn.close()

@pytest.mark.asyncio
async def test_path_dr_jaydeep(setup_env):
    db, stt, tts = setup_env
    stt.set_mock_name("પ્રિયાબેન શાહ")

    # Inputs:
    # Welcome -> 2 (Dr. Jaydeep)
    # Slot -> 1 (Book)
    # Mobile -> "9898012345"
    # Mobile Confirm -> 1
    # Name Confirm -> 1
    # Final Confirm -> 1
    inputs = ["2", "1", "9898012345", "1", "1", "1"]
    channel = MockAGIChannel(inputs=inputs)
    engine = IVREngine(channel=channel, db_service=db, stt_service=stt, tts_service=tts)

    await engine.run()

    assert engine.session.state == "DONE"
    assert engine.session.selected_doctor_id == 2
    assert engine.session.selected_doctor_name_en == "Dr. Jaydeep"
    assert engine.session.patient_name_gu == "પ્રિયાબેન શાહ"
    assert "APT-" in engine.session.appointment_code

@pytest.mark.asyncio
async def test_path_other_information(setup_env):
    db, stt, tts = setup_env
    # Welcome -> 3 (Other info)
    inputs = ["3"]
    channel = MockAGIChannel(inputs=inputs)
    engine = IVREngine(channel=channel, db_service=db, stt_service=stt, tts_service=tts)

    await engine.run()

    assert engine.session.state == "HANGUP"
    assert any("other_info" in cmd for cmd in channel.files_streamed)
    assert engine.session.selected_doctor_id is None

@pytest.mark.asyncio
async def test_no_slots_and_main_menu(setup_env):
    db, stt, tts = setup_env
    # Set doctor 1 slots to 0
    db.set_doctor_slots(doctor_id=1, max_slots=0)

    # Inputs:
    # 1: Welcome -> 1 (Dr. Shaishav)
    # 2: No slots -> 2 (Return to Main Menu)
    # 3: At Welcome -> 3 (Other info -> Hangup)
    inputs = ["1", "2", "3"]
    channel = MockAGIChannel(inputs=inputs)
    engine = IVREngine(channel=channel, db_service=db, stt_service=stt, tts_service=tts)

    await engine.run()

    assert any("no_slots_today" in cmd for cmd in channel.files_streamed)
    assert any("other_info" in cmd for cmd in channel.files_streamed)

@pytest.mark.asyncio
async def test_invalid_mobile_retry(setup_env):
    db, stt, tts = setup_env
    stt.set_mock_name("સુરેશભાઈ")

    # Inputs:
    # 1: Welcome -> 1 (Dr. Shaishav)
    # 2: Slot -> 1 (Book)
    # 3: Mobile -> "12345" (Invalid - not 10 digits and starts with 1)
    # 4: Mobile Retry -> "9825098765" (Valid)
    # 5: Mobile Confirm -> 1
    # 6: Name Confirm -> 1
    # 7: Final Confirm -> 1
    inputs = ["1", "1", "12345", "9825098765", "1", "1", "1"]
    channel = MockAGIChannel(inputs=inputs)
    engine = IVREngine(channel=channel, db_service=db, stt_service=stt, tts_service=tts)

    await engine.run()

    assert any("invalid_mobile" in cmd for cmd in channel.files_streamed)
    assert engine.session.state == "DONE"
    assert engine.session.mobile_number == "9825098765"

@pytest.mark.asyncio
async def test_name_reenter_retry(setup_env):
    db, stt, tts = setup_env
    stt.set_mock_name("મનોજભાઈ")

    # Inputs:
    # Welcome -> 1
    # Slot -> 1
    # Mobile -> "9825011223"
    # Mobile Confirm -> 1
    # Name Confirm 1st attempt -> 2 (Reject / Retry)
    # Name Confirm 2nd attempt -> 1 (Confirm)
    # Final Confirm -> 1
    inputs = ["1", "1", "9825011223", "1", "2", "1", "1"]
    channel = MockAGIChannel(inputs=inputs)
    engine = IVREngine(channel=channel, db_service=db, stt_service=stt, tts_service=tts)

    await engine.run()

    assert len(channel.files_recorded) == 2  # Recorded twice
    assert engine.session.state == "DONE"

@pytest.mark.asyncio
async def test_final_confirmation_cancel_to_menu(setup_env):
    db, stt, tts = setup_env
    stt.set_mock_name("ટેસ્ટ પટેલ")

    # Inputs:
    # Welcome -> 1
    # Slot -> 1
    # Mobile -> "9825033445"
    # Mobile Confirm -> 1
    # Name Confirm -> 1
    # Final Confirm -> 2 (Return to Main Menu!)
    # Welcome -> 3 (Other Info -> Hangup)
    inputs = ["1", "1", "9825033445", "1", "1", "2", "3"]
    channel = MockAGIChannel(inputs=inputs)
    engine = IVREngine(channel=channel, db_service=db, stt_service=stt, tts_service=tts)

    await engine.run()

    assert engine.session.appointment_code is None # No appointment created
    assert any("other_info" in cmd for cmd in channel.files_streamed)
