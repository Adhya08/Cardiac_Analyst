import React, { useState, useEffect } from 'react';
import { User, X, CheckCircle2, Loader2 } from 'lucide-react';
import { useStore } from '../store/useStore';
import { api, type UserProfile } from '../lib/api';

interface ProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ProfileModal: React.FC<ProfileModalProps> = ({ isOpen, onClose }) => {
  const { user, setUser } = useStore();

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

  const handleSave = async (e: React.FormEvent) => {
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
      await api.updateProfile(updated);
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
                Patient Demographics & Clinical Profile
              </h3>
              <p className="text-[11px] text-slate-500 font-medium">Used for personalized ECG & ASCVD calculations</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-navy-850 hover:bg-slate-100 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSave} className="p-6 space-y-4">
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
      </div>
    </div>
  );
};
