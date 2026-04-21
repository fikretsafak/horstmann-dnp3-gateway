import type { ApiDevice, ApiTelemetry, AuthSession, DeviceRow, LiveValue, UserRead, UserRole } from "./types";

const API_BASE_URL = "http://127.0.0.1:8000/api/v1";
const AUTH_STORAGE_KEY = "hsl-auth";

type LoginResponse = {
  access_token: string;
  token_type: string;
  role: UserRole;
  username: string;
};

function authHeaders(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json"
  };
}

export function loadSession(): AuthSession | null {
  const raw = localStorage.getItem(AUTH_STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthSession;
  } catch {
    localStorage.removeItem(AUTH_STORAGE_KEY);
    return null;
  }
}

export function saveSession(session: AuthSession): void {
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
}

export function clearSession(): void {
  localStorage.removeItem(AUTH_STORAGE_KEY);
}

export async function login(username: string, password: string): Promise<AuthSession> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password })
  });
  if (!response.ok) {
    throw new Error("Kullanici adi veya sifre hatali.");
  }
  const data = (await response.json()) as LoginResponse;
  return {
    accessToken: data.access_token,
    username: data.username,
    role: data.role
  };
}

export async function fetchDevices(token: string): Promise<DeviceRow[]> {
  const response = await fetch(`${API_BASE_URL}/devices`, {
    headers: authHeaders(token)
  });
  if (!response.ok) throw new Error("Cihaz listesi alinamadi.");
  const devices = (await response.json()) as ApiDevice[];
  return devices.map((item) => ({
    id: item.id,
    name: item.name,
    communicationStatus: item.communication_status,
    batteryPercent: item.battery_percent,
    alarmActive: item.alarm_active,
    lastUpdateAt: item.last_update_at ?? undefined,
    latitude: item.latitude,
    longitude: item.longitude
  }));
}

export async function fetchLiveValues(token: string, deviceNames: Map<number, string>): Promise<LiveValue[]> {
  const response = await fetch(`${API_BASE_URL}/telemetry/latest`, {
    headers: authHeaders(token)
  });
  if (!response.ok) throw new Error("Canli degerler alinamadi.");
  const telemetry = (await response.json()) as ApiTelemetry[];
  return telemetry.map((item) => ({
    deviceName: deviceNames.get(item.device_id) ?? `Device-${item.device_id}`,
    signalKey: item.signal_key,
    value: item.value,
    quality: item.quality,
    sourceTimestamp: item.source_timestamp
  }));
}

export async function fetchUsers(token: string): Promise<UserRead[]> {
  const response = await fetch(`${API_BASE_URL}/users`, {
    headers: authHeaders(token)
  });
  if (!response.ok) throw new Error("Kullanicilar alinamadi.");
  return (await response.json()) as UserRead[];
}

export async function fetchMe(token: string): Promise<UserRead> {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    headers: authHeaders(token)
  });
  if (!response.ok) throw new Error("Kullanici bilgisi alinamadi.");
  return (await response.json()) as UserRead;
}

export async function updateMyProfile(
  token: string,
  payload: { full_name: string; email: string }
): Promise<UserRead> {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(payload)
  });
  if (!response.ok) throw new Error("Profil guncellenemedi.");
  return (await response.json()) as UserRead;
}

export async function changeMyPassword(
  token: string,
  payload: { current_password: string; new_password: string }
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/auth/me/change-password`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload)
  });
  if (!response.ok) throw new Error("Sifre degistirilemedi.");
}

export async function createUser(
  token: string,
  payload: { username: string; email: string; full_name: string; password: string; role: UserRole }
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/users`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload)
  });
  if (!response.ok) throw new Error("Kullanici olusturulamadi.");
}

export async function deleteUser(token: string, userId: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/users/${userId}`, {
    method: "DELETE",
    headers: authHeaders(token)
  });
  if (!response.ok) throw new Error("Kullanici silinemedi.");
}
