import { useState } from "react";
import "../App.css";
import logo from "../assets/nutrigator-logo.png";
import ProgressDashboard from "../ProgressDashboard";
import SignUp from "./SignUp";
import { loginUser } from "../api/auth";
import { getLocalUserId } from "../utils/userId";

const ENABLE_DEMO_LOGIN = import.meta.env.DEV;

function Login({ onLogin, onCreateAccount }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleLogin = async (event) => {
    event.preventDefault();
    setError("");

    if (!email.trim() || !password) {
      setError("Please enter your email and password.");
      return;
    }

    setLoading(true);

    try {
      const data = await loginUser(email.trim(), password);
      const account = data.user;

      if (!account?.id) {
        throw new Error("Login worked, but no user was returned.");
      }

      onLogin({
        email: account.email || email.trim(),
        name: account.name,
        userId: await getLocalUserId(account.id),
        token: data.token,
        isDemo: false,
      });
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to log in."
      );
      setLoading(false);
    }
  };

  const handleDemoLogin = () => {
    onLogin({
      email: "demo@nutrigator.local",
      name: "Demo",
      userId: null,
      token: null,
      isDemo: true,
    });
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

        <form
          className="login-card"
          onSubmit={handleLogin}
        >
          <h2>Login</h2>

          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            placeholder="you@clinic.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="email"
            required
          />

          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            placeholder="••••••••"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            required
          />

          {error && (
            <p
              role="alert"
              style={{ color: "#b42318" }}
            >
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
            onClick={onCreateAccount}
            disabled={loading}
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
  return (
    <div className="nutrigator-shell">
      <header className="nutrigator-header">
        <button
          type="button"
          className="nutrigator-account"
          title={user.email}
        >
          <svg
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              d="M12 12a4.5 4.5 0 1 0-4.5-4.5A4.5 4.5 0 0 0 12 12Zm0 2c-4.8 0-8 2.4-8 5v1h16v-1c0-2.6-3.2-5-8-5Z"
              fill="currentColor"
            />
          </svg>
          <span>{user.name || "account"}</span>
        </button>

        <img
          src={logo}
          alt="NutriGator"
          className="nutrigator-header-logo"
        />

        <button
          type="button"
          className="nutrigator-logout"
          onClick={onLogout}
        >
          Logout
        </button>
      </header>

      <main className="nutrigator-content">
        {user.isDemo && (
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

        <ProgressDashboard
          userId={user.userId}
          token={user.token}
          isDemo={user.isDemo}
        />

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

export default function NutriGatorApp() {
  const [user, setUser] = useState(null);
  const [screen, setScreen] = useState("login");

  if (user) {
    return (
      <Home
        user={user}
        onLogout={() => {
          setUser(null);
          setScreen("login");
        }}
      />
    );
  }

  if (screen === "signup") {
    return <SignUp onBackToLogin={() => setScreen("login")} />;
  }

  return (
    <Login
      onLogin={setUser}
      onCreateAccount={() => setScreen("signup")}
    />
  );
}
