"""
Database Service with Transactional Locking for Asterisk IVR Doctor Appointment Booking.
Uses SQLite with WAL mode and atomic transaction locking (BEGIN IMMEDIATE).
"""
import sqlite3
import os
import datetime
from typing import Optional, Dict, Any, List

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ivr_appointments.db")

class DatabaseService:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.executescript("""
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY,
            name_en TEXT NOT NULL,
            name_gu TEXT NOT NULL,
            specialty_en TEXT,
            specialty_gu TEXT,
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS doctor_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id INTEGER NOT NULL,
            day_of_week INTEGER NOT NULL, -- 0=Mon, 6=Sun
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            slot_time_gu TEXT NOT NULL,
            slot_time_en TEXT NOT NULL,
            max_slots INTEGER DEFAULT 10,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY(doctor_id) REFERENCES doctors(id)
        );

        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mobile_number TEXT UNIQUE NOT NULL,
            name_gu TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_code TEXT UNIQUE NOT NULL,
            doctor_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            appointment_date TEXT NOT NULL, -- YYYY-MM-DD
            slot_time TEXT NOT NULL,
            status TEXT DEFAULT 'CONFIRMED', -- 'CONFIRMED', 'CANCELLED'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(doctor_id) REFERENCES doctors(id),
            FOREIGN KEY(patient_id) REFERENCES patients(id)
        );
        """)
        conn.close()

    def seed_initial_data(self, reset: bool = False):
        """Seeds default doctors (Dr. Shaishav, Dr. Jaydeep) and weekly schedules."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check if old legacy block schedules exist (e.g. 5:00 PM to 8:00 PM)
        cursor.execute("SELECT COUNT(*) as cnt FROM doctor_schedules WHERE slot_time_gu LIKE '%5:00 થી 8:00%' OR slot_time_gu LIKE '%10:00 થી બપોરે 1:00%'")
        has_legacy = cursor.fetchone()["cnt"] > 0

        if reset or has_legacy:
            cursor.execute("DELETE FROM appointments")
            cursor.execute("DELETE FROM doctor_schedules")
            cursor.execute("DELETE FROM doctors")

        # Check if doctors exist
        cursor.execute("SELECT COUNT(*) as cnt FROM doctors")
        if cursor.fetchone()["cnt"] == 0:
            doctors = [
                (1, "Dr. Shaishav Soni", "ડૉક્ટર શૈશવ સોની", "Orthopedic Surgeon", "ઓર્થોપેડિક સર્જન", 1),
                (2, "Dr. Jaydeep Patel", "ડૉક્ટર જયદીપ પટેલ", "Spine Specialist", "કરોડરજ્જુ નિષ્ણાત", 1)
            ]
            cursor.executemany(
                "INSERT INTO doctors (id, name_en, name_gu, specialty_en, specialty_gu, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                doctors
            )

            # Schedules: Every day (0 to 6)
            schedules = []
            for day in range(7):
                # Dr. Shaishav Soni (Doctor 1): 3 hourly slots (5 PM-6 PM, 6 PM-7 PM, 7 PM-8 PM), max 8 each
                schedules.append((1, day, "17:00", "18:00", "સાંજે 5:00 થી 6:00", "5:00 PM to 6:00 PM", 8, 1))
                schedules.append((1, day, "18:00", "19:00", "સાંજે 6:00 થી 7:00", "6:00 PM to 7:00 PM", 8, 1))
                schedules.append((1, day, "19:00", "20:00", "સાંજે 7:00 થી 8:00", "7:00 PM to 8:00 PM", 8, 1))

                # Dr. Jaydeep Patel (Doctor 2): 4 hourly slots (10 AM-11 AM, 11 AM-12 PM, 12 PM-1 PM, 1 PM-2 PM), max 8 each
                schedules.append((2, day, "10:00", "11:00", "સવારે 10:00 થી 11:00", "10:00 AM to 11:00 AM", 8, 1))
                schedules.append((2, day, "11:00", "12:00", "સવારે 11:00 થી 12:00", "11:00 AM to 12:00 PM", 8, 1))
                schedules.append((2, day, "12:00", "13:00", "બપોરે 12:00 થી 1:00", "12:00 PM to 1:00 PM", 8, 1))
                schedules.append((2, day, "13:00", "14:00", "બપોરે 1:00 થી 2:00", "1:00 PM to 2:00 PM", 8, 1))
                
            cursor.executemany(
                """INSERT INTO doctor_schedules 
                   (doctor_id, day_of_week, start_time, end_time, slot_time_gu, slot_time_en, max_slots, is_active) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                schedules
            )
        conn.close()

    def get_doctor(self, doctor_id: int) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM doctors WHERE id = ? AND is_active = 1", (doctor_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def check_availability(
        self,
        doctor_id: int,
        target_date: Optional[str] = None,
        current_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Checks today's (or given date's) hourly slot availability for a doctor.
        Filters out past hourly slots for today.
        Returns dict with available=True/False and list of available hourly slots.
        """
        today_str = datetime.date.today().isoformat()
        if not target_date:
            target_date = today_str
        
        target_dt = datetime.date.fromisoformat(target_date)
        day_of_week = target_dt.weekday() # 0=Monday, 6=Sunday

        filter_time = None
        if target_date == today_str:
            filter_time = current_time if current_time is not None else datetime.datetime.now().strftime("%H:%M")

        conn = self.get_connection()
        cursor = conn.cursor()

        # Get schedules for this doctor and day of week
        cursor.execute("""
            SELECT * FROM doctor_schedules 
            WHERE doctor_id = ? AND day_of_week = ? AND is_active = 1
            ORDER BY start_time ASC
        """, (doctor_id, day_of_week))
        schedules = cursor.fetchall()

        if not schedules:
            conn.close()
            return {
                "available": False,
                "reason": "NO_SCHEDULE",
                "doctor_id": doctor_id,
                "date": target_date,
                "slots": []
            }

        available_slots = []
        for s in schedules:
            # Filter out past slots for today (where end_time <= filter_time)
            if filter_time and target_date == today_str:
                if s["end_time"] <= filter_time:
                    continue

            slot_time_gu = s["slot_time_gu"]
            max_slots = s["max_slots"]

            cursor.execute("""
                SELECT COUNT(*) as booked FROM appointments 
                WHERE doctor_id = ? AND appointment_date = ? AND slot_time = ? AND status = 'CONFIRMED'
            """, (doctor_id, target_date, slot_time_gu))
            booked_count = cursor.fetchone()["booked"]
            slots_left = max_slots - booked_count

            if slots_left > 0:
                available_slots.append({
                    "slot_time_gu": slot_time_gu,
                    "slot_time_en": s["slot_time_en"],
                    "start_time": s["start_time"],
                    "end_time": s["end_time"],
                    "max_slots": max_slots,
                    "booked_count": booked_count,
                    "slots_left": slots_left
                })

        conn.close()

        if available_slots:
            return {
                "available": True,
                "doctor_id": doctor_id,
                "date": target_date,
                "slots": available_slots,
                "slot_time_gu": available_slots[0]["slot_time_gu"],
                "slot_time_en": available_slots[0]["slot_time_en"]
            }
        else:
            return {
                "available": False,
                "reason": "SLOTS_FULL",
                "doctor_id": doctor_id,
                "date": target_date,
                "slots": []
            }

    def book_appointment(
        self,
        doctor_id: int,
        mobile_number: str,
        patient_name_gu: str,
        target_date: Optional[str] = None,
        slot_time_gu: Optional[str] = None,
        current_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes atomic database transaction:
        1. Locks doctor & date with BEGIN IMMEDIATE.
        2. Verifies hourly slot availability and that slot end_time has not passed.
        3. Creates/upserts patient.
        4. Creates appointment.
        5. Returns appointment code and details.
        """
        today_str = datetime.date.today().isoformat()
        if not target_date:
            target_date = today_str
            
        target_dt = datetime.date.fromisoformat(target_date)
        day_of_week = target_dt.weekday()

        filter_time = None
        if target_date == today_str:
            filter_time = current_time if current_time is not None else datetime.datetime.now().strftime("%H:%M")

        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Atomic lock
            cursor.execute("BEGIN IMMEDIATE")

            # Verify doctor exists
            cursor.execute("SELECT * FROM doctors WHERE id = ? AND is_active = 1", (doctor_id,))
            doctor = cursor.fetchone()
            if not doctor:
                cursor.execute("ROLLBACK")
                conn.close()
                return {"success": False, "error": "DOCTOR_NOT_FOUND"}

            # Verify schedule and capacity for selected slot
            if slot_time_gu:
                cursor.execute("""
                    SELECT * FROM doctor_schedules 
                    WHERE doctor_id = ? AND day_of_week = ? AND slot_time_gu = ? AND is_active = 1
                """, (doctor_id, day_of_week, slot_time_gu))
                schedule = cursor.fetchone()
            else:
                cursor.execute("""
                    SELECT * FROM doctor_schedules 
                    WHERE doctor_id = ? AND day_of_week = ? AND is_active = 1
                    ORDER BY start_time ASC
                """, (doctor_id, day_of_week))
                all_scheds = cursor.fetchall()
                schedule = None
                for sch in all_scheds:
                    if not (filter_time and target_date == today_str and sch["end_time"] <= filter_time):
                        schedule = sch
                        break

            if not schedule:
                cursor.execute("ROLLBACK")
                conn.close()
                return {"success": False, "error": "NO_SCHEDULE"}

            if filter_time and target_date == today_str and schedule["end_time"] <= filter_time:
                cursor.execute("ROLLBACK")
                conn.close()
                return {"success": False, "error": "SLOT_EXPIRED"}

            target_slot_time_gu = schedule["slot_time_gu"]
            max_slots = schedule["max_slots"]

            cursor.execute("""
                SELECT COUNT(*) as booked FROM appointments 
                WHERE doctor_id = ? AND appointment_date = ? AND slot_time = ? AND status = 'CONFIRMED'
            """, (doctor_id, target_date, target_slot_time_gu))
            booked_count = cursor.fetchone()["booked"]

            if booked_count >= max_slots:
                cursor.execute("ROLLBACK")
                conn.close()
                return {"success": False, "error": "SLOTS_FULL"}

            # Upsert patient
            cursor.execute("SELECT id FROM patients WHERE mobile_number = ?", (mobile_number,))
            existing_patient = cursor.fetchone()
            if existing_patient:
                patient_id = existing_patient["id"]
                cursor.execute("""
                    UPDATE patients 
                    SET name_gu = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                """, (patient_name_gu, patient_id))
            else:
                cursor.execute("""
                    INSERT INTO patients (mobile_number, name_gu) 
                    VALUES (?, ?)
                """, (mobile_number, patient_name_gu))
                patient_id = cursor.lastrowid

            # Generate unique appointment reference code
            cursor.execute("SELECT COUNT(*) as total_appts FROM appointments")
            total = cursor.fetchone()["total_appts"]
            appointment_code = f"APT-{1000 + total + 1}"

            # Insert appointment
            cursor.execute("""
                INSERT INTO appointments 
                (appointment_code, doctor_id, patient_id, appointment_date, slot_time, status)
                VALUES (?, ?, ?, ?, ?, 'CONFIRMED')
            """, (appointment_code, doctor_id, patient_id, target_date, target_slot_time_gu))
            appointment_id = cursor.lastrowid

            cursor.execute("COMMIT")
            conn.close()

            return {
                "success": True,
                "appointment_id": appointment_id,
                "appointment_number": appointment_id,
                "appointment_code": appointment_code,
                "doctor_id": doctor_id,
                "doctor_name_gu": doctor["name_gu"],
                "doctor_name_en": doctor["name_en"],
                "patient_name_gu": patient_name_gu,
                "mobile_number": mobile_number,
                "appointment_date": target_date,
                "slot_time_gu": target_slot_time_gu,
                "slot_time_en": schedule["slot_time_en"]
            }

        except Exception as e:
            cursor.execute("ROLLBACK")
            conn.close()
            return {"success": False, "error": str(e)}

    def set_doctor_slots(self, doctor_id: int, max_slots: int):
        """Helper for testing: update doctor's max slots."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE doctor_schedules SET max_slots = ? WHERE doctor_id = ?", (max_slots, doctor_id))
        conn.commit()
        conn.close()
