import type { DeviceRow } from "../../shared/types";

type Props = {
  devices: DeviceRow[];
  selectedId: number;
  onSelect: (id: number) => void;
};

export function DeviceSidebar({ devices, selectedId, onSelect }: Props) {
  return (
    <aside className="sidebar">
      <h2>Devices</h2>
      <div className="device-list">
        {devices.length === 0 ? <p>Kayitli cihaz yok. Engineer rolunde cihaz ekleyin.</p> : null}
        {devices.map((device) => (
          <button
            key={device.id}
            className={`device-row ${selectedId === device.id ? "selected" : ""}`}
            onClick={() => onSelect(device.id)}
          >
            <div className="device-row-top">
              <strong>{device.name}</strong>
              <span className={`dot ${device.communicationStatus}`} />
            </div>
            <div className="device-row-meta">
              <span>Battery: {device.batteryPercent}%</span>
              <span>Alarm: {device.alarmActive ? "Active" : "Normal"}</span>
            </div>
            {device.lastUpdateAt ? <small>{device.lastUpdateAt}</small> : null}
          </button>
        ))}
      </div>
    </aside>
  );
}
