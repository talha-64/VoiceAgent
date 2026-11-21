import sqlite3
import os
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional

DB_PATH = Path(__file__).resolve().parent / "hospital.db"

def get_db_connection() -> sqlite3.Connection:
    """Returns a SQLite connection with dict-like row access."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def init_db():
    """Initializes the database schema and seeds initial data."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Doctors table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS doctors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        name_en TEXT NOT NULL,
        specialty TEXT NOT NULL,
        specialty_en TEXT NOT NULL,
        qualification TEXT NOT NULL,
        room_number TEXT NOT NULL,
        consultation_fee INTEGER NOT NULL,
        available_days TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        slot_duration_minutes INTEGER DEFAULT 30
    );
    """)

    # 2. Appointments table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        appointment_number TEXT UNIQUE NOT NULL,
        patient_name TEXT NOT NULL,
        patient_phone TEXT NOT NULL,
        doctor_id INTEGER NOT NULL,
        appointment_date TEXT NOT NULL,
        time_slot TEXT NOT NULL,
        reason TEXT DEFAULT 'General Consultation',
        status TEXT DEFAULT 'confirmed',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE
    );
    """)

    # Check if doctors are already seeded
    cursor.execute("SELECT COUNT(*) FROM doctors;")
    if cursor.fetchone()[0] == 0:
        seed_doctors = [
            (
                "ڈاکٹر طارق محمود",
                "Dr. Tariq Mahmood",
                "کارڈیالوجسٹ (ماہر امراض قلب)",
                "Cardiology",
                "MBBS, FCPS (Cardiology)",
                "Room 102 (1st Floor)",
                2500,
                "Monday, Tuesday, Wednesday, Thursday, Friday",
                "10:00",
                "14:00",
                30
            ),
            (
                "ڈاکٹر فاطمہ نور",
                "Dr. Fatima Noor",
                "ماہر امراض اطفال (بچوں کی ڈاکٹر)",
                "Pediatrics",
                "MBBS, MCPS (Pediatrics)",
                "Room 205 (2nd Floor)",
                1800,
                "Monday, Tuesday, Wednesday, Thursday, Friday, Saturday",
                "16:00",
                "20:00",
                30
            ),
            (
                "ڈاکٹر عمران خان",
                "Dr. Imran Khan",
                "آرتھوپیڈک سرجن (ہڈی و جوڑ)",
                "Orthopedics",
                "MBBS, MS (Orthopedic Surgery)",
                "Room 108 (1st Floor)",
                2200,
                "Tuesday, Thursday, Saturday",
                "11:00",
                "15:00",
                30
            ),
            (
                "ڈاکٹر عائشہ صدیقی",
                "Dr. Ayesha Siddiqui",
                "جنرل فزیشن (ماہر طب و علاج)",
                "General Physician",
                "MBBS, FCPS (Medicine)",
                "Room 101 (Ground Floor)",
                1200,
                "Monday, Tuesday, Wednesday, Thursday, Friday, Saturday",
                "09:00",
                "13:00",
                30
            ),
            (
                "ڈاکٹر زینب بلال",
                "Dr. Zainab Bilal",
                "گائناکالوجسٹ (ماہر امراض نسواں)",
                "Gynecology",
                "MBBS, FCPS (Obstetrics & Gynecology)",
                "Room 304 (3rd Floor)",
                2000,
                "Monday, Wednesday, Friday",
                "14:00",
                "18:00",
                30
            )
        ]
        cursor.executemany("""
        INSERT INTO doctors (
            name, name_en, specialty, specialty_en, qualification,
            room_number, consultation_fee, available_days, start_time, end_time, slot_duration_minutes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, seed_doctors)

        # Seed initial sample appointments for realistic initial view
        today = date.today().strftime("%Y-%m-%d")
        tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        sample_appointments = [
            ("APT-1001", "محمد علی", "03001234567", 1, today, "10:30 AM", "سینے میں درد اور بلڈ پریشر چیک اپ", "confirmed", now_str, now_str),
            ("APT-1002", "سارہ خان", "03219876543", 2, today, "04:30 PM", "بچے کو بخار اور کھانسی", "confirmed", now_str, now_str),
            ("APT-1003", "عثمان ملک", "03335551234", 3, tomorrow, "11:30 AM", "گھٹنے کا درد", "confirmed", now_str, now_str),
            ("APT-1004", "بلال حسن", "03124449876", 4, today, "09:30 AM", "سر درد اور الرجی", "completed", now_str, now_str),
        ]
        cursor.executemany("""
        INSERT INTO appointments (
            appointment_number, patient_name, patient_phone, doctor_id,
            appointment_date, time_slot, reason, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, sample_appointments)

    conn.commit()
    conn.close()

# Initialize upon module load
init_db()

# ==============================================================================
# Helper Queries for Doctors & Slots
# ==============================================================================

def get_all_doctors() -> List[Dict[str, Any]]:
    """Returns all registered doctors."""
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM doctors ORDER BY id ASC;").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def find_doctor_by_query(query: str) -> Optional[Dict[str, Any]]:
    """Finds a doctor by ID, name in Urdu, name in English, or specialty."""
    query_str = query.strip().lower()
    conn = get_db_connection()
    doctors = [dict(r) for r in conn.execute("SELECT * FROM doctors;").fetchall()]
    conn.close()

    # Match by ID if numeric
    if query_str.isdigit():
        doc_id = int(query_str)
        for d in doctors:
            if d["id"] == doc_id:
                return d

    # Exact or substring match on names and specialties
    for d in doctors:
        if (query_str in d["name"].lower() or 
            query_str in d["name_en"].lower() or 
            query_str in d["specialty"].lower() or 
            query_str in d["specialty_en"].lower()):
            return d

    # Fallback search by individual tokens
    tokens = query_str.split()
    for d in doctors:
        for t in tokens:
            if len(t) > 2 and (t in d["name"].lower() or t in d["name_en"].lower() or t in d["specialty"].lower() or t in d["specialty_en"].lower()):
                return d

    return None

def format_time_12h(time_str: str) -> str:
    """Converts '14:30' to '02:30 PM'."""
    try:
        t = datetime.strptime(time_str.strip(), "%H:%M")
        return t.strftime("%I:%M %p")
    except Exception:
        return time_str

def parse_time_24h(time_str: str) -> str:
    """Converts '02:30 PM' or '2:30pm' to '14:30'."""
    clean = time_str.strip().upper().replace(".", "")
    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M"):
        try:
            t = datetime.strptime(clean, fmt)
            return t.strftime("%H:%M")
        except ValueError:
            continue
    return time_str

def generate_slots(start_time: str, end_time: str, duration_minutes: int) -> List[str]:
    """Generates 12-hour formatted time slots between start and end time."""
    slots = []
    curr = datetime.strptime(start_time, "%H:%M")
    end = datetime.strptime(end_time, "%H:%M")
    while curr < end:
        slots.append(curr.strftime("%I:%M %p"))
        curr += timedelta(minutes=duration_minutes)
    return slots

def get_doctor_availability_and_slots(doctor_id: int, target_date_str: str) -> Dict[str, Any]:
    """
    Computes available and booked slots for a given doctor on a specific date (YYYY-MM-DD).
    """
    conn = get_db_connection()
    doc_row = conn.execute("SELECT * FROM doctors WHERE id = ?;", (doctor_id,)).fetchone()
    if not doc_row:
        conn.close()
        return {"error": "Doctor not found", "available": False, "slots": []}

    doctor = dict(doc_row)

    # Validate target date format
    try:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    except Exception:
        conn.close()
        return {"error": f"Invalid date format: {target_date_str}. Expected YYYY-MM-DD.", "available": False, "slots": []}

    day_of_week = target_date.strftime("%A")
    is_available_day = day_of_week.lower() in doctor["available_days"].lower()

    if not is_available_day:
        conn.close()
        return {
            "doctor": doctor,
            "date": target_date_str,
            "day_of_week": day_of_week,
            "is_working_day": False,
            "message": f"{doctor['name']} ({doctor['name_en']}) {day_of_week} کو ہسپتال میں دستیاب نہیں ہیں۔ ان کے کام کے دن: {doctor['available_days']}",
            "slots": []
        }

    all_slots = generate_slots(doctor["start_time"], doctor["end_time"], doctor["slot_duration_minutes"])

    # Query already booked slots (confirmed or rescheduled)
    booked_rows = conn.execute("""
        SELECT time_slot FROM appointments 
        WHERE doctor_id = ? AND appointment_date = ? AND status != 'cancelled';
    """, (doctor_id, target_date_str)).fetchall()
    conn.close()

    # Normalize booked slots to 12h
    booked_slots = set()
    for r in booked_rows:
        raw_slot = r["time_slot"]
        booked_slots.add(format_time_12h(parse_time_24h(raw_slot)))

    slot_details = []
    available_count = 0
    for s in all_slots:
        is_booked = s in booked_slots
        if not is_booked:
            available_count += 1
        slot_details.append({
            "slot": s,
            "available": not is_booked
        })

    return {
        "doctor": doctor,
        "date": target_date_str,
        "day_of_week": day_of_week,
        "is_working_day": True,
        "total_slots": len(all_slots),
        "available_slots_count": available_count,
        "slots": slot_details
    }

# ==============================================================================
# Appointments CRUD Operations
# ==============================================================================

def generate_appointment_number() -> str:
    """Generates next unique appointment number like APT-1005."""
    conn = get_db_connection()
    row = conn.execute("SELECT appointment_number FROM appointments ORDER BY id DESC LIMIT 1;").fetchone()
    conn.close()
    if row and row["appointment_number"].startswith("APT-"):
        try:
            num = int(row["appointment_number"].split("-")[1])
            return f"APT-{num + 1}"
        except Exception:
            pass
    return "APT-1005"

def create_appointment(
    patient_name: str,
    patient_phone: str,
    doctor_id: int,
    appointment_date: str,
    time_slot: str,
    reason: Optional[str] = "General Consultation"
) -> Dict[str, Any]:
    """Books a new appointment after verifying slot availability."""
    normalized_slot = format_time_12h(parse_time_24h(time_slot))

    # Check for duplicate active booking on same doctor, date and slot
    conn = get_db_connection()
    existing = conn.execute("""
        SELECT id, appointment_number FROM appointments 
        WHERE doctor_id = ? AND appointment_date = ? AND time_slot = ? AND status != 'cancelled';
    """, (doctor_id, appointment_date, normalized_slot)).fetchone()

    if existing:
        conn.close()
        return {
            "success": False,
            "error": "یہ وقت (Time Slot) پہلے سے بک ہو چکا ہے۔ برائے مہربانی کوئی دوسرا وقت منتخب فرمائیں۔",
            "error_en": f"Slot {normalized_slot} on {appointment_date} is already booked."
        }

    apt_number = generate_appointment_number()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO appointments (
            appointment_number, patient_name, patient_phone, doctor_id,
            appointment_date, time_slot, reason, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'confirmed', ?, ?);
    """, (apt_number, patient_name.strip(), patient_phone.strip(), doctor_id, appointment_date.strip(), normalized_slot, (reason or "General Consultation").strip(), now_str, now_str))
    
    new_id = cursor.lastrowid
    conn.commit()

    # Fetch created record with doctor details
    row = conn.execute("""
        SELECT a.*, d.name as doctor_name, d.name_en as doctor_name_en, d.specialty as doctor_specialty,
               d.room_number, d.consultation_fee
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.id
        WHERE a.id = ?;
    """, (new_id,)).fetchone()
    conn.close()

    return {
        "success": True,
        "appointment": dict(row),
        "message": f"آپ کا اپائنٹمنٹ کامیابی سے بک ہو گیا ہے۔ اپائنٹمنٹ نمبر: {apt_number}۔ وقت: {normalized_slot}، تاریخ: {appointment_date}۔"
    }

def get_all_appointments(
    search: Optional[str] = None,
    doctor_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    date_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Fetches appointments with joined doctor details and optional filtering."""
    conn = get_db_connection()
    query = """
        SELECT a.*, d.name as doctor_name, d.name_en as doctor_name_en, d.specialty as doctor_specialty,
               d.room_number, d.consultation_fee
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.id
        WHERE 1=1
    """
    params = []

    if search:
        s = f"%{search.strip()}%"
        query += " AND (a.patient_name LIKE ? OR a.patient_phone LIKE ? OR a.appointment_number LIKE ?)"
        params.extend([s, s, s])

    if doctor_id:
        query += " AND a.doctor_id = ?"
        params.append(doctor_id)

    if status_filter:
        query += " AND a.status = ?"
        params.append(status_filter)

    if date_filter:
        query += " AND a.appointment_date = ?"
        params.append(date_filter)

    query += " ORDER BY a.appointment_date DESC, a.time_slot ASC, a.id DESC;"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_appointment_by_id_or_number(identifier: str) -> Optional[Dict[str, Any]]:
    """Fetches an appointment by ID, appointment number, or patient phone."""
    conn = get_db_connection()
    query = """
        SELECT a.*, d.name as doctor_name, d.name_en as doctor_name_en, d.specialty as doctor_specialty,
               d.room_number, d.consultation_fee
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.id
        WHERE a.id = ? OR a.appointment_number = ? OR a.patient_phone = ?
        ORDER BY a.id DESC LIMIT 1;
    """
    row = conn.execute(query, (identifier, identifier, identifier)).fetchone()
    conn.close()
    return dict(row) if row else None

def update_appointment(
    appointment_id: int,
    patient_name: Optional[str] = None,
    patient_phone: Optional[str] = None,
    doctor_id: Optional[int] = None,
    appointment_date: Optional[str] = None,
    time_slot: Optional[str] = None,
    reason: Optional[str] = None,
    status: Optional[str] = None
) -> Dict[str, Any]:
    """Updates appointment details, date, or status with slot collision check."""
    conn = get_db_connection()
    current = conn.execute("SELECT * FROM appointments WHERE id = ?;", (appointment_id,)).fetchone()
    if not current:
        conn.close()
        return {"success": False, "error": "Appointment not found"}

    target_doctor_id = doctor_id if doctor_id is not None else current["doctor_id"]
    target_date = appointment_date if appointment_date is not None else current["appointment_date"]
    target_slot = format_time_12h(parse_time_24h(time_slot)) if time_slot is not None else current["time_slot"]

    # If rescheduling to another slot, check availability
    if (target_doctor_id != current["doctor_id"] or target_date != current["appointment_date"] or target_slot != current["time_slot"]):
        collision = conn.execute("""
            SELECT id FROM appointments 
            WHERE doctor_id = ? AND appointment_date = ? AND time_slot = ? 
              AND status != 'cancelled' AND id != ?;
        """, (target_doctor_id, target_date, target_slot, appointment_id)).fetchone()
        if collision:
            conn.close()
            return {"success": False, "error": "مطلوبہ وقت پہلے سے بک ہو چکا ہے۔ برائے مہربانی کوئی دوسرا وقت منتخب کریں۔"}

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("""
        UPDATE appointments SET
            patient_name = COALESCE(?, patient_name),
            patient_phone = COALESCE(?, patient_phone),
            doctor_id = ?,
            appointment_date = ?,
            time_slot = ?,
            reason = COALESCE(?, reason),
            status = COALESCE(?, status),
            updated_at = ?
        WHERE id = ?;
    """, (
        patient_name.strip() if patient_name else None,
        patient_phone.strip() if patient_phone else None,
        target_doctor_id,
        target_date,
        target_slot,
        reason.strip() if reason else None,
        status,
        now_str,
        appointment_id
    ))
    conn.commit()

    updated_row = conn.execute("""
        SELECT a.*, d.name as doctor_name, d.name_en as doctor_name_en, d.specialty as doctor_specialty,
               d.room_number, d.consultation_fee
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.id
        WHERE a.id = ?;
    """, (appointment_id,)).fetchone()
    conn.close()

    return {"success": True, "appointment": dict(updated_row), "message": "اپائنٹمنٹ کی تفصیلات کامیابی سے اپڈیٹ ہو گئیں۔"}

def cancel_appointment(identifier: str) -> Dict[str, Any]:
    """Cancels an appointment by ID, appointment number, or patient phone number."""
    conn = get_db_connection()
    row = conn.execute("""
        SELECT a.*, d.name as doctor_name, d.name_en as doctor_name_en 
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.id
        WHERE (a.id = ? OR a.appointment_number = ? OR a.patient_phone = ?) AND a.status != 'cancelled'
        ORDER BY a.id DESC LIMIT 1;
    """, (identifier, identifier, identifier)).fetchone()

    if not row:
        conn.close()
        return {"success": False, "error": "کوئی فعال اپائنٹمنٹ نہیں ملا (No active appointment found)."}

    apt_id = row["id"]
    apt_num = row["appointment_number"]
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn.execute("UPDATE appointments SET status = 'cancelled', updated_at = ? WHERE id = ?;", (now_str, apt_id))
    conn.commit()
    conn.close()

    return {
        "success": True,
        "appointment_number": apt_num,
        "message": f"اپائنٹمنٹ نمبر {apt_num} منسوخ (Cancel) کر دیا گیا ہے۔"
    }

def get_dashboard_stats() -> Dict[str, Any]:
    """Returns overview counts for the dashboard cards."""
    conn = get_db_connection()
    today_str = date.today().strftime("%Y-%m-%d")

    total_doctors = conn.execute("SELECT COUNT(*) FROM doctors;").fetchone()[0]
    total_appointments = conn.execute("SELECT COUNT(*) FROM appointments;").fetchone()[0]
    today_appointments = conn.execute("SELECT COUNT(*) FROM appointments WHERE appointment_date = ? AND status != 'cancelled';", (today_str,)).fetchone()[0]
    confirmed_appointments = conn.execute("SELECT COUNT(*) FROM appointments WHERE status = 'confirmed';").fetchone()[0]
    cancelled_appointments = conn.execute("SELECT COUNT(*) FROM appointments WHERE status = 'cancelled';").fetchone()[0]
    completed_appointments = conn.execute("SELECT COUNT(*) FROM appointments WHERE status = 'completed';").fetchone()[0]
    conn.close()

    return {
        "total_doctors": total_doctors,
        "total_appointments": total_appointments,
        "today_appointments": today_appointments,
        "confirmed_appointments": confirmed_appointments,
        "cancelled_appointments": cancelled_appointments,
        "completed_appointments": completed_appointments
    }
