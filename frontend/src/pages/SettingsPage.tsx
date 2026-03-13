import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import PageHeader from '../components/PageHeader';

export default function SettingsPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { profile, logout } = useAuthStore();

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <>
      <PageHeader title={t('settings.title')} />

      <div className="page page-enter">
        {/* Profile */}
        {profile && (
          <div className="card" style={{ padding: 16, marginBottom: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <div style={{ width: 44, height: 44, borderRadius: '50%', background: '#F0FDF4', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.3rem', flexShrink: 0 }}>🌴</div>
              <div>
                <strong style={{ color: '#111827', fontSize: '0.95rem' }}>{profile.name}</strong>
                <p style={{ fontSize: '0.78rem', color: '#9CA3AF' }}>
                  {profile.phone} • {profile.address}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Language */}
        <div className="card" style={{ marginBottom: 12, overflow: 'hidden' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontWeight: 500, fontSize: '0.9rem', color: '#1F2937' }}>
              <span>🌐</span> {t('settings.language')}
            </div>
            <div style={{ display: 'flex', background: '#F3F4F6', borderRadius: 20, overflow: 'hidden', border: '1px solid #E5E7EB' }}>
              <button onClick={() => i18n.changeLanguage('en')} style={{
                padding: '7px 14px', fontSize: '0.78rem', fontWeight: 600, border: 'none', cursor: 'pointer',
                background: i18n.language === 'en' ? '#166534' : 'transparent',
                color: i18n.language === 'en' ? '#fff' : '#6B7280',
                borderRadius: 20, transition: 'all 200ms',
              }}>EN</button>
              <button onClick={() => i18n.changeLanguage('kn')} style={{
                padding: '7px 14px', fontSize: '0.78rem', fontWeight: 600, border: 'none', cursor: 'pointer',
                background: i18n.language === 'kn' ? '#166534' : 'transparent',
                color: i18n.language === 'kn' ? '#fff' : '#6B7280',
                borderRadius: 20, transition: 'all 200ms',
              }}>ಕನ್ನಡ</button>
            </div>
          </div>
        </div>

        {/* About */}
        <div className="card" style={{ marginBottom: 12, overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 10, fontWeight: 500, fontSize: '0.9rem', color: '#1F2937' }}>
            <span>ℹ️</span> {t('settings.about')}
          </div>
          <p style={{ fontSize: '0.8rem', color: '#6B7280', padding: '0 16px 12px', lineHeight: 1.6 }}>
            ArecaMitra is an AI-powered crop disease surveillance system for arecanut farmers in Karnataka, India. Built as part of the Aeriothon initiative.
          </p>
          <div style={{ padding: '10px 16px', borderTop: '1px solid #F3F4F6', display: 'flex', alignItems: 'center', gap: 10, fontSize: '0.85rem', color: '#9CA3AF' }}>
            <span>📱</span> {t('settings.version')}
          </div>
        </div>

        {/* Logout */}
        <button className="btn btn-danger btn-full" style={{ marginTop: 8 }} onClick={handleLogout}>
          {t('settings.logout')}
        </button>
      </div>
    </>
  );
}
