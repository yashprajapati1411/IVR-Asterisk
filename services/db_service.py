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
        
        if reset:
            cursor.execute("DELETE FROM appointments")
            cursor.execute("DELETE FROM patients")
            cursor.execute("DELETE FROM doctor_schedules")
            cursor.execute("DELETE FROM doctors")

        # Check if doctors exist
        cursor.execute("SELECT COUNT(*) as cnt FROM doctors")
        if cursor.fetchone()["cnt"] == 0:
            doctors = [
                (1, "Dr. Shaishav", "ડૉક્ટર શૈશવ", "General Physician", "જનરલ ફિઝિશિયન", 1),
                (2, "Dr. Jaydeep", "ડૉક્ટર જયદીપ", "Cardiologist", "હૃદયરોગ નિષ્ણાત", 1)
            ]
            cursor.executemany(
                "INSERT INTO doctors (id, name_en, name_gu, specialty_en, specialty_gu, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                doctors
            )

            # Schedules: Every day (0 to 6)
            schedules = []
            for day in range(7):
                # Dr. Shaishav: 5:00 PM to 8:00 PM (10 slots)
                schedules.append((1, day, "17:00", "20:00", "સાંજે 5:00 વાગ્યે", "5:00 PM", 10, 1))
                # Dr. Jaydeep: 10:00 AM to 1:00 PM (8 slots)
                schedules.append((2, day, "10:00", "13:00", "સવારે 10:00 વાગ્યે", "10:00 AM", 8, 1))
                
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

    def check_availability(self, doctor_id: int, target_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Checks today's (or given date's) slot availability for a doctor.
        Returns dict with available=True/False and slot details.
        """
        if not target_date:
            target_date = datetime.date.today().isoformat()
        
        target_dt = datetime.date.fromisoformat(target_date)
        day_of_week = target_dt.weekday() # 0=Monday, 6=Sunday

        conn = self.get_connection()
        cursor = conn.cursor()

        # Get schedule for this doctor and day of week
        cursor.execute("""
            SELECT * FROM doctor_schedules 
            WHERE doctor_id = ? AND day_of_week = ? AND is_active = 1
        """, (doctor_id, day_of_week))
        schedule = cursor.fetchone()

        if not schedule:
            conn.close()
            return {
                "available": False,
                "reason": "NO_SCHEDULE",
                "doctor_id": doctor_id,
                "date": target_date
            }

        # Count booked appointments for this doctor on target_date
        cursor.execute("""
            SELECT COUNT(*) as booked FROM appointments 
            WHERE doctor_id = ? AND appointment_date = ? AND status = 'CONFIRMED'
        """, (doctor_id, target_date))
        booked_count = cursor.fetchone()["booked"]
        max_slots = schedule["max_slots"]
        slots_left = max_slots - booked_count

        conn.close()

        if slots_left > 0:
            return {
                "available": True,
                "doctor_id": doctor_id,
                "date": target_date,
                "slot_time_gu": schedule["slot_time_gu"],
                "slot_time_en": schedule["slot_time_en"],
                "slots_left": slots_left,
                "max_slots": max_slots
            }
        else:
            return {
                "available": False,
                "reason": "SLOTS_FULL",
                "doctor_id": doctor_id,
                "date": target_date,
                "slots_left": 0
            }

    def book_appointment(
        self,
        doctor_id: int,
        mobile_number: str,
        patient_name_gu: str,
        target_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes atomic database transaction:
        1. Locks doctor & date with BEGIN IMMEDIATE.
        2. Verifies availability.
        3. Creates/upserts patient.
        4. Creates appointment.
        5. Returns appointment code and details.
        """
        if not target_date:
            target_date = datetime.date.today().isoformat()
            
        target_dt = datetime.date.fromisoformat(target_date)
        day_of_week = target_dt.weekday()

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

            # Verify schedule and capacity
            cursor.execute("""
                SELECT * FROM doctor_schedules 
                WHERE doctor_id = ? AND day_of_week = ? AND is_active = 1
            """, (doctor_id, day_of_week))
            schedule = cursor.fetchone()
            if not schedule:
                cursor.execute("ROLLBACK")
                conn.close()
                return {"success": False, "error": "NO_SCHEDULE"}

            cursor.execute("""
                SELECT COUNT(*) as booked FROM appointments 
                WHERE doctor_id = ? AND appointment_date = ? AND status = 'CONFIRMED'
            """, (doctor_id, target_date))
            booked_count = cursor.fetchone()["booked"]

            if booked_count >= schedule["max_slots"]:
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

            slot_time = schedule["slot_time_gu"]

            # Insert appointment
            cursor.execute("""
                INSERT INTO appointments 
                (appointment_code, doctor_id, patient_id, appointment_date, slot_time, status)
                VALUES (?, ?, ?, ?, ?, 'CONFIRMED')
            """, (appointment_code, doctor_id, patient_id, target_date, slot_time))
            appointment_id = cursor.lastrowid

            cursor.execute("COMMIT")
            conn.close()

            return {
                "success": True,
                "appointment_id": appointment_id,
                "appointment_code": appointment_code,
                "doctor_id": doctor_id,
                "doctor_name_gu": doctor["name_gu"],
                "doctor_name_en": doctor["name_en"],
                "patient_name_gu": patient_name_gu,
                "mobile_number": mobile_number,
                "appointment_date": target_date,
                "slot_time_gu": slot_time,
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
