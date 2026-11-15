import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { api, getStoredUser, type UserProfile, type VitalsResponse, type HistoryRecord, type ShapFactor } from '../lib/api';

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
  // ── User & Auth
  user: UserProfile | null;
  authUser: any | null;
  isProfileComplete: boolean;
  isAuthModalOpen: boolean;
  authModalTab: 'demographics' | 'account';

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
  setUser: (user: UserProfile | null) => void;
  setAuthUser: (authUser: any | null) => void;
  openAuthModal: (tab?: 'demographics' | 'account') => void;
  closeAuthModal: () => void;
  logout: () => void;
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
      authUser: typeof window !== 'undefined' ? getStoredUser() : null,
      isProfileComplete: false,
      isAuthModalOpen: false,
      authModalTab: 'account',
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
          isProfileComplete: !!(user && user.age && user.sex),
        }),

      setAuthUser: (authUser) => set({ authUser }),

      openAuthModal: (tab = 'account') =>
        set({ isAuthModalOpen: true, authModalTab: tab }),

      closeAuthModal: () =>
        set({ isAuthModalOpen: false }),

      logout: () => {
        api.logout();
        set({
          user: null,
          authUser: null,
          isProfileComplete: false,
          latestRisk: null,
          vitalsHistory: [],
          activeECGStudyId: null,
          isAuthModalOpen: false,
        });
      },

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

      clearProfile: () => {
        api.logout();
        set({
          user: null,
          authUser: null,
          isProfileComplete: false,
          latestRisk: null,
          vitalsHistory: [],
          activeECGStudyId: null,
        });
      },
    }),
    {
      name: 'cardiac-clinical-v2',
      partialize: (s) => ({
        user: s.user,
        authUser: s.authUser,
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

