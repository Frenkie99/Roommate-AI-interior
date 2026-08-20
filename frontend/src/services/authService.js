const API_BASE = '/api/v1/auth';

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: 'same-origin',
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail;
    throw new Error(typeof detail === 'string' ? detail : detail?.message || body.message || '请求失败');
  }
  return body.data || {};
}

const authService = {
  register(username, password) {
    return request('/register', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
  },
  login(username, password) {
    return request('/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
  },
  me() {
    return request('/me');
  },
  logout() {
    return request('/logout', { method: 'POST', body: '{}' });
  },
};

export default authService;
