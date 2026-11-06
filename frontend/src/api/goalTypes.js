/* MIN/MAX (turned off for now). Needs a backend route for /api/goal-types.

const API_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000";

async function readResponse(response, fallbackMessage) {
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : fallbackMessage
    );
  }

  return data;
}

export async function getGoalTypes(userId) {
  let response;

  try {
    response = await fetch(`${API_URL}/api/goal-types/${userId}`);
  } catch {
    throw new Error("Cannot connect to the server.");
  }

  const data = await readResponse(response, "Failed to load goal types");

  return data.goal_types;
}

export async function saveGoalTypes(userId, body) {
  let response;

  try {
    response = await fetch(`${API_URL}/api/goal-types/${userId}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error("Cannot connect to the server.");
  }

  return readResponse(response, "Failed to save goal types");
}

*/
