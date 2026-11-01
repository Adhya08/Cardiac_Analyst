/**
 * ECGMode — 12-lead digital signal analysis via PTB-XL trained ResNet1D model.
 * Zero GenAI / Zero Gemini — deterministic local inference via ONNX Runtime.
 * Strictly 5 diagnostic superclasses: NORM, MI, STTC, CD, HYP.
 */
import React, { useState, useCallback, useEffect } from 'react';
import { useDropzone, type FileRejection } from 'react-dropzone';
import { useStore } from '../store/useStore';
import {
  Upload, FileText, CheckCircle2, Zap, AlertTriangle,
  RefreshCw, ChevronDown, ChevronUp, Clock, ExternalLink, Heart, ShieldAlert,
  AlertCircle, BarChart3, Activity, XCircle, FileWarning, RotateCcw,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { api, type ECGResponse, type ECGCondition } from '../lib/api';
import { translations } from '../lib/translations';

export const formatScorePercentage = (score: number | null | undefined): string => {
  if (score == null || isNaN(score)) return '—';
  const val = score * 100;
  if (val >= 99.95) return '>99.9%';
  if (val > 0 && val < 0.1) return '<0.1%';
  return `${val.toFixed(1)}%`;
};

type AnalysisStatus = 'idle' | 'uploading' | 'analyzing' | 'done' | 'error';

// Verified benchmarks from EVALUATION_REPORT.md (Fold 10 strictly held-out test set, 2,158 records)
const REAL_BENCHMARK = {
  dataset: 'PhysioNet PTB-XL v1.0.3 (Fold 10 Held-Out)',
  records: 2158,
  patients: 1877,
  macroAuroc: 0.9265,
  macroAurocCi: [0.9194, 0.9330],
  macroAuprc: 0.8196,
  macroAuprcCi: [0.8038, 0.8351],
  macroF1: 0.7520,
  macroF1Ci: [0.7350, 0.7658],
  macroSens: 0.7725,
  macroSensCi: [0.7546, 0.7891],
  macroSpec: 0.8985,
  macroSpecCi: [0.8924, 0.9045],
  classes: [
    { code: 'NORM', name: 'Normal ECG', threshold: 0.51, auroc: 0.9447, auprc: 0.9249, sens: '94.70%', spec: '79.75%', f1: 0.8616 },
    { code: 'MI', name: 'Myocardial Infarction', threshold: 0.41, auroc: 0.9244, auprc: 0.8288, sens: '80.00%', spec: '87.81%', f1: 0.7420 },
    { code: 'STTC', name: 'ST/T Changes', threshold: 0.70, auroc: 0.9351, auprc: 0.8314, sens: '80.04%', spec: '91.63%', f1: 0.7758 },
    { code: 'CD', name: 'Conduction Disturbance', threshold: 0.66, auroc: 0.9259, auprc: 0.8509, sens: '75.81%', spec: '93.86%', f1: 0.7721 },
    { code: 'HYP', name: 'Hypertrophy', threshold: 0.75, auroc: 0.9021, auprc: 0.6621, sens: '55.73%', spec: '96.20%', f1: 0.6083 },
  ],
};

const SEVERITY_CONFIG = {
  detected: {
    bg: 'bg-red-500/10',
    border: 'border-red-500/30',
    badge: 'bg-red-500 text-white',
    bar: 'bg-red-500',
    text: 'text-red-400',
    statusLabel: 'DETECTED',
  },
  possible: {
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/20',
    badge: 'bg-amber-500/20 text-amber-400 border border-amber-500/30',
    bar: 'bg-amber-500',
    text: 'text-amber-400',
    statusLabel: 'BORDERLINE',
  },
  normal: {
    bg: 'bg-slate-900/40',
    border: 'border-slate-800',
    badge: 'bg-slate-800 text-slate-400',
    bar: 'bg-emerald-500',
    text: 'text-slate-400',
    statusLabel: 'NOT DETECTED',
  },
  unavailable: {
    bg: 'bg-slate-900/40',
    border: 'border-slate-800',
    badge: 'bg-slate-800 text-slate-500',
    bar: 'bg-slate-700',
    text: 'text-slate-500',
    statusLabel: 'UNAVAILABLE',
  },
};

const URGENCY_CONFIG = {
  emergency: {
    label: '🚨 EMERGENCY',
    bg: 'bg-red-600',
    desc: 'Immediate emergency evaluation advised. Model flagged features crossing decision threshold for acute injury or infarction (research flag, not a clinical diagnosis).',
  },
  see_doctor_today: {
    label: '⚠️ SEE DOCTOR TODAY',
    bg: 'bg-amber-500/90 text-slate-950',
    desc: 'Abnormal findings detected. Consult a physician or cardiologist for clinical correlation.',
  },
  routine: {
    label: '✅ ROUTINE FINDINGS',
    bg: 'bg-emerald-600',
    desc: 'No diagnostic superclass exceeded its locked decision threshold. This model output does not rule out underlying cardiovascular disease.',
  },
  unavailable: {
    label: '⏸ ANALYSIS UNAVAILABLE',
    bg: 'bg-slate-700',
    desc: 'Automated analysis could not be completed reliably on the uploaded signal.',
  },
};

// ─────────────────────────────────────────────
// Condition Row Component (Strictly 5 Classes)
// ─────────────────────────────────────────────
const ConditionRow: React.FC<{ cond: ECGCondition; language: 'en' | 'hi' }> = ({ cond, language }) => {
  const [expanded, setExpanded] = useState(false);
  const severityKey = (cond.severity in SEVERITY_CONFIG) ? (cond.severity as keyof typeof SEVERITY_CONFIG) : 'normal';
  const s = SEVERITY_CONFIG[severityKey];
  
  // Model score is explicitly labeled as Model Score [0.0 - 1.0], NOT disease probability
  const score = cond.model_score ?? cond.probability ?? 0;
  const pct = Math.min(100, Math.max(0, Math.round(score * 100)));
  const thresholdPct = Math.round(cond.threshold * 100);

  const isNormDetected = cond.code === 'NORM' && cond.detected;
  const badgeLabel = isNormDetected ? 'NORMAL PATTERN' : s.statusLabel;
  const badgeClass = isNormDetected 
    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' 
    : s.badge;

  const formattedPct = formatScorePercentage(score);
  const formattedScore = score >= 0.9995 ? '>0.999' : (score > 0 && score < 0.001) ? '<0.001' : score.toFixed(3);

  return (
    <div className={`rounded-xl border p-3.5 transition-all ${s.bg} ${s.border}`}>
      <div className="flex items-center justify-between gap-3 cursor-pointer" onClick={() => setExpanded(e => !e)}>
        <div className="flex items-center gap-2.5 flex-1 min-w-0">
          <span className={`text-[10px] font-black px-2 py-0.5 rounded-full uppercase tracking-wider flex-shrink-0 ${badgeClass}`}>
            {badgeLabel}
          </span>
          <div className="min-w-0">
            <span className="text-xs font-bold text-slate-200 block truncate">
              {cond.name} <span className="text-slate-500 font-mono text-[10px]">({cond.code})</span>
            </span>
            <span className="text-[10px] text-slate-400 font-mono">
              Threshold: {cond.threshold.toFixed(2)} ({thresholdPct}%)
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-right">
            <span className="text-[9px] uppercase tracking-wider text-slate-500 block font-bold">Model Score</span>
            <span className={`text-xs font-mono font-black ${cond.detected ? 'text-red-400' : 'text-slate-300'}`}>
              {formattedScore} ({formattedPct})
            </span>
          </div>
          <button className="text-slate-500 hover:text-slate-300 p-1" aria-label="Toggle details">
            {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* Model Score Bar with locked threshold indicator */}
      <div className="relative h-2 w-full bg-slate-800/80 rounded-full overflow-hidden mt-3">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
          className={`h-full rounded-full ${cond.detected ? 'bg-red-500' : 'bg-emerald-500/80'}`}
        />
        {/* Threshold marker */}
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-amber-400 z-10"
          style={{ left: `${thresholdPct}%` }}
          title={`Locked Decision Threshold: ${cond.threshold.toFixed(2)}`}
        />
      </div>

      {/* Explanation drawer */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-3 pt-3 border-t border-white/5 space-y-2">
              <p className="text-xs text-slate-300 leading-relaxed">
                {language === 'hi' && cond.explanation_hi ? cond.explanation_hi : cond.explanation_en}
              </p>
              {cond.key_finding && (
                <p className="text-[11px] text-slate-400 font-mono bg-slate-900/60 p-2 rounded-lg border border-white/5">
                  🔍 <strong>Finding:</strong> {cond.key_finding}
                </p>
              )}
              {cond.leads_affected && cond.leads_affected.length > 0 && (
                <div className="flex items-center gap-1.5 flex-wrap pt-1">
                  <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Affected Leads:</span>
                  {cond.leads_affected.map(l => (
                    <span key={l} className="text-[10px] font-mono px-2 py-0.5 bg-slate-800 text-slate-300 rounded border border-white/5">
                      {l}
                    </span>
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
  const t = translations[language];
  const [status, setStatus] = useState<AnalysisStatus>('idle');
  const [result, setResult] = useState<ECGResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [showBenchmarkModal, setShowBenchmarkModal] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);
  const [history, setHistory] = useState<any[]>([]);

  const fetchHistory = async () => {
    try {
      const { ecg_sessions } = await api.getECGHistory();
      setHistory(ecg_sessions);
    } catch (err) {
      console.error('Failed to fetch history:', err);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const handleUpload = async (f: File) => {
    // Intercept photos/PDFs with clear friendly message before sending
    const lowerName = f.name.toLowerCase();
    const isImageOrPdf = lowerName.endsWith('.png') || lowerName.endsWith('.jpg') ||
                         lowerName.endsWith('.jpeg') || lowerName.endsWith('.webp') ||
                         lowerName.endsWith('.pdf') || f.type.startsWith('image/') ||
                         f.type === 'application/pdf';

    if (isImageOrPdf) {
      setStatus('error');
      setErrorMsg(
        'Photos, scans, and PDFs of paper ECGs are NOT supported in this version. ' +
        'This model requires raw digital 12-lead voltage timeseries (CSV, NPY, JSON, or WFDB). ' +
        'Please upload digital signal data or try one of the PTB-XL sample buttons below.'
      );
      setFile(f);
      return;
    }

    setStatus('uploading');
    setProgress(20);
    setErrorMsg('');
    setFile(f);

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
      setProgress(75);

      const ecgResult = await api.uploadECG(f, ctx);
      setProgress(100);
      setResult(ecgResult);
      setStatus('done');
      fetchHistory();
    } catch (err: any) {
      setStatus('error');
      setErrorMsg(err.message || 'ECG analysis failed. Make sure the backend server is running.');
      setProgress(0);
    }
  };

  const onDrop = useCallback((acceptedFiles: File[], fileRejections: FileRejection[]) => {
    if (fileRejections.length > 0) {
      const rejectedFile = fileRejections[0].file;
      setStatus('error');
      setErrorMsg(
        `File "${rejectedFile.name}" is not an accepted digital signal format. ` +
        'Photos and PDFs are NOT supported yet. Please upload a .csv, .npy, .json, or WFDB .dat/.hea file.'
      );
      return;
    }
    if (acceptedFiles.length > 0) {
      handleUpload(acceptedFiles[0]);
    }
  }, [user]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
      'application/json': ['.json'],
      'text/plain': ['.txt'],
      'application/octet-stream': ['.npy', '.dat'],
      'application/x-netcdf': ['.hea'],
    },
    maxFiles: 1,
    multiple: false,
  });

  const reset = () => {
    setStatus('idle');
    setResult(null);
    setFile(null);
    setProgress(0);
    setErrorMsg('');
  };

  const runDemoScan = async (filename: string, displayName: string) => {
    try {
      setStatus('uploading');
      setProgress(25);
      setErrorMsg('');

      const res = await fetch(`/demo_ecgs/${filename}`);
      if (!res.ok) throw new Error(`Failed to load ${filename}`);
      const blob = await res.blob();
      const ext = filename.split('.').pop()?.toLowerCase();
      const mime = ext === 'csv' ? 'text/csv' : ext === 'json' ? 'application/json' : ext === 'png' ? 'image/png' : 'application/octet-stream';
      const demoFile = new File([blob], displayName, { type: mime });
      
      // Let handleUpload validate or process
      await handleUpload(demoFile);
    } catch (err: any) {
      setStatus('error');
      setErrorMsg(err.message || 'Demo ECG analysis failed.');
      setProgress(0);
    }
  };

  const urgencyConfig = result && result.urgency ? URGENCY_CONFIG[result.urgency as keyof typeof URGENCY_CONFIG] || URGENCY_CONFIG.routine : null;

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* ── Header ── */}
      <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-3xl font-bold tracking-tight">{t.ecg_diagnostic}</h2>
            <span className="text-[10px] font-mono px-2.5 py-1 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold uppercase tracking-wider">
              ResNet1D · PTB-XL
            </span>
          </div>
          <p className="text-slate-400 text-sm mt-1">{t.ecg_tagline}</p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowBenchmarkModal(!showBenchmarkModal)}
            className="btn-secondary text-xs py-2 px-3 flex items-center gap-2"
          >
            <BarChart3 className="w-3.5 h-3.5 text-emerald-400" />
            Fold 10 Real Metrics
          </button>
          {status === 'done' && (
            <button onClick={reset} className="btn-secondary text-xs py-2">
              <RefreshCw className="w-3.5 h-3.5" /> {t.new_upload}
            </button>
          )}
        </div>
      </header>

      {/* ── Real Performance Benchmark Modal/Drawer ── */}
      <AnimatePresence>
        {showBenchmarkModal && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="glass-card p-6 border-emerald-500/30 overflow-hidden"
          >
            <div className="flex items-start justify-between mb-4 border-b border-white/5 pb-3">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-emerald-400" />
                  Verified Evaluation Report (PTB-XL Benchmark Fold 10)
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Evaluated on <strong>2,158 strictly held-out test records</strong> (1,877 unique patients) with thresholds locked on Fold 9.
                  Source: <span className="font-mono text-emerald-400">backend/models/EVALUATION_REPORT.md</span>
                </p>
              </div>
              <button
                onClick={() => setShowBenchmarkModal(false)}
                className="text-slate-500 hover:text-white text-xs px-2 py-1 bg-slate-800 rounded"
              >
                Close ✕
              </button>
            </div>

            {/* Macro Stats */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
              {[
                { label: 'Macro AUROC', val: REAL_BENCHMARK.macroAuroc.toFixed(4), ci: `[${REAL_BENCHMARK.macroAurocCi[0]}, ${REAL_BENCHMARK.macroAurocCi[1]}]` },
                { label: 'Macro AUPRC', val: REAL_BENCHMARK.macroAuprc.toFixed(4), ci: `[${REAL_BENCHMARK.macroAuprcCi[0]}, ${REAL_BENCHMARK.macroAuprcCi[1]}]` },
                { label: 'Macro F1', val: REAL_BENCHMARK.macroF1.toFixed(4), ci: `[${REAL_BENCHMARK.macroF1Ci[0]}, ${REAL_BENCHMARK.macroF1Ci[1]}]` },
                { label: 'Macro Sensitivity', val: `${(REAL_BENCHMARK.macroSens * 100).toFixed(2)}%`, ci: `[${REAL_BENCHMARK.macroSensCi[0]}, ${REAL_BENCHMARK.macroSensCi[1]}]` },
                { label: 'Macro Specificity', val: `${(REAL_BENCHMARK.macroSpec * 100).toFixed(2)}%`, ci: `[${REAL_BENCHMARK.macroSpecCi[0]}, ${REAL_BENCHMARK.macroSpecCi[1]}]` },
              ].map(stat => (
                <div key={stat.label} className="p-3 bg-slate-900/60 rounded-xl border border-white/5 text-center">
                  <p className="text-[10px] text-slate-400 uppercase font-bold">{stat.label}</p>
                  <p className="text-base font-black text-white mt-1">{stat.val}</p>
                  <p className="text-[9px] text-slate-500 font-mono mt-0.5">95% CI {stat.ci}</p>
                </div>
              ))}
            </div>

            {/* Per-class Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400 font-bold uppercase text-[10px]">
                    <th className="py-2 px-3">Class</th>
                    <th className="py-2 px-3">Description</th>
                    <th className="py-2 px-3 text-right">Threshold</th>
                    <th className="py-2 px-3 text-right">AUROC</th>
                    <th className="py-2 px-3 text-right">AUPRC</th>
                    <th className="py-2 px-3 text-right">Sensitivity</th>
                    <th className="py-2 px-3 text-right">Specificity</th>
                    <th className="py-2 px-3 text-right">F1 Score</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 font-mono text-[11px]">
                  {REAL_BENCHMARK.classes.map(row => (
                    <tr key={row.code} className="hover:bg-white/5 transition-colors">
                      <td className="py-2 px-3 font-bold text-emerald-400">{row.code}</td>
                      <td className="py-2 px-3 font-sans text-slate-300">{row.name}</td>
                      <td className="py-2 px-3 text-right text-slate-400">{row.threshold.toFixed(2)}</td>
                      <td className="py-2 px-3 text-right text-slate-200">{row.auroc.toFixed(4)}</td>
                      <td className="py-2 px-3 text-right text-slate-200">{row.auprc.toFixed(4)}</td>
                      <td className="py-2 px-3 text-right text-slate-200">{row.sens}</td>
                      <td className="py-2 px-3 text-right text-slate-200">{row.spec}</td>
                      <td className="py-2 px-3 text-right font-bold text-white">{row.f1.toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Upload Zone (idle) ── */}
      {status === 'idle' && (
        <div className="space-y-6">
          {/* Photos/PDFs Unsupported Notice Banner */}
          <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/25 flex items-start gap-3">
            <FileWarning className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="text-xs font-bold text-amber-300">
                {t.photo_pdf_unsupported_title}
              </p>
              <p className="text-xs text-amber-200/80 leading-relaxed">
                {t.photo_pdf_unsupported_desc}
              </p>
            </div>
          </div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            {...(getRootProps() as any)}
            className={`glass-card p-14 border-dashed border-2 flex flex-col items-center justify-center gap-5 cursor-pointer transition-all ${
              isDragActive
                ? 'border-emerald-500 bg-emerald-500/10'
                : 'border-emerald-500/30 hover:border-emerald-500/50 hover:bg-emerald-500/5'
            } group`}
          >
            <input {...getInputProps()} />
            <div
              className={`w-16 h-16 rounded-2xl bg-emerald-500/10 flex items-center justify-center transition-transform ${
                isDragActive ? 'scale-110' : 'group-hover:scale-110'
              }`}
            >
              <Upload className="text-emerald-500 w-8 h-8" />
            </div>
            <div className="text-center">
              <h3 className="text-lg font-bold text-white">{t.upload_zone_title}</h3>
              <p className="text-slate-400 text-xs mt-1.5 max-w-md mx-auto">{t.upload_zone_desc}</p>
            </div>
            <div className="flex gap-2 flex-wrap justify-center pt-2">
              {['12-Lead Digital', '100 Hz', 'CSV / NPY / JSON / WFDB', 'ResNet1D (ONNX)'].map(tag => (
                <span
                  key={tag}
                  className="text-[9px] font-mono font-bold py-1 px-2.5 bg-slate-900 border border-white/5 rounded-full text-slate-400 uppercase tracking-wider"
                >
                  {tag}
                </span>
              ))}
            </div>
          </motion.div>
        </div>
      )}

      {/* ── Error Banner (Centered Try Again button) ── */}
      {status === 'error' && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-8 border-red-500/30 text-center space-y-4">
          <AlertTriangle className="w-10 h-10 text-red-400 mx-auto" />
          <h3 className="text-base font-bold text-red-300">{t.analysis_failed}</h3>
          <p className="text-slate-300 text-xs max-w-xl mx-auto leading-relaxed">{errorMsg}</p>
          <div className="pt-2 flex justify-center items-center">
            <button
              onClick={reset}
              className="btn-secondary text-xs px-6 py-2.5 mx-auto flex items-center justify-center gap-2 hover:bg-slate-700 active:scale-95 transition-all shadow-md"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>{t.try_again}</span>
            </button>
          </div>
        </motion.div>
      )}

      {/* ── Quick Trial Section (Real PTB-XL Held-Out Benchmark Records) ── */}
      {(status === 'idle' || status === 'error') && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass-card p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
              <Zap className="w-4 h-4 text-emerald-400" />
              Test Real PTB-XL Held-Out Benchmark Records (Fold 10)
            </h4>
            <span className="text-[10px] text-slate-500 font-mono">10-second 12-lead digital files</span>
          </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {[
                { file: 'sample_ecg_NORM.csv', label: 'Normal Sinus Rhythm', code: 'NORM', color: 'emerald', icon: Heart, desc: 'Fold 10 held-out test sample' },
                { file: 'sample_ecg_MI.csv', label: 'Myocardial Infarction', code: 'MI', color: 'red', icon: ShieldAlert, desc: 'Fold 10 held-out test sample' },
                { file: 'sample_ecg_STTC.csv', label: 'ST/T Changes', code: 'STTC', color: 'amber', icon: Zap, desc: 'Fold 10 held-out test sample' },
                { file: 'sample_ecg_CD.csv', label: 'Conduction Disturbance', code: 'CD', color: 'purple', icon: Activity, desc: 'Fold 10 held-out test sample' },
                { file: 'sample_ecg_HYP.csv', label: 'Hypertrophy', code: 'HYP', color: 'blue', icon: Heart, desc: 'Fold 10 held-out test sample' },
              ].map(item => (
                <div
                  key={item.code}
                  onClick={(e) => { e.stopPropagation(); runDemoScan(item.file, item.file); }}
                  className="p-3.5 rounded-xl border border-slate-800 bg-slate-900/40 hover:border-emerald-500/40 hover:bg-emerald-500/5 transition-all cursor-pointer flex items-center justify-between group"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-9 h-9 rounded-lg bg-slate-800 flex items-center justify-center flex-shrink-0 group-hover:bg-emerald-500/20 transition-colors">
                      <item.icon className="w-4 h-4 text-slate-300 group-hover:text-emerald-400" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs font-bold text-slate-200 truncate">{item.label}</p>
                      <p className="text-[10px] text-slate-500 font-mono">{item.code} · {item.desc}</p>
                    </div>
                  </div>
                  <span className="text-[10px] font-black text-emerald-400 opacity-0 group-hover:opacity-100 transition-opacity pl-2">
                    RUN &rarr;
                  </span>
                </div>
              ))}
            </div>

            {/* Validation & Rejection Testing Section */}
            <div className="pt-3 border-t border-white/5">
              <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2.5">
                Edge-Case & Validation Testing (Verify Defensive Handling)
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => runDemoScan('normal_ecg_sample.png', 'paper_scan.png')}
                  className="p-3 rounded-xl border border-amber-500/20 bg-amber-500/5 hover:bg-amber-500/10 text-left transition-colors flex items-center justify-between group"
                >
                  <div className="flex items-center gap-2.5">
                    <XCircle className="w-4 h-4 text-amber-400 flex-shrink-0" />
                    <div>
                      <p className="text-xs font-bold text-amber-200">Test Photo/PDF Rejection</p>
                      <p className="text-[10px] text-slate-400">Attempts upload of paper image (.png) &rarr; friendly error</p>
                    </div>
                  </div>
                  <span className="text-[10px] font-mono text-amber-400 font-bold group-hover:translate-x-0.5 transition-transform">TEST &rarr;</span>
                </button>

                <button
                  type="button"
                  onClick={() => runDemoScan('flatline_corrupt.csv', 'flatline_sample.csv')}
                  className="p-3 rounded-xl border border-red-500/20 bg-red-500/5 hover:bg-red-500/10 text-left transition-colors flex items-center justify-between group"
                >
                  <div className="flex items-center gap-2.5">
                    <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                    <div>
                      <p className="text-xs font-bold text-red-200">Test Flatline / Corrupted Signal</p>
                      <p className="text-[10px] text-slate-400">Zero-variance signal &rarr; triggers "analysis unavailable"</p>
                    </div>
                  </div>
                  <span className="text-[10px] font-mono text-red-400 font-bold group-hover:translate-x-0.5 transition-transform">TEST &rarr;</span>
                </button>
              </div>
            </div>
          </motion.div>
      )}

      {/* ── Recent History (Idle or Error) ── */}
      {(status === 'idle' || status === 'error') && history.length > 0 && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
          <div className="flex items-center gap-2 text-slate-400 mb-2">
            <Clock className="w-4 h-4" />
            <h3 className="text-xs font-bold uppercase tracking-widest">{t.recent_studies}</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {history.slice(0, 6).map((item) => (
              <div
                key={item.ecg_id}
                className="glass-card p-4 hover:border-emerald-500/50 transition-colors group cursor-pointer"
                onClick={async () => {
                  setStatus('analyzing');
                  try {
                    const full = await api.getECGAnalysis(item.ecg_id);
                    setResult(full);
                    setStatus('done');
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                  } catch (e) {
                    setStatus('error');
                    setErrorMsg('Failed to load study from database.');
                  }
                }}
              >
                <div className="flex justify-between items-start mb-3">
                  <div
                    className={`text-[9px] font-black px-2 py-0.5 rounded-full uppercase ${
                      item.urgency === 'emergency'
                        ? 'bg-red-500 text-white'
                        : item.urgency === 'see_doctor_today'
                        ? 'bg-amber-500 text-black'
                        : 'bg-slate-800 text-slate-400'
                    }`}
                  >
                    {(item.urgency || 'routine').replace(/_/g, ' ')}
                  </div>
                  <span className="text-[10px] text-slate-500 font-mono">
                    {new Date(item.timestamp).toLocaleDateString()}
                  </span>
                </div>
                <h4 className="text-xs font-bold text-slate-200 truncate mb-1">
                  {item.top_condition || 'Normal Digital Scan'}
                </h4>
                <div className="flex items-center justify-between mt-3 pt-2 border-t border-white/5">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[9px] text-slate-500 font-mono uppercase">Top Score:</span>
                    <span className="text-xs font-mono font-bold text-emerald-400">
                      {formatScorePercentage(item.top_condition_prob)}
                    </span>
                  </div>
                  <button className="text-emerald-500 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1 text-[10px] font-bold uppercase">
                    {t.view} <ExternalLink className="w-3 h-3" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* ── Loading View ── */}
      {(status === 'uploading' || status === 'analyzing') && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass-card p-16 flex flex-col items-center gap-6 text-center">
          <div className="relative">
            <div className="w-20 h-20 border-4 border-emerald-500/20 border-t-emerald-500 rounded-full animate-spin" />
            <Activity className="absolute inset-0 m-auto text-emerald-500 w-7 h-7 animate-pulse" />
          </div>
          <div className="space-y-2">
            <h3 className="text-lg font-bold uppercase tracking-wider text-white">
              {status === 'uploading' ? t.uploading_ecg : t.medical_ai_analysis}
            </h3>
            <p className="text-slate-400 text-xs max-w-sm">
              {status === 'uploading'
                ? 'Validating 12-lead digital format and transferring array...'
                : t.analyzing_conditions}
            </p>
          </div>
          <div className="w-64 h-1.5 bg-slate-800 rounded-full overflow-hidden">
            <motion.div
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.4 }}
              className="h-full bg-emerald-500 rounded-full"
            />
          </div>
          {file && <p className="text-[11px] text-slate-500 font-mono">File: {file.name}</p>}
        </motion.div>
      )}



      {/* ── Results View ── */}
      {status === 'done' && result && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">

          {/* 1. Analysis Unavailable State */}
          {result.status === 'analysis_unavailable' && (
            <div className="p-6 rounded-2xl bg-red-950/40 border border-red-500/40 text-red-100 space-y-3">
              <div className="flex items-center gap-3">
                <XCircle className="w-6 h-6 text-red-400 flex-shrink-0" />
                <div>
                  <h3 className="text-base font-bold text-white uppercase tracking-wide">
                    {t.analysis_unavailable_title}
                  </h3>
                  <p className="text-xs text-red-300 mt-0.5">
                    Signal Quality: <span className="font-bold uppercase tracking-wider">{result.quality_status}</span>
                  </p>
                </div>
              </div>
              <div className="p-4 bg-red-900/20 rounded-xl border border-red-500/20 text-xs text-red-200 leading-relaxed">
                <strong>Reason: </strong> {result.abstain_reason || result.overall_assessment}
              </div>
              <p className="text-xs text-slate-300">
                Please re-record the ECG using standard 12-lead electrode placement and ensure 10-second duration at 100 Hz.
              </p>
            </div>
          )}

          {/* 2. Uncertainty Banner */}
          {(result.status === 'uncertain' || result.uncertainty_flag) && result.status !== 'analysis_unavailable' && (
            <div className="p-4 rounded-2xl bg-amber-500/15 border border-amber-500/35 flex items-start gap-3.5">
              <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
              <div className="space-y-1">
                <p className="text-xs font-bold text-amber-300 uppercase tracking-wide">
                  {t.uncertainty_title}
                </p>
                <p className="text-xs text-amber-200/90 leading-relaxed">
                  {result.abstain_reason || t.uncertainty_desc}
                </p>
              </div>
            </div>
          )}

          {/* 3. Urgency Banner */}
          {urgencyConfig && result.status !== 'analysis_unavailable' && (
            <div className={`p-4 rounded-2xl ${urgencyConfig.bg} text-white flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-lg`}>
              <div>
                <p className="font-black text-base uppercase tracking-wide">{urgencyConfig.label}</p>
                <p className="text-xs opacity-90 mt-0.5">{urgencyConfig.desc}</p>
              </div>
              <div className="flex flex-wrap gap-2.5">
                {result.urgency === 'emergency' && (
                  <button
                    onClick={() => setMode('emergency')}
                    className="bg-white/10 border border-white/20 text-white px-4 py-2.5 rounded-xl font-bold text-xs hover:bg-white hover:text-red-600 transition-colors uppercase tracking-wider"
                  >
                    🏥 Find Emergency Hospitals
                  </button>
                )}
                {result.urgency === 'emergency' && (
                  <a
                    href="tel:112"
                    className="bg-white text-red-600 px-5 py-2.5 rounded-xl font-black text-sm hover:scale-105 transition-transform flex items-center justify-center shadow-lg"
                  >
                    📞 Call 112
                  </a>
                )}
              </div>
            </div>
          )}

          {/* Main 2-Column Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            {/* Left: Signal Quality + Measurements + Clinical Report */}
            <div className="lg:col-span-7 space-y-6">

              {/* Signal Status Card */}
              <div className="glass-card p-5 space-y-4">
                <div className="flex items-center justify-between border-b border-white/5 pb-3">
                  <span className="text-xs font-bold uppercase tracking-widest text-slate-400">
                    Signal Quality & Parameters
                  </span>
                  <span
                    className={`text-[10px] font-mono px-2.5 py-0.5 rounded-full font-bold uppercase tracking-wider ${
                      result.quality_status === 'good'
                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                        : result.quality_status === 'poor_quality'
                        ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                        : 'bg-red-500/20 text-red-400 border border-red-500/30'
                    }`}
                  >
                    Signal: {result.quality_status.replace(/_/g, ' ')}
                  </span>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-center">
                  {[
                    { label: 'Heart Rate', value: result.heart_rate_bpm ? `${result.heart_rate_bpm} bpm` : '—' },
                    { label: 'Rhythm', value: result.rhythm ? result.rhythm.split(' ')[0] : '—' },
                    { label: 'QRS Width', value: result.qrs_duration_ms ? `${result.qrs_duration_ms} ms` : '—' },
                    { label: 'Model Version', value: result.model_version || 'v1.0' },
                  ].map(m => (
                    <div key={m.label} className="p-2.5 bg-slate-900/50 rounded-xl border border-white/5">
                      <p className="text-[10px] text-slate-500 font-bold uppercase">{m.label}</p>
                      <p className="text-xs font-black text-white mt-0.5 truncate">{m.value}</p>
                    </div>
                  ))}
                </div>

                {/* ST Elevation / Depression Indicators */}
                {(result.st_elevation_leads.length > 0 || result.st_depression_leads.length > 0) && (
                  <div className="p-3 bg-red-500/5 border border-red-500/20 rounded-xl space-y-1 text-xs">
                    {result.st_elevation_leads.length > 0 && (
                      <p className="text-red-400 font-bold font-mono">
                        ⬆ ST Elevation in: {result.st_elevation_leads.join(', ')}
                      </p>
                    )}
                    {result.st_depression_leads.length > 0 && (
                      <p className="text-amber-400 font-bold font-mono">
                        ⬇ ST Depression in: {result.st_depression_leads.join(', ')}
                      </p>
                    )}
                  </div>
                )}
              </div>

              {/* Clinical Assessment Report */}
              <div className="glass-card p-6 space-y-4">
                <div className="flex items-center justify-between border-b border-white/5 pb-3">
                  <h3 className="text-sm font-bold flex items-center gap-2 text-white">
                    <FileText className="w-4 h-4 text-emerald-400" />
                    {t.ai_clinical_report}
                  </h3>
                  <span className="text-[10px] text-slate-500 font-mono">PTB-XL Benchmarked</span>
                </div>

                <p className="text-slate-300 leading-relaxed text-xs">
                  {result.overall_assessment}
                </p>

                {result.recommendations.length > 0 && (
                  <div className="pt-3 border-t border-white/5 space-y-2">
                    <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">{t.recommendations}</p>
                    <ul className="space-y-1.5">
                      {result.recommendations.map((r, i) => (
                        <li key={i} className="flex gap-2 items-start text-xs text-slate-300">
                          <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full mt-1.5 flex-shrink-0" />
                          <span>{r}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="p-3 bg-slate-900/60 rounded-xl border border-white/5 text-[10px] text-slate-500 leading-relaxed italic">
                  {result.disclaimer}
                </div>
              </div>
            </div>

            {/* Right: The 5 Supported Superclasses */}
            <div className="lg:col-span-5 space-y-4">
              <div className="glass-card p-5 space-y-4">
                <div className="flex items-center justify-between border-b border-white/5 pb-3">
                  <div>
                    <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      {t.classification}
                    </h3>
                    <p className="text-[10px] text-slate-500 mt-0.5">
                      Deterministic ResNet1D outputs with locked thresholds
                    </p>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 bg-slate-800 text-slate-400 rounded">
                    5 Classes
                  </span>
                </div>

                {/* Condition rows strictly for the 5 classes */}
                <div className="space-y-2.5">
                  {result.conditions && result.conditions.length > 0 ? (
                    result.conditions.map(cond => (
                      <ConditionRow key={cond.code || cond.name} cond={cond} language={language} />
                    ))
                  ) : (
                    <p className="text-xs text-slate-500 text-center py-4">No condition outputs available.</p>
                  )}
                </div>
              </div>

              {/* Model Provenance Card */}
              <div className="glass-card p-4 space-y-2 text-center">
                <p className="text-[10px] text-slate-500 uppercase tracking-wider font-bold">Model Provenance</p>
                <p className="text-xs font-bold text-white">ResNet1D (12-Lead, 100 Hz, 1000 Steps)</p>
                <p className="text-[10px] text-slate-400 leading-relaxed">
                  Trained on 21,799 PTB-XL records · Evaluated on Fold 10 (2,158 records)
                  <br />
                  <span className="text-emerald-400 font-mono">Macro AUROC: 0.9265 · Macro F1: 0.7520</span>
                </p>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
};
