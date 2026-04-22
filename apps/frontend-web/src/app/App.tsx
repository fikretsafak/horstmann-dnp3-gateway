import { useEffect, useMemo, useState } from "react";
import { Header } from "../components/Header";
import { LoginForm } from "../features/auth/LoginForm";
import { UserManagementPanel } from "../features/auth/UserManagementPanel";
import { AlarmsPage } from "../features/alarms/AlarmsPage";
import { EventsPage } from "../features/events/EventsPage";
import { DeviceManagementPanel } from "../features/devices/DeviceManagementPanel";
import { OutboundTargetsPanel } from "../features/outbound/OutboundTargetsPanel";
import { DeviceSidebar } from "../features/devices/DeviceSidebar";
import { LiveValuesTab } from "../features/live-values/LiveValuesTab";
import { DeviceMapTab } from "../features/map/DeviceMapTab";
import {
  changeMyPassword,
  clearSession,
  createGateway,
  createDevice,
  createUser,
  deleteDevice,
  deleteGateway,
  deleteUser,
  fetchAlarmComments,
  fetchAlarmEvents,
  fetchDevices,
  fetchGateways,
  fetchSystemEvents,
  fetchLiveValues,
  fetchMe,
  fetchOutboundTargets,
  fetchUsers,
  loadSession,
  login,
  logout,
  resetUserPassword,
  saveSession,
  addAlarmComment,
  acknowledgeAlarm,
  acknowledgeAllAlarms,
  assignAlarm,
  resetAlarm,
  resetAllAlarms,
  updateGateway,
  updateOutboundTarget,
  updateDevice,
  createOutboundTarget,
  deleteOutboundTarget,
  updateUser,
  updateMyProfile
} from "../shared/api";
import type { AlarmComment, AlarmEvent, AuthSession, DeviceRow, Gateway, LiveValue, OutboundTarget, SystemEvent, UserRead } from "../shared/types";

type TabId = "map" | "values";
type PageMode = "home" | "alarms" | "events" | "engineering";
type EngineeringPage = "devices" | "users" | "outbound";
type NotificationSettings = {
  smtp_host: string;
  smtp_port: string;
  smtp_username: string;
  smtp_password: string;
  smtp_from_email: string;
  smtp_use_tls: boolean;
};

const NOTIFICATION_SETTINGS_STORAGE_KEY = "hsl-notification-settings";

function loadNotificationSettings(): NotificationSettings {
  try {
    const raw = localStorage.getItem(NOTIFICATION_SETTINGS_STORAGE_KEY);
    if (!raw) {
      return {
        smtp_host: "",
        smtp_port: "587",
        smtp_username: "",
        smtp_password: "",
        smtp_from_email: "",
        smtp_use_tls: true
      };
    }
    const parsed = JSON.parse(raw) as Partial<NotificationSettings>;
    return {
      smtp_host: parsed.smtp_host ?? "",
      smtp_port: parsed.smtp_port ?? "587",
      smtp_username: parsed.smtp_username ?? "",
      smtp_password: parsed.smtp_password ?? "",
      smtp_from_email: parsed.smtp_from_email ?? "",
      smtp_use_tls: parsed.smtp_use_tls ?? true
    };
  } catch {
    return {
      smtp_host: "",
      smtp_port: "587",
      smtp_username: "",
      smtp_password: "",
      smtp_from_email: "",
      smtp_use_tls: true
    };
  }
}

