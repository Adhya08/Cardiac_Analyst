import React, { useEffect } from 'react';
import {
  Menu, Globe, PhoneCall,
  User, ChevronRight
} from 'lucide-react';
import { useStore, type NavigationMode } from '../store/useStore';
import { api } from '../lib/api';

interface TopBarProps {
  onToggleMobileMenu: () => void;
  onOpenProfile: () => void;
}

const MODE_TITLES: Record<NavigationMode, { titleEn: string; titleHi: string; category: string }> = {
  overview: {
    titleEn: 'Clinical Overview & Diagnostic Summary',
    titleHi: 'क्लिनिकल अवलोकन और सारांश',
    category: 'Workstation',
  },
  ecg: {
    titleEn: '12-Lead Digital ECG Analysis Workspace',
    titleHi: '12-लीड डिजिटल ईसीजी विश्लेषण',
    category: 'Diagnostic Suite',
  },
  routine: {
    titleEn: 'Cardiovascular Risk Screening & Vitals',
    titleHi: 'हृदय जोखिम स्क्रीनिंग और वाइटल्स',
    category: 'Preventative Care',
  },
  history: {
    titleEn: 'Diagnostic History & Longitudinal Records',
    titleHi: 'डायग्नोस्टिक इतिहास और रिकॉर्ड',
    category: 'Medical Ledger',
  },
  emergency: {
    titleEn: 'Acute Triage & Rapid Hospital Dispatch',
    titleHi: 'आपातकालीन ट्राइएज और अस्पताल सहायता',
    category: 'Critical Care',
  },
};

export const TopBar: React.FC<TopBarProps> = ({
  onToggleMobileMenu,
  onOpenProfile,
}) => {
  const { currentMode, isSidebarCollapsed, language, setLanguage, setMode, user, backendHealth, setBackendHealth } = useStore();
  const modeInfo = MODE_TITLES[currentMode] || MODE_TITLES.overview;

  // Poll real backend health on mount
  useEffect(() => {
    let mounted = true;
    const checkHealth = async () => {
      try {
        const res = await api.getHealth();
        if (mounted) {
          setBackendHealth({
            isHealthy: res.status === 'healthy',
            modelLoaded: res.model_loaded,
            modelAccuracy: res.model_accuracy || '92.65% AUROC',
            version: 'ptbxl-resnet1d-v1.0',
          });
        }
      } catch {
        if (mounted) {
          setBackendHealth({
            isHealthy: false,
            modelLoaded: false,
          });
        }
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [setBackendHealth]);

  return (
    <header
      className={`fixed top-0 right-0 z-40 bg-white/95 backdrop-blur-md border-b border-border transition-all duration-300 ${
        isSidebarCollapsed ? 'left-0 lg:left-20' : 'left-0 lg:left-64'
      }`}
    >
      {/* Main Top Application Bar */}
      <div className="px-5 py-3 flex items-center justify-between gap-4">
        {/* Left: Mobile hamburger + Page Breadcrumb */}
        <div className="flex items-center gap-3">
          <button
            onClick={onToggleMobileMenu}
            className="p-2 -ml-2 rounded-lg text-slate-600 hover:text-navy-850 hover:bg-slate-100 lg:hidden"
            aria-label="Open Navigation"
          >
            <Menu className="w-5 h-5" />
          </button>

          <div>
            <div className="flex items-center gap-1.5 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
              <span>{modeInfo.category}</span>
              <ChevronRight className="w-3 h-3 text-slate-300" />
              <span className="text-teal-700">{currentMode.toUpperCase()}</span>
            </div>
            <h2 className="text-base font-bold text-navy-850 tracking-tight leading-tight">
              {language === 'hi' ? modeInfo.titleHi : modeInfo.titleEn}
            </h2>
          </div>
        </div>

        {/* Right Actions: Real Health Status, Language, Emergency SOS, Profile */}
        <div className="flex items-center gap-2.5">
          {/* Live Model Engine Status Chip */}
          <div
            title="Real-time backend inference service status"
            className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-xl border border-border bg-surface-secondary text-xs font-semibold text-slate-700"
          >
            <span
              className={`w-2 h-2 rounded-full ${
                backendHealth.isHealthy && backendHealth.modelLoaded
                  ? 'bg-emerald-500 animate-pulse'
                  : 'bg-amber-500'
              }`}
            />
            <span className="font-mono text-[11px]">
              {backendHealth.isHealthy ? 'Model Active' : 'Connecting...'}
            </span>
          </div>

          {/* Language Switcher Button */}
          <button
            onClick={() => setLanguage(language === 'en' ? 'hi' : 'en')}
            title="Toggle Language (English / हिन्दी)"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-border bg-white hover:bg-slate-50 text-slate-700 text-xs font-bold transition-all shadow-button-secondary"
          >
            <Globe className="w-3.5 h-3.5 text-slate-500" />
            <span>{language === 'en' ? 'हिन्दी' : 'EN'}</span>
          </button>

          {/* Patient Profile Trigger */}
          <button
            onClick={onOpenProfile}
            title="Patient Profile & Clinical Context"
            className="flex items-center gap-2 px-3 py-1.5 rounded-xl border border-border bg-white hover:bg-slate-50 text-slate-700 text-xs font-bold transition-all shadow-button-secondary"
          >
            <div className="w-5 h-5 rounded-full bg-teal-50 border border-teal-200 flex items-center justify-center text-teal-700">
              <User className="w-3 h-3" />
            </div>
            <span className="hidden md:inline text-navy-850">
              {user?.age ? `${user.sex || 'Patient'}, ${user.age}y` : 'Patient Profile'}
            </span>
          </button>

          {/* Direct Emergency 112 SOS Button */}
          <button
            onClick={() => setMode('emergency')}
            title="Emergency Triage & Hospital Routing"
            className="btn-clinical-danger px-3.5 py-1.5 text-xs shadow-sm"
          >
            <PhoneCall className="w-3.5 h-3.5 animate-pulse" />
            <span className="font-black tracking-tight">112 SOS</span>
          </button>
        </div>
      </div>
    </header>
  );
};
