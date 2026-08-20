import { createPortal } from 'react-dom';
import { useEffect, useRef, useState } from 'react';
import { X } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function AuthModal({ isOpen, onClose }) {
  const { login, register } = useAuth();
  const [mode, setMode] = useState('register');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const dialogRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return undefined;
    const onKey = (event) => event.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    dialogRef.current?.focus();
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      if (mode === 'register') await register(username, password);
      else await login(username, password);
      setUsername('');
      setPassword('');
    } catch (submitError) {
      setError(submitError.message);
    } finally {
      setSubmitting(false);
    }
  };

  return createPortal(
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby="auth-modal-title"
      tabIndex={-1}
      className="fixed inset-0 z-[99999] flex items-center justify-center bg-black/60 backdrop-blur-sm px-4"
      onClick={(event) => event.target === event.currentTarget && onClose()}
    >
      <div className="relative w-full max-w-md rounded-2xl bg-white p-7 shadow-2xl sm:p-9">
        <button type="button" onClick={onClose} aria-label="关闭" className="absolute right-4 top-4 p-2 text-charcoal/40 hover:text-charcoal">
          <X size={22} />
        </button>
        <p className="mb-2 text-xs font-semibold uppercase tracking-[0.22em] text-warm-gold">Roommate Demo</p>
        <h2 id="auth-modal-title" className="text-2xl font-semibold text-charcoal">
          {mode === 'register' ? '创建体验账号' : '欢迎回来'}
        </h2>
        <p className="mt-2 text-sm leading-6 text-charcoal/60">
          {mode === 'register' ? '注册后即可获得 3 次免费生图机会。' : '登录后继续你的设计体验。'}
        </p>

        <form onSubmit={submit} className="mt-7 space-y-4">
          <label className="block text-sm font-medium text-charcoal">
            用户名
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              maxLength={24}
              placeholder="3-24位中文、字母或数字"
              className="mt-2 w-full rounded-lg border border-charcoal/15 px-4 py-3 outline-none transition focus:border-warm-gold focus:ring-2 focus:ring-warm-gold/15"
              required
            />
          </label>
          <label className="block text-sm font-medium text-charcoal">
            密码
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
              minLength={8}
              maxLength={128}
              placeholder="至少 8 位"
              className="mt-2 w-full rounded-lg border border-charcoal/15 px-4 py-3 outline-none transition focus:border-warm-gold focus:ring-2 focus:ring-warm-gold/15"
              required
            />
          </label>
          {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}
          <button type="submit" disabled={submitting} className="gold-gradient w-full rounded-lg py-3.5 font-medium text-white transition hover:opacity-90 disabled:opacity-60">
            {submitting ? '请稍候…' : mode === 'register' ? '注册并开始体验' : '登录'}
          </button>
        </form>

        <button
          type="button"
          onClick={() => { setMode(mode === 'register' ? 'login' : 'register'); setError(''); }}
          className="mt-5 w-full text-center text-sm text-charcoal/60 hover:text-warm-gold"
        >
          {mode === 'register' ? '已有账号？直接登录' : '还没有账号？免费注册'}
        </button>
      </div>
    </div>,
    document.body,
  );
}
