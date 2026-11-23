import sqlite3
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional

DB_PATH = Path(__file__).resolve().parent / "hospital.db"

def get_connection() -> sqlite3.Connection:
    """Returns a SQLite connection with dict-like row access."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def init_db():
    """Initializes tables and seeds initial doctors, slots, and appointments."""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Doctors Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS doctors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        specialty TEXT NOT NULL,
        department TEXT NOT NULL,
        fee_pkr INTEGER NOT NULL,
        experience_years INTEGER NOT NULL,
        bio TEXT NOT NULL
    );
    """)

    # 2. Slots Table (today + next 3 days)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS slots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doctor_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        start_time TEXT NOT NULL,
        is_booked INTEGER DEFAULT 0,
        FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE,
        UNIQUE (doctor_id, date, start_time)
    );
    """)

    # 3. Appointments Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_reference TEXT UNIQUE NOT NULL,
        patient_name TEXT NOT NULL,
        patient_phone TEXT NOT NULL,
        doctor_id INTEGER NOT NULL,
        slot_id INTEGER,
        reason TEXT DEFAULT 'General Consultation',
        status TEXT DEFAULT 'confirmed',
        created_at TEXT NOT NULL,
        FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE,
        FOREIGN KEY (slot_id) REFERENCES slots(id) ON DELETE SET NULL
    );
    """)

    # Seed Doctors if empty
    cursor.execute("SELECT COUNT(*) FROM doctors;")
    if cursor.fetchone()[0] == 0:
        seed_doctors = [
            (
                "Dr. Ayesha Khan",
                "Cardiologist",
                "Cardiology",
                2500,
                12,
                "Senior Consultant Cardiologist specializing in heart disease, hypertension, and ECG diagnosis."
            ),
            (
                "Dr. Bilal Ahmed",
                "Dermatologist",
                "Dermatology",
                2000,
                8,
                "Clinical dermatologist specializing in acne, eczema, hair loss, and skin rejuvenation."
            ),
            (
                "Dr. Sara Tariq",
                "Pediatrician",
                "Pediatrics",
                1800,
                10,
                "Dedicated child healthcare specialist focusing on pediatric wellness, vaccines, and infections."
            ),
            (
                "Dr. Usman Malik",
                "Orthopedic Surgeon",
                "Orthopedics",
                2200,
                15,
                "Experienced orthopedic surgeon specializing in joint replacement, back pain, and bone fractures."
            ),
            (
                "Dr. Hina Raza",
                "General Physician",
                "General Medicine",
                1200,
                7,
                "Primary healthcare consultant treating fevers, seasonal infections, diabetes, and blood pressure."
            )
        ]
        cursor.executemany("""
        INSERT INTO doctors (name, specialty, department, fee_pkr, experience_years, bio)
        VALUES (?, ?, ?, ?, ?, ?);
        """, seed_doctors)
        conn.commit()

    # Generate slots for today + next 3 days dynamically on startup
    seed_dynamic_slots(cursor)

    # Seed initial sample appointments if empty
    cursor.execute("SELECT COUNT(*) FROM appointments;")
    if cursor.fetchone()[0] == 0:
        seed_sample_appointments(cursor)

    conn.commit()
    conn.close()

def get_slot_time_list() -> List[str]:
    return [
        "09:00 AM", "09:30 AM", "10:00 AM", "10:30 AM",
        "11:00 AM", "11:30 AM", "03:00 PM", "03:30 PM",
        "04:00 PM", "04:30 PM", "05:00 PM"
    ]

def seed_dynamic_slots(cursor: sqlite3.Cursor):
    """Ensures slots exist for today and the next 3 days for every doctor."""
    cursor.execute("SELECT id FROM doctors;")
    doc_ids = [r[0] for r in cursor.fetchall()]

    today = date.today()
    dates_to_seed = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(4)]
    slot_times = get_slot_time_list()

    for doc_id in doc_ids:
        for d_str in dates_to_seed:
            for s_time in slot_times:
                cursor.execute("""
                INSERT OR IGNORE INTO slots (doctor_id, date, start_time, is_booked)
                VALUES (?, ?, ?, 0);
                """, (doc_id, d_str, s_time))

