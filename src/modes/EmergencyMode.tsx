/**
 * EmergencyMode — Real geolocation + Google Places hospital finder + NICE CG95 triage
 * Clinical light workstation design. Minimal interaction steps, rapid accessible triage.
 */
import React, { useState, useEffect } from 'react';
import {
  PhoneCall, MapPin, Navigation, AlertTriangle, ShieldAlert,
  CheckCircle, Info, Loader2, RefreshCw, ExternalLink, MapPinned
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import HospitalMap from '../components/HospitalMap';
import { api, type TriageResponse } from '../lib/api';
import { translations } from '../lib/translations';
import { useStore } from '../store/useStore';
import {
  TRIAGE_QUESTION_DEFS,
  evaluateTriage
} from '../lib/triageEvaluator';

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
      setLocationError('Geolocation not supported by this browser. Using regional fallback.');
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
        setLocationError(`Location access denied: ${err.message}. Using regional center.`);
        setLocation({ lat: 28.6139, lon: 77.2090 });
        setGeoLoading(false);
      },
      { timeout: 10000, enableHighAccuracy: true }
    );
  };

  const handleAnswer = async (qIdx: number, val: boolean) => {
    const next = { ...answers, [qIdx]: val };
    setAnswers(next);

    if (Object.keys(next).length === TRIAGE_QUESTION_DEFS.length) {
      await submitTriage(next);
    }
  };

  const submitTriage = async (finalAnswers: Record<number, boolean>) => {
    setStep('analyzing');
    setApiError(null);

    const symptoms = TRIAGE_QUESTION_DEFS.map((_, i) => finalAnswers[i] ?? false);

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
      // Fallback result — deterministic offline evaluation matching shared rules exactly
      const evalRes = evaluateTriage(finalAnswers);

      setTriageResult({
        ...evalRes,
        hospitals: [],
        ambulances: [
          { service: 'India Emergency (112)', contact: '112', type: 'government', notes: 'National emergency helpline' },
          { service: 'Govt Ambulance (108)', contact: '108', type: 'government', notes: 'Free medical ambulance' },
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

  const totalQuestions = TRIAGE_QUESTION_DEFS.length;
  const progress = (Object.keys(answers).length / totalQuestions) * 100;
  const currentQ = Object.keys(answers).length;
  const isEmergency = triageResult?.severity === 'emergency';
  const isSeeDoctor = triageResult?.severity === 'see_doctor_today' || triageResult?.severity === 'see_doctor';

  const currentDef = TRIAGE_QUESTION_DEFS[currentQ];
  const questionTitle = currentDef
    ? (language === 'hi' && currentDef.text_hi ? currentDef.text_hi : currentDef.text)
    : '';

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Geolocation status bar */}
      <div className={`flex items-center gap-2 text-xs px-4 py-2.5 rounded-xl border ${
        geoLoading
          ? 'bg-slate-50 border-border text-slate-500'
          : locationError
          ? 'bg-amber-50 border-amber-200 text-amber-900'
          : 'bg-emerald-50 border-emerald-200 text-emerald-900'
      }`}>
        {geoLoading ? (
          <><Loader2 className="w-3.5 h-3.5 animate-spin text-slate-400" /> <span>Acquiring GPS location for nearest cardiac facilities...</span></>
        ) : locationError ? (
          <><MapPin className="w-3.5 h-3.5 text-amber-600" /> <span>{locationError}</span></>
        ) : (
          <><MapPin className="w-3.5 h-3.5 text-emerald-600" /> <span>Location acquired ({location?.lat.toFixed(4)}, {location?.lon.toFixed(4)}) — live hospital routing active</span></>
        )}
        {!geoLoading && locationError && (
          <button onClick={getLocation} className="ml-auto text-amber-800 hover:underline flex items-center gap-1 font-bold">
            <RefreshCw className="w-3 h-3" /> Retry
          </button>
        )}
      </div>

      <AnimatePresence mode="wait">
        {/* ── TRIAGE QUESTIONNAIRE ── */}
        {step === 'triage' && (
          <div className="clinical-card p-8 sm:p-12 space-y-8 bg-white border-border">
            <header className="text-center space-y-3">
              <div className="w-14 h-14 bg-red-50 text-red-600 rounded-2xl flex items-center justify-center mx-auto border border-red-200">
                <ShieldAlert className="w-7 h-7" />
              </div>
              <div>
                <h2 className="text-2xl font-black text-navy-850 tracking-tight">{t.emergency_triage}</h2>
                <p className="text-slate-500 text-xs mt-1">{t.triage_tagline}</p>
              </div>
            </header>

            {/* Progress */}
            <div className="space-y-2">
              <div className="flex justify-between text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                <span>{t.question} {currentQ + 1} {t.of} {totalQuestions}</span>
                <span>{Math.round(progress)}% {t.complete}</span>
              </div>
              <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden border border-border">
                <motion.div animate={{ width: `${progress}%` }} className="h-full bg-red-600 rounded-full" />
              </div>
            </div>

            {currentQ < totalQuestions && currentDef ? (
              <div className="space-y-8">
                {/* Category Badge */}
                <div className="flex justify-center">
                  <span className={`text-[11px] font-black tracking-wider uppercase px-3 py-1 rounded-full border ${
                    currentDef.category === 'red_flag'
                      ? 'bg-red-50 border-red-200 text-red-700'
                      : currentDef.category === 'risk_factor'
                      ? 'bg-blue-50 border-blue-200 text-blue-700'
                      : 'bg-amber-50 border-amber-200 text-amber-800'
                  }`}>
                    {currentDef.category === 'red_flag'
                      ? '⚠ Red Flag Symptom'
                      : currentDef.category === 'risk_factor'
                      ? 'Risk Factor Profile'
                      : 'Associated Symptom'}
                  </span>
                </div>

                <div className="min-h-[90px] flex items-center justify-center text-center">
                  <h3 className="text-xl sm:text-2xl font-bold text-navy-850 leading-snug">
                    {questionTitle}
                  </h3>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <button
                    onClick={() => handleAnswer(currentQ, true)}
                    className="py-5 rounded-xl bg-red-600 hover:bg-red-700 text-white font-black text-xl tracking-wider transition-all active:scale-95 shadow-md shadow-red-600/20 uppercase"
                  >
                    {t.yes}
                  </button>
                  <button
                    onClick={() => handleAnswer(currentQ, false)}
                    className="py-5 rounded-xl bg-slate-100 hover:bg-slate-200 text-navy-850 font-black text-xl tracking-wider transition-all active:scale-95 border border-border uppercase"
                  >
                    {t.no}
                  </button>
                </div>
              </div>
            ) : (
              <div className="text-center py-6">
                <p className="text-slate-500 text-xs font-bold">{t.submitting}</p>
              </div>
            )}
          </div>
        )}

        {/* ── ANALYZING ── */}
        {step === 'analyzing' && (
          <div className="clinical-card p-16 flex flex-col items-center gap-6 text-center bg-white">
            <div className="relative">
              <div className="w-16 h-16 border-4 border-red-200 border-t-red-600 rounded-full animate-spin" />
              <ShieldAlert className="absolute inset-0 m-auto text-red-600 w-6 h-6" />
            </div>
            <div>
              <h3 className="text-base font-bold text-navy-850">{t.assessing_situation}</h3>
              <p className="text-slate-500 text-xs mt-1">{t.triage_tagline}</p>
            </div>
          </div>
        )}

        {/* ── RESULT ── */}
        {step === 'result' && triageResult && (
          <div className="space-y-6 animate-in fade-in duration-200">
            {/* STEMI Suspicion Notice */}
            {triageResult.stemi_suspicious && (
              <div className="p-4 rounded-xl bg-red-50 border border-red-200 flex items-center gap-3">
                <AlertTriangle className="text-red-600 w-5 h-5 flex-shrink-0 animate-pulse" />
                <p className="text-red-900 font-bold text-xs">⚠ STEMI HIGH SUSPICION: Immediate emergency care advised. Call 112 immediately.</p>
              </div>
            )}

            {apiError && (
              <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-xs text-red-900 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-sm">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-5 h-5 text-red-600 flex-shrink-0 animate-pulse" />
                  <div>
                    <p className="font-black text-sm">Offline Emergency Protocol Active</p>
                    <p className="text-red-700 font-medium">Server rate-limited or unreachable. Offline rules applied. If experiencing distress, do not wait.</p>
                  </div>
                </div>
                <a
                  href="tel:112"
                  className="flex-shrink-0 bg-red-600 text-white font-black px-4 py-2 rounded-lg hover:bg-red-700 transition-all flex items-center gap-2 shadow"
                >
                  <PhoneCall className="w-4 h-4" /> Call 112 Now
                </a>
              </div>
            )}

            {/* Main Result Card */}
            <div className={`p-6 sm:p-8 rounded-2xl text-white shadow-md space-y-6 ${
              isEmergency
                ? 'bg-red-600'
                : isSeeDoctor
                ? 'bg-amber-600'
                : 'bg-emerald-700'
            }`}>
              <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
                <div className="space-y-1">
                  <h2 className="text-3xl font-black uppercase tracking-tight">
                    {isEmergency
                      ? t.emergency
                      : isSeeDoctor
                      ? t.see_doctor_today
                      : t.no_emergency_warning}
                  </h2>
                  <p className="opacity-90 font-medium text-xs sm:text-sm">
                    {isEmergency
                      ? t.potential_risk
                      : isSeeDoctor
                      ? t.eval_needed
                      : t.symptoms_non_emergent}
                  </p>
                  <p className="text-xs opacity-80 font-mono">
                    Confidence: {(triageResult.confidence * 100).toFixed(0)}% · Calculated Risk: {triageResult.risk_score.toFixed(0)}%
                  </p>
                </div>
                {isEmergency && (
                  <a
                    href="tel:112"
                    className="flex items-center gap-3 bg-white text-red-600 px-6 py-3.5 rounded-xl font-black text-lg hover:scale-105 active:scale-95 transition-all shadow-lg"
                  >
                    <PhoneCall className="w-5 h-5" /> {t.call_112}
                  </a>
                )}
              </div>

              {/* Triage answers count */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-4 border-t border-white/20 text-xs">
                <div className="bg-white/10 p-3 rounded-xl flex items-center gap-3">
                  <MapPinned className="w-4 h-4 text-white" />
                  <div>
                    <p className="text-[10px] font-bold uppercase opacity-80">Location Coordinates</p>
                    <p className="font-mono font-bold">{location ? `${location.lat.toFixed(4)}, ${location.lon.toFixed(4)}` : 'Unavailable'}</p>
                  </div>
                </div>
                <div className="bg-white/10 p-3 rounded-xl flex items-center gap-3">
                  <CheckCircle className="w-4 h-4 text-white" />
                  <div>
                    <p className="text-[10px] font-bold uppercase opacity-80">Reported Items</p>
                    <p className="font-bold">{triageResult.yes_count} of {totalQuestions} questions answered YES</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Instructions Card */}
            <div className="clinical-card p-5 bg-white space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-navy-850 flex items-center gap-2">
                <Info className="w-4 h-4 text-teal-600" />
                Clinical Instructions
              </h3>
              <ul className="space-y-2">
                {triageResult.instructions.map((inst, i) => (
                  <li key={i} className="flex gap-2.5 items-start text-xs text-slate-700">
                    <span className="w-1.5 h-1.5 bg-teal-600 rounded-full mt-1.5 flex-shrink-0" />
                    <span>{inst}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Hospitals + Ambulances Grid */}
            <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
              {/* Nearby Hospitals (8 Cols) */}
              <div className="md:col-span-8 space-y-4">
                <div className="clinical-card p-5 space-y-4 bg-white">
                  <div className="flex items-center justify-between border-b border-border pb-3">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-navy-850 flex items-center gap-2">
                      <Navigation className="w-4 h-4 text-teal-600" />
                      {t.nearest_hospitals}
                    </h3>
                    <span className="text-[10px] text-slate-400 font-mono">Live Google Places API</span>
                  </div>

                  {location && triageResult.hospitals.length > 0 && (
                    <HospitalMap userLat={location.lat} userLon={location.lon} hospitals={triageResult.hospitals} />
                  )}

                  {triageResult.hospitals.length > 0 ? (
                    <div className="space-y-3">
                      {triageResult.hospitals.map((h, i) => (
                        <div
                          key={h.place_id || i}
                          className="p-4 bg-surface-secondary rounded-xl border border-border flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 hover:border-slate-300 transition-all"
                        >
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <span className="w-5 h-5 rounded-full bg-red-600 text-white text-[10px] font-black flex items-center justify-center flex-shrink-0">
                                {i + 1}
                              </span>
                              <h4 className="text-xs font-bold text-navy-850">{h.name}</h4>
                            </div>
                            <div className="flex gap-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider pl-7 font-mono">
                              <span className="text-teal-700">{h.distance_km} km</span>
                              {h.rating && <span className="text-amber-700">⭐ {h.rating}</span>}
                              {h.open_now === true && <span className="text-emerald-700">● Open</span>}
                              {h.open_now === false && <span className="text-red-600">● Closed</span>}
                            </div>
                            {h.address && <p className="text-[11px] text-slate-500 pl-7">{h.address}</p>}
                          </div>

                          <div className="flex gap-2 w-full sm:w-auto">
                            {h.contact && (
                              <a
                                href={`tel:${h.contact.replace(/\D/g, '')}`}
                                className="btn-clinical-primary text-xs py-1.5 px-3 flex-1 sm:flex-none"
                              >
                                <PhoneCall className="w-3 h-3" />
                                <span>CALL</span>
                              </a>
                            )}
                            <a
                              href={h.maps_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="btn-clinical-secondary p-2"
                              title="Directions on Google Maps"
                            >
                              <ExternalLink className="w-3.5 h-3.5" />
                            </a>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-6 text-slate-400 text-xs">
                      {location ? 'No hospital facilities returned for this radius.' : 'Enable browser location to view nearby cardiac hospitals.'}
                    </div>
                  )}
                </div>
              </div>

              {/* Dispatch Services & Redo (4 Cols) */}
              <div className="md:col-span-4 space-y-4">
                <div className="clinical-card p-5 space-y-4 bg-white">
                  <div className="flex items-center justify-between border-b border-border pb-3">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-navy-850 flex items-center gap-2">
                      <PhoneCall className="w-4 h-4 text-teal-600" />
                      {t.dispatch_services}
                    </h3>
                  </div>

                  <div className="space-y-2.5">
                    {triageResult.ambulances.map((amb, i) => (
                      <div key={i} className="p-3 bg-surface-secondary rounded-xl border border-border">
                        <div className="flex justify-between items-start">
                          <div>
                            <p className="text-xs font-bold text-navy-850">{amb.service}</p>
                            {amb.eta_info && <p className="text-[10px] text-teal-700 font-bold mt-0.5">{amb.eta_info}</p>}
                          </div>
                          <a
                            href={`tel:${amb.contact.replace(/\D/g, '')}`}
                            className="btn-clinical-primary p-2 text-xs"
                          >
                            <PhoneCall className="w-3 h-3" />
                          </a>
                        </div>
                        {amb.notes && <p className="text-[10px] text-slate-500 mt-1">{amb.notes}</p>}
                      </div>
                    ))}
                  </div>
                </div>

                <button onClick={reset} className="btn-clinical-secondary w-full text-xs py-2.5">
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>{t.redo_assessment}</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};
