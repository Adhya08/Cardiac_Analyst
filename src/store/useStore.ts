import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { UserProfile, VitalsResponse, HistoryRecord, ShapFactor } from '../lib/api';

// Re-export for convenience
export type { UserProfile, ShapFactor };

export type NavigationMode = 'overview' | 'routine' | 'ecg' | 'history' | 'emergency';

export interface BackendHealthInfo {
  isHealthy: boolean;
  modelLoaded: boolean;
  modelAccuracy?: string;
  version?: string;
}

export interface AppState {
  // ── User
  user: UserProfile | null;
  isProfileComplete: boolean;

  // ── Current mode / screen
  currentMode: NavigationMode;

  // ── Navigation shell state
  isSidebarCollapsed: boolean;

  // ── Backend & Model Service Status
  backendHealth: BackendHealthInfo;

  // ── Active study inspection
  activeECGStudyId: string | null;

  // ── Language
  language: 'en' | 'hi';

  // ── Latest risk result from backend
  latestRisk: VitalsResponse | null;

  // ── Vitals history (cached from backend)
  vitalsHistory: HistoryRecord[];

  // ── Actions
  setUser: (user: UserProfile) => void;
  setMode: (mode: NavigationMode) => void;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setBackendHealth: (health: BackendHealthInfo) => void;
  setActiveECGStudyId: (id: string | null) => void;
  setLanguage: (lang: 'en' | 'hi') => void;
  setLatestRisk: (risk: VitalsResponse) => void;
  setVitalsHistory: (history: HistoryRecord[]) => void;
  clearProfile: () => void;
}

export const useStore = create<AppState>()(
  persist(
    (set) => ({
      user: null,
      isProfileComplete: false,
      currentMode: 'overview',
      isSidebarCollapsed: false,
      backendHealth: {
        isHealthy: true,
        modelLoaded: true,
        modelAccuracy: '92.65% AUROC',
        version: 'ptbxl-resnet1d-v1.0',
      },
      activeECGStudyId: null,
      language: 'en',
      latestRisk: null,
      vitalsHistory: [],

      setUser: (user) =>
        set({
          user,
          isProfileComplete: !!(user.age && user.sex),
        }),

      setMode: (mode) => set({ currentMode: mode }),

      toggleSidebar: () =>
        set((state) => ({ isSidebarCollapsed: !state.isSidebarCollapsed })),

      setSidebarCollapsed: (collapsed) =>
        set({ isSidebarCollapsed: collapsed }),

      setBackendHealth: (health) => set({ backendHealth: health }),

      setActiveECGStudyId: (id) => set({ activeECGStudyId: id }),

      setLanguage: (lang) => set({ language: lang }),

      setLatestRisk: (risk) => set({ latestRisk: risk }),

      setVitalsHistory: (history) => set({ vitalsHistory: history }),

      clearProfile: () =>
        set({
          user: null,
          isProfileComplete: false,
          latestRisk: null,
          vitalsHistory: [],
          activeECGStudyId: null,
        }),
    }),
    {
      name: 'cardiac-clinical-v2',
      partialize: (s) => ({
        user: s.user,
        isProfileComplete: s.isProfileComplete,
        language: s.language,
        currentMode: s.currentMode,
        isSidebarCollapsed: s.isSidebarCollapsed,
        latestRisk: s.latestRisk,
        vitalsHistory: s.vitalsHistory,
      }),
    }
  )
);
