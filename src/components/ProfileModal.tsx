import React, { useState, useEffect } from 'react';
import { User, X, CheckCircle2, Loader2, KeyRound, LogOut, ShieldCheck, Mail } from 'lucide-react';
import { useStore } from '../store/useStore';
import { api, getStoredUser, type UserProfile } from '../lib/api';

interface ProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ProfileModal: React.FC<ProfileModalProps> = ({ isOpen, onClose }) => {
  const { user, setUser } = useStore();
  const [activeTab, setActiveTab] = useState<'demographics' | 'account'>('account');

  // Account state
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [currentUser, setCurrentUser] = useState<any>(getStoredUser());
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [authError, setAuthError] = useState<string | null>(null);
  const [authLoading, setAuthLoading] = useState(false);

  // Demographics form
  const [form, setForm] = useState<Partial<UserProfile>>({
    name: 'Patient Record #001',
    age: 50,
    sex: 'Male',
    is_smoker: false,
    is_diabetic: false,
    has_family_history: false,
    height_cm: 172,
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const stored = getStoredUser();
    setCurrentUser(stored);
    if (stored) {
      setActiveTab('demographics');
    }
  }, [isOpen]);

  useEffect(() => {
    if (user) {
      setForm({
        name: user.name || 'Patient Record #001',
        age: user.age || 50,
        sex: user.sex || 'Male',
        is_smoker: !!user.is_smoker,
        is_diabetic: !!user.is_diabetic,
        has_family_history: !!user.has_family_history,
        height_cm: user.height_cm || 172,
      });
    }
  }, [user]);

  if (!isOpen) return null;

  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    setAuthError(null);
    try {
      if (authMode === 'register') {
        const res = await api.register({
          email,
          password,
          name: form.name || 'Clinician',
          age: Number(form.age) || 45,
          sex: form.sex || 'Male',
        });
        setCurrentUser(res.user);
        setUser(res.user);
        setActiveTab('demographics');
      } else {
        const res = await api.login({ email, password });
        setCurrentUser(res.user);
        setUser(res.user);
        setActiveTab('demographics');
      }
    } catch (err: any) {
      setAuthError(err.message || 'Authentication failed. Please check credentials.');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    api.logout();
    setCurrentUser(null);
    setAuthMode('login');
  };

  const handleSaveDemographics = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    const updated: UserProfile = {
      name: form.name || 'Patient Record',
      age: Number(form.age) || 50,
      sex: (form.sex as 'Male' | 'Female' | 'Other') || 'Male',
      is_smoker: !!form.is_smoker,
      is_diabetic: !!form.is_diabetic,
      has_family_history: !!form.has_family_history,
      height_cm: form.height_cm ? Number(form.height_cm) : undefined,
    };

