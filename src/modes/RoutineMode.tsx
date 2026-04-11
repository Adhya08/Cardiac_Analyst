/**
 * RoutineMode — Vitals logging + real LightGBM risk scoring + real SHAP explainability
 * All data comes from the FastAPI backend (no mocks).
 */
import React, { useState, useEffect } from 'react';
import { useStore } from '../store/useStore';
import { RiskArc } from '../components/RiskArc';
import {
  Activity, Plus, TrendingUp, History, Info,
  AlertCircle, CheckCircle2, User, Loader2, TrendingDown,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { api, type HistoryRecord } from '../lib/api';
import { translations } from '../lib/translations';
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement,
  LineElement, Title, Tooltip, Legend, Filler,
} from 'chart.js';
import { Line } from 'react-chartjs-2';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler);

// ─────────────────────────────────────────────
// Profile Setup Modal (inline)
// ─────────────────────────────────────────────
const ProfileSetup: React.FC<{ onSave: () => void }> = ({ onSave }) => {
  const { setUser, language } = useStore();
  const t = translations[language];
  const [form, setForm] = useState({ age: '', sex: 'Male', is_smoker: false, is_diabetic: false, has_family_history: false, height_cm: '' });
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!form.age) return;
    setSaving(true);
    const profile = {
      age: Number(form.age),
      sex: form.sex as 'Male' | 'Female' | 'Other',
      is_smoker: form.is_smoker,
      is_diabetic: form.is_diabetic,
      has_family_history: form.has_family_history,
      height_cm: form.height_cm ? Number(form.height_cm) : undefined,
    };
    try {
      await api.updateProfile(profile);
      setUser(profile);
      onSave();
    } catch (e) {
      // Still save locally even if backend fails
      setUser(profile);
      onSave();
    } finally {
      setSaving(false);
    }
  };

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-8 border-emerald-500/20">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center">
          <User className="text-emerald-500 w-5 h-5" />
        </div>
        <div>
          <h3 className="text-lg font-bold">{t.setup_profile}</h3>
          <p className="text-slate-400 text-xs">{t.required_risk}</p>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div className="space-y-2">
          <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">{t.age_years}</label>
          <input value={form.age} onChange={e => setForm(f => ({ ...f, age: e.target.value }))} type="number" className="input-field" placeholder="45" min={18} max={120} />
        </div>
        <div className="space-y-2">
          <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">{t.bio_sex}</label>
          <select value={form.sex} onChange={e => setForm(f => ({ ...f, sex: e.target.value }))} className="input-field">
            <option value="Male">{language === 'hi' ? 'पुरुष' : 'Male'}</option>
            <option value="Female">{language === 'hi' ? 'महिला' : 'Female'}</option>
            <option value="Other">{language === 'hi' ? 'अन्य' : 'Other'}</option>
          </select>
        </div>
        <div className="space-y-2">
          <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">{t.height_cm}</label>
          <input value={form.height_cm} onChange={e => setForm(f => ({ ...f, height_cm: e.target.value }))} type="number" className="input-field" placeholder="170" />
        </div>
        <div className="space-y-3 md:col-span-2 pt-2">
          <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">{t.risk_factors}</label>
          {[
            { key: 'is_smoker', label: t.smoker },
            { key: 'is_diabetic', label: t.diabetic },
            { key: 'has_family_history', label: t.family_history },
          ].map(({ key, label }) => (
            <label key={key} className="flex items-center gap-3 cursor-pointer group">
              <div
                onClick={() => setForm(f => ({ ...f, [key]: !f[key as keyof typeof f] }))}
                className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-all ${form[key as keyof typeof form] ? 'bg-emerald-500 border-emerald-500' : 'border-slate-600 group-hover:border-slate-400'}`}
              >
                {form[key as keyof typeof form] && <CheckCircle2 className="w-3 h-3 text-white" />}
              </div>
              <span className="text-sm text-slate-300">{label}</span>
            </label>
          ))}
        </div>
      </div>
      <button onClick={handleSave} disabled={!form.age || saving} className="btn-primary w-full mt-6">
        {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : ''}
        {saving ? t.saving : t.save_profile}
      </button>
    </motion.div>
  );
};

// ─────────────────────────────────────────────
// Vitals Trend Chart (real data)
// ─────────────────────────────────────────────
const VitalsChart: React.FC<{ history: HistoryRecord[] }> = ({ history }) => {
  if (history.length < 2) return null;
  const reversed = [...history].reverse();
  const labels = reversed.map(r => new Date(r.timestamp).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }));

  const chartData = {
    labels,
    datasets: [
      {
        label: 'Risk Score (%)',
        data: reversed.map(r => r.risk_score),
        borderColor: '#ef4444',
        backgroundColor: 'rgba(239,68,68,0.08)',
        fill: true,
        tension: 0.4,
        pointRadius: 3,
        pointBackgroundColor: '#ef4444',
        yAxisID: 'y',
      },
      {
        label: 'Systolic BP (mmHg)',
        data: reversed.map(r => r.bp_sys),
        borderColor: '#10b981',
        backgroundColor: 'rgba(16,185,129,0.05)',
        fill: false,
        tension: 0.4,
        pointRadius: 3,
        pointBackgroundColor: '#10b981',
        yAxisID: 'y1',
      },
      {
        label: 'Heart Rate (bpm)',
        data: reversed.map(r => r.hr),
        borderColor: '#f59e0b',
        backgroundColor: 'rgba(245,158,11,0.05)',
        fill: false,
        tension: 0.4,
        pointRadius: 3,
        pointBackgroundColor: '#f59e0b',
        yAxisID: 'y1',
      },
    ],
  };

  const options = {
    responsive: true,
    interaction: { mode: 'index' as const, intersect: false },
    scales: {
      x: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#94a3b8', font: { size: 10 } } },
      y: {
        type: 'linear' as const, position: 'left' as const,
        grid: { color: 'rgba(255,255,255,0.04)' },
        ticks: { color: '#94a3b8', font: { size: 10 } },
        title: { display: true, text: 'Risk %', color: '#ef4444', font: { size: 10 } },
      },
      y1: {
        type: 'linear' as const, position: 'right' as const,
        grid: { drawOnChartArea: false },
        ticks: { color: '#94a3b8', font: { size: 10 } },
        title: { display: true, text: 'BP / HR', color: '#10b981', font: { size: 10 } },
      },
    },
    plugins: {
      legend: { labels: { color: '#94a3b8', font: { size: 11 }, boxWidth: 12, padding: 16 } },
    },
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass-card p-6">
      <h4 className="text-sm font-bold flex items-center gap-2 mb-4">
        <History className="w-4 h-4 text-emerald-500" />
        30-Day Vitals Trend
        <span className="ml-auto text-[10px] text-slate-500 font-normal">Real data from database</span>
      </h4>
      <Line data={chartData} options={options} />
    </motion.div>
  );
};

// ─────────────────────────────────────────────
// Main RoutineMode
// ─────────────────────────────────────────────
export const RoutineMode: React.FC = () => {
  const { user, isProfileComplete, setMode, latestRisk, setLatestRisk, vitalsHistory, setVitalsHistory, language } = useStore();
  const t = translations[language];
  const [showForm, setShowForm] = useState(!latestRisk);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showProfile, setShowProfile] = useState(!isProfileComplete);

  // Load history on mount
  useEffect(() => {
    api.getVitalsHistory(30).then(data => {
      if (data.records) setVitalsHistory(data.records);
    }).catch(() => {});
  }, []);

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

    // Basic validation
    if (payload.bp_sys < 60 || payload.bp_sys > 250) { setError('Systolic BP must be 60–250 mmHg'); setLoading(false); return; }
    if (payload.hr < 20 || payload.hr > 250) { setError('Heart rate must be 20–250 bpm'); setLoading(false); return; }
    if (payload.spo2 < 40 || payload.spo2 > 100) { setError('SpO2 must be 40–100%'); setLoading(false); return; }

    try {
      const result = await api.logVitals(payload);
      setLatestRisk(result);
      // Refresh history
      const history = await api.getVitalsHistory(30);
      if (history.records) setVitalsHistory(history.records);
      setShowForm(false);
    } catch (err: any) {
      setError(err.message || 'Failed to log vitals. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  if (showProfile) {
    return (
      <div className="max-w-2xl mx-auto space-y-6">
        <header>
          <h2 className="text-3xl font-bold">{t.routine_screening}</h2>
          <p className="text-slate-400">{t.required_risk}</p>
        </header>
        <ProfileSetup onSave={() => setShowProfile(false)} />
      </div>
    );
  }

  const risk = latestRisk;

  return (
    <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-8">
      {/* Left Column */}
      <div className="lg:col-span-8 space-y-8">
        <header className="flex items-center justify-between">
          <div>
            <h2 className="text-3xl font-bold">{t.routine_screening}</h2>
            <p className="text-slate-400 text-sm">
              {user ? `${user.age}y ${user.sex} — ${t.log_vitals_desc}` : t.log_vitals_desc}
            </p>
          </div>
          <div className="flex gap-3">
            <button onClick={() => setShowProfile(true)} className="btn-secondary py-2 px-3 text-xs">
              <User className="w-3.5 h-3.5" /> {t.profile}
            </button>
            <button onClick={() => setShowForm(!showForm)} className="btn-secondary">
              {showForm ? t.dashboard : <><Plus className="w-4 h-4" /> {t.log_vitals}</>}
            </button>
          </div>
        </header>

        {/* Error banner */}
        <AnimatePresence>
          {error && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 flex items-start gap-3">
              <AlertCircle className="text-red-400 w-5 h-5 flex-shrink-0 mt-0.5" />
              <p className="text-red-300 text-sm">{error}</p>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ECG escalation banner */}
        <AnimatePresence>
          {risk?.ecg_prompt && (
            <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
              className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <AlertCircle className="text-amber-400 w-5 h-5 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-amber-300 font-bold text-sm">ECG Recommended</p>
                  <p className="text-amber-200/60 text-xs mt-1">Your risk score is elevated. Get a 12-lead ECG at a nearby clinic and upload it for deeper analysis.</p>
                </div>
              </div>
              <button onClick={() => setMode('ecg')} className="btn-primary text-xs py-2 px-4 whitespace-nowrap">
                Upload ECG →
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {showForm ? (
          /* ── Vitals Form ── */
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-8">
            <h3 className="text-xl font-bold mb-6 flex items-center gap-2">
              <Activity className="text-emerald-500 w-5 h-5" /> {t.daily_checkin}
            </h3>
            <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {[
                { name: 'bp_sys', label: t.bp_sys, placeholder: '120', required: true },
                { name: 'bp_dia', label: t.bp_dia, placeholder: '80', required: true },
                { name: 'hr', label: t.hr, placeholder: '72', required: true },
                { name: 'weight', label: t.weight, placeholder: '70', required: true, step: '0.1' },
                { name: 'spo2', label: t.spo2, placeholder: '98', required: true, step: '0.1' },
                { name: 'glucose', label: t.glucose, placeholder: t.optional },
                { name: 'cholesterol', label: t.cholesterol, placeholder: t.optional },
              ].map(f => (
                <div key={f.name} className="space-y-2">
                  <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">{f.label}</label>
                  <input name={f.name} type="number" step={f.step || '1'} required={f.required} className="input-field" placeholder={f.placeholder} />
                </div>
              ))}
              <div className="md:col-span-2 pt-2">
                <button type="submit" disabled={loading} className="btn-primary w-full shadow-emerald-500/20">
                  {loading ? (
                    <><Loader2 className="w-4 h-4 animate-spin" /> {t.analyzing_lgbm}</>
                  ) : t.analyze_btn}
                </button>
                <p className="text-center text-[10px] text-slate-500 mt-3">
                  Processed server-side by LightGBM + Framingham equations · SHAP explainability
                </p>
              </div>
            </form>
          </motion.div>
        ) : (
          /* ── Dashboard ── */
          <div className="space-y-6">
            {risk && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                  { label: 'Systolic BP', value: `${risk.vitals.bp_sys}/${risk.vitals.bp_dia}`, unit: 'mmHg', icon: Activity },
                  { label: 'Heart Rate', value: risk.vitals.hr, unit: 'bpm', icon: Activity },
                  { label: 'SpO2', value: `${risk.vitals.spo2}%`, unit: '', icon: TrendingUp },
                  {
                    label: 'vs Last Reading',
                    value: risk.trend_delta !== 0 ? `${risk.trend_delta > 0 ? '+' : ''}${risk.trend_delta.toFixed(1)}%` : '—',
                    unit: 'risk delta',
                    icon: risk.trend_delta > 0 ? TrendingUp : TrendingDown,
                    color: risk.trend_delta > 0 ? 'text-red-400' : 'text-emerald-400',
                  },
                ].map(({ label, value, unit, color }) => (
                  <motion.div key={label} initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
                    className="glass-card p-4 space-y-2">
                    <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">{label}</p>
                    <p className={`text-2xl font-black ${color || 'text-white'}`}>{value}</p>
                    <p className="text-[10px] text-slate-500">{unit}</p>
                  </motion.div>
                ))}
              </div>
            )}
            {/* Charts */}
            {vitalsHistory.length >= 2 && <VitalsChart history={vitalsHistory} />}
            {vitalsHistory.length < 2 && (
              <div className="glass-card p-8 text-center text-slate-500">
                <History className="w-10 h-10 mx-auto mb-3 opacity-20" />
                <p className="text-sm">Log 2+ readings to see trend charts</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Right Column: Risk + SHAP */}
      <div className="lg:col-span-4 space-y-6">
        <section>
          <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-4">{t.risk_assessment}</h3>
          {risk ? (
            <>
              <RiskArc score={risk.risk_score} tier={risk.risk_tier} />
              <div className="glass-card p-4 mt-4 grid grid-cols-2 gap-3 text-center">
                <div>
                  <p className="text-[10px] text-slate-500 uppercase">{t.lightgbm_score}</p>
                  <p className="text-lg font-black text-white">{risk.lgbm_probability.toFixed(1)}%</p>
                </div>
                <div>
                  <p className="text-[10px] text-slate-500 uppercase">{t.framingham_score}</p>
                  <p className="text-lg font-black text-white">{risk.framingham_risk.toFixed(1)}%</p>
                </div>
              </div>
            </>
          ) : (
            <div className="glass-card p-12 text-center text-slate-500">
              <Info className="w-12 h-12 mx-auto mb-4 opacity-20" />
              <p className="text-sm">Log vitals to see your risk score</p>
            </div>
          )}
        </section>

        {/* Real SHAP Explainability */}
        {risk?.shap_top5 && (
          <section className="glass-card p-6 space-y-5">
            <h4 className="text-sm font-bold flex items-center gap-2">
              <Info className="w-4 h-4 text-emerald-500" />
              {t.ai_explainability}
              <span className="ml-auto text-[9px] text-slate-600 font-normal">{t.real_data}</span>
            </h4>
            <div className="space-y-4">
              {risk.shap_top5.map((f) => (
                <div key={f.feature} className="space-y-1.5">
                  <div className="flex justify-between text-[11px] font-bold uppercase tracking-wider">
                    <span className="text-slate-400">{f.feature}</span>
                    <span className={f.direction === 'positive' ? 'text-red-400' : 'text-emerald-400'}>
                      {f.direction === 'positive' ? '+' : '-'}{f.percent}%
                    </span>
                  </div>
                  <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${f.percent}%` }}
                      transition={{ duration: 0.7, delay: 0.1 }}
                      className={`h-full rounded-full ${f.direction === 'positive' ? 'bg-red-500' : 'bg-emerald-500'}`}
                    />
                  </div>
                </div>
              ))}
            </div>
            <p className="text-[10px] text-slate-500 leading-relaxed italic border-t border-white/5 pt-4">
              SHAP values from trained LightGBM model. Red = raises risk, green = reduces risk.
              Confidence interval: {risk.confidence_interval.lower}%–{risk.confidence_interval.upper}%
            </p>
          </section>
        )}
      </div>
    </div>
  );
};
