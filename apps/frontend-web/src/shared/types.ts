export type CommunicationStatus = "online" | "offline" | "unknown";

export type DeviceRow = {
  id: number;
  name: string;
  communicationStatus: CommunicationStatus;
  batteryPercent: number;
  alarmActive: boolean;
  lastUpdateAt?: string;
  latitude: number;
  longitude: number;
};

export type LiveValue = {
  deviceName: string;
  signalKey: string;
  value: number;
  quality: string;
  sourceTimestamp: string;
};

export type UserRole = "operator" | "engineer";

export type AuthSession = {
  accessToken: string;
  username: string;
  role: UserRole;
};

export type ApiDevice = {
  id: number;
  code: string;
  name: string;
  ip_address: string;
  latitude: number;
  longitude: number;
  battery_percent: number;
  communication_status: CommunicationStatus;
  alarm_active: boolean;
  last_update_at?: string | null;
};

export type ApiTelemetry = {
  id: number;
  device_id: number;
  signal_key: string;
  value: number;
  quality: string;
  source_timestamp: string;
};

export type UserRead = {
  id: number;
  username: string;
  email: string;
  full_name: string;
  role: UserRole;
};
