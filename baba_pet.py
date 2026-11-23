"""爸爸桌宠 — a little crawling desktop pet that follows the mouse.

Pure Python (standard library only) + the pre-rendered sprites in assets/sprites.
Windows 10/11. No console window needed when launched with pythonw.exe.

Controls:
    left click  -> 爸爸
    right click -> menu (pause / resume, say, recenter, quit)
    Ctrl+Alt+P  -> pause / resume following
    Ctrl+Alt+Q  -> quit
"""
from __future__ import annotations

import ctypes
import json
import logging
import math
import random
import struct
import sys
import time
from ctypes import wintypes as wt
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
SPRITES = ASSETS / "sprites"
LOG_PATH = ROOT / "pet.log"

W, H = 280, 220
BASE_SCALE = 1.12
MAX_SPEED = 560.0

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
HCURSOR = wt.HANDLE
UINT_PTR = ctypes.c_size_t

# Window messages / styles
WM_DESTROY = 0x0002
WM_TIMER = 0x0113
WM_LBUTTONDOWN = 0x0201
WM_RBUTTONUP = 0x0205
WM_HOTKEY = 0x0312
WM_DPICHANGED = 0x02E0
WM_NCHITTEST = 0x0084
WM_NULL = 0x0000
HTTRANSPARENT = -1
WS_POPUP = 0x80000000
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
WS_EX_TRANSPARENT = 0x00000020
WS_EX_NOACTIVATE = 0x08000000
SW_SHOWNOACTIVATE = 4
SW_HIDE = 0
ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
DIB_RGB_COLORS = 0
HWND_TOPMOST = wt.HWND(-1)
HWND_NOTOPMOST = wt.HWND(-2)
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
TPM_RETURNCMD = 0x0100
TPM_NONOTIFY = 0x0080
TPM_RIGHTBUTTON = 0x0002
MF_STRING = 0x0000
MF_SEPARATOR = 0x0800
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
VK_P = 0x50
VK_Q = 0x51
ERROR_ALREADY_EXISTS = 183
MONITOR_DEFAULTTONEAREST = 2
PM_REMOVE = 0x0001
WM_QUIT = 0x0012
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.UINT),
        ("style", wt.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wt.HINSTANCE),
        ("hIcon", wt.HICON),
        ("hCursor", HCURSOR),
        ("hbrBackground", wt.HBRUSH),
        ("lpszMenuName", wt.LPCWSTR),
        ("lpszClassName", wt.LPCWSTR),
        ("hIconSm", wt.HICON),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wt.DWORD),
        ("biWidth", wt.LONG),
        ("biHeight", wt.LONG),
        ("biPlanes", wt.WORD),
        ("biBitCount", wt.WORD),
        ("biCompression", wt.DWORD),
        ("biSizeImage", wt.DWORD),
        ("biXPelsPerMeter", wt.LONG),
        ("biYPelsPerMeter", wt.LONG),
        ("biClrUsed", wt.DWORD),
        ("biClrImportant", wt.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", wt.BYTE),
        ("BlendFlags", wt.BYTE),
        ("SourceConstantAlpha", wt.BYTE),
        ("AlphaFormat", wt.BYTE),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("rcMonitor", wt.RECT),
        ("rcWork", wt.RECT),
        ("dwFlags", wt.DWORD),
    ]


class Frame:
    __slots__ = ("w", "h", "data")

    def __init__(self, w, h, data):
        self.w, self.h, self.data = w, h, data


def load_bmp(path: Path) -> Frame:
    data = path.read_bytes()
    if len(data) < 54 or data[:2] != b"BM":
        raise ValueError(f"not a BMP: {path}")
    off = struct.unpack_from("<I", data, 10)[0]
    w, h = struct.unpack_from("<ii", data, 18)
    bpp = struct.unpack_from("<H", data, 28)[0]
    comp = struct.unpack_from("<I", data, 30)[0]
    if bpp != 32 or comp != 0 or h >= 0:
        raise ValueError(f"unexpected BMP format: {path} ({w}x{h}, {bpp}bpp, comp={comp})")
    h = -h
    need = w * h * 4
    pixels = data[off:off + need]
    if len(pixels) != need:
        raise ValueError(f"truncated BMP: {path}")
    return Frame(w, h, pixels)


