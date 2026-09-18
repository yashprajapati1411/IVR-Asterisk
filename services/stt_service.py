"""
Speech-to-Text (STT) Client for Gujarati (gu-IN) patient name recognition.
Prioritizes Sarvam STT API if SARVAM_API_KEY is configured.
Falls back to Google Speech Recognition (SpeechRecognition) for live accurate transcription
in Gujarati (gu-IN) and Indian English (en-IN).
Includes intelligent name extraction to extract only the name when users speak full phrases
like "my name is dev", "મારું નામ દેવ છે", "this is dev solanki", etc.
"""
import os
import re
import logging
import requests
from typing import Optional, Dict, Any

logger = logging.getLogger("STTService")

SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"

def extract_clean_name(text: str) -> str:
    """
    Extracts only the person's name from conversational phrases in English, Gujarati, and Hindi.
    E.g.:
      "my name is dev" -> "Dev"
      "hello my name is dev solanki" -> "Dev Solanki"
      "this is dev" -> "Dev"
      "i am dev solanki" -> "Dev Solanki"
      "મારું નામ દેવ છે" -> "દેવ"
      "મારું નામ દેવ સોલંકી છે" -> "દેવ સોલંકી"
      "હું દેવ બોલું છું" -> "દેવ"
      "मेरा नाम देव है" -> "देव"
    """
    if not text:
        return ""
    t = text.strip()
    
    # Common conversational patterns
    patterns = [
        # English patterns
        r'^(?:hello|hi|hey)?\s*(?:my\s+name\s+is|this\s+is|i\s+am|i\'m|myself|name\s+is)\s+(.+?)(?:\s+(?:here|speaking|please))?$',
        # Gujarati patterns
        r'^(?:નમસ્તે|હેલો)?\s*(?:મારું\s+નામ|મારૂ\s+નામ)\s+(.+?)(?:\s+છે|\s+જી)?$',
        r'^(?:હું|હૂં)\s+(.+?)(?:\s+બોલું\s+છું|\s+છું)?$',
        # Hindi patterns
        r'^(?:नमस्ते|हेलो)?\s*(?:मेरा\s+नाम)\s+(.+?)(?:\s+है|\s+જી)?$',
        r'^(?:मैं)\s+(.+?)(?:\s+बोल\s+रहा\s+हूँ|\s+बोल\s+રહી\s+हूँ|\s+हूँ)?$'
    ]
    
    for p in patterns:
        m = re.search(p, t, re.IGNORECASE)
        if m:
            t = m.group(1).strip()
            break
            
    # Strip any trailing punctuation and filler words
    t = re.sub(r'[\.,!?]', '', t)
    t = re.sub(r'\s+(?:here|speaking|please|sir|ji|hai|che)$', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s+(?:છે|જી|સાહેબ|છું)$', '', t)
    t = t.strip()
    
    # Capitalize English words if ASCII
    words = t.split()
    if words and all(w.isascii() for w in words):
        t = ' '.join(w.capitalize() for w in words)
        
    return t

class SarvamSTTService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SARVAM_API_KEY", "")
        self.mock_name: Optional[str] = None

    def set_mock_name(self, name: str):
        """Allow unit tests to inject a mock name if explicitly desired."""
        self.mock_name = name

    def transcribe_audio(self, audio_filepath: str, language_code: str = "gu-IN") -> Dict[str, Any]:
        """
        Transcribes Asterisk recorded audio file to text and extracts the clean name.
        """
        # Unit test override
        if self.mock_name:
            return {
                "success": True,
                "transcript": extract_clean_name(self.mock_name),
                "source": "test_mock"
            }

        if not os.path.exists(audio_filepath) or os.path.getsize(audio_filepath) < 500:
            logger.warning(f"Audio file missing or empty: {audio_filepath}")
            return {
                "success": False,
                "transcript": "",
                "source": "none",
                "error": "Audio file not found or empty"
            }

        raw_transcript = ""
        source = "none"

        # 1. Try Sarvam STT if API key is provided
        if self.api_key and not self.api_key.startswith("mock") and len(self.api_key) > 5:
            try:
                with open(audio_filepath, "rb") as f:
                    files = {"file": (os.path.basename(audio_filepath), f, "audio/wav")}
                    data = {"model": "saarika:v2", "language_code": language_code}
                    headers = {"api-subscription-key": self.api_key}
                    response = requests.post(SARVAM_STT_URL, files=files, data=data, headers=headers, timeout=10.0)
                    
                if response.status_code == 200:
                    res_json = response.json()
                    raw_transcript = res_json.get("transcript", "").strip()
                    if raw_transcript:
                        source = "sarvam"
            except Exception as e:
                logger.warning(f"Sarvam STT request failed: {e}")

        # 2. Free live Speech Recognition (SpeechRecognition with Google STT)
        if not raw_transcript:
            try:
                import speech_recognition as sr
                r = sr.Recognizer()
                with sr.AudioFile(audio_filepath) as src:
                    audio = r.record(src)
                
                # First try Gujarati
                try:
                    text_gu = r.recognize_google(audio, language="gu-IN").strip()
                    if text_gu:
                        raw_transcript = text_gu
                        source = "google_gu"
                except (sr.UnknownValueError, Exception) as e_gu:
                    logger.debug(f"gu-IN recognition didn't match, trying en-IN: {e_gu}")

                # Fallback to Indian English
                if not raw_transcript:
                    try:
                        text_en = r.recognize_google(audio, language="en-IN").strip()
                        if text_en:
                            raw_transcript = text_en
                            source = "google_en"
                    except (sr.UnknownValueError, Exception) as e_en:
                        logger.warning(f"Speech recognition could not understand audio: {e_en}")

            except Exception as e:
                logger.error(f"SpeechRecognition library error: {e}")

        if raw_transcript:
            clean_name = extract_clean_name(raw_transcript)
            logger.info(f"Raw speech: '{raw_transcript}' -> Extracted clean name: '{clean_name}' (source: {source})")
            return {
                "success": bool(clean_name),
                "transcript": clean_name or raw_transcript,
                "raw_transcript": raw_transcript,
                "source": source
            }

        return {
            "success": False,
            "transcript": "",
            "source": "none",
            "error": "No speech detected"
        }
