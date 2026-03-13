import { useRef, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAppStore } from '../stores/appStore';
import { compressImage } from '../lib/utils';
import PageHeader from '../components/PageHeader';

export default function ScanPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { setCapturedImage, setCapturedFile } = useAppStore();

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [stream, setStream] = useState<MediaStream | null>(null);
  const [cameraActive, setCameraActive] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState('');

  const startCamera = useCallback(async () => {
    try {
      setError('');
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1024 }, height: { ideal: 1024 } },
      });
      setStream(mediaStream);
      setCameraActive(true);
      if (videoRef.current) videoRef.current.srcObject = mediaStream;
    } catch {
      setError('Camera access denied. Use the upload option.');
    }
  }, []);

  const stopCamera = useCallback(() => {
    if (stream) {
      stream.getTracks().forEach((t) => t.stop());
      setStream(null);
      setCameraActive(false);
    }
  }, [stream]);

  const capturePhoto = useCallback(() => {
    if (!videoRef.current || !canvasRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(video, 0, 0);
    const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
    setPreview(dataUrl);
    canvas.toBlob(async (blob) => {
      if (!blob) return;
      const file = new File([blob], 'capture.jpg', { type: 'image/jpeg' });
      const compressed = await compressImage(file);
      setCapturedFile(compressed);
      setCapturedImage(dataUrl);
    }, 'image/jpeg', 0.85);
    stopCamera();
  }, [stopCamera, setCapturedFile, setCapturedImage]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const compressed = await compressImage(file);
    const url = URL.createObjectURL(compressed);
    setPreview(url);
    setCapturedImage(url);
    setCapturedFile(compressed);
  };

  return (
    <div className="page-full page-enter">
      <PageHeader title={t('scan.title')} showBack />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 20, paddingBottom: 80 }}>
        {!cameraActive && !preview && (
          <div style={{ textAlign: 'center', maxWidth: 320 }}>
            <div style={{ fontSize: '3.5rem', marginBottom: 12, animation: 'float 3s ease-in-out infinite' }}>🌿</div>
            <h2 style={{ color: '#fff', fontSize: '1.1rem', marginBottom: 6 }}>{t('scan.title')}</h2>
            <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: '0.83rem', marginBottom: 24 }}>{t('scan.instruction')}</p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <button className="btn btn-primary btn-full btn-lg" onClick={startCamera}>
                📷 {t('scan.capture')}
              </button>
              <button className="btn btn-secondary btn-full" onClick={() => fileInputRef.current?.click()}>
                📁 {t('scan.upload')}
              </button>
            </div>
            <input ref={fileInputRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={handleFileUpload} />
            {error && <p style={{ color: '#FCA5A5', fontSize: '0.82rem', marginTop: 16, padding: '8px 12px', background: 'rgba(239,68,68,0.1)', borderRadius: 8 }}>{error}</p>}
          </div>
        )}

        {cameraActive && (
          <div style={{ position: 'relative', width: '100%', maxWidth: 360, aspectRatio: '1', borderRadius: 14, overflow: 'hidden', border: '2px solid rgba(255,255,255,0.1)' }}>
            <video ref={videoRef} autoPlay playsInline muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            {/* Corner guides */}
            <div style={{ position: 'absolute', inset: '12%', border: '1.5px solid rgba(255,255,255,0.3)', borderRadius: 12, pointerEvents: 'none' }} />
            {/* Capture button */}
            <button onClick={capturePhoto} style={{
              position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)',
              width: 64, height: 64, borderRadius: '50%', background: 'rgba(255,255,255,0.2)',
              backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center',
              border: '3px solid white',
            }}>
              <div style={{ width: 50, height: 50, borderRadius: '50%', background: 'white' }} />
            </button>
          </div>
        )}

        {preview && (
          <div style={{ width: '100%', maxWidth: 360 }}>
            <img src={preview} alt="Captured" style={{ width: '100%', aspectRatio: '1', objectFit: 'cover', borderRadius: 14, border: '2px solid rgba(255,255,255,0.1)', marginBottom: 16 }} />
            <div style={{ display: 'flex', gap: 10 }}>
              <button className="btn btn-secondary" style={{ flex: 1 }} onClick={() => { setPreview(null); setCapturedImage(null); setCapturedFile(null); startCamera(); }}>
                ↺ {t('scan.retake')}
              </button>
              <button className="btn btn-primary btn-lg" style={{ flex: 1 }} onClick={() => navigate('/result')}>
                {t('scan.analyze')} →
              </button>
            </div>
          </div>
        )}
      </div>

      <canvas ref={canvasRef} style={{ display: 'none' }} />
    </div>
  );
}
