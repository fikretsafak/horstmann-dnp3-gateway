import { useState, type FormEvent } from "react";

import type { UserRead } from "../../shared/types";

type Props = {
  users: UserRead[];
  onCreate: (payload: {
    username: string;
    email: string;
    full_name: string;
    password: string;
    role: "operator" | "engineer";
  }) => Promise<void>;
  onDelete: (userId: number) => Promise<void>;
};

export function UserManagementPanel({ users, onCreate, onDelete }: Props) {
  const [isCreateModalOpen, setCreateModalOpen] = useState(false);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"operator" | "engineer">("operator");

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onCreate({ username, email, full_name: fullName, password, role });
    setUsername("");
    setEmail("");
    setFullName("");
    setPassword("");
    setRole("operator");
    setCreateModalOpen(false);
  };

  return (
    <section className="tab-panel">
      <h3>Kullanici Yonetimi</h3>
      <button onClick={() => setCreateModalOpen(true)}>Kullanici Ekle</button>

      {isCreateModalOpen ? (
        <div className="settings-modal-backdrop">
          <form className="settings-modal" onSubmit={handleSubmit}>
            <h3>Yeni Kullanici</h3>
            <label>
              Kullanici adi
              <input value={username} onChange={(event) => setUsername(event.target.value)} required />
            </label>
            <label>
              E-posta
              <input value={email} onChange={(event) => setEmail(event.target.value)} required />
            </label>
            <label>
              Ad Soyad
              <input value={fullName} onChange={(event) => setFullName(event.target.value)} required />
            </label>
            <label>
              Sifre
              <input value={password} onChange={(event) => setPassword(event.target.value)} required />
            </label>
            <label>
              Rol
              <select value={role} onChange={(event) => setRole(event.target.value as "operator" | "engineer")}>
                <option value="operator">Operator</option>
                <option value="engineer">Engineer</option>
              </select>
            </label>
            <div className="settings-actions">
              <button type="button" onClick={() => setCreateModalOpen(false)}>
                Vazgec
              </button>
              <button type="submit">Kaydet</button>
            </div>
          </form>
        </div>
      ) : null}

      <table className="values-table">
        <thead>
          <tr>
            <th>Kullanici</th>
            <th>Rol</th>
            <th>E-posta</th>
            <th>Islem</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr key={user.id}>
              <td>{user.full_name}</td>
              <td>{user.role}</td>
              <td>{user.email}</td>
              <td>
                <button className="danger-btn" onClick={() => void onDelete(user.id)}>
                  Sil
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
