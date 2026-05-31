const STORAGE_KEY = 'roommate_design_history_v1';
const MAX_HISTORY_ITEMS = 50;

function hasStorage() {
  return typeof globalThis.localStorage !== 'undefined';
}

function readHistory() {
  if (!hasStorage()) return [];

  try {
    const rawHistory = globalThis.localStorage.getItem(STORAGE_KEY);
    const parsedHistory = rawHistory ? JSON.parse(rawHistory) : [];
    return Array.isArray(parsedHistory) ? parsedHistory : [];
  } catch (error) {
    console.warn('读取历史记录失败:', error);
    return [];
  }
}

function writeHistory(history) {
  if (!hasStorage()) return;

  try {
    globalThis.localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
  } catch (error) {
    console.warn('保存历史记录失败:', error);
  }
}

function normalizeRecord(record) {
  if (!record?.outputUrl) return null;

  const createdAt = record.createdAt || new Date().toISOString();
  const id = record.taskId || record.id || `design-${Date.now()}`;

  return {
    id,
    taskId: record.taskId || null,
    outputUrl: record.outputUrl,
    style: record.style || '',
    roomType: record.roomType || '',
    prompt: record.prompt || '',
    source: record.source || 'home',
    createdAt,
  };
}

export function getDesignHistory() {
  return readHistory()
    .filter((item) => item?.id && item?.outputUrl)
    .sort((left, right) => new Date(right.createdAt) - new Date(left.createdAt));
}

export function addDesignHistory(record) {
  const nextRecord = normalizeRecord(record);
  if (!nextRecord) return getDesignHistory();

  const history = readHistory().filter((item) => item.id !== nextRecord.id);
  const nextHistory = [nextRecord, ...history]
    .sort((left, right) => new Date(right.createdAt) - new Date(left.createdAt))
    .slice(0, MAX_HISTORY_ITEMS);

  writeHistory(nextHistory);
  return nextHistory;
}

export function deleteDesignHistory(id) {
  const nextHistory = readHistory().filter((item) => item.id !== id);
  writeHistory(nextHistory);
  return nextHistory;
}
