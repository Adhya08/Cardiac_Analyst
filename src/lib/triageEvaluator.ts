/**
 * Clinical Emergency Triage Evaluator
 * -------------------------------------
 * Loads the single shared rule definition from `shared/triage_rules.json`.
 * Both online and offline evaluation execute this exact deterministic logic.
 */
import rawRules from '../../shared/triage_rules.json';

export interface QuestionDef {
  id: string;
  text: string;
  text_hi: string;
  category: 'red_flag' | 'associated_symptom' | 'risk_factor';
  is_red_flag: boolean;
  clinical_focus: string;
}

export interface TriageRulesData {
  _comment: string;
  clinical_disclaimer: string;
  version: string;
  tiers: {
    emergency: { id: string; label: string; action_code: string; display_urgency: string; color: string };
    see_doctor_today: { id: string; label: string; action_code: string; display_urgency: string; color: string };
    no_emergency_warning_signs: { id: string; label: string; action_code: string; display_urgency: string; color: string };
  };
  instructions: {
    emergency: string[];
    see_doctor_today: string[];
    no_emergency_warning_signs: string[];
  };
  lowest_tier_statement: string;
  questions: QuestionDef[];
  rules: {
    red_flag_keys: string[];
    emergency_syncope_key: string;
    emergency_sweats_combo: string[];
    emergency_min_red_flags: number;
    emergency_shock_combo: string[];
    emergency_persistent_cad_combo: {
      requires_red_flag: boolean;
      requires_history: string;
      requires_duration: string;
    };
    vital_signs_thresholds: {
      bp_sys_shock_below: number;
      bp_sys_crisis_above: number;
      hr_critical_below: number;
      hr_critical_above: number;
    };
    see_doctor_today_rules: {
      min_red_flags: number;
      associated_symptoms: string[];
      risk_factors_to_escalate_associated: string[];
      min_risk_factors_for_associated: number;
    };
  };
}

export const triageRules = rawRules as TriageRulesData;

export const TRIAGE_QUESTIONS = triageRules.questions.map((q) => q.text);
export const TRIAGE_QUESTION_DEFS = triageRules.questions;

export type TriageSeverity = 'emergency' | 'see_doctor_today' | 'no_emergency_warning_signs';

export interface TriageEvaluationResult {
  severity: TriageSeverity;
  confidence: number;
  risk_score: number;
  yes_count: number;
  stemi_suspicious: boolean;
  combo_triggered: boolean;
  vitals_red_flag: boolean;
  instructions: string[];
  urgency_tier: string;
  action_headline: string;
}

/**
 * Deterministically evaluates triage rules against symptom and risk factor answers.
 */
