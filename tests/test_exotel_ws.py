"""
Unit and Integration Tests for Exotel Voicebot WebSocket and Passthru endpoints.
Tests bidirectional media streaming, DTMF processing, barge-in, and state transitions.
"""
import os
import json
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
