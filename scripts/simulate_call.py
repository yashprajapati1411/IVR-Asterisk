"""
Interactive Call Simulator for Asterisk Gujarati Doctor Appointment IVR.
Allows developers and users to test the entire IVR flow interactively from the terminal
without needing an active Asterisk instance or VoIP phone.
"""
import asyncio
import sys
import os
import re

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agi.agi_channel import AGIChannel
from agi.ivr_engine import IVREngine
from services.db_service import DatabaseService
from services.stt_service import SarvamSTTService
from services.tts_service import TTSService

PROMPT_DESCRIPTIONS = {
    "welcome_menu": "નમસ્તે, ડૉક્ટર એપોઇન્ટમેન્ટ સિસ્ટમમાં તમારું સ્વાગત છે.\n[1] Dr. Shaishav | [2] Dr. Jaydeep | [3] Other Info",
    "other_info": "અમારી હોસ્પિટલ સોમવાર થી શનિવાર સવારે 9 થી સાંજે 8 સુધી ખુલ્લી છે. ઇમરજન્સી સેવા 24 કલાક ઉપલબ્ધ છે. (Playing other info & hanging up...)",
    "no_slots_today": "આજે ડૉક્ટર માટે કોઈ સ્લોટ ઉપલબ્ધ નથી. [2] મુખ્ય મેનુ માટે 2 દબાવો.",
    "enter_mobile": "તમારો 10 અંકનો મોબાઇલ નંબર દાખલ કરો અને # દબાવો:",
    "invalid_mobile": "અમાન્ય મોબાઇલ નંબર. કૃપા કરીને 10 અંકનો માન્ય નંબર દાખલ કરો.",
    "speak_name": "કૃપા કરીને તમારું નામ જણાવો (Speak your name after the beep)...",
    "invalid_option": "અમાન્ય વિકલ્પ. કૃપા કરીને ફરીથી પ્રયાસ કરો.",
    "booking_failed": "માફ કરશો, આ સ્લોટ હમણાં જ ભરાઈ ગયો છે.",
    "goodbye": "અમારો સંપર્ક કરવા બદલ આભાર. આવજો."
}

class SimulatedAGIChannel(AGIChannel):
    """Interactive terminal implementation of Asterisk AGI Channel."""

    def __init__(self, interactive: bool = True, preprogrammed_inputs: list = None):
        super().__init__()
        self.interactive = interactive
        self.inputs = list(preprogrammed_inputs or [])
        self.input_index = 0
        self.simulated_env = {
            "agi_callerid": "9876543210",
            "agi_uniqueid": "sim_1710000000"
        }

    async def init_session(self):
        print("\n" + "=" * 60)
        print("📞 [ASTERISK INCOMING CALL CONNECTED]")
        print(f"Caller ID: {self.simulated_env['agi_callerid']}")
        print("=" * 60)
        return self.simulated_env

    async def answer(self):
        print("🔈 [Asterisk] Answered call (Channel State: UP)")
        return True

    async def verbose(self, message: str, level: int = 1):
        print(f"📋 [Asterisk Log] {message}")

    def _get_next_input(self, prompt_text: str = "Enter DTMF: ") -> str:
        if self.interactive:
            try:
                val = input(f"\n👉 {prompt_text} ").strip()
                return val
            except (EOFError, KeyboardInterrupt):
                self.is_hungup = True
                return ""
        else:
            if self.input_index < len(self.inputs):
                val = self.inputs[self.input_index]
                self.input_index += 1
                print(f"\n👉 [Simulated Input]: {val}")
                return str(val)
            return ""

    async def stream_file(self, filename: str, escape_digits: str = ""):
        basename = os.path.basename(filename)
        desc = PROMPT_DESCRIPTIONS.get(basename, f"Playing audio: {basename}")
        print(f"\n🔊 [Audio Stream]: {desc}")
        return None

    async def get_data(self, filename: str, timeout_ms: int = 5000, max_digits: int = 1):
        basename = os.path.basename(filename)
        desc = PROMPT_DESCRIPTIONS.get(basename, f"Audio Prompt: {basename}")
        print(f"\n🔊 [Audio Prompt]: {desc}")
        val = self._get_next_input(f"Enter input (max {max_digits} digits): ")
        return val

    async def record_file(self, filename: str, format_type: str = "wav", escape_digits: str = "#", timeout_ms: int = 5000, beep: bool = True, silence_sec: int = 2):
        print("\n🔴 [RECORDING AUDIO]: *BEEP* (Speak patient name...)")
        if self.interactive:
            name_spoken = input("👉 [Microphone/STT] Say or type patient name in Gujarati or English: ").strip()
            if not name_spoken:
                name_spoken = "ભાવેશભાઈ પટેલ"
        else:
            name_spoken = self._get_next_input("Simulate Spoken Name: ") or "ભાવેશભાઈ પટેલ"

        # Update Sarvam STT mock for this test
        self.last_spoken_name = name_spoken
        return True

    async def hangup(self):
        print("\n📴 [Asterisk] Call Hung Up (Channel State: DOWN)")
        print("=" * 60 + "\n")
        self.is_hungup = True

async def run_simulation(inputs=None, interactive=True):
    db = DatabaseService()
    db.seed_initial_data()
    stt = SarvamSTTService()
    tts = TTSService()

    channel = SimulatedAGIChannel(interactive=interactive, preprogrammed_inputs=inputs)
    
    # Hook STT mock to channel record input
    orig_transcribe = stt.transcribe_audio
    def custom_transcribe(path, language_code="gu-IN"):
        if hasattr(channel, "last_spoken_name") and channel.last_spoken_name:
            return {"success": True, "transcript": channel.last_spoken_name, "source": "simulated"}
        return orig_transcribe(path, language_code)
    stt.transcribe_audio = custom_transcribe

    engine = IVREngine(channel=channel, db_service=db, stt_service=stt, tts_service=tts)
    await engine.run()
    return engine.session

def main():
    print("Welcome to Asterisk Gujarati Doctor Appointment IVR Simulator!")
    print("This simulator lets you test the complete flow interactively.\n")
    asyncio.run(run_simulation(interactive=True))

if __name__ == "__main__":
    main()
