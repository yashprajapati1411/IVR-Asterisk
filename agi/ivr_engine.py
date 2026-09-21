"""
Asterisk IVR Engine for Doctor Appointment Booking in Gujarati.
Implements the full state machine:
Welcome Menu -> Availability Check -> Mobile Number Capture & Validation ->
Name Capture (Sarvam STT) -> Final Confirmation -> DB Transaction -> Booking Success -> Hangup.
"""
import os
import re
import wave
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

    def _sound(self, rel_or_abs_path: str) -> str:
        """Returns Asterisk-compatible path without .wav extension, using forward slashes."""
        path = rel_or_abs_path
        if path.endswith(".wav"):
            path = path[:-4]
        filename = os.path.basename(path)
        if "cache" in path:
            return f"{self.sounds_dir}/cache/{filename}".replace("\\", "/")
        elif "digits" in path:
            return f"{self.sounds_dir}/gu/digits/{filename}".replace("\\", "/")
        elif "gu" in path:
            return f"{self.sounds_dir}/gu/{filename}".replace("\\", "/")
        full = os.path.join(self.sounds_dir, path)
        return full.replace("\\", "/")

    def _get_or_create_mobile_confirmation_audio(self, mobile: str) -> str:
        """
        Dynamically stitches 'gu/your_mobile_is.wav' + trimmed digits + 'gu/confirm_mobile_options.wav'
        into a single continuous audio file in cache.
        This eliminates 10 separate AGI commands and 15 seconds of dead silence!
        """
        clean_num = re.sub(r"\D", "", mobile)
        cache_filename = f"conf_mobile_{clean_num}.wav"
        full_cache_path = os.path.join(self.tts.cache_dir, cache_filename)

        if not os.path.exists(full_cache_path) or os.path.getsize(full_cache_path) < 1000:
            your_mobile_wav = os.path.join(self.sounds_dir, "gu", "your_mobile_is.wav")
            confirm_opts_wav = os.path.join(self.sounds_dir, "gu", "confirm_mobile_options.wav")
            frames = []
            params = None

            if os.path.exists(your_mobile_wav):
                with wave.open(your_mobile_wav, "rb") as w:
                    params = w.getparams()
                    frames.append(w.readframes(w.getnframes()))
                    frames.append(b"\x00" * int(8000 * 2 * 0.15))  # 150ms pause

            for d in clean_num:
                d_wav = os.path.join(self.sounds_dir, "gu", "digits", f"{d}.wav")
                if os.path.exists(d_wav):
                    with wave.open(d_wav, "rb") as w:
                        if not params:
                            params = w.getparams()
                        frames.append(w.readframes(w.getnframes()))
                        frames.append(b"\x00" * int(8000 * 2 * 0.08))  # 80ms pause

            if os.path.exists(confirm_opts_wav):
                with wave.open(confirm_opts_wav, "rb") as w:
                    frames.append(b"\x00" * int(8000 * 2 * 0.20))  # 200ms pause
                    frames.append(w.readframes(w.getnframes()))

            if frames and params:
                os.makedirs(os.path.dirname(full_cache_path), exist_ok=True)
                with wave.open(full_cache_path, "wb") as out:
                    out.setparams(params)
                    out.writeframes(b"".join(frames))
                logger.info(f"Generated stitched mobile confirmation audio: {full_cache_path}")

        return f"{self.sounds_dir}/cache/conf_mobile_{clean_num}".replace("\\", "/")

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
                elif self.session.state == "OTHER_INFO":
                    await self._state_other_info()
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
            digit = await self.channel.get_data(self._sound("gu/welcome_menu"), timeout_ms=5000, max_digits=1)

            if digit == "1":
                self.session.selected_doctor_id = 1
                doc = self.db.get_doctor(1)
                self.session.selected_doctor_name_gu = doc["name_gu"] if doc else "ડૉક્ટર શૈશવ સોની"
                self.session.selected_doctor_name_en = doc["name_en"] if doc else "Dr. Shaishav Soni"
                self.session.state = "CHECK_AVAILABILITY"
                return

            elif digit == "2":
                self.session.selected_doctor_id = 2
                doc = self.db.get_doctor(2)
                self.session.selected_doctor_name_gu = doc["name_gu"] if doc else "ડૉક્ટર જયદીપ પટેલ"
                self.session.selected_doctor_name_en = doc["name_en"] if doc else "Dr. Jaydeep Patel"
                self.session.state = "CHECK_AVAILABILITY"
                return

            elif digit == "3":
                self.session.state = "OTHER_INFO"
                return

            else:
                attempts += 1
                if digit is not None and attempts < max_attempts:
                    await self.channel.stream_file(self._sound("gu/invalid_option"))

        await self.channel.stream_file(self._sound("gu/goodbye"))
        self.session.state = "HANGUP"

    # -------------------------------------------------------------------------
    # 2. OTHER INFORMATION / FEES / SERVICES
    # -------------------------------------------------------------------------
    async def _state_other_info(self):
        """
        Plays Hospital Info / Consultation Fees:
        "ફીસની માહિતી... મુખ્ય મેનુ માટે 1 દબાવો."
        Waits 20 seconds for user input.
        If user enters 1 (or any key) -> Return to Main Menu (WELCOME).
        If 20s timeout occurs with no input -> Goodbye & Hangup.
        """
        digit = await self.channel.get_data(
            self._sound("gu/other_info"),
            timeout_ms=20000,
            max_digits=1
        )
        logger.info(f"Other Info input received: '{digit}'")

        if digit is not None and digit != "":
            # User pressed 1 or any key -> return to main menu
            self.session.state = "WELCOME"
            return

        # 20 seconds timeout with no key pressed -> goodbye and hangup
        await self.channel.stream_file(self._sound("gu/goodbye"))
        self.session.state = "HANGUP"

    # -------------------------------------------------------------------------
    # 3. CHECK TODAY'S HOURLY SLOT AVAILABILITY
    # -------------------------------------------------------------------------
    async def _state_check_availability(self):
        """
        Checks today's hourly slot availability for selected doctor.
        Presents available hourly slots (max 8 per slot) to the caller.
        """
        doctor_id = self.session.selected_doctor_id
        avail = self.db.check_availability(doctor_id)

        if not avail.get("available", False):
            attempts = 0
            while attempts < 3 and not self.channel.is_hungup:
                digit = await self.channel.get_data(self._sound("gu/no_slots_today"), timeout_ms=6000, max_digits=1)
                if digit == "2":
                    self.session.state = "WELCOME"
                    return
                attempts += 1

            self.session.state = "WELCOME"
            return

        slots = avail.get("slots", [])
        if not slots:
            await self.channel.stream_file(self._sound("gu/no_slots_today"))
            self.session.state = "WELCOME"
            return

        self.session.selected_date = avail.get("date", "")

        # Build prompt listing available slots
        # E.g.: "ડૉક્ટર શૈશવ સોની માટે ઉપલબ્ધ સ્લોટ: સાંજે 5:00 થી 6:00 માટે 1 દબાવો..."
        prompt_parts = [f"{self.session.selected_doctor_name_gu} માટે ઉપલબ્ધ સ્લોટ: "]
        slot_mapping = {}

        for idx, s in enumerate(slots, start=1):
            if idx > 9:
                break
            slot_mapping[str(idx)] = s["slot_time_gu"]
            prompt_parts.append(f"{s['slot_time_gu']} માટે {idx} દબાવો. ")

        prompt_parts.append("મુખ્ય મેનુ માટે 9 દબાવો.")
        prompt_text = "".join(prompt_parts)
        prompt_path = self._sound(self.tts.synthesize_gujarati(prompt_text))

        attempts = 0
        while attempts < 3 and not self.channel.is_hungup:
            digit = await self.channel.get_data(prompt_path, timeout_ms=8000, max_digits=1)
            if digit in slot_mapping:
                self.session.selected_slot_time_gu = slot_mapping[digit]
                self.session.state = "MOBILE_CAPTURE"
                return
            elif digit in ("9", "2"):
                self.session.state = "WELCOME"
                return
            elif digit in ("#", "", None):
                attempts += 1
                continue
            else:
                attempts += 1
                if attempts < 3:
                    await self.channel.stream_file(self._sound("gu/invalid_option"))

        # Default: pick first available slot if user stayed on line
        self.session.selected_slot_time_gu = slots[0]["slot_time_gu"]
        self.session.state = "MOBILE_CAPTURE"

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
            # Collect up to 11 digits (to swallow optional trailing #)
            mobile = await self.channel.get_data(self._sound("gu/enter_mobile"), timeout_ms=15000, max_digits=11)

            if mobile:
                mobile = mobile.replace("#", "").strip()

            if mobile and re.match(r"^[6-9]\d{9}$", mobile):
                confirmed = await self._confirm_mobile_number(mobile)
                if confirmed:
                    self.session.mobile_number = mobile
                    self.session.state = "NAME_CAPTURE"
                    return
                else:
                    attempts += 1
                    continue
            else:
                attempts += 1
                if attempts < max_attempts:
                    await self.channel.stream_file(self._sound("gu/invalid_mobile"))

        await self.channel.stream_file(self._sound("gu/goodbye"))
        self.session.state = "HANGUP"

    async def _confirm_mobile_number(self, mobile: str) -> bool:
        """
        Speaks: "તમારો મોબાઇલ નંબર ... છે. સાચું હોય તો 1 દબાવો. ફરીથી દાખલ કરવા માટે 2 દબાવો."
        Plays a single continuous audio prompt with instant barge-in.
        """
        prompt_path = self._get_or_create_mobile_confirmation_audio(mobile)
        attempts = 0

        while attempts < 3 and not self.channel.is_hungup:
            digit = await self.channel.get_data(prompt_path, timeout_ms=8000, max_digits=1)
            logger.info(f"Mobile confirmation digit received: '{digit}' (attempt {attempts+1})")

            if digit == "1":
                return True
            elif digit == "2":
                return False
            elif digit == "#":
                digit = await self.channel.get_data(self._sound("gu/beep"), timeout_ms=4000, max_digits=1)
                if digit == "1":
                    return True
                elif digit == "2":
                    return False

            attempts += 1
            if digit is not None and digit not in ("1", "2", "#"):
                if attempts < 3:
                    await self.channel.stream_file(self._sound("gu/invalid_option"))

        # Fallback: User stayed on line through 3 attempts -> proceed to name capture
        return True

    # -------------------------------------------------------------------------
    # 4. NAME CAPTURE (VOICE RECORDING + SARVAM STT)
    # -------------------------------------------------------------------------
    async def _state_name_capture(self):
        """
        Prompts: "કૃપા કરીને તમારું નામ જણાવો"
        Records voice stream -> Sarvam STT gu-IN -> Recognized Gujarati Name
        Speaks back: "તમારું નામ ______ છે. સાચું હોય તો 1 દબાવો. ફરીથી કહેવા માટે 2 દબાવો."
        1 -> Name Confirmed -> FINAL_CONFIRMATION
        2 -> Name Capture Retry
        """
        attempts = 0
        max_attempts = 3
        recognized_name = ""

        while attempts < max_attempts and not self.channel.is_hungup:
            await self.channel.stream_file(self._sound("gu/speak_name"))

            rec_filename = f"rec_name_{self.session.unique_id}_{attempts}"
            rec_full_path = os.path.join(self.tts.cache_dir, f"{rec_filename}.wav")
            record_target = f"{self.sounds_dir}/cache/{rec_filename}".replace("\\", "/")

            await self.channel.record_file(record_target, format_type="wav", escape_digits="#", timeout_ms=6000, beep=True, silence_sec=2)

            stt_result = self.stt.transcribe_audio(rec_full_path, language_code="gu-IN")
            recognized_name = stt_result.get("transcript", "").strip()

            if not recognized_name:
                attempts += 1
                if attempts < max_attempts:
                    retry_prompt = self._sound(self.tts.synthesize_gujarati("અવાજ સંભળાયો નથી. કૃપા કરીને બીપ પછી તમારું નામ ફરીથી જણાવો."))
                    await self.channel.stream_file(retry_prompt)
                else:
                    recognized_name = "દર્દી"
                if not recognized_name or recognized_name == "દર્દી":
                    if attempts >= max_attempts:
                        break
                    continue

            confirm_text = f"તમારું નામ {recognized_name} છે. સાચું હોય તો 1 દબાવો. ફરીથી કહેવા માટે 2 દબાવો."
            confirm_audio = self._sound(self.tts.synthesize_gujarati(confirm_text))

            confirm_digit = await self.channel.get_data(confirm_audio, timeout_ms=8000, max_digits=1)
            if confirm_digit == "#":
                confirm_digit = await self.channel.get_data(self._sound("gu/beep"), timeout_ms=5000, max_digits=1)

            if confirm_digit == "1" or confirm_digit in ("#", "", None) or (attempts >= max_attempts - 1 and recognized_name):
                self.session.patient_name_gu = recognized_name
                self.session.state = "FINAL_CONFIRMATION"
                return
            elif confirm_digit == "2":
                attempts += 1
                continue
            else:
                attempts += 1
                if attempts < max_attempts:
                    await self.channel.stream_file(self._sound("gu/invalid_option"))

        self.session.patient_name_gu = recognized_name or "દર્દી"
        self.session.state = "FINAL_CONFIRMATION"

    # -------------------------------------------------------------------------
    # 6. STREAMLINED FINAL CONFIRMATION
    # -------------------------------------------------------------------------
    async def _state_final_confirmation(self):
        """
        Directly asks: "એપોઇન્ટમેન્ટ બુક કરવા માટે 1 દબાવો. મુખ્ય મેનુ માટે 2 દબાવો."
        1 -> Booking (DB Transaction)
        2 -> Main Menu
        """
        prompt_text = "એપોઇન્ટમેન્ટ બુક કરવા માટે 1 દબાવો. મુખ્ય મેનુ માટે 2 દબાવો."
        audio_path = self._sound(self.tts.synthesize_gujarati(prompt_text))

        attempts = 0
        while attempts < 3 and not self.channel.is_hungup:
            digit = await self.channel.get_data(audio_path, timeout_ms=8000, max_digits=1)
            if digit == "#":
                digit = await self.channel.get_data(self._sound("gu/beep"), timeout_ms=5000, max_digits=1)

            if digit == "1" or (attempts >= 2):
                self.session.state = "BOOKING_TRANSACTION"
                return
            elif digit == "2":
                self.session.state = "WELCOME"
                return
            elif digit in ("#", "", None):
                attempts += 1
                continue
            else:
                attempts += 1
                if attempts < 3:
                    await self.channel.stream_file(self._sound("gu/invalid_option"))

        self.session.state = "BOOKING_TRANSACTION"

    # -------------------------------------------------------------------------
    # 7. DB TRANSACTION & BOOKING SUCCESS ANNOUNCEMENT
    # -------------------------------------------------------------------------
    async def _state_booking_transaction(self):
        """
        Executes atomic database transaction:
        Locks doctor/slot/date with BEGIN IMMEDIATE, checks max 8 slots per hour, creates appointment.
        Then announces Booking Success details:
        "તમારી એપોઇન્ટમેન્ટ સફળતાપૂર્વક બુક થઈ ગઈ છે.
         તમારું નામ ______ છે.
         તમારો મોબાઇલ નંબર ______ છે.
         તમારો એપોઇન્ટમેન્ટ નંબર ______ છે.
         તમારો સમય ______ છે.
         ______ માટે ત્રિનય ઓર્થોપેડિક હોસ્પિટલ તરફથી આભાર."
        -> HANGUP
        """
        result = self.db.book_appointment(
            doctor_id=self.session.selected_doctor_id,
            mobile_number=self.session.mobile_number,
            patient_name_gu=self.session.patient_name_gu,
            target_date=self.session.selected_date,
            slot_time_gu=self.session.selected_slot_time_gu
        )

        if not result.get("success", False):
            # Error / slot full during transaction
            await self.channel.stream_file(self._sound("gu/booking_failed"))
            self.session.state = "WELCOME"
            return

        # Success!
        appt_code = result.get("appointment_code", "")
        appt_id = result.get("appointment_id")
        self.session.appointment_code = appt_code
        self.session.appointment_id = appt_id
        if result.get("slot_time_gu"):
            self.session.selected_slot_time_gu = result.get("slot_time_gu")

        # Use the database row number as the spoken appointment number
        spoken_appt_num = str(appt_id) if appt_id is not None else (appt_code.replace("APT-", "") if "APT-" in appt_code else appt_code)

        success_text = (
            f"તમારી એપોઇન્ટમેન્ટ સફળતાપૂર્વક બુક થઈ ગઈ છે. "
            f"તમારું નામ {self.session.patient_name_gu} છે. "
            f"તમારો મોબાઇલ નંબર {' '.join(self.session.mobile_number)} છે. "
            f"તમારો એપોઇન્ટમેન્ટ નંબર {spoken_appt_num} છે. "
            f"તમારો સમય {self.session.selected_slot_time_gu} છે. "
            f"{self.session.selected_doctor_name_gu} માટે ત્રિનય ઓર્થોપેડિક હોસ્પિટલ તરફથી આભાર."
        )
        success_audio = self._sound(self.tts.synthesize_gujarati(success_text))

        await self.channel.stream_file(success_audio)
        self.session.state = "DONE"
