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

## 4. Third-Party Service Interactions

- **Geocoding & Emergency Routing (Optional):** When using the Emergency Mode hospital finder, browser geolocation coordinates are used to query OpenStreetMap Nominatim and Overpass APIs for nearby emergency care centers. No patient identifiers, medical histories, or ECG findings are transmitted in these geographic lookups.

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
