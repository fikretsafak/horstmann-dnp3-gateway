import { useState, type FormEvent } from "react";

type Props = {
  onSubmit: (username: string, password: string) => Promise<void>;
  loading: boolean;
  error?: string;
};

export function LoginForm({ onSubmit, loading, error }: Props) {
  const [username, setUsername] = useState("engineer");
  const [password, setPassword] = useState("ChangeMe123!");

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onSubmit(username, password);
  };

  return (
    <div className="login-page">
      <div className="login-shell">
        <form className="login-card" onSubmit={handleSubmit}>
          <img
            className="customer-logo"
            src="/customer-logo.png"
            alt="Müşteri Logo"
            onError={(event) => {
              event.currentTarget.src = "/customer-logo-placeholder.svg";
            }}
          />
          <h2>Giriş Yap</h2>
          <label>
            Kullanıcı Adı
            <input value={username} onChange={(event) => setUsername(event.target.value)} required />
          </label>
          <label>
            Şifre
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          </label>
          {error ? <p className="error-text">{error}</p> : null}
          <button type="submit" disabled={loading}>
            {loading ? "Giriş yapılıyor..." : "Giriş"}
          </button>
          <img className="form-logo-bottom" src="/form-logo.png" alt="Form Elektrik" />
        </form>

        <aside className="login-visual">
          <img className="visual-image" src="/login-visual.png" alt="Form Elektrik Görseli" />
        </aside>
      </div>
    </div>
  );
}
