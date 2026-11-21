import json
import logging
from datetime import date, datetime, timedelta
from typing import Dict, Any, Optional
import database

logger = logging.getLogger("hospital-voice-tools")

# ==============================================================================
# Tool Schemas for Groq (OpenAI Function Calling Format)
# ==============================================================================

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "list_doctors",
            "description": "Get the list of all available doctors in Shifa Hospital with their specialties, consultation fees, rooms, and working days.",
            "parameters": {
                "type": "object",
                "properties": {
                    "specialty": {
                        "type": "string",
                        "description": "Optional specialty filter, e.g., 'Cardiology', 'Pediatrics', 'Orthopedics', 'General Physician', 'Gynecology' or Urdu terms."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_doctor_availability",
            "description": "Check a specific doctor's working schedule, available OPD hours, and open/booked appointment slots for a given date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_name": {
                        "type": "string",
                        "description": "Doctor's name or specialty (e.g. 'Dr. Tariq', 'ڈاکٹر فاطمہ', 'Cardiologist')."
                    },
                    "date": {
                        "type": "string",
                        "description": "Target date in YYYY-MM-DD format, or words like 'today', 'tomorrow', 'آج', 'کل'."
                    }
                },
                "required": ["doctor_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book a confirmed hospital appointment for a patient after checking available slots.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {
                        "type": "string",
                        "description": "Full name of the patient (e.g. 'احمد علی')."
                    },
                    "patient_phone": {
                        "type": "string",
                        "description": "Contact phone number of the patient (e.g. '03001234567')."
                    },
                    "doctor_name": {
                        "type": "string",
                        "description": "Name or ID of the doctor (e.g. 'Dr. Tariq Mahmood' or 'ڈاکٹر طارق')."
                    },
                    "appointment_date": {
                        "type": "string",
                        "description": "Appointment date in YYYY-MM-DD format (or 'today', 'tomorrow')."
                    },
                    "time_slot": {
                        "type": "string",
                        "description": "Preferred time slot (e.g. '10:30 AM', '11:00 AM', '04:30 PM')."
                    },
                    "reason": {
                        "type": "string",
                        "description": "Brief medical reason or symptoms for the visit (e.g. 'چیک اپ', 'سینے میں درد', 'بخار')."
                    }
                },
                "required": ["patient_name", "patient_phone", "doctor_name", "appointment_date", "time_slot"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_patient_appointments",
            "description": "Search and retrieve existing appointments using a patient's phone number or appointment number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "Patient phone number (e.g. '03001234567') or appointment number (e.g. 'APT-1001')."
                    }
                },
                "required": ["identifier"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_appointment",
            "description": "Reschedule an existing appointment to a new date and time slot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "Appointment number (e.g. 'APT-1001') or patient phone number."
                    },
                    "new_date": {
                        "type": "string",
                        "description": "New target appointment date in YYYY-MM-DD format (or 'today', 'tomorrow')."
                    },
                    "new_time_slot": {
                        "type": "string",
                        "description": "New time slot (e.g. '11:30 AM')."
                    }
                },
                "required": ["identifier", "new_date", "new_time_slot"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancel an active hospital appointment by appointment number or patient phone number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "Appointment number (e.g. 'APT-1001') or patient phone number."
                    },
                    "reason": {
                        "type": "string",
                        "description": "Optional cancellation reason."
                    }
                },
                "required": ["identifier"]
            }
        }
    }
]

# ==============================================================================
# Helper to resolve relative date words
# ==============================================================================

