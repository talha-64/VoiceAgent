import json
import logging
from typing import Dict, Any, Optional
import database

logger = logging.getLogger("hospital-voice-tools")

# ==============================================================================
# Groq & OpenAI Compatible Function Calling Tool Schemas
# ==============================================================================

GROQ_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_doctors",
            "description": "Lists available hospital doctors with their specialties, departments, consultation fees, and experience.",
            "parameters": {
                "type": "object",
                "properties": {
                    "specialty": {
                        "type": "string",
                        "description": "Optional specialty filter, e.g. 'Cardiologist', 'Dermatologist', 'Pediatrician', 'Orthopedic Surgeon', 'General Physician' or patient symptoms."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_doctor_availability",
            "description": "Queries available (unbooked) time slots for a specific doctor on a given date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_name": {
                        "type": "string",
                        "description": "Name of the doctor (e.g. 'Dr. Ayesha Khan', 'Dr. Bilal Ahmed', 'Sara Tariq', etc.)"
                    },
                    "date": {
                        "type": "string",
                        "description": "Target date: 'today', 'tomorrow', or 'YYYY-MM-DD'."
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
            "description": "Books a hospital appointment for a patient after confirming doctor, date, and available slot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_name": {
                        "type": "string",
                        "description": "Name of the doctor (e.g. 'Dr. Ayesha Khan')."
                    },
                    "date": {
                        "type": "string",
                        "description": "Appointment date: 'today', 'tomorrow', or 'YYYY-MM-DD'."
                    },
                    "time_slot": {
                        "type": "string",
                        "description": "Chosen time slot from available slots (e.g. '10:00 AM', '11:30 AM', '04:00 PM')."
                    },
                    "patient_name": {
                        "type": "string",
                        "description": "Full name of the patient (e.g. 'محمد احمد')."
                    },
                    "patient_phone": {
                        "type": "string",
                        "description": "Patient phone number (e.g. '03001234567')."
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason or medical symptoms for the visit."
                    }
                },
                "required": ["doctor_name", "date", "time_slot", "patient_name", "patient_phone"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_appointment",
            "description": "Checks details of an existing appointment by patient phone number or booking reference code (APT-XXXX).",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_phone": {
                        "type": "string",
                        "description": "Patient phone number."
                    },
                    "booking_reference": {
                        "type": "string",
                        "description": "Booking reference code like 'APT-1041'."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_appointment",
            "description": "Reschedules an existing appointment to a new date and time slot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_reference": {
                        "type": "string",
                        "description": "The booking reference code (e.g. 'APT-1042')."
                    },
                    "new_date": {
                        "type": "string",
                        "description": "New appointment date ('today', 'tomorrow', or 'YYYY-MM-DD')."
                    },
                    "new_time_slot": {
                        "type": "string",
                        "description": "New time slot (e.g. '11:00 AM', '04:30 PM')."
                    }
                },
                "required": ["booking_reference", "new_date", "new_time_slot"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancels an existing appointment using booking reference code or patient phone number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_reference": {
                        "type": "string",
                        "description": "Booking reference code (e.g. 'APT-1042') or patient phone number."
                    }
                },
                "required": ["booking_reference"]
            }
        }
    }
]

# ==============================================================================
# Tool Execution Dispatcher
# ==============================================================================

def execute_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Executes the requested tool and returns structured result."""
    logger.info("Executing Tool: %s with args: %s", name, arguments)
    try:
        if name == "list_doctors":
            return database.tool_list_doctors(specialty=arguments.get("specialty"))

        elif name == "get_doctor_availability":
            return database.tool_get_doctor_availability(
                doctor_name=arguments.get("doctor_name", ""),
                target_date=arguments.get("date")
            )

        elif name == "book_appointment":
            return database.tool_book_appointment(
                doctor_name=arguments.get("doctor_name", ""),
                date_str=arguments.get("date", ""),
                time_slot=arguments.get("time_slot", ""),
                patient_name=arguments.get("patient_name", ""),
                patient_phone=arguments.get("patient_phone", ""),
                reason=arguments.get("reason", "General Consultation")
            )

        elif name == "check_appointment":
            return database.tool_check_appointment(
                patient_phone=arguments.get("patient_phone"),
                booking_reference=arguments.get("booking_reference")
            )

        elif name == "reschedule_appointment":
            return database.tool_reschedule_appointment(
                booking_reference=arguments.get("booking_reference", ""),
                new_date=arguments.get("new_date", ""),
                new_time_slot=arguments.get("new_time_slot", "")
            )

        elif name == "cancel_appointment":
            return database.tool_cancel_appointment(
                booking_reference=arguments.get("booking_reference", "")
            )

        else:
            return {"status": "error", "message": f"Unknown tool: {name}"}

    except Exception as e:
        logger.error("Error executing tool %s: %s", name, e, exc_info=True)
        return {"status": "error", "message": str(e)}
