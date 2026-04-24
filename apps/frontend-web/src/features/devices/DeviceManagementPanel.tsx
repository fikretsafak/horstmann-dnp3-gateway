import { useEffect, useMemo, useState, type FormEvent } from "react";
import { MapContainer, Marker, TileLayer, useMapEvents } from "react-leaflet";
import L from "leaflet";
import type { DeviceRow, Gateway } from "../../shared/types";

type Props = {
  role: "operator" | "engineer" | "installer";
  gateways: Gateway[];
  devices: DeviceRow[];
  onSelectGateway: (gatewayCode: string) => Promise<void>;
  onCreateGateway: (payload: {
    code: string;
    name: string;
    host: string;
    listen_port: number;
    upstream_url: string;
    batch_interval_sec: number;
    max_devices: number;
    device_code_prefix?: string | null;
    token: string;
    is_active: boolean;
  }) => Promise<void>;
  onUpdateGateway: (
    gatewayCode: string,
    payload: { name?: string; host?: string; listen_port?: number; token?: string }
  ) => Promise<void>;
  onDeleteGateway: (gatewayCode: string) => Promise<void>;
  onCreate: (payload: {
    code: string;
    name: string;
    description?: string | null;
    gateway_code?: string | null;
    ip_address: string;
    dnp3_address: number;
    poll_interval_sec: number;
    timeout_ms: number;
    retry_count: number;
    signal_profile: string;
    latitude: number;
    longitude: number;
  }) => Promise<void>;
  onUpdate: (
    deviceCode: string,
    payload: {
      name?: string;
      description?: string | null;
      gateway_code?: string | null;
      ip_address?: string;
      dnp3_address?: number;
      poll_interval_sec?: number;
      timeout_ms?: number;
      retry_count?: number;
      latitude?: number;
      longitude?: number;
    }
  ) => Promise<void>;
  onDelete: (deviceCode: string) => Promise<void>;
};

