import json
import os
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk


CONFIG_FILE = Path(__file__).with_name("service_control_panel.config.json")
REFRESH_MS = 1500


@dataclass
class ServiceConfig:
    name: str
    service_type: str
    health_host: str = "127.0.0.1"
    health_port: int = 0
    windows_service_name: str = ""
    working_dir: str = ""
    command: list[str] | None = None
    env: dict[str, str] | None = None


def read_config() -> list[ServiceConfig]:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    items = []
    for row in data.get("services", []):
        items.append(
            ServiceConfig(
                name=row["name"],
                service_type=row["type"],
                health_host=row.get("health_host", "127.0.0.1"),
                health_port=int(row.get("health_port", 0)),
                windows_service_name=row.get("windows_service_name", ""),
                working_dir=row.get("working_dir", ""),
                command=row.get("command"),
                env=row.get("env", {}),
            )
        )
    return items


def is_port_open(host: str, port: int) -> bool:
    if port <= 0:
        return False
    candidates = [host]
    if host not in {"localhost", "127.0.0.1", "::1"}:
        candidates.extend(["localhost", "127.0.0.1"])
    else:
        candidates.extend(["localhost", "127.0.0.1", "::1"])

    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            with socket.create_connection((candidate, port), timeout=1.2):
                return True
        except OSError:
            continue
    return False


def run_ps(cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command", cmd],
        text=True,
        capture_output=True,
        encoding="utf-8",
    )


def get_windows_service_state(name: str) -> str:
    if not name:
        return "UNKNOWN"
    result = run_ps(f"Get-Service -Name '{name}' | Select-Object -ExpandProperty Status")
    if result.returncode != 0:
        return "NOT_FOUND"
    state = (result.stdout or "").strip().upper()
    return state or "UNKNOWN"