export function App() {
  const [session, setSession] = useState<AuthSession | null>(() => loadSession());
  const [devices, setDevices] = useState<DeviceRow[]>([]);
  const [liveValues, setLiveValues] = useState<LiveValue[]>([]);
  const [users, setUsers] = useState<UserRead[]>([]);
  const [alarms, setAlarms] = useState<AlarmEvent[]>([]);
  const [events, setEvents] = useState<SystemEvent[]>([]);
  const [gateways, setGateways] = useState<Gateway[]>([]);
  const [devicesByGateway, setDevicesByGateway] = useState<DeviceRow[]>([]);
  const [outboundTargets, setOutboundTargets] = useState<OutboundTarget[]>([]);
  const [alarmsLoading, setAlarmsLoading] = useState(false);
  const [currentUser, setCurrentUser] = useState<UserRead | null>(null);
  const [authError, setAuthError] = useState<string>();
  const [loadingLogin, setLoadingLogin] = useState(false);
  const [loadingData, setLoadingData] = useState(false);
  const [selectedDeviceId, setSelectedDeviceId] = useState<number>(0);
  const [activeTab, setActiveTab] = useState<TabId>("map");
  const [engineeringPage, setEngineeringPage] = useState<EngineeringPage>("devices");
  const [pageMode, setPageMode] = useState<PageMode>("home");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsFullName, setSettingsFullName] = useState("");
  const [settingsEmail, setSettingsEmail] = useState("");
  const [settingsCurrentPassword, setSettingsCurrentPassword] = useState("");
  const [settingsNewPassword, setSettingsNewPassword] = useState("");
  const [notificationSettings, setNotificationSettings] = useState<NotificationSettings>(loadNotificationSettings);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsError, setSettingsError] = useState("");

  useEffect(() => {
    const load = async () => {
      if (!session) return;
      setLoadingData(true);
      try {
        const me = await fetchMe(session.accessToken);
        setCurrentUser(me);
        setSettingsFullName(me.full_name);
        setSettingsEmail(me.email);
        const loadedDevices = await fetchDevices(session.accessToken);
        setDevices(loadedDevices);
        setDevicesByGateway(loadedDevices);
        const deviceNameMap = new Map<number, string>(loadedDevices.map((item) => [item.id, item.name]));
        const telemetry = await fetchLiveValues(session.accessToken, deviceNameMap);
        setLiveValues(telemetry);
        setAlarmsLoading(true);
        const alarmRows = await fetchAlarmEvents(session.accessToken);
        setAlarms(alarmRows);
        const eventRows = await fetchSystemEvents(session.accessToken);
        setEvents(eventRows);
        if (session.role === "engineer") {
          const gatewayRows = await fetchGateways(session.accessToken);
          setGateways(gatewayRows);
          const allUsers = await fetchUsers(session.accessToken);
          setUsers(allUsers);
          const outboundRows = await fetchOutboundTargets(session.accessToken);
          setOutboundTargets(outboundRows);
        } else {
          setGateways([]);
          setUsers([]);
          setOutboundTargets([]);
        }
      } catch {
        setAuthError("Oturum geçersiz veya API erişilemiyor.");
      } finally {
        setAlarmsLoading(false);
        setLoadingData(false);
      }
    };
    void load();
  }, [session]);

  useEffect(() => {
    if (!session) return;
    if (session.role !== "engineer" && pageMode === "engineering") {
      setPageMode("home");
      setEngineeringPage("devices");
    }
  }, [session, pageMode]);

  const handleLogin = async (username: string, password: string) => {
    setLoadingLogin(true);
    setAuthError(undefined);
    try {
      const nextSession = await login(username, password);
      saveSession(nextSession);
      setSession(nextSession);
      setPageMode("home");
      setEngineeringPage("devices");
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "Giriş başarısız.");
    } finally {
      setLoadingLogin(false);
    }
  };

  const handleLogout = () => {
    if (session) {
      void logout(session.accessToken);
    }
    clearSession();
    setSession(null);
    setCurrentUser(null);
    setDevices([]);
    setLiveValues([]);
    setUsers([]);
    setAlarms([]);
    setEvents([]);
    setGateways([]);
    setDevicesByGateway([]);
    setOutboundTargets([]);
    setEngineeringPage("devices");
    setPageMode("home");
  };

  const reloadUsers = async () => {
    if (!session || session.role !== "engineer") return;
    const allUsers = await fetchUsers(session.accessToken);
    setUsers(allUsers);
  };

  const handleCreateUser = async (payload: {
    username: string;
    email: string;
    phone_number?: string | null;
    full_name: string;
    password: string;
    role: "operator" | "engineer";
  }) => {
    if (!session) return;
    await createUser(session.accessToken, payload);
    await reloadUsers();
  };

  const handleDeleteUser = async (userId: number) => {
    if (!session) return;
    await deleteUser(session.accessToken, userId);
    await reloadUsers();
  };

  const handleUpdateUser = async (
    userId: number,
    payload: { email: string; phone_number?: string | null; full_name: string; role: "operator" | "engineer" }
  ) => {
    if (!session) return;
    await updateUser(session.accessToken, userId, payload);
    await reloadUsers();
  };

  const handleResetUserPassword = async (userId: number, newPassword: string) => {
    if (!session) return;
    await resetUserPassword(session.accessToken, userId, newPassword);
  };

  const handleAssignAlarm = async (alarmId: number, assignedTo: string | null) => {
    if (!session) return;
    const updated = await assignAlarm(session.accessToken, alarmId, assignedTo);
    setAlarms((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
  };

  const handleLoadAlarmComments = async (alarmId: number): Promise<AlarmComment[]> => {
    if (!session) return [];
    return fetchAlarmComments(session.accessToken, alarmId);
  };

  const handleAddAlarmComment = async (alarmId: number, comment: string) => {
    if (!session) return;
    await addAlarmComment(session.accessToken, alarmId, comment);
  };

  const handleAcknowledgeAlarm = async (alarmId: number) => {
    if (!session) return;
    const updated = await acknowledgeAlarm(session.accessToken, alarmId);
    setAlarms((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
  };

  const handleResetAlarm = async (alarmId: number) => {
    if (!session) return;
    const updated = await resetAlarm(session.accessToken, alarmId);
    setAlarms((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
  };

  const handleAcknowledgeAllAlarms = async () => {
    if (!session) return;
    const updated = await acknowledgeAllAlarms(session.accessToken);
    setAlarms(updated);
  };

  const handleResetAllAlarms = async () => {
    if (!session) return;
    const updated = await resetAllAlarms(session.accessToken);
    setAlarms(updated);
  };

  const reloadGateways = async () => {
    if (!session || session.role !== "engineer") return;
    const rows = await fetchGateways(session.accessToken);
    setGateways(rows);
  };

  const handleCreateGateway = async (payload: {
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
  }) => {
    if (!session) return;
    await createGateway(session.accessToken, payload);
    await reloadGateways();
  };

  const handleDeleteGateway = async (gatewayCode: string) => {
    if (!session) return;
    await deleteGateway(session.accessToken, gatewayCode);
    await reloadGateways();
  };

  const handleUpdateGateway = async (
    gatewayCode: string,
    payload: { name?: string; host?: string; listen_port?: number; token?: string }
  ) => {
    if (!session) return;
    await updateGateway(session.accessToken, gatewayCode, payload);
    await reloadGateways();
  };

  const handleSelectGatewayForDevices = async (gatewayCode: string) => {
    if (!session) return;
    const scopedDevices = await fetchDevices(session.accessToken, gatewayCode);
    setDevicesByGateway(scopedDevices);
  };

  const handleCreateDevice = async (payload: {
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
  }) => {
    if (!session) return;
    await createDevice(session.accessToken, payload);
    const all = await fetchDevices(session.accessToken);
    setDevices(all);
    if (payload.gateway_code) {
      const scoped = await fetchDevices(session.accessToken, payload.gateway_code);
      setDevicesByGateway(scoped);
    } else {
      setDevicesByGateway(all);
    }
  };

  const handleUpdateDevice = async (
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
  ) => {
    if (!session) return;
    await updateDevice(session.accessToken, deviceCode, payload);
    const all = await fetchDevices(session.accessToken);
    setDevices(all);
    if (payload.gateway_code) {
      const scoped = await fetchDevices(session.accessToken, payload.gateway_code);
      setDevicesByGateway(scoped);
    } else {
      setDevicesByGateway(all);
    }
  };

  const handleDeleteDevice = async (deviceCode: string) => {
    if (!session) return;
    await deleteDevice(session.accessToken, deviceCode);
    const all = await fetchDevices(session.accessToken);
    setDevices(all);
    setDevicesByGateway((prev) => prev.filter((item) => item.code !== deviceCode));
  };

  const reloadOutboundTargets = async () => {
    if (!session || session.role !== "engineer") return;
    const rows = await fetchOutboundTargets(session.accessToken);
    setOutboundTargets(rows);
  };

  const handleCreateOutboundTarget = async (payload: {
    name: string;
    protocol: "rest" | "mqtt";
    endpoint: string;
    topic?: string | null;
    event_filter: "all" | "telemetry" | "alarm";
    auth_header?: string | null;
    auth_token?: string | null;
    qos: number;
    retain: boolean;
    is_active: boolean;
  }) => {
    if (!session) return;
    await createOutboundTarget(session.accessToken, payload);
    await reloadOutboundTargets();
  };

  const handleUpdateOutboundTarget = async (
    targetId: number,
    payload: {
      endpoint?: string;
      topic?: string | null;
      event_filter?: "all" | "telemetry" | "alarm";
      auth_header?: string | null;
      auth_token?: string | null;
      qos?: number;
      retain?: boolean;
      is_active?: boolean;
    }
  ) => {
    if (!session) return;
    await updateOutboundTarget(session.accessToken, targetId, payload);
    await reloadOutboundTargets();
  };

  const handleDeleteOutboundTarget = async (targetId: number) => {
    if (!session) return;
    await deleteOutboundTarget(session.accessToken, targetId);
    await reloadOutboundTargets();
  };

  const handleOpenSettings = () => {
    if (currentUser) {
      setSettingsFullName(currentUser.full_name);
      setSettingsEmail(currentUser.email);
    }
    setSettingsCurrentPassword("");
    setSettingsNewPassword("");
    setSettingsError("");
    setNotificationSettings(loadNotificationSettings());
    setSettingsOpen(true);
  };

  const handleSaveSettings = async () => {
    if (!session) return;
    setSettingsSaving(true);
    setSettingsError("");
    try {
      const updated = await updateMyProfile(session.accessToken, {
        full_name: settingsFullName,
        email: settingsEmail
      });
      setCurrentUser(updated);
      if (settingsCurrentPassword && settingsNewPassword) {
        await changeMyPassword(session.accessToken, {
          current_password: settingsCurrentPassword,
          new_password: settingsNewPassword
        });
      }
      localStorage.setItem(NOTIFICATION_SETTINGS_STORAGE_KEY, JSON.stringify(notificationSettings));
      setSettingsOpen(false);
    } catch (error) {
      setSettingsError(error instanceof Error ? error.message : "Ayarlar kaydedilemedi.");
    } finally {
      setSettingsSaving(false);
    }
  };

  const selectedDevice = useMemo(
    () => devices.find((item) => item.id === selectedDeviceId),
    [devices, selectedDeviceId]
  );

  if (!session) {
    return <LoginForm onSubmit={handleLogin} loading={loadingLogin} error={authError} />;
  }

  return (
    <div className="layout">
      <Header
        fullName={currentUser?.full_name ?? session.username}
        role={session.role}
        activePage={pageMode}
        onChangePage={setPageMode}
        isEngineeringView={pageMode === "engineering"}
        onToggleEngineering={() => setPageMode("engineering")}
        onSettings={handleOpenSettings}
        onLogout={handleLogout}
      />
      <div className="body">
        {pageMode === "engineering" ? (
          <main className="content engineering-content">
            <div className="tabs">
              <button
                className={engineeringPage === "devices" ? "active" : ""}
                onClick={() => setEngineeringPage("devices")}
              >
                Cihazlar
              </button>
              <button
                className={engineeringPage === "users" ? "active" : ""}
                onClick={() => setEngineeringPage("users")}
              >
                Kullanıcılar
              </button>
              <button
                className={engineeringPage === "outbound" ? "active" : ""}
                onClick={() => setEngineeringPage("outbound")}
              >
                Outbound
              </button>
            </div>

            {engineeringPage === "devices" ? (
              <DeviceManagementPanel
                gateways={gateways}
                devices={devicesByGateway}
                onSelectGateway={handleSelectGatewayForDevices}
                onCreateGateway={handleCreateGateway}
                onUpdateGateway={handleUpdateGateway}
                onDeleteGateway={handleDeleteGateway}
                onCreate={handleCreateDevice}
                onUpdate={handleUpdateDevice}
                onDelete={handleDeleteDevice}
              />
            ) : null}
            {engineeringPage === "users" && session.role !== "operator" ? (
              <UserManagementPanel
                users={users}
                onCreate={handleCreateUser}
                onDelete={handleDeleteUser}
                onUpdate={handleUpdateUser}
                onResetPassword={handleResetUserPassword}
              />
            ) : null}
            {engineeringPage === "outbound" && session.role !== "operator" ? (
              <OutboundTargetsPanel
                targets={outboundTargets}
                onCreate={handleCreateOutboundTarget}
                onUpdate={handleUpdateOutboundTarget}
                onDelete={handleDeleteOutboundTarget}
              />
            ) : null}
          </main>
        ) : pageMode !== "home" ? (
          <main className="content">
            {pageMode === "alarms" ? (
              <AlarmsPage
                alarms={alarms}
                users={users}
                loading={alarmsLoading}
                onAssign={handleAssignAlarm}
                onLoadComments={handleLoadAlarmComments}
                onAddComment={handleAddAlarmComment}
                onAcknowledge={handleAcknowledgeAlarm}
                onReset={handleResetAlarm}
                onAcknowledgeAll={handleAcknowledgeAllAlarms}
                onResetAll={handleResetAllAlarms}
              />
            ) : null}
            {pageMode === "events" ? (
              <EventsPage events={events} loading={loadingData} />
            ) : null}
          </main>
        ) : (
          <>
            <DeviceSidebar devices={devices} selectedId={selectedDeviceId} onSelect={setSelectedDeviceId} />
            <main className={`content dashboard-content ${activeTab === "map" ? "map-active" : ""}`}>
              <div className="tabs dashboard-tabs">
                <button className={activeTab === "map" ? "active" : ""} onClick={() => setActiveTab("map")}>
                  Harita
                </button>
                <button className={activeTab === "values" ? "active" : ""} onClick={() => setActiveTab("values")}>
                  Tablo
                </button>
              </div>

              {loadingData ? <p>Yükleniyor...</p> : null}
              {activeTab === "map" ? (
                <DeviceMapTab
                  devices={devices}
                  selectedDevice={selectedDevice}
                  onSelectDevice={setSelectedDeviceId}
                />
              ) : null}
              {activeTab === "values" ? <LiveValuesTab values={liveValues} /> : null}
            </main>
          </>
        )}
      </div>

      {settingsOpen ? (
        <div className="settings-modal-backdrop">
          <div className="settings-modal">
            <h3>Profil Ayarları</h3>
            <label>
              İsim Soyisim
              <input value={settingsFullName} onChange={(event) => setSettingsFullName(event.target.value)} />
            </label>
            <label>
              E-posta
              <input value={settingsEmail} onChange={(event) => setSettingsEmail(event.target.value)} />
            </label>
            <label>
              Mevcut Şifre (opsiyonel)
              <input
                type="password"
                value={settingsCurrentPassword}
                onChange={(event) => setSettingsCurrentPassword(event.target.value)}
              />
            </label>
            <label>
              Yeni Şifre (opsiyonel)
              <input
                type="password"
                value={settingsNewPassword}
                onChange={(event) => setSettingsNewPassword(event.target.value)}
              />
            </label>
            <h3>Bildirim Ayarları</h3>
            <label>
              SMTP Sunucu
              <input
                value={notificationSettings.smtp_host}
                onChange={(event) =>
                  setNotificationSettings((prev) => ({ ...prev, smtp_host: event.target.value }))
                }
                placeholder="smtp.ornek.com"
              />
            </label>
            <label>
              SMTP Port
              <input
                type="number"
                min={1}
                max={65535}
                value={notificationSettings.smtp_port}
                onChange={(event) =>
                  setNotificationSettings((prev) => ({ ...prev, smtp_port: event.target.value }))
                }
              />
            </label>
            <label>
              SMTP Kullanıcı Adı
              <input
                value={notificationSettings.smtp_username}
                onChange={(event) =>
                  setNotificationSettings((prev) => ({ ...prev, smtp_username: event.target.value }))
                }
              />
            </label>
            <label>
              SMTP Şifre
              <input
                type="password"
                value={notificationSettings.smtp_password}
                onChange={(event) =>
                  setNotificationSettings((prev) => ({ ...prev, smtp_password: event.target.value }))
                }
              />
            </label>
            <label>
              Gönderen E-posta
              <input
                type="email"
                value={notificationSettings.smtp_from_email}
                onChange={(event) =>
                  setNotificationSettings((prev) => ({ ...prev, smtp_from_email: event.target.value }))
                }
                placeholder="alarm@firma.com"
              />
            </label>
            <label className="notify-option">
              <input
                type="checkbox"
                checked={notificationSettings.smtp_use_tls}
                onChange={(event) =>
                  setNotificationSettings((prev) => ({ ...prev, smtp_use_tls: event.target.checked }))
                }
              />
              TLS Kullan
            </label>
            {settingsError ? <p className="error-text">{settingsError}</p> : null}
            <div className="settings-actions">
              <button onClick={() => setSettingsOpen(false)}>Vazgeç</button>
              <button onClick={handleSaveSettings} disabled={settingsSaving}>
                {settingsSaving ? "Kaydediliyor..." : "Kaydet"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
