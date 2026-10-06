"""
Unit and Integration Tests for Exotel Voicebot WebSocket and Passthru endpoints.
Tests bidirectional media streaming, DTMF processing, barge-in, and state transitions.
"""
import os
import json
import asyncio
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client_app():
    from backend.app import app
    from services.db_service import DatabaseService
    db = DatabaseService()
    db.seed_initial_data(reset=True)
    return TestClient(app)

def test_exotel_passthru_get(client_app):
    """Tests Exotel Passthru Applet webhook via GET."""
    response = client_app.get("/exotel/passthru", params={
        "CallSid": "exocall_123",
        "DialCallDuration": "45",
        "RecordingUrl": "https://api.exotel.com/recordings/exocall_123.mp3"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["call_sid"] == "exocall_123"

def test_exotel_passthru_post(client_app):
    """Tests Exotel Passthru Applet webhook via POST."""
    response = client_app.post("/exotel/passthru", json={
        "CallSid": "exocall_456",
        "DialCallDuration": "120",
        "RecordingUrl": "https://api.exotel.com/recordings/exocall_456.mp3"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["call_sid"] == "exocall_456"

def test_exotel_voicebot_option_9_flow(client_app):
    """
    Tests Exotel WebSocket connection:
    - Handshake ('connected', 'start')
    - Welcome menu media received
    - Send DTMF '9' (Reception Number)
    - Reception number media received
    - Send DTMF '2' (Return to Main Menu)
    - Send DTMF '3' (Other Info)
    - Stop event
    """
    with client_app.websocket_connect("/exotel/voicebot?pace_audio=false") as ws:
        # 1. Send Exotel 'connected' event
        ws.send_text(json.dumps({"event": "connected"}))

        # 2. Send Exotel 'start' event
        ws.send_text(json.dumps({
            "event": "start",
            "stream_sid": "stream_test_001",
            "start": {
                "call_sid": "call_test_001",
                "from": "9825012345",
                "to": "08012345678"
            }
        }))

        # 3. Read media messages sent by IVR engine (welcome_menu audio frames)
        media_received = 0
        while True:
            msg_raw = ws.receive_text()
            msg = json.loads(msg_raw)
            if msg.get("event") == "media":
                media_received += 1
                assert "payload" in msg["media"]
                assert msg["stream_sid"] == "stream_test_001"
                # Once we receive enough chunks of the welcome menu, send DTMF '9'
                if media_received >= 3:
                    break

        assert media_received >= 3

        # 4. Caller presses DTMF '9' for Reception Number
        ws.send_text(json.dumps({
            "event": "dtmf",
            "stream_sid": "stream_test_001",
            "dtmf": {"digit": "9"}
        }))

        # 5. Receive reception number media chunks
        rec_media = 0
        while True:
            msg_raw = ws.receive_text()
            msg = json.loads(msg_raw)
            if msg.get("event") == "media":
                rec_media += 1
                if rec_media >= 3:
                    break

        assert rec_media >= 3

        # 6. Caller presses '2' to return to Main Menu
        ws.send_text(json.dumps({
            "event": "dtmf",
            "stream_sid": "stream_test_001",
            "dtmf": {"digit": "2"}
        }))

        # 7. Caller presses '3' for Other Info
        ws.send_text(json.dumps({
            "event": "dtmf",
            "stream_sid": "stream_test_001",
            "dtmf": {"digit": "3"}
        }))

        # 8. Send Stop event to end the call gracefully
        ws.send_text(json.dumps({
            "event": "stop",
            "stream_sid": "stream_test_001",
            "stop": {"call_sid": "call_test_001", "reason": "callended"}
        }))

@pytest.mark.asyncio
async def test_exotel_record_file_speech_and_silence(tmp_path):
    import struct
    import wave
    from services.exotel_channel import ExotelWSChannel
    channel = ExotelWSChannel(
        websocket=None,
        stream_sid="stream_test",
        call_sid="call_test",
        caller_id="9825012345",
        project_root=str(tmp_path)
    )

    speech_sample = struct.pack("<h", 2000) * 800
    silence_sample = struct.pack("<h", 0) * 800

    async def feeder():
        await asyncio.sleep(0.02)
        # Stream speech frames (1.2s)
        for _ in range(12):
            await channel.audio_queue.put(speech_sample)
            await asyncio.sleep(0.005)
        # Stream silence frames (1.5s)
        for _ in range(15):
            await channel.audio_queue.put(silence_sample)
            await asyncio.sleep(0.005)

    feeder_task = asyncio.create_task(feeder())
    out_file = str(tmp_path / "test_rec")
    success = await channel.record_file(out_file, timeout_ms=5000, beep=False, silence_sec=1)
    await feeder_task

    assert success is True
    saved_wav = f"{out_file}.wav"
    assert os.path.exists(saved_wav)
    assert os.path.getsize(saved_wav) >= 16000
    with wave.open(saved_wav, "rb") as w:
        assert w.getframerate() == 8000
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2

@pytest.mark.asyncio
async def test_exotel_record_file_escape_digit(tmp_path):
    import struct
    from services.exotel_channel import ExotelWSChannel
    channel = ExotelWSChannel(
        websocket=None,
        stream_sid="stream_test",
        call_sid="call_test",
        caller_id="9825012345",
        project_root=str(tmp_path)
    )
    speech_sample = struct.pack("<h", 2000) * 800

    async def feeder_escape():
        await asyncio.sleep(0.02)
        await channel.audio_queue.put(speech_sample)
        await channel.dtmf_queue.put("#")

    feed_task = asyncio.create_task(feeder_escape())
    out_file = str(tmp_path / "test_escape")
    success = await channel.record_file(out_file, timeout_ms=5000, beep=False)
    await feed_task
    assert success is True
    assert os.path.exists(f"{out_file}.wav")

def test_stt_alternate_path_resolution():
    import wave
    from services.stt_service import SarvamSTTService
    stt = SarvamSTTService(api_key="mock_key")
    cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sounds", "cache")
    os.makedirs(cache_dir, exist_ok=True)
    test_wav = os.path.join(cache_dir, "test_stt_alt.wav")
    with wave.open(test_wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00\x00" * 800)

    try:
        res = stt.transcribe_audio("/some/nonexistent/path/test_stt_alt.wav")
        assert res.get("error") != "Audio file not found or empty"
    finally:
        if os.path.exists(test_wav):
            os.remove(test_wav)

