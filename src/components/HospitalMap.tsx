/**
 * Google Maps component — shows user location + nearby hospitals as markers.
 * Uses @googlemaps/js-api-loader for clean async loading.
 */
import React, { useEffect, useRef, useState } from 'react';
import { Loader } from '@googlemaps/js-api-loader';
import type { Hospital } from '../lib/api';

const MAPS_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string;

interface HospitalMapProps {
  userLat: number;
  userLon: number;
  hospitals: Hospital[];
}

const DARK_STYLES: google.maps.MapTypeStyle[] = [
  { elementType: 'geometry', stylers: [{ color: '#0f172a' }] },
  { elementType: 'labels.text.stroke', stylers: [{ color: '#0f172a' }] },
  { elementType: 'labels.text.fill', stylers: [{ color: '#94a3b8' }] },
  { featureType: 'administrative.locality', elementType: 'labels.text.fill', stylers: [{ color: '#cbd5e1' }] },
  { featureType: 'poi', elementType: 'labels', stylers: [{ visibility: 'off' }] },
  { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#1e293b' }] },
  { featureType: 'road', elementType: 'geometry.stroke', stylers: [{ color: '#334155' }] },
  { featureType: 'road.highway', elementType: 'geometry', stylers: [{ color: '#334155' }] },
  { featureType: 'transit', elementType: 'geometry', stylers: [{ color: '#1e293b' }] },
  { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#0c1930' }] },
  { featureType: 'water', elementType: 'labels.text.fill', stylers: [{ color: '#334155' }] },
];

const HospitalMap: React.FC<HospitalMapProps> = ({ userLat, userLon, hospitals }) => {
  const mapRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMsg, setErrorMsg] = useState('');
  const mapInstance = useRef<google.maps.Map | null>(null);
  const markersRef = useRef<google.maps.Marker[]>([]);

  useEffect(() => {
    if (!MAPS_KEY) {
      setErrorMsg('Google Maps API key not configured.');
      setStatus('error');
      return;
    }

    const loader = new Loader({
      apiKey: MAPS_KEY,
      version: 'weekly',
      libraries: ['places', 'geometry'],
    });

    loader.load().then(() => {
      if (!mapRef.current) return;

      const map = new google.maps.Map(mapRef.current, {
        center: { lat: userLat, lng: userLon },
        zoom: 13,
        styles: DARK_STYLES,
        disableDefaultUI: false,
        zoomControl: true,
        streetViewControl: false,
        fullscreenControl: false,
        mapTypeControl: false,
      });

      mapInstance.current = map;

      // ── User location marker (green)
      new google.maps.Marker({
        position: { lat: userLat, lng: userLon },
        map,
        title: 'Your Location',
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 10,
          fillColor: '#10b981',
          fillOpacity: 1,
          strokeColor: '#ffffff',
          strokeWeight: 2.5,
        },
        zIndex: 100,
      });

      // ── Pulse ring around user
      new google.maps.Circle({
        center: { lat: userLat, lng: userLon },
        radius: 300,
        map,
        fillColor: '#10b981',
        fillOpacity: 0.08,
        strokeColor: '#10b981',
        strokeOpacity: 0.3,
        strokeWeight: 1,
      });

      // ── Hospital markers (red, numbered)
      markersRef.current.forEach((m) => m.setMap(null));
      markersRef.current = [];

      hospitals.forEach((hospital, idx) => {
        const marker = new google.maps.Marker({
          position: { lat: hospital.lat, lng: hospital.lon },
          map,
          title: hospital.name,
          label: {
            text: String(idx + 1),
            color: '#ffffff',
            fontSize: '11px',
            fontWeight: 'bold',
          },
          icon: {
            path: google.maps.SymbolPath.CIRCLE,
            scale: 14,
            fillColor: '#ef4444',
            fillOpacity: 0.95,
            strokeColor: '#ffffff',
            strokeWeight: 2,
          },
          zIndex: 50 - idx,
        });

        const content = `
          <div style="background:#1e293b;color:#f8fafc;padding:14px;border-radius:10px;
                      font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                      min-width:200px;max-width:260px;box-shadow:0 4px 20px #0005">
            <div style="font-size:13px;font-weight:700;margin-bottom:4px;color:#f8fafc">${hospital.name}</div>
            <div style="font-size:11px;color:#94a3b8;margin-bottom:8px">${hospital.address || ''}</div>
            <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px">
              <span style="background:#0f172a;padding:2px 8px;border-radius:20px;font-size:10px;color:#10b981;font-weight:600">
                📍 ${hospital.distance_km} km away
              </span>
              ${hospital.rating ? `<span style="background:#0f172a;padding:2px 8px;border-radius:20px;font-size:10px;color:#f59e0b;font-weight:600">⭐ ${hospital.rating}</span>` : ''}
              ${hospital.open_now === true ? '<span style="background:#0f172a;padding:2px 8px;border-radius:20px;font-size:10px;color:#10b981;font-weight:600">● Open Now</span>' : ''}
            </div>
            <a href="${hospital.maps_url}" target="_blank" rel="noopener noreferrer"
               style="display:block;text-align:center;background:#ef4444;color:white;padding:7px;border-radius:6px;
                      font-size:12px;font-weight:700;text-decoration:none;transition:background 0.2s">
              → Open in Google Maps
            </a>
          </div>
        `;

        const info = new google.maps.InfoWindow({ content });
        marker.addListener('click', () => {
          markersRef.current.forEach(() => info.close());
          info.open({ map, anchor: marker });
        });

        markersRef.current.push(marker);
      });

      // Fit bounds to show all markers
      if (hospitals.length > 0) {
        const bounds = new google.maps.LatLngBounds();
        bounds.extend({ lat: userLat, lng: userLon });
        hospitals.forEach((h) => bounds.extend({ lat: h.lat, lng: h.lon }));
        map.fitBounds(bounds, 50);
      }

      setStatus('ready');
    }).catch((err) => {
      console.error('Google Maps load error:', err);
      setErrorMsg(String(err));
      setStatus('error');
    });
  }, [userLat, userLon, hospitals]);

  if (status === 'error') {
    return (
      <div className="w-full h-72 rounded-2xl bg-slate-900 border border-red-500/20 flex items-center justify-center">
        <p className="text-red-400 text-sm text-center px-4">
          ⚠ Map unavailable: {errorMsg || 'Google Maps not loaded'}
        </p>
      </div>
    );
  }

  return (
    <div className="relative w-full h-80 rounded-2xl overflow-hidden bg-slate-900">
      <div ref={mapRef} className="w-full h-full" />
      {status === 'loading' && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-slate-900">
          <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-slate-400 text-xs">Loading map…</p>
        </div>
      )}
    </div>
  );
};

export default HospitalMap;
