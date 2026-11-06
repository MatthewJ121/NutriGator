
const API_URL = (
  import.meta.env.VITE_API_URL || "http://localhost:8000"
).replace(/\/$/, "");

function goalsEndpoint(userId) {
  if (!userId) {
    throw new Error("A user ID is required.");
  }

  return `${API_URL}/api/goals/${encodeURIComponent(userId)}`;
}

async function requestGoal(method, userId, goals) {
  const options = {
    method,
    headers: {
      "Content-Type": "application/json",
    },
  };

  if (goals !== undefined) {
    options.body = JSON.stringify(goals);
  }

  const response = await fetch(goalsEndpoint(userId), options);
  const text = await response.text();

  let data;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  if (!response.ok) {
    const detail = data?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : `Backend returned HTTP ${response.status}`;

    const error = new Error(message);
    error.status = response.status;
    error.data = data;
    throw error;
  }

  return {
    status: response.status,
    data,
  };
}

// POST: Create nutrition goals
export function createGoal(userId, goals) {
  return requestGoal("POST", userId, goals);
}

// PUT: Update nutrition goals
export function updateGoal(userId, goals) {
  return requestGoal("PUT", userId, goals);
}

// GET: Retrieve nutrition goals
export function getGoal(userId) {
  return requestGoal("GET", userId);
}
