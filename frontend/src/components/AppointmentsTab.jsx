import React, { useState } from 'react';
import { Search, Filter, Calendar, Phone, User, Stethoscope, AlertCircle, RefreshCw, XCircle, Clock } from 'lucide-react';

export default function AppointmentsTab({
  appointments,
  doctors,
  onOpenBooking,
  onOpenReschedule,
  onCancelAppointment,
  loading
}) {
  const [search, setSearch] = useState('');
  const [docFilter, setDocFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  const filtered = appointments.filter(apt => {
    // Search
    if (search.trim()) {
      const q = search.toLowerCase();
      const matchName = apt.patient_name?.toLowerCase().includes(q);
      const matchPhone = apt.patient_phone?.toLowerCase().includes(q);
      const matchRef = apt.booking_reference?.toLowerCase().includes(q);
      if (!matchName && !matchPhone && !matchRef) return false;
    }

    // Doctor filter
    if (docFilter && String(apt.doctor_id) !== String(docFilter)) {
      return false;
    }

    // Status filter
    if (statusFilter !== 'all' && apt.status?.toLowerCase() !== statusFilter.toLowerCase()) {
      return false;
    }

    return true;
  });

  return (
    <div className="space-y-4">
      
      {/* Top Filter Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col md:flex-row justify-between items-start md:items-center gap-3">
        
        <div className="flex items-center gap-3 w-full md:w-auto flex-1">
          {/* Search Box */}
          <div className="relative flex-1 max-w-sm">
            <input
              type="text"
              placeholder="Search by Patient Name, Phone or APT#..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full text-xs pl-8 pr-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900"
            />
            <Search className="w-4 h-4 text-slate-400 absolute left-2.5 top-2.5" />
          </div>

          {/* Doctor Filter */}
          <select
            value={docFilter}
            onChange={(e) => setDocFilter(e.target.value)}
            className="text-xs border border-slate-200 rounded-lg px-2.5 py-2 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-900"
          >
            <option value="">All Doctors</option>
            {doctors.map(d => (
              <option key={d.id} value={d.id}>{d.name} ({d.specialty})</option>
            ))}
          </select>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs border border-slate-200 rounded-lg px-2.5 py-2 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-900"
          >
            <option value="all">All Statuses</option>
            <option value="confirmed">Confirmed</option>
            <option value="rescheduled">Rescheduled</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>

        <button
          onClick={() => onOpenBooking()}
          className="px-4 py-2 text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded-lg transition-all shadow-sm flex items-center gap-1.5 whitespace-nowrap"
        >
          <span>+ New Appointment</span>
        </button>

      </div>

      {/* Appointments Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[11px]">
              <tr>
                <th className="py-3 px-4">Booking Ref</th>
                <th className="py-3 px-4">Patient Information</th>
                <th className="py-3 px-4">Specialist Doctor</th>
                <th className="py-3 px-4">Scheduled Date & Time</th>
                <th className="py-3 px-4">Symptoms / Reason</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-12 text-slate-400">
                    No appointments match your filters.
                  </td>
                </tr>
              ) : (
                filtered.map(apt => {
                  const isCancelled = apt.status === 'cancelled';

                  return (
                    <tr key={apt.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-3 px-4 font-mono font-bold text-slate-900">
                        {apt.booking_reference}
                      </td>

                      <td className="py-3 px-4">
                        <div className="font-semibold text-slate-900">{apt.patient_name}</div>
                        <div className="text-slate-500 flex items-center gap-1 mt-0.5">
                          <Phone className="w-3 h-3" />
                          <span>{apt.patient_phone}</span>
                        </div>
                      </td>

                      <td className="py-3 px-4">
                        <div className="font-medium text-slate-900">{apt.doctor_name}</div>
                        <div className="text-slate-500 text-[11px]">{apt.specialty} • Rs. {apt.fee_pkr?.toLocaleString()}</div>
                      </td>

                      <td className="py-3 px-4">
                        <div className="flex items-center gap-1 font-medium text-slate-800">
                          <Calendar className="w-3 h-3 text-slate-400" />
                          <span>{apt.appointment_date}</span>
                        </div>
                        <div className="flex items-center gap-1 text-slate-500 text-[11px] mt-0.5">
                          <Clock className="w-3 h-3 text-slate-400" />
                          <span>{apt.time_slot}</span>
                        </div>
                      </td>

                      <td className="py-3 px-4 max-w-xs truncate text-slate-600">
                        {apt.reason || 'General Checkup'}
                      </td>

                      <td className="py-3 px-4">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border ${
                          apt.status === 'confirmed'
                            ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                            : apt.status === 'rescheduled'
                              ? 'bg-amber-50 text-amber-800 border-amber-200'
                              : 'bg-slate-100 text-slate-500 border-slate-200 line-through'
                        }`}>
                          {apt.status}
                        </span>
                      </td>

                      <td className="py-3 px-4 text-right">
                        {!isCancelled && (
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              onClick={() => onOpenReschedule(apt)}
                              className="px-2.5 py-1 text-xs font-medium bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 rounded-md transition-colors"
                            >
                              Reschedule
                            </button>
                            <button
                              onClick={() => onCancelAppointment(apt.id)}
                              className="px-2.5 py-1 text-xs font-medium text-rose-700 hover:bg-rose-50 border border-rose-200 rounded-md transition-colors"
                            >
                              Cancel
                            </button>
                          </div>
                        )}
                        {isCancelled && (
                          <span className="text-[11px] text-slate-400 italic">Slot Released</span>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
}
