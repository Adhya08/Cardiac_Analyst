/**
 * ECGMode — Real ECG analysis via Gemini 2.5 Flash Vision API
 * File upload → FastAPI backend → Gemini analysis → structured 18-condition report
 */
import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { useStore } from '../store/useStore';
import {
  Upload, FileText, CheckCircle2, Zap, AlertTriangle,
  Eye, EyeOff, RefreshCw, ChevronDown, ChevronUp,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { api, type ECGResponse, type ECGCondition } from '../lib/api';

type AnalysisStatus = 'idle' | 'uploading' | 'analyzing' | 'done' | 'error';

const SEVERITY_COLORS = {
  detected: { bg: 'bg-red-500/15', border: 'border-red-500/30', badge: 'bg-red-500 text-white', bar: 'bg-red-500', text: 'text-red-400' },
  possible: { bg: 'bg-amber-500/10', border: 'border-amber-500/20', badge: 'bg-amber-500/20 text-amber-400', bar: 'bg-amber-500', text: 'text-amber-400' },
  normal: { bg: '', border: 'border-transparent', badge: 'bg-slate-800 text-slate-500', bar: 'bg-slate-700', text: 'text-slate-600' },
};

const URGENCY_CONFIG = {
  emergency: { label: '🚨 EMERGENCY', bg: 'bg-red-600', desc: 'Immediate medical attention required.' },
  see_doctor_today: { label: '⚠️ SEE DOCTOR TODAY', bg: 'bg-amber-500/80', desc: 'Visit a cardiologist within 24 hours.' },
  routine: { label: '✅ ROUTINE', bg: 'bg-emerald-600', desc: 'No urgent action needed. Follow up with your doctor.' },
};

// Condition row component
const ConditionRow: React.FC<{ cond: ECGCondition; language: 'en' | 'hi' }> = ({ cond, language }) => {
  const [expanded, setExpanded] = useState(false);
  const s = SEVERITY_COLORS[cond.severity];
  const pct = Math.round(cond.probability * 100);

  if (cond.severity === 'normal' && pct < 10) {
    // Collapse low-probability normal findings
    return null;
  }

  return (
    <div className={`rounded-xl border p-3 transition-all ${s.bg} ${s.border}`}>
      <div className="flex items-center justify-between gap-3 cursor-pointer" onClick={() => setExpanded(e => !e)}>
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <span className={`text-[9px] font-black px-2 py-0.5 rounded-full uppercase tracking-wider flex-shrink-0 ${s.badge}`}>
            {cond.severity}
          </span>
          <span className={`text-xs font-semibold truncate ${cond.severity !== 'normal' ? 'text-slate-200' : 'text-slate-500'}`}>
            {cond.name}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-xs font-black ${s.text}`}>{pct}%</span>
          {cond.severity !== 'normal' && (
            expanded ? <ChevronUp className="w-3 h-3 text-slate-500" /> : <ChevronDown className="w-3 h-3 text-slate-500" />
          )}
        </div>
      </div>

      {/* Probability bar */}
      <div className="h-1 w-full bg-slate-800/60 rounded-full overflow-hidden mt-2">
        <motion.div initial={{ width: 0 }} animate={{ width: `${pct}%` }} transition={{ duration: 0.6 }}
          className={`h-full rounded-full ${s.bar}`} />
      </div>

      {/* Expanded explanation */}
      <AnimatePresence>
        {expanded && cond.severity !== 'normal' && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
            <div className="mt-3 pt-3 border-t border-white/5 space-y-2">
              <p className="text-xs text-slate-300 leading-relaxed">
                {language === 'hi' && cond.explanation_hi ? cond.explanation_hi : cond.explanation_en}
              </p>
              {cond.key_finding && (
                <p className="text-[10px] text-slate-500 font-mono">🔍 {cond.key_finding}</p>
              )}
              {cond.leads_affected.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {cond.leads_affected.map(l => (
                    <span key={l} className="text-[9px] px-1.5 py-0.5 bg-slate-800 rounded text-slate-400">{l}</span>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

// ─────────────────────────────────────────────
// Main ECGMode
// ─────────────────────────────────────────────
export const ECGMode: React.FC = () => {
  const { user, language, setMode } = useStore();
  const [status, setStatus] = useState<AnalysisStatus>('idle');
  const [result, setResult] = useState<ECGResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [showHeatmap, setShowHeatmap] = useState(true);
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      setFile(acceptedFiles[0]);
      handleUpload(acceptedFiles[0]);
    }
  }, [user]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/jpeg': [], 'image/png': [], 'image/webp': [], 'application/pdf': [] },
    maxFiles: 1,
    multiple: false,
  });

  const handleUpload = async (f: File) => {
    setStatus('uploading');
    setProgress(20);
    setErrorMsg('');

    const ctx = {
      age: user?.age,
      sex: user?.sex,
      conditions: [
        user?.is_smoker && 'Smoker',
        user?.is_diabetic && 'Diabetes',
        user?.has_family_history && 'Family history of heart disease',
      ].filter(Boolean).join(', '),
    };

    try {
      setProgress(40);
      setStatus('analyzing');
      setProgress(70);

      const ecgResult = await api.uploadECG(f, ctx);
      setProgress(100);
      setResult(ecgResult);
      setStatus('done');

      // Auto-switch to emergency mode if life-threatening
      if (ecgResult.urgency === 'emergency') {
        setTimeout(() => setMode('emergency'), 3000);
      }
    } catch (err: any) {
      setStatus('error');
      setErrorMsg(err.message || 'ECG analysis failed. Make sure the backend is running.');
      setProgress(0);
    }
  };

  const reset = () => { setStatus('idle'); setResult(null); setFile(null); setProgress(0); setErrorMsg(''); };

  // ── Urgency banner
  const urgencyConfig = result ? URGENCY_CONFIG[result.urgency] : null;

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <header className="flex items-start justify-between">
        <div>
          <h2 className="text-3xl font-bold">ECG Diagnostic</h2>
          <p className="text-slate-400 text-sm">18-condition AI analysis using <strong className="text-emerald-400">Gemini 2.5 Flash Vision</strong></p>
        </div>
        {status === 'done' && (
          <button onClick={reset} className="btn-secondary text-xs py-2">
            <RefreshCw className="w-3.5 h-3.5" /> New Upload
          </button>
        )}
      </header>

      {/* ── Upload Zone (idle) ── */}
      {status === 'idle' && (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
          {...(getRootProps() as any)}
          className={`glass-card p-16 border-dashed border-2 flex flex-col items-center justify-center gap-6 cursor-pointer transition-all ${isDragActive ? 'border-emerald-500 bg-emerald-500/5' : 'border-emerald-500/30 hover:border-emerald-500/50 hover:bg-emerald-500/5'} group`}
        >
          <input {...getInputProps()} />
          <div className={`w-20 h-20 rounded-full bg-emerald-500/10 flex items-center justify-center transition-transform ${isDragActive ? 'scale-110' : 'group-hover:scale-110'}`}>
            <Upload className="text-emerald-500 w-8 h-8" />
          </div>
          <div className="text-center">
            <h3 className="text-xl font-bold">{isDragActive ? 'Drop your ECG here' : 'Upload ECG Study'}</h3>
            <p className="text-slate-500 text-sm mt-2">Drag & drop or click — JPG, PNG, WebP, PDF supported</p>
          </div>
          <div className="flex gap-3 flex-wrap justify-center">
            {['12-Lead ECG', 'Gemini Vision AI', 'No Mock Data'].map(tag => (
              <span key={tag} className="text-[10px] font-bold py-1 px-3 bg-slate-800 rounded-full text-slate-400 uppercase tracking-widest">{tag}</span>
            ))}
          </div>
        </motion.div>
      )}

      {/* ── Loading ── */}
      {(status === 'uploading' || status === 'analyzing') && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass-card p-16 flex flex-col items-center gap-8 text-center">
          <div className="relative">
            <div className="w-24 h-24 border-4 border-emerald-500/20 border-t-emerald-500 rounded-full animate-spin" />
            <Zap className="absolute inset-0 m-auto text-emerald-500 w-8 h-8 animate-pulse" />
          </div>
          <div className="space-y-2">
            <h3 className="text-xl font-bold uppercase tracking-widest animate-pulse">
              {status === 'uploading' ? 'Uploading ECG…' : 'Gemini AI Analysis…'}
            </h3>
            <p className="text-slate-400 text-sm">
              {status === 'uploading' ? 'Securing transmission to backend…' : 'Gemini 2.5 Flash Vision analysing 18 cardiac conditions…'}
            </p>
          </div>
          <div className="w-72 h-2 bg-slate-800 rounded-full overflow-hidden">
            <motion.div animate={{ width: `${progress}%` }} transition={{ duration: 0.5 }}
              className="h-full bg-gradient-to-r from-emerald-600 to-emerald-400 rounded-full" />
          </div>
          <p className="text-xs text-slate-600">File: {file?.name}</p>
        </motion.div>
      )}

      {/* ── Error ── */}
      {status === 'error' && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass-card p-8 border-red-500/20 text-center space-y-4">
          <AlertTriangle className="w-12 h-12 text-red-400 mx-auto" />
          <h3 className="text-lg font-bold text-red-300">Analysis Failed</h3>
          <p className="text-slate-400 text-sm">{errorMsg}</p>
          <button onClick={reset} className="btn-secondary">Try Again</button>
        </motion.div>
      )}

      {/* ── Results ── */}
      {status === 'done' && result && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
          {/* Urgency banner */}
          {urgencyConfig && (
            <div className={`p-4 rounded-2xl ${urgencyConfig.bg} text-white flex items-center justify-between gap-4`}>
              <div>
                <p className="font-black text-lg uppercase tracking-wide">{urgencyConfig.label}</p>
                <p className="text-sm opacity-80">{urgencyConfig.desc}</p>
              </div>
              {result.urgency === 'emergency' && (
                <a href="tel:112" className="bg-white text-red-600 px-6 py-3 rounded-xl font-black text-lg hover:scale-105 transition-transform">
                  📞 Call 112
                </a>
              )}
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            {/* Left: ECG visualizer + report */}
            <div className="lg:col-span-8 space-y-6">

              {/* Measurements */}
              <div className="glass-card overflow-hidden">
                <div className="p-4 border-b border-white/5 flex justify-between items-center bg-slate-900/50">
                  <span className="text-xs font-bold uppercase tracking-widest text-slate-400">ECG Measurements</span>
                  <button onClick={() => setShowHeatmap(!showHeatmap)}
                    className={`text-[10px] font-bold px-3 py-1 rounded-full transition-all ${showHeatmap ? 'bg-emerald-500 text-white' : 'bg-slate-800 text-slate-400'}`}>
                    {showHeatmap ? <><Eye className="w-3 h-3 inline mr-1" />HIGHLIGHTS ON</> : <><EyeOff className="w-3 h-3 inline mr-1" />HIGHLIGHTS OFF</>}
                  </button>
                </div>
                <div className="p-6 grid grid-cols-2 md:grid-cols-5 gap-4">
                  {[
                    { label: 'Heart Rate', value: result.heart_rate_bpm ? `${result.heart_rate_bpm} bpm` : '—', normal: result.heart_rate_bpm ? (result.heart_rate_bpm >= 60 && result.heart_rate_bpm <= 100) : null },
                    { label: 'Rhythm', value: result.rhythm ? result.rhythm.split(' ')[0] : '—', normal: null },
                    { label: 'PR Interval', value: result.pr_interval_ms ? `${result.pr_interval_ms}ms` : '—', normal: result.pr_interval_ms ? (result.pr_interval_ms >= 120 && result.pr_interval_ms <= 200) : null },
                    { label: 'QRS Duration', value: result.qrs_duration_ms ? `${result.qrs_duration_ms}ms` : '—', normal: result.qrs_duration_ms ? result.qrs_duration_ms < 120 : null },
                    { label: 'QTc', value: result.qtc_ms ? `${result.qtc_ms}ms` : '—', normal: result.qtc_ms ? result.qtc_ms < 450 : null },
                  ].map(m => (
                    <div key={m.label} className="text-center">
                      <p className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">{m.label}</p>
                      <p className="text-sm font-black text-white mt-1">{m.value}</p>
                      {m.normal !== null && (
                        <span className={`text-[9px] font-bold uppercase ${m.normal ? 'text-emerald-500' : 'text-red-400'}`}>
                          {m.normal ? 'Normal' : 'Abnormal'}
                        </span>
                      )}
                    </div>
                  ))}
                </div>

                {/* GradCAM highlights */}
                {showHeatmap && result.gradcam_highlights.length > 0 && (
                  <div className="p-4 bg-slate-900/40 border-t border-white/5">
                    <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">AI Attention Highlights (GradCAM)</p>
                    <div className="flex flex-wrap gap-2">
                      {result.gradcam_highlights.map((h, i) => (
                        <span key={i} className={`text-[10px] px-2 py-1 rounded-lg font-medium ${h.severity === 'critical' ? 'bg-red-500/20 text-red-400' : h.severity === 'abnormal' ? 'bg-amber-500/20 text-amber-400' : 'bg-slate-800 text-slate-400'}`}>
                          {h.lead}: {h.finding}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* ST changes */}
                {(result.st_elevation_leads.length > 0 || result.st_depression_leads.length > 0) && (
                  <div className="p-4 bg-red-500/5 border-t border-red-500/10">
                    {result.st_elevation_leads.length > 0 && (
                      <p className="text-xs text-red-400 font-bold">⬆ ST Elevation in: {result.st_elevation_leads.join(', ')}</p>
                    )}
                    {result.st_depression_leads.length > 0 && (
                      <p className="text-xs text-amber-400 font-bold">⬇ ST Depression in: {result.st_depression_leads.join(', ')}</p>
                    )}
                  </div>
                )}
              </div>

              {/* AI Report */}
              <div className="glass-card p-6 space-y-4">
                <h3 className="text-sm font-bold flex items-center gap-2">
                  <FileText className="w-4 h-4 text-emerald-500" />
                  AI Clinical Report (Gemini 2.5 Flash)
                  <span className={`ml-auto text-[9px] px-2 py-0.5 rounded-full uppercase font-bold ${result.image_quality === 'good' ? 'bg-emerald-500/20 text-emerald-400' : result.image_quality === 'fair' ? 'bg-amber-500/20 text-amber-400' : 'bg-red-500/20 text-red-400'}`}>
                    Image: {result.image_quality}
                  </span>
                </h3>
                <p className="text-slate-300 leading-relaxed text-sm">{result.overall_assessment}</p>

                {result.recommendations.length > 0 && (
                  <div className="pt-3 border-t border-white/5">
                    <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Recommendations</p>
                    <ul className="space-y-1">
                      {result.recommendations.map((r, i) => (
                        <li key={i} className="flex gap-2 items-start text-xs text-slate-300">
                          <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full mt-1.5 flex-shrink-0" />
                          {r}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <p className="text-[10px] text-slate-600 italic border-t border-white/5 pt-3">{result.disclaimer}</p>
              </div>
            </div>

            {/* Right: Condition list */}
            <div className="lg:col-span-4 space-y-4">
              <div className="glass-card p-5">
                <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-4 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                  18-Condition Classification
                </h3>
                <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
                  {result.conditions.map(cond => (
                    <ConditionRow key={cond.name} cond={cond} language={language} />
                  ))}
                </div>
              </div>

              <div className="glass-card p-4 text-center space-y-2">
                <p className="text-[10px] text-slate-500 uppercase tracking-wider">Powered By</p>
                <p className="text-sm font-bold text-white">Gemini 2.5 Flash Vision</p>
                <p className="text-[10px] text-slate-600">Real-time medical image analysis</p>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
};
