#!/usr/bin/env python3
"""
Standard AGI script for Asterisk (reads from stdin, writes to stdout).
Place in /var/lib/asterisk/agi-bin/ivr_handler.py with chmod +x.
"""
import asyncio
import logging
import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agi.agi_channel import AGIChannel
from agi.ivr_engine import IVREngine
from services.db_service import DatabaseService
from services.stt_service import SarvamSTTService
from services.tts_service import TTSService

logging.basicConfig(
    filename="/tmp/asterisk_ivr.log" if os.name != "nt" else "asterisk_ivr.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

async def main():
    db = DatabaseService()
    db.seed_initial_data()
    stt = SarvamSTTService()
    tts = TTSService()
    channel = AGIChannel() # stdin / stdout
    engine = IVREngine(channel=channel, db_service=db, stt_service=stt, tts_service=tts)
    await engine.run()

if __name__ == "__main__":
    asyncio.run(main())
