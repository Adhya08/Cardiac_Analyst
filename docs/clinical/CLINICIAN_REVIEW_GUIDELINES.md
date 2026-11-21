# Emergency Triage Protocol: Clinical Review Specification

> **Clinical Disclaimer**:  
> *These rules have NOT been clinically validated. Requires review by a qualified clinician before public release.*

---

## 1. Executive Summary for Reviewing Clinicians

This document outlines the deterministic rule-based emergency triage algorithm used in **Cardiac Analyst**. The system evaluates patients presenting with potential acute coronary syndromes (ACS) or acute cardiovascular distress.

### Key Clinical Changes from Previous Version
1. **Elimination of "Normal / Low-Risk" Classification**: Replaced with explicit non-reassurance statement: *"No emergency warning signs were identified from your answers. If symptoms continue, get worse, or you are worried, seek medical care."*
2. **Elimination of Delay Directives**: Removed all recommendations advising patients to "wait a week" or "schedule within the week."
3. **Strict Red-Flag Escalation**: Any single red-flag symptom immediately commands at least **"See a Doctor Today"** (`see_doctor_today`).
4. **Immediate Emergency Escalation**: Any syncope/fainting alone, any $\ge 2$ red-flag symptoms together, or cold sweats accompanied by nausea/lightheadedness immediately escalates to **"Call Emergency Services Now (112)"** (`emergency`).
5. **Cardiovascular Risk Stratification**: Questions regarding age ($\ge 40$), diabetes, known CAD, and symptom duration ($> 1\text{ hour}$) are incorporated to raise urgency, never to lower it.

---

## 2. Urgency Tiers & Action Directives

| Tier ID | Display Label | Action Directive | Color Code |
| :--- | :--- | :--- | :--- |
| **`emergency`** | **Call Emergency Services Now** | Immediately dial **112** (or local EMS). Sit/lie down, do not drive, unlock door, alert family/neighbor. | **Red** |
| **`see_doctor_today`** | **See a Doctor Today** | Urgent same-day clinical evaluation at cardiology clinic, urgent care, or emergency room. Avoid physical exertion; do not drive. | **Amber** |
| **`no_emergency_warning_signs`** | **No Emergency Warning Signs Identified** | *"No emergency warning signs were identified from your answers. If symptoms continue, get worse, or you are worried, seek medical care."* | **Emerald** |

---

## 3. Triage Questionnaire Elements (12 Questions)

| # | Question Identifier | Clinical Question Text | Category | Red Flag? | Review |
| :---: | :--- | :--- | :--- | :---: | :---: |
| **Q1** | `crushing_chest_pain` | Are you experiencing crushing, squeezing, heavy, or pressing chest pain? | Symptom | **YES** | `[ ] Approve`<br>`[ ] Change` |
| **Q2** | `radiating_pain` | Does the pain radiate to your left arm, jaw, neck, back, or shoulder? | Symptom | **YES** | `[ ] Approve`<br>`[ ] Change` |
| **Q3** | `dyspnea_at_rest` | Are you experiencing shortness of breath or breathlessness even while resting? | Symptom | **YES** | `[ ] Approve`<br>`[ ] Change` |
| **Q4** | `cold_sweats` | Are you sweating profusely or having cold sweats (diaphoresis)? | Symptom | **YES** | `[ ] Approve`<br>`[ ] Change` |
| **Q5** | `fainting` | Have you fainted, lost consciousness, or nearly fainted recently? | Symptom | **YES** | `[ ] Approve`<br>`[ ] Change` |
| **Q6** | `palpitations` | Is your heart racing, pounding, fluttering, or beating irregularly? | Symptom | **YES** | `[ ] Approve`<br>`[ ] Change` |
| **Q7** | `nausea_dizziness` | Are you feeling nauseous, lightheaded, or dizzy? | Associated | NO | `[ ] Approve`<br>`[ ] Change` |
| **Q8** | `confusion` | Are you feeling confused, disoriented, or having sudden blurred vision? | Associated | NO | `[ ] Approve`<br>`[ ] Change` |
| **Q9** | `age_over_40` | Are you 40 years of age or older? | Risk Factor | NO | `[ ] Approve`<br>`[ ] Change` |
| **Q10** | `diabetes` | Have you been diagnosed with diabetes? | Risk Factor | NO | `[ ] Approve`<br>`[ ] Change` |
| **Q11** | `known_heart_disease` | Do you have known heart disease (prior heart attack, stent, angina, bypass)? | Risk Factor | NO | `[ ] Approve`<br>`[ ] Change` |
| **Q12** | `duration_over_1_hour` | Have these symptoms lasted for more than 1 hour or persisted continuously? | Risk Factor | NO | `[ ] Approve`<br>`[ ] Change` |

---

## 4. Plain Decision Rules Table

