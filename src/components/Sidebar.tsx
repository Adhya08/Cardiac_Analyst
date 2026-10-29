import React from 'react';
import {
  LayoutDashboard, Activity, Heart, Clock, AlertTriangle,
  ChevronLeft, ChevronRight, Settings, HeartPulse, LogOut, LogIn
} from 'lucide-react';
import { useStore, type NavigationMode } from '../store/useStore';
import { isAuthenticated } from '../lib/api';

interface NavItem {
  id: NavigationMode;
  labelEn: string;
  labelHi: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
  tooltip: string;
}

const NAV_ITEMS: NavItem[] = [
  {
    id: 'overview',
    labelEn: 'Overview',
    labelHi: 'अवलोकन',
    icon: LayoutDashboard,
    tooltip: 'Clinical Workstation & Patient Summary',
  },
  {
    id: 'ecg',
    labelEn: 'ECG Analysis',
    labelHi: 'ईसीजी विश्लेषण',
    icon: Heart,
    badge: '12-Lead',
    tooltip: 'PTB-XL Residual 1D CNN Inference',
  },
  {
    id: 'routine',
    labelEn: 'Routine Screening',
    labelHi: 'नियमित जांच',
    icon: Activity,
    tooltip: 'Vitals Logging & LightGBM Risk',
  },
  {
    id: 'history',
    labelEn: 'Patient History',
    labelHi: 'मरीज का इतिहास',
    icon: Clock,
    tooltip: 'Diagnostic Studies & Vitals Ledger',
  },
  {
    id: 'emergency',
    labelEn: 'Emergency Support',
    labelHi: 'आपातकालीन सहायता',
    icon: AlertTriangle,
    badge: '112',
    tooltip: 'NICE CG95 Triage & Hospital Routing',
  },
];

