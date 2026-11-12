import { test } from 'node:test';
import assert from 'node:assert/strict';
import { foodToMeal, searchFoods } from './foodDataCentral.js';

test('scales per 100g nutrients by gram weight or serving weight without inventing missing nutrients', () => {
  const food = { description: 'Bread', servingSize: 30, servingSizeUnit: 'g', nutrients: { calories: 200, protein: 0 } };
  assert.deepEqual(foodToMeal(food, 50), { food_name: 'Bread', calories: 100, protein: 0 });
  assert.equal(foodToMeal(food, 2, 'servings').calories, 120);
  assert.throws(() => foodToMeal({ ...food, servingSizeUnit: 'ml' }, 1, 'servings'));
  assert.throws(() => foodToMeal(food, -2));
});

test('search encodes food names and preserves absent nutrients and zero', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async (url) => {
    assert.equal(new URL(url).searchParams.get('query'), 'rice & beans');
    return { ok: true, json: async () => ({ foods: [{ fdcId: 1, foodNutrients: [{ nutrientId: 1003, value: 0 }] }] }) };
  };
  try {
    const [food] = await searchFoods(' rice & beans ');
    assert.equal(food.nutrients.protein, 0);
    assert.equal(food.nutrients.calories, null);
  } finally { globalThis.fetch = original; }
});
