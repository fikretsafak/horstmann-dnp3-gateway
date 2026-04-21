import type { DeviceRow, LiveValue } from "./types";

export const devices: DeviceRow[] = [
  {
    id: 1,
    code: "SN2-001",
    name: "SN2-001",
    communicationStatus: "online",
    batteryPercent: 92,
    alarmActive: false,
    lastUpdateAt: "2026-04-21T10:20:00Z",
    latitude: 39.9208,
    longitude: 32.8541
  },
  {
    id: 2,
    code: "SN2-002",
    name: "SN2-002",
    communicationStatus: "offline",
    batteryPercent: 44,
    alarmActive: true,
    lastUpdateAt: "2026-04-21T09:48:00Z",
    latitude: 40.1885,
    longitude: 29.061
  }
];

export const liveValues: LiveValue[] = [
  {
    deviceName: "SN2-001",
    signalKey: "battery_voltage",
    value: 12.7,
    quality: "good",
    sourceTimestamp: "2026-04-21T10:20:00Z"
  },
  {
    deviceName: "SN2-002",
    signalKey: "door_alarm",
    value: 1,
    quality: "questionable",
    sourceTimestamp: "2026-04-21T09:48:00Z"
  }
];
