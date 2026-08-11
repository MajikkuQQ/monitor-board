# -*- coding: utf-8 -*-
"""
Детект питания монитора через DDC/CI (VCP 0xD6 Power Mode).

Почему не EnumDisplayDevices / WMI:
    Если монитор на USB-C (видео + питание одним кабелем), Windows при
    выключении кнопкой часто не убирает дисплей из списка — EDID кэшируется.
    Реальное состояние питания спрашиваем у монитора по DDC/CI (dxva2.dll).
"""

from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes
from dataclasses import dataclass

logger = logging.getLogger(__name__)

VCP_POWER_MODE = 0xD6  # 1=on, 4/5=off, 2/3=standby/suspend


@dataclass
class DetectedMonitor:
    key: str
    name: str
    powered_on: bool


class PHYSICAL_MONITOR(ctypes.Structure):
    _fields_ = [
        ("hPhysicalMonitor", wintypes.HANDLE),
        ("szPhysicalMonitorDescription", wintypes.WCHAR * 128),
    ]


MONITORENUMPROC = ctypes.WINFUNCTYPE(
    wintypes.BOOL,
    wintypes.HMONITOR,
    wintypes.HDC,
    ctypes.POINTER(wintypes.RECT),
    wintypes.LPARAM,
)


def _load_libs():
    if sys.platform != "win32":
        raise RuntimeError("DDC/CI agent поддерживается только на Windows")
    return ctypes.WinDLL("dxva2.dll"), ctypes.WinDLL("user32.dll")


def enum_hmonitors(user32) -> list:
    handles: list = []

    def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
        handles.append(hMonitor)
        return True

    user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(callback), 0)
    return handles


def get_physical_monitors(dxva2, hMonitor) -> list[PHYSICAL_MONITOR]:
    count = wintypes.DWORD()
    if not dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hMonitor, ctypes.byref(count)):
        return []
    if count.value == 0:
        return []
    arr = (PHYSICAL_MONITOR * count.value)()
    if not dxva2.GetPhysicalMonitorsFromHMONITOR(hMonitor, count.value, arr):
        return []
    return list(arr)


def destroy_physical_monitors(dxva2, monitors: list[PHYSICAL_MONITOR]) -> None:
    for m in monitors:
        try:
            dxva2.DestroyPhysicalMonitor(m.hPhysicalMonitor)
        except Exception:
            pass


def _probe_power(dxva2, handle) -> tuple[bool, bool]:
    """
    Returns (responded, powered_on).
    responded=False — DDC/CI не ответил (часто = выключен кнопкой).
    """
    p_type = wintypes.DWORD()
    current = wintypes.DWORD()
    maximum = wintypes.DWORD()
    ok = dxva2.GetVCPFeatureAndVCPFeatureReply(
        handle,
        ctypes.c_ubyte(VCP_POWER_MODE),
        ctypes.byref(p_type),
        ctypes.byref(current),
        ctypes.byref(maximum),
    )
    if not ok:
        return False, False
    return True, current.value == 1


def list_monitors() -> list[DetectedMonitor]:
    """
    Все физические мониторы, найденные через DDC/CI API.
    powered_on=True только если VCP 0xD6 == 1.
    Если DDC не отвечает — powered_on=False (считаем выключенным).
    """
    try:
        dxva2, user32 = _load_libs()
    except Exception:
        logger.exception("Не удалось загрузить dxva2/user32")
        return []

    hmonitors = enum_hmonitors(user32)
    if not hmonitors:
        logger.warning("EnumDisplayMonitors: нет HMONITOR")
        return []

    result: list[DetectedMonitor] = []
    index = 0

    for hMonitor in hmonitors:
        phys_list = get_physical_monitors(dxva2, hMonitor)
        if not phys_list:
            continue
        try:
            for pm in phys_list:
                index += 1
                name = (pm.szPhysicalMonitorDescription or "").strip() or f"Monitor {index}"
                # Стабильный ключ в рамках точки: описание + порядковый номер
                key = f"ddc:{index}:{name}"
                responded, powered_on = _probe_power(dxva2, pm.hPhysicalMonitor)
                if not responded:
                    logger.info("DDC/CI нет ответа: %s — считаем выключенным", name)
                result.append(
                    DetectedMonitor(key=key, name=name, powered_on=powered_on)
                )
        finally:
            destroy_physical_monitors(dxva2, phys_list)

    return result


def list_monitors_payload() -> list[dict[str, str]]:
    """
    Для heartbeat сервера: в списке только реально включённые (DDC on).
    Отсутствующий монитор сервер пометит как offline / откроет инцидент.
    """
    payload: list[dict[str, str]] = []
    for m in list_monitors():
        if m.powered_on:
            payload.append({"key": m.key, "name": m.name})
        else:
            logger.debug("Monitor off/no-DDC: %s", m.name)
    return payload
