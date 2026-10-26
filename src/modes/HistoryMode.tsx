import React, { useState, useEffect } from 'react';
import {
  Activity, Heart, Search, ArrowUpRight, RefreshCw, Clock
} from 'lucide-react';
import { useStore } from '../store/useStore';
import { api, type ECGHistoryItem, type HistoryRecord } from '../lib/api';

export const HistoryMode: React.FC = () => {
  const { setActiveECGStudyId, setMode } = useStore();
  const [activeFilter, setActiveFilter] = useState<'all' | 'ecg' | 'vitals'>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [ecgHistory, setEcgHistory] = useState<ECGHistoryItem[]>([]);
  const [vitalsHistory, setVitalsHistory] = useState<HistoryRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchRecords = async () => {
    setLoading(true);
    try {
      const [ecgRes, vitalsRes] = await Promise.allSettled([
        api.getECGHistory(),
        api.getVitalsHistory(60),
      ]);

      if (ecgRes.status === 'fulfilled' && ecgRes.value?.ecg_sessions) {
        setEcgHistory(ecgRes.value.ecg_sessions);
      }
      if (vitalsRes.status === 'fulfilled' && vitalsRes.value?.records) {
        setVitalsHistory(vitalsRes.value.records);
      }
    } catch (e) {
      console.error('Failed to load history:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecords();
  }, []);

  const handleInspectECG = (ecgId: string) => {
    setActiveECGStudyId(ecgId);
    setMode('ecg');
  };

  // Combine and sort records by timestamp
  const combinedRecords = [
    ...ecgHistory.map(e => ({
      type: 'ecg' as const,
      id: e.ecg_id,
      timestamp: e.timestamp,
      title: e.top_condition || '12-Lead ECG Analysis',
      subtitle: e.file_name,
      urgency: e.urgency,
      score: e.top_condition_prob,
      heartRate: e.heart_rate_bpm,
      metrics: `HR: ${e.heart_rate_bpm ? `${e.heart_rate_bpm} bpm` : '—'} · Rhythm: ${e.rhythm || 'Standard'}`,
    })),
    ...vitalsHistory.map(v => ({
      type: 'vitals' as const,
      id: v.id,
      timestamp: v.timestamp,
      title: `Vitals Assessment (${v.risk_tier} Risk)`,
      subtitle: `BP: ${v.bp_sys}/${v.bp_dia} mmHg · HR: ${v.hr} bpm`,
      urgency: v.risk_tier === 'Elevated' ? 'see_doctor_today' : 'routine',
      score: v.risk_score / 100,
      heartRate: v.hr,
      metrics: `SpO2: ${v.spo2}% · Weight: ${v.weight} kg`,
    })),
  ].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

  // Filter records
  const filteredRecords = combinedRecords.filter(rec => {
    if (activeFilter === 'ecg' && rec.type !== 'ecg') return false;
    if (activeFilter === 'vitals' && rec.type !== 'vitals') return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      return (
        rec.title.toLowerCase().includes(q) ||
        rec.subtitle.toLowerCase().includes(q) ||
        rec.metrics.toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header & Controls */}
      <div className="clinical-card p-6 bg-white flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-border">
        <div>
          <div className="flex items-center gap-2 text-teal-700 text-xs font-bold uppercase tracking-wider">
            <Clock className="w-4 h-4" />
            <span>Longitudinal Patient Records</span>
          </div>
          <h2 className="text-xl font-bold text-navy-850 mt-1">
            Diagnostic History & Analysis Ledger
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Complete chronological record of 12-lead digital ECG analyses and clinical vitals evaluations.
          </p>
        </div>

        <button
          onClick={fetchRecords}
          className="btn-clinical-secondary text-xs"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Ledger</span>
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        {/* Type Filter Buttons */}
        <div className="flex bg-slate-100 p-1 rounded-xl border border-border">
          <button
            onClick={() => setActiveFilter('all')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeFilter === 'all'
                ? 'bg-white text-navy-850 shadow-sm'
                : 'text-slate-500 hover:text-navy-850'
            }`}
          >
            All Studies ({combinedRecords.length})
          </button>
          <button
            onClick={() => setActiveFilter('ecg')}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeFilter === 'ecg'
                ? 'bg-white text-navy-850 shadow-sm'
                : 'text-slate-500 hover:text-navy-850'
            }`}
          >
            <Heart className="w-3.5 h-3.5 text-teal-600" />
            <span>ECG ({ecgHistory.length})</span>
          </button>
          <button
            onClick={() => setActiveFilter('vitals')}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeFilter === 'vitals'
                ? 'bg-white text-navy-850 shadow-sm'
                : 'text-slate-500 hover:text-navy-850'
            }`}
          >
            <Activity className="w-3.5 h-3.5 text-teal-600" />
            <span>Vitals ({vitalsHistory.length})</span>
          </button>
        </div>

        {/* Search input */}
        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search records or findings..."
            className="clinical-input pl-9 py-2 text-xs"
          />
        </div>
      </div>

      {/* Ledger Table */}
      <div className="clinical-card overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-xs text-slate-400">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto text-teal-600 mb-2" />
            <span>Fetching longitudinal records from database...</span>
          </div>
        ) : filteredRecords.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-border text-slate-500 uppercase text-[10px] font-bold">
                <tr>
                  <th className="px-5 py-3">Type</th>
                  <th className="px-5 py-3">Study / Entry</th>
                  <th className="px-5 py-3">Clinical Metrics</th>
                  <th className="px-5 py-3">Recorded At</th>
                  <th className="px-5 py-3">Triage Urgency</th>
                  <th className="px-5 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border font-medium">
                {filteredRecords.map((item) => (
                  <tr key={`${item.type}-${item.id}`} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-5 py-4">
                      <div className={`w-8 h-8 rounded-xl flex items-center justify-center ${
                        item.type === 'ecg'
                          ? 'bg-teal-50 border border-teal-200 text-teal-700'
                          : 'bg-blue-50 border border-blue-200 text-blue-700'
                      }`}>
                        {item.type === 'ecg' ? <Heart className="w-4 h-4" /> : <Activity className="w-4 h-4" />}
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <p className="font-bold text-navy-850">{item.title}</p>
                      <p className="text-[11px] text-slate-400 font-mono mt-0.5">{item.subtitle}</p>
                    </td>
                    <td className="px-5 py-4 font-mono text-[11px] text-slate-600">
                      {item.metrics}
                    </td>
                    <td className="px-5 py-4 text-slate-500 text-[11px] font-mono">
                      {new Date(item.timestamp).toLocaleString()}
                    </td>
                    <td className="px-5 py-4">
                      <span
                        className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                          item.urgency === 'emergency'
                            ? 'bg-red-50 text-red-600 border border-red-200'
                            : item.urgency === 'see_doctor_today'
                            ? 'bg-amber-50 text-amber-700 border border-amber-200'
                            : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        }`}
                      >
                        {item.urgency.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-right">
                      {item.type === 'ecg' ? (
                        <button
                          onClick={() => handleInspectECG(item.id)}
                          className="btn-clinical-secondary py-1 px-3 text-[11px]"
                        >
                          <span>Open Study</span>
                          <ArrowUpRight className="w-3 h-3" />
                        </button>
                      ) : (
                        <span className="text-[11px] text-slate-400 font-mono">Vitals Logged</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-12 text-center space-y-3">
            <Clock className="w-8 h-8 mx-auto text-slate-300" />
            <h4 className="text-sm font-bold text-navy-850">No Records Found</h4>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              No clinical studies match the current search or filter criteria.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
