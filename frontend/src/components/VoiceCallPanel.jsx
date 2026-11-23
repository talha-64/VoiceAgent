import React, { useState, useEffect, useRef } from 'react';
import { X, Mic, MicOff, PhoneCall, PhoneOff, Volume2, Sparkles, AlertCircle, RefreshCw } from 'lucide-react';
import Vapi from '@vapi-ai/web';

export default function VoiceCallPanel({
  isOpen,
  onClose,
  isCalling,
  setIsCalling,
  onCallEventTriggered
}) {
  const vapiPublicKey = import.meta.env.VITE_VAPI_PUBLIC_KEY || '3472661b-3a1c-43df-a10e-f2a69397c3d4';
  const vapiAssistantId = import.meta.env.VITE_VAPI_ASSISTANT_ID || 'f990c9dd-2114-4b4f-8de7-f114dcbf5c16';
  const ngrokUrl = import.meta.env.VITE_NGROK_URL || 'https://unbent-cufflink-connector.ngrok-free.dev';

  const [callStatus, setCallStatus] = useState('Idle'); // Idle, Connecting, In Call, Speaking
  const [isMuted, setIsMuted] = useState(false);
  const [volumeLevel, setVolumeLevel] = useState(0);
  const [transcripts, setTranscripts] = useState([
    { role: 'assistant', text: 'السلام علیکم! سٹی ہسپتال میں خوش آمدید، میں عائشہ ہوں۔ فرمائیے میں آپ کی کیا مدد کر سکتی ہوں؟' }
  ]);
  const [errorMsg, setErrorMsg] = useState('');

  const vapiRef = useRef(null);
  const chatScrollRef = useRef(null);

  // Auto-scroll transcript
  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [transcripts]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (vapiRef.current) {
        vapiRef.current.stop();
      }
    };
  }, []);

  const formatError = (err) => {
    if (!err) return 'Unknown error';
    
    // Check for Daily / WebRTC ejection or meeting ended
    const str = JSON.stringify(err).toLowerCase();
    if (str.includes('ejected') || str.includes('meeting has ended')) {
      return 'Call disconnected: Vapi did not receive microphone audio from the browser, or the call timed out. Please check that your microphone is active and not muted in Windows or Chrome.';
    }

    if (typeof err === 'string') return err;
    if (typeof err.message === 'string') return err.message;
    if (err.message && typeof err.message.message === 'string') return err.message.message;
    if (err.error && typeof err.error.message === 'string') return err.error.message;
    if (err.error && typeof err.error.message?.message === 'string') return err.error.message.message;
    try {
      return JSON.stringify(err);
    } catch {
      return String(err);
    }
  };

  const startCall = async () => {
    if (!vapiPublicKey) {
      setErrorMsg('Vapi Public Key is required.');
      return;
    }

    try {
      setErrorMsg('');
      setCallStatus('Connecting...');

      // Pre-flight browser microphone permission check
      if (navigator?.mediaDevices?.getUserMedia) {
        try {
          const micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
          micStream.getTracks().forEach(track => track.stop());
        } catch (micErr) {
          console.warn('Microphone permission check failed:', micErr);
          setErrorMsg('Microphone access is blocked or unavailable. Please click the camera/lock icon in your browser address bar to allow microphone access.');
          setCallStatus('Idle');
          return;
        }
      }
      
      const vapi = new Vapi(vapiPublicKey);
      vapiRef.current = vapi;

      vapi.on('call-start', () => {
        setIsCalling(true);
        setCallStatus('In Call');
      });

      vapi.on('speech-start', () => {
        setCallStatus('Speaking / Listening');
      });

      vapi.on('speech-end', () => {
        setCallStatus('In Call');
      });

      vapi.on('volume-level', (vol) => {
        setVolumeLevel(vol);
      });

      vapi.on('message', (msg) => {
        if (msg.type === 'transcript' && msg.transcriptType === 'final') {
          setTranscripts(prev => [
            ...prev,
            { role: msg.role, text: msg.transcript }
          ]);
          // Notify parent app to reload doctors and appointments in background
          onCallEventTriggered();
        }
      });

      vapi.on('call-end', () => {
        setIsCalling(false);
        setCallStatus('Idle');
        setVolumeLevel(0);
        onCallEventTriggered();
      });

      vapi.on('error', (err) => {
        console.error('Vapi Call Error:', err);
        setErrorMsg(formatError(err));
        setIsCalling(false);
        setCallStatus('Idle');
      });

      // Always use assistant ID if available, otherwise use ngrok URL inline config
      if (vapiAssistantId) {
        await vapi.start(vapiAssistantId);
      } else {
        let chatEndpoint = ngrokUrl.trim();
        if (!chatEndpoint.endsWith('/chat/completions')) {
          chatEndpoint = chatEndpoint.replace(/\/+$/, '') + '/chat/completions';
        }

        await vapi.start({
          transcriber: {
            provider: 'deepgram',
            model: 'nova-3',
            language: 'ur'
          },
          model: {
            provider: 'custom-llm',
            url: chatEndpoint,
            headers: {
              'ngrok-skip-browser-warning': 'true'
            }
          },
          voice: {
            provider: '11labs',
            voiceId: '21m00Tcm4TlvDq8ikWAM',
            model: 'eleven_multilingual_v2'
          },
          firstMessage: 'السلام علیکم! سٹی ہسپتال میں خوش آمدید، میں عائشہ ہوں، فرمائیے میں آپ کی کیا مدد کر سکتی ہوں؟'
        });
      }

    } catch (err) {
      console.error('Failed to start call:', err);
      setErrorMsg(formatError(err));
      setIsCalling(false);
      setCallStatus('Idle');
    }
  };

  const endCall = () => {
    if (vapiRef.current) {
      vapiRef.current.stop();
      setIsCalling(false);
      setCallStatus('Idle');
      setVolumeLevel(0);
    }
  };

  const toggleMute = () => {
    if (vapiRef.current) {
      const next = !isMuted;
      vapiRef.current.setMuted(next);
      setIsMuted(next);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-96 bg-white border-l border-slate-200 shadow-2xl flex flex-col animate-in slide-in-from-right duration-200">
      
      {/* Top Header */}
      <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-slate-900 text-white flex items-center justify-center font-bold text-sm">
            AI
          </div>
          <div>
            <h3 className="font-bold text-slate-900 text-sm">Urdu Voice Receptionist</h3>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className={`w-2 h-2 rounded-full ${
                isCalling ? 'bg-emerald-500 animate-ping' : 'bg-slate-400'
              }`} />
              <span className="text-[11px] text-slate-500 font-medium">{callStatus}</span>
            </div>
          </div>
        </div>

        <button 
          onClick={onClose}
          className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-200/50 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Persistent Call Controls */}
      <div className="p-4 border-b border-slate-200 space-y-3 bg-white">
        {errorMsg && (
          <div className="p-2.5 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-lg flex items-start gap-1.5">
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Call Toggle Button */}
        {!isCalling ? (
          <button
            onClick={startCall}
            disabled={callStatus === 'Connecting...'}
            className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-semibold rounded-xl text-sm flex items-center justify-center gap-2 shadow-sm transition-all"
          >
            <PhoneCall className="w-4 h-4" />
            <span>{callStatus === 'Connecting...' ? 'Connecting...' : 'Start Urdu Voice Call'}</span>
          </button>
        ) : (
          <div className="flex gap-2">
            <button
              onClick={toggleMute}
              className={`flex-1 py-2.5 px-3 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 border transition-all ${
                isMuted 
                  ? 'bg-amber-50 text-amber-800 border-amber-300' 
                  : 'bg-slate-100 text-slate-700 border-slate-200 hover:bg-slate-200'
              }`}
            >
              {isMuted ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
              <span>{isMuted ? 'Muted' : 'Mute Mic'}</span>
            </button>

            <button
              onClick={endCall}
              className="flex-1 py-2.5 px-3 bg-rose-600 hover:bg-rose-700 text-white font-semibold rounded-xl text-xs flex items-center justify-center gap-1.5 shadow-sm transition-all"
            >
              <PhoneOff className="w-4 h-4" />
              <span>End Call</span>
            </button>
          </div>
        )}

        {/* Audio Visualizer Strip */}
        <div className="flex items-center justify-between px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg">
          <span className="text-[11px] font-medium text-slate-500">Audio Activity</span>
          <div className="flex items-center gap-1 h-4">
            {[1, 2, 3, 4, 5, 6, 7].map(i => {
              const height = isCalling 
                ? Math.max(4, Math.min(16, (volumeLevel * 100) * (0.4 + (i * 0.1)))) 
                : 4;
              return (
                <div
                  key={i}
                  style={{ height: `${height}px` }}
                  className={`w-1 rounded-full transition-all duration-75 ${
                    isCalling ? 'bg-emerald-600' : 'bg-slate-300'
                  }`}
                />
              );
            })}
          </div>
        </div>
      </div>

      {/* Live Conversation Transcript Feed */}
      <div className="flex-1 p-4 overflow-y-auto space-y-3 bg-slate-50/50" ref={chatScrollRef}>
        <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider text-center">
          Real-time Voice Transcript
        </div>

        {transcripts.map((t, idx) => {
          const isAssistant = t.role === 'assistant';
          return (
            <div
              key={idx}
              className={`p-3 rounded-xl text-xs max-w-[88%] leading-relaxed ${
                isAssistant
                  ? 'bg-white border border-slate-200 text-slate-800 self-start mr-auto urdu-text'
                  : 'bg-slate-900 text-white ml-auto urdu-text'
              }`}
              style={{ direction: 'rtl', textAlign: 'right' }}
            >
              <div className="text-[10px] text-slate-400 font-sans font-medium mb-1" style={{ direction: 'ltr', textAlign: 'left' }}>
                {isAssistant ? 'عائشہ (Receptionist)' : 'آپ (Caller)'}
              </div>
              <p className="text-sm font-medium">{t.text}</p>
            </div>
          );
        })}
      </div>

      {/* Sample Urdu Voice Prompts */}
      <div className="p-3 border-t border-slate-200 bg-white">
        <span className="block text-[11px] font-semibold text-slate-500 mb-1.5">
          🗣️ Sample Voice Queries to Say in Urdu:
        </span>
        <div className="space-y-1.5 text-xs text-slate-700 urdu-text" style={{ direction: 'rtl', textAlign: 'right' }}>
          <div className="p-1.5 rounded bg-slate-50 border border-slate-100 hover:bg-slate-100 cursor-pointer">
            "السلام علیکم! مجھے دل کے ڈاکٹر کی فیس اور اوقات بتائیں"
          </div>
          <div className="p-1.5 rounded bg-slate-50 border border-slate-100 hover:bg-slate-100 cursor-pointer">
            "میرا نام کامران ہے، فون 03001234567، کل ڈاکٹر بلال سے اپائنٹمنٹ بک کریں"
          </div>
          <div className="p-1.5 rounded bg-slate-50 border border-slate-100 hover:bg-slate-100 cursor-pointer">
            "میرا اپائنٹمنٹ چیک کریں یا کینسل کر دیں"
          </div>
        </div>
      </div>

    </div>
  );
}
