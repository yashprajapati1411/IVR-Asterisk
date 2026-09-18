"""
Database Seed and Inspection Script for Asterisk IVR.
"""
import sys
import os
import datetime

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.db_service import DatabaseService

def main():
    db = DatabaseService()
    db.seed_initial_data(reset=True)
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    print("=== Doctors in DB ===")
    cursor.execute("SELECT * FROM doctors")
    for doc in cursor.fetchall():
        print(f"ID: {doc['id']} | En: {doc['name_en']} | Gu: {doc['name_gu']} | Specialty: {doc['specialty_gu']}")

    print("\n=== Today's Availability ===")
    today = datetime.date.today().isoformat()
    for doc_id in (1, 2):
        avail = db.check_availability(doc_id, today)
        print(f"Doctor {doc_id}: Available={avail.get('available')}, Slot={avail.get('slot_time_gu')}, Slots Left={avail.get('slots_left')}")

    conn.close()

if __name__ == "__main__":
    main()
