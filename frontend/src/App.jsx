
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

function Login({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const navigate = useNavigate();

  const handleLogin = (e) => {
    e.preventDefault();

    if (!email.trim() || !password) {
      alert("Please enter your email and password.");
      return;
    }

    onLogin(email.trim());
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

          <button type="submit" className="form-button">
            Log In
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
        </form>
      </div>
    </div>
  );
}

function Home({ onLogout }) {
  const navigate = useNavigate();

  const handleLogout = () => {
    onLogout();
    navigate("/", { replace: true });
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
              <Home onLogout={() => setUser(null)} />
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
