import { useState } from "react";
import logo from "../assets/nutrigator-logo.png";
import { signUp } from "../api/account";

const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export default function SignUp({ onBackToLogin }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState(false);

  const handleSignUp = async (event) => {
    event.preventDefault();
    setError("");

    if (!name.trim()) {
      setError("Please enter your name.");
      return;
    }

    if (!EMAIL_PATTERN.test(email.trim())) {
      setError("Please enter a valid email address.");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);

    try {
      await signUp(name.trim(), email.trim(), password);
      setCreated(true);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to create account."
      );
    } finally {
      setLoading(false);
    }
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

        {created ? (
          <div className="login-card">
            <h2>Account Created</h2>

            <p
              role="status"
              style={{ color: "#16703c", textAlign: "center" }}
            >
              Your account is ready. You can log in now.
            </p>

            <button
              type="button"
              className="form-button"
              onClick={onBackToLogin}
            >
              Go to Login
            </button>
          </div>
        ) : (
          <form
            className="login-card"
            onSubmit={handleSignUp}
            noValidate
          >
            <h2>Create Account</h2>

            <label htmlFor="signup-name">Name</label>
            <input
              id="signup-name"
              type="text"
              placeholder="Albert Gator"
              value={name}
              onChange={(event) => setName(event.target.value)}
              autoComplete="name"
              maxLength={50}
            />

            <label htmlFor="signup-email">Email</label>
            <input
              id="signup-email"
              type="email"
              placeholder="you@ufl.edu"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
            />

            <label htmlFor="signup-password">Password</label>
            <input
              id="signup-password"
              type="password"
              placeholder="At least 8 characters"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="new-password"
            />

            <label htmlFor="signup-confirm">Confirm Password</label>
            <input
              id="signup-confirm"
              type="password"
              placeholder="••••••••"
              value={confirmPassword}
              onChange={(event) =>
                setConfirmPassword(event.target.value)
              }
              autoComplete="new-password"
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
              {loading ? "Creating Account..." : "Create Account"}
            </button>

            <button
              type="button"
              className="form-button"
              onClick={onBackToLogin}
              disabled={loading}
            >
              Back to Login
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
