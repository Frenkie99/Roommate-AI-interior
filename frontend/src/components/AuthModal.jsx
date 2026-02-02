import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { X } from 'lucide-react';

export default function AuthModal({ isOpen, onClose }) {
  const navigate = useNavigate();

  if (!isOpen) return null;

  const handleTrial = () => {
    onClose();
    navigate('/playground');
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
          width: '420px',
          maxWidth: '90vw',
          padding: '40px 32px',
          textAlign: 'center'
        }}
      >
        <button 
          onClick={onClose} 
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

        <h2 style={{ 
          fontSize: '28px', 
          fontWeight: 'bold', 
          color: '#1a1a1a',
          marginBottom: '16px'
        }}>
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
