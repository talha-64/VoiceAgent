import React, { useState, useEffect } from 'react';
import { X, Calendar, Clock } from 'lucide-react';

export default function RescheduleModal({
  isOpen,
  onClose,
  appointment,
  doctors,
  onSuccess
}) {
  const [newDate, setNewDate] = useState('');
  const [newTimeSlot, setNewTimeSlot] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const currentDoctor = doctors.find(d => d.id === appointment?.doctor_id);
  const availableDates = Object.keys(currentDoctor?.slots_by_date || {});

  useEffect(() => {
    if (appointment) {
      setNewDate(appointment.appointment_date || availableDates[0] || '');
      setNewTimeSlot(appointment.time_slot || '');
    }
  }, [appointment, isOpen]);

  if (!isOpen || !appointment) return null;

  const openSlots = (currentDoctor?.slots_by_date?.[newDate] || [])
    .filter(s => !s.is_booked || s.start_time === appointment.time_slot)
    .map(s => s.start_time);

  const handleReschedule = async (e) => {
    e.preventDefault();
    if (!newDate || !newTimeSlot) {
      setError('Please select both a new date and time slot.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const res = await fetch(`/api/appointments/${appointment.id}/reschedule`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          new_date: newDate,
          new_time_slot: newTimeSlot
        })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || data.message || 'Rescheduling failed');
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
      <div className="bg-white rounded-xl shadow-xl border border-slate-200 w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/50">
          <div>
            <h3 className="font-semibold text-slate-900 text-base">Reschedule Appointment</h3>
            <p className="text-xs text-slate-500">{appointment.booking_reference} • {appointment.patient_name}</p>
          </div>
          <button 
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleReschedule} className="p-6 space-y-4">
          {error && (
            <div className="p-3 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-lg">
              {error}
            </div>
          )}

          <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-600 space-y-1">
            <p><strong>Doctor:</strong> {appointment.doctor_name} ({appointment.specialty})</p>
            <p><strong>Current Slot:</strong> {appointment.appointment_date} at {appointment.time_slot}</p>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Select New Date *
            </label>
            <select
              value={newDate}
              onChange={(e) => {
                setNewDate(e.target.value);
                setNewTimeSlot('');
              }}
              className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-900"
              required
            >
              {availableDates.map(d => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Select New Available Slot *
            </label>
            <select
              value={newTimeSlot}
              onChange={(e) => setNewTimeSlot(e.target.value)}
              className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-900"
              required
            >
              <option value="">Select a new time slot...</option>
              {openSlots.map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>

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
              className="px-4 py-2 text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 disabled:opacity-50 rounded-lg transition-all shadow-sm"
            >
              {loading ? 'Rescheduling...' : 'Confirm Reschedule'}
            </button>
          </div>
        </form>

      </div>
    </div>
  );
}
