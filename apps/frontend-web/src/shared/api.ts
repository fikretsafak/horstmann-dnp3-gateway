import type {
  AlarmComment,
  AlarmEvent,
  ApiDevice,
  ApiTelemetry,
  AuthSession,
  DeviceRow,
  LiveValue,
  SystemEvent,
  UserRead,
  UserRole
} from "./types";

const API_BASE_URL = "http://127.0.0.1:8000/api/v1";
const AUTH_STORAGE_KEY = "hsl-auth";

type LoginResponse = {
  access_token: string;
  token_type: string;
  role: UserRole;
  username: string;
};

type ApiErrorDetail =
  | string
  | {
      loc?: Array<string | number>;
      msg?: string;
      type?: string;
    };

type ApiErrorResponse = {
  detail?: ApiErrorDetail | ApiErrorDetail[];
};

function authHeaders(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json"
  };
}

async function buildApiError(response: Response, fallbackMessage: string): Promise<Error> {
  try {
    const data = (await response.json()) as ApiErrorResponse;
    const detail = data.detail;
    if (typeof detail === "string" && detail.trim()) {
      return new Error(detail);
    }
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0];
      if (typeof first === "string" && first.trim()) {
        return new Error(first);
      }
      if (first && typeof first === "object") {
        const field = first.loc ? String(first.loc[first.loc.length - 1]) : "alan";
        const msg = first.msg ?? "geçersiz değer";
        return new Error(`Doğrulama hatası (${field}): ${msg}`);
      }
    }
  } catch {
    // ignore body parse error and use fallback
  }
  return new Error(fallbackMessage);
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

export async function logout(token: string): Promise<void> {
  await fetch(`${API_BASE_URL}/auth/logout`, {
    method: "POST",
    headers: authHeaders(token)
  });
}

export async function login(username: string, password: string): Promise<AuthSession> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password })
  });
  if (!response.ok) {
    throw new Error("Kullanıcı adı veya şifre hatalı.");
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
  if (!response.ok) throw new Error("Cihaz listesi alınamadı.");
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
  if (!response.ok) throw new Error("Canlı değerler alınamadı.");
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
  if (!response.ok) throw new Error("Kullanıcılar alınamadı.");
  return (await response.json()) as UserRead[];
}

export async function fetchMe(token: string): Promise<UserRead> {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    headers: authHeaders(token)
  });
  if (!response.ok) throw new Error("Kullanıcı bilgisi alınamadı.");
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
  if (!response.ok) throw new Error("Profil güncellenemedi.");
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
  if (!response.ok) throw new Error("Şifre değiştirilemedi.");
}

export async function createUser(
  token: string,
  payload: {
    username: string;
    email: string;
    phone_number?: string | null;
    full_name: string;
    password: string;
    role: UserRole;
  }
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/users`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload)
  });
  if (!response.ok) throw await buildApiError(response, "Kullanıcı oluşturulamadı.");
}

export async function deleteUser(token: string, userId: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/users/${userId}`, {
    method: "DELETE",
    headers: authHeaders(token)
  });
  if (!response.ok) throw new Error("Kullanıcı silinemedi.");
}

export async function updateUser(
  token: string,
  userId: number,
  payload: { email: string; phone_number?: string | null; full_name: string; role: "operator" | "engineer" }
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/users/${userId}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(payload)
  });
  if (!response.ok) throw await buildApiError(response, "Kullanıcı güncellenemedi.");
}

export async function resetUserPassword(token: string, userId: number, newPassword: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/users/${userId}/reset-password`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ new_password: newPassword })
  });
  if (!response.ok) throw await buildApiError(response, "Şifre sıfırlanamadı.");
}

export async function fetchAlarmEvents(token: string): Promise<AlarmEvent[]> {
  const response = await fetch(`${API_BASE_URL}/alarms/events`, {
    headers: authHeaders(token)
  });
  if (!response.ok) throw new Error("Alarmlar alınamadı.");
  return (await response.json()) as AlarmEvent[];
}

export async function assignAlarm(token: string, alarmId: number, assignedTo: string | null): Promise<AlarmEvent> {
  const response = await fetch(`${API_BASE_URL}/alarms/events/${alarmId}/assign`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify({ assigned_to: assignedTo })
  });
  if (!response.ok) throw await buildApiError(response, "Alarm ataması yapılamadı.");
  return (await response.json()) as AlarmEvent;
}

export async function fetchAlarmComments(token: string, alarmId: number): Promise<AlarmComment[]> {
  const response = await fetch(`${API_BASE_URL}/alarms/events/${alarmId}/comments`, {
    headers: authHeaders(token)
  });
  if (!response.ok) throw await buildApiError(response, "Alarm yorumları alınamadı.");
  return (await response.json()) as AlarmComment[];
}

export async function addAlarmComment(token: string, alarmId: number, comment: string): Promise<AlarmComment> {
  const response = await fetch(`${API_BASE_URL}/alarms/events/${alarmId}/comments`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ comment })
  });
  if (!response.ok) throw await buildApiError(response, "Alarm yorumu kaydedilemedi.");
  return (await response.json()) as AlarmComment;
}

export async function acknowledgeAlarm(token: string, alarmId: number): Promise<AlarmEvent> {
  const response = await fetch(`${API_BASE_URL}/alarms/events/${alarmId}/ack`, {
    method: "PATCH",
    headers: authHeaders(token)
  });
  if (!response.ok) throw await buildApiError(response, "Alarm onaylanamadı.");
  return (await response.json()) as AlarmEvent;
}

export async function resetAlarm(token: string, alarmId: number): Promise<AlarmEvent> {
  const response = await fetch(`${API_BASE_URL}/alarms/events/${alarmId}/reset`, {
    method: "PATCH",
    headers: authHeaders(token)
  });
  if (!response.ok) throw await buildApiError(response, "Alarm resetlenemedi.");
  return (await response.json()) as AlarmEvent;
}

export async function acknowledgeAllAlarms(token: string): Promise<AlarmEvent[]> {
  const response = await fetch(`${API_BASE_URL}/alarms/events/ack-all`, {
    method: "POST",
    headers: authHeaders(token)
  });
  if (!response.ok) throw await buildApiError(response, "Tüm alarmlar onaylanamadı.");
  return (await response.json()) as AlarmEvent[];
}

export async function resetAllAlarms(token: string): Promise<AlarmEvent[]> {
  const response = await fetch(`${API_BASE_URL}/alarms/events/reset-all`, {
    method: "POST",
    headers: authHeaders(token)
  });
  if (!response.ok) throw await buildApiError(response, "Tüm alarmlar resetlenemedi.");
  return (await response.json()) as AlarmEvent[];
}

export async function fetchSystemEvents(token: string): Promise<SystemEvent[]> {
  const response = await fetch(`${API_BASE_URL}/events`, {
    headers: authHeaders(token)
  });
  if (!response.ok) throw await buildApiError(response, "Sistem olayları alınamadı.");
  return (await response.json()) as SystemEvent[];
}
