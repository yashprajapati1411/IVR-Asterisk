"""
FastAGI Server for Asterisk.
Listens for incoming TCP connections from Asterisk (default port 4573),
and executes the IVREngine state machine.
"""
import asyncio
import argparse
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
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s"
)
logger = logging.getLogger("FastAGIServer")

class FastAGIServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 4573):
        self.host = host
        self.port = port
        self.db = DatabaseService()
        self.stt = SarvamSTTService()
        self.tts = TTSService()
        # Seed default doctors & schedules if DB is fresh
        self.db.seed_initial_data()

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peer = writer.get_extra_info("peername")
        logger.info(f"Incoming Asterisk FastAGI connection from {peer}")
        try:
            channel = AGIChannel(reader=reader, writer=writer)
            engine = IVREngine(
                channel=channel,
                db_service=self.db,
                stt_service=self.stt,
                tts_service=self.tts
            )
            await engine.run()
        except Exception as e:
            logger.exception(f"Error handling FastAGI client {peer}: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            logger.info(f"Closed FastAGI connection from {peer}")

    async def start(self):
        server = await asyncio.start_server(self.handle_client, self.host, self.port)
        addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets)
        logger.info(f"FastAGI Server listening on {addrs}")
        async with server:
            await server.serve_forever()

def main():
    parser = argparse.ArgumentParser(description="Asterisk Gujarati IVR FastAGI Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host address to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=4573, help="Port to listen on (default: 4573)")
    args = parser.parse_args()

    server = FastAGIServer(host=args.host, port=args.port)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("FastAGI Server stopped by user.")

if __name__ == "__main__":
    main()
