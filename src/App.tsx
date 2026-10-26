import React from 'react';
import { useStore } from './store/useStore';
import { Navbar } from './components/Navbar';
import { RoutineMode } from './modes/RoutineMode';
import { ECGMode } from './modes/ECGMode';
import { EmergencyMode } from './modes/EmergencyMode';
import { Activity, Heart, AlertTriangle } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

function App() {
  const { currentMode, setMode } = useStore();

  const renderMode = () => {
    switch (currentMode) {
      case 'routine': return <RoutineMode />;
      case 'ecg': return <ECGMode />;
      case 'emergency': return <EmergencyMode />;
      default: return <RoutineMode />;
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50">
      <Navbar />
      
      {/* Sidebar / Mode Switcher */}
      <div className="fixed left-6 top-1/2 -translate-y-1/2 flex flex-col gap-4 z-40">
        <ModeTab 
          active={currentMode === 'routine'} 
          onClick={() => setMode('routine')}
          icon={<Activity className="w-5 h-5" />}
          label="Routine"
        />
        <ModeTab 
          active={currentMode === 'ecg'} 
          onClick={() => setMode('ecg')}
          icon={<Heart className="w-5 h-5" />}
          label="ECG Diagnostic"
        />
        <ModeTab 
          active={currentMode === 'emergency'} 
          onClick={() => setMode('emergency')}
          icon={<AlertTriangle className="w-5 h-5" />}
          label="Emergency"
        />
      </div>

      <main className="pt-6 pl-24 pr-8 pb-12 overflow-x-hidden">
        <AnimatePresence mode="wait">
          <motion.div
            key={currentMode}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
          >
            {renderMode()}
          </motion.div>
        </AnimatePresence>
      </main>

      {/* Decorative Background Elements */}
      <div className="fixed top-0 left-0 w-full h-full pointer-events-none -z-10 overflow-hidden">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-emerald-500/10 blur-[120px] rounded-full animate-pulse-slow"></div>
        <div className="absolute bottom-[0%] right-[-10%] w-[30%] h-[30%] bg-gold-500/10 blur-[120px] rounded-full animate-pulse-slow font-delay-2000"></div>
      </div>
    </div>
  );
}

interface ModeTabProps {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}

const ModeTab: React.FC<ModeTabProps> = ({ active, onClick, icon, label }) => {
  return (
    <button 
      onClick={onClick}
      className={`group relative flex items-center justify-center w-14 h-14 rounded-2xl transition-all duration-300 ${
        active 
          ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/20' 
          : 'bg-slate-900 text-slate-500 hover:text-slate-300 hover:bg-slate-800'
      }`}
    >
      {icon}
      <span className="absolute left-[calc(100%+12px)] px-3 py-1.5 bg-slate-800 text-white text-xs font-medium rounded-lg opacity-0 -translate-x-2 pointer-events-none group-hover:opacity-100 group-hover:translate-x-0 transition-all whitespace-nowrap shadow-xl border border-white/5">
        {label}
      </span>
      {active && (
        <motion.div 
          layoutId="active-indicator"
          className="absolute -left-1 w-1 h-8 bg-emerald-400 rounded-r-full"
        />
      )}
    </button>
  );
};

export default App;
