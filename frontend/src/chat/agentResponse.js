export async function parseAgentResponse(response) {
  const text = await response.text();

  if (!text.trim()) {
    throw new Error(`后端服务未返回有效响应（HTTP ${response.status}）。请确认后端 8000 服务已启动。`);
  }

  let payload;
  try {
    payload = JSON.parse(text);
  } catch {
    throw new Error(`后端返回了非 JSON 响应（HTTP ${response.status}）。请检查后端服务状态。`);
  }

  if (!response.ok || payload.code !== 0) {
    const detail = payload.detail;
    throw new Error(
      (typeof detail === 'string' ? detail : detail?.message) ||
      payload.message ||
      `服务器错误 ${response.status}`
    );
  }

  return payload;
}
