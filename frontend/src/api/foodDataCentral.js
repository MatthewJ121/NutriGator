const FDC_API_URL = "https://api.nal.usda.gov/fdc/v1/foods/search";
const FDC_API_KEY = import.meta.env?.VITE_FDC_API_KEY || "DEMO_KEY";

const NUTRIENT_MATCHERS = {
  calories: {
    ids: [1008],
    names: ["energy"],
  },
  protein: {
    ids: [1003],
    names: ["protein"],
  },
  carbs: {
    ids: [1005],
    names: ["carbohydrate"],
  },
  cholesterol: {
    ids: [1253],
    names: ["cholesterol"],
  },
  trans_fats: {
    ids: [1257],
    names: ["trans"],
  },
  saturated_fats: {
    ids: [1258],
    names: ["saturated"],
  },
  total_fats: {
    ids: [1004],
    names: ["total lipid", "total fat", "fat"],
  },
};

function findNutrientValue(foodNutrients, matchers) {
  if (!Array.isArray(foodNutrients)) return null;
  // IDs avoid confusing total fat with saturated fat, or kcal with kJ.
  const nutrient = foodNutrients.find((entry) => matchers.ids.includes(Number(entry.nutrientId)));
  if (nutrient?.value == null) return null;
  const value = Number(nutrient.value);
  return Number.isFinite(value) && value >= 0 ? value : null;
}

function normalizeFoodResult(item) {
  const nutrients = {};

  for (const [key, matchers] of Object.entries(NUTRIENT_MATCHERS)) {
    nutrients[key] = findNutrientValue(item.foodNutrients, matchers);
  }

  return {
    fdcId: item.fdcId,
    description: item.description || "Unnamed food",
    brandOwner: item.brandOwner || "",
    dataType: item.dataType || "",
    servingSize: Number(item.servingSize) || null,
    servingSizeUnit: item.servingSizeUnit || "",
    nutrients,
  };
}

const searchCache = new Map();

export async function searchFoodPage(query, pageNumber = 1) {
  const normalized = String(query || "").trim();
  if (!normalized) {
    return { foods: [], totalPages: 0 };
  }

  const cacheKey = `${normalized.toLowerCase()}:${pageNumber}`;
  const cached = searchCache.get(cacheKey);
  if (cached && Date.now() - cached.savedAt < 10 * 60 * 1000) return cached.result;
  const params = new URLSearchParams({
    api_key: FDC_API_KEY,
    query: normalized,
    pageSize: "25",
    pageNumber: String(pageNumber),
  });

  let response;

  try {
    response = await fetch(`${FDC_API_URL}?${params.toString()}`);
  } catch {
    throw new Error("Unable to connect to FoodData Central.");
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const message =
      typeof data.error?.message === "string"
        ? data.error.message
        : "Food search failed.";
    throw new Error(message);
  }

  const foods = Array.isArray(data.foods) ? data.foods : [];
  const result = { foods: foods.map(normalizeFoodResult), totalPages: Number(data.totalPages) || (foods.length ? 1 : 0) };
  if (searchCache.size >= 50) searchCache.delete(searchCache.keys().next().value);
  searchCache.set(cacheKey, { savedAt: Date.now(), result });
  return result;
}

// Search nutrient values are per 100 g. A serving is usable only when its
// weight is supplied; volume cannot be converted to grams without density.
export function foodToMeal(food, amount, unit = "grams") {
  const quantity = Number(amount);
  if (!Number.isFinite(quantity) || quantity <= 0) throw new Error("Enter an amount greater than zero.");
  const servingUnit = String(food.servingSizeUnit).toLowerCase();
  const servingGrams = ["g", "grm"].includes(servingUnit) ? food.servingSize
    : ["oz", "onz"].includes(servingUnit) ? food.servingSize * 28.349523125 : null;
  if (unit === "servings" && !(servingGrams > 0)) {
    throw new Error("This food has no serving weight. Enter the amount in grams.");
  }
  const grams = unit === "servings" ? quantity * servingGrams : quantity;
  const meal = { food_name: food.description };
  for (const key of Object.keys(NUTRIENT_MATCHERS)) {
    const value = food.nutrients[key];
    if (value != null && value >= 0) meal[key] = Number((value * grams / 100).toFixed(4));
  }
  return meal;
}

export async function searchFoods(query) {
  return (await searchFoodPage(query)).foods;
}
