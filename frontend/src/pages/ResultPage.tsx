import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAppStore } from '../stores/appStore';
import { useAuthStore } from '../stores/authStore';
import { submitReport } from '../lib/api';
import { fuzzCoordinates } from '../lib/utils';
import PageHeader from '../components/PageHeader';

export default function ResultPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { capturedFile, capturedImage, setLastScanResult, addScan, lastScanResult, clearCapture } = useAppStore();
  const userId = useAuthStore((s) => s.profile?.id);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (lastScanResult && !capturedFile) { setLoading(false); return; }
    if (!capturedFile) { navigate('/scan', { replace: true }); return; }

    const analyze = async () => {
      try {
        setLoading(true);
        setError('');
        let lat = 13.93, lon = 75.56;
        try {
          const pos = await new Promise<GeolocationPosition>((res, rej) =>
            navigator.geolocation.getCurrentPosition(res, rej, { timeout: 5000 })
          );
          lat = pos.coords.latitude;
          lon = pos.coords.longitude;
        } catch { /* use defaults */ }

        const fuzzed = fuzzCoordinates(lat, lon);
        const result = await submitReport(capturedFile, fuzzed.lat, fuzzed.lon, 'unknown', userId ?? 'anonymous');
        const scanResult = { ...result, imageUrl: capturedImage ?? undefined, timestamp: new Date().toISOString() };
        setLastScanResult(scanResult);
        addScan(scanResult);
        clearCapture();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Analysis failed');
      } finally {
        setLoading(false);
      }
    };
    analyze();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading) {
    return (
      <div className="page-full">
        <PageHeader title={t('result.title')} showBack />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16 }}>
          <div style={{ position: 'relative', width: 100, height: 100 }}>
            <div className="spinner" style={{ position: 'absolute', inset: 0, width: 100, height: 100, borderWidth: 3 }} />
            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '2.5rem', animation: 'float 2s ease-in-out infinite' }}>🔬</div>
          </div>
          <h2 style={{ color: '#fff', fontSize: '1.1rem' }}>Analyzing...</h2>
          <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: '0.85rem' }}>Our AI is examining your image</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page-full">
        <PageHeader title={t('result.title')} showBack />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, padding: 20 }}>
          <div style={{ fontSize: '2.5rem' }}>⚠️</div>
          <h2 style={{ color: '#fff' }}>Analysis Failed</h2>
          <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: '0.85rem', textAlign: 'center' }}>{error}</p>
          <button className="btn btn-primary" onClick={() => navigate('/scan')}>Try Again</button>
        </div>
      </div>
    );
  }

  const result = lastScanResult;
  if (!result) return null;

  const isHealthy = result.disease === 'healthy';
  const diseaseKey = result.disease === 'koleroga' ? 'koleroga' : result.disease === 'yellow_leaf' ? 'yellow_leaf' : 'healthy';

  return (
    <div className="page-full">
      <PageHeader title={t('result.title')} showBack />

      <div className="page page-enter">
        {/* Result Card */}
        <div className="card" style={{ padding: 20, marginBottom: 14, borderLeft: `4px solid ${isHealthy ? '#22C55E' : '#EF4444'}` }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '2.5rem', marginBottom: 8 }}>{isHealthy ? '✅' : '⚠️'}</div>
            <h1 style={{ fontSize: '1.25rem', marginBottom: 10, color: '#111827' }}>
              {isHealthy ? t('result.healthy_title') : t(`diseases.${diseaseKey}`)}
            </h1>

            {isHealthy ? (
              <p style={{ color: '#6B7280', fontSize: '0.88rem' }}>{t('result.healthy_msg')}</p>
            ) : (
              <div style={{ display: 'flex', justifyContent: 'center', gap: 24, marginTop: 8 }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '0.68rem', color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 4 }}>{t('result.confidence')}</div>
                  <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#111827', fontFamily: 'Outfit' }}>{(result.confidence * 100).toFixed(1)}%</div>
                </div>
                <div style={{ width: 1, background: '#E5E7EB' }} />
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '0.68rem', color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 4 }}>{t('result.severity')}</div>
                  <span className={`badge ${result.severity === 'severe' ? 'badge-severe' : result.severity === 'moderate' ? 'badge-moderate' : 'badge-mild'}`}>
                    {result.severity ? t(`severity.${result.severity}`) : '—'}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Weather */}
        {result.risk_message && (
          <div className="card" style={{ padding: 16, marginBottom: 14 }}>
            <h3 style={{ fontSize: '0.9rem', color: '#374151', marginBottom: 10 }}>🌦️ {t('result.weather_title')}</h3>
            <p style={{ fontSize: '0.85rem', color: '#6B7280', lineHeight: 1.6, marginBottom: 14 }}>{result.risk_message}</p>
            {result.weather && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                {[
                  { icon: '🌡️', val: `${result.weather.temperature}°C` },
                  { icon: '💧', val: `${result.weather.humidity}%` },
                  { icon: '🌧️', val: `${result.weather.rainfall_total}mm` },
                  { icon: '💨', val: `${result.weather.wind_speed} m/s` },
                ].map((w, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', background: '#F9FAFB', borderRadius: 8, fontSize: '0.85rem', fontWeight: 500, color: '#374151' }}>
                    <span>{w.icon}</span> {w.val}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Treatment */}
        {!isHealthy && (
          <div className="card" style={{ padding: 16, marginBottom: 14 }}>
            <h3 style={{ fontSize: '0.9rem', color: '#374151', marginBottom: 10 }}>💊 {t('result.treatment_title')}</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {t(`treatments.${diseaseKey}`).split('\n').map((step: string, i: number) => (
                <div key={i} style={{ padding: '10px 12px', background: '#F0FDF4', borderRadius: 8, borderLeft: '3px solid #22C55E', fontSize: '0.84rem', color: '#374151', lineHeight: 1.5 }}>{step}</div>
              ))}
            </div>
          </div>
        )}

        <button className="btn btn-primary btn-full btn-lg" onClick={() => { setLastScanResult(null); navigate('/scan'); }} style={{ marginTop: 4 }}>
          📷 {t('result.scan_again')}
        </button>
      </div>
    </div>
  );
}
