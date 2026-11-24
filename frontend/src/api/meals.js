const API_URL = import.meta.env?.VITE_API_URL || "http://localhost:8000";

export class UnauthorizedError extends Error {
  constructor(message = "Please log in again.") {
    super(message);
    this.status = 401;
  }
}

async function mealRequest(path, method = "GET", body) {
  const response = await fetch(`${API_URL}${path}`, {
    method,
    credentials: "include",
    ...(body === undefined ? {} : {
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  });
  if (response.status === 204) return [];
  const data = await response.json().catch(() => ({}));
  if (response.status === 401) throw new UnauthorizedError();
  if (!response.ok) {
    throw new Error(typeof data.detail === "string" ? data.detail : "Unable to update the meal log.");
  }
  return data;
}

export const getTodaysMeals = () => mealRequest("/meals/today");
export const getMealsByDate = (date) => {
  const start = new Date(`${date}T00:00:00`);
  const end = new Date(start);
  end.setDate(end.getDate() + 1);
  const params = new URLSearchParams({
    timezone_offset: start.getTimezoneOffset(),
    timezone_end_offset: end.getTimezoneOffset(),
  });
  return mealRequest(`/api/meals/${encodeURIComponent(date)}?${params}`);
};
export const logMeal = (meal) => mealRequest("/api/meals", "POST", meal);
export const saveMealEdits = logMeal;
export const removeMeal = (meal) => mealRequest(`/api/meals/${encodeURIComponent(meal.meal_id)}`, "DELETE");
