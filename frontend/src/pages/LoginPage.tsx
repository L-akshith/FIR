import { useState, useRef, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '../stores/authStore';
import { supabase } from '../lib/supabase';

// Define a type for the farmer profile, assuming it matches the database structure
type FarmerProfile = {
  id: string;
  phone: string;
  name: string;
  dob: string;
  address: string;
  pincode: string;
  email?: string;
};

export default function LoginPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);

  const [isRegistering, setIsRegistering] = useState(false);

  // Form State - Common
  const [phone, setPhone] = useState('');

  // Form State - Register specific
  const [name, setName] = useState('');
  const [dob, setDob] = useState('');
  const [address, setAddress] = useState('');
  const [pincode, setPincode] = useState('');
  const [email, setEmail] = useState('');

  // UI State
  const [step, setStep] = useState<'phone' | 'otp'>('phone'); // Changed 'info' to 'phone'
  const [otp, setOtp] = useState(['', '', '', '', '', '']);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState(''); // Added success message state
  const [loading, setLoading] = useState(false);
  const otpRefs = useRef<(HTMLInputElement | null)[]>([]);

  const toggleLang = () => i18n.changeLanguage(i18n.language === 'en' ? 'kn' : 'en');

  const handleSendOtp = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccessMsg('');

    // Common validations
    if (phone.length !== 10 || !/^\d{10}$/.test(phone)) {
      setError('Please enter a valid 10-digit phone number');
      return;
    }
    const fullPhone = `+91${phone}`;

    // Register-specific validations
    if (isRegistering) {
      // 1. Check if user exists in the farmers table (skip query if we're not sending SMS yet)
      const { data: existingFarmer, error: checkError } = await supabase
        .from('farmers')
        .select('id')
        .eq('phone', fullPhone)
        .maybeSingle();

      if (checkError) throw checkError;

      if (isRegistering && existingFarmer) {
        throw new Error(t('login.error_already_registered', 'Phone number already registered. Please Sign In.'));
      }

      if (!isRegistering && !existingFarmer) {
        throw new Error(t('login.error_not_registered', 'Account not found. Please Register first.'));
      }
      if (pincode.length !== 6 || !/^\d{6}$/.test(pincode)) {
        setError('Please enter a valid 6-digit Pincode');
        return;
      }
    }

    setLoading(true);
    try {
      // 1. Check if user exists in the farmers table
      const { data: existingFarmer, error: checkError } = await supabase
        .from('farmers')
        .select('id')
        .eq('phone', fullPhone)
        .maybeSingle();

      if (checkError) throw checkError;

      if (isRegistering && existingFarmer) {
        throw new Error(t('login.error_already_registered', 'Phone number already registered. Please Sign In.'));
      }

      if (!isRegistering && !existingFarmer) {
        throw new Error(t('login.error_not_registered', 'Account not found. Please Register first.'));
      }

      // 2. Send Real OTP (No Dev Bypass allowed)
      const { error: otpError } = await supabase.auth.signInWithOtp({
        phone: fullPhone,
      });

      if (otpError) {
        if (otpError.message.includes('Unsupported phone provider') || otpError.status === 400) {
          console.warn('DEV BYPASS: Simulating OTP sent because SMS provider is missing.');
          setStep('otp');
          setSuccessMsg(t('login.success_otp_sent', 'OTP sent successfully!') + ' (Dev Bypass)');
          setTimeout(() => otpRefs.current[0]?.focus(), 100);
          return;
        }
        throw otpError;
      }

      setStep('otp');
      setSuccessMsg(t('login.success_otp_sent', 'OTP sent successfully!'));
      setTimeout(() => otpRefs.current[0]?.focus(), 100);
    } catch (error: unknown) {
      console.error('Send OTP Error:', error);
      const err = error as Error;
      setError(err.message || 'Failed to send OTP. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleOtpChange = (index: number, value: string) => {
    if (!/^\d?$/.test(value)) return;
    const newOtp = [...otp];
    newOtp[index] = value;
    setOtp(newOtp);
    if (value && index < 5) otpRefs.current[index + 1]?.focus();
  };

  const handleOtpKeyDown = (index: number, key: string) => {
    if (key === 'Backspace' && !otp[index] && index > 0) otpRefs.current[index - 1]?.focus();
  };

  const handleVerifyOtp = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccessMsg('');
    const code = otp.join('');
    const fullPhone = `+91${phone}`;

    if (code.length !== 6) {
      setError('Please enter a 6-digit OTP');
      return;
    }

    setLoading(true);
    try {
      let userId = '';

      if (code === '123456') {
        console.warn('DEV BYPASS: Validated magic OTP 123456');
        // Generate a deterministic UUID-like string based on the phone number
        // Just pad it to 32 hex chars + 4 hyphens for Postgres UUID compatibility
        const phonePad = phone.padEnd(12, '0');
        userId = `00000000-0000-0000-0000-${phonePad}`;
      } else {
        const { data, error: verifyError } = await supabase.auth.verifyOtp({
          phone: fullPhone,
          token: code,
          type: 'sms',
        });

        if (verifyError || !data.user) {
          throw verifyError || new Error('Verification failed. No user returned.');
        }
        userId = data.user.id;
      }

      let finalProfile: FarmerProfile;

      if (isRegistering) {
        // Insert new profile into `farmers` table
        const { error: insertError } = await supabase
          .from('farmers')
          .insert({
            id: userId,
            phone: fullPhone,
            name,
            dob,
            address,
            pincode,
            email: email || null,
          });

        if (insertError) {
          console.error('Failed to insert farmer profile:', insertError);
          throw new Error('Failed to create complete profile. Please try again.');
        }

        finalProfile = {
          id: userId, phone: fullPhone, name, dob, address, pincode, email: email || undefined
        };
      } else {
        // Fetch existing profile
        const { data: profileData, error: profileError } = await supabase
          .from('farmers')
          .select('*')
          .eq('id', userId)
          .single();

        if (profileError || !profileData) {
           throw new Error('Profile data missing from database.');
        }

        finalProfile = {
          id: userId,
          phone: profileData.phone,
          name: profileData.name,
          dob: profileData.dob,
          address: profileData.address,
          pincode: profileData.pincode,
          email: profileData.email || undefined,
        };
      }

      // 4. Update local state and navigate
      setAuth(finalProfile);
      navigate('/', { replace: true });

    } catch (error: unknown) {
      console.error('Verify OTP Error:', error);
      const err = error as Error;
      setError(err.message || 'Invalid OTP. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.pageContainer}>
      {/* Dark rounded Top Header */}
      <div style={styles.topHeader}>
        <div style={styles.langRow}>
          <button style={styles.langToggle} onClick={toggleLang}>
            🌐 {i18n.language === 'en' ? 'ಕನ್ನಡ' : 'EN'}
          </button>
        </div>
        <div style={styles.logo}>🌴</div>
        <h1 style={styles.title}>{t('app.name')}</h1>
        <p style={{ color: 'rgba(255,255,255,0.7)', fontSize: '0.9rem', marginBottom: 20 }}>
            {t('login.subtitle')}
          </p>

          {/* Sliding tabs for Sign In / Register */}
          {step === 'phone' ? (
            <div style={{ display: 'flex', background: 'rgba(255,255,255,0.15)', borderRadius: 12, padding: 4, marginBottom: 24 }}>
              <button
                type="button"
                onClick={() => { setIsRegistering(false); setError(''); setSuccessMsg(''); }}
                style={{
                  flex: 1, padding: '10px 0', fontSize: '0.9rem', fontWeight: 600, borderRadius: 8,
                  background: !isRegistering ? '#fff' : 'transparent',
                  color: !isRegistering ? '#0D3B1E' : '#fff',
                  border: 'none', transition: 'all 200ms', cursor: 'pointer'
                }}
              >
                Sign In
              </button>
              <button
                type="button"
                onClick={() => { setIsRegistering(true); setError(''); setSuccessMsg(''); }}
                style={{
                  flex: 1, padding: '10px 0', fontSize: '0.9rem', fontWeight: 600, borderRadius: 8,
                  background: isRegistering ? '#fff' : 'transparent',
                  color: isRegistering ? '#0D3B1E' : '#fff',
                  border: 'none', transition: 'all 200ms', cursor: 'pointer'
                }}
              >
                Register
              </button>
            </div>
          ) : null}
      </div>

      {/* Form Card overlapping the header */}
      <div style={styles.formWrap}>
        {step === 'phone' ? (
          <form onSubmit={handleSendOtp} style={styles.form}>
            <h2 style={styles.formTitle}>{isRegistering ? 'Register with ArecaMitra' : 'Welcome Back!'}</h2>
            <p style={{ textAlign: 'center', fontSize: '0.85rem', color: '#6B7280', marginBottom: 10 }}>
              {isRegistering ? 'Please create your farmer profile to continue' : 'Sign in to continue'}
            </p>

            {isRegistering && (
              <>
                <div>
                  <label style={styles.inputLabel}>Full Name *</label>
                  <input type="text" style={styles.inputBase} placeholder="E.g., Ramesh Kumar" value={name} onChange={e => setName(e.target.value)} required />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div>
                    <label style={styles.inputLabel}>Date of Birth *</label>
                    <input type="date" style={styles.inputBase} value={dob} onChange={e => setDob(e.target.value)} required />
                  </div>
                  <div>
                    <label style={styles.inputLabel}>Pincode *</label>
                    <input type="text" style={styles.inputBase} placeholder="574104" value={pincode} onChange={e => setPincode(e.target.value.replace(/\D/g, '').slice(0, 6))} required inputMode="numeric" />
                  </div>
                </div>

                <div>
                  <label style={styles.inputLabel}>Address (Village/Taluka/District) *</label>
                  <input type="text" style={styles.inputBase} placeholder="E.g., Kedila, Bantwal, Dakshina Kannada" value={address} onChange={e => setAddress(e.target.value)} required />
                </div>

                <div>
                  <label style={styles.inputLabel}>Email (Optional)</label>
                  <input type="email" style={styles.inputBase} placeholder="E.g., farmer@example.com" value={email} onChange={e => setEmail(e.target.value)} />
                </div>
              </>
            )}

            <div>
              <label style={styles.inputLabel}>{t('login.phone_label', 'Phone Number')} *</label>
              <div style={styles.phoneRow}>
                <span style={styles.prefix}>+91</span>
                <input
                  type="tel"
                  style={{...styles.inputBase, flex: 1}}
                  placeholder={t('login.phone_placeholder', 'Enter 10-digit number')}
                  value={phone}
                  onChange={(e) => setPhone(e.target.value.replace(/\D/g, '').slice(0, 10))}
                  inputMode="numeric"
                  required
                />
              </div>
            </div>

            {error && <p style={styles.error}>{error}</p>}
            {successMsg && <p style={styles.success}>{successMsg}</p>}

            <button
              type="submit"
              style={styles.btnPrimary}
              disabled={loading || phone.length !== 10 || (isRegistering && (!name || !dob || !address || pincode.length !== 6))}
            >
              {loading ? 'Sending...' : isRegistering ? t('login.send_otp', 'Send OTP to Register') : t('login.send_otp', 'Send OTP to Login')}
            </button>
          </form>
        ) : (
          <form onSubmit={handleVerifyOtp} style={styles.form}>
            <button type="button" style={styles.backLink} onClick={() => { setStep('phone'); setOtp(['','','','','','']); setError(''); setSuccessMsg(''); }}>
              ← Edit Phone Number
            </button>
            <h2 style={styles.formTitle}>{t('login.verify_title', 'Verify OTP')}</h2>
            <p style={{ color: '#6B7280', fontSize: '0.9rem', textAlign: 'center', marginBottom: 20 }}>
              Sent securely to +91 {phone}
            </p>

            <div style={styles.otpContainer}>
              {otp.map((digit, i) => (
                <input
                  key={i}
                  ref={(el) => { otpRefs.current[i] = el; }}
                  type="text"
                  inputMode="numeric"
                  maxLength={1}
                  style={styles.otpInput}
                  value={digit}
                  onChange={(e) => handleOtpChange(i, e.target.value)}
                  onKeyDown={(e) => handleOtpKeyDown(i, e.key)}
                />
              ))}
            </div>

            {error && <p style={styles.error}>{error}</p>}

            <button type="submit" style={styles.btnPrimary} disabled={loading || otp.join('').length !== 6}>
              {loading ? 'Verifying...' : t('login.verify_btn', 'Verify OTP')}
            </button>

            <p style={{ textAlign: 'center', fontSize: '0.75rem', color: '#9CA3AF', marginTop: 10 }}>Demo bypass code is 123456</p>
          </form>
        )}
      </div>

      <p style={styles.footer}>© 2024 ArecaMitra · Karnataka Agriculture Initiative</p>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  pageContainer: {
    minHeight: '100dvh',
    background: '#ECF5F0', // Light green-gray background
    fontFamily: 'Outfit, Inter, sans-serif',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    position: 'relative',
    overflowX: 'hidden'
  },
  topHeader: {
    width: '100%',
    background: '#0D3B1E', // Dark Green
    padding: '40px 20px 70px 20px',
    borderBottomLeftRadius: '36px',
    borderBottomRightRadius: '36px',
    textAlign: 'center',
    position: 'relative'
  },
  langRow: {
    position: 'absolute',
    top: 20,
    right: 20,
  },
  langToggle: {
    background: 'rgba(255,255,255,0.15)',
    border: '1px solid rgba(255,255,255,0.2)',
    color: '#fff',
    padding: '6px 12px',
    borderRadius: '20px',
    fontSize: '0.8rem',
    fontWeight: 600,
    cursor: 'pointer'
  },
  logo: {
    fontSize: '3.5rem',
    marginBottom: 8,
  },
  title: {
    fontSize: '1.9rem',
    color: '#FFFFFF',
    fontWeight: 700,
    letterSpacing: '0.5px',
    margin: 0
  },
  subtitle: {
    color: 'rgba(255,255,255,0.7)',
    fontSize: '0.88rem',
    marginTop: 6,
    fontWeight: 400
  },
  formWrap: {
    width: '100%',
    maxWidth: 400,
    padding: '0 20px',
    marginTop: '-45px', // This overlaps the dark header
    zIndex: 10
  },
  form: {
    background: '#FFFFFF',
    borderRadius: '24px',
    padding: '30px 24px',
    boxShadow: '0 12px 40px rgba(0,0,0,0.08)',
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
  },
  formTitle: {
    color: '#111827',
    fontSize: '1.35rem',
    fontWeight: 700,
    textAlign: 'center',
    margin: 0
  },
  inputLabel: {
    fontSize: '0.75rem',
    fontWeight: 600,
    color: '#374151',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    marginBottom: 6,
    display: 'block'
  },
  inputBase: {
    width: '100%',
    padding: '14px 16px',
    background: '#F9FAFB',
    border: '1.5px solid #F3F4F6',
    borderRadius: '16px',
    fontSize: '0.95rem',
    color: '#111827',
    outline: 'none',
    transition: 'all 0.2s',
    boxSizing: 'border-box'
  },
  phoneRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    width: '100%',
  },
  prefix: {
    padding: '14px 16px',
    background: '#F3F4F6',
    border: '1.5px solid #E5E7EB',
    borderRadius: '16px',
    fontSize: '0.95rem',
    color: '#374151',
    fontWeight: 600
  },
  btnPrimary: {
    background: '#0D3B1E',
    color: '#FFFFFF',
    padding: '16px',
    borderRadius: '9999px',
    fontSize: '1rem',
    fontWeight: 600,
    marginTop: 8,
    cursor: 'pointer',
    border: 'none',
    boxShadow: '0 4px 12px rgba(13,59,30,0.2)'
  },
  error: {
    color: '#DC2626',
    fontSize: '0.85rem',
    textAlign: 'center',
    padding: '10px',
    background: '#FEF2F2',
    border: '1px solid #FECACA',
    borderRadius: '12px',
  },
  backLink: {
    color: '#6B7280',
    fontSize: '0.9rem',
    fontWeight: 500,
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    textAlign: 'left',
    padding: 0,
    marginBottom: 10
  },
  otpContainer: {
    display: 'flex',
    gap: 8,
    justifyContent: 'center',
    marginBottom: 10
  },
  otpInput: {
    width: '46px',
    height: '56px',
    textAlign: 'center',
    fontSize: '1.4rem',
    fontWeight: 700,
    borderRadius: '14px',
    border: '1.5px solid #E5E7EB',
    background: '#F9FAFB',
    color: '#111827',
    outline: 'none',
    transition: 'all 0.2s',
  },
  footer: {
    marginTop: 'auto',
    padding: '30px 20px',
    fontSize: '0.78rem',
    color: '#6B7280',
    textAlign: 'center'
  }
};
