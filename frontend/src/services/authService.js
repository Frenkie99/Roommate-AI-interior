/**
 * 认证服务 API
 *
 * @deprecated 后端当前未实现 /auth 路由（见 backend/app/routes/ 仅有 image/segment/knowledge，
 * main.py 也未挂载 auth router），本模块所有方法在运行时都会得到 404。
 *
 * 已知问题：
 *  - #41 默认 API_BASE_URL 此前回退到 http://localhost:8000；若生产构建忘记设置
 *    VITE_API_BASE_URL，会把手机号 / 短信验证码 / 密码静默 POST 到 localhost。本次修复
 *    将默认值改为 ''（同源相对路径），最坏情况是 nginx 同源 404，不会泄漏到无关 host。
 *  - #42 即便 login 写入 localStorage 的 JWT（XSS 可读），api.js / segmentApi.js 的
 *    axios 实例也从未附 Authorization 头 → 整套 auth 是死代码。
 *
 * 注意：保留导出而不是删除，是因为 AuthModal.jsx / Navbar.jsx 仍在 import 本模块，
 * 直接删除会破坏构建。后端实现真实 auth 路由前，请勿在新 UI 流程里依赖其返回值。
 *
 * 路径前缀已从 /auth/... 改为 /api/v1/auth/...，对齐后端未来路由约定与 nginx 反代规则。
 *
 * 跟踪 issue：#41 #42
 */

// 默认使用相对路径（同源），避免在缺失 VITE_API_BASE_URL 时把凭据 POST 到 localhost
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function _warnDeprecated(fn) {
  if (typeof console !== 'undefined') {
    console.warn(
      `[authService] ${fn} called but backend /auth routes are not implemented. ` +
      `Tracking issues #41 #42. This will return a 404.`
    );
  }
}

class AuthService {
  // 发送验证码
  async sendCode(phone) {
    _warnDeprecated('sendVerificationCode');
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/send-code`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ phone }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || '发送验证码失败');
      }

      return data;
    } catch (error) {
      // 只记录消息字符串，避免把请求体（含 phone）原样吐到 console
      console.error('发送验证码错误:', error?.message || error);
      throw error;
    }
  }

  // 用户注册
  async register(phone, code, password) {
    _warnDeprecated('register');
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ phone, code, password }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || '注册失败');
      }

      return data;
    } catch (error) {
      // 只记录消息字符串，避免把请求体（含 password）原样吐到 console
      console.error('注册错误:', error?.message || error);
      throw error;
    }
  }

  // 用户登录
  async login(phone, code, password) {
    _warnDeprecated('login');
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ phone, code, password }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || '登录失败');
      }

      // 保存token到localStorage
      // 注意：见 #42，api.js / segmentApi.js 从未读取此 token，目前实际无效。
      if (data.token) {
        localStorage.setItem('auth_token', data.token);
        localStorage.setItem('user_info', JSON.stringify(data.user));
      }

      return data;
    } catch (error) {
      // 只记录消息字符串，避免把请求体（含 password）原样吐到 console
      console.error('登录错误:', error?.message || error);
      throw error;
    }
  }

  // 获取用户信息
  async getUserInfo() {
    _warnDeprecated('getCurrentUser');
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('未登录');
      }

      const response = await fetch(`${API_BASE_URL}/api/v1/auth/user`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || '获取用户信息失败');
      }

      return data;
    } catch (error) {
      console.error('获取用户信息错误:', error?.message || error);
      throw error;
    }
  }

  // 退出登录
  logout() {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_info');
  }

  // 检查是否已登录
  isAuthenticated() {
    return !!localStorage.getItem('auth_token');
  }

  // 获取当前用户信息
  getCurrentUser() {
    const userInfo = localStorage.getItem('user_info');
    return userInfo ? JSON.parse(userInfo) : null;
  }
}

export default new AuthService();
