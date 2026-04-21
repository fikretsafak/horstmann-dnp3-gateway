import type { LiveValue } from "../../shared/types";

type Props = {
  values: LiveValue[];
};

export function LiveValuesTab({ values }: Props) {
  return (
    <section className="tab-panel">
      <h3>Live Values</h3>
      <table className="values-table">
        <thead>
          <tr>
            <th>Device</th>
            <th>Signal</th>
            <th>Value</th>
            <th>Quality</th>
            <th>Timestamp</th>
          </tr>
        </thead>
        <tbody>
          {values.map((item, idx) => (
            <tr key={`${item.deviceName}-${item.signalKey}-${idx}`}>
              <td>{item.deviceName}</td>
              <td>{item.signalKey}</td>
              <td>{item.value}</td>
              <td>{item.quality}</td>
              <td>{item.sourceTimestamp}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
