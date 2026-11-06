# Privacy Policy

**Effective Date:** October 26, 2026  
**Project:** Cardiac Analyst Research Prototype ([Cardiac Analyst](https://github.com/Adhya08/Cardiac_Analyst))

Cardiac Analyst is an academic and clinical research engineering prototype designed for automated 12-lead ECG rhythm classification and deterministic cardiovascular risk evaluation. This Privacy Policy details how data is handled, processed, and stored across the platform.

---

## 1. Core Principles

- **Local-First & Client-Side Control:** Cardiac Analyst is architected to operate locally. All signal processing and neural inference can run entirely within on-premise infrastructure or local development environments.
- **No Third-Party Advertising or Commercial Brokers:** We do not sell, rent, monetize, or trade patient health records, biometric signals, or telemetry data to data brokers or advertising networks.
- **Zero Generative AI Diagnostic Transmission:** No raw patient ECG signals, continuous telemetry waveforms, or patient medical records are ever sent to third-party generative large language model APIs (e.g., OpenAI, Anthropic, Google Gemini) for diagnosis. Neural classification is performed using a local 1D deep convolutional neural network (`resnet1d_ptbxl_5class.onnx`).

---

## 2. Information We Process

### 2.1 Biometric & Diagnostic Data
When utilizing ECG Analysis or Vital Signs logging, the application processes:
- **12-Lead Electrocardiogram Waveforms:** Voltage timeseries sampled at 100 Hz across 12 standard leads (I, II, III, aVR, aVL, aVF, V1–V6) representing a 10-second capture (1,000 samples $\times$ 12 leads).
- **Physiological Vitals:** Heart rate (bpm), non-invasive blood pressure (systolic and diastolic mmHg), and blood oxygen saturation ($\text{SpO}_2$ percentage).
- **Symptom & Triage Metrics:** Acute coronary symptom flags (chest pain severity, dyspnea, radiation, diaphoresis) collected strictly for deterministic NICE CG95 guideline emergency decision support.

### 2.2 Account Credentials & Profile Demographics
If an account is created:
- **Authentication Credentials:** Email address and a cryptographically salted password hash generated via `bcrypt`. Plaintext passwords are never stored or logged.
- **Clinical Demographics (Optional):** Age, biological sex, smoking status, and clinician notes.

---

## 3. Data Storage & Isolation

- **Default Storage Backend:** Data is persisted in a local SQLite database file (`cardiac_data.db`).
- **User Isolation:** Each ECG capture, triage event, and vitals log is associated with the authenticated user ID (`user_id`). Users can only query and retrieve their own records.
- **Exclusion from Source Control:** All SQLite database files, transient log files, and upload directories are explicitly excluded from public version control via `.gitignore`.

---

## 4. Third-Party Data Flow & External Service Integrations

Cardiac Analyst limits external cloud service interactions to non-diagnostic utilities. All core diagnostic machine learning (PTB-XL 1D ResNet, LightGBM Routine Risk Model, and NICE CG95 Triage Rules) executes **100% locally on-premise** with zero data leaving the host machine.

The platform interacts with two external services strictly under the following privacy constraints:

### 4.1 Google Places / Maps API (Emergency Facility Locator)
- **Purpose**: Geolocation lookup for emergency cardiac hospitals and trauma centers within a 15 km radius.
- **Endpoint**: `https://maps.googleapis.com/maps/api/place/nearbysearch/json`
- **Data Transmitted**:
  - Geographic latitude and longitude coordinates (`lat`, `lon`).
  - Search query filters (`keyword="cardiac heart cardiology emergency"`, `type="hospital"`).
- **Data NOT Transmitted**:
  - Zero patient identifiers (no names, emails, user IDs, or IP addresses).
  - Zero medical records (no symptoms, vitals, triage scores, or ECG waveforms).
- **Fallback Guarantee**: If `GOOGLE_MAPS_API_KEY` is absent or the service is unreachable, a static verified directory of regional cardiac facilities is used locally, generating zero external network calls.

### 4.2 Sarvam AI Cloud Assistant (Multilingual Reports & Q&A)
- **Purpose**: Optional, plain-language patient education and Hindi/English bilingual report summaries. **Sarvam AI is strictly secondary and never used for clinical diagnosis or triage decisions.**
- **Endpoint**: `https://api.sarvam.ai/v1/chat/completions` (model: `sarvam-m`)
- **Explicit Opt-In Consent**:
  - The chat, summary, and lifestyle advice endpoints (`/api/v1/chat/message`, `/api/v1/chat/summarize`, `/api/v1/chat/advice`) are **disabled by default**.
  - Any request must include an explicit user opt-in flag: `consent_third_party_ai=True`. Requests without explicit consent are immediately rejected with `HTTP 403 Forbidden`.
- **Data Transmitted (De-Identified Only)**:
  - User's conversational query string.
  - Anonymized clinical metrics (super-class diagnostic probabilities e.g., `NORM: 0.92`, heart rate bpm, numerical BP/SpO2/glucose levels).
- **Data NOT Transmitted**:
  - Zero Direct Identifiers: Patient name, email address, database user ID, client IP address, and date of birth are strictly stripped.
  - Zero Raw Waveforms: Raw continuous 1,000-sample voltage arrays are never transmitted to external APIs.
- **Access Control**: Users can only request summaries for ECG records they own or have explicit clinician delegation access to.

---

## 5. Security Safeguards

- Passwords hashed using standard `bcrypt` with automatic salt generation.
- Stateless session authentication enforced via signed JSON Web Tokens (`HS256`).
- Defensive input sanitization and boundary checking on all numerical vitals and ECG timeseries arrays.

---

## 6. User Rights & Data Deletion

Users have full authority over their data:
- **Right to Export:** Users can query and export their historical analyses directly via the REST API.
- **Right to Erasure:** Deleting a user account or deleting local database records permanently removes associated vitals logs, triage events, and ECG waveform files from disk.

---

## 7. Contact & Open Source Inquiries

For questions or security vulnerability notifications regarding this privacy policy, open an issue in the project repository:  
[GitHub Repository Issues](https://github.com/Adhya08/Cardiac_Analyst/issues)