def show_error(text: str):
    try:
        user32.MessageBoxW(None, text, "爸爸桌宠", 0x10)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# native helpers
# ---------------------------------------------------------------------------

def _setup_signatures():
    user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    user32.DefWindowProcW.restype = LRESULT
    user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
    user32.RegisterClassExW.restype = wt.ATOM
    user32.CreateWindowExW.argtypes = [
        wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wt.HWND, wt.HMENU, wt.HINSTANCE, ctypes.c_void_p,
    ]
    user32.CreateWindowExW.restype = wt.HWND
    user32.UpdateLayeredWindow.argtypes = [
        wt.HWND, wt.HDC, ctypes.POINTER(wt.POINT), ctypes.POINTER(wt.SIZE),
        wt.HDC, ctypes.POINTER(wt.POINT), wt.DWORD,
        ctypes.POINTER(BLENDFUNCTION), wt.DWORD,
    ]
    user32.UpdateLayeredWindow.restype = wt.BOOL
    user32.GetDC.argtypes = [wt.HWND]
    user32.GetDC.restype = wt.HDC
    user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
    user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
    user32.DestroyWindow.argtypes = [wt.HWND]
    user32.DefWindowProcW.restype = LRESULT
    user32.SetTimer.argtypes = [wt.HWND, UINT_PTR, wt.UINT, ctypes.c_void_p]
    user32.SetTimer.restype = UINT_PTR
    user32.KillTimer.argtypes = [wt.HWND, UINT_PTR]
    user32.PostQuitMessage.argtypes = [ctypes.c_int]
    user32.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]
    user32.GetCursorPos.restype = wt.BOOL
    user32.MonitorFromPoint.argtypes = [wt.POINT, wt.DWORD]
    user32.MonitorFromPoint.restype = wt.HMONITOR
    user32.MonitorFromWindow.argtypes = [wt.HWND, wt.DWORD]
    user32.MonitorFromWindow.restype = wt.HMONITOR
    user32.GetMonitorInfoW.argtypes = [wt.HMONITOR, ctypes.POINTER(MONITORINFO)]
    user32.GetMonitorInfoW.restype = wt.BOOL
    user32.SetForegroundWindow.argtypes = [wt.HWND]
    user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    user32.CreatePopupMenu.restype = wt.HMENU
    user32.AppendMenuW.argtypes = [wt.HMENU, wt.UINT, UINT_PTR, wt.LPCWSTR]
    user32.TrackPopupMenu.argtypes = [wt.HMENU, wt.UINT, ctypes.c_int, ctypes.c_int,
                                      ctypes.c_int, wt.HWND, ctypes.c_void_p]
    user32.TrackPopupMenu.restype = ctypes.c_int
    user32.DestroyMenu.argtypes = [wt.HMENU]
    user32.RegisterHotKey.argtypes = [wt.HWND, ctypes.c_int, wt.UINT, wt.UINT]
    user32.UnregisterHotKey.argtypes = [wt.HWND, ctypes.c_int]
    user32.MessageBoxW.argtypes = [wt.HWND, wt.LPCWSTR, wt.LPCWSTR, wt.UINT]
    user32.LoadCursorW.argtypes = [wt.HINSTANCE, ctypes.c_void_p]
    user32.LoadCursorW.restype = HCURSOR
    user32.LoadIconW.argtypes = [wt.HINSTANCE, ctypes.c_void_p]
    user32.LoadIconW.restype = wt.HICON
    user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, wt.UINT]
    user32.GetSystemMetrics.argtypes = [ctypes.c_int]
    user32.GetSystemMetrics.restype = ctypes.c_int
    user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
    user32.GetMessageW.restype = wt.BOOL
    user32.PeekMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT, wt.UINT]
    user32.PeekMessageW.restype = wt.BOOL
    user32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
    user32.DispatchMessageW.restype = LRESULT
    try:
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        user32.SetProcessDpiAwarenessContext.restype = wt.BOOL
    except AttributeError:
        pass
    try:
        user32.SetProcessDPIAware.restype = wt.BOOL
    except AttributeError:
        pass
    try:
        user32.GetDpiForWindow.argtypes = [wt.HWND]
        user32.GetDpiForWindow.restype = wt.UINT
    except AttributeError:
        pass
    gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
    gdi32.CreateCompatibleDC.restype = wt.HDC
    gdi32.CreateDIBSection.argtypes = [wt.HDC, ctypes.POINTER(BITMAPINFO), wt.UINT,
                                       ctypes.POINTER(ctypes.c_void_p), wt.HANDLE, wt.DWORD]
    gdi32.CreateDIBSection.restype = wt.HBITMAP
    gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
    gdi32.SelectObject.restype = wt.HGDIOBJ
    gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
    gdi32.DeleteDC.argtypes = [wt.HDC]
    gdi32.DeleteDC.restype = wt.BOOL
    kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wt.HMODULE
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.LPCWSTR]
    kernel32.CreateMutexW.restype = wt.HANDLE


