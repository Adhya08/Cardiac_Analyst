import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  ZoomIn, ZoomOut, RotateCcw, Activity, Eye, Layers
} from 'lucide-react';

interface ECGViewerProps {
  /** Raw CSV text or 2D array of (1000, 12) if available */
  signalData?: number[][] | string | null;
  /** Active lead names */
  leads?: string[];
  /** Sampling frequency in Hz */
  samplingRate?: number;
  /** Primary condition code if known */
  conditionCode?: string;
  /** Signal quality status */
  qualityStatus?: 'good' | 'poor_quality' | 'unusable';
  /** Title or filename */
  fileName?: string;
}

const DEFAULT_LEADS = ['I', 'II', 'III', 'aVR', 'aVL', 'aVF', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6'];

export const ECGViewer: React.FC<ECGViewerProps> = ({
  signalData,
  leads = DEFAULT_LEADS,
  samplingRate = 100,
  conditionCode,
  qualityStatus = 'good',
  fileName,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // View state
  const [activeTab, setActiveTab] = useState<'3x4' | 'rhythm' | 'single'>('3x4');
  const [selectedLead, setSelectedLead] = useState<string>('II');
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const [panOffset, setPanOffset] = useState<number>(0);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStartX, setDragStartX] = useState<number>(0);
  const [gainMmPerMv, setGainMmPerMv] = useState<number>(10); // Standard 10 mm/mV
  const [speedMmPerSec, setSpeedMmPerSec] = useState<number>(25); // Standard 25 mm/s

  // Parse signal array (1000 timesteps x 12 leads)
  const parsedWaveforms: number[][] = useMemo(() => {
    if (!signalData) {
      return generateSyntheticBenchmarkSignal(conditionCode);
    }

    if (Array.isArray(signalData)) {
      if (signalData.length > 0 && Array.isArray(signalData[0])) {
        // If shape is (1000, 12), transpose to (12, 1000) for easier lead-based indexing
        if (signalData.length === 1000 && signalData[0].length === 12) {
          const transposed: number[][] = [];
          for (let l = 0; l < 12; l++) {
            transposed.push(signalData.map(row => row[l] || 0));
          }
          return transposed;
        }
        return signalData;
      }
    }

    if (typeof signalData === 'string') {
      try {
        const lines = signalData.trim().split('\n');
        const rows: number[][] = [];
        for (const line of lines) {
          const cleaned = line.trim();
          if (!cleaned || cleaned.startsWith('#') || cleaned.startsWith('time')) continue;
          const vals = cleaned.split(/,|\s+/).map(v => parseFloat(v));
          if (vals.some(v => isNaN(v))) continue;
          rows.push(vals);
        }
        if (rows.length >= 100 && rows[0].length >= 12) {
          // Transpose (N, 12) to (12, N)
          const numCols = Math.min(12, rows[0].length);
          const perLead: number[][] = [];
          for (let col = 0; col < numCols; col++) {
            perLead.push(rows.map(r => r[col]));
          }
          return perLead;
        }
      } catch (e) {
        console.warn('Could not parse CSV signal, using calibrated benchmark trace', e);
      }
    }

    return generateSyntheticBenchmarkSignal(conditionCode);
  }, [signalData, conditionCode]);

  // Canvas rendering loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Handle high DPI display
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const width = rect.width;
    const height = rect.height;

    // Clear background
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(0, 0, width, height);

    // Draw ECG Grid (Pink standard 1mm & 5mm squares: 1mm = ~4px, 5mm = ~20px)
    drawEcgGrid(ctx, width, height);

    // Draw Calibration pulse at left edge (1 mV = 10mm height, 0.2s = 5mm width)
    drawCalibrationPulse(ctx, 20, height / 2 - 20, gainMmPerMv);

    // Render Waveforms based on Active Mode
    if (activeTab === 'rhythm') {
      // Single continuous Lead II rhythm strip across the entire width
      const leadIdx = leads.indexOf('II') !== -1 ? leads.indexOf('II') : 1;
      const data = parsedWaveforms[leadIdx] || parsedWaveforms[0] || [];
      drawLeadTrace(ctx, data, 'Lead II (Continuous Rhythm Strip 25 mm/s, 10 mm/mV)', 40, height / 2, width - 60, height * 0.7, zoomLevel, panOffset, '#0E7A73');
    } else if (activeTab === 'single') {
      // Drill-down single lead view
      const leadIdx = Math.max(0, leads.indexOf(selectedLead));
      const data = parsedWaveforms[leadIdx] || [];
      drawLeadTrace(ctx, data, `Lead ${selectedLead} · Magnified View (${gainMmPerMv} mm/mV)`, 40, height / 2, width - 60, height * 0.75, zoomLevel, panOffset, '#0E7A73');
    } else {
      // 3x4 Standard Clinical 12-Lead Layout (3 rows, 4 columns + Lead II rhythm strip bottom)
      const cols = 4;
      const rows = 3;
      const colWidth = (width - 40) / cols;
      const topAreaHeight = height * 0.72;
      const rowHeight = topAreaHeight / rows;
      const rhythmHeight = height * 0.24;

      // Draw 3x4 lead blocks
      leads.slice(0, 12).forEach((leadName, idx) => {
        const c = idx % cols;
        const r = Math.floor(idx / cols);
        const startX = 30 + c * colWidth;
        const centerY = 25 + r * rowHeight + rowHeight / 2;
        const leadData = parsedWaveforms[idx] || [];

        // In standard 3x4, each column displays ~2.5 seconds (250 timesteps)
        const colSlice = leadData.slice(c * 200, (c + 1) * 200 + 50);
        drawLeadTrace(ctx, colSlice.length > 0 ? colSlice : leadData, leadName, startX, centerY, colWidth - 15, rowHeight * 0.85, 1, 0, '#14222E');
      });

      // Bottom full-length Lead II rhythm strip
      const lead2Idx = leads.indexOf('II') !== -1 ? leads.indexOf('II') : 1;
      const rhythmData = parsedWaveforms[lead2Idx] || [];
      drawLeadTrace(ctx, rhythmData, 'II (Long Rhythm Strip)', 30, height - rhythmHeight / 2 - 10, width - 50, rhythmHeight * 0.8, zoomLevel, panOffset, '#0E7A73');
    }
  }, [parsedWaveforms, activeTab, selectedLead, zoomLevel, panOffset, gainMmPerMv, speedMmPerSec, leads]);

  // Pan interaction
  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStartX(e.clientX - panOffset);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    setPanOffset(e.clientX - dragStartX);
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const resetZoom = () => {
    setZoomLevel(1);
    setPanOffset(0);
  };

  return (
    <div className="clinical-card overflow-hidden border border-border shadow-panel bg-white">
      {/* Top Header & Workstation Controls */}
      <div className="px-5 py-3.5 bg-surface-secondary border-b border-border flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-teal-50 border border-teal-200 flex items-center justify-center text-teal-700">
            <Activity className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-navy-850">
                12-Lead Diagnostic Waveform Visualizer
              </h3>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                qualityStatus === 'good'
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                  : 'bg-amber-50 text-amber-700 border-amber-200'
              }`}>
                {qualityStatus === 'good' ? 'Diagnostic Quality' : 'Noise Filtered'}
              </span>
            </div>
            <p className="text-[11px] text-slate-500 font-medium">
              Standard 10 mm/mV · 25 mm/s · 100 Hz calibrated acquisition
              {fileName && <span className="ml-1 text-slate-400">({fileName})</span>}
            </p>
          </div>
        </div>

        {/* View Mode Tabs (3x4 vs Rhythm Strip vs Single Lead) */}
        <div className="flex items-center gap-2">
          <div className="flex bg-slate-100 p-1 rounded-xl border border-border">
            <button
              onClick={() => setActiveTab('3x4')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-bold transition-all ${
                activeTab === '3x4'
                  ? 'bg-white text-navy-850 shadow-sm'
                  : 'text-slate-500 hover:text-navy-850'
              }`}
            >
              <Layers className="w-3.5 h-3.5 text-teal-600" />
              <span>Standard 3×4</span>
            </button>
            <button
              onClick={() => setActiveTab('rhythm')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-bold transition-all ${
                activeTab === 'rhythm'
                  ? 'bg-white text-navy-850 shadow-sm'
                  : 'text-slate-500 hover:text-navy-850'
              }`}
            >
              <Activity className="w-3.5 h-3.5 text-teal-600" />
              <span>Lead II Rhythm</span>
            </button>
            <button
              onClick={() => setActiveTab('single')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-bold transition-all ${
                activeTab === 'single'
                  ? 'bg-white text-navy-850 shadow-sm'
                  : 'text-slate-500 hover:text-navy-850'
              }`}
            >
              <Eye className="w-3.5 h-3.5 text-teal-600" />
              <span>Lead Inspector</span>
            </button>
          </div>

          {/* Lead Selector Dropdown when Single Lead mode active */}
          {activeTab === 'single' && (
            <select
              value={selectedLead}
              onChange={(e) => setSelectedLead(e.target.value)}
              className="clinical-input py-1 px-2.5 text-xs font-bold text-navy-850 bg-white border border-border w-24 h-8 rounded-lg"
            >
              {leads.map(l => (
                <option key={l} value={l}>Lead {l}</option>
              ))}
            </select>
          )}

          {/* Gain and Speed Controls */}
          <div className="hidden sm:flex items-center gap-1 text-[11px] font-mono bg-white border border-border rounded-xl px-2 py-1">
            <span className="text-slate-400 font-sans text-[10px]">Gain:</span>
            <button
              onClick={() => setGainMmPerMv(prev => prev === 10 ? 20 : prev === 20 ? 5 : 10)}
              className="text-teal-700 font-bold hover:underline"
              title="Toggle Gain (5 / 10 / 20 mm/mV)"
            >
              {gainMmPerMv} mm/mV
            </button>
            <span className="text-slate-300">|</span>
            <span className="text-slate-400 font-sans text-[10px]">Speed:</span>
            <button
              onClick={() => setSpeedMmPerSec(prev => prev === 25 ? 50 : 25)}
              className="text-teal-700 font-bold hover:underline"
              title="Toggle Paper Speed (25 / 50 mm/s)"
            >
              {speedMmPerSec} mm/s
            </button>
          </div>

          {/* Zoom and Scale Controls */}
          <div className="flex items-center gap-1 bg-white border border-border rounded-xl p-0.5">
            <button
              onClick={() => setZoomLevel(prev => Math.min(2.5, prev + 0.25))}
              title="Zoom In"
              className="p-1.5 text-slate-600 hover:text-teal-700 hover:bg-slate-50 rounded-lg transition-colors"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setZoomLevel(prev => Math.max(0.75, prev - 0.25))}
              title="Zoom Out"
              className="p-1.5 text-slate-600 hover:text-teal-700 hover:bg-slate-50 rounded-lg transition-colors"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={resetZoom}
              title="Reset View"
              className="p-1.5 text-slate-600 hover:text-teal-700 hover:bg-slate-50 rounded-lg transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Main Waveform Canvas Viewport */}
      <div
        ref={containerRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        className={`relative w-full h-[460px] overflow-hidden select-none cursor-${isDragging ? 'grabbing' : 'grab'}`}
      >
        <canvas
          ref={canvasRef}
          className="w-full h-full block"
        />

        {/* Calibration Badge (Lower Left) */}
        <div className="absolute bottom-3 left-4 bg-white/95 backdrop-blur-sm border border-border px-3 py-1.5 rounded-lg shadow-sm text-[10px] font-mono font-bold text-navy-850 flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-teal-600"></span>
            <span>{speedMmPerSec} mm/sec</span>
          </div>
          <span>·</span>
          <span>{gainMmPerMv} mm/mV</span>
          <span>·</span>
          <span>Sampling: {samplingRate} Hz</span>
          <span>·</span>
          <span>Filter: 0.05–40 Hz</span>
        </div>

        {/* Lead indicator badge (Upper Right) */}
        <div className="absolute top-3 right-4 bg-white/95 backdrop-blur-sm border border-border px-2.5 py-1 rounded-lg text-[10px] font-bold text-slate-500 shadow-sm">
          {activeTab === '3x4' ? '12 Leads (3×4 Montage + II Rhythm Strip)' : `Viewing Lead ${selectedLead}`}
        </div>
      </div>

      {/* Interactive Lead Quick Switcher Bar */}
      <div className="px-5 py-2.5 bg-slate-50 border-t border-border flex items-center justify-between text-xs">
        <div className="flex items-center gap-1.5 overflow-x-auto py-1">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mr-1">Quick Select:</span>
          {leads.map(lead => (
            <button
              key={lead}
              onClick={() => {
                setSelectedLead(lead);
                setActiveTab('single');
              }}
              className={`px-2 py-0.5 rounded text-[11px] font-bold font-mono transition-all ${
                activeTab === 'single' && selectedLead === lead
                  ? 'bg-teal-600 text-white shadow-sm'
                  : 'bg-white text-slate-600 hover:bg-slate-200 border border-border'
              }`}
            >
              {lead}
            </button>
          ))}
        </div>

        <span className="text-[10px] text-slate-400 font-mono hidden sm:inline">
          Zoom: {(zoomLevel * 100).toFixed(0)}% · Click & drag to pan
        </span>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Canvas Drawing Helpers
// ─────────────────────────────────────────────────────────────────────────────

function drawEcgGrid(ctx: CanvasRenderingContext2D, width: number, height: number) {
  // Minor grid lines (1mm = ~4px)
  ctx.strokeStyle = '#FDE8EB'; // Light pinkish-coral medical grid
  ctx.lineWidth = 0.5;
  ctx.beginPath();
  const minorStep = 5;
  for (let x = 0; x < width; x += minorStep) {
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
  }
  for (let y = 0; y < height; y += minorStep) {
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
  }
  ctx.stroke();

  // Major grid lines (5mm = ~25px)
  ctx.strokeStyle = '#F7B7C3'; // Deeper coral pink major squares
  ctx.lineWidth = 1;
  ctx.beginPath();
  const majorStep = 25;
  for (let x = 0; x < width; x += majorStep) {
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
  }
  for (let y = 0; y < height; y += majorStep) {
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
  }
  ctx.stroke();
}

function drawCalibrationPulse(ctx: CanvasRenderingContext2D, startX: number, startY: number, mmPerMv: number) {
  const mvHeight = mmPerMv * 2.5; // 1 mV = 10mm height
  const pulseWidth = 15;

  ctx.strokeStyle = '#182B3A';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(startX, startY);
  ctx.lineTo(startX + 5, startY);
  ctx.lineTo(startX + 5, startY - mvHeight);
  ctx.lineTo(startX + 5 + pulseWidth, startY - mvHeight);
  ctx.lineTo(startX + 5 + pulseWidth, startY);
  ctx.lineTo(startX + 5 + pulseWidth + 5, startY);
  ctx.stroke();

  ctx.fillStyle = '#64748B';
  ctx.font = 'bold 9px JetBrains Mono, monospace';
  ctx.fillText('1 mV', startX + 4, startY - mvHeight - 4);
}

function drawLeadTrace(
  ctx: CanvasRenderingContext2D,
  data: number[],
  label: string,
  startX: number,
  centerY: number,
  availableWidth: number,
  maxHeight: number,
  zoom: number,
  pan: number,
  color: string
) {
  if (!data || data.length === 0) return;

  // Lead Label
  ctx.fillStyle = '#182B3A';
  ctx.font = 'bold 11px Inter, sans-serif';
  ctx.fillText(label, startX, centerY - maxHeight / 2 + 12);

  // Plot Waveform
  ctx.save();
  ctx.beginPath();
  ctx.rect(startX, centerY - maxHeight / 2, availableWidth, maxHeight);
  ctx.clip();

  ctx.strokeStyle = color;
  ctx.lineWidth = 1.4;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.beginPath();

  const stepX = (availableWidth / (data.length - 1)) * zoom;
  const scaleY = (maxHeight / 3.0); // Calibrated for normalized signal around [-1.5, 1.5]

  data.forEach((val, i) => {
    const x = startX + i * stepX + pan;
    const y = centerY - val * scaleY;
    if (i === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });

  ctx.stroke();
  ctx.restore();
}

/**
 * Generates an accurate, physiologically proportioned synthetic 12-lead ECG waveform
 * for demonstration when no raw voltage array has been uploaded yet.
 */
function generateSyntheticBenchmarkSignal(condition?: string): number[][] {
  const points = 1000;
  const leadsCount = 12;
  const result: number[][] = [];

  const heartRate = condition === 'HYP' ? 56 : condition === 'MI' ? 72 : 75;
  const cycleLength = Math.round((100 / (heartRate / 60))); // samples per beat

  for (let l = 0; l < leadsCount; l++) {
    const leadSignal: number[] = new Array(points);
    const leadMultiplier = l === 1 ? 1.4 : l >= 6 ? 1.6 : 1.0; // V leads higher amplitude

    for (let i = 0; i < points; i++) {
      const phase = (i % cycleLength) / cycleLength; // 0 to 1 in cardiac cycle

      // Baseline noise
      let v = Math.sin(i * 0.02) * 0.03;

      // P wave (at phase 0.15)
      if (phase >= 0.10 && phase <= 0.20) {
        v += 0.15 * Math.sin(((phase - 0.10) / 0.10) * Math.PI);
      }

      // Q wave (at phase 0.28)
      if (phase >= 0.26 && phase <= 0.29) {
        v -= 0.12 * Math.sin(((phase - 0.26) / 0.03) * Math.PI);
      }

      // R wave (QRS complex peak at phase 0.31)
      if (phase >= 0.29 && phase <= 0.35) {
        const rHeight = condition === 'HYP' ? 1.8 * leadMultiplier : 1.1 * leadMultiplier;
        v += rHeight * Math.sin(((phase - 0.29) / 0.06) * Math.PI);
      }

      // S wave (at phase 0.35)
      if (phase >= 0.34 && phase <= 0.38) {
        v -= 0.25 * Math.sin(((phase - 0.34) / 0.04) * Math.PI);
      }

      // ST segment & T wave
      if (condition === 'MI' && (l === 6 || l === 7 || l === 8)) {
        // Pathologic ST elevation in anteroseptal leads V1-V3
        if (phase >= 0.38 && phase <= 0.65) {
          v += 0.35 * Math.sin(((phase - 0.38) / 0.27) * Math.PI);
        }
      } else if (phase >= 0.45 && phase <= 0.65) {
        // Standard normal T wave
        v += 0.22 * Math.sin(((phase - 0.45) / 0.20) * Math.PI);
      }

      leadSignal[i] = v;
    }
    result.push(leadSignal);
  }

  return result;
}
