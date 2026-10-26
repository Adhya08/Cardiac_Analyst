import React from 'react';
import { useStore } from '../store/useStore';
import { Shield, PhoneCall, Globe, LogOut, AlertTriangle } from 'lucide-react';
import { translations } from '../lib/translations';

export const Navbar: React.FC = () => {
  const { language, setLanguage, setMode, clearProfile } = useStore();
  const t = translations[language];
  const headerRef = React.useRef<HTMLElement>(null);
  const [headerHeight, setHeaderHeight] = React.useState<number>(84);

  React.useEffect(() => {
    if (!headerRef.current) return;
    const updateHeight = () => {
      if (headerRef.current) {
        setHeaderHeight(headerRef.current.offsetHeight);
      }
    };
    updateHeight();
    const ro = new ResizeObserver(updateHeight);
    ro.observe(headerRef.current);
    return () => ro.disconnect();
  }, []);

  return (
    <>
      <header ref={headerRef} className="fixed top-0 left-0 right-0 z-50">
        {/* Persistent Visible Disclaimer Banner */}
        <div className="bg-amber-950/90 border-b border-amber-500/30 px-4 py-1.5 backdrop-blur-xl flex items-center justify-center gap-2 text-center shadow-lg">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 animate-pulse" />
          <p className="text-[11px] font-medium text-amber-200 leading-tight">
            <strong className="font-bold text-amber-300 mr-1.5 uppercase tracking-wide">
              {t.disclaimer_banner_title}:
            </strong>
            {t.disclaimer_banner_text}
          </p>
        </div>

        <nav className="px-6 py-3 flex items-center justify-between border-b border-white/10 bg-slate-950/80 backdrop-blur-xl">
          <div className="flex items-center gap-2.5 cursor-pointer transition-transform hover:scale-105" onClick={() => setMode('routine')}>
            <div className="w-9 h-9 bg-emerald-500 rounded-lg flex items-center justify-center shadow-lg shadow-emerald-500/20">
              <Shield className="text-white w-5 h-5" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-white leading-tight">CARDIAC<span className="text-emerald-500">AI</span></h1>
              <p className="text-[9px] text-slate-400 font-medium tracking-[0.2em] uppercase">PTB-XL RESNET-1D</p>
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
              className="btn-danger group h-9 px-5 text-xs"
            >
              <PhoneCall className="w-3.5 h-3.5 group-hover:rotate-12 transition-transform" />
              <span className="hidden md:inline font-black tracking-tighter ml-1">{t.sos}</span>
            </button>

            <button 
              onClick={clearProfile}
              className="p-2 text-slate-400 hover:text-white transition-colors"
              title={t.reset_data}
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </nav>
      </header>
      {/* Spacer to reserve header height in normal document flow */}
      <div style={{ height: headerHeight }} aria-hidden="true" />
    </>
  );
};
