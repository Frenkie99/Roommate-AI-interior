import assert from 'node:assert/strict';
import { beforeEach, test } from 'node:test';

import {
  addDesignHistory,
  deleteDesignHistory,
  getDesignHistory,
} from './historyService.js';

class MemoryStorage {
  constructor() {
    this.store = new Map();
  }

  getItem(key) {
    return this.store.has(key) ? this.store.get(key) : null;
  }

  setItem(key, value) {
    this.store.set(key, String(value));
  }

  removeItem(key) {
    this.store.delete(key);
  }

  clear() {
    this.store.clear();
  }
}

beforeEach(() => {
  globalThis.localStorage = new MemoryStorage();
});

test('adds generated designs in newest-first order and deduplicates by id', () => {
  addDesignHistory({
    taskId: 'task-old',
    outputUrl: '/output/old.png',
    style: 'modern_minimalist',
    roomType: 'living_room',
    prompt: 'old prompt',
    source: 'home',
    createdAt: '2026-05-31T10:00:00.000Z',
  });

  addDesignHistory({
    taskId: 'task-new',
    outputUrl: '/output/new.png',
    style: 'natural_wood',
    roomType: 'bedroom',
    prompt: 'new prompt',
    source: 'playground',
    createdAt: '2026-05-31T11:00:00.000Z',
  });

  addDesignHistory({
    taskId: 'task-old',
    outputUrl: '/output/old-updated.png',
    style: 'modern_minimalist',
    roomType: 'living_room',
    prompt: 'updated prompt',
    source: 'agent',
    createdAt: '2026-05-31T12:00:00.000Z',
  });

  const history = getDesignHistory();

  assert.equal(history.length, 2);
  assert.deepEqual(
    history.map((item) => item.id),
    ['task-old', 'task-new'],
  );
  assert.equal(history[0].outputUrl, '/output/old-updated.png');
  assert.equal(history[0].source, 'agent');
});

test('ignores records without generated image urls', () => {
  addDesignHistory({
    taskId: 'missing-image',
    style: 'modern_minimalist',
    roomType: 'living_room',
    source: 'home',
  });

  assert.deepEqual(getDesignHistory(), []);
});

test('keeps only the latest 50 records', () => {
  for (let index = 0; index < 55; index += 1) {
    addDesignHistory({
      taskId: `task-${index}`,
      outputUrl: `/output/${index}.png`,
      style: 'modern_minimalist',
      roomType: 'living_room',
      source: 'home',
      createdAt: new Date(Date.UTC(2026, 4, 31, 10, index)).toISOString(),
    });
  }

  const history = getDesignHistory();

  assert.equal(history.length, 50);
  assert.equal(history[0].id, 'task-54');
  assert.equal(history.at(-1).id, 'task-5');
});

test('deletes one design history record by id', () => {
  addDesignHistory({
    taskId: 'keep',
    outputUrl: '/output/keep.png',
    source: 'home',
  });
  addDesignHistory({
    taskId: 'remove',
    outputUrl: '/output/remove.png',
    source: 'home',
  });

  deleteDesignHistory('remove');

  assert.deepEqual(
    getDesignHistory().map((item) => item.id),
    ['keep'],
  );
});
