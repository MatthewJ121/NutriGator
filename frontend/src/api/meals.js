const API_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000";

async function mealRequest(path, options, fallbackMessage) {
  let response;

  try {
    response = await fetch(`${API_URL}${path}`, {
      ...options,
      credentials: "include",
    });
  } catch {
    throw new Error("Cannot connect to the server.");
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    let message = fallbackMessage;

    if (typeof data.detail === "string") {
      message = data.detail;
    } else if (Array.isArray(data.detail) && data.detail[0]?.msg) {
      message = data.detail[0].msg;
    }

    throw new Error(message);
  }

  return data;
}

export function getTodaysMeals() {
  return mealRequest("/meals/today", { method: "GET" }, "Failed to load meals");
}

export function logMeal(meal) {
  return mealRequest(
    "/meals",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(meal),
    },
    "Failed to log meal"
  );
}
