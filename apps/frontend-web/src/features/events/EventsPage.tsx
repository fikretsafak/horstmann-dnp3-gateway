import { useMemo, useState } from "react";

import type { SystemEvent } from "../../shared/types";

type Props = {
  events: SystemEvent[];
  loading?: boolean;
};

export function EventsPage({ events, loading }: Props) {
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [severityFilter, setSeverityFilter] = useState("all");

  const categories = useMemo(() => Array.from(new Set(events.map((item) => item.category))).sort(), [events]);

  const filteredEvents = useMemo(() => {
    return events.filter((item) => {
      const categoryOk = categoryFilter === "all" ? true : item.category === categoryFilter;
      const severityOk = severityFilter === "all" ? true : item.severity === severityFilter;
      const text = `${item.message} ${item.actor_username ?? ""} ${item.device_code ?? ""}`.toLowerCase();
      const searchOk = search.trim() ? text.includes(search.trim().toLowerCase()) : true;
      return categoryOk && severityOk && searchOk;
    });
  }, [events, categoryFilter, severityFilter, search]);

  return (
    <section className="alarms-layout">
      <div className="alarms-list-card">
        <div className="alarms-toolbar">
          <input
            className="device-search-input"
            placeholder="Olay ara..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <div className="alarms-filter-row">
            <select value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}>
              <option value="all">Tüm Kategoriler</option>
              {categories.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
            <select value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)}>
              <option value="all">Tüm Öncelikler</option>
              <option value="info">Bilgi</option>
              <option value="warning">Uyarı</option>
              <option value="error">Hata</option>
            </select>
          </div>
        </div>

        <div className="alarms-table-wrap">
          <table className="values-table">
            <thead>
              <tr>
                <th>Öncelik</th>
                <th>Kategori</th>
                <th>Mesaj</th>
                <th>Kullanıcı</th>
                <th>Cihaz</th>
                <th>Tarih</th>
              </tr>
            </thead>
            <tbody>
              {filteredEvents.map((item) => (
                <tr key={item.id}>
                  <td>
                    <span className={`alarm-state ${item.severity === "warning" ? "state-open" : "state-ack"}`}>
                      {item.severity}
                    </span>
                  </td>
                  <td>{item.category}</td>
                  <td>{item.message}</td>
                  <td>{item.actor_username ?? "-"}</td>
                  <td>{item.device_code ?? "-"}</td>
                  <td>{new Date(item.created_at).toLocaleString("tr-TR")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!loading && filteredEvents.length === 0 ? <p className="helper-text">Filtreye uygun olay bulunamadı.</p> : null}
      </div>
    </section>
  );
}
