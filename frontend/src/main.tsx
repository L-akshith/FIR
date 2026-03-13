import { createRoot } from 'react-dom/client'
import 'leaflet/dist/leaflet.css'
import './i18n/config'
import './index.css'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <App />
)
