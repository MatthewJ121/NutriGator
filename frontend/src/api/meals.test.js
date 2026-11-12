import { test } from 'node:test';
import assert from 'node:assert/strict';
import { getMealsByDate, logMeal, removeMeal, UnauthorizedError } from './meals.js';

test('meal operations use the specified routes and immediately propagate 401', async () => {
  const original = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return { status: 401, ok: false, json: async () => ({}) };
  };
  try {
    for (const operation of [() => getMealsByDate('2026-11-10'), () => logMeal({ food_name: 'Toast', protein: 0 }), () => removeMeal({ meal_id: 3 })]) {
      await assert.rejects(operation, UnauthorizedError);
    }
    assert.equal(calls.length, 3);
    assert.match(calls[0].url, /\/api\/meals\/2026-11-10\?/);
    assert.equal(calls[1].options.method, 'POST');
    assert.deepEqual(JSON.parse(calls[1].options.body), { food_name: 'Toast', protein: 0 });
    assert.equal(calls[2].options.method, 'DELETE');
    assert.match(calls[2].url, /\/api\/meals\/3$/);
    assert.equal(calls[2].options.body, undefined);
    assert.equal(calls[2].options.credentials, 'include');
  } finally { globalThis.fetch = original; }
});