| Rule ID | Trigger Condition | Urgency Tier | Clinical Rationale | Review |
| :--- | :--- | :--- | :--- | :---: |
| **R-01** | Syncope / Fainting alone (`fainting == True`) | **`emergency`** | Syncope in cardiac context indicates malignant ventricular arrhythmia, advanced AV block, severe aortic stenosis, or critical hypoperfusion. | `[ ] Approve`<br>`[ ] Change` |
| **R-02** | Any $\ge 2$ Red Flags (`red_flag_count >= 2`) | **`emergency`** | Multiple cardinal ischemic symptoms (e.g., retrosternal chest pain + radiation, or chest pain + diaphoresis) represent classic acute coronary syndrome / STEMI presentations. | `[ ] Approve`<br>`[ ] Change` |
| **R-03** | Cold Sweats + Nausea / Dizziness (`cold_sweats AND nausea_dizziness`) | **`emergency`** | Profuse diaphoresis accompanied by autonomic symptoms (nausea, lightheadedness) indicates severe sympathetic surge, vagal stimulation, or inferior STEMI. | `[ ] Approve`<br>`[ ] Change` |
| **R-04** | Crushing Chest Pain + Confusion (`crushing_chest_pain AND confusion`) | **`emergency`** | Acute chest pain accompanied by altered mental status or confusion reflects acute cardiogenic shock or profound cerebral hypoperfusion. | `[ ] Approve`<br>`[ ] Change` |
| **R-05** | Any Red Flag + Known CAD + Duration $>1\text{ hr}$ (`red_flag >= 1 AND known_heart_disease AND duration_over_1_hour`) | **`emergency`** | Prolonged ischemic symptom in a patient with documented prior coronary disease represents ongoing unresolving myocardial infarction. | `[ ] Approve`<br>`[ ] Change` |
| **R-06** | Systolic BP $< 90\text{ mmHg}$ | **`emergency`** | Hypotensive shock state requiring immediate resuscitation and inotropic/mechanical support. | `[ ] Approve`<br>`[ ] Change` |
| **R-07** | Systolic BP $> 180\text{ mmHg}$ | **`emergency`** | Hypertensive crisis carrying risk of acute pulmonary edema, aortic dissection, or acute end-organ damage. | `[ ] Approve`<br>`[ ] Change` |
| **R-08** | Heart Rate $< 40\text{ bpm}$ or $> 150\text{ bpm}$ | **`emergency`** | Severe bradyarrhythmia (complete heart block) or unstable tachyarrhythmia (VT/SVT) compromising cardiac output. | `[ ] Approve`<br>`[ ] Change` |
| **R-09** | Any Single Red Flag (`red_flag_count == 1`) | **`see_doctor_today`** | Single potential acute cardiac sign (e.g., isolated resting dyspnea, isolated jaw radiation, or isolated palpitations) requires urgent physician assessment, ECG, and troponin testing. | `[ ] Approve`<br>`[ ] Change` |
| **R-10** | Associated Symptom + Duration $> 1\text{ hr}$ (`(nausea OR confusion) AND duration_over_1_hour`) | **`see_doctor_today`** | Persistent unexplained autonomic or neurological distress requires urgent medical evaluation. | `[ ] Approve`<br>`[ ] Change` |
| **R-11** | Associated Symptom + $\ge 2$ Risk Factors (`(nausea OR confusion) AND >= 2 of (age_over_40, diabetes, known_CAD)`) | **`see_doctor_today`** | Diabetic/elderly patients frequently present with atypical "silent" myocardial ischemia manifest only as nausea, diaphoresis, or dizziness. | `[ ] Approve`<br>`[ ] Change` |
| **R-12** | Associated Symptom + Known CAD (`(nausea OR confusion) AND known_heart_disease`) | **`see_doctor_today`** | Any new unexplained symptoms in established coronary patients warrant same-day clinical review. | `[ ] Approve`<br>`[ ] Change` |
| **R-13** | Zero Red Flags & Zero Associated Symptoms | **`no_emergency_warning_signs`** | No emergent warning signs identified from questionnaire. User is instructed to seek medical care if symptoms persist, worsen, or cause worry. | `[ ] Approve`<br>`[ ] Change` |

---

## 5. Risk Factor Monotonicity Verification

Cardiovascular risk factors (`age_over_40`, `diabetes`, `known_heart_disease`, `duration_over_1_hour`) are constrained by the following mathematical safety theorem:

$$\forall \text{ profiles } A, B : A \subseteq B \implies \text{UrgencyTier}(B) \ge \text{UrgencyTier}(A)$$

Under no circumstances can answering "YES" to a risk factor decrease urgency or downgrade patient triage status.

---

## 6. Lowest Tier Communication Standard

```
"No emergency warning signs were identified from your answers. If symptoms continue, get worse, or you are worried, seek medical care."
```

### Clinician Safety Checklist
- [x] Does NOT use the words "normal", "healthy", or "low-risk".
- [x] Does NOT instruct the patient to wait a week or delay seeking care.
- [x] Advises immediate emergency call (112) if symptoms worsen or new symptoms appear.
- [x] Advises that absence of warning signs on a self-administered questionnaire does not rule out underlying pathology.

---

## 7. Clinician Reviewer Sign-Off

| Field | Clinician Response |
| :--- | :--- |
| **Reviewer Full Name** | _____________________________________________ |
| **Medical License / Reg No.** | _____________________________________________ |
| **Specialty** | Cardiology / Emergency Medicine / Internal Medicine |
| **Hospital / Institution** | _____________________________________________ |
| **Review Date** | _____________________________________________ |
| **Overall Recommendation** | `[ ] Approved for Clinical Beta` &nbsp;&nbsp;&nbsp; `[ ] Revisions Required` |
| **Reviewer Comments** | <br><br>_____________________________________________ |
