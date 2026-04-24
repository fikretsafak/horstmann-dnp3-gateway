import { useMemo, useState, type FormEvent } from "react";
import type {
  AlarmComparator,
  AlarmLevel,
  AlarmRuleRow,
  SignalCatalogRow,
  UserRole
} from "../../shared/types";

type Props = {
  role: UserRole;
  rules: AlarmRuleRow[];
  signals: SignalCatalogRow[];
  loading: boolean;
  error?: string;
  onCreate: (payload: Omit<AlarmRuleRow, "id">) => Promise<void>;
  onUpdate: (ruleId: number, payload: Partial<Omit<AlarmRuleRow, "id" | "signal_key">>) => Promise<void>;
  onDelete: (ruleId: number) => Promise<void>;
};

const LEVELS: AlarmLevel[] = ["info", "warning", "critical"];
const COMPARATORS: Array<{ value: AlarmComparator; label: string }> = [
  { value: "gt", label: "> (büyüktür)" },
  { value: "gte", label: ">= (büyük-eşit)" },
  { value: "lt", label: "< (küçüktür)" },
  { value: "lte", label: "<= (küçük-eşit)" },
  { value: "eq", label: "= (eşittir)" },
  { value: "ne", label: "!= (eşit değil)" },
  { value: "between", label: "arası (low..high)" },
  { value: "outside", label: "dışı (low..high dışı)" },
  { value: "boolean_true", label: "BOOL = TRUE" },
  { value: "boolean_false", label: "BOOL = FALSE" }
];

const EMPTY_FORM: Omit<AlarmRuleRow, "id"> = {
  signal_key: "",
  name: "",
  description: "",
  level: "warning",
  comparator: "gt",
  threshold: 0,
  threshold_high: null,
  hysteresis: 0,
  debounce_sec: 0,
  device_code_filter: "",
  is_active: true
};

