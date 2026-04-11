import React from 'react';
import { useStore } from '../store/useStore';
import { Shield, PhoneCall, Globe, LogOut } from 'lucide-react';
import { translations } from '../lib/translations';

export const Navbar: React.FC = () => {
  const { language, setLanguage, setMode, clearProfile } = useStore();
  const t = translations[language];

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 px-6 py-4 flex items-center justify-between border-b border-white/10 bg-slate-950/50 backdrop-blur-xl">
      <div className="flex items-center gap-2 cursor-pointer transition-transform hover:scale-105" onClick={() => setMode('routine')}>
        <div className="w-10 h-10 bg-emerald-500 rounded-lg flex items-center justify-center shadow-lg shadow-emerald-500/20">
          <Shield className="text-white w-6 h-6" />
        </div>
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white">CARDIAC<span className="text-emerald-500">AI</span></h1>
          <p className="text-[10px] text-slate-400 font-medium tracking-[0.2em] uppercase">V2.0 WEB-PRO</p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <button 
          onClick={() => setLanguage(language === 'en' ? 'hi' : 'en')}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-white/5 hover:bg-slate-800 transition-colors text-xs font-medium text-slate-300"
        >
          <Globe className="w-3.5 h-3.5" />
          {language === 'en' ? 'हिन्दी' : 'ENGLISH'}
        </button>

        <button 
          onClick={() => setMode('emergency')}
          className="btn-danger group h-10 px-6"
        >
          <PhoneCall className="w-4 h-4 group-hover:rotate-12 transition-transform" />
          <span className="hidden md:inline font-black tracking-tighter ml-1">{t.sos}</span>
        </button>

        <button 
          onClick={clearProfile}
          className="p-2 text-slate-400 hover:text-white transition-colors"
          title={t.reset_data}
        >
          <LogOut className="w-5 h-5" />
        </button>
      </div>
    </nav>
  );
};
