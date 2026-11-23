import React, { useState } from 'react';
import { Calendar, Clock, DollarSign, Award, CheckCircle, AlertCircle, PlusCircle } from 'lucide-react';

export default function DoctorsTab({
  doctors,
  onBookSlot,
  loading
}) {
  const [selectedSpecialty, setSelectedSpecialty] = useState('All');
  
  // Extract all available dates across doctors
  const allDates = Array.from(
    new Set(
      doctors.flatMap(d => Object.keys(d.slots_by_date || {}))
    )
  ).sort();

  const [activeDate, setActiveDate] = useState(allDates[0] || new Date().toISOString().split('T')[0]);

  // Keep activeDate in sync once dates load
  React.useEffect(() => {
    if (allDates.length > 0 && !allDates.includes(activeDate)) {
      setActiveDate(allDates[0]);
    }
  }, [allDates, activeDate]);

  const specialties = ['All', 'Cardiology', 'Dermatology', 'Pediatrics', 'Orthopedics', 'General Medicine'];

  const filteredDoctors = doctors.filter(doc => {
    if (selectedSpecialty === 'All') return true;
    return (
      doc.specialty?.toLowerCase().includes(selectedSpecialty.toLowerCase()) ||
      doc.department?.toLowerCase().includes(selectedSpecialty.toLowerCase())
    );
  });

  return (
    <div className="space-y-6">
      
      {/* Top Filter & Date Selector Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        
        {/* Specialty Filter Pills */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider mr-1">Specialty:</span>
          {specialties.map(spec => (
            <button
              key={spec}
              onClick={() => setSelectedSpecialty(spec)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                selectedSpecialty === spec
                  ? 'bg-slate-900 text-white shadow-sm'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {spec}
            </button>
          ))}
        </div>

        {/* Date Selector Pills */}
        <div className="flex items-center gap-1.5">
          <Calendar className="w-4 h-4 text-slate-400 mr-1" />
          {allDates.map((d, index) => {
            const isToday = index === 0;
            const isTomorrow = index === 1;
            const label = isToday ? 'Today' : isTomorrow ? 'Tomorrow' : d.slice(5);

            return (
              <button
                key={d}
                onClick={() => setActiveDate(d)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  activeDate === d
                    ? 'bg-slate-900 text-white shadow-sm'
                    : 'bg-white border border-slate-200 text-slate-700 hover:bg-slate-50'
                }`}
              >
                <span>{label}</span>
                <span className="text-[10px] ml-1 opacity-70">({d.slice(5)})</span>
              </button>
            );
          })}
        </div>

      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-xs text-slate-500 px-1">
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-emerald-500 border border-emerald-600"></span>
          <span>Green = <strong>Available Slot</strong> (Click to Book)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-slate-200 border border-slate-300"></span>
          <span className="line-through">Gray = <strong>Booked Slot</strong></span>
        </div>
        <div className="ml-auto text-slate-400">
          Showing {filteredDoctors.length} Specialists
        </div>
      </div>

      {/* Doctors Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredDoctors.map(doctor => {
          const slotsForDate = doctor.slots_by_date?.[activeDate] || [];
          const availableCount = slotsForDate.filter(s => !s.is_booked).length;

          return (
            <div 
              key={doctor.id} 
              className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 flex flex-col justify-between hover:border-slate-300 transition-all"
            >
              <div>
                {/* Doctor Header */}
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div>
                    <h3 className="font-bold text-slate-900 text-base">{doctor.name}</h3>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-xs font-semibold text-slate-700 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                        {doctor.specialty}
                      </span>
                      <span className="text-xs text-slate-500">{doctor.department}</span>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="text-sm font-bold text-slate-900">PKR {doctor.fee_pkr.toLocaleString()}</span>
                    <span className="block text-[10px] text-slate-500">per visit</span>
                  </div>
                </div>

                {/* Experience & Bio */}
                <p className="text-xs text-slate-600 mb-3 leading-relaxed">
                  {doctor.bio}
                </p>

                <div className="flex items-center gap-2 text-xs text-slate-500 mb-4 pb-3 border-b border-slate-100">
                  <Award className="w-3.5 h-3.5 text-slate-400" />
                  <span><strong>{doctor.experience_years} years</strong> clinical experience</span>
                </div>

                {/* Slots Section */}
                <div>
                  <div className="flex items-center justify-between text-xs mb-2 font-medium">
                    <span className="text-slate-700 flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-slate-400" />
                      <span>Slots for {activeDate}:</span>
                    </span>
                    <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${
                      availableCount > 0 ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'
                    }`}>
                      {availableCount} Available
                    </span>
                  </div>

                  {slotsForDate.length === 0 ? (
                    <p className="text-xs text-slate-400 py-3 text-center">No slots scheduled for this date.</p>
                  ) : (
                    <div className="grid grid-cols-3 gap-1.5">
                      {slotsForDate.map(slot => {
                        const isAvailable = !slot.is_booked;

                        return (
                          <button
                            key={slot.id}
                            disabled={!isAvailable}
                            onClick={() => onBookSlot(doctor.id, activeDate, slot.start_time)}
                            className={`py-1.5 px-2 rounded-lg text-xs font-medium text-center transition-all ${
                              isAvailable
                                ? 'bg-emerald-50 text-emerald-800 border border-emerald-300 hover:bg-emerald-100 hover:border-emerald-400 cursor-pointer shadow-xs active:scale-95'
                                : 'bg-slate-100 text-slate-400 border border-slate-200 line-through cursor-not-allowed opacity-60'
                            }`}
                            title={isAvailable ? 'Click to book this slot' : 'Slot already booked'}
                          >
                            {slot.start_time}
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>

              {/* Quick Book Button */}
              <div className="mt-5 pt-3 border-t border-slate-100 flex items-center justify-between">
                <span className="text-[11px] text-slate-500">
                  {availableCount > 0 ? 'Click green slot to book' : 'Fully booked today'}
                </span>
                <button
                  onClick={() => onBookSlot(doctor.id, activeDate, '')}
                  className="text-xs font-semibold text-slate-900 hover:text-slate-700 flex items-center gap-1 hover:underline"
                >
                  <PlusCircle className="w-3.5 h-3.5" />
                  <span>Manual Book</span>
                </button>
              </div>

            </div>
          );
        })}
      </div>

    </div>
  );
}