def resolve_date_str(date_input: Optional[str]) -> str:
    """Resolves relative date words like 'today', 'tomorrow', 'آج', 'کل' to YYYY-MM-DD."""
    if not date_input:
        return date.today().strftime("%Y-%m-%d")

    clean = date_input.strip().lower()
    if clean in ("today", "آج", "now"):
        return date.today().strftime("%Y-%m-%d")
    elif clean in ("tomorrow", "کل", "اگلے دن"):
        return (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    elif clean in ("day after tomorrow", "پرسوں"):
        return (date.today() + timedelta(days=2)).strftime("%Y-%m-%d")

    # If already YYYY-MM-DD or standard parseable
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            d = datetime.strptime(clean, fmt).date()
            return d.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return clean

# ==============================================================================
# Tool Execution Dispatcher
# ==============================================================================

def execute_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Executes the appropriate database tool and returns a structured response."""
    logger.info("⚡ Executing Tool: %s with args: %s", name, arguments)

    try:
        if name == "list_doctors":
            specialty = arguments.get("specialty")
            doctors = database.get_all_doctors()
            if specialty:
                spec_clean = specialty.strip().lower()
                doctors = [
                    d for d in doctors 
                    if spec_clean in d["specialty"].lower() or spec_clean in d["specialty_en"].lower()
                ]
            formatted_doctors = [
                {
                    "id": d["id"],
                    "name": d["name"],
                    "name_en": d["name_en"],
                    "specialty": d["specialty"],
                    "room": d["room_number"],
                    "fee": f"Rs. {d['consultation_fee']}",
                    "days": d["available_days"],
                    "hours": f"{d['start_time']} to {d['end_time']}"
                }
                for d in doctors
            ]
            return {
                "status": "success",
                "count": len(formatted_doctors),
                "doctors": formatted_doctors
            }

        elif name == "check_doctor_availability":
            doctor_query = arguments.get("doctor_name", "")
            target_date = resolve_date_str(arguments.get("date"))

            doctor = database.find_doctor_by_query(doctor_query)
            if not doctor:
                return {
                    "status": "error",
                    "message": f"ڈاکٹر '{doctor_query}' نہیں ملے۔ کیا آپ فہرست میں سے کوئی دوسرا ڈاکٹر منتخب کرنا چاہیں گے؟"
                }

            availability = database.get_doctor_availability_and_slots(doctor["id"], target_date)
            if not availability.get("is_working_day", True):
                return {
                    "status": "not_working_day",
                    "doctor_name": doctor["name"],
                    "date": target_date,
                    "day_of_week": availability.get("day_of_week"),
                    "message": availability.get("message")
                }

            # Filter only available slots for clean speech response
            open_slots = [s["slot"] for s in availability.get("slots", []) if s["available"]]
            return {
                "status": "success",
                "doctor_name": doctor["name"],
                "doctor_name_en": doctor["name_en"],
                "specialty": doctor["specialty"],
                "room": doctor["room_number"],
                "fee": f"Rs. {doctor['consultation_fee']}",
                "date": target_date,
                "day_of_week": availability.get("day_of_week"),
                "total_available_slots": len(open_slots),
                "available_slots": open_slots,
                "message": f"{doctor['name']} کے لیے {target_date} کو {len(open_slots)} سلاٹ دستیاب ہیں: {', '.join(open_slots[:5])}"
            }

        elif name == "book_appointment":
            patient_name = arguments.get("patient_name", "").strip()
            patient_phone = arguments.get("patient_phone", "").strip()
            doctor_name = arguments.get("doctor_name", "").strip()
            target_date = resolve_date_str(arguments.get("appointment_date"))
            time_slot = arguments.get("time_slot", "").strip()
            reason = arguments.get("reason", "General Consultation")

            doctor = database.find_doctor_by_query(doctor_name)
            if not doctor:
                return {
                    "status": "error",
                    "message": f"ڈاکٹر '{doctor_name}' کا ریکارڈ نہیں ملا۔ برائے مہربانی درست نام بتائیں۔"
                }

            result = database.create_appointment(
                patient_name=patient_name,
                patient_phone=patient_phone,
                doctor_id=doctor["id"],
                appointment_date=target_date,
                time_slot=time_slot,
                reason=reason
            )

            if not result.get("success"):
                return {
                    "status": "slot_unavailable",
                    "error": result.get("error"),
                    "message": result.get("error")
                }

            apt = result["appointment"]
            return {
                "status": "confirmed",
                "appointment_number": apt["appointment_number"],
                "patient_name": apt["patient_name"],
                "doctor_name": apt["doctor_name"],
                "date": apt["appointment_date"],
                "time_slot": apt["time_slot"],
                "room": apt["room_number"],
                "fee": f"Rs. {apt['consultation_fee']}",
                "message": f"اپائنٹمنٹ کامیابی سے بک ہو گیا۔ اپائنٹمنٹ نمبر {apt['appointment_number']} ہے۔ وقت: {apt['time_slot']}، تاریخ: {apt['appointment_date']}، ڈاکٹر: {apt['doctor_name']}، کمرہ: {apt['room_number']}۔"
            }

        elif name == "get_patient_appointments":
            identifier = arguments.get("identifier", "").strip()
            apt = database.get_appointment_by_id_or_number(identifier)
            if not apt:
                # Also try searching list
                apts = database.get_all_appointments(search=identifier)
                if apts:
                    return {
                        "status": "success",
                        "found": len(apts),
                        "appointments": [
                            {
                                "number": a["appointment_number"],
                                "patient": a["patient_name"],
                                "doctor": a["doctor_name"],
                                "date": a["appointment_date"],
                                "time": a["time_slot"],
                                "status": a["status"]
                            }
                            for a in apts
                        ]
                    }
                return {
                    "status": "not_found",
                    "message": f"فون نمبر یا اپائنٹمنٹ نمبر '{identifier}' کے لیے کوئی ریکارڈ نہیں ملا۔"
                }

            return {
                "status": "success",
                "appointment": {
                    "number": apt["appointment_number"],
                    "patient": apt["patient_name"],
                    "phone": apt["patient_phone"],
                    "doctor": apt["doctor_name"],
                    "specialty": apt["doctor_specialty"],
                    "room": apt["room_number"],
                    "date": apt["appointment_date"],
                    "time": apt["time_slot"],
                    "status": apt["status"]
                },
                "message": f"اپائنٹمنٹ نمبر {apt['appointment_number']} مل گیا ہے۔ مریض: {apt['patient_name']}، ڈاکٹر: {apt['doctor_name']}، تاریخ: {apt['appointment_date']}، وقت: {apt['time_slot']}، اسٹیٹس: {apt['status']}۔"
            }

        elif name == "reschedule_appointment":
            identifier = arguments.get("identifier", "").strip()
            new_date = resolve_date_str(arguments.get("new_date"))
            new_slot = arguments.get("new_time_slot", "").strip()

            apt = database.get_appointment_by_id_or_number(identifier)
            if not apt:
                return {
                    "status": "error",
                    "message": f"اپائنٹمنٹ '{identifier}' نہیں ملا۔"
                }

            update_res = database.update_appointment(
                appointment_id=apt["id"],
                appointment_date=new_date,
                time_slot=new_slot,
                status="rescheduled"
            )

            if not update_res.get("success"):
                return {
                    "status": "error",
                    "message": update_res.get("error")
                }

            updated_apt = update_res["appointment"]
            return {
                "status": "success",
                "appointment_number": updated_apt["appointment_number"],
                "doctor": updated_apt["doctor_name"],
                "new_date": updated_apt["appointment_date"],
                "new_time": updated_apt["time_slot"],
                "message": f"اپائنٹمنٹ نمبر {updated_apt['appointment_number']} نئی تاریخ {updated_apt['appointment_date']} اور وقت {updated_apt['time_slot']} کے لیے ری شیڈول (تبدیل) کر دیا گیا ہے۔"
            }

        elif name == "cancel_appointment":
            identifier = arguments.get("identifier", "").strip()
            cancel_res = database.cancel_appointment(identifier)
            return cancel_res

        else:
            return {"status": "error", "message": f"Unknown tool: {name}"}

    except Exception as e:
        logger.error("Error executing tool %s: %s", name, e, exc_info=True)
        return {"status": "error", "message": f"Tool execution error: {str(e)}"}
