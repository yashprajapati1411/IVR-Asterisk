"""
Exotel WebSocket Channel for Asterisk IVR Engine.
Bridges bidirectional real-time audio and DTMF between Exotel's Voicebot Applet
and the Python IVREngine state machine.
"""
import os
import wave
import json
import base64
import asyncio
import logging
import math
import struct
import shutil
from typing import Optional, Dict

logger = logging.getLogger("ExotelWSChannel")

class ExotelWSChannel:
    """
    Implements the AGIChannel interface for Exotel's Voicebot Applet over WebSocket.
    Allows IVREngine to run transparently on Exotel calls without modification.
    """

    def __init__(
        self,
        websocket,
        stream_sid: str = "",
        call_sid: str = "",
        caller_id: str = "",
        project_root: Optional[str] = None,
        pace_audio: bool = True
    ):
        self.websocket = websocket
        self.stream_sid = stream_sid
        self.call_sid = call_sid
        self.caller_id = caller_id
        self.is_hungup = False
        self.pace_audio = pace_audio
        self.env: Dict[str, str] = {
            "agi_callerid": caller_id,
            "agi_uniqueid": call_sid or f"exo_{stream_sid}"
        }
        self.dtmf_queue: asyncio.Queue = asyncio.Queue()
        self.audio_queue: asyncio.Queue = asyncio.Queue()
        self.sequence_number = 1

        self.project_root = project_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.sounds_dirs = [
            os.path.join(self.project_root, "sounds", "gu"),
            os.path.join(self.project_root, "sounds"),
            "/var/lib/asterisk/sounds/ivr/gu",
            "/var/lib/asterisk/sounds/ivr",
            "/app/sounds/gu",
            "/app/sounds",
        ]

    def _resolve_wav_path(self, filename: str) -> Optional[str]:
        """Resolves audio filename to an existing WAV path on the filesystem."""
        candidates = []
        clean = filename[:-4] if filename.endswith(".wav") else filename

        # Direct absolute or relative path
        candidates.append(f"{clean}.wav")
        candidates.append(filename)

        base = os.path.basename(clean)
        # In configured sound dirs
        for sdir in self.sounds_dirs:
            candidates.append(os.path.join(sdir, f"{base}.wav"))
            candidates.append(os.path.join(sdir, "digits", f"{base}.wav"))
            candidates.append(os.path.join(sdir, "cache", f"{base}.wav"))

        for c in candidates:
            if os.path.exists(c) and os.path.isfile(c):
                return os.path.abspath(c)

        logger.warning(f"Audio file not found for: '{filename}' (searched {len(candidates)} locations)")
        return None

    async def init_session(self) -> Dict[str, str]:
        """Returns initialized environment variables."""
        return self.env

    async def answer(self) -> bool:
        """Answers the call session."""
        logger.info(f"Answering Exotel call session: {self.call_sid}")
        return True

    async def verbose(self, message: str, level: int = 1):
        """Logs verbose message."""
        logger.info(f"[ExotelCall {self.call_sid}] {message}")

    async def stream_file(self, filename: str, escape_digits: str = "") -> Optional[str]:
        """
        Streams audio file to Exotel as base64-encoded linear PCM chunks (3200 bytes / 100ms).
        Returns pressed escape digit if caller interrupts (barge-in), else None.
        """
        if self.is_hungup:
            return None

        wav_path = self._resolve_wav_path(filename)
        if not wav_path:
            return None

        logger.info(f"Streaming audio file to Exotel: {os.path.basename(wav_path)}")

        try:
            with wave.open(wav_path, "rb") as w:
                n_channels = w.getnchannels()
                sampwidth = w.getsampwidth()
                framerate = w.getframerate()

                # Read raw PCM frames
                raw_pcm = w.readframes(w.getnframes())

            chunk_size = 1600  # 100ms at 8kHz 16-bit mono PCM (800 samples * 2 bytes = 1600 bytes)
            offset = 0

            while offset < len(raw_pcm) and not self.is_hungup:
                # Check for barge-in DTMF digits
                if escape_digits and not self.dtmf_queue.empty():
                    digit = await self.dtmf_queue.get()
                    if digit in escape_digits or not escape_digits:
                        logger.info(f"Barge-in DTMF received during playback: '{digit}'")
                        await self.clear_audio()
                        return digit

                chunk = raw_pcm[offset : offset + chunk_size]
                offset += chunk_size

                # Pad last chunk if smaller than 320 bytes to maintain Exotel frame multiple
                if len(chunk) % 320 != 0:
                    padding = 320 - (len(chunk) % 320)
                    chunk += b"\x00" * padding

                payload = base64.b64encode(chunk).decode("ascii")
                msg = {
                    "event": "media",
                    "stream_sid": self.stream_sid,
                    "media": {
                        "payload": payload
                    }
                }
                await self.websocket.send_text(json.dumps(msg))

                if self.pace_audio:
                    # 98ms sleep for 100ms chunk keeps smooth real-time stream without buffer overflow
                    await asyncio.sleep(0.098)

            return None

        except Exception as e:
            logger.error(f"Error streaming audio to Exotel: {e}")
            return None

    async def clear_audio(self):
        """Sends clear event to Exotel to interrupt playback (barge-in)."""
        try:
            msg = {
                "event": "clear",
                "stream_sid": self.stream_sid
            }
            await self.websocket.send_text(json.dumps(msg))
        except Exception as e:
            logger.debug(f"Failed to send clear event: {e}")

    async def get_data(self, filename: str, timeout_ms: int = 5000, max_digits: int = 1) -> Optional[str]:
        """
        Plays audio prompt and waits for DTMF digits from caller.
        """
        if self.is_hungup:
            return None

        # Play audio prompt (can be interrupted by DTMF)
        first_digit = None
        if filename:
            first_digit = await self.stream_file(filename, escape_digits="0123456789*#")

        collected = []
        if first_digit:
            if first_digit == "#":
                return ""
            collected.append(first_digit)
            if len(collected) >= max_digits:
                return "".join(collected)

        # Wait for remaining digits up to timeout
        timeout_sec = timeout_ms / 1000.0
        start_time = asyncio.get_event_loop().time()

        while len(collected) < max_digits and not self.is_hungup:
            elapsed = asyncio.get_event_loop().time() - start_time
            remaining = timeout_sec - elapsed
            if remaining <= 0:
                break

            try:
                digit = await asyncio.wait_for(self.dtmf_queue.get(), timeout=remaining)
                if digit == "#":
                    break
                collected.append(digit)
            except asyncio.TimeoutError:
                break

        res = "".join(collected) if collected else None
        logger.info(f"get_data result: '{res}'")
        return res

    async def record_file(
        self,
        filename: str,
        format_type: str = "wav",
        escape_digits: str = "#",
        timeout_ms: int = 6000,
        beep: bool = True,
        silence_sec: int = 2
    ) -> bool:
        """
        Records user voice from Exotel incoming media stream packets.
        Saves output as 8000Hz 16-bit mono PCM WAV file.
        Detects speech via RMS energy and stops after silence_sec of silence following speech,
        or upon DTMF escape_digits or timeout_ms.
        """
        if self.is_hungup:
            return False

        if beep:
            await self.stream_file("gu/beep")

        # Drain old audio packets received before recording started
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        timeout_sec = max(3.0, timeout_ms / 1000.0)
        silence_timeout = max(1.2, float(silence_sec))
        frames = []
        start_time = asyncio.get_event_loop().time()
        speech_detected = False
        last_speech_time = None

        def _get_rms(data: bytes) -> float:
            if not data or len(data) < 2:
                return 0.0
            num_samples = len(data) // 2
            try:
                samples = struct.unpack(f"<{num_samples}h", data[:num_samples * 2])
                sum_sq = sum(s * s for s in samples)
                return math.sqrt(sum_sq / num_samples)
            except Exception:
                return 0.0

        while not self.is_hungup:
            now = asyncio.get_event_loop().time()
            elapsed = now - start_time
            if elapsed >= timeout_sec:
                logger.info(f"[Exotel Record] Reached maximum recording timeout ({elapsed:.1f}s)")
                break

            # Check if caller pressed escape digit
            if not self.dtmf_queue.empty():
                digit = self.dtmf_queue.get_nowait()
                if digit in escape_digits:
                    logger.info(f"[Exotel Record] Stopped by DTMF escape digit: '{digit}'")
                    break

            try:
                chunk = await asyncio.wait_for(self.audio_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                chunk = None

            if chunk:
                frames.append(chunk)
                rms = _get_rms(chunk)
                # Telephony speech threshold for 16-bit linear PCM (280.0 captures normal speaking voice)
                if rms >= 280.0:
                    if not speech_detected:
                        logger.info(f"[Exotel Record] Speech activity started (RMS={rms:.1f})")
                    speech_detected = True
                    last_speech_time = now

            # If speech has been detected and caller has now stopped speaking for at least silence_timeout
            if speech_detected and last_speech_time is not None:
                silence_gap = now - last_speech_time
                total_bytes = sum(len(f) for f in frames)
                # At 8kHz 16-bit mono PCM: 1 sec = 16,000 bytes. Ensure at least 1.0s of audio captured
                if silence_gap >= silence_timeout and total_bytes >= 16000:
                    logger.info(f"[Exotel Record] Post-speech silence ({silence_gap:.1f}s) detected. Completing recording.")
                    break

        out_path = f"{filename}.wav" if not filename.endswith(".wav") else filename
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

        audio_bytes = b"".join(frames)
        logger.info(f"[Exotel Record] Total recorded frames: {len(frames)}, bytes: {len(audio_bytes)}")

        try:
            with wave.open(out_path, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(8000)
                w.writeframes(audio_bytes)
            logger.info(f"Successfully recorded Exotel audio -> {out_path} ({os.path.getsize(out_path)} bytes)")

            # Also mirror to alternate cache locations so all services can locate the file
            alt_cache_dirs = [
                "/var/lib/asterisk/sounds/ivr/cache",
                "/app/sounds/cache",
                os.path.join(self.project_root, "sounds", "cache")
            ]
            for alt_dir in alt_cache_dirs:
                if os.path.exists(alt_dir) and os.path.isdir(alt_dir):
                    alt_file = os.path.join(alt_dir, os.path.basename(out_path))
                    if os.path.abspath(alt_file) != os.path.abspath(out_path):
                        try:
                            shutil.copy2(out_path, alt_file)
                            logger.info(f"[Exotel Record] Mirrored audio to {alt_file}")
                        except Exception as err:
                            logger.warning(f"Could not mirror audio to {alt_file}: {err}")

            return True
        except Exception as e:
            logger.error(f"Error saving recorded WAV file: {e}")
            return False

    async def say_digits(self, digits: str, escape_digits: str = "") -> Optional[str]:
        """Pronounces digits by streaming digit WAV files."""
        for d in str(digits):
            if self.is_hungup:
                break
            digit_res = await self.stream_file(f"digits/{d}.wav", escape_digits=escape_digits)
            if digit_res:
                return digit_res
            if self.pace_audio:
                await asyncio.sleep(0.05)
        return None

    async def hangup(self):
        """Ends the call session and closes the WebSocket."""
        if not self.is_hungup:
            self.is_hungup = True
            logger.info(f"Ending Exotel call session: {self.call_sid}")
            try:
                msg = {
                    "event": "clear",
                    "stream_sid": self.stream_sid
                }
                await self.websocket.send_text(json.dumps(msg))
            except Exception:
                pass
            try:
                await self.websocket.close()
            except Exception:
                pass
