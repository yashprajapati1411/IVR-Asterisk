# Asterisk Gujarati Doctor Appointment IVR System (TOPH-IVR)

[![Asterisk](https://img.shields.io/badge/Asterisk-18%20%2F%2020%20%2F%2022%20LTS-orange.svg)](https://www.asterisk.org/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Protocol](https://img.shields.io/badge/Protocol-PJSIP%20%2F%20FastAGI-green.svg)]()
[![Voice](https://img.shields.io/badge/Language-Gujarati%20(gu--IN)-purple.svg)]()
[![License](https://img.shields.io/badge/License-MIT-brightgreen.svg)]()

A complete, production-ready automated **Gujarati Doctor Appointment Booking IVR System** built natively for **Asterisk PBX** using **Python FastAGI**.

Features real-time doctor availability checks, 10-digit mobile validation, Gujarati Speech-to-Text (STT) name extraction, dynamic Neural Text-to-Speech (TTS) prompt generation, atomic SQLite database booking locking, unique appointment row numbers, and graceful call flow control.

---

## 🚀 Quick Start (Run in 1 Command)

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/install/)

### 1. Clone & Launch
```bash
git clone https://github.com/yashprajapati1411/IVR-Asterisk.git
cd IVR-Asterisk

# Start Asterisk + FastAGI system
docker compose up -d --build
```

That's it! Asterisk PBX is now running on port `5060` (SIP) and port `4573` (FastAGI).

---

## 📞 Testing Live Calls with MicroSIP / Softphone

1. Install **MicroSIP** (or Zoiper / Linphone).
2. Configure a new account:
   - **SIP Server**: `127.0.0.1` (or your host IP `172.24.X.X`)
   - **Username**: `100`
   - **Password**: `secretpassword123`
   - **Domain**: `127.0.0.1`
   - **Transport**: `TCP`
3. Dial **`1000`** in MicroSIP to initiate the call.

---

## 🔄 Complete IVR Navigation Flow

```
                     ┌────────────────────────┐
                     │ Gujarati Welcome Menu  │
                     │                        │
                     │ Press 1 → Dr. Shaishav │
                     │ Press 2 → Dr. Jaydeep  │
                     │ Press 3 → Other Info   │
                     └───────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
             (1)                (2)                (3)
              │                  │                  │
              ▼                  ▼                  ▼
       Dr. Shaishav       Dr. Jaydeep       Other Information & Fees
              │                  │                  │
              └────────┬─────────┘                  ├─ Press 1 → Return to Menu
                       │                            └─ 20s Inactivity → Goodbye
                       ▼
              CHECK AVAILABILITY
                       │
             ┌─────────┴─────────┐
             │                   │
         AVAILABLE         NOT AVAILABLE
             │                   │
             ▼                   ▼
    Play Slot Timing      "No Slots Today"
    Press 1 → Book        Press 2 → Main Menu
    Press 2 → Main Menu
             │
             ▼
      MOBILE CAPTURE (10 Digits + #)
             │
             ▼
      VALIDATE & READ BACK DIGITS
      Press 1 → Confirm | Press 2 → Re-enter
             │
             ▼
      NAME CAPTURE (Voice Recording + AI STT)
      "તમારું નામ જણાવો"
             │
             ▼
      STT Name Extraction & Confirmation
      "તમારું નામ _____ છે. 1 Confirm | 2 Retry"
             │
             ▼
      FINAL CONFIRMATION
      Press 1 → Book Appointment | Press 2 → Main Menu
             │
             ▼
      DATABASE TRANSACTION & SUCCESS
      Speaks Unique Appointment Number & Slot
             │
             ▼
          HANGUP
```

---

## 🛠️ System Architecture & Key Components

| Component | Layer | Technology |
| :--- | :--- | :--- |
| **PBX Engine** | SIP / Media | Asterisk 18/20 LTS (PJSIP driver over TCP/UDP) |
| **AGI Application** | Business Logic | Python FastAGI (`server.py`, `ivr_engine.py`) on port `4573` |
| **Speech-to-Text** | Name Recognition | Sarvam AI (`saarika:v2`) with Google Speech Recognition fallback |
| **Text-to-Speech** | Audio Synthesis | Microsoft Edge-TTS (`gu-IN-DhwaniNeural`) & FFmpeg 8kHz mono conversion |
| **Database** | Persistence | SQLite 3 (`ivr_appointments.db`) with atomic `BEGIN IMMEDIATE` locks |

---

## 📁 Repository Structure

```text
├── agi/
│   ├── server.py              # FastAGI Server (Async TCP server on port 4573)
│   ├── ivr_engine.py          # State Machine for full IVR call lifecycle
│   ├── agi_channel.py         # Async AGI protocol abstraction (stream, get_data, record)
│   └── session.py             # In-memory call session data model
├── asterisk_config/
│   ├── extensions.conf        # Dialplan extension rules (routes 1000 -> FastAGI)
│   ├── pjsip.conf             # PJSIP endpoint & NAT transport configuration
│   └── rtp.conf               # RTP media port bounds (10000-10100)
├── services/
│   ├── db_service.py          # SQLite database connection & transaction logic
│   ├── stt_service.py         # Gujarati STT & conversational name cleaner
│   └── tts_service.py         # Gujarati neural TTS & FFmpeg audio converter
├── sounds/
│   └── gu/                    # Static Gujarati WAV prompts (8000Hz 16-bit Mono PCM)
├── tests/
│   ├── test_ivr_engine.py     # Pytest unit tests for full IVR state machine
│   └── test_db_service.py    # Pytest unit tests for database transactions
├── Dockerfile                 # Multi-stage Ubuntu Docker build with FFmpeg & Asterisk
├── docker-compose.yml         # Container orchestrator
├── requirements.txt           # Python dependencies
└── README.md                  # System Documentation
```

---

## 🧪 Running Automated Tests

Run the full pytest suite locally or inside Docker:

```bash
# Run tests locally
python -m pytest tests/

# Or run tests inside running Docker container
docker exec asterisk-gujarati-ivr python3 -m pytest tests/
```

---

## ⚙️ Environment Configuration (.env)

Create a `.env` file in the root directory (optional, fallbacks work automatically):

```env
SARVAM_API_KEY="your-sarvam-api-key"   # Optional: Sarvam AI STT key
ASTERISK_SOUNDS_DIR="/var/lib/asterisk/sounds/ivr"
```

---

## 📜 License
This project is open-source under the [MIT License](LICENSE).
