import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

interface PageHeaderProps {
  title: string;
  showBack?: boolean;
}

export default function PageHeader({ title, showBack = false }: PageHeaderProps) {
  const navigate = useNavigate();
  const { i18n } = useTranslation();

  const currentLang = i18n.language;
  const toggleLang = () => {
    i18n.changeLanguage(currentLang === 'en' ? 'kn' : 'en');
  };

  return (
    <header className="top-header">
      <div className="top-header-left">
        {showBack && (
          <button className="back-btn" onClick={() => navigate(-1)} aria-label="Go back">
            ←
          </button>
        )}
        <span className="top-header-title">{title}</span>
      </div>
      <button className="lang-toggle-btn" onClick={toggleLang} aria-label="Toggle language">
        <span className="lang-icon">🌐</span>
        {currentLang === 'en' ? 'ಕನ್ನಡ' : 'EN'}
      </button>
    </header>
  );
}