interface SidebarProps {
  isOpenMobile: boolean;
  onCloseMobile: () => void;
  onOpenProfile: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpenMobile,
  onCloseMobile,
  onOpenProfile,
}) => {
  const { currentMode, setMode, isSidebarCollapsed, toggleSidebar, language, backendHealth, authUser, logout, openAuthModal } = useStore();

  const handleSelect = (mode: NavigationMode) => {
    setMode(mode);
    onCloseMobile();
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpenMobile && (
        <div
          onClick={onCloseMobile}
          className="fixed inset-0 bg-navy-950/40 backdrop-blur-sm z-40 lg:hidden"
          aria-hidden="true"
        />
      )}

      {/* Main Persistent Sidebar */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 bg-white border-r border-border transition-all duration-300 flex flex-col justify-between shadow-panel ${
          isOpenMobile ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        } ${isSidebarCollapsed ? 'w-20' : 'w-64'}`}
      >
        {/* Top Logo & App Brand */}
        <div className="p-4 border-b border-border flex items-center justify-between">
          <div
            onClick={() => handleSelect('overview')}
            className="flex items-center gap-3 cursor-pointer group select-none"
          >
            <div className="w-10 h-10 rounded-xl bg-teal-600 text-white flex items-center justify-center shadow-button transition-transform group-hover:scale-105 flex-shrink-0">
              <HeartPulse className="w-6 h-6" />
            </div>
            {!isSidebarCollapsed && (
              <div className="overflow-hidden">
                <div className="flex items-center gap-1.5">
                  <h1 className="text-sm font-bold text-navy-850 tracking-tight leading-tight">
                    CARDIAC<span className="text-teal-600">ANALYST</span>
                  </h1>
                </div>
                <p className="text-[10px] text-slate-400 font-medium uppercase tracking-wider truncate">
                  Clinical Workstation
                </p>
              </div>
            )}
          </div>

          {/* Desktop Collapse Toggle */}
          <button
            onClick={toggleSidebar}
            title={isSidebarCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
            aria-label={isSidebarCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
            className="hidden lg:flex w-7 h-7 rounded-lg text-slate-400 hover:text-navy-850 hover:bg-slate-100 items-center justify-center transition-colors"
          >
            {isSidebarCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>

        {/* Navigation Items List */}
        <nav className="p-3 space-y-1.5 flex-1 overflow-y-auto" aria-label="Workstation Navigation">
          <div className={`px-3 py-1.5 text-[10px] font-bold text-slate-400 uppercase tracking-widest ${isSidebarCollapsed ? 'text-center' : ''}`}>
            {isSidebarCollapsed ? '•' : 'Navigation'}
          </div>

          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = currentMode === item.id;
            const label = language === 'hi' ? item.labelHi : item.labelEn;

            return (
              <button
                key={item.id}
                onClick={() => handleSelect(item.id)}
                title={`${label} — ${item.tooltip}`}
                className={`w-full flex items-center gap-3 px-3.5 py-3 rounded-xl font-semibold text-xs transition-all relative group ${
                  isActive
                    ? 'bg-teal-50 text-teal-800 border border-teal-200 shadow-sm'
                    : 'text-slate-600 hover:text-navy-850 hover:bg-slate-50 border border-transparent'
                } ${isSidebarCollapsed ? 'justify-center px-2' : ''}`}
              >
                <Icon
                  className={`w-4 h-4 flex-shrink-0 transition-transform ${
                    isActive ? 'text-teal-700' : 'text-slate-400 group-hover:text-navy-850 group-hover:scale-110'
                  }`}
                />

                {!isSidebarCollapsed && (
                  <span className="truncate flex-1 text-left">{label}</span>
                )}

                {!isSidebarCollapsed && item.badge && (
                  <span
                    className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider ${
                      item.id === 'emergency'
                        ? 'bg-red-50 text-red-600 border border-red-200'
                        : 'bg-teal-100 text-teal-700'
                    }`}
                  >
                    {item.badge}
                  </span>
                )}

                {/* Collapsed Tooltip */}
                {isSidebarCollapsed && (
                  <div className="absolute left-[calc(100%+12px)] px-3 py-1.5 bg-navy-900 text-white text-xs font-semibold rounded-lg opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity whitespace-nowrap shadow-elevated z-50 flex items-center gap-2">
                    <span>{label}</span>
                    <span className="text-[10px] text-teal-400">· {item.tooltip}</span>
                  </div>
                )}
              </button>
            );
          })}
        </nav>

        {/* Bottom Profile & Model Provenance */}
        <div className="p-3 border-t border-border space-y-2 bg-surface-secondary">
          {/* Real Model Service Status */}
          <div className={`p-2.5 rounded-xl border flex items-center gap-2.5 ${
            backendHealth.isHealthy
              ? 'bg-emerald-50/60 border-emerald-200/60'
              : 'bg-amber-50 border-amber-200'
          } ${isSidebarCollapsed ? 'justify-center p-2' : ''}`}>
            <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
              backendHealth.isHealthy ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'
            }`} />
            {!isSidebarCollapsed && (
              <div className="overflow-hidden">
                <p className="text-[11px] font-bold text-navy-850 leading-tight">
                  ResNet1D Local Engine
                </p>
                <p className="text-[10px] text-slate-500 font-mono truncate">
                  {backendHealth.modelLoaded ? 'ONNX Active · 7.46 ms' : 'Engine Offline'}
                </p>
              </div>
            )}
          </div>

          {/* Profile & Settings Button */}
          <button
            onClick={onOpenProfile}
            className={`w-full flex items-center gap-2.5 p-2 rounded-xl text-xs font-semibold text-slate-600 hover:text-navy-850 hover:bg-white transition-all border border-transparent hover:border-border ${
              isSidebarCollapsed ? 'justify-center' : ''
            }`}
            title="Configure Patient Profile & Demographics"
          >
            <Settings className="w-4 h-4 text-slate-400" />
            {!isSidebarCollapsed && <span>Patient Settings</span>}
          </button>

          {/* Dedicated Sign Out / Sign In Action */}
          {isAuthenticated() ? (
            <button
              onClick={logout}
              className={`w-full flex items-center gap-2.5 p-2 rounded-xl text-xs font-semibold text-rose-600 hover:text-rose-700 hover:bg-rose-50 transition-all border border-transparent hover:border-rose-200 ${
                isSidebarCollapsed ? 'justify-center' : ''
              }`}
              title={`Sign Out of Patient Account ${authUser?.email ? `(${authUser.email})` : ''}`}
            >
              <LogOut className="w-4 h-4 text-rose-500 flex-shrink-0" />
              {!isSidebarCollapsed && (
                <span className="truncate text-left">
                  Sign Out {authUser?.name ? `(${authUser.name})` : ''}
                </span>
              )}
            </button>
          ) : (
            <button
              onClick={() => openAuthModal('account')}
              className={`w-full flex items-center gap-2.5 p-2 rounded-xl text-xs font-semibold text-teal-700 hover:text-teal-800 hover:bg-teal-50 transition-all border border-teal-200/80 ${
                isSidebarCollapsed ? 'justify-center' : ''
              }`}
              title="Sign In or Register Patient Account"
            >
              <LogIn className="w-4 h-4 text-teal-600" />
              {!isSidebarCollapsed && <span>Sign In / Register</span>}
            </button>
          )}
        </div>
      </aside>
    </>
  );
};
