import { useEffect, useMemo, useState } from "react";
import { Header } from "../components/Header";
import { LoginForm } from "../features/auth/LoginForm";
import { UserManagementPanel } from "../features/auth/UserManagementPanel";
import { DeviceSidebar } from "../features/devices/DeviceSidebar";
import { LiveValuesTab } from "../features/live-values/LiveValuesTab";
import { DeviceMapTab } from "../features/map/DeviceMapTab";
import {
  changeMyPassword,
  clearSession,
  createUser,
  deleteUser,
  fetchDevices,
  fetchLiveValues,
  fetchMe,
  fetchUsers,
  loadSession,
  login,
  saveSession,
  updateMyProfile
} from "../shared/api";
import type { AuthSession, DeviceRow, LiveValue, UserRead } from "../shared/types";

type TabId = "map" | "values";
type ViewMode = "dashboard" | "engineering";
type PageMode = "home" | "alarms" | "events";

export function App() {
  const [session, setSession] = useState<AuthSession | null>(() => loadSession());
  const [devices, setDevices] = useState<DeviceRow[]>([]);
  const [liveValues, setLiveValues] = useState<LiveValue[]>([]);
  const [users, setUsers] = useState<UserRead[]>([]);
  const [currentUser, setCurrentUser] = useState<UserRead | null>(null);
  const [authError, setAuthError] = useState<string>();
  const [loadingLogin, setLoadingLogin] = useState(false);
  const [loadingData, setLoadingData] = useState(false);
  const [selectedDeviceId, setSelectedDeviceId] = useState<number>(0);
  const [activeTab, setActiveTab] = useState<TabId>("map");
  const [viewMode, setViewMode] = useState<ViewMode>("dashboard");
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
        if (session.role === "engineer") {
          const allUsers = await fetchUsers(session.accessToken);
          setUsers(allUsers);
        } else {
          setUsers([]);
        }
      } catch {
        setAuthError("Oturum gecersiz veya API erisilemiyor.");
      } finally {
        setLoadingData(false);
      }
    };
    void load();
  }, [session]);

  const handleLogin = async (username: string, password: string) => {
    setLoadingLogin(true);
    setAuthError(undefined);
    try {
      const nextSession = await login(username, password);
      saveSession(nextSession);
      setSession(nextSession);
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "Giris basarisiz.");
    } finally {
      setLoadingLogin(false);
    }
  };

  const handleLogout = () => {
    clearSession();
    setSession(null);
    setCurrentUser(null);
    setDevices([]);
    setLiveValues([]);
    setUsers([]);
    setViewMode("dashboard");
  };

  const reloadUsers = async () => {
    if (!session || session.role !== "engineer") return;
    const allUsers = await fetchUsers(session.accessToken);
    setUsers(allUsers);
  };

  const handleCreateUser = async (payload: {
    username: string;
    email: string;
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
        isEngineeringView={viewMode === "engineering"}
        onToggleEngineering={() =>
          setViewMode((prev) => (prev === "engineering" ? "dashboard" : "engineering"))
        }
        onSettings={handleOpenSettings}
        onLogout={handleLogout}
      />
      <div className="body">
        {pageMode !== "home" ? (
          <main className="content">
            {pageMode === "alarms" ? (
              <section className="tab-panel">
                <h3>Alarmlar</h3>
                <p>Alarm listesi ve alarm gecmisi bu sayfada gosterilecek.</p>
              </section>
            ) : null}
            {pageMode === "events" ? (
              <section className="tab-panel">
                <h3>Olaylar</h3>
                <p>Olay kayitlari ve event gecmisi bu sayfada gosterilecek.</p>
              </section>
            ) : null}
          </main>
        ) : viewMode === "dashboard" ? (
          <>
            <DeviceSidebar devices={devices} selectedId={selectedDeviceId} onSelect={setSelectedDeviceId} />
            <main className="content">
              <div className="tabs">
                <button className={activeTab === "map" ? "active" : ""} onClick={() => setActiveTab("map")}>
                  Map
                </button>
                <button className={activeTab === "values" ? "active" : ""} onClick={() => setActiveTab("values")}>
                  Live Values
                </button>
                {selectedDevice ? <span className="selected-device">Selected: {selectedDevice.name}</span> : null}
              </div>

              {loadingData ? <p>Yukleniyor...</p> : null}
              {activeTab === "map" ? <DeviceMapTab devices={devices} /> : null}
              {activeTab === "values" ? <LiveValuesTab values={liveValues} /> : null}
            </main>
          </>
        ) : (
          <main className="content engineering-content">
            <section className="tab-panel">
              <h3>Muhendislik Paneli</h3>
              <p>Cihaz ve kullanici islemleri bu sayfadan yonetilir.</p>
            </section>
            <section className="tab-panel">
              <h3>Cihaz Yonetimi</h3>
              <p>Cihaz ekle/duzenle islemleri bir sonraki adimda bu bolume tasinacak.</p>
            </section>
            {session.role === "engineer" ? (
              <UserManagementPanel users={users} onCreate={handleCreateUser} onDelete={handleDeleteUser} />
            ) : null}
          </main>
        )}
      </div>

      {settingsOpen ? (
        <div className="settings-modal-backdrop">
          <div className="settings-modal">
            <h3>Profil Ayarlari</h3>
            <label>
              Isim Soyisim
              <input value={settingsFullName} onChange={(event) => setSettingsFullName(event.target.value)} />
            </label>
            <label>
              E-posta
              <input value={settingsEmail} onChange={(event) => setSettingsEmail(event.target.value)} />
            </label>
            <label>
              Mevcut Sifre (opsiyonel)
              <input
                type="password"
                value={settingsCurrentPassword}
                onChange={(event) => setSettingsCurrentPassword(event.target.value)}
              />
            </label>
            <label>
              Yeni Sifre (opsiyonel)
              <input
                type="password"
                value={settingsNewPassword}
                onChange={(event) => setSettingsNewPassword(event.target.value)}
              />
            </label>
            {settingsError ? <p className="error-text">{settingsError}</p> : null}
            <div className="settings-actions">
              <button onClick={() => setSettingsOpen(false)}>Vazgec</button>
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
