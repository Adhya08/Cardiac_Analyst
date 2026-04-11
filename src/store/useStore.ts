import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { UserProfile, VitalsResponse, HistoryRecord, ShapFactor } from '../lib/api';

// Re-export for convenience
export type { UserProfile, ShapFactor };

export interface AppState {
  // ── User
  user: UserProfile | null;
  isProfileComplete: boolean;

  // ── Current mode
  currentMode: 'routine' | 'ecg' | 'emergency';

  // ── Language
  language: 'en' | 'hi';

  // ── Latest risk result from backend
  latestRisk: VitalsResponse | null;

  // ── Vitals history (cached from backend)
  vitalsHistory: HistoryRecord[];

  // ── Actions
  setUser: (user: UserProfile) => void;
  setMode: (mode: 'routine' | 'ecg' | 'emergency') => void;
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
      currentMode: 'routine',
      language: 'en',
      latestRisk: null,
      vitalsHistory: [],

      setUser: (user) =>
        set({
          user,
          isProfileComplete: !!(user.age && user.sex),
        }),

      setMode: (mode) => set({ currentMode: mode }),

      setLanguage: (lang) => set({ language: lang }),

      setLatestRisk: (risk) => set({ latestRisk: risk }),

      setVitalsHistory: (history) => set({ vitalsHistory: history }),

      clearProfile: () =>
        set({
          user: null,
          isProfileComplete: false,
          latestRisk: null,
          vitalsHistory: [],
        }),
    }),
    {
      name: 'cardiac-ai-v2',
      partialize: (s) => ({
        user: s.user,
        isProfileComplete: s.isProfileComplete,
        language: s.language,
        currentMode: s.currentMode,
        latestRisk: s.latestRisk,
        vitalsHistory: s.vitalsHistory,
      }),
    }
  )
);
