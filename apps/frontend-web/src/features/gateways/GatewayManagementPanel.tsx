import { useState, type FormEvent } from "react";

import type { Gateway } from "../../shared/types";

type Props = {
  gateways: Gateway[];
  onCreate: (payload: {
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
  onToggleActive: (gatewayCode: string, isActive: boolean) => Promise<void>;
  onDelete: (gatewayCode: string) => Promise<void>;
};

export function GatewayManagementPanel({ gateways, onCreate, onToggleActive, onDelete }: Props) {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [host, setHost] = useState("");
  const [listenPort, setListenPort] = useState("20000");
  const [upstreamUrl, setUpstreamUrl] = useState("/api/v1/telemetry/gateway/{gateway_code}");
  const [batchIntervalSec, setBatchIntervalSec] = useState("5");
  const [maxDevices, setMaxDevices] = useState("200");
  const [deviceCodePrefix, setDeviceCodePrefix] = useState("");
  const [token, setToken] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    try {
      await onCreate({
        code,
        name,
        host,
        listen_port: Number(listenPort),
        upstream_url: upstreamUrl,
        batch_interval_sec: Number(batchIntervalSec),
        max_devices: Number(maxDevices),
        device_code_prefix: deviceCodePrefix.trim() || null,
        token,
        is_active: true
      });
      setShowCreateModal(false);
      setCode("");
      setName("");
      setHost("");
      setListenPort("20000");
      setUpstreamUrl("/api/v1/telemetry/gateway/{gateway_code}");
      setBatchIntervalSec("5");
      setMaxDevices("200");
      setDeviceCodePrefix("");
      setToken("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gateway oluşturulamadı.");
    }
  };

  return (
    <section className="tab-panel">
      <h3>Gateway Yönetimi</h3>
      <p className="helper-text">
        Gateway&apos;ler DNP3 verisini toplayıp HTTPS ile tek mesajda çatı yazılıma iletir. Yük dağıtımı için cihaz kapsamı
        ve kapasite limitleri bu ekrandan yönetilir.
      </p>

      <div className="users-panel-toolbar">
        <button className="primary-btn" onClick={() => setShowCreateModal(true)}>
          Gateway Ekle
        </button>
      </div>

      <div className="gateway-endpoint">
        DNP3 connector ingest endpoint: <code>/api/v1/telemetry/gateway/{"{gateway_code}"}</code> (Header:{" "}
        <code>X-Gateway-Token</code>)
      </div>

      <table className="values-table">
        <thead>
          <tr>
            <th>Kod</th>
            <th>Ad</th>
            <th>Host</th>
            <th>Port</th>
            <th>Kapsam</th>
            <th>Maks. Cihaz</th>
            <th>Batch (sn)</th>
            <th>Durum</th>
            <th>Son Görülme</th>
            <th>İşlem</th>
          </tr>
        </thead>
        <tbody>
          {gateways.map((gateway) => (
            <tr key={gateway.id}>
              <td>{gateway.code}</td>
              <td>{gateway.name}</td>
              <td>{gateway.host}</td>
              <td>{gateway.listen_port}</td>
              <td>{gateway.device_code_prefix ? `${gateway.device_code_prefix}*` : "Tümü"}</td>
              <td>{gateway.max_devices}</td>
              <td>{gateway.batch_interval_sec}</td>
              <td>{gateway.is_active ? "Aktif" : "Pasif"}</td>
              <td>{gateway.last_seen_at ? new Date(gateway.last_seen_at).toLocaleString("tr-TR") : "-"}</td>
              <td className="actions-cell">
                <button
                  className="secondary-btn action-btn"
                  onClick={() => void onToggleActive(gateway.code, !gateway.is_active)}
                >
                  {gateway.is_active ? "Pasifleştir" : "Aktifleştir"}
                </button>
                <button className="danger-btn action-btn" onClick={() => void onDelete(gateway.code)}>
                  Sil
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {showCreateModal ? (
        <div className="settings-modal-backdrop">
          <form className="settings-modal" onSubmit={handleSubmit}>
            <h3>Gateway Ekle</h3>
            <label>
              Kod
              <input placeholder="gw-01" value={code} onChange={(event) => setCode(event.target.value)} required />
            </label>
            <label>
              Gateway Adı
              <input value={name} onChange={(event) => setName(event.target.value)} required />
            </label>
            <label>
              Host
              <input placeholder="10.10.10.20" value={host} onChange={(event) => setHost(event.target.value)} required />
            </label>
            <label>
              Port
              <input
                type="number"
                min={1}
                max={65535}
                value={listenPort}
                onChange={(event) => setListenPort(event.target.value)}
                required
              />
            </label>
            <label>
              Çatı API URL
              <input value={upstreamUrl} onChange={(event) => setUpstreamUrl(event.target.value)} required />
            </label>
            <label>
              Batch Aralığı (sn)
              <input
                type="number"
                min={1}
                max={3600}
                value={batchIntervalSec}
                onChange={(event) => setBatchIntervalSec(event.target.value)}
                required
              />
            </label>
            <label>
              Maksimum Cihaz Sayısı
              <input
                type="number"
                min={1}
                max={2000}
                value={maxDevices}
                onChange={(event) => setMaxDevices(event.target.value)}
                required
              />
            </label>
            <label>
              Cihaz Kod Ön Eki (opsiyonel)
              <input
                placeholder="örn: ist-1-"
                value={deviceCodePrefix}
                onChange={(event) => setDeviceCodePrefix(event.target.value)}
              />
            </label>
            <label>
              Gateway Token
              <input value={token} onChange={(event) => setToken(event.target.value)} required />
            </label>
            {error ? <p className="error-text">{error}</p> : null}
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
    </section>
  );
}
