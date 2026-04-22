import { useEffect, useState, type FormEvent } from "react";

import type { NotificationSettings } from "../../shared/types";

type Props = {
  initialSettings: NotificationSettings | null;
  loading: boolean;
  saving: boolean;
  error: string;
  onSave: (payload: NotificationSettings) => Promise<void>;
};

const EMPTY_SETTINGS: NotificationSettings = {
  smtp_enabled: false,
  smtp_host: "",
  smtp_port: 587,
  smtp_username: "",
  smtp_password: "",
  smtp_from_email: "",
  sms_enabled: false,
  sms_provider: "mock",
  sms_api_url: "",
  sms_api_key: ""
};

export function NotificationSettingsPanel({ initialSettings, loading, saving, error, onSave }: Props) {
  const [form, setForm] = useState<NotificationSettings>(EMPTY_SETTINGS);
  const [submitError, setSubmitError] = useState("");

  useEffect(() => {
    if (initialSettings) {
      setForm(initialSettings);
    }
  }, [initialSettings]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitError("");
    try {
      await onSave(form);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Bildirim ayarları kaydedilemedi.");
    }
  };

  return (
    <section className="tab-panel">
      <div className="panel-head">
        <h3>Bildirim Ayarları</h3>
      </div>
      <form className="settings-modal notification-settings-panel" onSubmit={handleSubmit}>
        <label className="notify-option">
          <input
            type="checkbox"
            checked={form.smtp_enabled}
            onChange={(event) => setForm((prev) => ({ ...prev, smtp_enabled: event.target.checked }))}
          />
          SMTP Aktif
        </label>
        <label>
          SMTP Sunucu
          <input
            value={form.smtp_host}
            onChange={(event) => setForm((prev) => ({ ...prev, smtp_host: event.target.value }))}
            placeholder="smtp.ornek.com"
          />
        </label>
        <label>
          SMTP Port
          <input
            type="number"
            min={1}
            max={65535}
            value={form.smtp_port}
            onChange={(event) => setForm((prev) => ({ ...prev, smtp_port: Number(event.target.value) || 0 }))}
          />
        </label>
        <label>
          SMTP Kullanıcı Adı
          <input
            value={form.smtp_username}
            onChange={(event) => setForm((prev) => ({ ...prev, smtp_username: event.target.value }))}
          />
        </label>
        <label>
          SMTP Şifre
          <input
            type="password"
            value={form.smtp_password}
            onChange={(event) => setForm((prev) => ({ ...prev, smtp_password: event.target.value }))}
          />
        </label>
        <label>
          Gönderen E-posta
          <input
            type="email"
            value={form.smtp_from_email}
            onChange={(event) => setForm((prev) => ({ ...prev, smtp_from_email: event.target.value }))}
            placeholder="alarm@firma.com"
          />
        </label>

        <label className="notify-option">
          <input
            type="checkbox"
            checked={form.sms_enabled}
            onChange={(event) => setForm((prev) => ({ ...prev, sms_enabled: event.target.checked }))}
          />
          SMS Aktif
        </label>
        <label>
          SMS Sağlayıcı
          <input
            value={form.sms_provider}
            onChange={(event) => setForm((prev) => ({ ...prev, sms_provider: event.target.value }))}
            placeholder="mock / netgsm / twilio"
          />
        </label>
        <label>
          SMS API URL
          <input
            value={form.sms_api_url}
            onChange={(event) => setForm((prev) => ({ ...prev, sms_api_url: event.target.value }))}
            placeholder="https://..."
          />
        </label>
        <label>
          SMS API Key
          <input
            value={form.sms_api_key}
            onChange={(event) => setForm((prev) => ({ ...prev, sms_api_key: event.target.value }))}
          />
        </label>

        {loading ? <p className="helper-text">Ayarlar yükleniyor...</p> : null}
        {error ? <p className="error-text">{error}</p> : null}
        {submitError ? <p className="error-text">{submitError}</p> : null}
        <div className="settings-actions">
          <button type="submit" disabled={saving}>
            {saving ? "Kaydediliyor..." : "Kaydet"}
          </button>
        </div>
      </form>
    </section>
  );
}
