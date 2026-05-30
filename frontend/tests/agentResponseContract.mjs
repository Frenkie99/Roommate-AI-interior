import assert from 'node:assert/strict';
import { parseAgentResponse } from '../src/chat/agentResponse.js';

const emptyErrorResponse = new Response('', { status: 500, statusText: 'Internal Server Error' });

await assert.rejects(
  () => parseAgentResponse(emptyErrorResponse),
  /后端服务未返回有效响应/,
);

const successResponse = new Response(JSON.stringify({
  code: 0,
  message: 'success',
  data: { action: 'knowledge_answer', assistant_message: 'ok' },
}), {
  status: 200,
  headers: { 'content-type': 'application/json' },
});

assert.deepEqual(await parseAgentResponse(successResponse), {
  code: 0,
  message: 'success',
  data: { action: 'knowledge_answer', assistant_message: 'ok' },
});
