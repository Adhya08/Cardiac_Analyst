/**
 * RoutineMode — Vitals logging + real LightGBM risk scoring + real SHAP explainability
 * All data comes from the FastAPI backend. Light clinical workstation design.
 */
import React, { useState, useEffect } from 'react';
import { useStore } from '../store/useStore';
import { RiskArc } from '../components/RiskArc';
import {
  Activity, Plus, TrendingUp, History, Info,
  AlertCircle, CheckCircle2, Loader2, TrendingDown,
  Heart, BarChart2, AlertTriangle
} from 'lucide-react';
import { motion } from 'framer-motion';
import { api, type HistoryRecord } from '../lib/api';
import { translations } from '../lib/translations';
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement,
  LineElement, Title, Tooltip, Legend, Filler,
} from 'chart.js';
import { Line } from 'react-chartjs-2';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler);

// ─────────────────────────────────────────────
// Vitals Trend Chart (Light Theme)
// ─────────────────────────────────────────────
const VitalsChart: React.FC<{ history: HistoryRecord[] }> = ({ history }) => {
  if (history.length < 2) return null;
  const reversed = [...history].reverse();
  const labels = reversed.map(r => new Date(r.timestamp).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }));

  const chartData = {
    labels,
    datasets: [
      {
        label: 'ASCVD Risk (%)',
        data: reversed.map(r => r.risk_score),
        borderColor: '#DC2626',
        backgroundColor: 'rgba(220,38,38,0.06)',
        fill: true,
        tension: 0.3,
        pointRadius: 3,
        pointBackgroundColor: '#DC2626',
        yAxisID: 'y',
      },
      {
        label: 'Systolic BP (mmHg)',
        data: reversed.map(r => r.bp_sys),
        borderColor: '#0F8B83',
        backgroundColor: 'transparent',
        fill: false,
        tension: 0.3,
        pointRadius: 3,
        pointBackgroundColor: '#0F8B83',
        yAxisID: 'y1',
      },
      {
        label: 'Heart Rate (bpm)',
        data: reversed.map(r => r.hr),
        borderColor: '#D97706',
        backgroundColor: 'transparent',
        fill: false,
        tension: 0.3,
        pointRadius: 3,
        pointBackgroundColor: '#D97706',
        yAxisID: 'y1',
      },
    ],
  };

  const options = {
    responsive: true,
    interaction: { mode: 'index' as const, intersect: false },
    scales: {
      x: {
        grid: { color: '#E2E8F0' },
        ticks: { color: '#64748B', font: { size: 10 } },
      },
      y: {
        type: 'linear' as const,
        position: 'left' as const,
        grid: { color: '#E2E8F0' },
        ticks: { color: '#64748B', font: { size: 10 } },
        title: { display: true, text: 'Risk %', color: '#DC2626', font: { size: 10, weight: 'bold' as const } },
      },
      y1: {
        type: 'linear' as const,
        position: 'right' as const,
        grid: { drawOnChartArea: false },
        ticks: { color: '#64748B', font: { size: 10 } },
        title: { display: true, text: 'BP / HR', color: '#0F8B83', font: { size: 10, weight: 'bold' as const } },
      },
    },
    plugins: {
      legend: {
        labels: { color: '#182B3A', font: { size: 11, weight: 'bold' as const }, boxWidth: 12, padding: 14 },
      },
    },
  };

  return (
    <div className="clinical-card p-6 bg-white space-y-4">
      <div className="flex items-center justify-between border-b border-border pb-3">
        <h4 className="text-xs font-bold uppercase tracking-wider text-navy-850 flex items-center gap-2">
          <History className="w-4 h-4 text-teal-600" />
          Longitudinal 30-Day Vitals & Risk Trend
        </h4>
        <span className="text-[10px] text-slate-400 font-mono">SQLite Historical Records</span>
      </div>
      <Line data={chartData} options={options} />
    </div>
  );
};