def seed_sample_appointments(cursor: sqlite3.Cursor):
    """Inserts realistic initial appointments and marks their slots booked."""
    today_str = date.today().strftime("%Y-%m-%d")
    tomorrow_str = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    samples = [
        ("APT-1041", "Tariq Mahmood", "03001234567", 1, today_str, "10:00 AM", "Chest tightness & routine checkup"),
        ("APT-1042", "Zainab Bibi", "03215556677", 2, today_str, "03:30 PM", "Severe skin rash on arms"),
        ("APT-1043", "Hamza Ali", "03338889900", 3, tomorrow_str, "11:00 AM", "Child fever and throat irritation"),
        ("APT-1044", "Kamran Javed", "03457771122", 4, today_str, "04:00 PM", "Knee joint pain after exercise"),
    ]

    for ref, p_name, p_phone, doc_id, apt_date, s_time, reason in samples:
        # Find matching slot
        cursor.execute("""
        SELECT id FROM slots WHERE doctor_id = ? AND date = ? AND start_time = ?;
        """, (doc_id, apt_date, s_time))
        slot_row = cursor.fetchone()
        slot_id = slot_row[0] if slot_row else None

        if slot_id:
            cursor.execute("UPDATE slots SET is_booked = 1 WHERE id = ?;", (slot_id,))

        cursor.execute("""
        INSERT INTO appointments (booking_reference, patient_name, patient_phone, doctor_id, slot_id, reason, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'confirmed', ?);
        """, (ref, p_name, p_phone, doc_id, slot_id, reason, now_str))

# Initialize database schema immediately
init_db()

