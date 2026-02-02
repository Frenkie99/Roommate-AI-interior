import { useState, useEffect } from 'react';
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

  // 表单验证规则（只验证手机号和验证码）
  const validateForm = () => {
    const newErrors = {};
    
    // 手机号验证
    if (!phone) {
      newErrors.phone = '请输入手机号';
    } else if (!/^1[3-9]\d{9}$/.test(phone)) {
      newErrors.phone = '请输入正确的手机号';
    }
    
    // 验证码验证
    if (!code) {
      newErrors.code = '请输入验证码';
    } else if (!/^\d{4,6}$/.test(code)) {
      newErrors.code = '验证码应为4-6位数字';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // 倒计时效果
  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [countdown]);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) return;
    
    setIsLoading(true);
    try {
      if (isLogin) {
        const result = await authService.login(phone, code);
        console.log('登录成功:', result);
        onSuccess && onSuccess(result.user);
        onClose();
      } else {
        const result = await authService.register(phone, code);
        console.log('注册成功:', result);
        onSuccess && onSuccess(result.user);
        onClose();
      }
    } catch (error) {
      setErrors({ submit: error.message });
    } finally {
      setIsLoading(false);
    }
  };

  const sendCode = async () => {
    // 验证手机号
    if (!phone) {
      setErrors({ phone: '请输入手机号' });
      return;
    }
    
    if (!/^1[3-9]\d{9}$/.test(phone)) {
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

  return (
    <div 
      className="fixed inset-0 z-[9999] flex items-center justify-center"
      style={{ 
        backgroundColor: 'rgba(0, 0, 0, 0.6)',
        backdropFilter: 'blur(4px)',
        WebkitBackdropFilter: 'blur(4px)'
      }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div 
        className="bg-white w-full max-w-2xl mx-4 overflow-hidden"
        style={{ 
          borderRadius: '12px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)'
        }}
      >
        <div className="flex flex-col md:flex-row" style={{ minHeight: '420px' }}>
          {/* 左侧 - Logo和设计图片区域 */}
          <div className="hidden md:flex md:w-1/2 relative overflow-hidden">
            {/* 背景图片 */}
            <img 
              src="/styles/现代轻奢.png" 
              alt="室内设计" 
              className="w-full h-full object-cover"
            />
            {/* 暗色遮罩 */}
            <div className="absolute inset-0 bg-black/40"></div>
            {/* Logo */}
            <div className="absolute inset-0 flex flex-col justify-center items-center p-8">
              <img 
                src="/assets/logo/导航栏logo-抠图.png" 
                alt="Roommate" 
                className="h-20 drop-shadow-lg"
              />
            </div>
          </div>

          {/* 右侧 - 登录/注册表单 */}
          <div className="w-full md:w-1/2 p-8 flex flex-col bg-white">
            {/* 关闭按钮 */}
            <button 
              onClick={onClose}
              className="self-end text-gray-400 hover:text-gray-600 transition-colors"
            >
              <X className="w-6 h-6" />
            </button>

            {/* 表单内容 */}
            <div className="flex-1 flex flex-col justify-center px-4">
              <h2 className="text-2xl font-bold text-gray-900 mb-8 text-center">
                {isLogin ? '登录' : '注册'}
              </h2>

              <form onSubmit={handleSubmit} className="space-y-5">
                {/* 全局错误提示 */}
                {errors.submit && (
                  <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    <span>{errors.submit}</span>
                  </div>
                )}

                {/* 手机号输入 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    手机号
                  </label>
                  <div className="relative">
                    <Phone className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                    <input
                      type="tel"
                      value={phone}
                      onChange={(e) => { setPhone(e.target.value); setErrors(prev => ({...prev, phone: ''})); }}
                      placeholder="请输入手机号"
                      className={`w-full pl-10 pr-4 py-4 border rounded-lg focus:outline-none focus:ring-2 focus:ring-[#D4B07B] focus:border-transparent ${errors.phone ? 'border-red-400' : 'border-gray-300'}`}
                    />
                  </div>
                  {errors.phone && <p className="text-red-500 text-xs mt-1">{errors.phone}</p>}
                </div>

                {/* 验证码输入 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    验证码
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={code}
                      onChange={(e) => { setCode(e.target.value); setErrors(prev => ({...prev, code: ''})); }}
                      placeholder="请输入验证码"
                      maxLength={6}
                      className={`flex-1 px-4 py-4 border rounded-lg focus:outline-none focus:ring-2 focus:ring-[#D4B07B] focus:border-transparent ${errors.code ? 'border-red-400' : 'border-gray-300'}`}
                    />
                    <button
                      type="button"
                      onClick={sendCode}
                      disabled={countdown > 0 || isLoading}
                      className={`px-4 py-4 rounded-lg text-sm font-medium transition-colors min-w-[100px] ${
                        countdown > 0 || isLoading 
                          ? 'bg-gray-300 text-gray-500 cursor-not-allowed' 
                          : 'bg-[#D4B07B] text-white hover:bg-[#C9A56C]'
                      }`}
                    >
                      {countdown > 0 ? `${countdown}s` : (codeSent ? '重新获取' : '获取验证码')}
                    </button>
                  </div>
                  {errors.code && <p className="text-red-500 text-xs mt-1">{errors.code}</p>}
                </div>

                {/* 提交按钮 */}
                <button
                  type="submit"
                  disabled={isLoading}
                  className={`w-full text-white py-4 rounded-lg font-medium transition-all flex items-center justify-center gap-2 ${
                    isLoading ? 'opacity-70 cursor-not-allowed' : 'hover:brightness-110'
                  }`}
                  style={{ backgroundColor: '#D4B07B' }}
                >
                  {isLoading ? (
                    <>
                      <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      <span>处理中...</span>
                    </>
                  ) : (
                    <span>{isLogin ? '登录' : '注册'}</span>
                  )}
                </button>
              </form>

              {/* 切换登录/注册 */}
              <div className="mt-6 text-center text-sm text-gray-600">
                {isLogin ? '还没有账号？' : '已有账号？'}
                <button
                  onClick={() => setIsLogin(!isLogin)}
                  className="font-medium ml-1"
                  style={{ color: '#D4B07B' }}
                >
                  {isLogin ? '立即注册' : '立即登录'}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
