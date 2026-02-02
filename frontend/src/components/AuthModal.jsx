import { useState, useEffect } from 'react';
import { X, Phone, Lock, Eye, EyeOff, CheckCircle, AlertCircle } from 'lucide-react';
import authService from '../services/authService';

export default function AuthModal({ isOpen, onClose, onSuccess }) {
  const [isLogin, setIsLogin] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [errors, setErrors] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const [codeSent, setCodeSent] = useState(false);
  const [countdown, setCountdown] = useState(0);

  // 表单验证规则
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
    } else if (!/^\d{6}$/.test(code)) {
      newErrors.code = '验证码应为6位数字';
    }
    
    // 密码验证
    if (!password) {
      newErrors.password = '请输入密码';
    } else if (password.length < 6) {
      newErrors.password = '密码至少6位';
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
        const result = await authService.login(phone, code, password);
        console.log('登录成功:', result);
        onSuccess && onSuccess(result.user);
        onClose();
      } else {
        const result = await authService.register(phone, code, password);
        console.log('注册成功:', result);
        // 注册成功后自动登录
        const loginResult = await authService.login(phone, code, password);
        onSuccess && onSuccess(loginResult.user);
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl mx-4 overflow-hidden">
        <div className="flex h-[600px]">
          {/* 左侧 - 设计图片区域 */}
          <div className="hidden md:flex md:w-1/2 bg-gradient-to-br from-warm-gold/20 to-soft-gold/10 relative overflow-hidden">
            <div className="absolute inset-0 bg-black/20"></div>
            <img 
              src="/assets/interior-design-bg.jpg" 
              alt="室内设计" 
              className="w-full h-full object-cover"
            />
            <div className="absolute inset-0 flex flex-col justify-center items-center text-white p-8">
              <div className="mb-8">
                <img src="/assets/logo/导航栏logo-抠图.png" alt="Roommate" className="h-16 drop-shadow-lg" />
              </div>
              <h1 className="text-3xl font-bold mb-4 text-center">Roommate</h1>
              <p className="text-lg text-center opacity-90">AI智能室内设计平台</p>
              <p className="text-sm text-center opacity-75 mt-2">让设计更简单，让空间更美好</p>
            </div>
          </div>

          {/* 右侧 - 登录/注册表单 */}
          <div className="w-full md:w-1/2 p-8 flex flex-col">
            {/* 关闭按钮 */}
            <button 
              onClick={onClose}
              className="self-end text-gray-400 hover:text-gray-600 transition-colors"
            >
              <X className="w-6 h-6" />
            </button>

            {/* 标题 */}
            <div className="flex-1 flex flex-col justify-center">
              <h2 className="text-2xl font-bold text-gray-900 mb-6 text-center">
                {isLogin ? '登录' : '注册'}
              </h2>

              <form onSubmit={handleSubmit} className="space-y-4">
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
                      className={`w-full pl-10 pr-3 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-warm-gold focus:border-transparent ${errors.phone ? 'border-red-400' : 'border-gray-300'}`}
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
                      className={`flex-1 px-3 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-warm-gold focus:border-transparent ${errors.code ? 'border-red-400' : 'border-gray-300'}`}
                    />
                    <button
                      type="button"
                      onClick={sendCode}
                      disabled={countdown > 0 || isLoading}
                      className={`px-4 py-3 rounded-lg text-sm font-medium transition-colors min-w-[100px] ${
                        countdown > 0 || isLoading 
                          ? 'bg-gray-300 text-gray-500 cursor-not-allowed' 
                          : 'bg-warm-gold text-white hover:bg-warm-gold/90'
                      }`}
                    >
                      {countdown > 0 ? `${countdown}s` : (codeSent ? '重新获取' : '获取验证码')}
                    </button>
                  </div>
                  {errors.code && <p className="text-red-500 text-xs mt-1">{errors.code}</p>}
                </div>

                {/* 密码输入 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    密码
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => { setPassword(e.target.value); setErrors(prev => ({...prev, password: ''})); }}
                      placeholder="请输入密码"
                      className={`w-full pl-10 pr-10 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-warm-gold focus:border-transparent ${errors.password ? 'border-red-400' : 'border-gray-300'}`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    >
                      {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                    </button>
                  </div>
                  {errors.password && <p className="text-red-500 text-xs mt-1">{errors.password}</p>}
                </div>

                {/* 提交按钮 */}
                <button
                  type="submit"
                  disabled={isLoading}
                  className={`w-full gold-gradient text-white py-3 rounded-lg font-medium transition-opacity flex items-center justify-center gap-2 ${
                    isLoading ? 'opacity-70 cursor-not-allowed' : 'hover:opacity-90'
                  }`}
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
                  className="text-warm-gold hover:text-warm-gold/80 font-medium ml-1"
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
