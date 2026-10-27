
import { useState } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useNavigate,
} from "react-router-dom";

import "./App.css";
import logo from "./assets/nutrigator-logo.png";
import ProgressDashboard from "./ProgressDashboard";

// Backend URL and login route.
const API_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000";

const LOGIN_ENDPOINT = "/auth/login";
const LOGOUT_ENDPOINT = "/auth/logout";

// Demo login is available only when running Vite in development.
const ENABLE_DEMO_LOGIN = import.meta.env.DEV;

function Login({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const navigate = useNavigate();

  // REAL LOGIN: React -> FastAPI -> Better Auth
  const handleLogin = async (e) => {
    e.preventDefault();
    setError("");

    if (!email.trim() || !password) {
      setError("Please enter your email and password.");
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(
        `${API_URL}${LOGIN_ENDPOINT}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          credentials: "include",
          body: JSON.stringify({
            email: email.trim(),
            password: password,
          }),
        }
      );

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        const message =
          typeof data.detail === "string"
            ? data.detail
            : data.message || "Login failed. Please try again.";

        throw new Error(message);
      }

      // Expected bearer-token response from FastAPI.
      const token = data.token;

      if (!token) {
        throw new Error(
          "The backend did not return an authentication token."
        );
      }

      // Keep the token in React memory, not localStorage.
      onLogin({
        email: data.user?.email || email.trim(),
        user: data.user || null,
        token: token,
        isDemo: false,
      });

      navigate("/app/log", { replace: true });
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to connect to the backend."
      );
    } finally {
      setLoading(false);
    }
  };

  // DEMO LOGIN: frontend development only.
  // Does not call the backend or create a real session.
  const handleDemoLogin = () => {
    if (!ENABLE_DEMO_LOGIN) return;

    setError("");

    onLogin({
      email: "demo@nutrigator.local",
      user: null,
      token: null,
      isDemo: true,
    });

    navigate("/app/log", { replace: true });
  };

  return (
    <div className="login-page">
      <div className="login-container">
        <div className="branding">
          <img
            src={logo}
            alt="NutriGator Logo"
            className="nutrigator-logo"
          />
          <h1>NutriGator</h1>
        </div>

        <form className="login-card" onSubmit={handleLogin}>
          <h2>Login</h2>

          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            placeholder="you@clinic.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
          />

          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />

          {error && (
            <p role="alert" style={{ color: "#b42318" }}>
              {error}
            </p>
          )}

          <button
            type="submit"
            className="form-button"
            disabled={loading}
          >
            {loading ? "Logging In..." : "Log In"}
          </button>

          <button
            type="button"
            className="form-button"
            onClick={() =>
              alert("Account creation coming soon!")
            }
          >
            Create Account
          </button>

          {ENABLE_DEMO_LOGIN && (
            <button
              type="button"
              className="form-button"
              onClick={handleDemoLogin}
              disabled={loading}
            >
              Demo Login (Frontend Testing)
            </button>
          )}
        </form>
      </div>
    </div>
  );
}

function Home({ user, onLogout }) {
  const navigate = useNavigate();

  const handleLogout = async () => {
    onLogout();
    navigate("/", { replace: true });

    try {
      const response = await fetch(`${API_URL}${LOGOUT_ENDPOINT}`, {
        method: "POST",
        credentials: "include",
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "The server could not confirm logout."
        );
      }
    } catch (error) {
      alert(
        error instanceof Error
          ? `Your local session was cleared, but server logout may have failed: ${error.message}`
          : "Your local session was cleared, but server logout may have failed."
      );
    }
  };

  return (
    <div className="nutrigator-shell">
      <header className="nutrigator-header">
        <button
          type="button"
          className="nutrigator-account"
          onClick={() =>
            alert("Account page coming soon!")
          }
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path
              d="M12 12a4.5 4.5 0 1 0-4.5-4.5A4.5 4.5 0 0 0 12 12Zm0 2c-4.8 0-8 2.4-8 5v1h16v-1c0-2.6-3.2-5-8-5Z"
              fill="currentColor"
            />
          </svg>
          <span>account</span>
        </button>

        <img
          src={logo}
          alt="NutriGator"
          className="nutrigator-header-logo"
        />

        <button
          type="button"
          className="nutrigator-logout"
          onClick={handleLogout}
        >
          Logout
        </button>
      </header>

      <main className="nutrigator-content">
        {user?.isDemo && (
          <p
            style={{
              textAlign: "center",
              fontSize: "13px",
              color: "#555",
            }}
          >
            Demo Mode — Frontend Testing Only
          </p>
        )}

        <ProgressDashboard />

        <section className="nutrigator-food-placeholder">
          <h3>Food Log</h3>
        </section>
      </main>

      <nav
        className="nutrigator-bottom-nav"
        aria-label="Main navigation"
      >
        <span>log</span>
      </nav>
    </div>
  );
}

export default function App() {
  // Stores the authenticated user and token in memory.
  const [user, setUser] = useState(null);

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={
            user ? (
              <Navigate to="/app/log" replace />
            ) : (
              <Login onLogin={setUser} />
            )
          }
        />

        <Route
          path="/app/log"
          element={
            user ? (
              <Home
                user={user}
                onLogout={() => setUser(null)}
              />
            ) : (
              <Navigate to="/" replace />
            )
          }
        />

        <Route
          path="*"
          element={<Navigate to="/" replace />}
        />
      </Routes>
    </BrowserRouter>
  );
}