class Surface:
    """A top-down 32-bit premultiplied BGRA DIB + memory DC."""

    def __init__(self, screen_dc, w, h):
        self.w, self.h = w, h
        self.memdc = gdi32.CreateCompatibleDC(screen_dc)
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0
        bmi.bmiHeader.biSizeImage = w * h * 4
        self.bits = ctypes.c_void_p()
        self.bitmap = gdi32.CreateDIBSection(screen_dc, ctypes.byref(bmi), DIB_RGB_COLORS,
                                             ctypes.byref(self.bits), None, 0)
        if not self.memdc or not self.bitmap:
            raise OSError("CreateDIBSection failed")
        self.old = gdi32.SelectObject(self.memdc, self.bitmap)

    def upload(self, data: bytes):
        if len(data) != self.w * self.h * 4:
            raise ValueError("bad pixel buffer size")
        ctypes.memmove(self.bits, data, len(data))

    def close(self):
        try:
            if self.old:
                gdi32.SelectObject(self.memdc, self.old)
            if self.bitmap:
                gdi32.DeleteObject(self.bitmap)
            if self.memdc:
                gdi32.DeleteDC(self.memdc)
        except Exception:
            pass


class Pet:
    def __init__(self):
        self.running = True
        self.paused = False
        self.hwnd = None
        self.bubble_hwnd = None
        self.pet_proc_ref = None
        self.bubble_proc_ref = None
        self.screen_dc = None
        self.pet_surface = None
        self.bubble_surface = None
        self.frames = {}
        self.bubbles = []
        self.scale = BASE_SCALE
        self.x = 0
        self.y = 0
        self.facing = "r"
        self.gait = 0.0
        self.idle_t = 0.0
        self.flip_hold = 0.0
        self.last_move = 0.0
        self.frame_key = None
        self.last_cursor = wt.POINT(0, 0)
        self.last_t = time.perf_counter()
        self.next_say = time.perf_counter() + 1.8
        self.bubble_start = 0.0
        self.bubble_end = 0.0
        self.bubble_idx = 0
        self.bubble_visible = False
        self.bubble_shown = False
        self.bubble_last_key = -1
        self.bubble_alpha = 0
        self.destroying = False
        self.last_top = 0.0
        self.menu_open = False
        self.last_draw = None
        self.phrases = ["爸爸", "爸爸~", "爸爸！", "爸爸？"]

    # ---- setup -----------------------------------------------------------
    def load_frames(self):
        needed = []
        for direction in ("r", "l"):
            for i in range(8):
                needed.append(f"pet_{direction}_c{i}.bmp")
            for i in range(4):
                needed.append(f"pet_{direction}_i{i}.bmp")
        for name in needed:
            self.frames[name[:-4]] = load_bmp(SPRITES / name)
        for i in range(4):
            self.bubbles.append(load_bmp(SPRITES / f"bubble_{i}.bmp"))

    def create(self):
        _setup_signatures()
        self.load_frames()
        self.screen_dc = user32.GetDC(None)
        src = self.frames["pet_r_c0"]
        self.pet_surface = Surface(self.screen_dc, src.w, src.h)
        bsrc = self.bubbles[0]
        self.bubble_surface = Surface(self.screen_dc, bsrc.w, bsrc.h)

        hinst = kernel32.GetModuleHandleW(None)
        hcursor = user32.LoadCursorW(None, ctypes.c_void_p(32512))
        hicon = user32.LoadIconW(None, ctypes.c_void_p(32512))

        self.pet_proc_ref = WNDPROC(self._pet_wndproc)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = self.pet_proc_ref
        wc.hInstance = hinst
        wc.hCursor = hcursor
        wc.hIcon = hicon
        wc.lpszClassName = "BabaPetWnd_v1"
        if not user32.RegisterClassExW(ctypes.byref(wc)):
            raise ctypes.WinError(ctypes.get_last_error())

        self.bubble_proc_ref = WNDPROC(self._bubble_wndproc)
        wc2 = WNDCLASSEXW()
        wc2.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc2.lpfnWndProc = self.bubble_proc_ref
        wc2.hInstance = hinst
        wc2.lpszClassName = "BabaPetBubble_v1"
        if not user32.RegisterClassExW(ctypes.byref(wc2)):
            raise ctypes.WinError(ctypes.get_last_error())

        exstyle = WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_TOPMOST | WS_EX_NOACTIVATE
        self.hwnd = user32.CreateWindowExW(
            exstyle, "BabaPetWnd_v1", "爸爸桌宠", WS_POPUP,
            0, 0, 10, 10, None, None, hinst, None)
        if not self.hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        self.bubble_hwnd = user32.CreateWindowExW(
            exstyle, "BabaPetBubble_v1", "", WS_POPUP,
            0, 0, 10, 10, None, None, hinst, None)
        if not self.bubble_hwnd:
            raise ctypes.WinError(ctypes.get_last_error())

        # keep the pet topmost even if some other app re-orders topmost windows
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

        pt = wt.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        self.last_cursor = pt
        self.recenter(pt, initial=True)
        self.draw_pet(force=True)
        self.draw_bubble(0.0, force=True)
        user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        user32.RegisterHotKey(self.hwnd, 10, MOD_CONTROL | MOD_ALT, VK_P)
        user32.RegisterHotKey(self.hwnd, 11, MOD_CONTROL | MOD_ALT, VK_Q)
        self.next_say = time.perf_counter() + 1.6

    def dpi(self):
        try:
            d = user32.GetDpiForWindow(self.hwnd)
            return d if d else 96
        except Exception:
            return 96

    def refresh_scale(self):
        self.scale = BASE_SCALE * self.dpi() / 96.0
        self.disp_w = max(1, round(W * self.scale))
        self.disp_h = max(1, round(H * self.scale))

    # ---- geometry --------------------------------------------------------
    def head_center(self):
        hx = 198 if self.facing == "r" else W - 198
        return self.x + hx * self.scale, self.y + 82 * self.scale

    def head_top(self):
        hx = 198 if self.facing == "r" else W - 198
        return self.x + hx * self.scale, self.y + 30 * self.scale

    def work_area(self, use_cursor=True):
        if use_cursor:
            pt = wt.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            mon = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
        else:
            mon = user32.MonitorFromWindow(self.hwnd, MONITOR_DEFAULTTONEAREST)
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if mon and user32.GetMonitorInfoW(mon, ctypes.byref(mi)):
            return mi.rcWork
        return wt.RECT(0, 0,
                       user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
                       user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))

    def clamp(self, use_cursor=True):
        wa = self.work_area(use_cursor)
        max_x = wa.right - self.disp_w
        max_y = wa.bottom - self.disp_h
        min_x = wa.left
        min_y = wa.top
        if max_x < min_x:
            max_x = min_x
        if max_y < min_y:
            max_y = min_y
        self.x = min(max(self.x, min_x), max_x)
        self.y = min(max(self.y, min_y), max_y)

    def recenter(self, pt=None, initial=False):
        if pt is None:
            pt = wt.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
        self.facing = "r"
        self.refresh_scale()
        hx = 198
        target_x = pt.x - 22 * self.scale
        target_y = pt.y + 26 * self.scale
        self.x = target_x - hx * self.scale
        self.y = target_y - 82 * self.scale
        self.clamp()

    # ---- painting --------------------------------------------------------
    def draw_pet(self, force=False):
        key = self.current_frame_key()
        pos = (round(self.x), round(self.y), self.disp_w, self.disp_h)
        if not force and key == self.frame_key and pos == self.last_draw:
            return
        if force or key != self.frame_key:
            frame = self.frames[key]
            self.pet_surface.upload(frame.data)
            self.frame_key = key
        self.blit(self.hwnd, self.pet_surface, self.x, self.y, self.disp_w, self.disp_h, 255)
        self.last_draw = pos

    def draw_bubble(self, alpha, force=False):
        idx = self.bubble_idx
        if force or idx != self.bubble_last_key:
            frame = self.bubbles[idx]
            self.bubble_surface.upload(frame.data)
            self.bubble_last_key = idx
        self.bubble_alpha = alpha

    def blit(self, hwnd, surface, x, y, w, h, alpha):
        dst = wt.POINT(int(x), int(y))
        size = wt.SIZE(int(w), int(h))
        src = wt.POINT(0, 0)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, max(0, min(255, int(alpha))), AC_SRC_ALPHA)
        ok = user32.UpdateLayeredWindow(hwnd, self.screen_dc, ctypes.byref(dst),
                                        ctypes.byref(size), surface.memdc, ctypes.byref(src),
                                        0, ctypes.byref(blend), ULW_ALPHA)
        if not ok:
            logging.warning("UpdateLayeredWindow failed hwnd=%s: %s", hwnd, ctypes.get_last_error())

    def current_frame_key(self):
        if self.paused or time.perf_counter() - self.last_move > 0.20:
            idx = int(self.idle_t * 2.6) % 4
            return f"pet_{self.facing}_i{idx}"
        idx = int(self.gait * 8) % 8
        return f"pet_{self.facing}_c{idx}"

    # ---- speech ----------------------------------------------------------
    def say(self, text=None):
        if text is None:
            r = random.random()
            if r < 0.70:
                text = "爸爸"
            elif r < 0.82:
                text = "爸爸~"
            elif r < 0.92:
                text = "爸爸！"
            else:
                text = "爸爸？"
        try:
            self.bubble_idx = self.phrases.index(text)
        except ValueError:
            self.bubble_idx = 0
        now = time.perf_counter()
        self.bubble_start = now
        self.bubble_end = now + 2.9
        self.bubble_visible = True
        self.next_say = now + random.uniform(7.5, 15.0)
        # draw the bubble at its smallest immediately so the fade-in is visible
        self.update_bubble(now)

    def update_bubble(self, now):
        if not self.bubble_visible:
            return
        elapsed = now - self.bubble_start
        if elapsed >= self.bubble_end - self.bubble_start:
            if self.bubble_shown:
                user32.ShowWindow(self.bubble_hwnd, SW_HIDE)
                self.bubble_shown = False
            self.bubble_visible = False
            return
        # pop-in / settle
        if elapsed < 0.16:
            pop = 0.74 + 0.34 * (elapsed / 0.16)
        elif elapsed < 0.30:
            pop = 1.08 - 0.08 * ((elapsed - 0.16) / 0.14)
        else:
            pop = 1.0
        # fade in / out
        alpha = 255.0
        if elapsed < 0.12:
            alpha = 255.0 * (elapsed / 0.12)
        remain = (self.bubble_end - self.bubble_start) - elapsed
        if remain < 0.30:
            alpha = 255.0 * max(0.0, remain / 0.30)
        self.draw_bubble(alpha)
        head_x, head_top = self.head_top()
        bw = self.bubbles[self.bubble_idx].w * self.scale * pop
        bh = self.bubbles[self.bubble_idx].h * self.scale * pop
        # tail tip in the bubble bitmap is around (110, 108) of (220, 120)
        tail_x = head_x
        tail_y = head_top + 7 * self.scale
        bx = tail_x - bw * (110.0 / 220.0)
        by = tail_y - bh * (108.0 / 120.0)
        wa = self.work_area(use_cursor=False)
        bx = min(max(bx, wa.left + 2), max(wa.left + 2, wa.right - bw - 2))
        by = min(max(by, wa.top + 2), max(wa.top + 2, wa.bottom - bh - 2))
        self.blit(self.bubble_hwnd, self.bubble_surface, bx, by, bw, bh, alpha)
        if not self.bubble_shown:
            user32.ShowWindow(self.bubble_hwnd, SW_SHOWNOACTIVATE)
            self.bubble_shown = True

    # ---- update loop -----------------------------------------------------
    def tick(self):
        now = time.perf_counter()
        dt = max(0.0, min(0.10, now - self.last_t))
        self.last_t = now
        if not self.paused:
            self.update_motion(now, dt)
        else:
            self.idle_t += dt
        self.draw_pet()
        self.update_bubble(now)
        if now >= self.next_say and not self.bubble_visible:
            self.say()
        self.raise_topmost(now)

    def raise_topmost(self, now):
        if self.menu_open or now - self.last_top < 0.45:
            return
        self.last_top = now
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        user32.BringWindowToTop(self.hwnd)
        if self.bubble_shown:
            user32.SetWindowPos(self.bubble_hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
            user32.BringWindowToTop(self.bubble_hwnd)

    def update_motion(self, now, dt):
        self.refresh_scale()
        self.idle_t += dt
        pt = wt.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        head_x, head_y = self.head_center()
        dx = pt.x - head_x
        # decide facing with a little hysteresis
        want = "r" if dx >= 0 else "l"
        if want != self.facing and abs(dx) > 26 * self.scale:
            self.flip_hold += dt
            if self.flip_hold >= 0.14:
                old_hx = 198 if self.facing == "r" else W - 198
                self.facing = want
                new_hx = 198 if self.facing == "r" else W - 198
                self.x += (old_hx - new_hx) * self.scale
                self.flip_hold = 0.0
                head_x, head_y = self.head_center()
        else:
            self.flip_hold = 0.0

        if self.facing == "r":
            target_head_x = pt.x - 22 * self.scale
        else:
            target_head_x = pt.x + 22 * self.scale
        target_head_y = pt.y + 26 * self.scale
        hx_src = 198 if self.facing == "r" else W - 198
        tx = target_head_x - hx_src * self.scale
        ty = target_head_y - 82 * self.scale

        ddx, ddy = tx - self.x, ty - self.y
        dist = math.hypot(ddx, ddy)
        moved = 0.0
        if dist > 0.7:
            speed = min(MAX_SPEED * self.scale, 90 * self.scale + dist * 4.2)
            step = min(dist, speed * dt)
            self.x += ddx / dist * step
            self.y += ddy / dist * step
            moved = step
        elif dist > 0:
            self.x, self.y = tx, ty
        self.clamp()
        if moved > 0.25 * self.scale:
            self.last_move = now
            self.gait += moved / (44.0 * self.scale)
        else:
            self.idle_t += dt

        self.last_cursor = pt

    # ---- menu / actions --------------------------------------------------
    def show_menu(self):
        menu = user32.CreatePopupMenu()
        if not menu:
            return
        user32.AppendMenuW(menu, MF_STRING, 1, "叫一声“爸爸”")
        user32.AppendMenuW(menu, MF_STRING, 2, "继续跟随" if self.paused else "暂停跟随")
        user32.AppendMenuW(menu, MF_STRING, 3, "回到鼠标旁边")
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, MF_STRING, 4, "退出桌宠")
        pt = wt.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        self.menu_open = True
        bubble_was = self.bubble_visible
        if self.bubble_shown:
            user32.ShowWindow(self.bubble_hwnd, SW_HIDE)
            self.bubble_shown = False
        # Hide the pet while the native popup menu is open.  The menu itself is a
        # topmost system window, so this also avoids the old "menu behind the pet"
        # and "pet lowered behind another topmost app" traps.
        user32.SetForegroundWindow(self.hwnd)
        user32.ShowWindow(self.hwnd, SW_HIDE)
        cmd = user32.TrackPopupMenu(
            menu, TPM_RETURNCMD | TPM_NONOTIFY | TPM_RIGHTBUTTON,
            pt.x, pt.y, 0, self.hwnd, None)
        user32.DestroyMenu(menu)
        user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        self.menu_open = False
        self.last_top = 0.0
        if cmd == 4:
            self.quit()
            return
        user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        user32.BringWindowToTop(self.hwnd)
        if bubble_was:
            self.update_bubble(time.perf_counter())
        if cmd == 1:
            self.say("爸爸")
        elif cmd == 2:
            self.paused = not self.paused
            self.flip_hold = 0.0
        elif cmd == 3:
            self.recenter()
            self.paused = False
        self.last_t = time.perf_counter()

    def quit(self):
        if self.destroying:
            return
        self.destroying = True
        self.running = False
        user32.UnregisterHotKey(self.hwnd, 10)
        user32.UnregisterHotKey(self.hwnd, 11)
        user32.DestroyWindow(self.bubble_hwnd)
        user32.DestroyWindow(self.hwnd)
        user32.PostQuitMessage(0)

    # ---- window procs ----------------------------------------------------
    def _pet_wndproc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_TIMER:
                self.tick()
                return 0
            if msg == WM_LBUTTONDOWN:
                self.say("爸爸")
                return 0
            if msg == WM_RBUTTONUP:
                self.show_menu()
                return 0
            if msg == WM_HOTKEY:
                if wparam == 10:
                    self.paused = not self.paused
                    self.last_t = time.perf_counter()
                elif wparam == 11:
                    self.quit()
                return 0
            if msg == WM_DPICHANGED:
                self.refresh_scale()
                return 0
            if msg == WM_DESTROY:
                if not self.destroying:
                    self.destroying = True
                    user32.PostQuitMessage(0)
                return 0
        except Exception:
            logging.exception("pet wndproc error")
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _bubble_wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_NCHITTEST:
            return HTTRANSPARENT
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def close(self):
        try:
            if self.pet_surface:
                self.pet_surface.close()
            if self.bubble_surface:
                self.bubble_surface.close()
            if self.screen_dc:
                user32.ReleaseDC(None, self.screen_dc)
        except Exception:
            pass


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(LOG_PATH),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )
    logging.info("starting pet")
    try:
        # per-monitor DPI aware (best effort)
        try:
            user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except Exception:
            try:
                user32.SetProcessDPIAware()
            except Exception:
                pass

        ctypes.set_last_error(0)
        mutex = kernel32.CreateMutexW(None, False, "BabaDesktopPet_SingleInstance_v1")
        mutex_err = ctypes.get_last_error()
        if mutex and mutex_err == ERROR_ALREADY_EXISTS:
            show_error("爸爸桌宠已经在运行啦～\n看看桌面右下角，或者按 Ctrl+Alt+Q 退出。")
            return

        pet = Pet()
        pet.create()
        msg = wt.MSG()
        while pet.running:
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                if msg.message == WM_QUIT:
                    pet.running = False
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            if not pet.running:
                break
            pet.tick()
            time.sleep(0.012)
        pet.close()
        logging.info("pet stopped")
    except Exception:
        logging.exception("fatal")
        show_error("爸爸桌宠启动失败了。\n\n详情见 pet.log。")
        raise


if __name__ == "__main__":
    main()


