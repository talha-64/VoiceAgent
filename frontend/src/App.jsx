import React, { useState, useEffect, useCallback } from 'react';
import Header from './components/Header';
import DoctorsTab from './components/DoctorsTab';
import AppointmentsTab from './components/AppointmentsTab';
import VoiceCallPanel from './components/VoiceCallPanel';
import BookingModal from './components/BookingModal';
import RescheduleModal from './components/RescheduleModal';

export default function App() {
  const [activeTab, setActiveTab] = useState('doctors'); // 'doctors' | 'appointments'
  const [isCallOpen, setIsCallOpen] = useState(false);
  const [isCalling, setIsCalling] = useState(false);

  const [doctors, setDoctors] = useState([]);
  const [appointments, setAppointments] = useState([]);
  const [stats, setStats] = useState({
    total_doctors: 5,
    total_appointments: 0,
    today_appointments: 0,
    confirmed_appointments: 0
  });

  const [loading, setLoading] = useState(true);

  // Modals state
  const [isBookingOpen, setIsBookingOpen] = useState(false);
  const [bookingPrefills, setBookingPrefills] = useState({ doctorId: '', date: '', slot: '' });

  const [isRescheduleOpen, setIsRescheduleOpen] = useState(false);
  const [rescheduleTarget, setRescheduleTarget] = useState(null);

  // Fetch all live data from FastAPI backend
  const fetchHospitalData = useCallback(async () => {
    try {
      const [docsRes, aptsRes, statsRes] = await Promise.all([
        fetch('/api/doctors'),
        fetch('/api/appointments'),
        fetch('/api/stats')
      ]);

      if (docsRes.ok) {
        const docs = await docsRes.json();
        setDoctors(docs);
      }
      if (aptsRes.ok) {
        const apts = await aptsRes.json();
        setAppointments(apts);
      }
      if (statsRes.ok) {
        const s = await statsRes.json();
        setStats(s);
      }
    } catch (err) {
      console.warn('Live sync poll warning:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load + 3-second auto-refresh polling
  useEffect(() => {
    fetchHospitalData();
    const interval = setInterval(fetchHospitalData, 3000);
    return () => clearInterval(interval);
  }, [fetchHospitalData]);

  // Quick book slot click from DoctorsTab
  const handleBookSlotClick = (doctorId, date, slot) => {
    setBookingPrefills({ doctorId, date, slot });
    setIsBookingOpen(true);
  };

  // Open reschedule modal from AppointmentsTab
  const handleOpenReschedule = (apt) => {
    setRescheduleTarget(apt);
    setIsRescheduleOpen(true);
  };

  // Cancel appointment handler
  const handleCancelAppointment = async (aptId) => {
    if (!confirm('Are you sure you want to cancel this appointment and release the slot?')) {
      return;
    }

    try {
      const res = await fetch(`/api/appointments/${aptId}`, { method: 'DELETE' });
      if (res.ok) {
        await fetchHospitalData();
      } else {
        const data = await res.json();
        alert('Cancellation failed: ' + (data.detail || data.message));
      }
    } catch (err) {
      alert('Error: ' + err.message);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900">
      
      {/* Navigation Header */}
      <Header
        stats={stats}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        isCallOpen={isCallOpen}
        setIsCallOpen={setIsCallOpen}
        isCalling={isCalling}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        
        {/* Tab 1: Doctors & Live Schedule */}
        {activeTab === 'doctors' && (
          <DoctorsTab
            doctors={doctors}
            onBookSlot={handleBookSlotClick}
            loading={loading}
          />
        )}

        {/* Tab 2: Booked Appointments Ledger */}
        {activeTab === 'appointments' && (
          <AppointmentsTab
            appointments={appointments}
            doctors={doctors}
            onOpenBooking={() => {
              setBookingPrefills({ doctorId: '', date: '', slot: '' });
              setIsBookingOpen(true);
            }}
            onOpenReschedule={handleOpenReschedule}
            onCancelAppointment={handleCancelAppointment}
            loading={loading}
          />
        )}

      </main>

      {/* Persistent Voice Call Panel Drawer */}
      <VoiceCallPanel
        isOpen={isCallOpen}
        onClose={() => setIsCallOpen(false)}
        isCalling={isCalling}
        setIsCalling={setIsCalling}
        onCallEventTriggered={fetchHospitalData}
      />

      {/* Booking Modal */}
      <BookingModal
        isOpen={isBookingOpen}
        onClose={() => setIsBookingOpen(false)}
        doctors={doctors}
        preselectedDoctorId={bookingPrefills.doctorId}
        preselectedDate={bookingPrefills.date}
        preselectedSlot={bookingPrefills.slot}
        onSuccess={fetchHospitalData}
      />

      {/* Reschedule Modal */}
      <RescheduleModal
        isOpen={isRescheduleOpen}
        onClose={() => setIsRescheduleOpen(false)}
        appointment={rescheduleTarget}
        doctors={doctors}
        onSuccess={fetchHospitalData}
      />

    </div>
  );
}
