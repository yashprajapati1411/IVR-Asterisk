"""
Prompt Generator Utility for Asterisk Gujarati IVR.
Generates all required static Gujarati audio prompt WAV files (8000Hz 16-bit Mono PCM).
Converts existing voice recordings from IVR-system/voice_recordign when available,
and synthesizes remaining prompts with Sarvam TTS (bulbul:v3) or Edge-TTS.
"""
import os
import sys
import wave
import math
import logging
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.tts_service import TTSService, _convert_to_asterisk_wav

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PromptGenerator")

PROMPTS = {
    "welcome_menu": (
        "ત્રિનય ઓર્થોપેડિક હોસ્પિટલમાં આપનું સ્વાગત છે. "
        "ડૉક્ટર શૈશવ સોની માટે 1 દબાવો, "
        "ડૉક્ટર જયદીપ પટેલ માટે 2 દબાવો, "
        "અન્ય જાણકારી માટે 3 દબાવો, "
        "રિસેપ્શનિસ્ટ સાથે વાત કરવા માટે 0 દબાવો."
    ),
    "connecting_receptionist": (
        "કૃપા કરીને રાહ જુઓ, તમારો કોલ હોસ્પિટલ રિસેપ્શનિસ્ટ સાથે જોડવામાં આવી રહ્યો છે."
    ),
    "other_info": (
        "ફીસની માહિતી. નવા કેસનો ચાર્જ છસો રૂપિયા છે. જૂના કેસના ત્રણસો રૂપિયા છે. "
        "જૂનો કેસ બે મહિના માટે જ માન્ય ગણાશે. એના ઉપરાંત નવો કેસ કઢાવવો પડશે. "
        "જોઈન્ટના દુખાવા માટે ડૉક્ટર શૈશવ સોનીની સલાહ લો. કરોડરજ્જુના દુખાવા માટે ડૉક્ટર જયદીપ પટેલની સલાહ લો. "
        "વધુ માહિતી માટે હોસ્પિટલની મુલાકાત લો. "
        "મુખ્ય મેનુ માટે 1 દબાવો."
    ),
    "avail_shaishav": (
        "ડૉક્ટર શૈશવ સોની માટે 1 કલાકના સ્લોટ ઉપલબ્ધ છે. એપોઇન્ટમેન્ટ બુક કરવા માટે સ્લોટ પસંદ કરો."
    ),
    "avail_jaydeep": (
        "ડૉક્ટર જયદીપ પટેલ માટે 1 કલાકના સ્લોટ ઉપલબ્ધ છે. એપોઇન્ટમેન્ટ બુક કરવા માટે સ્લોટ પસંદ કરો."
    ),
    "your_mobile_is": (
        "તમારો મોબાઇલ નંબર છે"
    ),
    "confirm_mobile_options": (
        "સાચું હોય તો 1 દબાવો. ફરીથી દાખલ કરવા માટે 2 દબાવો."
    ),
    "your_name_is": (
        "તમારું નામ છે"
    ),
    "confirm_name_options": (
        "સાચું હોય તો 1 દબાવો. ફરીથી કહેવા માટે 2 દબાવો."
    ),
    "booking_success_header": (
        "તમારી એપોઇન્ટમેન્ટ સફળતાપૂર્વક બુક થઈ ગઈ છે."
    ),
    "appt_number_is": (
        "તમારો એપોઇન્ટમેન્ટ નંબર છે"
    ),
    "thank_you_toph": (
        "ત્રિનય ઓર્થોપેડિક હોસ્પિટલ તરફથી આભાર."
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
        "કૃપા કરીને તમારું નામ જણાવો."
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

# Mapping to external recorded clips if available
EXTERNAL_AUDIO_SOURCES = {
    "other_info": "other_information.mp3",
    "enter_mobile": "collect_phone.mp3",
    "invalid_mobile": "invalid_phone.mp3",
    "no_slots_today": "no_slots.mp3",
    "goodbye": "hangup.mp3"
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
    
    # Check if external recordings exist in IVR-system
    external_dir = os.path.abspath(os.path.join(root, "..", "IVR-system", "voice_recordign", "tts"))
    
    tts = TTSService(cache_dir=target_dir, speed_rate="+45%")
    logger.info(f"Generating Gujarati voice prompts into: {target_dir}")

    for name, text in PROMPTS.items():
        out_wav = os.path.join(target_dir, f"{name}.wav")
        if os.path.exists(out_wav):
            os.remove(out_wav)

        # For specific files like other_info, prefer existing recording if present
        ext_filename = EXTERNAL_AUDIO_SOURCES.get(name)
        converted = False
        if ext_filename and os.path.exists(os.path.join(external_dir, ext_filename)) and name == "other_info":
            ext_path = os.path.join(external_dir, ext_filename)
            logger.info(f"Converting recorded audio from {ext_path} -> {out_wav}...")
            converted = _convert_to_asterisk_wav(ext_path, out_wav)

        if not converted:
            logger.info(f"Synthesizing prompt '{name}' with TTS: {text[:45]}...")
            gen_path = tts.synthesize_gujarati(text)
            if gen_path != out_wav and os.path.exists(gen_path):
                with open(gen_path, "rb") as src, open(out_wav, "wb") as dst:
                    dst.write(src.read())

        if os.path.exists(out_wav):
            logger.info(f"Successfully created -> {out_wav} ({os.path.getsize(out_wav)} bytes)")

    beep_wav = os.path.join(target_dir, "beep.wav")
    generate_beep_wav(beep_wav)
    logger.info(f"Generated beep audio -> {beep_wav}")

    # Generate individual Gujarati digits 0-9
    digits_dir = os.path.join(target_dir, "digits")
    os.makedirs(digits_dir, exist_ok=True)
    DIGITS_MAP = {
        "0": "ઝીરો",
        "1": "એક",
        "2": "બે",
        "3": "ત્રણ",
        "4": "ચાર",
        "5": "પાંચ",
        "6": "છ",
        "7": "સાત",
        "8": "આઠ",
        "9": "નવ"
    }
    for digit, gu_word in DIGITS_MAP.items():
        digit_wav = os.path.join(digits_dir, f"{digit}.wav")
        gen_path = tts.synthesize_gujarati(gu_word)
        if os.path.exists(gen_path):
            with open(gen_path, "rb") as src, open(digit_wav, "wb") as dst:
                dst.write(src.read())
            logger.info(f"Generated digit '{digit}' ({gu_word}) -> {digit_wav}")

    print("\nAll Gujarati prompts and digits generated successfully!")

if __name__ == "__main__":
    main()
