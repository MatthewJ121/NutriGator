
const API_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000";

async function authRequest(path, body) {
  let response;

  try {
    response = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include",
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error(
      "Cannot connect to the authentication server."
    );
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : data.message || "Authentication failed."
    );
  }

  return data;
}

export function loginUser(email, password) {
  return authRequest("/auth/login", {
    email,
    password,
  });
}

export function signupUser(name, email, password) {
  return authRequest("/auth/signup", {
    name,
    email,
    password,
  });
}
