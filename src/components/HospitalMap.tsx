/**
 * HospitalMap — Open-source MapLibre GL JS & OpenFreeMap vector map component.
 * Displays user location and nearby cardiac emergency facilities with zero API keys or billable quotas.
 */
import React, { useEffect, useRef, useState } from 'react';
import {
  Map,
  Marker,
  Popup,
  NavigationControl,
  AttributionControl,
  LngLatBounds,
} from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { Hospital } from '../lib/api';

interface HospitalMapProps {
  userLat: number;
  userLon: number;
  hospitals: Hospital[];
}

const OPENFREEMAP_STYLE = 'https://tiles.openfreemap.org/styles/liberty';

const isWebGLSupported = (): boolean => {
  try {
    const canvas = document.createElement('canvas');
    return !!(window.WebGLRenderingContext && (canvas.getContext('webgl') || canvas.getContext('experimental-webgl')));
  } catch {
    return false;
  }
};

const HospitalMap: React.FC<HospitalMapProps> = ({ userLat, userLon, hospitals }) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<Map | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    if (!mapContainerRef.current) return;

    // Check WebGL support
    if (!isWebGLSupported()) {
      setErrorMsg('WebGL is not supported or disabled in this browser. Please use the list below.');
      setStatus('error');
      return;
    }

    setStatus('loading');

    // Clean up previous instance
    if (mapInstance.current) {
      mapInstance.current.remove();
      mapInstance.current = null;
    }

    try {
      const map = new Map({
        container: mapContainerRef.current,
        style: OPENFREEMAP_STYLE,
        center: [userLon, userLat],
        zoom: 13,
        attributionControl: false,
      });

      // Add navigation controls
      map.addControl(new NavigationControl({ showCompass: true }), 'top-right');
      map.addControl(
        new AttributionControl({
          compact: true,
          customAttribution: '© <a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> | © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> | Geoapify',
        }),
        'bottom-right'
      );

      map.on('load', () => {
        setStatus('ready');

        // ── 1. User Location Marker (Pulsing Emerald)
        const userEl = document.createElement('div');
        userEl.className = 'user-map-pin';
        userEl.style.width = '22px';
        userEl.style.height = '22px';
        userEl.style.borderRadius = '50%';
        userEl.style.backgroundColor = '#10b981';
        userEl.style.border = '3px solid #ffffff';
        userEl.style.boxShadow = '0 0 12px rgba(16, 185, 129, 0.7)';
        userEl.style.cursor = 'pointer';

        const userPopup = new Popup({ offset: 15, closeButton: false }).setHTML(
          `<div style="font-family:sans-serif;font-size:12px;font-weight:700;color:#0f172a;padding:4px 8px;">
            📍 Your Current Location
          </div>`
        );

        const userMarker = new Marker({ element: userEl })
          .setLngLat([userLon, userLat])
          .setPopup(userPopup)
          .addTo(map);

        markersRef.current.push(userMarker);

        // ── 2. Hospital Markers (Numbered Red Pins)
        const bounds = new LngLatBounds();
        bounds.extend([userLon, userLat]);

        hospitals.forEach((h, idx) => {
          bounds.extend([h.lon, h.lat]);

          const el = document.createElement('div');
          el.className = 'hospital-map-pin';
          el.style.width = '28px';
          el.style.height = '28px';
          el.style.borderRadius = '50%';
          el.style.backgroundColor = '#dc2626';
          el.style.color = '#ffffff';
          el.style.display = 'flex';
          el.style.alignItems = 'center';
          el.style.justifyContent = 'center';
          el.style.fontSize = '12px';
          el.style.fontWeight = 'bold';
          el.style.border = '2px solid #ffffff';
          el.style.boxShadow = '0 3px 8px rgba(0,0,0,0.35)';
          el.style.cursor = 'pointer';
          el.innerText = String(idx + 1);

          const osmUrl = h.osm_url || `https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route=${userLat}%2C${userLon}%3B${h.lat}%2C${h.lon}`;
          const mapsUrl = h.maps_url || `https://www.google.com/maps/dir/?api=1&origin=${userLat},${userLon}&destination=${h.lat},${h.lon}`;

          const popupContent = `
            <div style="background:#0f172a;color:#f8fafc;padding:12px;border-radius:10px;
                        font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                        min-width:210px;max-width:260px;line-height:1.4;">
              <div style="font-size:13px;font-weight:700;margin-bottom:4px;color:#f8fafc;">${h.name}</div>
              <div style="font-size:11px;color:#94a3b8;margin-bottom:8px;">${h.address || ''}</div>
              <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px;">
                <span style="background:#1e293b;padding:2px 7px;border-radius:12px;font-size:10px;color:#10b981;font-weight:700;">
                  📍 ${h.distance_km} km away
                </span>
                ${h.open_now !== false ? '<span style="background:#1e293b;padding:2px 7px;border-radius:12px;font-size:10px;color:#38bdf8;font-weight:700;">● 24x7 Emergency</span>' : ''}
              </div>
              <div style="display:flex;gap:6px;">
                <a href="${mapsUrl}" target="_blank" rel="noopener noreferrer"
                   style="flex:1;text-align:center;background:#dc2626;color:white;padding:6px 4px;border-radius:6px;
                          font-size:11px;font-weight:700;text-decoration:none;display:block;">
                  Directions
                </a>
                <a href="${osmUrl}" target="_blank" rel="noopener noreferrer"
                   style="flex:1;text-align:center;background:#334155;color:white;padding:6px 4px;border-radius:6px;
                          font-size:11px;font-weight:700;text-decoration:none;display:block;">
                  OpenStreetMap
                </a>
              </div>
            </div>
          `;

          const popup = new Popup({ offset: 20 }).setHTML(popupContent);

          const marker = new Marker({ element: el })
            .setLngLat([h.lon, h.lat])
            .setPopup(popup)
            .addTo(map);

          markersRef.current.push(marker);
        });

        // Fit map viewport to encompass user and hospital pins
        if (hospitals.length > 0) {
          map.fitBounds(bounds, {
            padding: { top: 40, bottom: 40, left: 40, right: 40 },
            maxZoom: 14,
          });
        }
      });

      map.on('error', (e: any) => {
        console.warn('MapLibre GL tile loading notice:', e);
      });

      mapInstance.current = map;
    } catch (err: any) {
      console.error('Failed to initialize MapLibre map:', err);
      setErrorMsg(err.message || 'Error initializing open map.');
      setStatus('error');
    }

    return () => {
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      if (mapInstance.current) {
        mapInstance.current.remove();
        mapInstance.current = null;
      }
    };
  }, [userLat, userLon, hospitals]);

  if (status === 'error') {
    return (
      <div className="w-full h-72 rounded-2xl bg-slate-900 border border-slate-700 flex flex-col items-center justify-center p-6 text-center">
        <p className="text-amber-400 text-xs font-semibold mb-2">
          🗺️ Offline Map Notice
        </p>
        <p className="text-slate-400 text-xs max-w-md">
          {errorMsg || 'Interactive map tiles unavailable. You can still use the direct directions links in the hospital list below.'}
        </p>
      </div>
    );
  }

  return (
    <div className="relative w-full h-80 rounded-2xl overflow-hidden border border-border bg-slate-900 shadow-sm">
      <div ref={mapContainerRef} className="w-full h-full" />
      {status === 'loading' && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-slate-900/80 backdrop-blur-sm z-10">
          <div className="w-7 h-7 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-slate-300 text-xs font-medium">Loading OpenFreeMap vector tiles…</p>
        </div>
      )}
    </div>
  );
};

export default HospitalMap;
