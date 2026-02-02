// 认证服务 API
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

class AuthService {
  // 发送验证码
  async sendCode(phone) {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/send-code`, {
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
      console.error('发送验证码错误:', error);
      throw error;
    }
  }

  // 用户注册
  async register(phone, code, password) {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/register`, {
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
      console.error('注册错误:', error);
      throw error;
    }
  }

  // 用户登录
  async login(phone, code, password) {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/login`, {
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
      if (data.token) {
        localStorage.setItem('auth_token', data.token);
        localStorage.setItem('user_info', JSON.stringify(data.user));
      }
      
      return data;
    } catch (error) {
      console.error('登录错误:', error);
      throw error;
    }
  }

  // 获取用户信息
  async getUserInfo() {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('未登录');
      }
      
      const response = await fetch(`${API_BASE_URL}/auth/user`, {
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
      console.error('获取用户信息错误:', error);
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
