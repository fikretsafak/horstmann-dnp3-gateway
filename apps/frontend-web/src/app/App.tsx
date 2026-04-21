import { useEffect, useMemo, useState } from "react";
import { Header } from "../components/Header";
import { LoginForm } from "../features/auth/LoginForm";
import { UserManagementPanel } from "../features/auth/UserManagementPanel";
import { AlarmsPage } from "../features/alarms/AlarmsPage";
import { EventsPage } from "../features/events/EventsPage";
import { DeviceSidebar } from "../features/devices/DeviceSidebar";
import { LiveValuesTab } from "../features/live-values/LiveValuesTab";
import { DeviceMapTab } from "../features/map/DeviceMapTab";
import {
  changeMyPassword,
  clearSession,
  createUser,
  deleteUser,
  fetchAlarmComments,
  fetchAlarmEvents,
  fetchDevices,
  fetchSystemEvents,
  fetchLiveValues,
  fetchMe,
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
  updateUser,
  updateMyProfile
} from "../shared/api";
import type { AlarmComment, AlarmEvent, AuthSession, DeviceRow, LiveValue, SystemEvent, UserRead } from "../shared/types";

type TabId = "map" | "values";
type PageMode = "home" | "alarms" | "events" | "engineering";
type EngineeringPage = "overview" | "devices" | "users";

export function App() {
  const [session, setSession] = useState<AuthSession | null>(() => loadSession());
  const [devices, setDevices] = useState<DeviceRow[]>([]);
  const [liveValues, setLiveValues] = useState<LiveValue[]>([]);
  const [users, setUsers] = useState<UserRead[]>([]);
  const [alarms, setAlarms] = useState<AlarmEvent[]>([]);
  const [events, setEvents] = useState<SystemEvent[]>([]);
  const [alarmsLoading, setAlarmsLoading] = useState(false);
  const [currentUser, setCurrentUser] = useState<UserRead | null>(null);
  const [authError, setAuthError] = useState<string>();
  const [loadingLogin, setLoadingLogin] = useState(false);
  const [loadingData, setLoadingData] = useState(false);
  const [selectedDeviceId, setSelectedDeviceId] = useState<number>(0);
  const [activeTab, setActiveTab] = useState<TabId>("map");
  const [engineeringPage, setEngineeringPage] = useState<EngineeringPage>("overview");
  const [pageMode, setPageMode] = useState<PageMode>("home");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsFullName, setSettingsFullName] = useState("");
  const [settingsEmail, setSettingsEmail] = useState("");
  const [settingsCurrentPassword, setSettingsCurrentPassword] = useState("");
  const [settingsNewPassword, setSettingsNewPassword] = useState("");
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsError, setSettingsError] = useState("");

  useEffect(() => {
    if (devices.length > 0 && selectedDeviceId === 0) {
      setSelectedDeviceId(devices[0].id);
    }
  }, [devices, selectedDeviceId]);

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
        const deviceNameMap = new Map<number, string>(loadedDevices.map((item) => [item.id, item.name]));
        const telemetry = await fetchLiveValues(session.accessToken, deviceNameMap);
        setLiveValues(telemetry);
        setAlarmsLoading(true);
        const alarmRows = await fetchAlarmEvents(session.accessToken);
        setAlarms(alarmRows);
        const eventRows = await fetchSystemEvents(session.accessToken);
        setEvents(eventRows);
        if (session.role === "engineer") {
          const allUsers = await fetchUsers(session.accessToken);
          setUsers(allUsers);
        } else {
          setUsers([]);
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
      setEngineeringPage("overview");
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
      setEngineeringPage("overview");
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
    setEngineeringPage("overview");
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

  const handleOpenSettings = () => {
    if (currentUser) {
      setSettingsFullName(currentUser.full_name);
      setSettingsEmail(currentUser.email);
    }
    setSettingsCurrentPassword("");
    setSettingsNewPassword("");
    setSettingsError("");
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
                className={engineeringPage === "overview" ? "active" : ""}
                onClick={() => setEngineeringPage("overview")}
              >
                Özet
              </button>
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
            </div>

            {engineeringPage === "overview" ? (
              <section className="tab-panel">
                <h3>Mühendislik Paneli</h3>
                <p>Bu alandan cihaz, kullanıcı ve sistem yönetimi alt sayfalarına geçiş yapabilirsiniz.</p>
              </section>
            ) : null}
            {engineeringPage === "devices" ? (
              <section className="tab-panel">
                <h3>Cihaz Yönetimi</h3>
                <p>Cihaz ekle/düzenle/sil işlemleri bu alt sayfaya taşınacak.</p>
              </section>
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
                {selectedDevice ? <span className="selected-device">Seçili: {selectedDevice.name}</span> : null}
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