def get_windows_services_state(names: list[str]) -> dict[str, str]:
    clean_names = [name for name in names if name]
    if not clean_names:
        return {}
    quoted = ",".join([f"'{name}'" for name in clean_names])
    cmd = (
        "$names=@("
        + quoted
        + "); "
        "$items=Get-Service -Name $names -ErrorAction SilentlyContinue | "
        "Select-Object Name,Status; "
        "$items | ConvertTo-Json -Compress"
    )
    result = run_ps(cmd)
    if result.returncode != 0:
        return {}
    raw = (result.stdout or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    rows = data if isinstance(data, list) else [data]
    mapped: dict[str, str] = {}
    for row in rows:
        service_name = str(row.get("Name", "")).strip()
        raw_status = row.get("Status", "UNKNOWN")
        status = _normalize_windows_status(raw_status)
        if service_name:
            mapped[service_name] = status
    return mapped


def _normalize_windows_status(raw_status: object) -> str:
    # PowerShell sometimes serializes service status enum as int.
    enum_map = {
        "1": "STOPPED",
        "2": "START_PENDING",
        "3": "STOP_PENDING",
        "4": "RUNNING",
        "5": "CONTINUE_PENDING",
        "6": "PAUSE_PENDING",
        "7": "PAUSED",
    }
    normalized = str(raw_status).strip().upper()
    return enum_map.get(normalized, normalized if normalized else "UNKNOWN")


class ServiceControlPanel:
    def __init__(self, root: tk.Tk, services: list[ServiceConfig]) -> None:
        self.root = root
        self.services = services
        self.rows: dict[str, dict] = {}
        self.processes: dict[str, subprocess.Popen] = {}
        self.status_queue: list[dict[str, tuple[str, str]]] = []
        self._stop_event = threading.Event()
        self._build_ui()
        self._start_status_worker()
        self._apply_status_updates()

    def _build_ui(self) -> None:
        self.root.title("Horstman Sistem Kontrol Paneli")
        self.root.geometry("1120x500")
        self.root.minsize(980, 430)

        top = ttk.Frame(self.root, padding=12)
        top.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(top, text="Servis Durumu ve Kontrol", font=("Segoe UI", 14, "bold"))
        title.pack(anchor="w")

        info = ttk.Label(
            top,
            text="PostgreSQL / RabbitMQ / API / Tag Engine / Alarm Worker / Outbound Worker / Frontend servislerini tek yerden yönet.",
        )
        info.pack(anchor="w", pady=(0, 10))
        self.action_info = ttk.Label(top, text="Hazır.", foreground="#334155")
        self.action_info.pack(anchor="w", pady=(0, 8))

        actions = ttk.Frame(top)
        actions.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(actions, text="Tümünü Başlat", command=self.start_all).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(actions, text="Tümünü Durdur", command=self.stop_all).pack(side=tk.LEFT, padx=6)
        ttk.Button(actions, text="Tümünü Yeniden Başlat", command=self.restart_all).pack(side=tk.LEFT, padx=6)

        table = ttk.Frame(top)
        table.pack(fill=tk.X)
        headers = ["Servis", "Tip", "Durum", "Sağlık", "Aksiyon"]
        widths = [220, 160, 220, 240, 300]
        for i, text in enumerate(headers):
            lbl = ttk.Label(table, text=text, font=("Segoe UI", 10, "bold"))
            lbl.grid(row=0, column=i, sticky="w", padx=6, pady=4)
            table.grid_columnconfigure(i, minsize=widths[i])

        for idx, svc in enumerate(self.services, start=1):
            name_lbl = ttk.Label(table, text=svc.name)
            type_lbl = ttk.Label(table, text=self._friendly_service_type(svc.service_type))
            state_lbl = tk.Label(table, text="-", anchor="w", font=("Segoe UI", 9, "bold"))
            health_lbl = tk.Label(table, text="-", anchor="w", font=("Segoe UI", 9, "bold"))
            btns = ttk.Frame(table)
            start_btn = ttk.Button(btns, text="Baslat", command=lambda s=svc: self.start_service(s))
            stop_btn = ttk.Button(btns, text="Durdur", command=lambda s=svc: self.stop_service(s))
            restart_btn = ttk.Button(btns, text="Yeniden Baslat", command=lambda s=svc: self.restart_service(s))
            start_btn.pack(side=tk.LEFT, padx=2)
            stop_btn.pack(side=tk.LEFT, padx=2)
            restart_btn.pack(side=tk.LEFT, padx=2)

            name_lbl.grid(row=idx, column=0, sticky="w", padx=6, pady=6)
            type_lbl.grid(row=idx, column=1, sticky="w", padx=6, pady=6)
            state_lbl.grid(row=idx, column=2, sticky="w", padx=6, pady=6)
            health_lbl.grid(row=idx, column=3, sticky="w", padx=6, pady=6)
            btns.grid(row=idx, column=4, sticky="w", padx=6, pady=6)

            self.rows[svc.name] = {
                "state": state_lbl,
                "health": health_lbl,
                "cfg": svc,
            }

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _read_process_output(self, service_name: str, process: subprocess.Popen) -> None:
        last_lines: list[str] = []
        try:
            if process.stdout is None:
                return
            for line in process.stdout:
                stripped = line.strip()
                if stripped:
                    last_lines.append(stripped)
                    if len(last_lines) > 6:
                        last_lines.pop(0)
        except Exception as ex:
            self._set_action_info_threadsafe(f"{service_name}: çıktı okunamadı. {ex}", is_error=True)
            return

        rc = process.poll()
        if rc is None:
            return
        if rc != 0:
            hint = last_lines[-1] if last_lines else "detay yok"
            self._set_action_info_threadsafe(
                f"{service_name}: süreç kapandı (exit={rc}). Son mesaj: {hint}",
                is_error=True,
            )
        else:
            self._set_action_info_threadsafe(f"{service_name}: süreç tamamlandı.")

    def start_service(self, svc: ServiceConfig) -> None:
        if svc.service_type == "windows_service":
            if not svc.windows_service_name:
                self._set_action_info(f"{svc.name}: Windows servis adı tanımlı değil.", is_error=True)
                return
            result = run_ps(f"Start-Service -Name '{svc.windows_service_name}'")
            if result.returncode == 0:
                self._set_action_info(f"{svc.name}: başlat komutu gönderildi.")
            else:
                self._set_action_info(f"{svc.name}: başlatılamadı. {result.stderr.strip()}", is_error=True)
            return

        if svc.name in self.processes and self.processes[svc.name].poll() is None:
            self._set_action_info(f"{svc.name}: zaten çalışıyor.")
            return

        env = os.environ.copy()
        if svc.env:
            env.update(svc.env)
        cwd = svc.working_dir or str(Path.cwd())
        try:
            process = self._spawn_process(svc.command or [], cwd, env)
            self.processes[svc.name] = process
            self._set_action_info(f"{svc.name}: başlatıldı (PID {process.pid}).")
            th = threading.Thread(target=self._read_process_output, args=(svc.name, process), daemon=True)
            th.start()
        except Exception as ex:
            self._set_action_info(f"{svc.name}: başlatılamadı. {ex}", is_error=True)

    def stop_service(self, svc: ServiceConfig) -> None:
        if svc.service_type == "windows_service":
            if not svc.windows_service_name:
                self._set_action_info(f"{svc.name}: Windows servis adı tanımlı değil.", is_error=True)
                return
            result = run_ps(f"Stop-Service -Name '{svc.windows_service_name}' -Force")
            if result.returncode == 0:
                self._set_action_info(f"{svc.name}: durdur komutu gönderildi.")
            else:
                self._set_action_info(f"{svc.name}: durdurulamadı. {result.stderr.strip()}", is_error=True)
            return

        process = self.processes.get(svc.name)
        if process is None or process.poll() is not None:
            self._set_action_info(f"{svc.name}: çalışmıyor.")
            return
        process.terminate()
        try:
            process.wait(timeout=6)
            self._set_action_info(f"{svc.name}: durduruldu.")
        except subprocess.TimeoutExpired:
            process.kill()
            self._set_action_info(f"{svc.name}: zorla sonlandırıldı.")

    def restart_service(self, svc: ServiceConfig) -> None:
        if svc.service_type == "windows_service":
            if not svc.windows_service_name:
                self._set_action_info(f"{svc.name}: Windows servis adı tanımlı değil.", is_error=True)
                return
            result = run_ps(f"Restart-Service -Name '{svc.windows_service_name}' -Force")
            if result.returncode == 0:
                self._set_action_info(f"{svc.name}: yeniden başlat komutu gönderildi.")
            else:
                self._set_action_info(f"{svc.name}: yeniden başlatılamadı. {result.stderr.strip()}", is_error=True)
            return
        self.stop_service(svc)
        time.sleep(0.3)
        self.start_service(svc)

    def start_all(self) -> None:
        for svc in self.services:
            self.start_service(svc)

    def stop_all(self) -> None:
        for svc in self.services:
            self.stop_service(svc)

    def restart_all(self) -> None:
        for svc in self.services:
            self.restart_service(svc)

    def _spawn_process(self, command: list[str], cwd: str, env: dict[str, str]) -> subprocess.Popen:
        if not command:
            raise RuntimeError("Komut boş.")

        attempts = [command]
        cmd0 = command[0].lower()

        if cmd0 == "npm":
            attempts.insert(0, ["cmd", "/c", *command])
        elif cmd0 == "py" and len(command) >= 4 and command[2] == "-m":
            # py launcher bulunamazsa mevcut python ile aynı modülü çalıştır.
            attempts.append([sys.executable, "-m", *command[3:]])

        last_error: Exception | None = None
        for candidate in attempts:
            try:
                return subprocess.Popen(
                    candidate,
                    cwd=cwd,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                )
            except Exception as ex:
                last_error = ex
        raise RuntimeError(f"Process başlatılamadı: {last_error}")

    def _set_action_info(self, text: str, is_error: bool = False) -> None:
        self.action_info.configure(text=text, foreground="#b91c1c" if is_error else "#166534")

    def _set_action_info_threadsafe(self, text: str, is_error: bool = False) -> None:
        self.root.after(0, lambda: self._set_action_info(text, is_error))

    def _poll_status(self) -> None:
        status_payload: dict[str, tuple[str, str]] = {}
        service_names = [svc.windows_service_name for svc in self.services if svc.service_type == "windows_service"]
        windows_states = get_windows_services_state(service_names)

        for svc in self.services:
            healthy = "UP" if is_port_open(svc.health_host, svc.health_port) else "DOWN"
            if svc.service_type == "windows_service":
                state = windows_states.get(svc.windows_service_name, "")
                if not state:
                    state = "RUNNING_EXTERNAL" if healthy == "UP" else "NOT_FOUND"
            else:
                process = self.processes.get(svc.name)
                if process is not None and process.poll() is None:
                    state = "RUNNING"
                else:
                    state = "RUNNING_EXTERNAL" if healthy == "UP" else "STOPPED"
            status_payload[svc.name] = (state, healthy)
        self.status_queue = [status_payload]

    def _start_status_worker(self) -> None:
        def _worker() -> None:
            while not self._stop_event.is_set():
                self._poll_status()
                self._stop_event.wait(REFRESH_MS / 1000)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def _apply_status_updates(self) -> None:
        latest = self.status_queue[-1] if self.status_queue else None
        if latest:
            for svc_name, (state, healthy) in latest.items():
                row = self.rows.get(svc_name)
                if not row:
                    continue
                state_lbl: tk.Label = row["state"]
                health_lbl: tk.Label = row["health"]
                cfg: ServiceConfig = row["cfg"]
                state_text, state_color = self._format_state(state)
                health_text, health_color = self._format_health(healthy, cfg.health_host, cfg.health_port)
                state_lbl.configure(text=state_text, fg=state_color)
                health_lbl.configure(text=health_text, fg=health_color)
            self.status_queue.clear()
        self.root.after(200, self._apply_status_updates)

    @staticmethod
    def _format_state(state: str) -> tuple[str, str]:
        normalized = state.upper().strip()
        if normalized == "RUNNING":
            return "● ÇALIŞIYOR", "#15803d"
        if normalized == "RUNNING_EXTERNAL":
            return "● ÇALIŞIYOR", "#15803d"
        if normalized in {"STOPPED", "STOP_PENDING"}:
            return "● DURDU", "#b45309"
        if normalized in {"START_PENDING", "CONTINUE_PENDING"}:
            return "● BAŞLATILIYOR", "#1d4ed8"
        if normalized in {"PAUSED", "PAUSE_PENDING"}:
            return "● DURAKLATILDI", "#7c3aed"
        if normalized == "NOT_FOUND":
            return "● SERVİS BULUNAMADI", "#dc2626"
        return f"● {normalized}", "#475569"

    @staticmethod
    def _format_health(health: str, host: str, port: int) -> tuple[str, str]:
        if health == "UP":
            return f"● ERİŞİLEBİLİR ({host}:{port})", "#15803d"
        return f"● ERİŞİLEMİYOR ({host}:{port})", "#dc2626"

    @staticmethod
    def _friendly_service_type(service_type: str) -> str:
        if service_type == "windows_service":
            return "Windows Servisi"
        if service_type == "process":
            return "Uygulama Prosesi"
        return service_type

    def _on_close(self) -> None:
        self._stop_event.set()
        for name, process in self.processes.items():
            if process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=3)
                except Exception:
                    pass
                _ = name
        time.sleep(0.1)
        self.root.destroy()


def main() -> None:
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"Config file not found: {CONFIG_FILE}")
    services = read_config()
    root = tk.Tk()
    app = ServiceControlPanel(root, services)
    _ = app
    root.mainloop()


if __name__ == "__main__":
    main()
