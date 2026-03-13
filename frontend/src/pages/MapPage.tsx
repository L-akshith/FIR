import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { MapContainer, TileLayer, CircleMarker, Circle, Popup, useMap, Polygon, Tooltip } from 'react-leaflet';
import MarkerClusterGroup from 'react-leaflet-cluster';
import { fetchMapData } from '../lib/api';
import PageHeader from '../components/PageHeader';
import { useAuthStore } from '../stores/authStore';
import type { LatLngExpression } from 'leaflet';

interface MapPin {
  id: string;
  latitude: number;
  longitude: number;
  disease: string;
  confidence: number;
  severity: string;
  color: string;
}

interface MapZone {
  id: string;
  disease: string;
  center_lat: number | string;
  center_lon?: number;
  radius_km: number;
  case_count: number;
  boundary?: string;
  centroid?: string;
  risk_level?: string;
}

interface TalukZone {
  id: string;
  taluk: string;
  district: string;
  center_lat: number;
  center_lon: number;
  severity: string;
  avg_incidence: number;
  avg_intensity: number;
  max_incidence: number;
  affected_villages: number;
  total_villages: number;
  inner_radius_km: number;
  square_half_km: number;
  outer_radius_km: number;
}

interface VillagePin {
  id: string;
  latitude: number;
  longitude: number;
  disease: string;
  confidence: number;
  severity: string;
  color: string;
  village: string;
  taluk: string;
  district: string;
  incidence: number;
  intensity: number;
}

function parseWktPoint(wkt: string): [number, number] | null {
  if (!wkt) return null;
  const match = wkt.match(/POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)\s*\)/i);
  if (match) return [parseFloat(match[2]), parseFloat(match[1])];
  return null;
}

function parseWktPolygon(wkt: string): [number, number][] | null {
  if (!wkt) return null;
  const match = wkt.match(/POLYGON\s*\(\(([\s\S]+?)\)\)/i);
  if (!match) return null;
  const pairs = match[1].split(',').map(p => p.trim());
  return pairs.map(pair => {
    const coords = pair.split(' ');
    return [parseFloat(coords[1]), parseFloat(coords[0])];
  });
}

function ZoomWatcher({ onZoomChange }: { onZoomChange: (z: number) => void }) {
  const map = useMap();
  useEffect(() => {
    const handler = () => onZoomChange(map.getZoom());
    map.on('zoomend', handler);
    return () => { map.off('zoomend', handler); };
  }, [map, onZoomChange]);
  return null;
}

function MapResizer() {
  const map = useMap();
  useEffect(() => {
    const timeout = setTimeout(() => {
      map.invalidateSize();
    }, 100);
    return () => clearTimeout(timeout);
  }, [map]);
  return null;
}

function MapController({ center }: { center: [number, number] }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, map.getZoom(), { animate: true });
  }, [center, map]);
  return null;
}

