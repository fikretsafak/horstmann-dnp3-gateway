import { useEffect, useMemo, useState, type FormEvent } from "react";
import type { SignalCatalogRow, SignalDataType, SignalLiveRow, SignalSource, UserRole } from "../../shared/types";

type Props = {
  role: UserRole;
  signals: SignalCatalogRow[];
  liveValues: SignalLiveRow[];
  loading: boolean;
  liveLoading: boolean;
  error?: string;
  onCreate: (payload: Omit<SignalCatalogRow, "id">) => Promise<void>;
  onUpdate: (signalKey: string, payload: Partial<Omit<SignalCatalogRow, "id" | "key">>) => Promise<void>;
  onDelete: (signalKey: string) => Promise<void>;
  onRefreshLive: () => Promise<void>;
};

type SubTab = "catalog" | "live";
type SourceFilter = "all" | SignalSource;
type DataTypeFilter = "all" | SignalDataType;

const DATA_TYPES: SignalDataType[] = [
  "analog",
  "analog_output",
  "binary",
  "binary_output",
  "counter",
  "string"
];

const SOURCES: SignalSource[] = ["master", "sat01", "sat02"];

const SOURCE_LABEL: Record<SignalSource, string> = {
  master: "Master",
  sat01: "Satellite 01",
  sat02: "Satellite 02"
};

const DATA_TYPE_LABEL: Record<SignalDataType, string> = {
  analog: "Analog",
  analog_output: "Analog Out",
  binary: "Binary",
  binary_output: "Binary Out",
  counter: "Counter",
  string: "String"
};

const EMPTY_FORM: Omit<SignalCatalogRow, "id"> = {
  key: "",
  label: "",
  unit: "",
  description: "",
  source: "master",
  dnp3_class: "Class 1",
  data_type: "analog",
  dnp3_object_group: 30,
  dnp3_index: 0,
  scale: 1.0,
  offset: 0.0,
  supports_alarm: false,
  is_active: true,
  display_order: 0
};

