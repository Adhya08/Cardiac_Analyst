/**
 * Typed API client — all calls proxy to FastAPI backend at localhost:8000
 * The Vite dev server proxies /api → http://localhost:8000
 */

const BASE = '/api/v1';

// ─────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────

export interface UserProfile {
  id?: string;
  name?: string;
  age: number;
  sex: 'Male' | 'Female' | 'Other';
  is_smoker: boolean;
  is_diabetic: boolean;
  has_family_history: boolean;
  height_cm?: number;
}

export interface VitalsPayload {
  bp_sys: number;
  bp_dia: number;
  hr: number;
  weight: number;
  spo2: number;
  glucose?: number;
  cholesterol?: number;
}

export interface ShapFactor {
  feature: string;
  value: number;
  impact: number;
  percent: number;
  direction: 'positive' | 'negative';
}

export interface VitalsResponse {
  id: string;
  risk_score: number;
  risk_tier: 'Low' | 'Borderline' | 'Elevated';
  lgbm_probability: number;
  framingham_risk: number;
  confidence_interval: { lower: number; upper: number };
  shap_top5: ShapFactor[];
  ecg_prompt: boolean;
  trend_delta: number;
  vitals: VitalsPayload;
  timestamp: string;
}

export interface HistoryRecord {
  id: string;
  timestamp: string;
  bp_sys: number;
  bp_dia: number;
  hr: number;
  weight: number;
  spo2: number;
  glucose?: number;
  cholesterol?: number;
  risk_score: number;
  risk_tier: string;
}

export interface VitalsHistory {
  records: HistoryRecord[];
  count: number;
  trend: { bp_sys_trend: number };
  risk_history: { timestamp: string; risk_score: number; risk_tier: string }[];
}

export interface ECGCondition {
  code: string;
  name: string;
  model_score: number;
  threshold: number;
  detected: boolean;
  severity: 'normal' | 'possible' | 'detected' | 'unavailable';
  leads_affected?: string[];
  key_finding?: string;
  explanation_en: string;
  explanation_hi?: string;
  // Legacy alias for older history records
  probability?: number;
}

export interface ECGGradCAMHighlight {
  lead: string;
  finding: string;
  severity: 'normal' | 'abnormal' | 'critical';
}

export interface ECGResponse {
  status: 'ok' | 'uncertain' | 'analysis_unavailable';
  model_version: string;
  supported_labels: string[];
  model_scores: Record<string, number>;
  quality_status: 'good' | 'poor_quality' | 'unusable';
  uncertainty_flag: boolean;
  abstain_reason?: string;

  ecg_id: string;
  heart_rate_bpm?: number;
  rhythm?: string;
  pr_interval_ms?: number;
  qrs_duration_ms?: number;
  qtc_ms?: number;
  axis_degrees?: number;
  st_elevation_leads: string[];
  st_depression_leads: string[];
  conditions: ECGCondition[];
  gradcam_highlights: ECGGradCAMHighlight[];
  overall_assessment: string;
  urgency: 'routine' | 'see_doctor_today' | 'emergency' | 'unavailable';
  recommendations: string[];
  image_quality?: 'good' | 'fair' | 'poor' | string;
  image_quality_note?: string;
  disclaimer: string;
  file_url?: string;
}

export interface Hospital {
  name: string;
  address?: string;
  lat: number;
  lon: number;
  distance_km: number;
  rating?: number;
  total_ratings?: number;
  maps_url: string;
  open_now?: boolean;
  contact?: string;
  place_id?: string;
}

export interface AmbulanceService {
  service: string;
  contact: string;
  type: 'government' | 'private';
  eta_info?: string;
  maps_url?: string;
  notes?: string;
}

export interface TriagePayload {
  symptoms: boolean[];
  bp_sys?: number;
  hr?: number;
  lat?: number;
  lon?: number;
  user_id?: string;
}

export interface TriageResponse {
  severity: 'normal' | 'see_doctor' | 'emergency';
  confidence: number;
  risk_score: number;
  yes_count: number;
  stemi_suspicious: boolean;
  combo_triggered: boolean;
  vitals_red_flag: boolean;
  instructions: string[];
  hospitals: Hospital[];
  ambulances: AmbulanceService[];
  triage_id: string;
}

export interface ECGContext {
  age?: number;
  sex?: string;
  conditions?: string;
  bp_sys?: number;
  hr?: number;
}

// ─────────────────────────────────────────────────────────
// Auth Helper & Storage
// ─────────────────────────────────────────────────────────
const AUTH_TOKEN_KEY = 'cardiac_auth_token';
const AUTH_USER_KEY = 'cardiac_auth_user';

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: UserProfile & { email?: string; role?: string; is_active?: boolean };
}