    try {
      if (currentUser) {
        await api.updateMe(updated);
      } else {
        await api.updateProfile(updated);
      }
      setUser(updated);
      onClose();
    } catch {
      setUser(updated);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-navy-950/40 backdrop-blur-sm">
      <div className="clinical-card w-full max-w-md bg-white border border-border shadow-modal overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="px-5 py-4 border-b border-border flex items-center justify-between bg-surface-secondary">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-teal-50 border border-teal-200 flex items-center justify-center text-teal-700">
              <User className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-navy-850">
                User Account & Demographics
              </h3>
              <p className="text-[11px] text-slate-500 font-medium">Authentication & ASCVD risk profile</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-navy-850 hover:bg-slate-100 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-border bg-slate-50/50">
          <button
            onClick={() => setActiveTab('account')}
            className={`flex-1 py-2.5 text-xs font-bold tracking-wider uppercase border-b-2 transition-colors ${
              activeTab === 'account'
                ? 'border-teal-600 text-teal-700 bg-white'
                : 'border-transparent text-slate-500 hover:text-navy-850'
            }`}
          >
            Account Access
          </button>
          <button
            onClick={() => setActiveTab('demographics')}
            className={`flex-1 py-2.5 text-xs font-bold tracking-wider uppercase border-b-2 transition-colors ${
              activeTab === 'demographics'
                ? 'border-teal-600 text-teal-700 bg-white'
                : 'border-transparent text-slate-500 hover:text-navy-850'
            }`}
          >
            Demographics
          </button>
        </div>

        {activeTab === 'account' ? (
          <div className="p-6 space-y-4">
            {currentUser ? (
              <div className="space-y-4">
                <div className="p-4 rounded-xl bg-teal-50/60 border border-teal-200 flex items-center gap-3">
                  <ShieldCheck className="w-6 h-6 text-teal-600 shrink-0" />
                  <div>
                    <div className="text-xs font-bold text-navy-850">Authenticated Clinician</div>
                    <div className="text-xs text-slate-600 font-mono mt-0.5">{currentUser.email || 'Active Account'}</div>
                    <div className="text-[11px] text-teal-700 font-semibold uppercase tracking-wider mt-1">Role: {currentUser.role || 'Clinician'}</div>
                  </div>
                </div>
                <div className="text-xs text-slate-500">
                  Your diagnostic sessions, vitals history, and local records are cryptographically isolated under your account ID.
                </div>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="btn-clinical-secondary w-full text-xs text-red-600 hover:bg-red-50 hover:border-red-200"
                >
                  <LogOut className="w-3.5 h-3.5 mr-1" />
                  <span>Sign Out</span>
                </button>
              </div>
            ) : (
              <form onSubmit={handleAuthSubmit} className="space-y-4">
                <div className="flex gap-2 p-1 bg-slate-100 rounded-lg">
                  <button
                    type="button"
                    onClick={() => { setAuthMode('login'); setAuthError(null); }}
                    className={`flex-1 py-1.5 text-xs font-semibold rounded-md transition-all ${authMode === 'login' ? 'bg-white shadow-sm text-navy-850 font-bold' : 'text-slate-500'}`}
                  >
                    Sign In
                  </button>
                  <button
                    type="button"
                    onClick={() => { setAuthMode('register'); setAuthError(null); }}
                    className={`flex-1 py-1.5 text-xs font-semibold rounded-md transition-all ${authMode === 'register' ? 'bg-white shadow-sm text-navy-850 font-bold' : 'text-slate-500'}`}
                  >
                    Register
                  </button>
                </div>

                {authError && (
                  <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg">
                    {authError}
                  </div>
                )}

                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-slate-600 uppercase tracking-wider">Email Address</label>
                  <div className="relative">
                    <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                    <input
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="clinician@hospital.org"
                      className="clinical-input pl-9"
                    />
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-slate-600 uppercase tracking-wider">Password</label>
                  <div className="relative">
                    <KeyRound className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                    <input
                      type="password"
                      required
                      minLength={8}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Minimum 8 characters"
                      className="clinical-input pl-9"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={authLoading}
                  className="btn-clinical-primary w-full text-xs"
                >
                  {authLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                  <span>{authMode === 'login' ? 'Sign In to Account' : 'Create Clinician Account'}</span>
                </button>
              </form>
            )}
          </div>
        ) : (
          <form onSubmit={handleSaveDemographics} className="p-6 space-y-4">
            <div className="space-y-1">
              <label className="text-[11px] font-bold text-slate-600 uppercase tracking-wider">Patient Name / Identifier</label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm(f => ({ ...f, name: e.target.value }))}
                placeholder="e.g. Patient Record #5527"
                className="clinical-input"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-[11px] font-bold text-slate-600 uppercase tracking-wider">Age (Years)</label>
                <input
                  type="number"
                  min={18}
                  max={110}
                  value={form.age || ''}
                  onChange={(e) => setForm(f => ({ ...f, age: parseInt(e.target.value) || 0 }))}
                  className="clinical-input"
                />
              </div>
              <div className="space-y-1">
                <label className="text-[11px] font-bold text-slate-600 uppercase tracking-wider">Biological Sex</label>
                <select
                  value={form.sex}
                  onChange={(e) => setForm(f => ({ ...f, sex: e.target.value as any }))}
                  className="clinical-input"
                >
                  <option value="Male">Male</option>
                  <option value="Female">Female</option>
                  <option value="Other">Other</option>
                </select>
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-[11px] font-bold text-slate-600 uppercase tracking-wider">Height (cm)</label>
              <input
                type="number"
                min={100}
                max={250}
                value={form.height_cm || ''}
                onChange={(e) => setForm(f => ({ ...f, height_cm: parseInt(e.target.value) || 0 }))}
                className="clinical-input"
                placeholder="170"
              />
            </div>

            <div className="space-y-2 pt-2 border-t border-border">
              <label className="text-[11px] font-bold text-slate-600 uppercase tracking-wider">Clinical Risk Factors</label>
              <div className="space-y-2">
                <label className="flex items-center gap-2.5 text-xs text-navy-850 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.is_smoker}
                    onChange={(e) => setForm(f => ({ ...f, is_smoker: e.target.checked }))}
                    className="rounded border-slate-300 text-teal-600 focus:ring-teal-500 w-4 h-4"
                  />
                  <span>Active Smoker / Tobacco User</span>
                </label>
                <label className="flex items-center gap-2.5 text-xs text-navy-850 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.is_diabetic}
                    onChange={(e) => setForm(f => ({ ...f, is_diabetic: e.target.checked }))}
                    className="rounded border-slate-300 text-teal-600 focus:ring-teal-500 w-4 h-4"
                  />
                  <span>Diagnosed Diabetes Mellitus</span>
                </label>
                <label className="flex items-center gap-2.5 text-xs text-navy-850 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.has_family_history}
                    onChange={(e) => setForm(f => ({ ...f, has_family_history: e.target.checked }))}
                    className="rounded border-slate-300 text-teal-600 focus:ring-teal-500 w-4 h-4"
                  />
                  <span>Family History of Premature CAD</span>
                </label>
              </div>
            </div>

            <div className="pt-3 flex items-center justify-end gap-2.5 border-t border-border">
              <button
                type="button"
                onClick={onClose}
                className="btn-clinical-secondary text-xs"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="btn-clinical-primary text-xs"
              >
                {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                <span>Save Demographics</span>
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
