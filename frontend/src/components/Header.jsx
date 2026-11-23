import React from 'react';
import { PhoneCall, PhoneOff, Activity, Stethoscope, CalendarCheck, Users } from 'lucide-react';

export default function Header({ 
  stats, 
  activeTab, 
  setActiveTab, 
  isCallOpen, 
  setIsCallOpen, 
  isCalling,
  agentStatus 
}) {
  return (
    <header className="sticky top-0 z-40 bg-white border-b border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          
          {/* Brand */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-slate-900 text-white flex items-center justify-center font-bold text-lg shadow-sm">
              H
            </div>
            <div>
              <h1 className="font-bold text-slate-900 tracking-tight text-lg">City Hospital</h1>
              <p className="text-xs text-slate-500">Clinical Operations & Urdu Voice Receptionist</p>
            </div>
          </div>

          {/* Quick Stats Ticker (Desktop) */}
          <div className="hidden lg:flex items-center gap-6 text-xs text-slate-600">
            <div className="flex items-center gap-2">
              <Users className="w-4 h-4 text-slate-400" />
              <span><strong>{stats?.total_doctors || 5}</strong> Specialists</span>
            </div>
            <div className="w-px h-4 bg-slate-200" />
            <div className="flex items-center gap-2">
              <CalendarCheck className="w-4 h-4 text-slate-400" />
              <span><strong>{stats?.today_appointments || 0}</strong> Today</span>
            </div>
            <div className="w-px h-4 bg-slate-200" />
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-emerald-600" />
              <span><strong>{stats?.confirmed_appointments || 0}</strong> Active Confirmed</span>
            </div>
          </div>

          {/* Persistent Voice Agent Call Button */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsCallOpen(!isCallOpen)}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-lg font-medium text-xs sm:text-sm transition-all shadow-sm ${
                isCalling 
                  ? 'bg-rose-600 hover:bg-rose-700 text-white animate-pulse'
                  : isCallOpen 
                    ? 'bg-slate-900 text-white hover:bg-slate-800'
                    : 'bg-emerald-600 hover:bg-emerald-700 text-white'
              }`}
            >
              {isCalling ? (
                <>
                  <PhoneOff className="w-4 h-4" />
                  <span>Call Active (Urdu)</span>
                </>
              ) : (
                <>
                  <PhoneCall className="w-4 h-4" />
                  <span>{isCallOpen ? 'Voice Console Open' : 'Talk in Urdu (AI Call)'}</span>
                </>
              )}
            </button>
          </div>

        </div>

        {/* Tab Navigation */}
        <div className="flex gap-8 -mb-px">
          <button
            onClick={() => setActiveTab('doctors')}
            className={`py-3.5 px-1 border-b-2 font-medium text-sm transition-colors flex items-center gap-2 ${
              activeTab === 'doctors'
                ? 'border-slate-900 text-slate-900 font-semibold'
                : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
            }`}
          >
            <Stethoscope className="w-4 h-4" />
            <span>Doctors & Live Slots Schedule</span>
          </button>

          <button
            onClick={() => setActiveTab('appointments')}
            className={`py-3.5 px-1 border-b-2 font-medium text-sm transition-colors flex items-center gap-2 ${
              activeTab === 'appointments'
                ? 'border-slate-900 text-slate-900 font-semibold'
                : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
            }`}
          >
            <CalendarCheck className="w-4 h-4" />
            <span>Booked Appointments Ledger</span>
            {stats?.confirmed_appointments > 0 && (
              <span className="ml-1.5 px-2 py-0.5 rounded-full text-[11px] bg-slate-100 text-slate-700 font-medium">
                {stats.confirmed_appointments}
              </span>
            )}
          </button>
        </div>

      </div>
    </header>
  );
}