export function SignalsPage({
  role,
  signals,
  liveValues,
  loading,
  liveLoading,
  error,
  onCreate,
  onUpdate,
  onDelete,
  onRefreshLive
}: Props) {
  const canEdit = role === "installer";
  const [subTab, setSubTab] = useState<SubTab>("catalog");
  const [selectedKey, setSelectedKey] = useState<string>("");
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState<Omit<SignalCatalogRow, "id">>(EMPTY_FORM);
  const [localError, setLocalError] = useState("");
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("all");
  const [dataTypeFilter, setDataTypeFilter] = useState<DataTypeFilter>("all");
  const [searchTerm, setSearchTerm] = useState("");

  const filteredSignals = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    return signals.filter((signal) => {
      if (sourceFilter !== "all" && signal.source !== sourceFilter) return false;
      if (dataTypeFilter !== "all" && signal.data_type !== dataTypeFilter) return false;
      if (!q) return true;
      return (
        signal.label.toLowerCase().includes(q) ||
        signal.key.toLowerCase().includes(q) ||
        (signal.description ?? "").toLowerCase().includes(q)
      );
    });
  }, [signals, sourceFilter, dataTypeFilter, searchTerm]);

  const selected = useMemo(
    () => signals.find((signal) => signal.key === selectedKey) ?? null,
    [signals, selectedKey]
  );

  const [editLabel, setEditLabel] = useState("");
  const [editUnit, setEditUnit] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editSource, setEditSource] = useState<SignalSource>("master");
  const [editDnp3Class, setEditDnp3Class] = useState("Class 1");
  const [editDataType, setEditDataType] = useState<SignalDataType>("analog");
  const [editGroup, setEditGroup] = useState("30");
  const [editIndex, setEditIndex] = useState("0");
  const [editScale, setEditScale] = useState("1");
  const [editOffset, setEditOffset] = useState("0");
  const [editSupportsAlarm, setEditSupportsAlarm] = useState(false);
  const [editIsActive, setEditIsActive] = useState(true);
  const [editDisplayOrder, setEditDisplayOrder] = useState("0");

  useEffect(() => {
    if (selected) {
      setEditLabel(selected.label);
      setEditUnit(selected.unit ?? "");
      setEditDescription(selected.description ?? "");
      setEditSource(selected.source);
      setEditDnp3Class(selected.dnp3_class);
      setEditDataType(selected.data_type);
      setEditGroup(String(selected.dnp3_object_group));
      setEditIndex(String(selected.dnp3_index));
      setEditScale(String(selected.scale));
      setEditOffset(String(selected.offset));
      setEditSupportsAlarm(selected.supports_alarm);
      setEditIsActive(selected.is_active);
      setEditDisplayOrder(String(selected.display_order));
    }
  }, [selected]);

  const handleSave = async () => {
    if (!selected) return;
    setLocalError("");
    try {
      await onUpdate(selected.key, {
        label: editLabel,
        unit: editUnit.trim() || null,
        description: editDescription.trim() || null,
        source: editSource,
        dnp3_class: editDnp3Class,
        data_type: editDataType,
        dnp3_object_group: Number(editGroup),
        dnp3_index: Number(editIndex),
        scale: Number(editScale),
        offset: Number(editOffset),
        supports_alarm: editSupportsAlarm,
        is_active: editIsActive,
        display_order: Number(editDisplayOrder)
      });
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "Sinyal güncellenemedi.");
    }
  };

  const handleDelete = async () => {
    if (!selected) return;
    if (!window.confirm(`"${selected.label}" sinyali silinsin mi?`)) return;
    setLocalError("");
    try {
      await onDelete(selected.key);
      setSelectedKey("");
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "Sinyal silinemedi.");
    }
  };

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLocalError("");
    try {
      await onCreate({
        ...createForm,
        unit: createForm.unit?.toString().trim() || null,
        description: createForm.description?.toString().trim() || null,
        dnp3_object_group: Number(createForm.dnp3_object_group),
        dnp3_index: Number(createForm.dnp3_index),
        scale: Number(createForm.scale),
        offset: Number(createForm.offset),
        display_order: Number(createForm.display_order)
      });
      setShowCreate(false);
      setCreateForm(EMPTY_FORM);
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "Sinyal oluşturulamadı.");
    }
  };

  return (
    <section className="tab-panel signals-panel">
      <div className="subtabs">
        <button className={subTab === "catalog" ? "active" : ""} onClick={() => setSubTab("catalog")}>
          Sinyal Listesi
        </button>
        <button
          className={subTab === "live" ? "active" : ""}
          onClick={() => {
            setSubTab("live");
            void onRefreshLive();
          }}
        >
          Canlı Değerler
        </button>
      </div>

      {subTab === "catalog" ? (
        <div className="device-management-layout signals-layout">
          <div className="device-management-left">
            <h4>Standart Sinyaller</h4>
            {canEdit ? (
              <div className="section-actions">
                <button className="add-user-btn full-width-btn" onClick={() => setShowCreate(true)}>
                  Sinyal Ekle
                </button>
              </div>
            ) : (
              <p className="helper-text">
                Sinyal listesini yalnızca <strong>kurulumcu</strong> (installer) rolü düzenleyebilir.
              </p>
            )}
            <div className="signals-filter-bar">
              <input
                type="search"
                placeholder="Ara (etiket / key)..."
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
              />
              <select
                value={sourceFilter}
                onChange={(event) => setSourceFilter(event.target.value as SourceFilter)}
              >
                <option value="all">Tüm Kaynaklar</option>
                {SOURCES.map((src) => (
                  <option key={src} value={src}>
                    {SOURCE_LABEL[src]}
                  </option>
                ))}
              </select>
              <select
                value={dataTypeFilter}
                onChange={(event) => setDataTypeFilter(event.target.value as DataTypeFilter)}
              >
                <option value="all">Tüm Tipler</option>
                {DATA_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {DATA_TYPE_LABEL[type]}
                  </option>
                ))}
              </select>
              <span className="helper-text">
                {filteredSignals.length} / {signals.length}
              </span>
            </div>
            {loading ? <p>Yükleniyor...</p> : null}
            <div className="device-group-list">
              {filteredSignals.map((signal) => (
                <button
                  key={signal.key}
                  className={`device-group-item device-item ${selectedKey === signal.key ? "active" : ""}`}
                  onClick={() => setSelectedKey(signal.key)}
                >
                  <div className="device-title-row">
                    <strong>{signal.label}</strong>
                    <span className={`badge badge-source badge-source-${signal.source}`}>
                      {SOURCE_LABEL[signal.source]}
                    </span>
                    <span className={`badge badge-${signal.data_type}`}>
                      {DATA_TYPE_LABEL[signal.data_type]}
                    </span>
                  </div>
                  <div className="device-meta-row">
                    <span>{signal.key}</span>
                    <span>G{signal.dnp3_object_group} / i{signal.dnp3_index}</span>
                  </div>
                </button>
              ))}
              {filteredSignals.length === 0 && !loading ? (
                <p className="helper-text">
                  {signals.length === 0 ? "Henüz sinyal tanımlı değil." : "Filtreye uygun sinyal yok."}
                </p>
              ) : null}
            </div>
          </div>

          <div className="device-management-right signals-detail">
            <h4>Sinyal Detayı</h4>
            {!selected ? (
              <p className="helper-text">Detay için soldan bir sinyal seçin.</p>
            ) : (
              <div className="device-detail-form">
                <label>
                  Key
                  <input value={selected.key} disabled readOnly />
                </label>
                <label>
                  Etiket
                  <input
                    value={editLabel}
                    onChange={(event) => setEditLabel(event.target.value)}
                    disabled={!canEdit}
                  />
                </label>
                <label>
                  Birim
                  <input
                    value={editUnit}
                    onChange={(event) => setEditUnit(event.target.value)}
                    disabled={!canEdit}
                  />
                </label>
                <label>
                  Açıklama
                  <input
                    value={editDescription}
                    onChange={(event) => setEditDescription(event.target.value)}
                    disabled={!canEdit}
                  />
                </label>
                <label>
                  Kaynak (Master/Satellite)
                  <select
                    value={editSource}
                    onChange={(event) => setEditSource(event.target.value as SignalSource)}
                    disabled={!canEdit}
                  >
                    {SOURCES.map((src) => (
                      <option key={src} value={src}>
                        {SOURCE_LABEL[src]}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  DNP3 Class
                  <input
                    value={editDnp3Class}
                    onChange={(event) => setEditDnp3Class(event.target.value)}
                    disabled={!canEdit}
                    placeholder="Class 1 / Class 2 / -"
                  />
                </label>
                <label>
                  Veri Tipi
                  <select
                    value={editDataType}
                    onChange={(event) => setEditDataType(event.target.value as SignalDataType)}
                    disabled={!canEdit}
                  >
                    {DATA_TYPES.map((type) => (
                      <option key={type} value={type}>
                        {DATA_TYPE_LABEL[type]}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  DNP3 Object Group
                  <input
                    type="number"
                    value={editGroup}
                    onChange={(event) => setEditGroup(event.target.value)}
                    disabled={!canEdit}
                  />
                </label>
                <label>
                  DNP3 Index
                  <input
                    type="number"
                    value={editIndex}
                    onChange={(event) => setEditIndex(event.target.value)}
                    disabled={!canEdit}
                  />
                </label>
                <label>
                  Scale
                  <input
                    type="number"
                    step="0.0001"
                    value={editScale}
                    onChange={(event) => setEditScale(event.target.value)}
                    disabled={!canEdit}
                  />
                </label>
                <label>
                  Offset
                  <input
                    type="number"
                    step="0.0001"
                    value={editOffset}
                    onChange={(event) => setEditOffset(event.target.value)}
                    disabled={!canEdit}
                  />
                </label>
                <label className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={editSupportsAlarm}
                    onChange={(event) => setEditSupportsAlarm(event.target.checked)}
                    disabled={!canEdit}
                  />
                  Alarm destekli
                </label>
                <label className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={editIsActive}
                    onChange={(event) => setEditIsActive(event.target.checked)}
                    disabled={!canEdit}
                  />
                  Aktif
                </label>
                <label>
                  Sıra
                  <input
                    type="number"
                    value={editDisplayOrder}
                    onChange={(event) => setEditDisplayOrder(event.target.value)}
                    disabled={!canEdit}
                  />
                </label>
                {canEdit ? (
                  <div className="device-form-actions">
                    <button type="button" className="primary-btn" onClick={() => void handleSave()}>
                      Kaydet
                    </button>
                    <button type="button" className="danger-btn" onClick={() => void handleDelete()}>
                      Sil
                    </button>
                  </div>
                ) : null}
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="live-values-panel">
          <div className="section-actions">
            <button className="secondary-btn" onClick={() => void onRefreshLive()} disabled={liveLoading}>
              {liveLoading ? "Yenileniyor..." : "Yenile"}
            </button>
          </div>
          <div className="live-values-table-wrap">
            <table className="values-table">
              <thead>
                <tr>
                  <th>Cihaz</th>
                  <th>Kaynak</th>
                  <th>Sinyal</th>
                  <th>Değer</th>
                  <th>Birim</th>
                  <th>Kalite</th>
                  <th>Zaman</th>
                </tr>
              </thead>
              <tbody>
                {liveValues.map((item, idx) => (
                  <tr key={`${item.device_code}-${item.signal_key}-${idx}`}>
                    <td>{item.device_name} ({item.device_code})</td>
                    <td>
                      <span className={`badge badge-source badge-source-${item.source}`}>
                        {SOURCE_LABEL[item.source] ?? item.source}
                      </span>
                    </td>
                    <td>{item.signal_label}</td>
                    <td>{item.value}</td>
                    <td>{item.unit ?? "-"}</td>
                    <td>{item.quality}</td>
                    <td>{new Date(item.source_timestamp).toLocaleString("tr-TR")}</td>
                  </tr>
                ))}
                {liveValues.length === 0 && !liveLoading ? (
                  <tr>
                    <td colSpan={7} className="helper-text" style={{ textAlign: "center" }}>
                      Henüz canlı değer yok.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {(localError || error) ? <p className="error-text">{localError || error}</p> : null}

      {showCreate ? (
        <div className="settings-modal-backdrop">
          <form className="settings-modal" onSubmit={handleCreate}>
            <h3>Yeni Sinyal Ekle</h3>
            <label>
              Key
              <input
                value={createForm.key}
                onChange={(event) => setCreateForm({ ...createForm, key: event.target.value })}
                required
              />
            </label>
            <label>
              Etiket
              <input
                value={createForm.label}
                onChange={(event) => setCreateForm({ ...createForm, label: event.target.value })}
                required
              />
            </label>
            <label>
              Birim
              <input
                value={createForm.unit ?? ""}
                onChange={(event) => setCreateForm({ ...createForm, unit: event.target.value })}
              />
            </label>
            <label>
              Kaynak (Master/Satellite)
              <select
                value={createForm.source}
                onChange={(event) => setCreateForm({ ...createForm, source: event.target.value as SignalSource })}
              >
                {SOURCES.map((src) => (
                  <option key={src} value={src}>
                    {SOURCE_LABEL[src]}
                  </option>
                ))}
              </select>
            </label>
            <label>
              DNP3 Class
              <input
                value={createForm.dnp3_class}
                onChange={(event) => setCreateForm({ ...createForm, dnp3_class: event.target.value })}
                placeholder="Class 1 / Class 2"
              />
            </label>
            <label>
              Veri Tipi
              <select
                value={createForm.data_type}
                onChange={(event) => setCreateForm({ ...createForm, data_type: event.target.value as SignalDataType })}
              >
                {DATA_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {DATA_TYPE_LABEL[type]}
                  </option>
                ))}
              </select>
            </label>
            <label>
              DNP3 Object Group
              <input
                type="number"
                value={createForm.dnp3_object_group}
                onChange={(event) => setCreateForm({ ...createForm, dnp3_object_group: Number(event.target.value) })}
              />
            </label>
            <label>
              DNP3 Index
              <input
                type="number"
                value={createForm.dnp3_index}
                onChange={(event) => setCreateForm({ ...createForm, dnp3_index: Number(event.target.value) })}
              />
            </label>
            <label>
              Scale
              <input
                type="number"
                step="0.0001"
                value={createForm.scale}
                onChange={(event) => setCreateForm({ ...createForm, scale: Number(event.target.value) })}
              />
            </label>
            <label>
              Offset
              <input
                type="number"
                step="0.0001"
                value={createForm.offset}
                onChange={(event) => setCreateForm({ ...createForm, offset: Number(event.target.value) })}
              />
            </label>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={createForm.supports_alarm}
                onChange={(event) => setCreateForm({ ...createForm, supports_alarm: event.target.checked })}
              />
              Alarm destekli
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
