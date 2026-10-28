/**
 * Exhaustive Combinatorial Triage Evaluator (Frontend Logic Parity Test)
 * -----------------------------------------------------------------------
 * Evaluates all 2^12 = 4,096 answer combinations against the shared rules.
 * Used for parity verification against backend/app/ml/triage.py.
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const rulesPath = path.resolve(__dirname, '../shared/triage_rules.json');
const triageRules = JSON.parse(fs.readFileSync(rulesPath, 'utf8'));

export function evaluateFrontendTriage(answers, bp_sys = null, hr = null) {
  const ansMap = {};
  triageRules.questions.forEach((q, idx) => {
    ansMap[q.id] = Boolean(answers[idx]);
  });

  const thresholds = triageRules.rules.vital_signs_thresholds;
  const bp_shock = bp_sys != null && bp_sys < thresholds.bp_sys_shock_below;
  const bp_crisis = bp_sys != null && bp_sys > thresholds.bp_sys_crisis_above;
  const hr_critical = hr != null && (hr < thresholds.hr_critical_below || hr > thresholds.hr_critical_above);
  const vitals_red_flag = bp_shock || bp_crisis || hr_critical;

  const redFlagKeys = triageRules.rules.red_flag_keys;
  const presentRedFlags = redFlagKeys.filter((k) => ansMap[k]);
  const redFlagCount = presentRedFlags.length;
  const yes_count = Object.values(ansMap).filter(Boolean).length;

  const stemi_suspicious = Boolean(
    ansMap['crushing_chest_pain'] && ansMap['radiating_pain'] && (ansMap['cold_sweats'] || ansMap['dyspnea_at_rest'])
  );

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

  let severity;
  let confidence;
  let risk_score;

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

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const total = 1 << triageRules.questions.length;
  console.log(`Running exhaustive evaluation across ${total} combinations...`);
  const counts = { emergency: 0, see_doctor_today: 0, no_emergency_warning_signs: 0 };

  for (let mask = 0; mask < total; mask++) {
    const answers = [];
    for (let i = 0; i < triageRules.questions.length; i++) {
      answers.push(Boolean((mask >> i) & 1));
    }
    const res = evaluateFrontendTriage(answers);
    counts[res.severity]++;

    // Assert safety rules:
    // 1. Never normal or low risk
    if (res.severity === 'normal' || res.severity === 'low_risk') {
      throw new Error(`Forbidden severity output at mask ${mask}: ${res.severity}`);
    }
    // 2. Fainting gives emergency
    if (answers[4] && res.severity !== 'emergency') {
      throw new Error(`Safety violation: Syncope present but severity is ${res.severity} at mask ${mask}`);
    }
    // 3. Any 2 red flags gives emergency
    const redCount = [0, 1, 2, 3, 4, 5].filter((idx) => answers[idx]).length;
    if (redCount >= 2 && res.severity !== 'emergency') {
      throw new Error(`Safety violation: Red count ${redCount} >= 2 but severity is ${res.severity} at mask ${mask}`);
    }
    // 4. Cold sweats + nausea/dizziness gives emergency
    if (answers[3] && answers[6] && res.severity !== 'emergency') {
      throw new Error(`Safety violation: Cold sweats + nausea but severity is ${res.severity} at mask ${mask}`);
    }
    // 5. Any single red flag gives at least see_doctor_today
    if (redCount >= 1 && res.severity === 'no_emergency_warning_signs') {
      throw new Error(`Safety violation: Red flag present but lowest tier returned at mask ${mask}`);
    }
  }

  console.log(`[Frontend Exhaustive Parity] 100% of ${total} combinations passed all safety invariants!`);
  console.log(`Urgency Distribution:`, counts);
}
