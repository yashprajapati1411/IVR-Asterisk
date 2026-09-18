"""
Asterisk IVR Engine for Doctor Appointment Booking in Gujarati.
Implements the full state machine:
Welcome Menu -> Availability Check -> Mobile Number Capture & Validation ->
Name Capture (Sarvam STT) -> Final Confirmation -> DB Transaction -> Booking Success -> Hangup.
"""
import os
import re
import logging
from typing import Optional

from .agi_channel import AGIChannel
from .session import CallSession
from services.db_service import DatabaseService
from services.stt_service import SarvamSTTService
from services.tts_service import TTSService

logger = logging.getLogger("IVREngine")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOUNDS_DIR = os.getenv("ASTERISK_SOUNDS_DIR", os.path.join(PROJECT_ROOT, "sounds"))

class IVREngine:
    def __init__(
        self,
        channel: AGIChannel,
        db_service: Optional[DatabaseService] = None,
        stt_service: Optional[SarvamSTTService] = None,
        tts_service: Optional[TTSService] = None,
        sounds_dir: str = SOUNDS_DIR
    ):
        self.channel = channel
        self.db = db_service or DatabaseService()
        self.stt = stt_service or SarvamSTTService()
        self.tts = tts_service or TTSService()
        self.sounds_dir = sounds_dir
        self.session = CallSession()

    def _sound(self, rel_path: str) -> str:
        """Returns full path without .wav extension for Asterisk AGI."""
        path = os.path.join(self.sounds_dir, rel_path)
        if path.endswith(".wav"):
            path = path[:-4]
        return path

    async def run(self):
        """Main entry point for incoming call."""
        try:
            env = await self.channel.init_session()
            self.session.unique_id = env.get("agi_uniqueid", "test_call")
            self.session.caller_id = env.get("agi_callerid", "")
            
            await self.channel.answer()
            await self.channel.verbose(f"IVR Call Started: CallerID={self.session.caller_id}, ID={self.session.unique_id}", 1)

            while not self.channel.is_hungup:
                if self.session.state == "WELCOME":
                    await self._state_welcome_menu()
                elif self.session.state == "CHECK_AVAILABILITY":
                    await self._state_check_availability()
                elif self.session.state == "MOBILE_CAPTURE":
                    await self._state_mobile_capture()
                elif self.session.state == "NAME_CAPTURE":
                    await self._state_name_capture()
                elif self.session.state == "FINAL_CONFIRMATION":
                    await self._state_final_confirmation()
                elif self.session.state == "BOOKING_TRANSACTION":
                    await self._state_booking_transaction()
                elif self.session.state in ("DONE", "HANGUP"):
                    break
                else:
                    logger.error(f"Unknown state: {self.session.state}")
                    break

        except Exception as e:
            logger.exception(f"Error during IVR execution: {e}")
        finally:
            await self.channel.hangup()
            await self.channel.verbose("IVR Call Finished.", 1)

    # -------------------------------------------------------------------------
    # 1. WELCOME MENU
    # -------------------------------------------------------------------------
    async def _state_welcome_menu(self):
        """
        Gujarati Welcome Menu:
        Press 1 -> Dr. Shaishav
        Press 2 -> Dr. Jaydeep
        Press 3 -> Other Info
        """
        attempts = 0
        max_attempts = 3

        while attempts < max_attempts and not self.channel.is_hungup:
            # Play welcome menu prompt and collect 1 digit (timeout 5000ms)
            digit = await self.channel.get_data(self._sound("gu/welcome_menu"), timeout_ms=5000, max_digits=1)

            if digit == "1":
                # Dr. Shaishav
                self.session.selected_doctor_id = 1
                doc = self.db.get_doctor(1)
                self.session.selected_doctor_name_gu = doc["name_gu"] if doc else "ડૉક્ટર શૈશવ"
                self.session.selected_doctor_name_en = doc["name_en"] if doc else "Dr. Shaishav"
                self.session.state = "CHECK_AVAILABILITY"
                return

            elif digit == "2":
                # Dr. Jaydeep
                self.session.selected_doctor_id = 2
                doc = self.db.get_doctor(2)
                self.session.selected_doctor_name_gu = doc["name_gu"] if doc else "ડૉક્ટર જયદીપ"
                self.session.selected_doctor_name_en = doc["name_en"] if doc else "Dr. Jaydeep"
                self.session.state = "CHECK_AVAILABILITY"
                return

            elif digit == "3":
                # Other information -> Play audio -> Hangup
                await self.channel.stream_file(self._sound("gu/other_info"))
                self.session.state = "HANGUP"
                return

            else:
                attempts += 1
                if attempts < max_attempts:
                    await self.channel.stream_file(self._sound("gu/invalid_option"))

        # Exceeded retries
        await self.channel.stream_file(self._sound("gu/goodbye"))
        self.session.state = "HANGUP"

    # -------------------------------------------------------------------------
    # 2. CHECK TODAY'S AVAILABILITY
    # -------------------------------------------------------------------------
    async def _state_check_availability(self):
        """
        Checks today's availability for selected doctor.
        AVAILABLE: Play slot timing -> Press 1 Booking, Press 2 Main Menu
        NOT AVAILABLE: 'આજે ડોક્ટર માટે કોઈ સ્લોટ ઉપલબ્ધ નથી' -> Press 2 Main Menu
        """
        doctor_id = self.session.selected_doctor_id
        avail = self.db.check_availability(doctor_id)

        if not avail.get("available", False):
            # Not Available
            # Play: "આજે ડોક્ટર માટે કોઈ સ્લોટ ઉપલબ્ધ નથી. મુખ્ય મેનુ માટે 2 દબાવો."
            attempts = 0
            while attempts < 3 and not self.channel.is_hungup:
                digit = await self.channel.get_data(self._sound("gu/no_slots_today"), timeout_ms=5000, max_digits=1)
                if digit == "2":
                    self.session.state = "WELCOME"
                    return
                attempts += 1

            self.session.state = "HANGUP"
            return

        # Available
        slot_time_gu = avail.get("slot_time_gu", "સાંજે 5:00 વાગ્યે")
        self.session.selected_slot_time_gu = slot_time_gu
        self.session.selected_date = avail.get("date", "")

        # Dynamic slot announcement:
        # "ડોક્ટર માટે આજનો સમય <slot_time> છે. બુક કરવા માટે 1 દબાવો. મુખ્ય મેનુ માટે 2 દબાવો."
        slot_text = f"{self.session.selected_doctor_name_gu} માટે આજનો સમય {slot_time_gu} છે. બુક કરવા માટે 1 દબાવો. મુખ્ય મેનુ માટે 2 દબાવો."
        prompt_path = self.tts.synthesize_gujarati(slot_text)

        attempts = 0
        while attempts < 3 and not self.channel.is_hungup:
            digit = await self.channel.get_data(prompt_path, timeout_ms=6000, max_digits=1)
            if digit == "1":
                self.session.state = "MOBILE_CAPTURE"
                return
            elif digit == "2":
                self.session.state = "WELCOME"
                return
            else:
                attempts += 1
                if attempts < 3:
                    await self.channel.stream_file(self._sound("gu/invalid_option"))

        self.session.state = "HANGUP"

    # -------------------------------------------------------------------------
    # 3. MOBILE NUMBER CAPTURE & VALIDATION
    # -------------------------------------------------------------------------
    async def _state_mobile_capture(self):
        """
        Captures 10-digit mobile number, validates, speaks it back,
        and asks user: Press 1 Confirm, Press 2 Re-enter.
        """
        attempts = 0
        max_attempts = 3

        while attempts < max_attempts and not self.channel.is_hungup:
            # Prompt: "તમારો 10 અંકનો મોબાઇલ નંબર દાખલ કરો અને # દબાવો"
            mobile = await self.channel.get_data(self._sound("gu/enter_mobile"), timeout_ms=8000, max_digits=10)

            # Strip any trailing # or whitespace
            if mobile:
                mobile = mobile.replace("#", "").strip()

            # Validate Indian mobile: exactly 10 digits, starts with 6, 7, 8, or 9
            if mobile and re.match(r"^[6-9]\d{9}$", mobile):
                # Valid number -> Speak number & ask confirmation
                confirmed = await self._confirm_mobile_number(mobile)
                if confirmed:
                    self.session.mobile_number = mobile
                    self.session.state = "NAME_CAPTURE"
                    return
                else:
                    # User pressed 2 to re-enter -> loop back in mobile capture
                    attempts += 1
                    continue
            else:
                attempts += 1
                if attempts < max_attempts:
                    # "અમાન્ય મોબાઇલ નંબર. કૃપા કરીને ફરીથી પ્રયાસ કરો."
                    await self.channel.stream_file(self._sound("gu/invalid_mobile"))

        await self.channel.stream_file(self._sound("gu/goodbye"))
        self.session.state = "HANGUP"

    async def _confirm_mobile_number(self, mobile: str) -> bool:
        """
        Speaks: "તમારો મોબાઇલ નંબર ... છે. સાચું હોય તો 1 દબાવો. ફરીથી દાખલ કરવા માટે 2 દબાવો."
        """
        attempts = 0
        prompt_text = f"તમારો મોબાઇલ નંબર {', '.join(mobile)} છે. સાચું હોય તો 1 દબાવો. ફરીથી દાખલ કરવા માટે 2 દબાવો."
        confirm_audio = self.tts.synthesize_gujarati(prompt_text)

        while attempts < 3 and not self.channel.is_hungup:
            digit = await self.channel.get_data(confirm_audio, timeout_ms=5000, max_digits=1)
            if digit == "1":
                return True
            elif digit == "2":
                return False
            attempts += 1

        return False

    # -------------------------------------------------------------------------
    # 4. NAME CAPTURE (VOICE RECORDING + SARVAM STT)
    # -------------------------------------------------------------------------
    async def _state_name_capture(self):
        """
        Prompts: "કૃપા કરીને તમારું નામ જણાવો"
        Records voice stream -> Sarvam STT gu-IN -> Recognized Gujarati Name
        Speaks back: "તમારું નામ ______ છે. સાચું હોય તો 1 દબાવો. ફરીથી કહેવા માટે 2 દબાવો."
        1 -> Name Confirmed
        2 -> Name Capture Retry
        """
        attempts = 0
        max_attempts = 3

        while attempts < max_attempts and not self.channel.is_hungup:
            # Play prompt: "કૃપા કરીને તમારું નામ જણાવો"
            await self.channel.stream_file(self._sound("gu/speak_name"))

            # Temporary record target path
            rec_filename = f"rec_name_{self.session.unique_id}_{attempts}"
            rec_full_path = os.path.join(self.tts.cache_dir, f"{rec_filename}.wav")

            # Asterisk RECORD FILE command
            # record_file(<filename_without_ext>, format="wav", escape_digits="#", timeout_ms=5000, beep=True)
            record_target = os.path.join(self.tts.cache_dir, rec_filename)
            await self.channel.record_file(record_target, format_type="wav", escape_digits="#", timeout_ms=5000, beep=True)

            # Transcribe via STT
            stt_result = self.stt.transcribe_audio(rec_full_path, language_code="gu-IN")
            recognized_name = stt_result.get("transcript", "").strip()

            if not recognized_name:
                attempts += 1
                if attempts < max_attempts:
                    retry_prompt = self.tts.synthesize_gujarati("અવાજ સંભળાયો નથી. કૃપા કરીને બીપ પછી તમારું નામ ફરીથી જણાવો.")
                    await self.channel.stream_file(retry_prompt)
                continue

            # Prompt user to confirm recognized name:
            # "તમારું નામ <name> છે. સાચું હોય તો 1 દબાવો. ફરીથી કહેવા માટે 2 દબાવો."
            confirm_text = f"તમારું નામ {recognized_name} છે. સાચું હોય તો 1 દબાવો. ફરીથી કહેવા માટે 2 દબાવો."
            confirm_audio = self.tts.synthesize_gujarati(confirm_text)

            confirm_digit = await self.channel.get_data(confirm_audio, timeout_ms=5000, max_digits=1)

            if confirm_digit == "1":
                self.session.patient_name_gu = recognized_name
                self.session.state = "FINAL_CONFIRMATION"
                return
            elif confirm_digit == "2":
                # Retry name capture
                attempts += 1
                continue
            else:
                attempts += 1
                if attempts < max_attempts:
                    await self.channel.stream_file(self._sound("gu/invalid_option"))

        self.session.state = "HANGUP"

    # -------------------------------------------------------------------------
    # 5. FINAL CONFIRMATION
    # -------------------------------------------------------------------------
    async def _state_final_confirmation(self):
        """
        "તમારું નામ ______ છે.
         તમારો મોબાઇલ નંબર ______ છે.
         ડોક્ટર ______ માટે આજનો સમય ______ છે.
         બુક કરવા માટે 1 દબાવો.
         મુખ્ય મેનુ માટે 2 દબાવો."
        1 -> Booking (DB Transaction)
        2 -> Main Menu
        """
        prompt_text = (
            f"તમારું નામ {self.session.patient_name_gu} છે. "
            f"તમારો મોબાઇલ નંબર {', '.join(self.session.mobile_number)} છે. "
            f"{self.session.selected_doctor_name_gu} માટે આજનો સમય {self.session.selected_slot_time_gu} છે. "
            f"બુક કરવા માટે 1 દબાવો. મુખ્ય મેનુ માટે 2 દબાવો."
        )
        audio_path = self.tts.synthesize_gujarati(prompt_text)

        attempts = 0
        while attempts < 3 and not self.channel.is_hungup:
            digit = await self.channel.get_data(audio_path, timeout_ms=6000, max_digits=1)
            if digit == "1":
                self.session.state = "BOOKING_TRANSACTION"
                return
            elif digit == "2":
                self.session.state = "WELCOME"
                return
            attempts += 1

        self.session.state = "HANGUP"

    # -------------------------------------------------------------------------
    # 6. DB TRANSACTION & BOOKING SUCCESS
    # -------------------------------------------------------------------------
    async def _state_booking_transaction(self):
        """
        Executes atomic database transaction:
        Lock doctor/date, verify availability, upsert patient, create appointment, generate ID.
        Then announces Booking Success:
        "તમારી એપોઇન્ટમેન્ટ સફળતાપૂર્વક બુક થઈ ગઈ છે.
         તમારું નામ ______ છે.
         તમારો મોબાઇલ નંબર ______ છે.
         તમારો એપોઇન્ટમેન્ટ નંબર ______ છે.
         સમય ______ છે."
        -> HANGUP
        """
        result = self.db.book_appointment(
            doctor_id=self.session.selected_doctor_id,
            mobile_number=self.session.mobile_number,
            patient_name_gu=self.session.patient_name_gu,
            target_date=self.session.selected_date
        )

        if not result.get("success", False):
            # Error / slot full during transaction
            await self.channel.stream_file(self._sound("gu/booking_failed"))
            self.session.state = "WELCOME"
            return

        # Success!
        appt_code = result.get("appointment_code", "")
        self.session.appointment_code = appt_code
        self.session.appointment_id = result.get("appointment_id")

        success_text = (
            f"તમારી એપોઇન્ટમેન્ટ સફળતાપૂર્વક બુક થઈ ગઈ છે. "
            f"તમારું નામ {self.session.patient_name_gu} છે. "
            f"તમારો મોબાઇલ નંબર {', '.join(self.session.mobile_number)} છે. "
            f"તમારો એપોઇન્ટમેન્ટ નંબર {appt_code} છે. "
            f"સમય {self.session.selected_slot_time_gu} છે. "
            f"હોસ્પિટલ તરફથી આભાર."
        )
        success_audio = self.tts.synthesize_gujarati(success_text)

        await self.channel.stream_file(success_audio)
        self.session.state = "DONE"
