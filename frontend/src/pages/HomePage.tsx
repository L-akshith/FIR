import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '../stores/authStore';
import { useAppStore } from '../stores/appStore';
import { fetchAdvisory } from '../lib/api';
import PageHeader from '../components/PageHeader';

interface RiskData {
  status: string;
  advisory: string;
  reports_count: number;
}

export default function HomePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const profile = useAuthStore((s) => s.profile);
  const recentScans = useAppStore((s) => s.recentScans);
  const [risk, setRisk] = useState<RiskData | null>(null);
  const [loadingRisk, setLoadingRisk] = useState(true);

  useEffect(() => {
    const fetchRisk = async () => {
      try {
        let lat = 13.93, lon = 75.56;
        try {
          const pos = await new Promise<GeolocationPosition>((res, rej) => 
            navigator.geolocation.getCurrentPosition(res, rej, { timeout: 6000 })
          );
          lat = pos.coords.latitude;
          lon = pos.coords.longitude;
        } catch (e) {
          console.warn("Geolocation denied or timed out. Falling back to default coordinates.", e);
        }

        const data = await fetchAdvisory(lat, lon);
        setRisk(data);
      } catch {
        setRisk({ status: 'safe', advisory: t('home.risk_safe'), reports_count: 0 });
      } finally {
        setLoadingRisk(false);
      }
    };
    fetchRisk();
  }, [t]);

  return (
    <>
      <PageHeader title={t('app.name')} />

      <div className="page page-enter">
        {/* Greeting */}
        <div style={{ marginBottom: 20 }}>
          <h1 style={{ color: '#fff', fontSize: '1.35rem', marginBottom: 4 }}>
            {t('home.greeting')} 👋
          </h1>
          {profile && (
            <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: '0.85rem' }}>
              {profile.address} - {profile.pincode}
            </p>
          )}
        </div>

        {/* Risk Status */}
        <div className="card" style={{ padding: 18, marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <h3 style={{ fontSize: '0.88rem', color: '#374151' }}>{t('home.risk_title')}</h3>
            {loadingRisk ? (
              <div style={{ width: 60, height: 22, borderRadius: 12, background: '#F3F4F6', animation: 'pulse 1.5s infinite' }} />
            ) : (
              <span className={`badge ${risk?.status === 'severe' ? 'badge-severe' : risk?.status === 'warning' ? 'badge-moderate' : 'badge-safe'}`}>
                {risk?.status === 'safe' ? '✓ Safe' : risk?.status?.toUpperCase()}
              </span>
            )}
          </div>
          <p style={{ fontSize: '0.85rem', color: '#6B7280', lineHeight: 1.5 }}>
            {loadingRisk ? '...' : risk?.advisory}
          </p>
        </div>

        {/* Scan CTA */}
        <button onClick={() => navigate('/scan')} style={{
          display: 'flex', alignItems: 'center', gap: 14, width: '100%', padding: '18px 16px',
          background: '#16A34A', borderRadius: 12, color: '#fff', marginBottom: 20,
          textAlign: 'left', border: '1px solid rgba(255,255,255,0.15)', transition: 'all 200ms',
        }}>
          <span style={{ fontSize: '1.8rem', flexShrink: 0 }}>📷</span>
          <div style={{ flex: 1 }}>
            <strong style={{ fontSize: '0.95rem', display: 'block' }}>{t('home.scan_btn')}</strong>
            <span style={{ fontSize: '0.78rem', opacity: 0.8 }}>{t('home.scan_desc')}</span>
          </div>
          <span style={{ fontSize: '1.2rem', opacity: 0.6 }}>→</span>
        </button>

        {/* Recent Scans */}
        <h3 style={{ color: '#fff', fontSize: '0.95rem', marginBottom: 10 }}>{t('home.recent_title')}</h3>
        {recentScans.length === 0 ? (
          <div className="card-dark" style={{ padding: '28px 16px', textAlign: 'center', color: 'rgba(255,255,255,0.4)', fontSize: '0.85rem' }}>
            {t('home.no_scans')}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {recentScans.slice(0, 5).map((scan, i) => (
              <div key={i} className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{
                    width: 10, height: 10, borderRadius: '50%', flexShrink: 0,
                    background: scan.disease === 'koleroga' ? '#EF4444' : scan.disease === 'yellow_leaf' ? '#EAB308' : '#22C55E',
                  }} />
                  <span style={{ fontWeight: 500, fontSize: '0.88rem', color: '#1F2937' }}>
                    {t(`diseases.${scan.disease}`, scan.disease)}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span className={`badge ${scan.severity === 'severe' ? 'badge-severe' : scan.severity === 'moderate' ? 'badge-moderate' : scan.severity === 'mild' ? 'badge-mild' : 'badge-safe'}`}>
                    {scan.severity ? t(`severity.${scan.severity}`) : '✓'}
                  </span>
                  <span style={{ fontSize: '0.78rem', color: '#9CA3AF', fontWeight: 600 }}>
                    {(scan.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
