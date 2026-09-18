"""
Prompt Generator Utility for Asterisk Gujarati IVR.
Generates all required static Gujarati audio prompt WAV files (8000Hz 16-bit Mono PCM).
Uses Sarvam TTS if configured, or Edge-TTS neural voice (gu-IN-DhwaniNeural).
"""
import os
import sys
import wave
import math
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.tts_service import TTSService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PromptGenerator")

PROMPTS = {
    "welcome_menu": (
        "નમસ્તે, ડૉક્ટર એપોઇન્ટમેન્ટ સિસ્ટમમાં તમારું સ્વાગત છે. "
        "ડૉક્ટર શૈશવ માટે 1 દબાવો. "
        "ડૉક્ટર જયદીપ માટે 2 દબાવો. "
        "અન્ય માહિતી માટે 3 દબાવો."
    ),
    "other_info": (
        "અમારી હોસ્પિટલ સોમવાર થી શનિવાર સવારે 9 થી સાંજે 8 સુધી ખુલ્લી છે. "
        "ઇમરજન્સી સેવા 24 કલાક ઉપલબ્ધ છે. "
        "વધુ માહિતી માટે રિસેપ્શન પર સંપર્ક કરો. આભાર."
    ),
    "no_slots_today": (
        "આજે ડૉક્ટર માટે કોઈ સ્લોટ ઉપલબ્ધ નથી. મુખ્ય મેનુ માટે 2 દબાવો."
    ),
    "enter_mobile": (
        "તમારો 10 અંકનો મોબાઇલ નંબર દાખલ કરો અને હેશ દબાવો."
    ),
    "invalid_mobile": (
        "અમાન્ય મોબાઇલ નંબર. કૃપા કરીને 10 અંકનો માન્ય મોબાઇલ નંબર દાખલ કરો."
    ),
    "speak_name": (
        "કૃપા કરીને બીપ પછી તમારું નામ જણાવો."
    ),
    "invalid_option": (
        "અમાન્ય વિકલ્પ. કૃપા કરીને ફરીથી પ્રયાસ કરો."
    ),
    "booking_failed": (
        "માફ કરશો, આ સ્લોટ હમણાં જ ભરાઈ ગયો છે. કૃપા કરીને ફરીથી પ્રયાસ કરો."
    ),
    "goodbye": (
        "અમારો સંપર્ક કરવા બદલ આભાર. આવજો."
    )
}

def generate_beep_wav(file_path: str, duration_sec: float = 0.3, freq: float = 880.0):
    """Generates standard Asterisk-compatible beep tone."""
    sample_rate = 8000
    num_samples = int(sample_rate * duration_sec)
    
    with wave.open(file_path, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        
        frames = bytearray()
        for i in range(num_samples):
            envelope = min(i / 400.0, (num_samples - i) / 400.0, 1.0)
            sample_val = int(envelope * 8000.0 * math.sin(2.0 * math.pi * freq * (i / sample_rate)))
            frames.extend(sample_val.to_bytes(2, byteorder='little', signed=True))
        wav.writeframes(frames)

def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target_dir = os.path.join(root, "sounds", "gu")
    os.makedirs(target_dir, exist_ok=True)
    
    tts = TTSService(cache_dir=target_dir, speed_rate="+45%")
    
    logger.info(f"Generating Gujarati voice prompts (1.5x speed) into: {target_dir}")

    for name, text in PROMPTS.items():
        out_wav = os.path.join(target_dir, f"{name}.wav")
        # Remove old wav so it is forced to regenerate
        if os.path.exists(out_wav):
            os.remove(out_wav)
        logger.info(f"Generating prompt '{name}': {text[:40]}...")
        gen_path = tts.synthesize_gujarati(text)
        if gen_path != out_wav and os.path.exists(gen_path):
            with open(gen_path, "rb") as src, open(out_wav, "wb") as dst:
                dst.write(src.read())
        logger.info(f"Successfully generated -> {out_wav} ({os.path.getsize(out_wav)} bytes)")

    beep_wav = os.path.join(target_dir, "beep.wav")
    generate_beep_wav(beep_wav)
    logger.info(f"Generated beep audio -> {beep_wav}")

    print("\nAll Gujarati prompts generated with real voice!")

if __name__ == "__main__":
    main()