export function getStoredToken(): string | null {
  try {
    return localStorage.getItem(AUTH_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setStoredAuth(token: string, user: any): void {
  try {
    localStorage.setItem(AUTH_TOKEN_KEY, token);
    localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
  } catch {}
}

export function clearStoredAuth(): void {
  try {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_USER_KEY);
  } catch {}
}

export function getStoredUser(): any | null {
  try {
    const raw = localStorage.getItem(AUTH_USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

// ─────────────────────────────────────────────────────────
// Helper
// ─────────────────────────────────────────────────────────
async function request<T>(url: string, opts?: RequestInit): Promise<T> {
  const token = getStoredToken();
  const headers = new Headers(opts?.headers || {});
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const res = await fetch(url, { ...opts, headers });
  if (!res.ok) {
    if (res.status === 401 && !url.includes('/auth/login')) {
      clearStoredAuth();
    }
    const errText = await res.text().catch(() => res.statusText);
    throw new Error(`API Error ${res.status}: ${errText}`);
  }
  return res.json() as Promise<T>;
}

// ─────────────────────────────────────────────────────────
// API client
// ─────────────────────────────────────────────────────────
export const api = {
  // ── Authentication & Account System
  async register(data: { email: string; password: string; name?: string; role?: string; age?: number; sex?: string }): Promise<AuthResponse> {
    const res = await request<AuthResponse>(`${BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    setStoredAuth(res.access_token, res.user);
    return res;
  },

  async login(credentials: { email: string; password: string }): Promise<AuthResponse> {
    const res = await request<AuthResponse>(`${BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(credentials),
    });
    setStoredAuth(res.access_token, res.user);
    return res;
  },

  async getMe(): Promise<UserProfile | null> {
    try {
      return await request<UserProfile>(`${BASE}/auth/me`);
    } catch {
      return null;
    }
  },

  async updateMe(profile: Partial<UserProfile>): Promise<UserProfile> {
    return request<UserProfile>(`${BASE}/auth/me`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(profile),
    });
  },

  logout(): void {
    clearStoredAuth();
  },

  // ── User Profile (Legacy / Guest)
  async getProfile(userId = 'default_user'): Promise<UserProfile | null> {
    try {
      const token = getStoredToken();
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const r = await fetch(`${BASE}/user/profile?user_id=${userId}`, { headers });
      if (!r.ok) return null;
      return r.json();
    } catch {
      return null;
    }
  },

  async updateProfile(profile: Partial<UserProfile>, userId = 'default_user'): Promise<void> {
    await request(`${BASE}/user/profile?user_id=${userId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(profile),
    });
  },

  // ── Vitals
  async logVitals(data: VitalsPayload, userId = 'default_user'): Promise<VitalsResponse> {
    return request(`${BASE}/vitals?user_id=${userId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  },

  async getVitalsHistory(days = 30, userId = 'default_user'): Promise<VitalsHistory> {
    return request(`${BASE}/vitals/history?user_id=${userId}&days=${days}`);
  },

  // ── ECG
  async uploadECG(file: File, ctx: ECGContext, userId = 'default_user'): Promise<ECGResponse> {
    const form = new FormData();
    form.append('file', file);
    form.append('user_id', userId);
    if (ctx.age) form.append('age', String(ctx.age));
    if (ctx.sex) form.append('sex', ctx.sex);
    if (ctx.conditions) form.append('conditions', ctx.conditions);
    if (ctx.bp_sys) form.append('bp_sys', String(ctx.bp_sys));
    if (ctx.hr) form.append('hr', String(ctx.hr));

    return request(`${BASE}/ecg/upload`, { method: 'POST', body: form });
  },

  async getECGHistory(userId = 'default_user') {
    return request<{ ecg_sessions: any[]; total: number }>(
      `${BASE}/ecg/history?user_id=${userId}`
    );
  },

  async getECGAnalysis(ecgId: string): Promise<ECGResponse> {
    return request<ECGResponse>(`${BASE}/ecg/${ecgId}`);
  },

  // ── Emergency / Triage
  async getTriageQuestions(): Promise<{ questions: string[] }> {
    return request(`${BASE}/emergency/questions`);
  },

  async submitTriage(data: TriagePayload): Promise<TriageResponse> {
    return request(`${BASE}/emergency/triage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  },

  async triggerSOS(data?: { lat?: number; lon?: number }): Promise<any> {
    return request(`${BASE}/emergency/sos`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data || {}),
    });
  },

  // ── Hospitals
  async getNearbyHospitals(lat: number, lon: number, radius = 10): Promise<{ hospitals: Hospital[]; total_found: number }> {
    return request(`${BASE}/hospitals/nearby?lat=${lat}&lon=${lon}&radius_km=${radius}`);
  },

  async getNearbyAmbulances(lat: number, lon: number): Promise<{ ambulances: AmbulanceService[] }> {
    return request(`${BASE}/ambulance/nearby?lat=${lat}&lon=${lon}`);
  },

  // ── Health / Model Readiness
  async getHealth(): Promise<{ status: string; model_loaded: boolean; model_accuracy?: string }> {
    try {
      const res = await fetch('/health');
      if (!res.ok) throw new Error('Health check failed');
      return res.json();
    } catch {
      return { status: 'offline', model_loaded: false };
    }
  },
};

export interface ECGHistoryItem {
  ecg_id: string;
  timestamp: string;
  urgency: 'routine' | 'see_doctor_today' | 'emergency';
  heart_rate_bpm: number | null;
  rhythm: string | null;
  qtc_ms: number | null;
  image_quality: string;
  top_condition: string;
  top_condition_prob: number;
  file_name: string;
}

