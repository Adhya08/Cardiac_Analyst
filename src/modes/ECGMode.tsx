/**
 * ECGMode — 12-lead digital signal analysis via PTB-XL trained ResNet1D model.
 * Zero GenAI / Zero Gemini — deterministic local inference via ONNX Runtime.
 * Strictly 5 diagnostic superclasses: NORM, MI, STTC, CD, HYP.
 * Refined Clinical Workstation Light Theme.
 */
import React, { useState, useCallback, useEffect } from 'react';
import { useDropzone, type FileRejection } from 'react-dropzone';
import { useStore } from '../store/useStore';
import {
  Upload, CheckCircle2, Zap, AlertTriangle,
  ChevronDown, ChevronUp, Heart,
  AlertCircle, BarChart3, Activity, XCircle, RotateCcw
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { api, type ECGResponse, type ECGCondition } from '../lib/api';
import { translations } from '../lib/translations';
import { DualAnalysisReport } from '../components/DualAnalysisReport';
import { ECGViewer } from '../components/ECGViewer';

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
    bg: 'bg-red-50/60',
    border: 'border-red-200',
    badge: 'bg-red-600 text-white',
    bar: 'bg-red-600',
    text: 'text-red-700',
    statusLabel: 'DETECTED',
  },
  possible: {
    bg: 'bg-amber-50/60',
    border: 'border-amber-200',
    badge: 'bg-amber-100 text-amber-800 border border-amber-300',
    bar: 'bg-amber-500',
    text: 'text-amber-700',
    statusLabel: 'BORDERLINE',
  },
  normal: {
    bg: 'bg-slate-50',
    border: 'border-border',
    badge: 'bg-slate-100 text-slate-600',
    bar: 'bg-teal-600',
    text: 'text-slate-600',
    statusLabel: 'NOT DETECTED',
  },
  unavailable: {
    bg: 'bg-slate-50',
    border: 'border-border',
    badge: 'bg-slate-100 text-slate-400',
    bar: 'bg-slate-300',
    text: 'text-slate-400',
    statusLabel: 'UNAVAILABLE',
  },
};

