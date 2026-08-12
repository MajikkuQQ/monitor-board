# -*- coding: utf-8 -*-
"""
Простой установщик MonitorAgent.
Собирается в MonitorAgentSetup.exe и кладёт агент в выбранную папку,
пишет config.json и создаёт автозапуск при входе в Windows.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


DEFAULT_SERVER = "http://YOUR_SERVER:8787"
DEFAULT_DIR = r"C:\monitor-agent"
TASK_NAME = "MonitorAgent"
EXE_NAME = "MonitorAgent.exe"


def resource_path(name: str) -> Path:
    """Файл рядом с установщиком или внутри PyInstaller bundle."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundled = Path(sys._MEIPASS) / name
        if bundled.exists():
            return bundled
        beside = Path(sys.executable).resolve().parent / name
        if beside.exists():
            return beside
        return bundled
    return Path(__file__).resolve().parent / "dist" / name


def is_admin() -> bool:
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def run_powershell(script: str) -> None:
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(detail or f"PowerShell exit {completed.returncode}")


def create_autostart(exe_path: Path, work_dir: Path) -> None:
    # Удалить старую задачу, создать новую при входе текущего пользователя
    user = os.environ.get("USERNAME", "")
    exe = str(exe_path)
    wd = str(work_dir)
    script = f"""
$ErrorActionPreference = 'Stop'
Unregister-ScheduledTask -TaskName '{TASK_NAME}' -Confirm:$false -ErrorAction SilentlyContinue
Get-Process -Name 'MonitorAgent' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
$action = New-ScheduledTaskAction -Execute '{exe}' -WorkingDirectory '{wd}'
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero)
$principal = New-ScheduledTaskPrincipal -UserId '{user}' -LogonType Interactive -RunLevel Highest
Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Start-ScheduledTask -TaskName '{TASK_NAME}'
"""
    run_powershell(script)


def remove_autostart() -> None:
    script = f"""
Unregister-ScheduledTask -TaskName '{TASK_NAME}' -Confirm:$false -ErrorAction SilentlyContinue
Get-Process -Name 'MonitorAgent' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
"""
    run_powershell(script)


def install(target_dir: Path, server_url: str, token: str, hostname: str) -> Path:
    src_exe = resource_path(EXE_NAME)
    if not src_exe.exists():
        raise FileNotFoundError(
            f"Не найден {EXE_NAME}. Пересоберите пакет через build.ps1"
        )

    target_dir.mkdir(parents=True, exist_ok=True)
    dest_exe = target_dir / EXE_NAME
    shutil.copy2(src_exe, dest_exe)

    config = {
        "server_url": server_url.rstrip("/"),
        "agent_token": token.strip(),
        "hostname": hostname.strip() or None,
        "poll_interval_sec": 5,
        "debounce_checks": 3,
        "request_timeout_sec": 10,
    }
    (target_dir / "config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # короткий readme
    (target_dir / "README.txt").write_text(
        "MonitorAgent\n"
        "Лог: agent.log\n"
        "Автозапуск: Планировщик заданий -> MonitorAgent\n"
        "Удаление: снова запустите установщик и нажмите «Удалить»\n",
        encoding="utf-8",
    )

    create_autostart(dest_exe, target_dir)
    return dest_exe


class InstallerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Установка Monitor Agent")
        self.geometry("520x420")
        self.minsize(480, 400)
        self.configure(padx=16, pady=16)

        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")

        ttk.Label(
            self,
            text="Агент мониторинга мониторов",
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            self,
            text="Python не нужен. Укажите данные точки и нажмите «Установить».",
            foreground="#444",
        ).pack(anchor="w", pady=(0, 12))

        form = ttk.Frame(self)
        form.pack(fill="x")

        self.var_dir = tk.StringVar(value=DEFAULT_DIR)
        self.var_server = tk.StringVar(value=DEFAULT_SERVER)
        self.var_token = tk.StringVar()
        self.var_host = tk.StringVar()

        self._row(form, 0, "Папка установки", self.var_dir, browse=True)
        self._row(form, 1, "Адрес сервера", self.var_server)
        self._row(form, 2, "Токен точки", self.var_token)
        self._row(form, 3, "Имя точки", self.var_host)

        ttk.Label(
            form,
            text="Пример имени: Касса-1",
            foreground="#666",
            font=("Segoe UI", 8),
        ).grid(row=4, column=1, sticky="w", pady=(0, 8))

        btns = ttk.Frame(self)
        btns.pack(fill="x", pady=12)
        ttk.Button(btns, text="Установить", command=self.on_install).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(btns, text="Удалить с ПК", command=self.on_uninstall).pack(
            side="left"
        )
        ttk.Button(btns, text="Выход", command=self.destroy).pack(side="right")

        self.status = tk.StringVar(
            value="Администратор: права администратора желательны для автозапуска."
        )
        ttk.Label(self, textvariable=self.status, wraplength=480).pack(
            anchor="w", pady=(8, 0)
        )

        if not is_admin():
            self.status.set(
                "Внимание: запущено без прав администратора. "
                "Автозапуск может не создаться — запустите установщик правой кнопкой → от администратора."
            )

    def _row(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
        browse: bool = False,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=6)
        entry = ttk.Entry(parent, textvariable=variable, width=48)
        entry.grid(row=row, column=1, sticky="ew", pady=6, padx=(8, 0))
        if browse:
            ttk.Button(
                parent,
                text="…",
                width=3,
                command=self._browse,
            ).grid(row=row, column=2, padx=(6, 0))
        parent.columnconfigure(1, weight=1)

    def _browse(self) -> None:
        path = filedialog.askdirectory(initialdir=self.var_dir.get() or DEFAULT_DIR)
        if path:
            self.var_dir.set(path)

    def on_install(self) -> None:
        token = self.var_token.get().strip()
        host = self.var_host.get().strip()
        server = self.var_server.get().strip()
        target = Path(self.var_dir.get().strip() or DEFAULT_DIR)

        if not token:
            messagebox.showerror("Ошибка", "Введите токен точки.")
            return
        if not server:
            messagebox.showerror("Ошибка", "Введите адрес сервера.")
            return
        if not host:
            if not messagebox.askyesno(
                "Имя точки",
                "Имя точки пустое. Продолжить? Будет использовано имя компьютера.",
            ):
                return

        try:
            self.status.set("Установка…")
            self.update_idletasks()
            dest = install(target, server, token, host)
            self.status.set(f"Установлено: {dest}")
            messagebox.showinfo(
                "Готово",
                f"Агент установлен в:\n{target}\n\n"
                f"Автозапуск: задача «{TASK_NAME}» при входе в Windows.\n"
                f"Лог: {target / 'agent.log'}",
            )
        except Exception as exc:
            self.status.set("Ошибка установки")
            messagebox.showerror("Ошибка", str(exc))

    def on_uninstall(self) -> None:
        target = Path(self.var_dir.get().strip() or DEFAULT_DIR)
        if not messagebox.askyesno(
            "Удаление",
            f"Остановить агент и убрать автозапуск?\nПапка {target} останется (можете удалить вручную).",
        ):
            return
        try:
            remove_autostart()
            self.status.set("Автозапуск удалён")
            messagebox.showinfo("Готово", "Автозапуск и процесс остановлены.")
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc))


def main() -> None:
    # Если запустили не из GUI-контекста с админом — можно продолжить, предупреждение уже есть
    app = InstallerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
