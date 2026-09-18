"""
Text-to-Speech (TTS) Service for Asterisk Gujarati Prompts.
Supports Sarvam TTS (bulbul:v1), Edge-TTS neural voice (gu-IN-DhwaniNeural),
and audio conversion to Asterisk 8kHz mono PCM WAV with 1.5x speed.
"""
import os
import io
import wave
import hashlib
import logging
import base64
import subprocess
import requests
from typing import Optional

logger = logging.getLogger("TTSService")

SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"
CACHE_DIR = os.getenv(
    "ASTERISK_CACHE_DIR",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "sounds", "cache")
)

class TTSService:
    def __init__(self, api_key: Optional[str] = None, cache_dir: str = CACHE_DIR, speed_rate: str = "+45%"):
        self.api_key = api_key or os.getenv("SARVAM_API_KEY", "")
        self.cache_dir = cache_dir
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

        # 1. Try Sarvam TTS if key provided
        if self.api_key and not self.api_key.startswith("mock") and len(self.api_key) > 5:
            try:
                headers = {
                    "api-subscription-key": self.api_key,
                    "Content-Type": "application/json"
                }
                payload = {
                    "inputs": [text],
                    "target_language_code": "gu-IN",
                    "speaker": "meera",
                    "pitch": 0,
                    "pace": 1.4, # 1.4x-1.5x speed
                    "loudness": 1.5,
                    "speech_sample_rate": 8000,
                    "enable_preprocessing": True,
                    "model": "bulbul:v1"
                }
                res = requests.post(SARVAM_TTS_URL, json=payload, headers=headers, timeout=10.0)
                if res.status_code == 200:
                    audios = res.json().get("audios", [])
                    if audios:
                        raw_audio = base64.b64decode(audios[0])
                        with open(cache_path, "wb") as f:
                            f.write(raw_audio)
                        logger.info(f"Synthesized Gujarati audio via Sarvam TTS -> {cache_path}")
                        return cache_path
            except Exception as e:
                logger.warning(f"Sarvam TTS failed, trying edge-tts: {e}")

        # 2. Try Edge-TTS (gu-IN-DhwaniNeural) with 1.5x speed
        try:
            temp_mp3 = cache_path.replace(".wav", ".mp3")
            cmd_edge = [
                "edge-tts",
                "--voice", "gu-IN-DhwaniNeural",
                f"--rate={self.speed_rate}",
                "--text", text,
                "--write-media", temp_mp3
            ]
            subprocess.run(cmd_edge, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Convert to Asterisk 8000Hz 16-bit mono PCM wav using sox
            cmd_sox = ["sox", temp_mp3, "-r", "8000", "-c", "1", "-b", "16", cache_path]
            subprocess.run(cmd_sox, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
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
