import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { useEffect, useRef } from 'react';
import { X } from 'lucide-react';

export default function AuthModal({ isOpen, onClose }) {
  const navigate = useNavigate();
  const dialogRef = useRef(null);

  // Escape 键关闭 + body scroll lock + 焦点移入
  useEffect(() => {
    if (!isOpen) return;

    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
    };

    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    dialogRef.current?.focus();

    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleTrial = () => {
    onClose();
    navigate('/playground');
  };

  const modalContent = (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby="auth-modal-title"
      tabIndex={-1}
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
          position: 'relative',
          backgroundColor: 'white',
          borderRadius: '12px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
          width: '420px',
          maxWidth: '90vw',
          padding: '40px 32px',
          textAlign: 'center'
        }}
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="关闭"
          style={{
            position: 'absolute',
            top: '16px',
            right: '16px',
            color: '#999',
            cursor: 'pointer',
            background: 'none',
            border: 'none'
          }}
        >
          <X size={24} />
        </button>

        <h2
          id="auth-modal-title"
          style={{
            fontSize: '28px',
            fontWeight: 'bold',
            color: '#1a1a1a',
            marginBottom: '16px'
          }}
        >
          欢迎试用 Roommate
        </h2>

        <p style={{
          fontSize: '16px',
          color: '#6b7280',
          marginBottom: '32px',
          lineHeight: '1.6'
        }}>
          即刻上传毛坯图，体验 AI 室内设计黑科技
        </p>

        <button
          type="button"
          onClick={handleTrial}
          style={{
            width: '100%',
            padding: '16px',
            borderRadius: '8px',
            fontSize: '18px',
            fontWeight: '600',
            border: 'none',
            cursor: 'pointer',
            backgroundColor: '#D4B07B',
            color: 'white',
            transition: 'all 0.2s'
          }}
          onMouseOver={(e) => e.target.style.backgroundColor = '#C9A56C'}
          onMouseOut={(e) => e.target.style.backgroundColor = '#D4B07B'}
        >
          限时免费试用
        </button>
      </div>
    </div>
  );

  return createPortal(modalContent, document.body);
}
