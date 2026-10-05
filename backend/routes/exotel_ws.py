"""
Exotel Voicebot WebSocket Route and Passthru Webhook Endpoint.
Handles incoming WebSocket audio connections from Exotel's Voicebot Applet (Beta).
"""
import os
import json
import base64
import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse

from services.exotel_channel import ExotelWSChannel
from agi.ivr_engine import IVREngine
from services.db_service import DatabaseService
from services.stt_service import SarvamSTTService
from services.tts_service import TTSService

logger = logging.getLogger("ExotelRoute")
router = APIRouter(tags=["Exotel"])

# Shared services
db = DatabaseService()
stt = SarvamSTTService()
tts = TTSService()

async def _listen_incoming_exotel_events(websocket: WebSocket, channel: ExotelWSChannel):
    """
    Asynchronously listens for incoming Exotel WebSocket events:
    - 'media': base64-encoded audio chunk from caller
    - 'dtmf': touch-tone keypresses from caller
    - 'stop': customer hung up or stream closed
    """
    try:
        while not channel.is_hungup:
            message_text = await websocket.receive_text()
            if not message_text:
                continue

            data = json.loads(message_text)
            event = data.get("event")
            logger.info(f"[Exotel WS Inbound] event='{event}' keys={list(data.keys())}")

            if event == "media":
                payload = data.get("media", {}).get("payload", "")
                if payload:
                    raw_audio = base64.b64decode(payload)
                    await channel.audio_queue.put(raw_audio)

            elif event == "dtmf":
                dtmf_data = data.get("dtmf", {})
                digit = str(dtmf_data.get("digit", ""))
                if digit:
                    logger.info(f"[Exotel DTMF] Caller pressed: '{digit}'")
                    await channel.dtmf_queue.put(digit)

            elif event == "stop":
                logger.info(f"[Exotel Event] Call stream stopped by Exotel: {data}")
                channel.is_hungup = True
                break

            elif event == "mark":
                logger.info(f"[Exotel Mark] Milestone reached: {data.get('mark')}")

    except WebSocketDisconnect:
        logger.info("[Exotel WebSocket] Client disconnected.")
        channel.is_hungup = True
    except Exception as e:
        logger.warning(f"[Exotel WebSocket] Listener error: {e}")
        channel.is_hungup = True

@router.websocket("/voicebot")
async def exotel_voicebot_websocket(websocket: WebSocket, pace_audio: bool = True):
    """
    Bidirectional WebSocket endpoint for Exotel's Voicebot Applet.
    URL to configure in Exotel App Bazaar:
    ws://<your-server-ip>:8000/exotel/voicebot
    """
    await websocket.accept()
    logger.info("[Exotel WebSocket] New connection established. Waiting for handshake...")

    stream_sid = ""
    call_sid = ""
    caller_id = ""

    # 1. Read initial handshake events ('connected', 'start')
    try:
        # Exotel sends {"event": "connected"} first
        init_msg = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        init_data = json.loads(init_msg)
        logger.info(f"[Exotel WebSocket] Received initial event: {init_data.get('event')}")

        # Followed by {"event": "start", "start": {...}}
        start_msg = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        start_data = json.loads(start_msg)

        if start_data.get("event") == "start":
            start_payload = start_data.get("start", {})
            stream_sid = start_data.get("stream_sid") or start_payload.get("stream_sid") or ""
            call_sid = start_payload.get("call_sid", "")
            caller_id = start_payload.get("from", "")
            logger.info(f"[Exotel Call Start] Caller: {caller_id}, CallSID: {call_sid}, StreamSID: {stream_sid}")
            logger.info(f"[Exotel START FULL DATA]: {json.dumps(start_data)}")
        else:
            logger.warning(f"[Exotel Handshake] Unexpected second event: {start_data.get('event')}")

    except Exception as e:
        logger.error(f"[Exotel Handshake Error] Failed to complete handshake: {e}")
        await websocket.close()
        return

    # 2. Initialize ExotelWSChannel adapter
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    channel = ExotelWSChannel(
        websocket=websocket,
        stream_sid=stream_sid,
        call_sid=call_sid,
        caller_id=caller_id,
        project_root=project_root,
        pace_audio=pace_audio
    )

    # 3. Launch background listener for incoming Exotel packets
    listener_task = asyncio.create_task(_listen_incoming_exotel_events(websocket, channel))

    # 4. Launch IVREngine with our channel adapter
    try:
        engine = IVREngine(
            channel=channel,
            db_service=db,
            stt_service=stt,
            tts_service=tts,
            sounds_dir=os.path.join(project_root, "sounds")
        )
        logger.info(f"[Exotel IVR] Running IVR State Machine for caller: {caller_id}...")
        await engine.run()
        logger.info(f"[Exotel IVR] Call completed successfully for: {caller_id}")

    except Exception as e:
        logger.exception(f"[Exotel IVR Error] Exception in IVR execution: {e}")

    finally:
        channel.is_hungup = True
        listener_task.cancel()
        try:
            await channel.hangup()
        except Exception:
            pass

@router.api_route("/passthru", methods=["GET", "POST"])
async def exotel_passthru_webhook(request: Request):
    """
    Passthru Applet Webhook called by Exotel right after the Voicebot Applet.
    Logs call metadata, recording URLs, and duration.
    """
    params = dict(request.query_params)
    body = {}
    try:
        body = await request.json()
    except Exception:
        try:
            form = await request.form()
            body = dict(form)
        except Exception:
            pass

    call_sid = params.get("CallSid") or body.get("CallSid", "")
    recording_url = params.get("RecordingUrl") or body.get("RecordingUrl", "")
    duration = params.get("DialCallDuration") or body.get("Legs", [{}])[0].get("Duration", "")

    logger.info(f"[Exotel Passthru] CallSID: {call_sid}, Duration: {duration}s, Recording: {recording_url}")
    return JSONResponse({
        "status": "success",
        "message": "Call metadata recorded",
        "call_sid": call_sid
    })