const URGENCY_CONFIG = {
  emergency: {
    label: '🚨 EMERGENCY',
    bg: 'bg-red-600 text-white',
    desc: 'Immediate emergency evaluation advised. Model flagged features crossing decision threshold for acute injury or infarction (research flag, not a clinical diagnosis).',
  },
  see_doctor_today: {
    label: '⚠️ SEE DOCTOR TODAY',
    bg: 'bg-amber-500 text-slate-950',
    desc: 'Abnormal findings detected. Consult a physician or cardiologist for clinical correlation.',
  },
  routine: {
    label: '✅ ROUTINE FINDINGS',
    bg: 'bg-teal-700 text-white',
    desc: 'No diagnostic superclass exceeded its locked decision threshold. This model output does not rule out underlying cardiovascular disease.',
  },
  unavailable: {
    label: '⏸ ANALYSIS UNAVAILABLE',
    bg: 'bg-slate-700 text-white',
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
  
  const score = cond.model_score ?? cond.probability ?? 0;
  const pct = Math.min(100, Math.max(0, Math.round(score * 100)));
  const thresholdPct = Math.round(cond.threshold * 100);

  const isNormDetected = cond.code === 'NORM' && cond.detected;
  const badgeLabel = isNormDetected ? 'NORMAL PATTERN' : s.statusLabel;
  const badgeClass = isNormDetected 
    ? 'bg-emerald-100 text-emerald-800 border border-emerald-300' 
    : s.badge;

  const formattedPct = formatScorePercentage(score);
  const formattedScore = score >= 0.9995 ? '>0.999' : (score > 0 && score < 0.001) ? '<0.001' : score.toFixed(3);

  return (
    <div className={`rounded-xl border p-3.5 transition-all ${s.bg} ${s.border}`}>
      <div className="flex items-center justify-between gap-3 cursor-pointer" onClick={() => setExpanded(e => !e)}>
        <div className="flex items-center gap-2.5 flex-1 min-w-0">
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider flex-shrink-0 ${badgeClass}`}>
            {badgeLabel}
          </span>
          <div className="min-w-0">
            <span className="text-xs font-bold text-navy-850 block truncate">
              {cond.name} <span className="text-slate-400 font-mono text-[10px]">({cond.code})</span>
            </span>
            <span className="text-[10px] text-slate-500 font-mono">
              Threshold: {cond.threshold.toFixed(2)} ({thresholdPct}%)
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-right">
            <span className="text-[9px] uppercase tracking-wider text-slate-400 block font-bold">Model Score</span>
            <span className={`text-xs font-mono font-black ${cond.detected ? 'text-red-600' : 'text-navy-850'}`}>
              {formattedScore} ({formattedPct})
            </span>
          </div>
          <button className="text-slate-400 hover:text-navy-850 p-1" aria-label="Toggle details">
            {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* Model Score Bar with locked threshold indicator */}
      <div className="relative h-2 w-full bg-slate-200 rounded-full overflow-hidden mt-3">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
          className={`h-full rounded-full ${cond.detected ? 'bg-red-500' : 'bg-teal-600'}`}
        />
        {/* Threshold marker */}
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-amber-500 z-10"
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
            <div className="mt-3 pt-3 border-t border-border space-y-2 text-xs">
              <p className="text-slate-600 leading-relaxed">
                {language === 'hi' && cond.explanation_hi ? cond.explanation_hi : cond.explanation_en}
              </p>
              {cond.key_finding && (
                <p className="text-[11px] text-slate-700 font-mono bg-white p-2.5 rounded-lg border border-border">
                  🔍 <strong>Finding:</strong> {cond.key_finding}
                </p>
              )}
              {cond.leads_affected && cond.leads_affected.length > 0 && (
                <div className="flex items-center gap-1.5 flex-wrap pt-1">
                  <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Affected Leads:</span>
                  {cond.leads_affected.map(l => (
                    <span key={l} className="text-[10px] font-mono px-2 py-0.5 bg-white text-navy-850 rounded border border-border font-bold">
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
  const { user, language, setMode, activeECGStudyId, setActiveECGStudyId } = useStore();
  const t = translations[language];
  const [status, setStatus] = useState<AnalysisStatus>('idle');
  const [result, setResult] = useState<ECGResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [showBenchmarkModal, setShowBenchmarkModal] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [rawSignalText, setRawSignalText] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);

  // Inspect active study from store if requested
  useEffect(() => {
    if (activeECGStudyId) {
      const loadActiveStudy = async () => {
        try {
          setStatus('analyzing');
          const studyData = await api.getECGAnalysis(activeECGStudyId);
          setResult(studyData);
          setStatus('done');
        } catch (e) {
          console.error('Failed to load active study:', e);
        }
      };
      loadActiveStudy();
    }
  }, [activeECGStudyId]);

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

    // Try reading text for waveform viewer
    try {
      const text = await f.text();
      setRawSignalText(text);
    } catch {
      setRawSignalText(null);
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
    setErrorMsg('');
    setFile(null);
    setRawSignalText(null);
    setActiveECGStudyId(null);
  };

  const runDemoScan = async (demoFile: string, displayName: string) => {
    try {
      const response = await fetch(`/samples/${demoFile}`);
      const blob = await response.blob();
      const demoF = new File([blob], displayName, { type: 'text/csv' });
      await handleUpload(demoF);
    } catch (e: any) {
      setStatus('error');
      setErrorMsg(`Failed to load demo file ${demoFile}: ${e.message}`);
    }
  };

  const urgencyConfig = result?.urgency ? (URGENCY_CONFIG[result.urgency] || URGENCY_CONFIG.routine) : null;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* ── Mode Header ── */}
      <div className="clinical-card p-6 bg-white flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-border">
        <div>
          <div className="flex items-center gap-2 text-teal-700 text-xs font-bold uppercase tracking-wider">
            <Heart className="w-4 h-4" />
            <span>12-Lead Diagnostic Workstation</span>
          </div>
          <h2 className="text-xl font-bold text-navy-850 mt-1">
            PTB-XL Residual 1D CNN Inference Suite
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Strictly evaluates 5 diagnostic superclasses (NORM, MI, STTC, CD, HYP) with calibrated decision thresholds.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowBenchmarkModal(true)}
            className="btn-clinical-secondary text-xs"
          >
            <BarChart3 className="w-3.5 h-3.5 text-teal-600" />
            <span>Fold 10 Metrics</span>
          </button>
          {status === 'done' && (
            <button
              onClick={reset}
              className="btn-clinical-primary text-xs"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>New Analysis</span>
            </button>
          )}
        </div>
      </div>

      {/* ── Upload Area (Shown when idle) ── */}
      {status === 'idle' && (
        <div className="space-y-6">
          {/* Format Guidance Notice */}
          <div className="p-4 rounded-xl bg-blue-50 border border-blue-200 text-blue-900 text-xs flex items-start gap-3">
            <Activity className="w-4 h-4 text-blue-700 flex-shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <strong className="font-bold text-blue-950 uppercase tracking-wide">
                Digital Voltage Timeseries Required:
              </strong>
              <p className="text-slate-600 leading-relaxed">
                This neural network requires calibrated 100 Hz, 1000-timestep 12-lead voltage arrays (CSV, NPY, JSON, or WFDB). Scanned paper photos and PDF documents cannot be processed by this 1D model version.
              </p>
            </div>
          </div>

          {/* Drag & Drop Upload Zone */}
          <div
            {...getRootProps()}
            className={`clinical-card p-12 text-center cursor-pointer border-2 border-dashed transition-all ${
              isDragActive
                ? 'border-teal-600 bg-teal-50/50'
                : 'border-slate-300 hover:border-teal-600 bg-white hover:bg-slate-50/50'
            }`}
          >
            <input {...getInputProps()} />
            <div className="w-16 h-16 rounded-2xl bg-teal-50 border border-teal-200 flex items-center justify-center mx-auto text-teal-700 mb-4 transition-transform group-hover:scale-105">
              <Upload className="w-7 h-7" />
            </div>
            <h3 className="text-base font-bold text-navy-850">
              {isDragActive ? 'Drop digital ECG file here' : 'Select or drag & drop digital 12-lead ECG file'}
            </h3>
            <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
              Accepts <strong>.csv, .npy, .json, or WFDB (.hea/.dat)</strong> timeseries files up to 20 MB.
            </p>
            <div className="flex gap-2 flex-wrap justify-center pt-4">
              {['12-Lead Digital', '100 Hz Timeseries', 'Shape (1000, 12)', 'Local ONNX ResNet1D'].map(tag => (
                <span
                  key={tag}
                  className="text-[10px] font-mono font-bold py-1 px-2.5 bg-slate-100 border border-border rounded-full text-slate-600"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Error Banner ── */}
      {status === 'error' && (
        <div className="clinical-card p-8 border-red-300 bg-red-50/30 text-center space-y-4">
          <AlertTriangle className="w-10 h-10 text-red-600 mx-auto" />
          <h3 className="text-base font-bold text-red-900">{t.analysis_failed}</h3>
          <p className="text-slate-600 text-xs max-w-xl mx-auto leading-relaxed">{errorMsg}</p>
          <div className="pt-2 flex justify-center items-center">
            <button
              onClick={reset}
              className="btn-clinical-secondary text-xs px-6 py-2.5 mx-auto"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>{t.try_again}</span>
            </button>
          </div>
        </div>
      )}

      {/* ── Quick Trial Section (Real PTB-XL Held-Out Benchmark Records) ── */}
      {(status === 'idle' || status === 'error') && (
        <div className="clinical-card p-6 space-y-4 bg-white">
          <div className="flex items-center justify-between border-b border-border pb-3">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-teal-600" />
              <h4 className="text-xs font-bold uppercase tracking-wider text-navy-850">
                Test Real PTB-XL Held-Out Benchmark Records (Fold 10)
              </h4>
            </div>
            <span className="text-[10px] text-slate-400 font-mono">10-second 12-lead digital files</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {[
              { file: 'sample_ecg_NORM.csv', label: 'Normal Sinus Rhythm', code: 'NORM', desc: 'Fold 10 held-out test sample' },
              { file: 'sample_ecg_MI.csv', label: 'Myocardial Infarction', code: 'MI', desc: 'Fold 10 held-out test sample' },
              { file: 'sample_ecg_STTC.csv', label: 'ST/T Changes', code: 'STTC', desc: 'Fold 10 held-out test sample' },
              { file: 'sample_ecg_CD.csv', label: 'Conduction Disturbance', code: 'CD', desc: 'Fold 10 held-out test sample' },
              { file: 'sample_ecg_HYP.csv', label: 'Hypertrophy', code: 'HYP', desc: 'Fold 10 held-out test sample' },
            ].map(item => (
              <div
                key={item.code}
                onClick={(e) => { e.stopPropagation(); runDemoScan(item.file, item.file); }}
                className="clinical-card-interactive p-3.5 flex items-center justify-between group"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-9 h-9 rounded-xl bg-teal-50 border border-teal-200 flex items-center justify-center flex-shrink-0 text-teal-700">
                    <Heart className="w-4 h-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-bold text-navy-850 truncate">{item.label}</p>
                    <p className="text-[10px] text-slate-500 font-mono">{item.code} · {item.desc}</p>
                  </div>
                </div>
                <span className="text-[10px] font-bold text-teal-700 opacity-0 group-hover:opacity-100 transition-opacity pl-2">
                  RUN &rarr;
                </span>
              </div>
            ))}
          </div>

          {/* Validation & Defensive Handling Tests */}
          <div className="pt-3 border-t border-border">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2.5">
              Defensive Safety & Validation Edge-Cases
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => handleUpload(new File([new Uint8Array(64)], 'paper_scan.png', { type: 'image/png' }))}
                className="p-3 rounded-xl border border-amber-200 bg-amber-50/50 hover:bg-amber-100/50 text-left transition-colors flex items-center justify-between group"
              >
                <div className="flex items-center gap-2.5">
                  <XCircle className="w-4 h-4 text-amber-600 flex-shrink-0" />
                  <div>
                    <p className="text-xs font-bold text-amber-900">Test Photo/PDF Rejection</p>
                    <p className="text-[10px] text-slate-500">Upload paper scan (.png) &rarr; friendly rejection state</p>
                  </div>
                </div>
                <span className="text-[10px] font-mono text-amber-800 font-bold">TEST &rarr;</span>
              </button>

              <button
                type="button"
                onClick={() => runDemoScan('flatline_corrupt.csv', 'flatline_sample.csv')}
                className="p-3 rounded-xl border border-red-200 bg-red-50/50 hover:bg-red-100/50 text-left transition-colors flex items-center justify-between group"
              >
                <div className="flex items-center gap-2.5">
                  <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
                  <div>
                    <p className="text-xs font-bold text-red-900">Test Flatline Signal Defense</p>
                    <p className="text-[10px] text-slate-500">Zero-variance flatline &rarr; analysis_unavailable state</p>
                  </div>
                </div>
                <span className="text-[10px] font-mono text-red-800 font-bold">TEST &rarr;</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Loading View ── */}
      {(status === 'uploading' || status === 'analyzing') && (
        <div className="clinical-card p-16 flex flex-col items-center gap-6 text-center bg-white">
          <div className="relative">
            <div className="w-16 h-16 border-4 border-teal-200 border-t-teal-600 rounded-full animate-spin" />
            <Activity className="absolute inset-0 m-auto text-teal-600 w-6 h-6 animate-pulse" />
          </div>
          <div className="space-y-1.5">
            <h3 className="text-base font-bold uppercase tracking-wider text-navy-850">
              {status === 'uploading' ? t.uploading_ecg : t.medical_ai_analysis}
            </h3>
            <p className="text-slate-500 text-xs max-w-sm">
              {status === 'uploading'
                ? 'Validating 12-lead digital format and transferring array...'
                : t.analyzing_conditions}
            </p>
          </div>
          <div className="w-64 h-2 bg-slate-100 rounded-full overflow-hidden border border-border">
            <motion.div
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.4 }}
              className="h-full bg-teal-600 rounded-full"
            />
          </div>
          {file && <p className="text-[11px] text-slate-400 font-mono">File: {file.name}</p>}
        </div>
      )}

      {/* ── Results View ── */}
      {status === 'done' && result && (
        <div className="space-y-6 animate-in fade-in duration-200">
          {/* 1. Defensive Analysis Unavailable State */}
          {result.status === 'analysis_unavailable' && (
            <div className="p-6 rounded-2xl bg-red-50 border border-red-200 text-red-950 space-y-3">
              <div className="flex items-center gap-3">
                <XCircle className="w-6 h-6 text-red-600 flex-shrink-0" />
                <div>
                  <h3 className="text-base font-bold text-red-900 uppercase tracking-wide">
                    {t.analysis_unavailable_title}
                  </h3>
                  <p className="text-xs text-red-700 mt-0.5">
                    Signal Quality: <span className="font-bold uppercase tracking-wider">{result.quality_status}</span>
                  </p>
                </div>
              </div>
              <div className="p-4 bg-white/80 rounded-xl border border-red-200 text-xs text-red-900 leading-relaxed">
                <strong>Abstain Reason: </strong> {result.abstain_reason || result.overall_assessment}
              </div>
              <p className="text-xs text-slate-600">
                Please re-record the ECG using standard 12-lead electrode placement and ensure 10-second duration at 100 Hz.
              </p>
            </div>
          )}

          {/* 2. Uncertainty Warning Banner */}
          {(result.status === 'uncertain' || result.uncertainty_flag) && result.status !== 'analysis_unavailable' && (
            <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 flex items-start gap-3.5">
              <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
              <div className="space-y-0.5">
                <p className="text-xs font-bold text-amber-900 uppercase tracking-wide">
                  {t.uncertainty_title}
                </p>
                <p className="text-xs text-amber-800 leading-relaxed">
                  {result.abstain_reason || t.uncertainty_desc}
                </p>
              </div>
            </div>
          )}

          {/* 3. Triage Urgency Header */}
          {urgencyConfig && result.status !== 'analysis_unavailable' && (
            <div className={`p-4 rounded-2xl ${urgencyConfig.bg} flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-sm`}>
              <div>
                <p className="font-black text-base uppercase tracking-wide">{urgencyConfig.label}</p>
                <p className="text-xs opacity-90 mt-0.5">{urgencyConfig.desc}</p>
              </div>
              <div className="flex flex-wrap gap-2.5">
                {result.urgency === 'emergency' && (
                  <button
                    onClick={() => setMode('emergency')}
                    className="bg-white/20 text-white border border-white/30 px-4 py-2 rounded-xl font-bold text-xs hover:bg-white hover:text-red-600 transition-colors uppercase tracking-wider"
                  >
                    🏥 Find Hospitals
                  </button>
                )}
                {result.urgency === 'emergency' && (
                  <a
                    href="tel:112"
                    className="bg-white text-red-600 px-5 py-2 rounded-xl font-black text-sm shadow-md flex items-center justify-center"
                  >
                    📞 Call 112
                  </a>
                )}
              </div>
            </div>
          )}

          {/* 4. Interactive 12-Lead ECG Waveform Viewer */}
          <ECGViewer
            signalData={rawSignalText}
            fileName={file?.name || 'Diagnostic Study'}
            conditionCode={result.conditions?.find(c => c.detected)?.code || result.conditions?.[0]?.code || 'NORM'}
            qualityStatus={result.quality_status}
          />

          {/* 5. Main Diagnostic Columns: Clinical & Family Report (Left) + Superclass Findings (Right) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left Column: Measurements + Dual Perspective Report (7 cols) */}
            <div className="lg:col-span-7 space-y-6">
              {/* Measurements Card */}
              <div className="clinical-card p-5 space-y-4">
                <div className="flex items-center justify-between border-b border-border pb-3">
                  <span className="text-xs font-bold uppercase tracking-wider text-navy-850">
                    Acquisition Parameters & Time-Domain Measurements
                  </span>
                  <span
                    className={`text-[10px] font-mono px-2.5 py-0.5 rounded-full font-bold uppercase tracking-wider ${
                      result.quality_status === 'good'
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        : 'bg-amber-50 text-amber-700 border border-amber-200'
                    }`}
                  >
                    Signal: {result.quality_status.replace(/_/g, ' ')}
                  </span>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-center">
                  {[
                    { label: 'Ventricular Rate', value: result.heart_rate_bpm ? `${result.heart_rate_bpm} bpm` : '—' },
                    { label: 'Rhythm', value: result.rhythm ? result.rhythm.split(' ')[0] : '—' },
                    { label: 'QRS Duration', value: result.qrs_duration_ms ? `${result.qrs_duration_ms} ms` : '—' },
                    { label: 'Model Version', value: result.model_version || 'v1.0' },
                  ].map(m => (
                    <div key={m.label} className="p-3 bg-surface-secondary rounded-xl border border-border">
                      <p className="text-[10px] text-slate-500 font-bold uppercase">{m.label}</p>
                      <p className="text-sm font-black text-navy-850 mt-0.5 truncate">{m.value}</p>
                    </div>
                  ))}
                </div>

                {/* ST Vector Abnormalities */}
                {(result.st_elevation_leads.length > 0 || result.st_depression_leads.length > 0) && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-xl space-y-1 text-xs">
                    {result.st_elevation_leads.length > 0 && (
                      <p className="text-red-700 font-bold font-mono">
                        ⬆ ST Elevation in Leads: {result.st_elevation_leads.join(', ')}
                      </p>
                    )}
                    {result.st_depression_leads.length > 0 && (
                      <p className="text-amber-800 font-bold font-mono">
                        ⬇ ST Depression in Leads: {result.st_depression_leads.join(', ')}
                      </p>
                    )}
                  </div>
                )}
              </div>

              {/* Dual-Perspective Report (Clinical & Family Guide) */}
              <DualAnalysisReport result={result} language={language} />
            </div>

            {/* Right Column: 5 Supported Superclasses Breakdown (5 cols) */}
            <div className="lg:col-span-5 space-y-4">
              <div className="clinical-card p-5 space-y-4">
                <div className="flex items-center justify-between border-b border-border pb-3">
                  <div>
                    <h3 className="text-xs font-bold text-navy-850 uppercase tracking-wider flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-teal-600" />
                      {t.classification}
                    </h3>
                    <p className="text-[10px] text-slate-500 mt-0.5">
                      Deterministic ResNet1D outputs with locked thresholds
                    </p>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 bg-slate-100 text-slate-600 rounded font-bold">
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
              <div className="clinical-card p-5 space-y-2 text-center bg-surface-secondary">
                <p className="text-[10px] text-slate-400 uppercase tracking-wider font-bold">Model Provenance</p>
                <p className="text-xs font-bold text-navy-850">ResNet1D (12-Lead, 100 Hz, 1000 Steps)</p>
                <p className="text-[11px] text-slate-600 leading-relaxed">
                  Trained on 21,799 PTB-XL records · Evaluated on Fold 10 (2,158 records)
                  <br />
                  <span className="text-teal-700 font-mono font-bold">Macro AUROC: 0.9265 · Macro F1: 0.7520</span>
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Fold 10 Benchmark Modal ── */}
      {showBenchmarkModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-navy-950/40 backdrop-blur-sm">
          <div className="clinical-card w-full max-w-2xl bg-white border border-border shadow-modal overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="px-5 py-4 border-b border-border flex items-center justify-between bg-surface-secondary">
              <div className="flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-teal-600" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-navy-850">
                  PhysioNet PTB-XL Fold 10 Test Benchmark Matrix
                </h3>
              </div>
              <button
                onClick={() => setShowBenchmarkModal(false)}
                className="text-slate-400 hover:text-navy-850 p-1"
              >
                ✕
              </button>
            </div>

            <div className="p-6 space-y-4 max-h-[80vh] overflow-y-auto text-xs">
              <p className="text-slate-600 leading-relaxed">
                Evaluated strictly once on the 2,158 held-out records of Fold 10. These records were never used during model training or hyperparameter tuning.
              </p>

              <div className="overflow-x-auto rounded-xl border border-border">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-600 border-b border-border text-[10px] font-bold uppercase">
                    <tr>
                      <th className="p-2.5">Superclass</th>
                      <th className="p-2.5">Threshold</th>
                      <th className="p-2.5">AUROC</th>
                      <th className="p-2.5">Sensitivity</th>
                      <th className="p-2.5">Specificity</th>
                      <th className="p-2.5">F1</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border font-medium">
                    {REAL_BENCHMARK.classes.map(c => (
                      <tr key={c.code} className="hover:bg-slate-50">
                        <td className="p-2.5 font-bold text-navy-850">{c.code} ({c.name})</td>
                        <td className="p-2.5 font-mono text-slate-500">{c.threshold.toFixed(2)}</td>
                        <td className="p-2.5 font-mono font-bold text-teal-700">{c.auroc.toFixed(4)}</td>
                        <td className="p-2.5 font-mono text-slate-600">{c.sens}</td>
                        <td className="p-2.5 font-mono text-slate-600">{c.spec}</td>
                        <td className="p-2.5 font-mono font-bold text-navy-850">{c.f1.toFixed(4)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="p-3 bg-teal-50 rounded-xl border border-teal-200 text-teal-900 text-[11px]">
                <strong>Macro Average:</strong> AUROC {REAL_BENCHMARK.macroAuroc.toFixed(4)} · AUPRC {REAL_BENCHMARK.macroAuprc.toFixed(4)} · F1 {REAL_BENCHMARK.macroF1.toFixed(4)}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
