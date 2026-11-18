import { test } from "node:test";
import assert from "node:assert/strict";
import { createGoal, getGoal, updateGoal } from "./goals.js";

test("goal requests use the session-authenticated goals endpoint", async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return {
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ goals: [] }),
    };
  };

  try {
    await getGoal("11111111-1111-4111-8111-111111111111");
    await createGoal("11111111-1111-4111-8111-111111111111", { calories: 2000 });
    await updateGoal("11111111-1111-4111-8111-111111111111", { calories: 2000 });

    assert.deepEqual(
      calls.map(({ url, options }) => [new URL(url).pathname, options.method]),
      [
        ["/api/goals", "GET"],
        ["/api/goals", "POST"],
        ["/api/goals", "PUT"],
      ],
    );
    assert.ok(calls.every(({ options }) => options.credentials === "include"));
  } finally {
    globalThis.fetch = originalFetch;
  }
});
