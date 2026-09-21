"""
Text-to-Speech (TTS) Service for Asterisk Gujarati Prompts.
Supports Sarvam TTS (bulbul:v1), Edge-TTS neural voice (gu-IN-DhwaniNeural),
and audio conversion to Asterisk 8kHz mono PCM WAV with 1.5x speed.
"""
import os
import io
import sys
import wave
import hashlib
import logging
import base64
import shutil
import subprocess
import requests
from typing import Optional
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("TTSService")

SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"
env_cache = os.getenv("ASTERISK_CACHE_DIR", "").strip()
env_sounds = os.getenv("ASTERISK_SOUNDS_DIR", "").strip()
if env_cache:
    CACHE_DIR = env_cache
elif env_sounds:
    CACHE_DIR = os.path.join(env_sounds, "cache")
else:
    CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sounds", "cache")

def _convert_to_asterisk_wav(input_path: str, output_wav: str) -> bool:
    """Converts any audio file to Asterisk 8000Hz 16-bit mono PCM WAV using ffmpeg or sox."""
    ffmpeg_bin = shutil.which("ffmpeg") or (r"C:\ffmpeg-8.1-essentials_build\bin\ffmpeg.exe" if os.path.exists(r"C:\ffmpeg-8.1-essentials_build\bin\ffmpeg.exe") else None)
    sox_bin = shutil.which("sox")

    if ffmpeg_bin:
        cmd = [ffmpeg_bin, "-y", "-i", input_path, "-ar", "8000", "-ac", "1", "-sample_fmt", "s16", output_wav]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res.returncode == 0
    elif sox_bin:
        cmd = [sox_bin, input_path, "-r", "8000", "-c", "1", "-b", "16", output_wav]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res.returncode == 0
    return False

class TTSService:
    def __init__(self, api_key: Optional[str] = None, cache_dir: Optional[str] = None, speed_rate: str = "+45%"):
        self.api_key = api_key or os.getenv("SARVAM_API_KEY", "")
        self.cache_dir = (cache_dir.strip() if cache_dir and cache_dir.strip() else CACHE_DIR)
        self.speed_rate = speed_rate # 1.5x speed rate
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_path(self, text: str) -> str:
        # Include speed rate in hash so changes in rate invalidate old cache
        text_hash = hashlib.md5(f"{text}_{self.speed_rate}".encode("utf-8")).hexdigest()
        return os.path.join(self.cache_dir, f"tts_{text_hash}.wav")

    def synthesize_gujarati(self, text: str) -> str:
        """
        Synthesizes Gujarati text to an 8kHz 16-bit mono WAV file at 1.5x speed.
        Returns the absolute filepath to the .wav file.
        """
        cache_path = self._get_cache_path(text)
        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 1000:
            return cache_path

        # 1. Try Sarvam TTS (bulbul:v3) if key provided and not previously failed with quota error
        if self.api_key and not self.api_key.startswith("mock") and len(self.api_key) > 5 and getattr(self, "_sarvam_active", True):
            try:
                headers = {
                    "api-subscription-key": self.api_key,
                    "Content-Type": "application/json"
                }
                payload = {
                    "inputs": [text],
                    "target_language_code": "gu-IN",
                    "speaker": "pooja",
                    "pitch": 0,
                    "pace": 1.4,
                    "loudness": 1.5,
                    "speech_sample_rate": 8000,
                    "enable_preprocessing": True,
                    "model": "bulbul:v3"
                }
                res = requests.post(SARVAM_TTS_URL, json=payload, headers=headers, timeout=5.0)
                if res.status_code == 200:
                    audios = res.json().get("audios", [])
                    if audios:
                        raw_audio = base64.b64decode(audios[0])
                        with open(cache_path, "wb") as f:
                            f.write(raw_audio)
                        logger.info(f"Synthesized Gujarati audio via Sarvam TTS (bulbul:v3) -> {cache_path}")
                        return cache_path
                else:
                    if res.status_code in (401, 402, 403):
                        self._sarvam_active = False
                    logger.warning(f"Sarvam TTS returned status {res.status_code}: {res.text}")
            except Exception as e:
                logger.warning(f"Sarvam TTS failed, trying edge-tts: {e}")

        # 2. Try Edge-TTS (gu-IN-DhwaniNeural) with 1.5x speed
        try:
            temp_mp3 = cache_path.replace(".wav", ".mp3")
            try:
                import edge_tts
                import asyncio
                communicate = edge_tts.Communicate(text, "gu-IN-DhwaniNeural", rate=self.speed_rate)
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Running in an active async event loop
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            executor.submit(lambda: asyncio.run(communicate.save(temp_mp3))).result()
                    else:
                        loop.run_until_complete(communicate.save(temp_mp3))
                except Exception:
                    asyncio.run(communicate.save(temp_mp3))
            except Exception:
                cmd_edge = [
                    sys.executable, "-m", "edge_tts",
                    "--voice", "gu-IN-DhwaniNeural",
                    f"--rate={self.speed_rate}",
                    "--text", text,
                    "--write-media", temp_mp3
                ]
                subprocess.run(cmd_edge, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if os.path.exists(temp_mp3) and os.path.getsize(temp_mp3) > 100:
                if _convert_to_asterisk_wav(temp_mp3, cache_path):
                    if os.path.exists(temp_mp3):
                        os.remove(temp_mp3)
                    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 500:
                        logger.info(f"Synthesized Gujarati audio via Edge-TTS (1.5x) -> {cache_path}")
                        return cache_path
        except Exception as e:
            logger.warning(f"Edge-TTS failed: {e}")

        # 3. Fallback tone
        self._generate_fallback_wav(cache_path, duration_sec=1.0)
        return cache_path

    def _generate_fallback_wav(self, output_path: str, duration_sec: float = 1.0):
        """Generates a soft audible tone in 8kHz 16-bit PCM mono format."""
        import math
        sample_rate = 8000
        num_samples = int(sample_rate * duration_sec)
        frequency = 440.0
        
        with wave.open(output_path, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            
            raw_frames = bytearray()
            for i in range(num_samples):
                envelope = min(i / 400.0, (num_samples - i) / 400.0, 1.0)
                sample_val = int(envelope * 5000.0 * math.sin(2.0 * math.pi * frequency * (i / sample_rate)))
                raw_frames.extend(sample_val.to_bytes(2, byteorder='little', signed=True))
                
            wav_file.writeframes(raw_frames)
