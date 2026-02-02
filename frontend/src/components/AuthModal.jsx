import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X, Phone, AlertCircle } from 'lucide-react';
import authService from '../services/authService';

export default function AuthModal({ isOpen, onClose, onSuccess }) {
  const [isLogin, setIsLogin] = useState(true);
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [errors, setErrors] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const [codeSent, setCodeSent] = useState(false);
  const [countdown, setCountdown] = useState(0);

  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [countdown]);

  if (!isOpen) return null;

  const validateForm = () => {
    const newErrors = {};
    if (!phone) {
      newErrors.phone = '请输入手机号';
    } else if (!/^1[3-9]\d{9}$/.test(phone)) {
      newErrors.phone = '请输入正确的手机号';
    }
    if (!code) {
      newErrors.code = '请输入验证码';
    } else if (!/^\d{4,6}$/.test(code)) {
      newErrors.code = '验证码应为4-6位数字';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateForm()) return;
    setIsLoading(true);
    try {
      const result = isLogin 
        ? await authService.login(phone, code)
        : await authService.register(phone, code);
      onSuccess && onSuccess(result.user);
      onClose();
    } catch (error) {
      setErrors({ submit: error.message });
    } finally {
      setIsLoading(false);
    }
  };

  const sendCode = async () => {
    if (!phone || !/^1[3-9]\d{9}$/.test(phone)) {
      setErrors({ phone: '请输入正确的手机号' });
      return;
    }
    setIsLoading(true);
    try {
      await authService.sendCode(phone);
      setCodeSent(true);
      setCountdown(60);
      setErrors({});
    } catch (error) {
      setErrors({ phone: error.message });
    } finally {
      setIsLoading(false);
    }
  };

  const modalContent = (
    <div 
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        zIndex: 99999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(0, 0, 0, 0.6)',
        backdropFilter: 'blur(4px)'
      }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div 
        style={{
          backgroundColor: 'white',
          borderRadius: '12px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
          width: '400px',
          maxWidth: '90vw',
          padding: '32px'
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
          <h2 style={{ fontSize: '24px', fontWeight: 'bold', color: '#1a1a1a' }}>
            {isLogin ? '登录' : '注册'}
          </h2>
          <button onClick={onClose} style={{ color: '#999', cursor: 'pointer', background: 'none', border: 'none' }}>
            <X size={24} />
          </button>
        </div>

        {errors.submit && (
          <div style={{ padding: '12px', backgroundColor: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px', color: '#dc2626', fontSize: '14px', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertCircle size={16} />
            <span>{errors.submit}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '8px' }}>
              手机号
            </label>
            <div style={{ position: 'relative' }}>
              <Phone size={20} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#9ca3af' }} />
              <input
                type="tel"
                value={phone}
                onChange={(e) => { setPhone(e.target.value); setErrors(prev => ({...prev, phone: ''})); }}
                placeholder="请输入手机号"
                style={{
                  width: '100%',
                  padding: '14px 14px 14px 44px',
                  border: `1px solid ${errors.phone ? '#f87171' : '#d1d5db'}`,
                  borderRadius: '8px',
                  fontSize: '16px',
                  outline: 'none',
                  boxSizing: 'border-box'
                }}
              />
            </div>
            {errors.phone && <p style={{ color: '#ef4444', fontSize: '12px', marginTop: '4px' }}>{errors.phone}</p>}
          </div>

          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '8px' }}>
              验证码
            </label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input
                type="text"
                value={code}
                onChange={(e) => { setCode(e.target.value); setErrors(prev => ({...prev, code: ''})); }}
                placeholder="请输入验证码"
                maxLength={6}
                style={{
                  flex: 1,
                  padding: '14px',
                  border: `1px solid ${errors.code ? '#f87171' : '#d1d5db'}`,
                  borderRadius: '8px',
                  fontSize: '16px',
                  outline: 'none',
                  boxSizing: 'border-box'
                }}
              />
              <button
                type="button"
                onClick={sendCode}
                disabled={countdown > 0 || isLoading}
                style={{
                  padding: '14px 16px',
                  borderRadius: '8px',
                  fontSize: '14px',
                  fontWeight: '500',
                  border: 'none',
                  cursor: countdown > 0 || isLoading ? 'not-allowed' : 'pointer',
                  backgroundColor: countdown > 0 || isLoading ? '#d1d5db' : '#D4B07B',
                  color: countdown > 0 || isLoading ? '#6b7280' : 'white',
                  whiteSpace: 'nowrap'
                }}
              >
                {countdown > 0 ? `${countdown}s` : (codeSent ? '重新获取' : '获取验证码')}
              </button>
            </div>
            {errors.code && <p style={{ color: '#ef4444', fontSize: '12px', marginTop: '4px' }}>{errors.code}</p>}
          </div>

          <button
            type="submit"
            disabled={isLoading}
            style={{
              width: '100%',
              padding: '14px',
              borderRadius: '8px',
              fontSize: '16px',
              fontWeight: '500',
              border: 'none',
              cursor: isLoading ? 'not-allowed' : 'pointer',
              backgroundColor: '#D4B07B',
              color: 'white',
              opacity: isLoading ? 0.7 : 1
            }}
          >
            {isLoading ? '处理中...' : (isLogin ? '登录' : '注册')}
          </button>
        </form>

        <div style={{ marginTop: '20px', textAlign: 'center', fontSize: '14px', color: '#6b7280' }}>
          {isLogin ? '还没有账号？' : '已有账号？'}
          <button
            onClick={() => setIsLogin(!isLogin)}
            style={{ color: '#D4B07B', fontWeight: '500', marginLeft: '4px', background: 'none', border: 'none', cursor: 'pointer' }}
          >
            {isLogin ? '立即注册' : '立即登录'}
          </button>
        </div>
      </div>
    </div>
  );

  return createPortal(modalContent, document.body);
}
