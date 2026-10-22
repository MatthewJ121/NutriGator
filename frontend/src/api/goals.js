
const API_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function createGoal(userId, goals) {
  const response = await fetch(
    `${API_URL}/api/goals/new_goal/${userId}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(goals),
    }
  );

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "Failed to save nutrition goals"
    );
  }

  return data;
}
