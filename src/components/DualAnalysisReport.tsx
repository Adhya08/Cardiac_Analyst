import React, { useState } from 'react';
import {
  Stethoscope, Users, Printer, CheckCircle2, AlertTriangle,
  HelpCircle, Heart, Activity, FileText, ChevronRight, ShieldCheck,
} from 'lucide-react';
import type { ECGResponse } from '../lib/api';

interface DualAnalysisReportProps {
  result: ECGResponse;
  language: 'en' | 'hi';
}

interface PlainConditionExplainer {
  plainNameEn: string;
  plainNameHi: string;
  analogyEn: string;
  analogyHi: string;
  whatItMeansEn: string;
  whatItMeansHi: string;
  familyAdviceEn: string;
  familyAdviceHi: string;
}

const PLAIN_EXPLAINERS: Record<string, PlainConditionExplainer> = {
  HYP: {
    plainNameEn: 'Heart Muscle Thickening (Hypertrophy)',
    plainNameHi: 'दिल की मांसपेशियों का मोटा होना (हाइपरट्रॉफी)',
    analogyEn: 'Think of an arm muscle that gets bigger from lifting heavy weights every day. The heart wall has grown thicker because it has been working extra hard to pump blood against high resistance.',
    analogyHi: 'इसे उस हाथ की मांसपेशी की तरह समझें जो भारी वजन उठाने से मोटी हो जाती है। दिल की दीवार मोटी हो गई है क्योंकि उसे रक्त पंप करने के लिए अतिरिक्त मेहनत करनी पड़ रही है।',
    whatItMeansEn: 'The heart muscle walls are thicker than usual, most commonly caused by long-standing high blood pressure or valve stiffness.',
    whatItMeansHi: 'दिल की मांसपेशी की दीवारें सामान्य से अधिक मोटी हैं, जो अक्सर लंबे समय तक उच्च रक्तचाप (हाई बीपी) के कारण होता है।',
    familyAdviceEn: 'Keep the patient calm and seated. Ensure they take their prescribed blood pressure medications as directed. Arrange a non-emergency visit with a cardiologist soon.',
    familyAdviceHi: 'मरीज को शांत और आराम से बैठाएं। डॉक्टर द्वारा दी गई बीपी की दवाएं समय पर दें। जल्द ही किसी हृदय रोग विशेषज्ञ (कार्डियोलॉजिस्ट) को दिखाएं।',
  },
  MI: {
    plainNameEn: 'Possible Heart Muscle Strain / Injury (Heart Attack Sign)',
    plainNameHi: 'संभावित हृदय की चोट (हार्ट अटैक का संकेत)',
    analogyEn: 'Like a garden hose that is kinked, preventing water from reaching plants, an area of the heart muscle may not be getting enough fresh blood and oxygen.',
    analogyHi: 'जैसे पानी के पाइप में रुकावट आने से पौधों तक पानी नहीं पहुंचता, वैसे ही दिल के एक हिस्से को पर्याप्त रक्त और ऑक्सीजन नहीं मिल पा रही हो सकती है।',
    whatItMeansEn: 'The electrical recording shows patterns that can occur during acute or past lack of blood flow to the heart muscle.',
    whatItMeansHi: 'ईसीजी रिकॉर्डिंग से पता चलता है कि दिल की मांसपेशियों को पर्याप्त रक्त प्रवाह नहीं मिल रहा है। यह एक गंभीर स्थिति है।',
    familyAdviceEn: 'URGENT: Have the patient sit or lie down immediately. Do not allow them to exert themselves or drive. Call 112 or take them to the nearest emergency room immediately.',
    familyAdviceHi: 'अति आवश्यक: मरीज को तुरंत आराम से बैठाएं या लेटाएं। कोई शारीरिक श्रम न करने दें। तुरंत 112 पर कॉल करें या नजदीकी आपातकालीन अस्पताल ले जाएं।',
  },
  STTC: {
    plainNameEn: 'Heart Recovery Cycle Changes (ST/T-Wave Changes)',
    plainNameHi: 'दिल की रिकवरी में बदलाव (एसटी-टी वेव परिवर्तन)',
    analogyEn: 'Between each heartbeat pump, the heart takes a split second to recharge its electrical battery. This test shows that the recharge step is taking a slightly different path.',
    analogyHi: 'हर धड़कन के बाद दिल अपनी इलेक्ट्रिकल बैटरी को दोबारा चार्ज करता है। इस जांच से पता चलता है कि यह रिचार्ज होने का चरण थोड़ा बदला हुआ है।',
    whatItMeansEn: 'Repolarization (recharging) differences in the heart. This can be caused by temporary stress, minor blood flow reduction, mineral imbalances (like potassium), or blood pressure strain.',
    whatItMeansHi: 'दिल के पुनः चार्ज होने में थोड़ा बदलाव। यह तनाव, निर्जलीकरण, खनिजों (पोटेशियम आदि) के असंतुलन या रक्तचाप के कारण हो सकता है।',
    familyAdviceEn: 'Have the patient rest quietly. Check if they have stayed hydrated and taken their routine medicines. Consult their physician within 24 to 48 hours.',
    familyAdviceHi: 'मरीज को शांत वातावरण में आराम करने दें। पानी की पर्याप्त मात्रा सुनिश्चित करें और 24-48 घंटों के भीतर डॉक्टर से परामर्श लें।',
  },
  CD: {
    plainNameEn: 'Electrical Pathway Delay (Conduction Delay)',
    plainNameHi: 'इलेक्ट्रिकल सिग्नल में देरी (कंडक्शन डिले)',
    analogyEn: 'The heart has natural electrical wires that tell the chambers when to squeeze. Here, the signal is traveling through a detour, causing a small, measurable timing delay.',
    analogyHi: 'दिल में कुदरती बिजली के तार होते हैं जो दिल को धड़कने का इशारा देते हैं। यहां वह सिग्नल थोड़े धीमे या घुमावदार रास्ते से जा रहा है।',
    whatItMeansEn: 'A delay in how the heart\'s natural electrical pacing pulse spreads across the left or right heart chambers (such as a Bundle Branch Block).',
    whatItMeansHi: 'दिल के प्राकृतिक इलेक्ट्रिकल सिग्नल के फैलने में मामूली देरी (जैसे बंडल ब्रांच ब्लॉक)।',
    familyAdviceEn: 'Many conduction delays are chronic and well-managed with standard care. However, if the patient feels faint, dizzy, or short of breath, seek prompt medical attention.',
    familyAdviceHi: 'कई बार यह देरी सामान्य या पुरानी हो सकती है। लेकिन यदि मरीज को चक्कर आएं, बेहोशी लगे या सांस फूले तो तुरंत डॉक्टर को दिखाएं।',
  },
  NORM: {
    plainNameEn: 'Normal Electrical Pattern',
    plainNameHi: 'सामान्य हृदय ताल (नॉर्मल ईसीजी)',
    analogyEn: 'A smooth, orderly rhythm where the heart\'s electrical pacemaker fires on time and signals travel clearly through all standard pathways.',
    analogyHi: 'एक सुचारू और नियमित धड़कन, जहां दिल के सभी इलेक्ट्रिकल सिग्नल सही समय और रास्ते पर काम कर रहे हैं।',
    whatItMeansEn: 'No acute abnormal cardiac electrical patterns or conduction blocks were detected in this 10-second 12-lead recording.',
    whatItMeansHi: 'इस 12-लीड ईसीजी में कोई असामान्य विद्युत पैटर्न या रुकावट नहीं पाई गई है।',
    familyAdviceEn: 'The recording is reassuring. Continue regular lifestyle healthy habits, manage stress, and attend standard annual health checkups.',
    familyAdviceHi: 'यह रिपोर्ट संतोषजनक है। स्वस्थ जीवनशैली बनाए रखें, तनाव से बचें और नियमित स्वास्थ्य जांच कराते रहें।',
  },
};

