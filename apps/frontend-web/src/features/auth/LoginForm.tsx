import { useState, type FormEvent } from "react";

type Props = {
  onSubmit: (username: string, password: string) => Promise<void>;
  loading: boolean;
  error?: string;
};

export function LoginForm({ onSubmit, loading, error }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onSubmit(username, password);
  };

  return (
    <div className="login-page">
      <div className="login-shell">
        <form className="login-card" onSubmit={handleSubmit} autoComplete="off">
          <img
            className="customer-logo"
            src="/customer-logo.png"
            alt="Müşteri Logo"
            onError={(event) => {
              event.currentTarget.src = "/customer-logo-placeholder.svg";
            }}
          />
          <div className="login-form-fields">
            <h2>Giriş Yap</h2>
            <label>
              Kullanıcı Adı
              <input
                name="hsl-login-username"
                autoComplete="off"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                required
              />
            </label>
            <label>
              Şifre
              <div className="password-input-wrap">
                <input
                  type={showPassword ? "text" : "password"}
                  name="hsl-login-password"
                  autoComplete="new-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                />
                <button
                  type="button"
                  className="password-toggle-btn"
                  onClick={() => setShowPassword((prev) => !prev)}
                  aria-label={showPassword ? "Şifreyi gizle" : "Şifreyi göster"}
                  title={showPassword ? "Şifreyi gizle" : "Şifreyi göster"}
                >
                  {showPassword ? (
                    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                      <path
                        fill="currentColor"
                        d="M12 7a5 5 0 0 1 5 5c0 .54-.09 1.06-.25 1.54l2.92 2.92C21.12 15.18 22.19 13.62 23 12c-1.73-3.46-5.21-6-9-6-1.24 0-2.42.27-3.49.75l2.17 2.17C11.31 8.34 11.64 8 12 8zm-9.19-4.19L1.39 4.22l3.01 3.01C2.27 8.93.64 10.82 0 12c1.73 3.46 5.21 6 9 6 1.56 0 3.03-.43 4.31-1.16l3.47 3.47 1.41-1.41zM9 10.6l3.4 3.4c-.11.01-.26.01-.4.01a2 2 0 0 1-2-2c0-.14 0-.29.01-.41zm5 1.81-3.41-3.41c.12-.01.27-.01.41-.01a2 2 0 0 1 2 2c0 .14 0 .29-.01.42z"
                      />
                    </svg>
                  ) : (
                    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                      <path
                        fill="currentColor"
                        d="M12 5c-7 0-10 7-10 7s3 7 10 7 10-7 10-7-3-7-10-7zm0 12a5 5 0 1 1 0-10 5 5 0 0 1 0 10zm0-8a3 3 0 1 0 0 6 3 3 0 0 0 0-6z"
                      />
                    </svg>
                  )}
                </button>
              </div>
            </label>
            {error ? <p className="error-text">{error}</p> : null}
            <button type="submit" disabled={loading}>
              {loading ? "Giriş yapılıyor..." : "Giriş"}
            </button>
          </div>
          <img className="form-logo-bottom" src="/form-logo.png" alt="Form Elektrik" />
        </form>

        <aside className="login-visual">
          <img className="visual-image" src="/login-visual.png" alt="Form Elektrik Görseli" />
        </aside>
      </div>
    </div>
  );
}
