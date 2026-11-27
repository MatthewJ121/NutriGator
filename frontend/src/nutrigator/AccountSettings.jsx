import { useEffect, useRef } from "react";
import "./AccountSettings.css";

export default function AccountSettings({ onBack }) {
  const heading = useRef(null);
  useEffect(() => { heading.current?.focus(); }, []);

  return (
    <section className="account-settings" aria-labelledby="account-settings-title">
      <button type="button" className="account-back" onClick={onBack}>← Back to food log</button>
      <h1 id="account-settings-title" ref={heading} tabIndex={-1}>Account settings</h1>
      <nav className="account-sections" aria-label="Account settings sections">
        <a href="#account-password">Password</a>
        <a href="#account-premium">Premium</a>
        <a href="#account-delete">Delete account</a>
      </nav>
      <div className="account-settings-card">
      <section id="account-password" className="account-setting" aria-labelledby="account-password-title">
        <h2 id="account-password-title">Password</h2>
        <p>Update your account password.</p>
        <p className="account-unavailable">Password updates are not available yet.</p>
      </section>
      <section id="account-premium" className="account-setting" aria-labelledby="account-premium-title">
        <h2 id="account-premium-title">Premium</h2>
        <p>Manage your premium membership.</p>
        <p className="account-unavailable">Premium settings are not available yet.</p>
      </section>
      <section id="account-delete" className="account-setting" aria-labelledby="account-delete-title">
        <h2 id="account-delete-title">Delete account</h2>
        <p>Manage deletion of your account.</p>
        <p className="account-unavailable">Account deletion is not available yet.</p>
      </section>
      </div>
    </section>
  );
}
