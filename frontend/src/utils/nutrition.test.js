import { describe, test } from "node:test";
import assert from "node:assert/strict";
import {
  makeDraftGoals,
  makeGoalRequests,
  parseGoalDraft,
  pickCurrentGoals,
} from "./nutrition.js";

const savedGoals = {
  calories: { target: 2000 },
  protein: { target: 120 },
};

describe("goal form", () => {
  test("only sends the goals that are checked", () => {
    const draft = makeDraftGoals(savedGoals);
    draft.carbs = { tracked: false, target: "300" };

    assert.deepEqual(parseGoalDraft(draft), { goals: savedGoals });
  });

  test("accepts decimals and zero", () => {
    const draft = makeDraftGoals(savedGoals);
    draft.protein.target = "120.5";
    draft.trans_fats = { tracked: true, target: "0" };

    const { goals } = parseGoalDraft(draft);
    assert.equal(goals.protein.target, 120.5);
    assert.equal(goals.trans_fats.target, 0);
  });

  for (const badValue of ["", "abc", "-5", "1e5", "12..5"]) {
    test(`rejects ${JSON.stringify(badValue)} as a target`, () => {
      const draft = makeDraftGoals(savedGoals);
      draft.calories.target = badValue;

      assert.ok(parseGoalDraft(draft).error);
    });
  }

  test("ignores categories that are not real goal fields", () => {
    const draft = makeDraftGoals(savedGoals);
    draft.sugar = { tracked: true, target: "50" };

    assert.equal(parseGoalDraft(draft).goals.sugar, undefined);
  });

  test("cancelling throws away draft edits", () => {
    const draft = makeDraftGoals(savedGoals);
    draft.calories.target = "9999";
    draft.protein.tracked = false;

    const resetDraft = makeDraftGoals(savedGoals);

    assert.deepEqual(resetDraft.calories, { tracked: true, target: "2000" });
    assert.equal(resetDraft.protein.tracked, true);
    assert.equal(savedGoals.calories.target, 2000);
  });
});

describe("talking to the goals backend", () => {
  test("builds Matthew's goal body with only the checked goals", () => {
    const { values } = makeGoalRequests(savedGoals, "2026-10-24");

    assert.deepEqual(values, { effective_date: "2026-10-24", calories: 2000, protein: 120 });
  });

  test("picks the latest goal that has started and skips -1 values", () => {
    const goalRows = [
      { effective_date: "2026-10-20", calories: 1800, protein: -1, carbs: -1, cholesterol: -1, trans_fats: -1, saturated_fats: -1, total_fats: -1 },
      { effective_date: "2026-10-22", calories: 2000, protein: 120, carbs: -1, cholesterol: -1, trans_fats: 0, saturated_fats: -1, total_fats: -1 },
      { effective_date: "2026-10-30", calories: 9999, protein: -1, carbs: -1, cholesterol: -1, trans_fats: -1, saturated_fats: -1, total_fats: -1 },
    ];

    const { goals, effectiveDate } = pickCurrentGoals(goalRows, "2026-10-24");

    assert.equal(effectiveDate, "2026-10-22");
    assert.deepEqual(goals, {
      calories: { target: 2000 },
      protein: { target: 120 },
      trans_fats: { target: 0 },
    });
  });

  test("no saved goals means nothing is tracked", () => {
    assert.deepEqual(pickCurrentGoals([], "2026-10-24").goals, {});
  });
});
