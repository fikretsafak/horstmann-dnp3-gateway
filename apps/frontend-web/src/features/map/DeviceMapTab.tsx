import type { DeviceRow } from "../../shared/types";

type Props = {
  devices: DeviceRow[];
};

export function DeviceMapTab({ devices }: Props) {
  return (
    <section className="tab-panel">
      <h3>Device Map</h3>
      <div className="map-placeholder">
        {devices.map((device) => (
          <div key={device.id} className="map-item">
            <strong>{device.name}</strong>
            <span>
              ({device.latitude.toFixed(4)}, {device.longitude.toFixed(4)})
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
