import React, { useState, useEffect } from 'react';
import {
  Heart, Activity, FileText, ArrowUpRight, Plus, AlertTriangle, ChevronRight
} from 'lucide-react';
import { useStore } from '../store/useStore';
import { api, type ECGHistoryItem, type HistoryRecord } from '../lib/api';
import { formatScorePercentage } from './ECGMode';

export const OverviewMode: React.FC = () => {
  const { setMode, user, setActiveECGStudyId, backendHealth } = useStore();

  const [recentECGs, setRecentECGs] = useState<ECGHistoryItem[]>([]);
  const [vitalsRecords, setVitalsRecords] = useState<HistoryRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let mounted = true;
    const loadOverviewData = async () => {
      setLoading(true);
      try {
        const [ecgRes, vitalsRes] = await Promise.allSettled([
          api.getECGHistory(),
          api.getVitalsHistory(30),
        ]);

        if (mounted) {
          if (ecgRes.status === 'fulfilled' && ecgRes.value?.ecg_sessions) {
            setRecentECGs(ecgRes.value.ecg_sessions);
          }
          if (vitalsRes.status === 'fulfilled' && vitalsRes.value?.records) {
            setVitalsRecords(vitalsRes.value.records);
          }
        }
      } catch (err) {
        console.error('Failed to load overview data:', err);
      } finally {
        if (mounted) setLoading(false);
      }
    };

    loadOverviewData();
    return () => {
      mounted = false;
    };
  }, []);

  const latestVitals = vitalsRecords.length > 0 ? vitalsRecords[0] : null;
  const latestECG = recentECGs.length > 0 ? recentECGs[0] : null;

  const handleOpenStudy = (ecgId: string) => {
    setActiveECGStudyId(ecgId);
    setMode('ecg');
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* 1. Clinical Welcome & Quick Action Bar */}
      <div className="clinical-card p-6 bg-gradient-to-r from-surface to-surface-secondary flex flex-col md:flex-row items-start md:items-center justify-between gap-6 border-border">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-teal-600"></span>
            <span className="text-[11px] font-bold uppercase tracking-wider text-teal-800">
              Active Medical Workstation
            </span>
          </div>
          <h2 className="text-xl font-bold text-navy-850 tracking-tight">
            {user?.name ? `Welcome back, ${user.name}` : 'Clinical Dashboard & Diagnostics'}
          </h2>
          <p className="text-xs text-slate-500 max-w-xl leading-relaxed">
            Local 1D Residual CNN diagnostic pipeline trained on 21,799 PTB-XL records.
            Multi-label detection for NORM, MI, STTC, CD, and HYP with zero cloud dependencies.
          </p>
        </div>

        {/* Primary and Secondary Actions */}
        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
          <button
            onClick={() => setMode('ecg')}
            className="btn-clinical-primary flex-1 sm:flex-none py-3 px-5 text-xs shadow-md"
          >
            <Plus className="w-4 h-4" />
            <span>New ECG Analysis</span>
          </button>
          <button
            onClick={() => setMode('routine')}
            className="btn-clinical-secondary flex-1 sm:flex-none py-3 px-5 text-xs"
          >
            <Activity className="w-4 h-4 text-teal-700" />
            <span>Log Patient Vitals</span>
          </button>
        </div>
      </div>

      {/* 2. Top Metric Cards (Latest Vitals + Engine Status + Study Counts) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1: Blood Pressure */}
        <div className="clinical-card p-4 space-y-2">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[10px] font-bold uppercase tracking-wider">Latest Blood Pressure</span>
            <span className="text-[10px] font-mono text-slate-400">mmHg</span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-black text-navy-850 tabular-nums">
              {latestVitals ? `${latestVitals.bp_sys}/${latestVitals.bp_dia}` : '120/80'}
            </span>
            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
              latestVitals && latestVitals.bp_sys > 140
                ? 'bg-amber-100 text-amber-800'
                : 'bg-emerald-100 text-emerald-800'
            }`}>
              {latestVitals ? (latestVitals.bp_sys > 140 ? 'Stage 1' : 'Normal') : 'Baseline'}
            </span>
          </div>
          <p className="text-[10px] text-slate-400 truncate">
            {latestVitals ? `Recorded ${new Date(latestVitals.timestamp).toLocaleDateString()}` : 'Awaiting vitals input'}
          </p>
        </div>

        {/* Metric 2: Resting Heart Rate */}
        <div className="clinical-card p-4 space-y-2">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[10px] font-bold uppercase tracking-wider">Resting Heart Rate</span>
            <span className="text-[10px] font-mono text-slate-400">BPM</span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-black text-navy-850 tabular-nums">
              {latestECG?.heart_rate_bpm || latestVitals?.hr || 72}
            </span>
            <span className="text-xs text-slate-500">bpm</span>
          </div>
          <p className="text-[10px] text-slate-400 truncate">
            {latestECG?.rhythm || 'Normal Sinus Rhythm'}
          </p>
        </div>

        {/* Metric 3: Latest Diagnostic Study */}
        <div className="clinical-card p-4 space-y-2">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[10px] font-bold uppercase tracking-wider">Latest ECG Finding</span>
            <Heart className="w-3.5 h-3.5 text-teal-600" />
          </div>
          <div className="space-y-0.5">
            <p className="text-sm font-bold text-navy-850 truncate">
              {latestECG ? latestECG.top_condition : 'No studies recorded'}
            </p>
            <p className="text-xs font-mono font-bold text-teal-700">
              {latestECG ? `Score: ${formatScorePercentage(latestECG.top_condition_prob)}` : 'Ready to analyze'}
            </p>
          </div>
          <p className="text-[10px] text-slate-400 truncate">
            {latestECG ? `${new Date(latestECG.timestamp).toLocaleDateString()}` : 'Upload 12-lead signal'}
          </p>
        </div>

        {/* Metric 4: ONNX Model Provenance */}
        <div className="clinical-card p-4 space-y-2 bg-surface-secondary">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[10px] font-bold uppercase tracking-wider">ResNet1D Model Status</span>
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
          </div>
          <div className="space-y-0.5">
            <p className="text-sm font-black text-navy-850">
              0.9265 AUROC
            </p>
            <p className="text-[10px] text-slate-500 font-mono">
              Fold 10 Macro F1: 0.7520
            </p>
          </div>
          <p className="text-[10px] text-teal-700 font-bold truncate">
            {backendHealth.modelLoaded ? 'ONNX CPU: ~7.46 ms' : 'Initializing model'}
          </p>
        </div>
      </div>

      {/* 3. Main Dashboard Grid (Recent ECG Studies Table + System Overview) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Recent Diagnostic Studies Ledger (8 Cols) */}
        <div className="lg:col-span-8 space-y-4">
          <div className="clinical-card overflow-hidden">
            <div className="px-5 py-4 border-b border-border flex items-center justify-between bg-surface-secondary">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-teal-600" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-navy-850">
                  Recent 12-Lead Diagnostic Studies
                </h3>
              </div>
              <button
                onClick={() => setMode('history')}
                className="text-xs font-bold text-teal-700 hover:text-teal-900 flex items-center gap-1 transition-colors"
              >
                <span>View Full Ledger</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>

            {loading ? (
              <div className="p-8 text-center text-xs text-slate-400">
                Loading clinical records from database...
              </div>
            ) : recentECGs.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 border-b border-border text-slate-500 uppercase text-[10px] font-bold">
                    <tr>
                      <th className="px-5 py-3">Study / File</th>
                      <th className="px-5 py-3">Recorded</th>
                      <th className="px-5 py-3">Top Condition</th>
                      <th className="px-5 py-3">Model Score</th>
                      <th className="px-5 py-3">Triage Urgency</th>
                      <th className="px-5 py-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border font-medium">
                    {recentECGs.slice(0, 5).map((study) => (
                      <tr key={study.ecg_id} className="hover:bg-slate-50/80 transition-colors">
                        <td className="px-5 py-3.5">
                          <div className="flex items-center gap-2.5">
                            <div className="w-7 h-7 rounded-lg bg-teal-50 border border-teal-200 flex items-center justify-center text-teal-700 flex-shrink-0">
                              <Heart className="w-3.5 h-3.5" />
                            </div>
                            <div>
                              <p className="font-bold text-navy-850 truncate max-w-[140px]">
                                {study.file_name}
                              </p>
                              <p className="text-[10px] text-slate-400 font-mono">
                                HR: {study.heart_rate_bpm ? `${study.heart_rate_bpm} bpm` : '—'}
                              </p>
                            </div>
                          </div>
                        </td>
                        <td className="px-5 py-3.5 text-slate-500 text-[11px] font-mono">
                          {new Date(study.timestamp).toLocaleDateString()}
                        </td>
                        <td className="px-5 py-3.5 font-bold text-navy-850">
                          {study.top_condition || 'Normal Digital Scan'}
                        </td>
                        <td className="px-5 py-3.5 font-mono font-bold text-teal-700">
                          {formatScorePercentage(study.top_condition_prob)}
                        </td>
                        <td className="px-5 py-3.5">
                          <span
                            className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                              study.urgency === 'emergency'
                                ? 'bg-red-50 text-red-600 border border-red-200'
                                : study.urgency === 'see_doctor_today'
                                ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            }`}
                          >
                            {study.urgency.replace(/_/g, ' ')}
                          </span>
                        </td>
                        <td className="px-5 py-3.5 text-right">
                          <button
                            onClick={() => handleOpenStudy(study.ecg_id)}
                            className="inline-flex items-center gap-1 text-[11px] font-bold text-teal-700 hover:text-teal-900 bg-teal-50 hover:bg-teal-100 border border-teal-200 px-2.5 py-1 rounded-lg transition-colors"
                          >
                            <span>Inspect</span>
                            <ArrowUpRight className="w-3 h-3" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-10 text-center space-y-3">
                <div className="w-12 h-12 rounded-2xl bg-slate-100 border border-border flex items-center justify-center mx-auto text-slate-400">
                  <FileText className="w-6 h-6" />
                </div>
                <div>
                  <h4 className="text-sm font-bold text-navy-850">No Clinical Studies Recorded Yet</h4>
                  <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                    Upload your first digital 12-lead signal or click one of the PTB-XL sample buttons to test.
                  </p>
                </div>
                <button
                  onClick={() => setMode('ecg')}
                  className="btn-clinical-primary text-xs mx-auto"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Launch ECG Workspace</span>
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Model Specs & Clinical Reference (4 Cols) */}
        <div className="lg:col-span-4 space-y-4">
          {/* Card: Model Architecture & Benchmark Matrix */}
          <div className="clinical-card p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <span className="text-xs font-bold uppercase tracking-wider text-navy-850">
                Diagnostic Superclasses (PTB-XL)
              </span>
              <span className="text-[10px] font-mono font-bold bg-teal-50 text-teal-700 border border-teal-200 px-2 py-0.5 rounded">
                5 Targets
              </span>
            </div>

            <div className="space-y-2">
              {[
                { code: 'NORM', name: 'Normal ECG', threshold: '0.51', auc: '0.9335' },
                { code: 'MI', name: 'Myocardial Infarction', threshold: '0.41', auc: '0.9118' },
                { code: 'STTC', name: 'ST/T-Wave Changes', threshold: '0.70', auc: '0.9322' },
                { code: 'CD', name: 'Conduction Disturbance', threshold: '0.66', auc: '0.9111' },
                { code: 'HYP', name: 'Hypertrophy', threshold: '0.75', auc: '0.8327' },
              ].map((c) => (
                <div key={c.code} className="p-2.5 bg-slate-50 rounded-xl border border-border flex items-center justify-between text-xs">
                  <div>
                    <span className="font-bold text-navy-850">{c.code}</span>
                    <span className="text-[11px] text-slate-500 ml-1.5">{c.name}</span>
                  </div>
                  <div className="text-right font-mono text-[10px]">
                    <span className="text-slate-400">θ = {c.threshold}</span>
                    <span className="text-teal-700 font-bold ml-2">AUC {c.auc}</span>
                  </div>
                </div>
              ))}
            </div>

            <div className="p-3 bg-surface-secondary rounded-xl border border-border text-[11px] text-slate-600 leading-relaxed">
              <strong>Evaluation Standards:</strong> Evaluated strictly once on 2,158 held-out records of PhysioNet PTB-XL Fold 10. Macro AUROC 0.9265, Macro F1 0.7520.
            </div>
          </div>

          {/* Card: Emergency Shortcut */}
          <div className="clinical-card p-5 border-l-4 border-l-red-500 space-y-3 bg-red-50/20">
            <div className="flex items-center gap-2 text-red-700">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              <h4 className="text-xs font-bold uppercase tracking-wider">Clinical Safety Protocol</h4>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              If the patient exhibits crushing chest pain, radiating arm/jaw pain, or severe shortness of breath, do not await computer interpretation.
            </p>
            <button
              onClick={() => setMode('emergency')}
              className="btn-clinical-danger w-full text-xs shadow-sm"
            >
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>Launch Emergency Triage</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
