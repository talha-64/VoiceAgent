import React, { useState, useEffect } from 'react';
import { X, Calendar, Clock, User, Phone, FileText, CheckCircle2 } from 'lucide-react';

export default function BookingModal({
  isOpen,
  onClose,
  doctors,
  preselectedDoctorId,
  preselectedDate,
  preselectedSlot,
  onSuccess
}) {
  const [doctorId, setDoctorId] = useState(preselectedDoctorId || '');
  const [selectedDate, setSelectedDate] = useState(preselectedDate || '');
  const [timeSlot, setTimeSlot] = useState(preselectedSlot || '');
  const [patientName, setPatientName] = useState('');
  const [patientPhone, setPatientPhone] = useState('');
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (preselectedDoctorId) setDoctorId(preselectedDoctorId);
    if (preselectedDate) setSelectedDate(preselectedDate);
    if (preselectedSlot) setTimeSlot(preselectedSlot);
  }, [preselectedDoctorId, preselectedDate, preselectedSlot, isOpen]);

  if (!isOpen) return null;

  const currentDoctor = doctors.find(d => String(d.id) === String(doctorId)) || doctors[0];
  const availableSlotsForDate = (currentDoctor?.slots_by_date?.[selectedDate] || [])
    .filter(s => !s.is_booked)
    .map(s => s.start_time);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!doctorId || !selectedDate || !timeSlot || !patientName.trim() || !patientPhone.trim()) {
      setError('Please fill in all required fields (Doctor, Date, Slot, Name, Phone).');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const res = await fetch('/api/appointments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          doctor_id: parseInt(doctorId),
          date: selectedDate,
          time_slot: timeSlot,
          patient_name: patientName.trim(),
          patient_phone: patientPhone.trim(),
          reason: reason.trim() || 'General Consultation'
        })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || data.message || 'Failed to book appointment');
      }

      onSuccess(data);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm">
      <div className="bg-white rounded-xl shadow-xl border border-slate-200 w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/50">
          <div>
            <h3 className="font-semibold text-slate-900 text-base">Book Clinical Appointment</h3>
            <p className="text-xs text-slate-500 mt-0.5">Direct reception override & testing</p>
          </div>
          <button 
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-lg">
              {error}
            </div>
          )}

          {/* Doctor Selection */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Doctor Specialist *
            </label>
            <select
              value={doctorId}
              onChange={(e) => {
                setDoctorId(e.target.value);
                setTimeSlot('');
              }}
              className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-900"
              required
            >
              {doctors.map(d => (
                <option key={d.id} value={d.id}>
                  {d.name} — {d.specialty} (Rs. {d.fee_pkr})
                </option>
              ))}
            </select>
          </div>

          {/* Date & Slot Row */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Date *
              </label>
              <select
                value={selectedDate}
                onChange={(e) => {
                  setSelectedDate(e.target.value);
                  setTimeSlot('');
                }}
                className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-900"
                required
              >
                {Object.keys(currentDoctor?.slots_by_date || {}).map(d => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Available Time Slot *
              </label>
              <select
                value={timeSlot}
                onChange={(e) => setTimeSlot(e.target.value)}
                className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-900"
                required
              >
                <option value="">Select a slot...</option>
                {availableSlotsForDate.map(slot => (
                  <option key={slot} value={slot}>{slot}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Patient Details */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Patient Full Name *
              </label>
              <div className="relative">
                <input
                  type="text"
                  placeholder="e.g. احمد خان"
                  value={patientName}
                  onChange={(e) => setPatientName(e.target.value)}
                  className="w-full text-sm border border-slate-200 rounded-lg pl-8 pr-3 py-2 focus:outline-none focus:ring-2 focus:ring-slate-900"
                  required
                />
                <User className="w-4 h-4 text-slate-400 absolute left-2.5 top-2.5" />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Patient Phone Number *
              </label>
              <div className="relative">
                <input
                  type="text"
                  placeholder="e.g. 03001234567"
                  value={patientPhone}
                  onChange={(e) => setPatientPhone(e.target.value)}
                  className="w-full text-sm border border-slate-200 rounded-lg pl-8 pr-3 py-2 focus:outline-none focus:ring-2 focus:ring-slate-900"
                  required
                />
                <Phone className="w-4 h-4 text-slate-400 absolute left-2.5 top-2.5" />
              </div>
            </div>
          </div>

          {/* Medical Reason */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Reason / Symptoms
            </label>
            <input
              type="text"
              placeholder="e.g. Chest tightness, skin rash, fever"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-slate-900"
            />
          </div>

          {/* Footer Actions */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 disabled:opacity-50 rounded-lg transition-all flex items-center gap-1.5 shadow-sm"
            >
              {loading ? 'Booking...' : 'Confirm Appointment'}
            </button>
          </div>
        </form>

      </div>
    </div>
  );
}
