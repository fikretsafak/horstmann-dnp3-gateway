import { useState, type FormEvent } from "react";

import type { UserRead, UserRole } from "../../shared/types";

type Props = {
  users: UserRead[];
  onCreate: (payload: { username: string; email: string; full_name: string; password: string; role: UserRole }) => Promise<void>;
  onDelete: (userId: number) => Promise<void>;
};

export function UserManagementPanel({ users, onCreate, onDelete }: Props) {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("operator");

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onCreate({ username, email, full_name: fullName, password, role });
    setUsername("");
    setEmail("");
    setFullName("");
    setPassword("");
    setRole("operator");
  };

  return (
    <section className="tab-panel">
      <h3>Kullanici Yonetimi</h3>
      <form className="user-form" onSubmit={handleSubmit}>
        <input placeholder="Kullanici adi" value={username} onChange={(event) => setUsername(event.target.value)} required />
        <input placeholder="E-posta" value={email} onChange={(event) => setEmail(event.target.value)} required />
        <input placeholder="Ad Soyad" value={fullName} onChange={(event) => setFullName(event.target.value)} required />
        <input placeholder="Sifre" value={password} onChange={(event) => setPassword(event.target.value)} required />
        <select value={role} onChange={(event) => setRole(event.target.value as UserRole)}>
          <option value="operator">Operator</option>
          <option value="engineer">Engineer</option>
        </select>
        <button type="submit">Kullanici Ekle</button>
      </form>
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
