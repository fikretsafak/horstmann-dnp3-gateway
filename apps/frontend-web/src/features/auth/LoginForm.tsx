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
            alt="Musteri Logo"
            onError={(event) => {
              event.currentTarget.src = "/customer-logo-placeholder.svg";
            }}
          />
          <h2>Giris Yap</h2>
          <label>
            Kullanici Adi
            <input value={username} onChange={(event) => setUsername(event.target.value)} required />
          </label>
          <label>
            Sifre
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          </label>
          {error ? <p className="error-text">{error}</p> : null}
          <button type="submit" disabled={loading}>
            {loading ? "Giris yapiliyor..." : "Giris"}
          </button>
          <img className="form-logo-bottom" src="/form-logo.png" alt="Form Elektrik" />
        </form>

        <aside className="login-visual">
          <img className="visual-image" src="/login-visual.png" alt="Form Elektrik Gorseli" />
        </aside>
      </div>
    </div>
  );
}
