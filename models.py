from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class DoctorBase(BaseModel):
    name: str
    specialty: str
    department: str
    fee_pkr: int
    experience_years: int
    bio: str

class SlotOut(BaseModel):
    id: int
    doctor_id: int
    date: str
    start_time: str
    is_booked: bool

class DoctorWithSlots(DoctorBase):
    id: int
    slots_by_date: Dict[str, List[SlotOut]] = {}
    total_available_slots: int = 0

class AppointmentBase(BaseModel):
    patient_name: str
    patient_phone: str
    doctor_id: int
    slot_id: Optional[int] = None
    reason: Optional[str] = "General Consultation"

class AppointmentCreate(AppointmentBase):
    date: Optional[str] = None
    time_slot: Optional[str] = None

class AppointmentReschedule(BaseModel):
    new_date: str
    new_time_slot: str

class AppointmentOut(BaseModel):
    id: int
    booking_reference: str
    patient_name: str
    patient_phone: str
    doctor_id: int
    doctor_name: str
    specialty: str
    department: str
    fee_pkr: int
    slot_id: Optional[int]
    appointment_date: str
    time_slot: str
    reason: Optional[str]
    status: str
    created_at: str

class DashboardStats(BaseModel):
    total_doctors: int
    total_appointments: int
    today_appointments: int
    confirmed_appointments: int
    cancelled_appointments: int