// ─────────────────────────────────────────────
// Main RoutineMode
// ─────────────────────────────────────────────
export const RoutineMode: React.FC = () => {
  const { user, setMode, latestRisk, setLatestRisk, vitalsHistory, setVitalsHistory, language } = useStore();
  const t = translations[language];
  const [showForm, setShowForm] = useState(!latestRisk);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load history on mount
  useEffect(() => {
    api.getVitalsHistory(30).then(data => {
      if (data.records) setVitalsHistory(data.records);
    }).catch(() => {});
  }, [setVitalsHistory]);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const fd = new FormData(e.currentTarget);
    const payload = {
      bp_sys: Number(fd.get('bp_sys')),
      bp_dia: Number(fd.get('bp_dia')),
      hr: Number(fd.get('hr')),
      weight: Number(fd.get('weight')),
      spo2: Number(fd.get('spo2')),
      glucose: Number(fd.get('glucose')) || undefined,
      cholesterol: Number(fd.get('cholesterol')) || undefined,
    };

    if (payload.bp_sys < 60 || payload.bp_sys > 250) { setError('Systolic BP must be between 60–250 mmHg'); setLoading(false); return; }
    if (payload.hr < 20 || payload.hr > 250) { setError('Heart rate must be between 20–250 bpm'); setLoading(false); return; }
    if (payload.spo2 < 40 || payload.spo2 > 100) { setError('SpO2 must be between 40–100%'); setLoading(false); return; }

    try {
      const result = await api.logVitals(payload);
      setLatestRisk(result);
      const history = await api.getVitalsHistory(30);
      if (history.records) setVitalsHistory(history.records);
      setShowForm(false);
    } catch (err: any) {
      setError(err.message || 'Failed to log vitals. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  const risk = latestRisk;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* ── Mode Header ── */}
      <div className="clinical-card p-6 bg-white flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-border">
        <div>
          <div className="flex items-center gap-2 text-teal-700 text-xs font-bold uppercase tracking-wider">
            <Activity className="w-4 h-4" />
            <span>Cardiovascular Risk Screening</span>
          </div>
          <h2 className="text-xl font-bold text-navy-850 mt-1">
            {t.routine_screening}
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            {user ? `${user.age}y ${user.sex} · ${t.log_vitals_desc}` : t.log_vitals_desc}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowForm(!showForm)}
            className="btn-clinical-primary text-xs"
          >
            {showForm ? (
              <span>View Results</span>
            ) : (
              <>
                <Plus className="w-3.5 h-3.5" />
                <span>{t.log_vitals}</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-900 text-xs flex items-start gap-3">
          <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
          <p>{error}</p>
        </div>
      )}

      {/* ECG Escalation Prompt */}
      {risk?.ecg_prompt && (
        <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-amber-950 font-bold text-xs uppercase tracking-wide">12-Lead ECG Evaluation Recommended</p>
              <p className="text-amber-800 text-xs mt-0.5">
                Elevated cardiovascular risk factors detected. Upload a 12-lead digital ECG in the ECG Workspace for deep electrophysiological analysis.
              </p>
            </div>
          </div>
          <button
            onClick={() => setMode('ecg')}
            className="btn-clinical-primary text-xs whitespace-nowrap"
          >
            Go to ECG Analysis &rarr;
          </button>
        </div>
      )}

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Form or Vitals Dashboard (8 cols) */}
        <div className="lg:col-span-8 space-y-6">
          {showForm ? (
            /* Vitals Entry Form */
            <div className="clinical-card p-6 bg-white space-y-6">
              <div className="flex items-center justify-between border-b border-border pb-3">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-teal-600" />
                  <h3 className="text-xs font-bold uppercase tracking-wider text-navy-850">
                    Patient Vitals Entry & ASCVD Assessment
                  </h3>
                </div>
                <span className="text-[10px] text-amber-800 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded font-mono font-bold">Experimental, not validated</span>
              </div>

              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                  {[
                    { name: 'bp_sys', label: t.bp_sys, placeholder: '120', unit: 'mmHg', required: true },
                    { name: 'bp_dia', label: t.bp_dia, placeholder: '80', unit: 'mmHg', required: true },
                    { name: 'hr', label: t.hr, placeholder: '72', unit: 'BPM', required: true },
                    { name: 'weight', label: t.weight, placeholder: '70.0', unit: 'kg', step: '0.1', required: true },
                    { name: 'spo2', label: t.spo2, placeholder: '98', unit: '%', step: '0.1', required: true },
                    { name: 'glucose', label: t.glucose, placeholder: '95', unit: 'mg/dL' },
                    { name: 'cholesterol', label: t.cholesterol, placeholder: '180', unit: 'mg/dL' },
                  ].map(f => (
                    <div key={f.name} className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <label className="text-[11px] font-bold text-slate-600 uppercase tracking-wider">{f.label}</label>
                        <span className="text-[10px] font-mono text-slate-400 font-bold">{f.unit}</span>
                      </div>
                      <div className="relative">
                        <input
                          name={f.name}
                          type="number"
                          step={f.step || '1'}
                          required={f.required}
                          className="clinical-input pr-12 font-mono text-sm"
                          placeholder={f.placeholder}
                        />
                        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] text-slate-400 font-bold font-mono pointer-events-none">
                          {f.unit}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="pt-4 border-t border-border flex items-center justify-between gap-4">
                  <button
                    type="button"
                    onClick={() => setShowForm(false)}
                    className="btn-clinical-secondary text-xs"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={loading}
                    className="btn-clinical-primary text-xs px-6"
                  >
                    {loading ? (
                      <><Loader2 className="w-3.5 h-3.5 animate-spin" /> {t.analyzing_lgbm}</>
                    ) : (
                      <><CheckCircle2 className="w-3.5 h-3.5" /> Calculate Cardiovascular Risk</>
                    )}
                  </button>
                </div>
              </form>
            </div>
          ) : (
            /* Current Vitals Readings Grid */
            <div className="space-y-6">
              {risk && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  {[
                    { label: 'Systolic / Diastolic', value: `${risk.vitals.bp_sys}/${risk.vitals.bp_dia}`, unit: 'mmHg', icon: Activity },
                    { label: 'Heart Rate', value: risk.vitals.hr, unit: 'BPM', icon: Heart },
                    { label: 'Blood Oxygen (SpO2)', value: `${risk.vitals.spo2}%`, unit: 'Pulse Oximetry', icon: TrendingUp },
                    {
                      label: 'Trend Delta',
                      value: risk.trend_delta !== 0 ? `${risk.trend_delta > 0 ? '+' : ''}${risk.trend_delta.toFixed(1)}%` : 'Stable',
                      unit: 'vs Prior Reading',
                      icon: risk.trend_delta > 0 ? TrendingUp : TrendingDown,
                      color: risk.trend_delta > 0 ? 'text-red-600' : 'text-emerald-700',
                    },
                  ].map(({ label, value, unit, color }) => (
                    <div key={label} className="clinical-card p-4 space-y-1.5 bg-white">
                      <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">{label}</p>
                      <p className={`text-2xl font-black tabular-nums ${color || 'text-navy-850'}`}>{value}</p>
                      <p className="text-[10px] text-slate-500 font-mono">{unit}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Longitudinal Charts */}
              {vitalsHistory.length >= 2 ? (
                <VitalsChart history={vitalsHistory} />
              ) : (
                <div className="clinical-card p-8 text-center text-slate-400 bg-white space-y-2">
                  <History className="w-8 h-8 mx-auto text-slate-300" />
                  <p className="text-xs font-bold text-navy-850">Trend Chart Requires 2+ Readings</p>
                  <p className="text-[11px] text-slate-500">Log vitals regularly to track multi-day blood pressure and heart rate trends.</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Column: LightGBM Risk Arc + SHAP Explainability (4 cols) */}
        <div className="lg:col-span-4 space-y-6">
          <div className="space-y-4">
            <h3 className="text-xs font-bold text-navy-850 uppercase tracking-wider">
              {t.risk_assessment}
            </h3>

            <div className="p-3 bg-amber-50/80 rounded-xl border border-amber-200/80 text-amber-900 text-xs flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
              <div>
                <span className="font-bold uppercase tracking-wider text-[10px] block text-amber-800">Research Prototype</span>
                <span className="text-[11px] leading-tight">Vitals risk score is <strong>experimental, not validated</strong> for independent clinical diagnostic decisions.</span>
              </div>
            </div>

            {risk ? (
              <div className="space-y-4">
                <RiskArc score={risk.risk_score} tier={risk.risk_tier} />

                {/* Score Comparison Grid */}
                <div className="clinical-card p-4 grid grid-cols-2 gap-3 text-center bg-surface-secondary">
                  <div>
                    <p className="text-[10px] text-slate-400 uppercase font-bold">{t.lightgbm_score}</p>
                    <p className="text-lg font-black text-navy-850 tabular-nums">{risk.lgbm_probability.toFixed(1)}%</p>
                  </div>
                  <div className="border-l border-border pl-3">
                    <p className="text-[10px] text-slate-400 uppercase font-bold">{t.framingham_score}</p>
                    <p className="text-lg font-black text-navy-850 tabular-nums">{risk.framingham_risk.toFixed(1)}%</p>
                  </div>
                </div>

                {/* Real SHAP Feature Importance */}
                {risk.shap_top5 && (
                  <div className="clinical-card p-5 space-y-4 bg-white">
                    <div className="flex items-center justify-between border-b border-border pb-3">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-navy-850 flex items-center gap-1.5">
                        <BarChart2 className="w-3.5 h-3.5 text-teal-600" />
                        SHAP Risk Attribution
                      </h4>
                      <span className="text-[10px] text-slate-400 font-mono">Top Factors</span>
                    </div>

                    <div className="space-y-3">
                      {risk.shap_top5.map((f) => (
                        <div key={f.feature} className="space-y-1">
                          <div className="flex justify-between text-[11px] font-bold uppercase tracking-wider">
                            <span className="text-slate-600">{f.feature}</span>
                            <span className={f.direction === 'positive' ? 'text-red-600 font-mono' : 'text-teal-700 font-mono'}>
                              {f.direction === 'positive' ? '+' : '-'}{f.percent}%
                            </span>
                          </div>
                          <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden border border-border">
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${f.percent}%` }}
                              transition={{ duration: 0.6 }}
                              className={`h-full rounded-full ${f.direction === 'positive' ? 'bg-red-500' : 'bg-teal-600'}`}
                            />
                          </div>
                        </div>
                      ))}
                    </div>

                    <p className="text-[10px] text-slate-400 leading-relaxed italic border-t border-border pt-3">
                      Confidence Interval: {risk.confidence_interval.lower}%–{risk.confidence_interval.upper}%. Server-side SHAP values.
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <div className="clinical-card p-10 text-center text-slate-400 space-y-2 bg-white">
                <Info className="w-8 h-8 mx-auto text-slate-300" />
                <p className="text-xs font-bold text-navy-850">No Risk Score Calculated</p>
                <p className="text-[11px] text-slate-500">Log patient vitals to generate the LightGBM predictive score and SHAP attribution.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
