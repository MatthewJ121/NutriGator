const API_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000";

function readError(data, fallbackMessage) {
  if (typeof data.detail === "string") {
    return data.detail;
  }

  if (Array.isArray(data.detail) && data.detail[0]?.msg) {
    return data.detail[0].msg;
  }

  return fallbackMessage;
}

export async function signUp(name, email, password) {
  let response;

  try {
    response = await fetch(`${API_URL}/auth/register`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include",
      body: JSON.stringify({ name, email, password }),
    });
  } catch {
    throw new Error("Cannot connect to the server.");
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(readError(data, "Could not create account."));
  }

  return data;
}