# ==============================================================================
# Helper Date Resolver
# ==============================================================================
def resolve_date_input(date_str: Optional[str]) -> str:
    """Converts 'today', 'tomorrow', 'کل', 'آج' or returns normalized YYYY-MM-DD."""
    if not date_str:
        return date.today().strftime("%Y-%m-%d")
    clean = date_str.strip().lower()
    if clean in ("today", "آج", "now"):
        return date.today().strftime("%Y-%m-%d")
    elif clean in ("tomorrow", "کل"):
        return (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    elif clean in ("day after tomorrow", "پرسوں"):
        return (date.today() + timedelta(days=2)).strftime("%Y-%m-%d")

    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(clean, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date.today().strftime("%Y-%m-%d")

def generate_booking_reference() -> str:
    """Generates unique reference code like APT-1045."""
    conn = get_connection()
    row = conn.execute("SELECT booking_reference FROM appointments ORDER BY id DESC LIMIT 1;").fetchone()
    conn.close()
    if row and row["booking_reference"].startswith("APT-"):
        try:
            num = int(row["booking_reference"].split("-")[1])
            return f"APT-{num + 1}"
        except Exception:
            pass
    return "APT-1045"

# ==============================================================================
# Doctor & Slot Queries
# ==============================================================================
def find_doctor_by_name(query: str) -> Optional[Dict[str, Any]]:
    """Finds doctor by name, specialty, or partial match."""
    q = query.strip().lower()
    conn = get_connection()
    doctors = [dict(r) for r in conn.execute("SELECT * FROM doctors;").fetchall()]
    conn.close()

    # Match ID
    if q.isdigit():
        for d in doctors:
            if d["id"] == int(q):
                return d

    # Substring in name, specialty, or department
    for d in doctors:
        if q in d["name"].lower() or q in d["specialty"].lower() or q in d["department"].lower():
            return d

    # Token match (e.g. 'ayesha', 'bilal', 'sara', 'usman', 'hina', 'cardio', 'skin')
    tokens = [t for t in q.replace("dr.", "").replace("dr", "").split() if len(t) > 2]
    for d in doctors:
        for t in tokens:
            if t in d["name"].lower() or t in d["specialty"].lower():
                return d

    return None

def get_all_doctors_with_slots(specialty: Optional[str] = None, target_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns all doctors with their slots grouped by date."""
    conn = get_connection()
    query = "SELECT * FROM doctors"
    params = []
    if specialty and specialty.strip().lower() != "all":
        query += " WHERE LOWER(specialty) LIKE ? OR LOWER(department) LIKE ?"
        params.extend([f"%{specialty.lower()}%", f"%{specialty.lower()}%"])
    query += " ORDER BY id ASC;"

    doctors = [dict(r) for r in conn.execute(query, params).fetchall()]

    today = date.today()
    valid_dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(4)]
    if target_date and target_date in valid_dates:
        dates_to_fetch = [target_date]
    else:
        dates_to_fetch = valid_dates

    results = []
    for doc in doctors:
        # Fetch slots for these dates
        slots_rows = conn.execute("""
            SELECT id, doctor_id, date, start_time, is_booked
            FROM slots
            WHERE doctor_id = ? AND date IN ({})
            ORDER BY date ASC, id ASC;
        """.format(",".join("?" * len(dates_to_fetch))), [doc["id"]] + dates_to_fetch).fetchall()

        slots_by_date = {d: [] for d in dates_to_fetch}
        available_count = 0

        for r in slots_rows:
            slot_dict = {
                "id": r["id"],
                "doctor_id": r["doctor_id"],
                "date": r["date"],
                "start_time": r["start_time"],
                "is_booked": bool(r["is_booked"])
            }
            slots_by_date[r["date"]].append(slot_dict)
            if not r["is_booked"]:
                available_count += 1

        doc_copy = dict(doc)
        doc_copy["slots_by_date"] = slots_by_date
        doc_copy["total_available_slots"] = available_count
        results.append(doc_copy)

    conn.close()
    return results

# ==============================================================================
# Agentic Tool Functions
# ==============================================================================
def tool_list_doctors(specialty: Optional[str] = None) -> Dict[str, Any]:
    """Lists doctors in hospital with their specialties, departments, and consultation fees."""
    conn = get_connection()
    if specialty:
        s = f"%{specialty.lower()}%"
        rows = conn.execute("SELECT * FROM doctors WHERE LOWER(specialty) LIKE ? OR LOWER(department) LIKE ?;", (s, s)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM doctors ORDER BY id ASC;").fetchall()
    conn.close()

    docs = []
    for r in rows:
        docs.append({
            "id": r["id"],
            "name": r["name"],
            "specialty": r["specialty"],
            "department": r["department"],
            "fee_pkr": r["fee_pkr"],
            "experience_years": r["experience_years"],
            "bio": r["bio"]
        })
    return {
        "status": "success",
        "count": len(docs),
        "doctors": docs
    }

def tool_get_doctor_availability(doctor_name: str, target_date: Optional[str] = None) -> Dict[str, Any]:
    """Queries slots table for available/unbooked timeslots for a doctor on a given date."""
    doc = find_doctor_by_name(doctor_name)
    if not doc:
        return {
            "status": "error",
            "message": f"ڈاکٹر '{doctor_name}' کا ریکارڈ نہیں ملا۔ برائے مہربانی دستیاب ڈاکٹروں میں سے منتخب کریں۔"
        }

    date_str = resolve_date_input(target_date)
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, start_time, is_booked
        FROM slots
        WHERE doctor_id = ? AND date = ?
        ORDER BY id ASC;
    """, (doc["id"], date_str)).fetchall()
    conn.close()

    if not rows:
        return {
            "status": "no_slots",
            "doctor": doc["name"],
            "date": date_str,
            "message": f"تاریخ {date_str} کے لیے کوئی سلاٹس دستیاب نہیں ہیں۔"
        }

    open_slots = [r["start_time"] for r in rows if not r["is_booked"]]
    booked_slots = [r["start_time"] for r in rows if r["is_booked"]]

    return {
        "status": "success",
        "doctor_name": doc["name"],
        "specialty": doc["specialty"],
        "fee_pkr": doc["fee_pkr"],
        "date": date_str,
        "available_slots_count": len(open_slots),
        "available_slots": open_slots,
        "booked_slots_count": len(booked_slots),
        "message": f"{doc['name']} ({doc['specialty']}) کے پاس {date_str} کو {len(open_slots)} خالی سلاٹس ہیں: {', '.join(open_slots[:4])}"
    }

def tool_book_appointment(
    doctor_name: str,
    date_str: str,
    time_slot: str,
    patient_name: str,
    patient_phone: str,
    reason: Optional[str] = "General Consultation"
) -> Dict[str, Any]:
    """Books an appointment by marking the slot is_booked=1 and inserting an appointment record."""
    doc = find_doctor_by_name(doctor_name)
    if not doc:
        return {"status": "error", "message": f"ڈاکٹر '{doctor_name}' کا ریکارڈ نہیں ملا۔"}

    norm_date = resolve_date_input(date_str)
    # Clean time format e.g. '10:00 AM'
    clean_time = time_slot.strip().upper()

    conn = get_connection()
    cursor = conn.cursor()

    # Find matching slot
    slot_row = cursor.execute("""
        SELECT id, is_booked FROM slots 
        WHERE doctor_id = ? AND date = ? AND (start_time LIKE ? OR start_time = ?)
    """, (doc["id"], norm_date, f"%{clean_time}%", clean_time)).fetchone()

    if not slot_row:
        conn.close()
        return {
            "status": "error",
            "message": f"مطلوبہ وقت ({clean_time}) تاریخ {norm_date} پر شیڈول میں نہیں ہے۔"
        }

    slot_id = slot_row["id"]
    if slot_row["is_booked"]:
        conn.close()
        return {
            "status": "already_booked",
            "message": f"یہ وقت ({clean_time}) پہلے سے بک ہے۔ برائے مہربانی کوئی دوسرا وقت منتخب کریں۔"
        }

    # Reserve the slot
    cursor.execute("UPDATE slots SET is_booked = 1 WHERE id = ?;", (slot_id,))

    booking_ref = generate_booking_reference()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
    INSERT INTO appointments (booking_reference, patient_name, patient_phone, doctor_id, slot_id, reason, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?, 'confirmed', ?);
    """, (booking_ref, patient_name.strip(), patient_phone.strip(), doc["id"], slot_id, reason.strip() if reason else "Consultation", now_str))

    apt_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "status": "confirmed",
        "appointment_id": apt_id,
        "booking_reference": booking_ref,
        "patient_name": patient_name,
        "patient_phone": patient_phone,
        "doctor_name": doc["name"],
        "specialty": doc["specialty"],
        "date": norm_date,
        "time_slot": clean_time,
        "fee_pkr": doc["fee_pkr"],
        "message": f"آپ کا اپائنٹمنٹ کامیابی سے بک ہو گیا ہے۔ آپ کا بکنگ ریفرنس نمبر {booking_ref} ہے۔ ڈاکٹر: {doc['name']}، تاریخ: {norm_date}، وقت: {clean_time}۔"
    }

def tool_check_appointment(patient_phone: Optional[str] = None, booking_reference: Optional[str] = None) -> Dict[str, Any]:
    """Looks up existing appointment details."""
    conn = get_connection()
    query = """
        SELECT a.*, d.name as doctor_name, d.specialty, d.fee_pkr, s.date as appointment_date, s.start_time as time_slot
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.id
        LEFT JOIN slots s ON a.slot_id = s.id
        WHERE 1=1
    """
    params = []
    if booking_reference:
        query += " AND a.booking_reference = ?"
        params.append(booking_reference.strip().upper())
    elif patient_phone:
        clean_num = "".join(c for c in patient_phone if c.isdigit())
        if len(clean_num) >= 9:
            last_9 = clean_num[-9:]
            query += " AND (a.patient_phone LIKE ? OR a.patient_phone LIKE ?)"
            params.extend([f"%{patient_phone.strip()}%", f"%{last_9}%"])
        else:
            query += " AND a.patient_phone LIKE ?"
            params.append(f"%{patient_phone.strip()}%")
    else:
        conn.close()
        return {"status": "error", "message": "فون نمبر یا بکنگ ریفرنس بتائیں۔"}

    query += " ORDER BY a.id DESC LIMIT 3;"
    rows = [dict(r) for r in conn.execute(query, params).fetchall()]
    conn.close()

    if not rows:
        return {"status": "not_found", "message": "کوئی اپائنٹمنٹ ریکارڈ نہیں ملا۔"}

    return {
        "status": "success",
        "count": len(rows),
        "appointments": rows,
        "message": f"اپائنٹمنٹ {rows[0]['booking_reference']} برائے {rows[0]['patient_name']} مل گیا۔ ڈاکٹر: {rows[0]['doctor_name']}، تاریخ: {rows[0]['appointment_date']}، وقت: {rows[0]['time_slot']}، اسٹیٹس: {rows[0]['status']}۔"
    }

def tool_reschedule_appointment(booking_reference: str, new_date: str, new_time_slot: str) -> Dict[str, Any]:
    """Frees the old slot, reserves the new slot, and updates the appointment record."""
    ref = booking_reference.strip().upper()
    norm_new_date = resolve_date_input(new_date)
    clean_new_slot = new_time_slot.strip().upper()

    conn = get_connection()
    cursor = conn.cursor()

    apt_row = cursor.execute("SELECT * FROM appointments WHERE booking_reference = ?;", (ref,)).fetchone()
    if not apt_row:
        conn.close()
        return {"status": "error", "message": f"اپائنٹمنٹ ریفرنس '{ref}' نہیں ملا۔"}

    old_slot_id = apt_row["slot_id"]
    doc_id = apt_row["doctor_id"]

    # Check new slot
    new_slot_row = cursor.execute("""
        SELECT id, is_booked FROM slots
        WHERE doctor_id = ? AND date = ? AND (start_time LIKE ? OR start_time = ?);
    """, (doc_id, norm_new_date, f"%{clean_new_slot}%", clean_new_slot)).fetchone()

    if not new_slot_row:
        conn.close()
        return {"status": "error", "message": f"مطلوبہ نئی تاریخ یا وقت دستیاب نہیں ہے۔"}

    if new_slot_row["is_booked"] and new_slot_row["id"] != old_slot_id:
        conn.close()
        return {"status": "already_booked", "message": "یہ نیا وقت پہلے سے بک ہو چکا ہے۔ کوئی دوسرا وقت بتائیں۔"}

    # Free old slot
    if old_slot_id:
        cursor.execute("UPDATE slots SET is_booked = 0 WHERE id = ?;", (old_slot_id,))

    # Book new slot
    new_slot_id = new_slot_row["id"]
    cursor.execute("UPDATE slots SET is_booked = 1 WHERE id = ?;", (new_slot_id,))

    # Update appointment
    cursor.execute("""
        UPDATE appointments 
        SET slot_id = ?, status = 'rescheduled'
        WHERE id = ?;
    """, (new_slot_id, apt_row["id"]))

    conn.commit()
    conn.close()

    return {
        "status": "rescheduled",
        "booking_reference": ref,
        "new_date": norm_new_date,
        "new_time": clean_new_slot,
        "message": f"آپ کا اپائنٹمنٹ {ref} کامیابی سے تبدیل کر دیا گیا ہے۔ نئی تاریخ: {norm_new_date}، وقت: {clean_new_slot}۔"
    }

def tool_cancel_appointment(booking_reference: str) -> Dict[str, Any]:
    """Marks appointment cancelled and frees the booked slot."""
    ref = booking_reference.strip().upper()
    conn = get_connection()
    cursor = conn.cursor()

    apt_row = cursor.execute("SELECT * FROM appointments WHERE booking_reference = ? OR patient_phone = ?;", (ref, ref)).fetchone()
    if not apt_row:
        conn.close()
        return {"status": "error", "message": f"اپائنٹمنٹ '{ref}' نہیں ملا۔"}

    if apt_row["status"] == "cancelled":
        conn.close()
        return {"status": "already_cancelled", "message": f"اپائنٹمنٹ {apt_row['booking_reference']} پہلے سے منسوخ ہے۔"}

    slot_id = apt_row["slot_id"]
    if slot_id:
        cursor.execute("UPDATE slots SET is_booked = 0 WHERE id = ?;", (slot_id,))

    cursor.execute("UPDATE appointments SET status = 'cancelled' WHERE id = ?;", (apt_row["id"],))
    conn.commit()
    conn.close()

    return {
        "status": "cancelled",
        "booking_reference": apt_row["booking_reference"],
        "message": f"اپائنٹمنٹ نمبر {apt_row['booking_reference']} کامیابی سے منسوخ (Cancel) کر دیا گیا ہے۔"
    }

# ==============================================================================
# Appointments Table Queries (For Dashboard)
# ==============================================================================
def get_all_appointments(
    search: Optional[str] = None,
    doctor_id: Optional[int] = None,
    status: Optional[str] = None,
    target_date: Optional[str] = None
) -> List[Dict[str, Any]]:
    conn = get_connection()
    query = """
        SELECT a.id, a.booking_reference, a.patient_name, a.patient_phone, a.doctor_id,
               d.name as doctor_name, d.specialty, d.department, d.fee_pkr,
               a.slot_id, COALESCE(s.date, '') as appointment_date, COALESCE(s.start_time, '') as time_slot,
               a.reason, a.status, a.created_at
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.id
        LEFT JOIN slots s ON a.slot_id = s.id
        WHERE 1=1
    """
    params = []
    if search:
        s = f"%{search.strip()}%"
        query += " AND (a.patient_name LIKE ? OR a.patient_phone LIKE ? OR a.booking_reference LIKE ?)"
        params.extend([s, s, s])

    if doctor_id:
        query += " AND a.doctor_id = ?"
        params.append(doctor_id)

    if status and status.lower() != "all":
        query += " AND a.status = ?"
        params.append(status.lower())

    if target_date:
        query += " AND s.date = ?"
        params.append(target_date)

    query += " ORDER BY a.id DESC;"
    rows = [dict(r) for r in conn.execute(query, params).fetchall()]
    conn.close()
    return rows

def get_dashboard_stats() -> Dict[str, Any]:
    conn = get_connection()
    today_str = date.today().strftime("%Y-%m-%d")

    total_doctors = conn.execute("SELECT COUNT(*) FROM doctors;").fetchone()[0]
    total_appointments = conn.execute("SELECT COUNT(*) FROM appointments;").fetchone()[0]
    today_appointments = conn.execute("""
        SELECT COUNT(*) FROM appointments a
        LEFT JOIN slots s ON a.slot_id = s.id
        WHERE s.date = ? AND a.status != 'cancelled';
    """, (today_str,)).fetchone()[0]
    confirmed_appointments = conn.execute("SELECT COUNT(*) FROM appointments WHERE status = 'confirmed';").fetchone()[0]
    cancelled_appointments = conn.execute("SELECT COUNT(*) FROM appointments WHERE status = 'cancelled';").fetchone()[0]
    conn.close()

    return {
        "total_doctors": total_doctors,
        "total_appointments": total_appointments,
        "today_appointments": today_appointments,
        "confirmed_appointments": confirmed_appointments,
        "cancelled_appointments": cancelled_appointments
    }
