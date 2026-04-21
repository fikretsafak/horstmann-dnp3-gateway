import type { LiveValue } from "../../shared/types";

type Props = {
  values: LiveValue[];
};

export function LiveValuesTab({ values }: Props) {
  return (
    <section className="tab-panel live-values-panel">
      <div className="live-values-table-wrap">
        <table className="values-table">
          <thead>
            <tr>
              <th>Cihaz</th>
              <th>Sinyal</th>
              <th>Değer</th>
              <th>Kalite</th>
              <th>Zaman</th>
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
      </div>
    </section>
  );
}