export function DeviceManagementPanel({
  role,
  gateways,
  devices,
  onSelectGateway,
  onCreateGateway,
  onUpdateGateway,
  onDeleteGateway,
  onCreate,
  onUpdate,
  onDelete
}: Props) {
  const canManageGateways = role === "installer";
  const [selectedGatewayCode, setSelectedGatewayCode] = useState(gateways[0]?.code ?? "");
  const [selectedDeviceCode, setSelectedDeviceCode] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showGatewayCreateModal, setShowGatewayCreateModal] = useState(false);
  const [showGatewayEditModal, setShowGatewayEditModal] = useState(false);
  const [error, setError] = useState("");

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [ipAddress, setIpAddress] = useState("");
  const [dnp3Address, setDnp3Address] = useState("1");
  const [pollIntervalSec, setPollIntervalSec] = useState("5");
  const [timeoutMs, setTimeoutMs] = useState("3000");
  const [retryCount, setRetryCount] = useState("2");
  const [latitude, setLatitude] = useState("0");
  const [longitude, setLongitude] = useState("0");

  const [createCode, setCreateCode] = useState("");
  const [createName, setCreateName] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [createIpAddress, setCreateIpAddress] = useState("");
  const [createDnp3Address, setCreateDnp3Address] = useState("1");
  const [createPollIntervalSec, setCreatePollIntervalSec] = useState("5");
  const [createTimeoutMs, setCreateTimeoutMs] = useState("3000");
  const [createRetryCount, setCreateRetryCount] = useState("2");
  const [createLatitude, setCreateLatitude] = useState("0");
  const [createLongitude, setCreateLongitude] = useState("0");
  const [gatewayCode, setGatewayCode] = useState("");
  const [gatewayName, setGatewayName] = useState("");
  const [gatewayHost, setGatewayHost] = useState("");
  const [gatewayPort, setGatewayPort] = useState("20000");
  const [gatewayToken, setGatewayToken] = useState("");
  const [editGatewayCode, setEditGatewayCode] = useState("");
  const [editGatewayName, setEditGatewayName] = useState("");
  const [editGatewayHost, setEditGatewayHost] = useState("");
  const [editGatewayPort, setEditGatewayPort] = useState("20000");
  const [editGatewayToken, setEditGatewayToken] = useState("");
  const [showMapPicker, setShowMapPicker] = useState(false);
  const [pickerLat, setPickerLat] = useState(39);
  const [pickerLon, setPickerLon] = useState(35);

  const selectedDevice = useMemo(
    () => devices.find((item) => item.code === selectedDeviceCode) ?? null,
    [devices, selectedDeviceCode]
  );

  const isGatewayOnline = (gateway: Gateway) => {
    if (!gateway.is_active || !gateway.last_seen_at) return false;
    const diffMs = Date.now() - new Date(gateway.last_seen_at).getTime();
    return diffMs <= 2 * 60 * 1000;
  };

  useEffect(() => {
    if (!gateways.length) {
      setSelectedGatewayCode("");
      return;
    }
    const exists = gateways.some((item) => item.code === selectedGatewayCode);
    if (!selectedGatewayCode || !exists) {
      const nextGatewayCode = gateways[0].code;
      setSelectedGatewayCode(nextGatewayCode);
      void onSelectGateway(nextGatewayCode);
    }
  }, [gateways, selectedGatewayCode, onSelectGateway]);

  const applySelectedDeviceToForm = (device: DeviceRow) => {
    setName(device.name);
    setDescription(device.description ?? "");
    setIpAddress(device.ipAddress ?? "");
    setDnp3Address(String(device.dnp3Address ?? 1));
    setPollIntervalSec(String(device.pollIntervalSec ?? 5));
    setTimeoutMs(String(device.timeoutMs ?? 3000));
    setRetryCount(String(device.retryCount ?? 2));
    setLatitude(String(device.latitude ?? 0));
    setLongitude(String(device.longitude ?? 0));
  };

  const handleGatewaySelect = async (gatewayCode: string) => {
    setSelectedGatewayCode(gatewayCode);
    setSelectedDeviceCode("");
    setError("");
    await onSelectGateway(gatewayCode);
  };

  const handleDeviceSelect = (device: DeviceRow) => {
    setSelectedDeviceCode(device.code);
    applySelectedDeviceToForm(device);
  };

  const handleSaveDevice = async () => {
    if (!selectedDevice) return;
    setError("");
    try {
      await onUpdate(selectedDevice.code, {
        name,
        description: description.trim() || null,
        gateway_code: selectedGatewayCode || null,
        ip_address: ipAddress,
        dnp3_address: Number(dnp3Address),
        poll_interval_sec: Number(pollIntervalSec),
        timeout_ms: Number(timeoutMs),
        retry_count: Number(retryCount),
        latitude: Number(latitude),
        longitude: Number(longitude)
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cihaz güncellenemedi.");
    }
  };

  const handleDeleteDevice = async () => {
    if (!selectedDevice) return;
    if (!window.confirm(`"${selectedDevice.name}" cihazı silinsin mi?`)) return;
    setError("");
    try {
      await onDelete(selectedDevice.code);
      setSelectedDeviceCode("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cihaz silinemedi.");
    }
  };

  const handleCreateDevice = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    try {
      await onCreate({
        code: createCode,
        name: createName,
        description: createDescription.trim() || null,
        gateway_code: selectedGatewayCode || null,
        ip_address: createIpAddress,
        dnp3_address: Number(createDnp3Address),
        poll_interval_sec: Number(createPollIntervalSec),
        timeout_ms: Number(createTimeoutMs),
        retry_count: Number(createRetryCount),
        signal_profile: "horstmann_sn2_fixed",
        latitude: Number(createLatitude),
        longitude: Number(createLongitude)
      });
      setShowCreateModal(false);
      setCreateCode("");
      setCreateName("");
      setCreateDescription("");
      setCreateIpAddress("");
      setCreateDnp3Address("1");
      setCreatePollIntervalSec("5");
      setCreateTimeoutMs("3000");
      setCreateRetryCount("2");
      setCreateLatitude("0");
      setCreateLongitude("0");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cihaz oluşturulamadı.");
    }
  };

  const handleCreateGateway = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    try {
      await onCreateGateway({
        code: gatewayCode,
        name: gatewayName,
        host: gatewayHost,
        listen_port: Number(gatewayPort),
        upstream_url: "/api/v1/telemetry/gateway/{gateway_code}",
        batch_interval_sec: 5,
        max_devices: 200,
        device_code_prefix: null,
        token: gatewayToken,
        is_active: true
      });
      setShowGatewayCreateModal(false);
      setGatewayCode("");
      setGatewayName("");
      setGatewayHost("");
      setGatewayPort("20000");
      setGatewayToken("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gateway oluşturulamadı.");
    }
  };

  const handleDeleteGateway = async (gatewayCode?: string) => {
    const codeToDelete = gatewayCode ?? selectedGatewayCode;
    if (!codeToDelete) return;
    const gateway = gateways.find((item) => item.code === codeToDelete);
    if (!gateway) return;
    if (!window.confirm(`"${gateway.name}" gateway silinsin mi?`)) return;
    setError("");
    try {
      await onDeleteGateway(codeToDelete);
      setSelectedGatewayCode("");
      setSelectedDeviceCode("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gateway silinemedi.");
    }
  };

  const handleStartGatewayEdit = (gateway: Gateway) => {
    setEditGatewayCode(gateway.code);
    setEditGatewayName(gateway.name);
    setEditGatewayHost(gateway.host);
    setEditGatewayPort(String(gateway.listen_port));
    setEditGatewayToken(gateway.token);
    setShowGatewayEditModal(true);
  };

  const handleUpdateGateway = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!editGatewayCode) return;
    setError("");
    try {
      await onUpdateGateway(editGatewayCode, {
        name: editGatewayName,
        host: editGatewayHost,
        listen_port: Number(editGatewayPort),
        token: editGatewayToken
      });
      setShowGatewayEditModal(false);
      if (selectedGatewayCode === editGatewayCode) {
        await onSelectGateway(editGatewayCode);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gateway güncellenemedi.");
    }
  };

  const handleOpenMapPicker = () => {
    setPickerLat(Number(latitude) || 39);
    setPickerLon(Number(longitude) || 35);
    setShowMapPicker(true);
  };

  const handleApplyMapLocation = () => {
    setLatitude(String(pickerLat));
    setLongitude(String(pickerLon));
    setShowMapPicker(false);
  };

  const mapPickerIcon = L.divIcon({
    className: "device-pin-wrapper",
    html: `<span class="device-pin" style="background:#2563eb"></span>`,
    iconSize: [20, 20],
    iconAnchor: [10, 10]
  });

  function LocationPicker() {
    useMapEvents({
      click(event) {
        setPickerLat(Number(event.latlng.lat.toFixed(6)));
        setPickerLon(Number(event.latlng.lng.toFixed(6)));
      }
    });
    return <Marker position={[pickerLat, pickerLon]} icon={mapPickerIcon} />;
  }

  return (
    <section className="tab-panel device-management-panel">
      <div className="device-management-layout">
        <div className="device-management-left">
          <h4>Gatewayler</h4>
          {canManageGateways ? (
            <div className="section-actions">
              <button
                className="secondary-btn action-btn full-width-btn"
                onClick={() => setShowGatewayCreateModal(true)}
              >
                Gateway Ekle
              </button>
            </div>
          ) : null}
          <div className="device-group-list">
            {gateways.map((gateway) => (
              <div
                key={gateway.id}
                className={`device-group-item gateway-item ${selectedGatewayCode === gateway.code ? "active" : ""}`}
              >
                <button className="device-group-main" onClick={() => void handleGatewaySelect(gateway.code)}>
                  <div className="gateway-title-row">
                    <div className="gateway-name-with-status">
                      <span className={`gateway-status ${isGatewayOnline(gateway) ? "online" : "offline"}`}>
                        <span className="gateway-status-dot" />
                      </span>
                      <strong>{gateway.name}</strong>
                    </div>
                    {canManageGateways ? (
                      <div className="item-actions inline-actions">
                        <button
                          type="button"
                          className="secondary-btn action-btn"
                          onClick={() => handleStartGatewayEdit(gateway)}
                          title="Gateway Düzenle"
                          aria-label="Gateway Düzenle"
                        >
                          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                            <path
                              fill="currentColor"
                              d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75zM20.71 7.04a1 1 0 0 0 0-1.41L18.37 3.29a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75z"
                            />
                          </svg>
                        </button>
                        <button
                          type="button"
                          className="danger-btn action-btn"
                          onClick={() => void handleDeleteGateway(gateway.code)}
                          title="Gateway Sil"
                          aria-label="Gateway Sil"
                        >
                          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                            <path
                              fill="currentColor"
                              d="M6 19a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7H6zm3.46-7.12 1.41-1.41L12 11.59l1.12-1.12 1.41 1.41L13.41 13l1.12 1.12-1.41 1.41L12 14.41l-1.12 1.12-1.41-1.41L10.59 13zM15.5 4l-1-1h-5l-1 1H5v2h14V4z"
                            />
                          </svg>
                        </button>
                      </div>
                    ) : null}
                  </div>
                  <span>{gateway.host}</span>
                </button>
              </div>
            ))}
          </div>

        </div>

        <div className="device-management-middle">
          <h4>Cihazlar</h4>
          <div className="section-actions">
            <button className="add-user-btn full-width-btn" onClick={() => setShowCreateModal(true)} disabled={!selectedGatewayCode}>
              Cihaz Ekle
            </button>
          </div>
          <div className="device-group-list">
            {devices.map((device) => (
              <button
                key={device.id}
                className={`device-group-item device-item ${selectedDeviceCode === device.code ? "active" : ""}`}
                onClick={() => handleDeviceSelect(device)}
              >
                <div className="device-title-row">
                  <div className="device-name-with-status">
                    <span className={`device-status-dot ${device.communicationStatus}`} />
                    <strong>{device.name}</strong>
                  </div>
                  <span className="device-status-sr-only">
                    {device.communicationStatus === "online"
                      ? "Haberleşme Var"
                      : device.communicationStatus === "offline"
                        ? "Haberleşme Yok"
                        : "Durum Belirsiz"}
                  </span>
                </div>
                <div className="device-meta-row">
                  <span>{device.code}</span>
                  <span className="device-ip-text">{device.ipAddress ?? "-"}</span>
                </div>
              </button>
            ))}
            {devices.length === 0 ? <p className="helper-text">Bu gateway altında henüz cihaz yok.</p> : null}
          </div>
        </div>

        <div className="device-management-right">
          <h4>Cihaz Özellikleri</h4>
          {!selectedDevice ? (
            <p className="helper-text">Sağ panelde düzenlemek için soldan bir cihaz seçin.</p>
          ) : (
            <div className="device-detail-form">
              <label>
                Cihaz Kodu
                <input value={selectedDevice.code} disabled readOnly />
              </label>
              <label>
                Sinyal Kaynağı
                <input value="Standart Sinyal Kataloğu" disabled readOnly />
              </label>
              <label>
                İsim
                <input value={name} onChange={(event) => setName(event.target.value)} />
              </label>
              <label>
                Açıklama
                <input value={description} onChange={(event) => setDescription(event.target.value)} />
              </label>
              <label>
                IP Adresi
                <input value={ipAddress} onChange={(event) => setIpAddress(event.target.value)} />
              </label>
              <label>
                DNP3 Adresi
                <input type="number" value={dnp3Address} onChange={(event) => setDnp3Address(event.target.value)} />
              </label>
              <label>
                Poll Aralığı (sn)
                <input
                  type="number"
                  min={1}
                  max={3600}
                  value={pollIntervalSec}
                  onChange={(event) => setPollIntervalSec(event.target.value)}
                />
              </label>
              <label>
                Timeout (ms)
                <input
                  type="number"
                  min={100}
                  max={60000}
                  value={timeoutMs}
                  onChange={(event) => setTimeoutMs(event.target.value)}
                />
              </label>
              <label>
                Retry
                <input type="number" min={0} max={10} value={retryCount} onChange={(event) => setRetryCount(event.target.value)} />
              </label>
              <label>
                Enlem
                <input value={latitude} onChange={(event) => setLatitude(event.target.value)} />
              </label>
              <label>
                Boylam
                <input value={longitude} onChange={(event) => setLongitude(event.target.value)} />
              </label>
              <div className="device-form-actions">
                <button type="button" className="secondary-btn" onClick={handleOpenMapPicker}>
                  Haritadan Seç
                </button>
                <button type="button" className="primary-btn" onClick={() => void handleSaveDevice()}>
                  Kaydet
                </button>
                <button type="button" className="danger-btn" onClick={() => void handleDeleteDevice()}>
                  Sil
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {error ? <p className="error-text">{error}</p> : null}

      {showGatewayCreateModal ? (
        <div className="settings-modal-backdrop">
          <form className="settings-modal" onSubmit={handleCreateGateway}>
            <h3>Yeni Gateway Ekle</h3>
            <label>
              Gateway Kodu
              <input value={gatewayCode} onChange={(event) => setGatewayCode(event.target.value)} required />
            </label>
            <label>
              Gateway Adı
              <input value={gatewayName} onChange={(event) => setGatewayName(event.target.value)} required />
            </label>
            <label>
              Host
              <input value={gatewayHost} onChange={(event) => setGatewayHost(event.target.value)} required />
            </label>
            <label>
              Port
              <input
                type="number"
                min={1}
                max={65535}
                value={gatewayPort}
                onChange={(event) => setGatewayPort(event.target.value)}
                required
              />
            </label>
            <label>
              Token
              <input value={gatewayToken} onChange={(event) => setGatewayToken(event.target.value)} required />
            </label>
            <div className="modal-actions">
              <button type="button" className="secondary-btn" onClick={() => setShowGatewayCreateModal(false)}>
                İptal
              </button>
              <button type="submit" className="primary-btn">
                Oluştur
              </button>
            </div>
          </form>
        </div>
      ) : null}

      {showCreateModal ? (
        <div className="settings-modal-backdrop">
          <form className="settings-modal device-create-modal" onSubmit={handleCreateDevice}>
            <h3>Yeni Cihaz Ekle</h3>
            <p className="helper-text">
              Cihaz standart sinyal kataloğundaki tüm sinyalleri otomatik okur. Sinyal adresleri <strong>Sinyaller</strong> sayfasından yönetilir.
            </p>
            <label>
              Cihaz Kodu
              <input value={createCode} onChange={(event) => setCreateCode(event.target.value)} required />
            </label>
            <label>
              Cihaz Adı
              <input value={createName} onChange={(event) => setCreateName(event.target.value)} required />
            </label>
            <label>
              Açıklama
              <input value={createDescription} onChange={(event) => setCreateDescription(event.target.value)} />
            </label>
            <label>
              IP Adresi
              <input value={createIpAddress} onChange={(event) => setCreateIpAddress(event.target.value)} required />
            </label>
            <label>
              DNP3 Adresi
              <input
                type="number"
                min={1}
                value={createDnp3Address}
                onChange={(event) => setCreateDnp3Address(event.target.value)}
                required
              />
            </label>
            <label>
              Poll Aralığı (sn)
              <input
                type="number"
                min={1}
                max={3600}
                value={createPollIntervalSec}
                onChange={(event) => setCreatePollIntervalSec(event.target.value)}
                required
              />
            </label>
            <label>
              Timeout (ms)
              <input
                type="number"
                min={100}
                max={60000}
                value={createTimeoutMs}
                onChange={(event) => setCreateTimeoutMs(event.target.value)}
                required
              />
            </label>
            <label>
              Retry
              <input
                type="number"
                min={0}
                max={10}
                value={createRetryCount}
                onChange={(event) => setCreateRetryCount(event.target.value)}
                required
              />
            </label>
            <label>
              Enlem
              <input value={createLatitude} onChange={(event) => setCreateLatitude(event.target.value)} required />
            </label>
            <label>
              Boylam
              <input value={createLongitude} onChange={(event) => setCreateLongitude(event.target.value)} required />
            </label>
            <div className="modal-actions">
              <button type="button" className="secondary-btn" onClick={() => setShowCreateModal(false)}>
                İptal
              </button>
              <button type="submit" className="primary-btn">
                Oluştur
              </button>
            </div>
          </form>
        </div>
      ) : null}

      {showGatewayEditModal ? (
        <div className="settings-modal-backdrop">
          <form className="settings-modal" onSubmit={handleUpdateGateway}>
            <h3>Gateway Düzenle</h3>
            <label>
              Gateway Kodu
              <input value={editGatewayCode} disabled readOnly />
            </label>
            <label>
              Gateway Adı
              <input value={editGatewayName} onChange={(event) => setEditGatewayName(event.target.value)} required />
            </label>
            <label>
              Host
              <input value={editGatewayHost} onChange={(event) => setEditGatewayHost(event.target.value)} required />
            </label>
            <label>
              Port
              <input
                type="number"
                min={1}
                max={65535}
                value={editGatewayPort}
                onChange={(event) => setEditGatewayPort(event.target.value)}
                required
              />
            </label>
            <label>
              Token
              <input value={editGatewayToken} onChange={(event) => setEditGatewayToken(event.target.value)} required />
            </label>
            <div className="modal-actions">
              <button type="button" className="secondary-btn" onClick={() => setShowGatewayEditModal(false)}>
                İptal
              </button>
              <button type="submit" className="primary-btn">
                Kaydet
              </button>
            </div>
          </form>
        </div>
      ) : null}

      {showMapPicker ? (
        <div className="settings-modal-backdrop">
          <div className="settings-modal map-picker-modal">
            <h3>Haritadan Konum Seç</h3>
            <p className="helper-text">Haritaya tıklayarak cihaz konumunu belirleyin.</p>
            <div className="map-picker-shell">
              <MapContainer className="world-map" center={[pickerLat, pickerLon]} zoom={7} scrollWheelZoom>
                <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                <LocationPicker />
              </MapContainer>
            </div>
            <div className="map-picker-coords">
              <span>Enlem: {pickerLat}</span>
              <span>Boylam: {pickerLon}</span>
            </div>
            <div className="modal-actions">
              <button type="button" className="secondary-btn" onClick={() => setShowMapPicker(false)}>
                İptal
              </button>
              <button type="button" className="primary-btn" onClick={handleApplyMapLocation}>
                Konumu Uygula
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
