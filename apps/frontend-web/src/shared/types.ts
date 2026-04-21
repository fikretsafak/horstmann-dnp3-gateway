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

export type UserRole = "operator" | "engineer" | "installer";

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
  phone_number?: string | null;
  full_name: string;
  role: UserRole;
};

export type AlarmEvent = {
  id: number;
  device_id: number;
  level: string;
  title: string;
  description: string;
  assigned_to?: string | null;
  acknowledged?: boolean;
  reset?: boolean;
  acknowledged_at?: string | null;
  reset_at?: string | null;
  created_at: string;
};

export type AlarmComment = {
  id: number;
  alarm_event_id: number;
  author_username: string;
  comment: string;
  created_at: string;
};

export type SystemEvent = {
  id: number;
  category: string;
  event_type: string;
  severity: string;
  message: string;
  actor_username?: string | null;
  device_code?: string | null;
  metadata_json?: string | null;
  created_at: string;
};
