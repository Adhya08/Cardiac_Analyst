import React from 'react';
import { motion } from 'framer-motion';

interface RiskArcProps {
  score: number;
  tier: string;
}

export const RiskArc: React.FC<RiskArcProps> = ({ score, tier }) => {
  const radius = 90;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (Math.min(100, Math.max(0, score)) / 100) * circumference;

  const getTierColor = (t: string) => {
    switch (t) {
      case 'Low': return 'text-emerald-700';
      case 'Borderline': return 'text-amber-700';
      case 'Elevated': return 'text-red-700';
      default: return 'text-emerald-700';
    }
  };

  const getStrokeColor = (t: string) => {
    switch (t) {
      case 'Low': return '#0F8B83';
      case 'Borderline': return '#D97706';
      case 'Elevated': return '#DC2626';
      default: return '#0F8B83';
    }
  };

  return (
    <div className="relative flex flex-col items-center justify-center p-6 bg-white rounded-2xl border border-border shadow-card">
      <svg className="w-56 h-56 -rotate-90">
        {/* Background Arc */}
        <circle
          cx="112"
          cy="112"
          r={radius}
          fill="transparent"
          stroke="#EDF2F7"
          strokeWidth="12"
          strokeLinecap="round"
        />
        {/* Progress Arc */}
        <motion.circle
          cx="112"
          cy="112"
          r={radius}
          fill="transparent"
          stroke={getStrokeColor(tier)}
          strokeWidth="12"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.2, ease: "easeOut" }}
          strokeLinecap="round"
        />
      </svg>
      
      <div className="absolute inset-0 flex flex-col items-center justify-center pt-2">
        <motion.span 
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          className="text-4xl font-black tracking-tight text-navy-850 tabular-nums"
        >
          {Math.round(score)}%
        </motion.span>
        <span className={`text-[11px] font-bold uppercase tracking-wider mt-0.5 ${getTierColor(tier)}`}>
          {tier} ASCVD Risk
        </span>
      </div>

      <div className="mt-4 flex flex-col items-center gap-2 w-full justify-center border-t border-border pt-4">
        <span className="text-[10px] font-bold uppercase tracking-wider text-amber-800 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full">
          Experimental, not validated
        </span>
        <div className="flex gap-6 w-full justify-center">
          <div className="text-center">
            <p className="text-[10px] text-slate-400 uppercase font-bold">Model Engine</p>
            <p className="text-xs font-bold text-navy-850 font-mono">LightGBM (Research)</p>
          </div>
          <div className="text-center border-l border-border pl-6">
            <p className="text-[10px] text-slate-400 uppercase font-bold">Reference Calibration</p>
            <p className="text-xs font-bold text-navy-850">Framingham / ICMR</p>
          </div>
        </div>
      </div>
    </div>
  );
};