export default function MapPage() {
  const { t } = useTranslation();
  const { profile } = useAuthStore();
  const [pins, setPins] = useState<MapPin[]>([]);
  const [villagePins, setVillagePins] = useState<VillagePin[]>([]);
  const [talukZones, setTalukZones] = useState<TalukZone[]>([]);
  const [projectedZones, setProjectedZones] = useState<MapZone[]>([]);
  const [historicalPolygon, setHistoricalPolygon] = useState<{lat: number, lng: number}[]>([]);
  const [zoom, setZoom] = useState(8);
  const [loading, setLoading] = useState(true);
  const [windData, setWindData] = useState<{ speed: number; deg: number } | null>(null);
  
  // Dynamic Location States
  const [radius, setRadius] = useState<number>(100);
  const [mapCenter, setMapCenter] = useState<[number, number]>([13.5, 75.5]);
  const [userLoc, setUserLoc] = useState<[number, number] | null>(null);

  // 1. On Mount: Geocode Pincode or ask Geolocation
  useEffect(() => {
    let mounted = true;
    const initLocation = async () => {
      // Try to get coords from default pincode via Nominatim
      if (profile?.pincode) {
        try {
          const res = await fetch(`https://nominatim.openstreetmap.org/search?postalcode=${profile.pincode}&country=India&format=json`);
          const data = await res.json();
          if (data && data.length > 0 && mounted) {
            const lat = parseFloat(data[0].lat);
            const lon = parseFloat(data[0].lon);
            setMapCenter([lat, lon]);
            setUserLoc([lat, lon]);
          }
        } catch (e) {
          console.error("Geocoding failed", e);
        }
      }
    };
    initLocation();
    return () => { mounted = false; };
  }, [profile?.pincode]);

  // 2. Fetch data whenever center or radius changes
  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const data = await fetchMapData(mapCenter[0], mapCenter[1], radius);
        setPins(data.pins ?? []);
        setVillagePins(data.csv_village_pins ?? []);
        setTalukZones(data.csv_taluk_zones ?? []);
        const allZones: MapZone[] = data.live_zones || [];
        setProjectedZones(allZones.filter((z: MapZone) => z.risk_level === 'projected_spread'));
        setHistoricalPolygon(data.historical_polygon ?? []);
        if (data.wind_data) setWindData(data.wind_data);
      } catch (err) {
        console.error('Map load failed:', err);
      } finally {
        setLoading(false);
      }
    };
    
    // Slight debounce so dragging sliders doesn't spam API
    const timeoutId = setTimeout(() => {
      load();
    }, 500);
    return () => clearTimeout(timeoutId);
  }, [mapCenter[0], mapCenter[1], radius]);

  const handleLocateMe = () => {
    if ('geolocation' in navigator) {
      setLoading(true);
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const coords: [number, number] = [pos.coords.latitude, pos.coords.longitude];
          setMapCenter(coords);
          setUserLoc(coords);
          setLoading(false);
        },
        (err) => {
          console.error("Geolocation error:", err);
          alert("Could not fetch location. Please ensure location services are enabled.");
          setLoading(false);
        },
        { timeout: 10000 }
      );
    } else {
      alert("Geolocation is not supported by your browser");
    }
  };

  const getZoneCenter = useCallback((zone: MapZone): [number, number] => {
    // Check traditional centroid first
    if (zone.centroid) {
      const parsed = parseWktPoint(zone.centroid);
      if (parsed) return parsed;
    }
    // Handle the case where center_lat contains the WKT string
    if (typeof zone.center_lat === 'string') {
        const parsedLat = parseWktPoint(zone.center_lat);
        if (parsedLat) return parsedLat;
    }
    // Fallback to raw numeric coords
    return [(Number(zone.center_lat) || 13.5), zone.center_lon ?? 75.5];
  }, []);

  const showPins = zoom < 13;

  return (
    <div className="page-full" style={{ position: 'relative' }}>
      {loading && (
        <div style={{ position: 'absolute', top: 60, left: 0, right: 0, zIndex: 1000, textAlign: 'center' }}>
          <div style={{ display: 'inline-block', background: '#fff', color: '#166534', padding: '6px 16px', borderRadius: 20, boxShadow: '0 2px 10px rgba(0,0,0,0.1)', fontWeight: 'bold' }}>
            Updating Map Data...
          </div>
        </div>
      )}
      
      {/* UI Controls: Radius Slider & Locate Me */}
      <div style={{
        position: 'absolute',
        top: 80,
        right: 20,
        zIndex: 1000,
        background: 'rgba(255, 255, 255, 0.95)',
        padding: '12px',
        borderRadius: '12px',
        boxShadow: '0 4px 15px rgba(0,0,0,0.1)',
        width: '200px',
        border: '1px solid #e2e8f0',
        color: '#1e293b'
      }}>
        <div style={{ fontWeight: 600, marginBottom: 8, fontSize: '0.9rem' }}>Radius: {radius} km</div>
        <input 
          type="range" 
          min="2" 
          max="500" 
          value={radius} 
          onChange={(e) => setRadius(parseInt(e.target.value))}
          style={{ width: '100%', accentColor: '#166534' }}
        />
        
        <button 
          onClick={handleLocateMe}
          style={{
            marginTop: 12,
            width: '100%',
            background: '#166534',
            color: 'white',
            border: 'none',
            padding: '8px',
            borderRadius: '6px',
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px'
          }}
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg> Locate Me
        </button>
      </div>
      {/* SVG Definitions for Map Patterns */}
      <svg width="0" height="0" style={{ position: 'absolute' }}>
        <defs>
          <pattern id="stripes" patternUnits="userSpaceOnUse" width="12" height="12" patternTransform="rotate(45)">
            <line x1="0" y="0" x2="0" y2="12" stroke="#DC2626" strokeWidth="3" opacity="0.4" />
          </pattern>
          <pattern id="dots" patternUnits="userSpaceOnUse" width="10" height="10">
            <circle cx="2" cy="2" r="2" fill="#EAB308" opacity="0.3" />
          </pattern>
        </defs>
      </svg>
      <PageHeader title={t('map.title')} showBack />

      {/* Analysis Panel */}
      <div className="analysis-panel">
        <div className="analysis-title">Region Analysis</div>
        <div className="analysis-row">
          <span className="analysis-label">Taluk Clusters</span>
          <span className="analysis-value">{talukZones.length}</span>
        </div>
        <div className="analysis-row">
          <span className="analysis-label">High Risk</span>
          <span className="analysis-value" style={{ color: '#EF4444' }}>{talukZones.filter(z => z.severity === 'high_risk').length}</span>
        </div>
        <div className="analysis-row">
          <span className="analysis-label">Moderate Risk</span>
          <span className="analysis-value" style={{ color: '#F97316' }}>{talukZones.filter(z => z.severity === 'moderate_risk').length}</span>
        </div>
        <div className="analysis-row">
          <span className="analysis-label">Village Data Points</span>
          <span className="analysis-value">{villagePins.length}</span>
        </div>
        {windData && (
          <div className="analysis-row" style={{ marginTop: 6, paddingTop: 6, borderTop: '1px solid rgba(255,255,255,0.1)' }}>
            <span className="analysis-label">Wind Vector</span>
            <span className="analysis-value" style={{ color: '#FCD34D' }}>
              {windData.speed} km/h • {windData.deg}°
            </span>
          </div>
        )}
      </div>

      {/* Legend */}
      <div style={{
        position: 'absolute', top: 68, right: 12, zIndex: 1001,
        background: 'rgba(13,59,30,0.92)', backdropFilter: 'blur(12px)',
        border: '1px solid rgba(255,255,255,0.12)', borderRadius: 10,
        padding: '10px 14px', fontSize: '0.75rem', color: 'rgba(255,255,255,0.8)',
      }}>
        <div style={{ fontWeight: 700, marginBottom: 6, fontSize: '0.78rem', color: '#fff' }}>{t('map.legend_title')}</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
          <LegendItem color="#EF4444" label={t('map.koleroga')} />
          <LegendItem color="#EAB308" label={t('map.yellow_leaf')} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 12, height: 12, borderRadius: '50%', background: 'rgba(239,68,68,0.35)', border: '2px solid #EF4444', flexShrink: 0 }} />
            High Risk (2 km)
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 12, height: 12, background: 'rgba(249,115,22,0.2)', border: '2px solid #F97316', flexShrink: 0 }} />
            Moderate Risk (Square)
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 12, height: 12, borderRadius: '50%', background: 'rgba(234,179,8,0.1)', border: '2px dashed #EAB308', flexShrink: 0 }} />
            Least Affected (4 km)
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 12, height: 12, border: '2px dashed rgba(234,179,8,0.5)', background: 'rgba(234,179,8,0.05)', flexShrink: 0 }} />
            Historical Background Risk
          </div>
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div style={{ position: 'absolute', inset: 0, zIndex: 1002, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: 'rgba(13,59,30,0.95)' }}>
          <div className="spinner" />
          <p style={{ color: '#fff', marginTop: 12, fontSize: '0.9rem' }}>Loading map data...</p>
        </div>
      )}

      <div className="map-wrap">
        <MapContainer center={mapCenter} zoom={8} style={{ width: '100vw', height: 'calc(100vh - 140px)' }} zoomControl={false}>
          <TileLayer
            attribution='&copy; <a href="https://openstreetmap.org/copyright">OSM</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <MapResizer />
          <ZoomWatcher onZoomChange={setZoom} />

          {/* Historical Boundary */}
          {historicalPolygon.length > 2 && (
            <Polygon 
              positions={historicalPolygon}
              pathOptions={{
                color: 'rgba(234,179,8,0.5)',
                weight: 2,
                dashArray: '5, 5',
                className: 'pattern-dots'
              }}
            >
              <Tooltip sticky>
                <strong>Historical Yellow Leaf Outbreak Zone</strong>
                <br />
                <span style={{ fontSize: '0.8rem', opacity: 0.8 }}>Based on past dataset records</span>
              </Tooltip>
            </Polygon>
          )}

          {/* Taluk-Level Concentric Zones from CSV */}
          {talukZones.map((tz) => {
            const c: [number, number] = [tz.center_lat, tz.center_lon];
            const colorInner = tz.severity === 'high_risk' ? '#DC2626' : tz.severity === 'moderate_risk' ? '#F97316' : '#EAB308';
            const colorOuter = tz.severity === 'high_risk' ? '#EF4444' : tz.severity === 'moderate_risk' ? '#FB923C' : '#FDE047';
            return (
              <>
                {/* Outer circle — least affected (yellow dashed) */}
                <Circle
                  key={`outer-${tz.id}`}
                  center={c}
                  radius={tz.outer_radius_km * 1000}
                  pathOptions={{ color: '#EAB308', fillColor: '#FDE047', fillOpacity: 0.06, weight: 2, dashArray: '10 6' }}
                >
                  <Popup>
                    <strong style={{ color: '#CA8A04' }}>🟡 Least Affected — {tz.taluk}</strong><br />
                    District: {tz.district}<br />
                    Outer {tz.outer_radius_km} km boundary — stay alert.
                  </Popup>
                </Circle>
                {/* Middle square — moderate (orange) */}
                <Circle
                  key={`mid-${tz.id}`}
                  center={c}
                  radius={tz.square_half_km * 1000}
                  pathOptions={{ color: '#F97316', fillColor: '#FB923C', fillOpacity: 0.15, weight: 2.5 }}
                >
                  <Popup>
                    <strong style={{ color: '#F97316' }}>🟠 Moderate Risk — {tz.taluk}</strong><br />
                    District: {tz.district}<br />
                    Avg Incidence: {tz.avg_incidence}% | Intensity: {tz.avg_intensity}%<br />
                    {tz.affected_villages}/{tz.total_villages} villages affected.
                  </Popup>
                </Circle>
                {/* Inner circle — high risk (red solid) */}
                <Circle
                  key={`inner-${tz.id}`}
                  center={c}
                  radius={tz.inner_radius_km * 1000}
                  pathOptions={{ color: colorInner, fillColor: colorOuter, fillOpacity: 0.3, weight: 3 }}
                >
                  <Popup>
                    <strong style={{ color: colorInner }}>🔴 Core Risk — {tz.taluk}</strong><br />
                    District: {tz.district}<br />
                    Classification: {tz.severity.replace('_', ' ')}<br />
                    Max Incidence: {tz.max_incidence}%<br />
                    Avg: {tz.avg_incidence}% incidence, {tz.avg_intensity}% intensity
                  </Popup>
                </Circle>
              </>
            );
          })}

          {/* Village-level pins from CSV dataset */}
          {zoom >= 9 && villagePins.filter(v => v.incidence > 0).map((vp) => (
            <CircleMarker
              key={vp.id}
              center={[vp.latitude, vp.longitude]}
              radius={Math.min(4 + vp.incidence / 5, 12)}
              pathOptions={{ color: vp.color, fillColor: vp.color, fillOpacity: 0.7, weight: 1 }}
            >
              <Popup>
                <strong>{vp.village}</strong><br />
                Taluk: {vp.taluk} | District: {vp.district}<br />
                Incidence: {vp.incidence}% | Intensity: {vp.intensity}%<br />
                Severity: <span style={{ color: vp.color, fontWeight: 700 }}>{vp.severity.toUpperCase()}</span>
              </Popup>
            </CircleMarker>
          ))}

          {/* Layer 3: Projected Spread — directional stripe patterned */}
          {projectedZones.map((zone) => {
            const c = getZoneCenter(zone);
            const polyPoints = zone.boundary ? parseWktPolygon(zone.boundary) : null;
            
            if (polyPoints) {
              return (
                <Polygon
                  key={`p-${zone.id}`}
                  positions={polyPoints}
                  pathOptions={{ color: '#DC2626', weight: 2, dashArray: '8 6', className: 'pattern-stripes' }}
                >
                  <Popup>
                    <strong style={{ color: '#DC2626' }}>💨 Projected Wind Spread</strong><br />
                    {t(`diseases.${zone.disease}`, zone.disease)}<br />
                    High risk of directional expansion due to active wind vectors extending the transmission range.
                  </Popup>
                </Polygon>
              );
            }

            // Fallback backward compat
            return (
              <Circle
                key={`p-${zone.id}`}
                center={c}
                radius={(zone.radius_km || 25) * 1000}
                pathOptions={{ color: '#DC2626', fillColor: 'transparent', fillOpacity: 0.0, weight: 2, dashArray: '10 6' }}
              >
                <Popup>
                  <strong style={{ color: '#DC2626' }}>💨 Projected Spread</strong><br />
                  {t(`diseases.${zone.disease}`, zone.disease)}<br />
                </Popup>
              </Circle>
            );
          })}

          {/* Disease Pins inside a Cluster */}
          {showPins && (
            <MarkerClusterGroup 
              chunkedLoading 
              maxClusterRadius={40}
              spiderfyOnMaxZoom={true}
              polygonOptions={{
                fillColor: 'rgba(13, 59, 30, 0.2)',
                color: '#0D3B1E',
                weight: 1,
                opacity: 0.6
              }}
            >
              {pins.map((pin) => (
                <CircleMarker
                  key={pin.id}
                  center={[pin.latitude, pin.longitude]}
                  radius={7}
                  pathOptions={{
                    color: pin.color === 'red' ? '#DC2626' : '#CA8A04',
                    fillColor: pin.color === 'red' ? '#EF4444' : '#EAB308',
                    fillOpacity: 0.85, weight: 2,
                  }}
                >
                  <Popup>
                    <strong>{t(`diseases.${pin.disease}`, pin.disease)}</strong><br />
                    {t('result.confidence', 'Confidence')}: {(pin.confidence * 100).toFixed(0)}%<br />
                    {t('result.severity', 'Severity')}: {pin.severity ?? '—'}
                  </Popup>
                </CircleMarker>
              ))}
            </MarkerClusterGroup>
          )}
        </MapContainer>
      </div>
    </div>
  );
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{ width: 10, height: 10, borderRadius: '50%', background: color, flexShrink: 0 }} />
      {label}
    </div>
  );
}