export function AlarmRulesPage({
  role,
  rules,
  signals,
  loading,
  error,
  onCreate,
  onUpdate,
  onDelete
}: Props) {
  const canEdit = role === "installer";
  const alarmableSignals = useMemo(() => signals.filter((signal) => signal.supports_alarm), [signals]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<Omit<AlarmRuleRow, "id">>({ ...EMPTY_FORM });
  const [localError, setLocalError] = useState("");

  const signalLabel = (signalKey: string) => {
    const signal = signals.find((item) => item.key === signalKey);
    return signal ? `${signal.label} (${signal.key})` : signalKey;
  };

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLocalError("");
    if (!form.signal_key) {
      setLocalError("Bir sinyal seçin.");
      return;
    }
    try {
      await onCreate({
        ...form,
        description: form.description?.toString().trim() || null,
        device_code_filter: form.device_code_filter?.toString().trim() || null,
        threshold: Number(form.threshold),
        threshold_high: form.threshold_high === null || form.threshold_high === undefined
          ? null
          : Number(form.threshold_high),
        hysteresis: Number(form.hysteresis),
        debounce_sec: Number(form.debounce_sec)
      });
      setShowCreate(false);
      setForm({ ...EMPTY_FORM });
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "Alarm kuralı oluşturulamadı.");
    }
  };

  const handleToggle = async (rule: AlarmRuleRow) => {
    setLocalError("");
    try {
      await onUpdate(rule.id, { is_active: !rule.is_active });
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "Alarm kuralı güncellenemedi.");
    }
  };

  const handleDelete = async (rule: AlarmRuleRow) => {
    if (!window.confirm(`"${rule.name}" alarm kuralı silinsin mi?`)) return;
    setLocalError("");
    try {
      await onDelete(rule.id);
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "Alarm kuralı silinemedi.");
    }
  };

  return (
    <section className="tab-panel alarm-rules-panel">
      <div className="section-header">
        <h4>Alarm Yönetimi</h4>
        {canEdit ? (
          <button className="add-user-btn" onClick={() => setShowCreate(true)} disabled={alarmableSignals.length === 0}>
            Yeni Alarm Kuralı
          </button>
        ) : null}
      </div>

      {!canEdit ? (
        <p className="helper-text">
          Alarm kurallarını yalnızca <strong>kurulumcu</strong> (installer) rolü düzenleyebilir.
        </p>
      ) : null}
      {alarmableSignals.length === 0 ? (
        <p className="helper-text">
          Hiçbir sinyal alarmı desteklemiyor. Sinyaller sekmesinden ilgili sinyallerde "Alarm destekli" seçeneğini aktifleştirin.
        </p>
      ) : null}

      {loading ? <p>Yükleniyor...</p> : null}

      <div className="values-table-wrap">
        <table className="values-table">
          <thead>
            <tr>
              <th>Sinyal</th>
              <th>Ad</th>
              <th>Seviye</th>
              <th>Koşul</th>
              <th>Eşik</th>
              <th>Histerezis</th>
              <th>Debounce (sn)</th>
              <th>Cihaz Filtresi</th>
              <th>Durum</th>
              {canEdit ? <th style={{ textAlign: "right" }}>İşlem</th> : null}
            </tr>
          </thead>
          <tbody>
            {rules.map((rule) => (
              <tr key={rule.id}>
                <td>{signalLabel(rule.signal_key)}</td>
                <td>{rule.name}</td>
                <td>
                  <span className={`badge level-${rule.level}`}>{rule.level}</span>
                </td>
                <td>{rule.comparator}</td>
                <td>
                  {rule.comparator === "between" || rule.comparator === "outside"
                    ? `${rule.threshold} .. ${rule.threshold_high ?? "?"}`
                    : rule.threshold}
                </td>
                <td>{rule.hysteresis}</td>
                <td>{rule.debounce_sec}</td>
                <td>{rule.device_code_filter || <span className="helper-text">tümü</span>}</td>
                <td>{rule.is_active ? "Aktif" : "Pasif"}</td>
                {canEdit ? (
                  <td style={{ textAlign: "right" }}>
                    <button
                      className="secondary-btn action-btn"
                      type="button"
                      onClick={() => void handleToggle(rule)}
                      title={rule.is_active ? "Pasif Yap" : "Aktif Yap"}
                    >
                      {rule.is_active ? "Pasifleştir" : "Aktifleştir"}
                    </button>
                    <button
                      className="danger-btn action-btn"
                      type="button"
                      onClick={() => void handleDelete(rule)}
                      style={{ marginLeft: 6 }}
                    >
                      Sil
                    </button>
                  </td>
                ) : null}
              </tr>
            ))}
            {rules.length === 0 && !loading ? (
              <tr>
                <td colSpan={canEdit ? 10 : 9} className="helper-text" style={{ textAlign: "center" }}>
                  Henüz alarm kuralı tanımlı değil.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      {(localError || error) ? <p className="error-text">{localError || error}</p> : null}

      {showCreate ? (
        <div className="settings-modal-backdrop">
          <form className="settings-modal" onSubmit={handleCreate}>
            <h3>Yeni Alarm Kuralı</h3>
            <label>
              Sinyal
              <select
                value={form.signal_key}
                onChange={(event) => setForm({ ...form, signal_key: event.target.value })}
                required
              >
                <option value="" disabled>
                  Seçiniz
                </option>
                {alarmableSignals.map((signal) => (
                  <option key={signal.key} value={signal.key}>
                    {signal.label} ({signal.key})
                  </option>
                ))}
              </select>
            </label>
            <label>
              Kural Adı
              <input
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                required
              />
            </label>
            <label>
              Açıklama
              <input
                value={form.description ?? ""}
                onChange={(event) => setForm({ ...form, description: event.target.value })}
              />
            </label>
            <label>
              Seviye
              <select
                value={form.level}
                onChange={(event) => setForm({ ...form, level: event.target.value as AlarmLevel })}
              >
                {LEVELS.map((level) => (
                  <option key={level} value={level}>
                    {level}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Koşul
              <select
                value={form.comparator}
                onChange={(event) => setForm({ ...form, comparator: event.target.value as AlarmComparator })}
              >
                {COMPARATORS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Eşik (low)
              <input
                type="number"
                step="0.0001"
                value={form.threshold}
                onChange={(event) => setForm({ ...form, threshold: Number(event.target.value) })}
              />
            </label>
            {form.comparator === "between" || form.comparator === "outside" ? (
              <label>
                Eşik (high)
                <input
                  type="number"
                  step="0.0001"
                  value={form.threshold_high ?? 0}
                  onChange={(event) => setForm({ ...form, threshold_high: Number(event.target.value) })}
                />
              </label>
            ) : null}
            <label>
              Histerezis
              <input
                type="number"
                step="0.0001"
                value={form.hysteresis}
                onChange={(event) => setForm({ ...form, hysteresis: Number(event.target.value) })}
              />
            </label>
            <label>
              Debounce (sn)
              <input
                type="number"
                value={form.debounce_sec}
                onChange={(event) => setForm({ ...form, debounce_sec: Number(event.target.value) })}
              />
            </label>
            <label>
              Cihaz Kodu Filtresi (virgülle ayrılmış, boş = tümü)
              <input
                value={form.device_code_filter ?? ""}
                onChange={(event) => setForm({ ...form, device_code_filter: event.target.value })}
              />
            </label>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
              />
              Aktif
            </label>
            <div className="modal-actions">
              <button type="button" className="secondary-btn" onClick={() => setShowCreate(false)}>
                İptal
              </button>
              <button type="submit" className="primary-btn">
                Oluştur
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </section>
  );
}
