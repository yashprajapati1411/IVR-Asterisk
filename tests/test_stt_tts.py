"""
Tests for Sarvam STT and Asterisk TTS audio synthesis and format compliance.
"""
import os
import wave
import pytest
from services.stt_service import SarvamSTTService
from services.tts_service import TTSService

TEST_CACHE_DIR = "test_sounds_cache"

@pytest.fixture
def tts_service():
    os.makedirs(TEST_CACHE_DIR, exist_ok=True)
    service = TTSService(api_key="mock_key", cache_dir=TEST_CACHE_DIR)
    yield service
    # Cleanup
    if os.path.exists(TEST_CACHE_DIR):
        for f in os.listdir(TEST_CACHE_DIR):
            try:
                os.remove(os.path.join(TEST_CACHE_DIR, f))
            except Exception:
                pass
        try:
            os.rmdir(TEST_CACHE_DIR)
        except Exception:
            pass

def test_stt_fallback_and_mock():
    stt = SarvamSTTService(api_key="mock_key")
    stt.set_mock_name("ડૉક્ટર દર્શિત")

    # When file doesn't exist
    res = stt.transcribe_audio("nonexistent_file.wav")
    assert res["success"] is True
    assert res["transcript"] == "ડૉક્ટર દર્શિત"

def test_extract_clean_name():
    from services.stt_service import extract_clean_name
    assert extract_clean_name("my name is dev") == "Dev"
    assert extract_clean_name("hello my name is dev solanki") == "Dev Solanki"
    assert extract_clean_name("this is dev") == "Dev"
    assert extract_clean_name("i am dev solanki") == "Dev Solanki"
    assert extract_clean_name("myself dev solanki") == "Dev Solanki"
    assert extract_clean_name("મારું નામ દેવ છે") == "દેવ"
    assert extract_clean_name("મારું નામ દેવ સોલંકી છે") == "દેવ સોલંકી"
    assert extract_clean_name("હું દેવ બોલું છું") == "દેવ"
    assert extract_clean_name("मेरा नाम देव है") == "देव"
    assert extract_clean_name("dev solanki") == "Dev Solanki"

def test_tts_generates_asterisk_compliant_wav(tts_service):
    text = "નમસ્તે, ડૉક્ટર શૈશવ માટે 1 દબાવો"
    wav_path = tts_service.synthesize_gujarati(text)
    
    assert os.path.exists(wav_path)
    assert os.path.getsize(wav_path) > 100

    # Verify Asterisk WAV specifications: 8000Hz, 16-bit (2 bytes), mono (1 channel)
    with wave.open(wav_path, "rb") as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        
        assert channels == 1, f"Expected mono (1 channel), got {channels}"
        assert sampwidth == 2, f"Expected 16-bit (2 bytes), got {sampwidth}"
        assert framerate == 8000, f"Expected 8000 Hz, got {framerate}"

def test_tts_cache_reuse(tts_service):
    text = "ટેસ્ટ પ્રોમ્પ્ટ"
    path1 = tts_service.synthesize_gujarati(text)
    mtime1 = os.path.getmtime(path1)

    path2 = tts_service.synthesize_gujarati(text)
    mtime2 = os.path.getmtime(path2)

    assert path1 == path2
    assert mtime1 == mtime2
