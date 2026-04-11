import React from 'react';
import { motion } from 'framer-motion';

interface RiskArcProps {
  score: number;
  tier: string;
}

export const RiskArc: React.FC<RiskArcProps> = ({ score, tier }) => {
  const radius = 90;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  const getTierColor = (t: string) => {
    switch (t) {
      case 'Low': return 'text-emerald-500';
      case 'Borderline': return 'text-gold-500';
      case 'Elevated': return 'text-red-500';
      default: return 'text-emerald-500';
    }
  };

  const getStrokeColor = (t: string) => {
    switch (t) {
      case 'Low': return '#10b981';
      case 'Borderline': return '#f59e0b';
      case 'Elevated': return '#ef4444';
      default: return '#10b981';
    }
  };

  return (
    <div className="relative flex flex-col items-center justify-center p-8 bg-slate-900/40 rounded-3xl border border-white/5 backdrop-blur-sm">
      <svg className="w-64 h-64 -rotate-90">
        {/* Background Arc */}
        <circle
          cx="128"
          cy="128"
          r={radius}
          fill="transparent"
          stroke="rgba(255,255,255,0.05)"
          strokeWidth="12"
          strokeLinecap="round"
        />
        {/* Progress Arc */}
        <motion.circle
          cx="128"
          cy="128"
          r={radius}
          fill="transparent"
          stroke={getStrokeColor(tier)}
          strokeWidth="12"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.5, ease: "easeOut" }}
          strokeLinecap="round"
        />
      </svg>
      
      <div className="absolute inset-0 flex flex-col items-center justify-center pt-4">
        <motion.span 
          initial={{ opacity: 0, scale: 0.5 }}
          animate={{ opacity: 1, scale: 1 }}
          className="text-5xl font-black tracking-tighter"
        >
          {Math.round(score)}%
        </motion.span>
        <span className={`text-xs font-bold uppercase tracking-[0.2em] mt-1 ${getTierColor(tier)}`}>
          {tier} Risk
        </span>
      </div>

      <div className="mt-8 flex gap-8 w-full justify-center">
        <div className="text-center">
          <p className="text-[10px] text-slate-500 uppercase font-bold">Confidence</p>
          <p className="text-sm font-semibold text-slate-300">98.2%</p>
        </div>
        <div className="text-center border-l border-white/10 pl-8">
          <p className="text-[10px] text-slate-500 uppercase font-bold">Calibration</p>
          <p className="text-sm font-semibold text-slate-300">Indian Cohort</p>
        </div>
      </div>
    </div>
  );
};
