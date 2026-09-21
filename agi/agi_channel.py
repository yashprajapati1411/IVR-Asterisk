"""
Asterisk Gateway Interface (AGI) Channel Protocol Implementation.
Supports both FastAGI (asyncio Stream reader/writer) and Standard AGI (stdio).
"""
import sys
import os
import re
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger("AGIChannel")

class AGIChannel:
    """Handles communication with Asterisk over AGI/FastAGI protocol."""

    def __init__(self, reader=None, writer=None):
        self.reader = reader
        self.writer = writer
        self.env: Dict[str, str] = {}
        self.is_hungup = False

    async def init_session(self) -> Dict[str, str]:
        """Reads initial AGI environment variables sent by Asterisk."""
        self.env = {}
        while True:
            if self.reader:
                line = await self.reader.readline()
                line = line.decode("utf-8", errors="ignore").strip()
            else:
                line = sys.stdin.readline().strip()

            if not line:
                break

            if ":" in line:
                key, val = line.split(":", 1)
                self.env[key.strip()] = val.strip()

        logger.debug(f"AGI session initialized with env: {self.env}")
        return self.env

    async def send_command(self, cmd: str) -> Tuple[int, str, str]:
        """
        Sends an AGI command to Asterisk and returns (status_code, result_value, raw_response).
        E.g. "200 result=1" -> (200, "1", "200 result=1")
        """
        if self.is_hungup:
            return 511, "", "Channel already hungup"

        cmd_clean = cmd.strip() + "\n"
        if self.writer:
            self.writer.write(cmd_clean.encode("utf-8"))
            await self.writer.drain()
            resp_line = await self.reader.readline()
            resp = resp_line.decode("utf-8", errors="ignore").strip()
        else:
            sys.stdout.write(cmd_clean)
            sys.stdout.flush()
            resp = sys.stdin.readline().strip()

        logger.debug(f"AGI CMD: '{cmd.strip()}' -> RESP: '{resp}'")

        if not resp:
            self.is_hungup = True
            return -1, "", "Empty response (channel closed)"

        # Parse status code
        parts = resp.split(" ", 2)
        try:
            status_code = int(parts[0])
        except ValueError:
            status_code = -1

        # Match result=<value>
        match = re.search(r"result=([^\s]+)", resp)
        result_val = match.group(1) if match else ""

        # Status 511 indicates Asterisk channel is dead/hung up.
        # -1 indicates connection error.
        # Note: result=-1 does NOT mean hungup! It is returned on timeout, silence, or non-fatal command errors.
        if status_code in (511, -1):
            self.is_hungup = True

        return status_code, result_val, resp

    async def answer(self) -> bool:
        status, result, _ = await self.send_command("ANSWER")
        return result == "0"

    async def verbose(self, message: str, level: int = 1):
        clean_msg = message.replace('"', '\\"')
        await self.send_command(f'VERBOSE "{clean_msg}" {level}')

    async def stream_file(self, filename: str, escape_digits: str = "") -> Optional[str]:
        """
        Streams audio file. Strips .wav extension if present.
        Returns pressed escape digit, or None if audio played to end.
        """
        # Asterisk expects filename without extension
        if filename.endswith(".wav"):
            filename = filename[:-4]

        status, result, _ = await self.send_command(f'STREAM FILE "{filename}" "{escape_digits}"')
        if result and result != "0" and result != "-1":
            try:
                ascii_code = int(result)
                if ascii_code > 0:
                    return chr(ascii_code)
            except ValueError:
                return result
        return None

    async def get_data(self, filename: str, timeout_ms: int = 5000, max_digits: int = 1) -> Optional[str]:
        """
        Plays audio prompt and captures DTMF digits.
        """
        if filename.endswith(".wav"):
            filename = filename[:-4]

        status, result, raw = await self.send_command(f'GET DATA "{filename}" {timeout_ms} {max_digits}')
        if result and result != "-1" and result != "timeout":
            return result
        return None

    async def record_file(
        self,
        filename: str,
        format_type: str = "wav",
        escape_digits: str = "#",
        timeout_ms: int = 5000,
        beep: bool = True,
        silence_sec: int = 2
    ) -> bool:
        """
        Records user audio on Asterisk.
        Usage: RECORD FILE <file> <format> <escape_digits> <timeout> <offset> <beep> <s>
        """
        if filename.endswith(f".{format_type}"):
            filename = filename[: -(len(format_type) + 1)]

        beep_str = "beep" if beep else ""
        cmd = f'RECORD FILE "{filename}" {format_type} "{escape_digits}" {timeout_ms} 0 {beep_str} s={silence_sec}'
        status, result, _ = await self.send_command(cmd)
        return status == 200 and result != "-1"

    async def say_digits(self, digits: str, escape_digits: str = "") -> Optional[str]:
        """Pronounces digits."""
        status, result, _ = await self.send_command(f'SAY DIGITS {digits} "{escape_digits}"')
        if result and result != "0" and result != "-1":
            try:
                ascii_code = int(result)
                if ascii_code > 0:
                    return chr(ascii_code)
            except ValueError:
                return result
        return None

    async def hangup(self):
        if not self.is_hungup:
            await self.send_command("HANGUP")
            self.is_hungup = True
