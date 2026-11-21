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
  setWorkerUrl,
} from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import type { Hospital } from '../lib/api';

// Explicitly register bundled worker URL for MapLibre GL JS v6 under Vite
setWorkerUrl(maplibreWorkerUrl);

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

    let loadTimeout: ReturnType<typeof setTimeout> | undefined;

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

      loadTimeout = setTimeout(() => {
        setStatus((curr) => {
          if (curr === 'loading') {
            setErrorMsg('Interactive vector map tiles timed out. Please hard-refresh your browser (Ctrl+F5) or use the direct facility directions below.');
            return 'error';
          }
          return curr;
        });
      }, 7000);

      map.on('load', () => {
        clearTimeout(loadTimeout);
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

        // User location popup (safe text node)
        const userPopupEl = document.createElement('div');
        userPopupEl.style.cssText = 'font-family:sans-serif;font-size:12px;font-weight:700;color:#0f172a;padding:4px 8px;';
        userPopupEl.textContent = '📍 Your Current Location';

        const userPopup = new Popup({ offset: 15, closeButton: false }).setDOMContent(userPopupEl);

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

          // Safe DOM-based popup construction to prevent HTML injection (XSS)
          const popupCard = document.createElement('div');
          popupCard.style.cssText = 'background:#0f172a;color:#f8fafc;padding:12px;border-radius:10px;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;min-width:210px;max-width:260px;line-height:1.4;';

          const nameHeading = document.createElement('div');
          nameHeading.style.cssText = 'font-size:13px;font-weight:700;margin-bottom:4px;color:#f8fafc;';
          nameHeading.textContent = h.name || 'Healthcare Facility';
          popupCard.appendChild(nameHeading);

          if (h.address) {
            const addrDiv = document.createElement('div');
            addrDiv.style.cssText = 'font-size:11px;color:#94a3b8;margin-bottom:8px;';
            addrDiv.textContent = h.address;
            popupCard.appendChild(addrDiv);
          }

          const badgeRow = document.createElement('div');
          badgeRow.style.cssText = 'display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px;';

          const distSpan = document.createElement('span');
          distSpan.style.cssText = 'background:#1e293b;padding:2px 7px;border-radius:12px;font-size:10px;color:#10b981;font-weight:700;';
          distSpan.textContent = `📍 ${h.distance_km} km away`;
          badgeRow.appendChild(distSpan);

          const careSpan = document.createElement('span');
          careSpan.style.cssText = 'background:#1e293b;padding:2px 7px;border-radius:12px;font-size:10px;color:#38bdf8;font-weight:700;';
          careSpan.textContent = h.open_now !== false ? '● Emergency Care' : '● Medical Facility';
          badgeRow.appendChild(careSpan);

          popupCard.appendChild(badgeRow);

          const actionsRow = document.createElement('div');
          actionsRow.style.cssText = 'display:flex;gap:6px;';

          const sanitizeUrl = (u: string) => (u.startsWith('https://') || u.startsWith('http://') ? u : '#');

          const navA = document.createElement('a');
          navA.href = sanitizeUrl(mapsUrl);
          navA.target = '_blank';
          navA.rel = 'noopener noreferrer';
          navA.style.cssText = 'flex:1;text-align:center;background:#dc2626;color:white;padding:6px 4px;border-radius:6px;font-size:11px;font-weight:700;text-decoration:none;display:block;';
          navA.textContent = 'Directions';
          actionsRow.appendChild(navA);

          const osmA = document.createElement('a');
          osmA.href = sanitizeUrl(osmUrl);
          osmA.target = '_blank';
          osmA.rel = 'noopener noreferrer';
          osmA.style.cssText = 'flex:1;text-align:center;background:#334155;color:white;padding:6px 4px;border-radius:6px;font-size:11px;font-weight:700;text-decoration:none;display:block;';
          osmA.textContent = 'OpenStreetMap';
          actionsRow.appendChild(osmA);

          popupCard.appendChild(actionsRow);

          const popup = new Popup({ offset: 20 }).setDOMContent(popupCard);

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
        const errStr = String(e?.error?.message || e?.message || e || '');
        if (errStr.toLowerCase().includes('worker') || errStr.toLowerCase().includes('failed to load')) {
          clearTimeout(loadTimeout);
          setErrorMsg('Vector map worker could not initialize. Please hard-refresh (Ctrl+F5) to clear stale worker cache, or use the direct facility directions below.');
          setStatus('error');
        }
      });

      mapInstance.current = map;
    } catch (err: any) {
      console.error('Failed to initialize MapLibre map:', err);
      setErrorMsg(err.message || 'Error initializing open map.');
      setStatus('error');
    }

    return () => {
      clearTimeout(loadTimeout);
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