export function evaluateTriage(
  answers: boolean[] | Record<string, boolean> | Record<number, boolean>,
  bp_sys?: number | null,
  hr?: number | null
): TriageEvaluationResult {
  // Normalize answers into dictionary by question id
  const ansMap: Record<string, boolean> = {};

  if (Array.isArray(answers)) {
    triageRules.questions.forEach((q, idx) => {
      ansMap[q.id] = Boolean(answers[idx]);
    });
  } else {
    // Check if keys are numeric indices or string IDs
    const keys = Object.keys(answers);
    const isNumeric = keys.length > 0 && keys.every((k) => !isNaN(Number(k)));
    if (isNumeric) {
      triageRules.questions.forEach((q, idx) => {
        ansMap[q.id] = Boolean((answers as Record<number, boolean>)[idx]);
      });
    } else {
      triageRules.questions.forEach((q) => {
        ansMap[q.id] = Boolean((answers as Record<string, boolean>)[q.id]);
      });
    }
  }

  // 1. Vital signs evaluation
  const thresholds = triageRules.rules.vital_signs_thresholds;
  const bp_shock = bp_sys != null && bp_sys < thresholds.bp_sys_shock_below;
  const bp_crisis = bp_sys != null && bp_sys > thresholds.bp_sys_crisis_above;
  const hr_critical = hr != null && (hr < thresholds.hr_critical_below || hr > thresholds.hr_critical_above);
  const vitals_red_flag = bp_shock || bp_crisis || hr_critical;

  // 2. Red flag symptom calculation
  const redFlagKeys = triageRules.rules.red_flag_keys;
  const presentRedFlags = redFlagKeys.filter((k) => ansMap[k]);
  const redFlagCount = presentRedFlags.length;

  // Total yes count
  const yes_count = Object.values(ansMap).filter(Boolean).length;

  // Cardinal STEMI triad suspicion
  const stemi_suspicious = Boolean(
    ansMap['crushing_chest_pain'] && ansMap['radiating_pain'] && (ansMap['cold_sweats'] || ansMap['dyspnea_at_rest'])
  );

  // 3. Emergency conditions
  const syncope = Boolean(ansMap[triageRules.rules.emergency_syncope_key]);
  const sweatsCombo = triageRules.rules.emergency_sweats_combo.every((k) => ansMap[k]);
  const shockCombo = triageRules.rules.emergency_shock_combo.every((k) => ansMap[k]);
  const persistentCadCombo = Boolean(
    redFlagCount >= 1 &&
      ansMap[triageRules.rules.emergency_persistent_cad_combo.requires_history] &&
      ansMap[triageRules.rules.emergency_persistent_cad_combo.requires_duration]
  );
  const twoOrMoreRedFlags = redFlagCount >= triageRules.rules.emergency_min_red_flags;

  const isEmergency =
    vitals_red_flag ||
    syncope ||
    twoOrMoreRedFlags ||
    sweatsCombo ||
    shockCombo ||
    persistentCadCombo;

  const combo_triggered =
    syncope || twoOrMoreRedFlags || sweatsCombo || shockCombo || persistentCadCombo;

  // 4. "See Doctor Today" conditions (if not already emergency)
  const seeDoctorRules = triageRules.rules.see_doctor_today_rules;
  const singleRedFlag = redFlagCount >= seeDoctorRules.min_red_flags;

  const hasAssociatedSymptom = seeDoctorRules.associated_symptoms.some((k) => ansMap[k]);
  const riskFactorCount = seeDoctorRules.risk_factors_to_escalate_associated.filter((k) => ansMap[k]).length;
  const associatedWithRiskFactors =
    hasAssociatedSymptom &&
    (riskFactorCount >= seeDoctorRules.min_risk_factors_for_associated || ansMap['known_heart_disease']);

  const associatedWithProlongedDuration = hasAssociatedSymptom && Boolean(ansMap['duration_over_1_hour']);

  const isSeeDoctor =
    singleRedFlag ||
    associatedWithRiskFactors ||
    associatedWithProlongedDuration ||
    (hasAssociatedSymptom && ansMap['age_over_40'] && ansMap['diabetes']);

  // 5. Final Severity Determination
  let severity: TriageSeverity;
  let confidence: number;
  let risk_score: number;

  if (isEmergency) {
    severity = 'emergency';
    confidence = Math.min(0.99, 0.85 + redFlagCount * 0.03 + (vitals_red_flag ? 0.05 : 0.0));
    risk_score = Math.min(99.0, 75.0 + redFlagCount * 4.0 + (vitals_red_flag ? 10.0 : 0.0));
  } else if (isSeeDoctor) {
    severity = 'see_doctor_today';
    confidence = Math.min(0.88, 0.72 + redFlagCount * 0.05 + riskFactorCount * 0.02);
    risk_score = Math.min(68.0, 38.0 + redFlagCount * 12.0 + riskFactorCount * 5.0);
  } else {
    severity = 'no_emergency_warning_signs';
    confidence = 0.82;
    risk_score = Math.max(3.0, 5.0 + yes_count * 2.0);
  }

  const instructions = triageRules.instructions[severity];
  const tierInfo = triageRules.tiers[severity];

  return {
    severity,
    confidence: Math.round(confidence * 1000) / 1000,
    risk_score: Math.round(risk_score * 10) / 10,
    yes_count,
    stemi_suspicious,
    combo_triggered,
    vitals_red_flag,
    instructions,
    urgency_tier: tierInfo.id,
    action_headline: tierInfo.label,
  };
}
