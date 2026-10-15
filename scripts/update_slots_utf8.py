import sqlite3

def run():
    db_paths = ["/app/ivr_appointments.db", "ivr_appointments.db"]
    for path in db_paths:
        try:
            conn = sqlite3.connect(path)
            c = conn.cursor()
            c.execute("UPDATE doctor_schedules SET slot_time_gu = 'સાંજે 5:00 થી 6:00' WHERE slot_time_en = '5:00 PM to 6:00 PM' AND slot_time_gu LIKE '%?%'")
            c.execute("UPDATE doctor_schedules SET slot_time_gu = 'સાંજે 6:00 થી 7:00' WHERE slot_time_en = '6:00 PM to 7:00 PM' AND slot_time_gu LIKE '%?%'")
            c.execute("UPDATE doctor_schedules SET slot_time_gu = 'સાંજે 7:00 થી 8:00' WHERE slot_time_en = '7:00 PM to 8:00 PM' AND slot_time_gu LIKE '%?%'")
            conn.commit()
            conn.close()
            print(f"Updated schedules in {path}")
        except Exception as e:
            pass

    import sys
    sys.path.insert(0, '/app')
    from services.db_service import DatabaseService
    import json
    db = DatabaseService()
    print("Doc 1:", json.dumps(db.check_availability(1), ensure_ascii=False))
    print("Doc 2:", json.dumps(db.check_availability(2), ensure_ascii=False))

if __name__ == "__main__":
    run()