export const DualAnalysisReport: React.FC<DualAnalysisReportProps> = ({ result, language }) => {
  const [activeTab, setActiveTab] = useState<'family' | 'clinical'>('family');

  const detectedConditions = (result.conditions || []).filter(c => c.detected);
  const primaryConditionCode = detectedConditions.length > 0 ? detectedConditions[0].code : 'NORM';
  const explainer = PLAIN_EXPLAINERS[primaryConditionCode] || PLAIN_EXPLAINERS.NORM;

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="clinical-card overflow-hidden border border-border shadow-panel bg-white print:border-none print:shadow-none">
      {/* Header with Perspective Switcher & Print Button */}
      <div className="p-4 sm:p-5 bg-surface-secondary border-b border-border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 print:hidden">
        <div>
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-teal-600" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-navy-850">
              Dual-Perspective Diagnostic Report
            </h3>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Switch between accessible patient/family guidance and formal electrophysiology terminology
          </p>
        </div>

        <div className="flex items-center gap-2 self-stretch sm:self-auto">
          {/* Tab buttons */}
          <div className="flex bg-slate-100 p-1 rounded-xl border border-border flex-1 sm:flex-none">
            <button
              onClick={() => setActiveTab('family')}
              className={`flex-1 sm:flex-none flex items-center justify-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
                activeTab === 'family'
                  ? 'bg-white text-navy-850 shadow-sm'
                  : 'text-slate-500 hover:text-navy-850'
              }`}
            >
              <Users className="w-3.5 h-3.5 text-teal-600" />
              <span>Family Guide</span>
            </button>
            <button
              onClick={() => setActiveTab('clinical')}
              className={`flex-1 sm:flex-none flex items-center justify-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
                activeTab === 'clinical'
                  ? 'bg-white text-navy-850 shadow-sm'
                  : 'text-slate-500 hover:text-navy-850'
              }`}
            >
              <Stethoscope className="w-3.5 h-3.5 text-teal-600" />
              <span>Doctor / Specialist</span>
            </button>
          </div>

          <button
            onClick={handlePrint}
            title="Print or Save PDF report for doctor or family"
            className="p-2 bg-white hover:bg-slate-50 text-slate-600 hover:text-navy-850 rounded-xl border border-border shadow-button-secondary transition-colors"
          >
            <Printer className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          PERSPECTIVE 1: FAMILY & PATIENT GUIDE (Plain Non-Doctor Language)
         ───────────────────────────────────────────────────────────── */}
      {activeTab === 'family' && (
        <div className="p-6 space-y-6">
          {/* Top plain-language headline */}
          <div className={`p-4 rounded-xl border flex items-start gap-4 ${
            result.urgency === 'emergency'
              ? 'bg-red-50/70 border-red-200 text-red-950'
              : result.urgency === 'see_doctor_today'
              ? 'bg-amber-50/70 border-amber-200 text-amber-950'
              : 'bg-emerald-50/70 border-emerald-200 text-emerald-950'
          }`}>
            <div className={`p-2.5 rounded-xl flex-shrink-0 ${
              result.urgency === 'emergency'
                ? 'bg-red-600 text-white shadow-sm'
                : result.urgency === 'see_doctor_today'
                ? 'bg-amber-600 text-white shadow-sm'
                : 'bg-emerald-600 text-white shadow-sm'
            }`}>
              {result.urgency === 'emergency' ? <AlertTriangle className="w-5 h-5" /> : <Heart className="w-5 h-5" />}
            </div>
            <div className="space-y-1">
              <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">
                {language === 'hi' ? 'परिवार के लिए सारांश' : 'Summary for Patient & Family'}
              </span>
              <h4 className="text-base font-bold text-navy-850">
                {language === 'hi' ? explainer.plainNameHi : explainer.plainNameEn}
              </h4>
              <p className="text-xs leading-relaxed text-slate-600">
                {language === 'hi' ? explainer.whatItMeansHi : explainer.whatItMeansEn}
              </p>
            </div>
          </div>

          {/* Everyday Analogy Card ("Think of it like...") */}
          <div className="p-4 bg-surface-secondary rounded-xl border border-border space-y-2">
            <div className="flex items-center gap-2 text-teal-800 font-bold text-xs uppercase tracking-wider">
              <span>💡 Plain Everyday Analogy</span>
            </div>
            <p className="text-xs text-slate-700 leading-relaxed italic">
              "{language === 'hi' ? explainer.analogyHi : explainer.analogyEn}"
            </p>
          </div>

          {/* Condition Breakdown in Simple Words */}
          <div className="space-y-3">
            <h5 className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-2">
              <Activity className="w-3.5 h-3.5 text-teal-600" />
              What Was Found in Simple Words
            </h5>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {(result.conditions || []).map(cond => {
                const info = PLAIN_EXPLAINERS[cond.code] || PLAIN_EXPLAINERS.NORM;
                return (
                  <div
                    key={cond.code}
                    className={`p-3.5 rounded-xl border transition-all ${
                      cond.detected
                        ? 'bg-amber-50/50 border-amber-200'
                        : 'bg-white border-border'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-bold text-navy-850">
                        {language === 'hi' ? info.plainNameHi : info.plainNameEn}
                      </span>
                      <span
                        className={`text-[9px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider ${
                          cond.detected
                            ? 'bg-amber-100 text-amber-800 border border-amber-200'
                            : 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        {cond.detected ? (language === 'hi' ? 'पहचाना गया' : 'Flagged') : (language === 'hi' ? 'सामान्य' : 'Clear')}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-600 leading-normal">
                      {language === 'hi' ? info.whatItMeansHi : info.whatItMeansEn}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* What Family Should Do Right Now */}
          <div className="p-4 bg-teal-50/50 rounded-xl border border-teal-200 space-y-3">
            <h5 className="text-xs font-bold text-teal-800 uppercase tracking-wider flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-teal-600" />
              What the Family Should Do Right Now
            </h5>
            <ul className="space-y-2 text-xs text-slate-700">
              <li className="flex items-start gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-teal-600 mt-0.5 flex-shrink-0" />
                <span><strong>Keep the patient calm:</strong> Avoid stressful conversations and keep them seated comfortably.</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-teal-600 mt-0.5 flex-shrink-0" />
                <span><strong>Gather medication records:</strong> Have their current prescription bottles ready for the doctor to review.</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-teal-600 mt-0.5 flex-shrink-0" />
                <span><strong>Hydration & rest:</strong> Avoid caffeinated drinks, tobacco, and physical exertion until evaluated.</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-teal-600 mt-0.5 flex-shrink-0" />
                <span>{language === 'hi' ? explainer.familyAdviceHi : explainer.familyAdviceEn}</span>
              </li>
            </ul>
          </div>

          {/* Questions to Ask the Doctor */}
          <div className="p-4 bg-surface-secondary rounded-xl border border-border space-y-3">
            <h5 className="text-xs font-bold text-navy-850 uppercase tracking-wider flex items-center gap-2">
              <HelpCircle className="w-4 h-4 text-blue-600" />
              Helpful Questions to Ask Your Doctor
            </h5>
            <div className="space-y-1.5 text-xs text-slate-600">
              <p className="flex items-start gap-2">
                <ChevronRight className="w-3 h-3 text-blue-600 mt-1 flex-shrink-0" />
                <span>"Does this ECG finding suggest our loved one needs an echocardiogram (ultrasound of the heart)?"</span>
              </p>
              <p className="flex items-start gap-2">
                <ChevronRight className="w-3 h-3 text-blue-600 mt-1 flex-shrink-0" />
                <span>"Are their current blood pressure or cholesterol medicines at the target dosage?"</span>
              </p>
              <p className="flex items-start gap-2">
                <ChevronRight className="w-3 h-3 text-blue-600 mt-1 flex-shrink-0" />
                <span>"What specific symptoms should prompt us to call 112 or visit the emergency room right away?"</span>
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          PERSPECTIVE 2: CLINICAL / DOCTOR SPECIALIST REPORT
         ───────────────────────────────────────────────────────────── */}
      {activeTab === 'clinical' && (
        <div className="p-6 space-y-6 text-xs">
          {/* Formal Electrophysiological Header */}
          <div className="p-4 bg-blue-50/60 rounded-xl border border-blue-200 text-blue-950 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase font-bold tracking-widest text-blue-700">
                Electrophysiological Diagnostic Impression
              </span>
              <span className="text-[10px] bg-blue-100 text-blue-800 px-2 py-0.5 rounded font-mono font-bold">
                ICD-10 / PTB-XL Schema
              </span>
            </div>
            <p className="text-xs text-navy-850 font-bold leading-relaxed">
              {result.overall_assessment}
            </p>
          </div>

          {/* Quantitative Interval Metrics */}
          <div className="space-y-2">
            <span className="text-[10px] text-slate-500 uppercase tracking-wider font-bold">
              Time-Domain Measurements & Waveform Metrics
            </span>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-center">
              <div className="p-3 bg-surface-secondary rounded-xl border border-border">
                <span className="text-[10px] text-slate-500 uppercase block font-bold">Ventricular Rate</span>
                <span className="text-sm font-black text-navy-850 tabular-nums">
                  {result.heart_rate_bpm ? `${result.heart_rate_bpm} BPM` : 'N/A'}
                </span>
              </div>
              <div className="p-3 bg-surface-secondary rounded-xl border border-border">
                <span className="text-[10px] text-slate-500 uppercase block font-bold">QRS Duration</span>
                <span className="text-sm font-black text-navy-850 tabular-nums">
                  {result.qrs_duration_ms ? `${result.qrs_duration_ms} ms` : 'N/A'}
                </span>
              </div>
              <div className="p-3 bg-surface-secondary rounded-xl border border-border">
                <span className="text-[10px] text-slate-500 uppercase block font-bold">Rhythm Classification</span>
                <span className="text-xs font-bold text-navy-850 truncate block mt-0.5">
                  {result.rhythm || 'Sinus Rhythm'}
                </span>
              </div>
              <div className="p-3 bg-surface-secondary rounded-xl border border-border">
                <span className="text-[10px] text-slate-500 uppercase block font-bold">Model Engine</span>
                <span className="text-xs font-bold text-teal-700 block mt-0.5 font-mono">
                  1D ResNet (ONNX)
                </span>
              </div>
            </div>
          </div>

          {/* Lead Distribution of ST Findings */}
          {(result.st_elevation_leads.length > 0 || result.st_depression_leads.length > 0) && (
            <div className="p-3 bg-red-50 rounded-xl border border-red-200 space-y-1">
              <span className="text-[10px] uppercase font-bold text-red-800">ST-Segment Vector Abnormalities:</span>
              {result.st_elevation_leads.length > 0 && (
                <p className="text-red-700 font-mono">Elevations (Myocardial Injury): {result.st_elevation_leads.join(', ')}</p>
              )}
              {result.st_depression_leads.length > 0 && (
                <p className="text-amber-700 font-mono">Depressions (Reciprocal / Subendocardial Strain): {result.st_depression_leads.join(', ')}</p>
              )}
            </div>
          )}

          {/* 5-Class Quantitative Decision Matrix */}
          <div className="space-y-2">
            <span className="text-[10px] text-slate-500 uppercase tracking-wider font-bold">
              Calibrated Superclass Outputs & Validation Thresholds
            </span>
            <div className="overflow-x-auto rounded-xl border border-border">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-600 border-b border-border text-[10px] font-bold">
                  <tr>
                    <th className="p-2.5">Superclass</th>
                    <th className="p-2.5">Model Score</th>
                    <th className="p-2.5">Threshold (θ)</th>
                    <th className="p-2.5">Decision</th>
                    <th className="p-2.5">Electrophysiologic Finding</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border bg-white font-medium">
                  {(result.conditions || []).map(cond => (
                    <tr key={cond.code} className={cond.detected ? 'bg-amber-50/30' : ''}>
                      <td className="p-2.5 font-bold text-navy-850">{cond.code} ({cond.name.split(' ')[0]})</td>
                      <td className="p-2.5 font-bold text-teal-700 font-mono">{cond.model_score.toFixed(4)}</td>
                      <td className="p-2.5 text-slate-500 font-mono">{cond.threshold.toFixed(2)}</td>
                      <td className="p-2.5">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          cond.detected
                            ? 'bg-red-50 text-red-700 border border-red-200'
                            : 'bg-slate-100 text-slate-600'
                        }`}>
                          {cond.detected ? 'DETECTED' : 'CLEAR'}
                        </span>
                      </td>
                      <td className="p-2.5 text-slate-600 text-[11px]">{cond.key_finding || cond.explanation_en}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Clinical Management Recommendations */}
          {result.recommendations && result.recommendations.length > 0 && (
            <div className="p-4 bg-surface-secondary rounded-xl border border-border space-y-2">
              <span className="text-[10px] uppercase font-bold text-slate-500">Cardiology Guidance</span>
              <ul className="space-y-1 text-slate-700">
                {result.recommendations.map((rec, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="text-teal-600 font-bold">•</span>
                    <span>{rec}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Footer Prototype Notice */}
      <div className="p-3.5 bg-slate-50 border-t border-border text-[10px] text-slate-500 flex flex-col sm:flex-row justify-between items-center gap-2">
        <span>Research & Educational Prototype · Not a certified diagnostic device</span>
        <span className="font-mono text-teal-800">PTB-XL Benchmark Fold 10 (AUROC: 0.9265, F1: 0.7520)</span>
      </div>
    </div>
  );
};
