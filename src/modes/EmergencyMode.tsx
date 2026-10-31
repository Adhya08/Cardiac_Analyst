/**
 * EmergencyMode — Real geolocation + Google Places hospital finder + NICE CG95 triage
 * No mock data. All hospital data is live from Google Places API.
 */
import React, { useState, useEffect } from 'react';
import {
  PhoneCall, MapPin, Navigation, AlertTriangle, ShieldAlert,
  CheckCircle, Info, Loader2, RefreshCw, ExternalLink, MapPinned,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import HospitalMap from '../components/HospitalMap';
import { api, type TriageResponse } from '../lib/api';
import { translations } from '../lib/translations';
import { useStore } from '../store/useStore';

// Triage questions — same as backend (NICE CG95)
const TRIAGE_QUESTIONS = [
  "Are you experiencing crushing or squeezing chest pain?",
  "Does the pain radiate to your left arm, jaw, or shoulder?",
  "Are you short of breath even while resting?",
  "Are you feeling nauseous or lightheaded / dizzy?",
  "Is your heart racing or beating irregularly?",
  "Are you sweating profusely or having cold sweats?",
  "Have you fainted or nearly fainted recently?",
  "Is your vision blurry or are you confused?",
];

type Step = 'triage' | 'analyzing' | 'result';

export const EmergencyMode: React.FC = () => {
  const { language } = useStore();
  const t = translations[language];
  const [step, setStep] = useState<Step>('triage');
  const [answers, setAnswers] = useState<Record<number, boolean>>({});
  const [triageResult, setTriageResult] = useState<TriageResponse | null>(null);
  const [location, setLocation] = useState<{ lat: number; lon: number } | null>(null);
  const [locationError, setLocationError] = useState<string | null>(null);
  const [geoLoading, setGeoLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);

  // Get real geolocation on mount
  useEffect(() => {
    getLocation();
  }, []);

  const getLocation = () => {
    setGeoLoading(true);
    setLocationError(null);
    if (!navigator.geolocation) {
      setLocationError('Geolocation not supported by this browser.');
      setGeoLoading(false);
      setLocation({ lat: 28.6139, lon: 77.2090 }); // Delhi fallback
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocation({ lat: pos.coords.latitude, lon: pos.coords.longitude });
        setGeoLoading(false);
      },
      (err) => {
        setLocationError(`Location access denied: ${err.message}. Using Delhi as fallback.`);
        setLocation({ lat: 28.6139, lon: 77.2090 });
        setGeoLoading(false);
      },
      { timeout: 10000, enableHighAccuracy: true }
    );
  };

  const handleAnswer = async (qIdx: number, val: boolean) => {
    const next = { ...answers, [qIdx]: val };
    setAnswers(next);

    if (Object.keys(next).length === TRIAGE_QUESTIONS.length) {
      await submitTriage(next);
    }
  };

  const submitTriage = async (finalAnswers: Record<number, boolean>) => {
    setStep('analyzing');
    setApiError(null);

    const symptoms = TRIAGE_QUESTIONS.map((_, i) => finalAnswers[i] ?? false);

    try {
      const result = await api.submitTriage({
        symptoms,
        lat: location?.lat,
        lon: location?.lon,
      });
      setTriageResult(result);
      setStep('result');
    } catch (err: any) {
      setApiError(err.message);
      // Fallback result — government numbers always available
      setTriageResult({
        severity: 'emergency',
        confidence: 0.8,
        risk_score: 70,
        yes_count: Object.values(finalAnswers).filter(Boolean).length,
        stemi_suspicious: finalAnswers[0] && finalAnswers[1],
        combo_triggered: false,
        vitals_red_flag: false,
        instructions: [
          'Call 112 immediately.',
          'Sit or lie down. Do not drive yourself.',
          'Unlock your front door.',
          'Remain calm and rest quietly until emergency medical personnel arrive.',
        ],
        hospitals: [],
        ambulances: [
          { service: 'India Emergency', contact: '112', type: 'government' },
          { service: 'Govt Ambulance', contact: '108', type: 'government' },
        ],
        triage_id: 'offline',
      });
      setStep('result');
    }
  };

  const reset = () => {
    setStep('triage');
    setAnswers({});
    setTriageResult(null);
    setApiError(null);
  };

  const progress = (Object.keys(answers).length / TRIAGE_QUESTIONS.length) * 100;
  const currentQ = Object.keys(answers).length;
  const isEmergency = triageResult?.severity === 'emergency';

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Geolocation status bar */}
      <div className={`flex items-center gap-2 text-xs px-3 py-2 rounded-lg ${geoLoading ? 'bg-slate-800' : locationError ? 'bg-amber-500/10 border border-amber-500/20' : 'bg-emerald-500/10 border border-emerald-500/20'}`}>
        {geoLoading ? (
          <><Loader2 className="w-3 h-3 animate-spin text-slate-400" /> <span className="text-slate-400">Getting your location…</span></>
        ) : locationError ? (
          <><MapPin className="w-3 h-3 text-amber-400" /> <span className="text-amber-400">{locationError}</span></>
        ) : (
          <><MapPin className="w-3 h-3 text-emerald-400" /> <span className="text-emerald-400">Location acquired — hospital finder active</span></>
        )}
        {!geoLoading && locationError && (
          <button onClick={getLocation} className="ml-auto text-slate-400 hover:text-white flex items-center gap-1">
            <RefreshCw className="w-3 h-3" /> Retry
          </button>
        )}
      </div>

      <AnimatePresence mode="wait">
        {/* ── TRIAGE QUESTIONNAIRE ── */}
        {step === 'triage' && (
          <motion.div key="triage" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }} className="glass-card p-12 space-y-10 border-red-500/20">

            <header className="text-center space-y-4">
              <div className="w-16 h-16 bg-red-500/10 rounded-full flex items-center justify-center mx-auto border border-red-500/20">
                <ShieldAlert className="text-red-500 w-8 h-8 animate-pulse" />
              </div>
              <div>
                <h2 className="text-3xl font-black text-white uppercase tracking-tighter">{t.emergency_triage}</h2>
                <p className="text-slate-400 text-sm mt-1">{t.triage_tagline}</p>
              </div>
            </header>

            {/* Progress */}
            <div className="space-y-2">
              <div className="flex justify-between text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">
                <span>{t.question} {currentQ + 1} {t.of} {TRIAGE_QUESTIONS.length}</span>
                <span>{Math.round(progress)}% {t.complete}</span>
              </div>
              <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                <motion.div animate={{ width: `${progress}%` }} className="h-full bg-red-500 rounded-full" />
              </div>
            </div>

            {currentQ < TRIAGE_QUESTIONS.length ? (
              <>
                <div className="min-h-[100px] flex items-center justify-center text-center">
                  <motion.h3 key={currentQ} initial={{ opacity: 0, x: 30 }} animate={{ opacity: 1, x: 0 }}
                    className="text-2xl font-bold text-slate-100 leading-snug">
                    {TRIAGE_QUESTIONS[currentQ]}
                  </motion.h3>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <button onClick={() => handleAnswer(currentQ, true)}
                    className="py-6 rounded-2xl bg-red-600 hover:bg-red-500 text-white font-black text-2xl tracking-widest transition-all active:scale-95 shadow-xl shadow-red-900/20 uppercase">
                    {t.yes}
                  </button>
                  <button onClick={() => handleAnswer(currentQ, false)}
                    className="py-6 rounded-2xl bg-slate-800 hover:bg-slate-700 text-white font-black text-2xl tracking-widest transition-all active:scale-95 uppercase">
                    {t.no}
                  </button>
                </div>
              </>
            ) : (
              <div className="text-center">
                <p className="text-slate-400 mt-3">{t.submitting}</p>
              </div>
            )}
          </motion.div>
        )}

        {/* ── ANALYZING ── */}
        {step === 'analyzing' && (
          <motion.div key="analyzing" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            className="glass-card p-16 flex flex-col items-center gap-8 text-center">
            <div className="relative">
              <div className="w-24 h-24 border-4 border-red-500/20 border-t-red-500 rounded-full animate-spin" />
              <ShieldAlert className="absolute inset-0 m-auto text-red-500 w-8 h-8" />
            </div>
            <div>
              <h3 className="text-xl font-bold">{t.assessing_situation}</h3>
              <p className="text-slate-400 mt-2">{t.triage_tagline}</p>
            </div>
          </motion.div>
        )}

        {/* ── RESULT ── */}
        {step === 'result' && triageResult && (
          <motion.div key="result" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-8">
            {/* STEMI suspicion warning */}
            {triageResult.stemi_suspicious && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                className="p-4 rounded-2xl bg-red-600/20 border border-red-500/40 flex items-center gap-3">
                <AlertTriangle className="text-red-400 w-6 h-6 flex-shrink-0 animate-pulse" />
                <p className="text-red-300 font-bold text-sm">⚠ STEMI HIGH SUSPICION — Call 112 immediately. Do not wait.</p>
              </motion.div>
            )}

            {apiError && (
              <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-400">
                ⚠ Backend unreachable: {apiError}. Using offline emergency fallback with government numbers.
              </div>
            )}

            {/* Main emergency card */}
            <div className={`p-8 rounded-3xl text-white shadow-2xl space-y-6 ${isEmergency ? 'bg-red-600 shadow-red-600/30' : triageResult.severity === 'see_doctor' ? 'bg-amber-600 shadow-amber-600/20' : 'bg-emerald-700 shadow-emerald-700/20'}`}>
              <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
                <div className="space-y-1">
                  <h2 className="text-4xl font-black uppercase tracking-tighter">
                    {isEmergency ? t.emergency : triageResult.severity === 'see_doctor' ? t.see_doctor_today : t.low_risk}
                  </h2>
                  <p className="opacity-80 font-medium">
                    {isEmergency ? t.potential_risk :
                      triageResult.severity === 'see_doctor' ? t.eval_needed :
                      t.symptoms_non_emergent}
                  </p>
                  <p className="text-sm opacity-60">
                    Confidence: {(triageResult.confidence * 100).toFixed(0)}% · Risk score: {triageResult.risk_score.toFixed(0)}%
                  </p>
                </div>
                {isEmergency && (
                  <a href="tel:112" className="flex items-center gap-3 bg-white text-red-600 px-8 py-4 rounded-2xl font-black text-xl hover:scale-105 active:scale-95 transition-all shadow-xl">
                    <PhoneCall className="w-6 h-6" /> {t.call_112}
                  </a>
                )}
              </div>

              {/* Location + status */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-white/20">
                <div className="bg-white/10 p-4 rounded-2xl flex gap-3 items-center border border-white/10">
                  <div className="p-2 bg-white text-red-600 rounded-xl"><MapPinned className="w-5 h-5" /></div>
                  <div>
                    <p className="text-[10px] font-bold uppercase opacity-70">Location</p>
                    <p className="text-sm font-bold">
                      {location ? `${location.lat.toFixed(4)}, ${location.lon.toFixed(4)}` : 'Unavailable'}
                    </p>
                  </div>
                </div>
                <div className="bg-white/10 p-4 rounded-2xl flex gap-3 items-center border border-white/10">
                  <div className="p-2 bg-white text-red-600 rounded-xl"><CheckCircle className="w-5 h-5" /></div>
                  <div>
                    <p className="text-[10px] font-bold uppercase opacity-70">Triage Answers</p>
                    <p className="text-sm font-bold">{triageResult.yes_count}/8 symptoms reported</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Instructions */}
            <div className="glass-card p-6 border-emerald-500/20 bg-emerald-500/5">
              <h3 className="text-sm font-bold flex items-center gap-2 mb-4">
                <Info className="w-4 h-4 text-emerald-500" /> Instructions While Waiting
              </h3>
              <ul className="space-y-2">
                {triageResult.instructions.map((inst, i) => (
                  <li key={i} className="flex gap-2 items-start text-xs text-slate-300">
                    <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full mt-1.5 flex-shrink-0" />
                    {inst}
                  </li>
                ))}
              </ul>
            </div>

            {/* Map + Hospitals + Ambulances */}
            <div className="grid grid-cols-1 md:grid-cols-12 gap-8">
              <div className="md:col-span-8 space-y-6">
                <div className="glass-card p-6 space-y-4">
                  <h3 className="text-sm font-bold flex items-center gap-2">
                    <Navigation className="w-4 h-4 text-emerald-500" />
                    {t.nearest_hospitals}
                    <span className="ml-auto text-[9px] text-slate-600 font-normal">Live data — Google Places API</span>
                  </h3>

                  {/* Google Maps */}
                  {location && triageResult.hospitals.length > 0 && (
                    <HospitalMap userLat={location.lat} userLon={location.lon} hospitals={triageResult.hospitals} />
                  )}

                  {/* Hospital list */}
                  {triageResult.hospitals.length > 0 ? (
                    <div className="space-y-3">
                      {triageResult.hospitals.map((h, i) => (
                        <div key={h.place_id || i}
                          className="p-4 bg-slate-900 rounded-2xl border border-white/5 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 hover:bg-slate-800 transition-all group">
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <span className="w-5 h-5 rounded-full bg-red-500 text-white text-[10px] font-black flex items-center justify-center flex-shrink-0">{i + 1}</span>
                              <h4 className="text-sm font-bold">{h.name}</h4>
                            </div>
                            <div className="flex gap-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest pl-7">
                              <span>{h.distance_km} km</span>
                              {h.rating && <span className="text-amber-500">⭐ {h.rating}</span>}
                              {h.open_now === true && <span className="text-emerald-500">● Open</span>}
                              {h.open_now === false && <span className="text-red-500">● Closed</span>}
                            </div>
                            <div className="flex items-center gap-2 pl-7 mt-1">
                              <PhoneCall className="w-3 h-3 text-emerald-500" />
                              <span className="text-xs font-black text-emerald-500 tracking-tighter">{h.contact || 'No number found'}</span>
                            </div>
                            {h.address && (
                              <p className="text-[10px] text-slate-600 pl-7">{h.address}</p>
                            )}
                          </div>
                          <div className="flex gap-2 w-full sm:w-auto">
                            {h.contact && h.contact !== 'Call 112 for routing' && (
                              <a href={`tel:${h.contact.replace(/\D/g, '')}`}
                                className="flex-1 sm:flex-none flex items-center justify-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-xl text-xs font-bold hover:bg-emerald-500 transition-all">
                                <PhoneCall className="w-3.5 h-3.5" /> CALL
                              </a>
                            )}
                            <a href={h.maps_url} target="_blank" rel="noopener noreferrer"
                              className="p-2 bg-slate-800 rounded-xl hover:bg-blue-500 hover:text-white transition-all text-slate-400">
                              <ExternalLink className="w-4 h-4" />
                            </a>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-6 text-slate-500 text-sm">
                      {location ? 'No hospitals found nearby. Enable location for accurate results.' : 'Enable location to find nearby hospitals.'}
                    </div>
                  )}
                </div>
              </div>

              {/* Ambulances */}
              <div className="md:col-span-4 space-y-4">
                <div className="glass-card p-6 space-y-4">
                  <h3 className="text-sm font-bold flex items-center gap-2">
                    <PhoneCall className="w-4 h-4 text-emerald-500" /> {t.dispatch_services}
                  </h3>
                  <div className="space-y-3">
                    {triageResult.ambulances.map((amb, i) => (
                      <div key={i} className="p-3 bg-slate-950 rounded-xl border border-white/5">
                        <div className="flex justify-between items-start">
                          <div>
                            <p className="text-xs font-bold">{amb.service}</p>
                            {amb.eta_info && <p className="text-[10px] text-emerald-500 font-bold mt-0.5">{amb.eta_info}</p>}
                          </div>
                          <a href={`tel:${amb.contact.replace(/\D/g, '')}`}
                            className="p-2 bg-emerald-500/10 text-emerald-500 rounded-lg hover:bg-emerald-500 hover:text-white transition-all">
                            <PhoneCall className="w-4 h-4" />
                          </a>
                        </div>
                        {amb.notes && <p className="text-[10px] text-slate-600 mt-1">{amb.notes}</p>}
                        {amb.maps_url && (
                          <a href={amb.maps_url} target="_blank" rel="noopener noreferrer"
                            className="text-[10px] text-emerald-500 hover:underline flex items-center gap-1 mt-1">
                            <ExternalLink className="w-2.5 h-2.5" /> View on Maps
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                <button onClick={reset} className="btn-secondary w-full text-xs py-3">
                  <RefreshCw className="w-3.5 h-3.5" /> {t.redo_assessment}
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
