"""
Live view: show the model the agent works on in the IDEA StatiCa Connection desktop application.

The agent runs this helper; the user does not need to. Windows only, Python 3.8 or later;
`start`, `show` and `stop` also need `pip install grpcio`.

    python live_view.py status
    python live_view.py remember ask|always|never [--layout side-by-side|window]
    python live_view.py start [--service http://localhost:5000] [--install DIR] [--layout side-by-side|window]
    python live_view.py show FILE.ideaCon [--replace-edited]
    python live_view.py arrange
    python live_view.py stop

`start` opens a Connection window that this helper can drive, from the same installation as the
running Connection REST API service. `show` opens a saved .ideaCon in that window. `show` never
starts a window: a window the user closed stays closed until `start` runs again.

Exit codes: 0 done, 1 error, 2 bad arguments, 3 no live view window (never started, or the user
closed it), 4 the window holds edits the user has not saved (nothing was replaced).

How it works: `IdeaConnection.exe -cmd:automation-<id> -grpcPort:<port> user-mode 0` makes the
application a gRPC server on localhost (contract: IdeaStatiCa.Plugin in
github.com/idea-statica/ideastatica-public). This helper calls its automation methods
(OpenProjectAsync, GetIsEdited, Shutdown) by reflection, the same channel that IDEA StatiCa
Checkbot uses. The application cannot patch an open model, so every update reopens the file.
"""

from __future__ import annotations

import argparse
import base64
import ctypes
import gzip
import json
import os
import random
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
from ctypes import wintypes
from datetime import datetime, timedelta
from pathlib import Path

EXIT_ERROR, EXIT_ARGS, EXIT_NO_WINDOW, EXIT_EDITED = 1, 2, 3, 4

SERVICE_EXE = "IdeaStatiCa.ConnectionRestApi.exe"
DESKTOP_EXE = "IdeaConnection.exe"
STATE_FILE = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "IDEA StatiCa agent skills" / "connection-live-view.json"
DEFAULT_PREFERENCE = {"mode": "ask", "layout": "side-by-side"}
SIDE_BY_SIDE_MIN_WIDTH = 1600  # px of the monitor work area; below it the ribbon of a 60 % window truncates
CONNECTION_SHARE = 0.6
OPEN_DONE_MARK = "runs in command mode"  # "Application <localised app name> runs in command mode"


class LiveViewError(RuntimeError):
    def __init__(self, message: str, code: int = EXIT_ERROR):
        super().__init__(message)
        self.code = code


# ---------- state: the remembered choice and the window this helper started ----------

def load_state() -> dict:
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    state["preference"] = {**DEFAULT_PREFERENCE, **(state.get("preference") or {})}
    return state


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, STATE_FILE)


# ---------- Win32 ----------

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_u32 = ctypes.WinDLL("user32", use_last_error=True)
_ver = ctypes.WinDLL("version", use_last_error=True)

_k32.CreateEventW.restype = wintypes.HANDLE
_k32.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
_k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_k32.CloseHandle.argtypes = [wintypes.HANDLE]
_k32.OpenProcess.restype = wintypes.HANDLE
_k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
_k32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                            ctypes.POINTER(wintypes.DWORD)]
_ver.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
_ver.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
_ver.VerQueryValueW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p),
                                ctypes.POINTER(wintypes.UINT)]


class _RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG), ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", _RECT), ("rcWork", _RECT), ("dwFlags", wintypes.DWORD)]


class _FIXEDFILEINFO(ctypes.Structure):
    _fields_ = [(name, wintypes.DWORD) for name in (
        "signature", "struc_version", "file_ms", "file_ls", "product_ms", "product_ls", "flags_mask",
        "flags", "os", "type", "subtype", "date_ms", "date_ls")]


_u32.GetForegroundWindow.restype = wintypes.HWND
_u32.GetWindow.restype = wintypes.HWND
_u32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
_u32.MonitorFromWindow.restype = wintypes.HANDLE
_u32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
_u32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_MONITORINFO)]
_u32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                              ctypes.c_int, wintypes.UINT]
_u32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
for _name in ("IsWindow", "IsWindowVisible", "IsZoomed", "IsIconic", "SetForegroundWindow", "BringWindowToTop",
              "GetWindowTextLengthW"):
    getattr(_u32, _name).argtypes = [wintypes.HWND]
_u32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
_u32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(_RECT)]
_u32.GetWindowThreadProcessId.restype = wintypes.DWORD
_u32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]

_ENUM_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def file_version(path: Path) -> str | None:
    """The numeric product version of an executable, e.g. '26.1.1.2809'."""
    size = _ver.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        return None
    buf = ctypes.create_string_buffer(size)
    if not _ver.GetFileVersionInfoW(str(path), 0, size, buf):
        return None
    ptr, length = ctypes.c_void_p(), wintypes.UINT()
    if not _ver.VerQueryValueW(buf, "\\", ctypes.byref(ptr), ctypes.byref(length)) or not ptr.value:
        return None
    info = _FIXEDFILEINFO.from_address(ptr.value)
    return f"{info.product_ms >> 16}.{info.product_ms & 0xFFFF}.{info.product_ls >> 16}.{info.product_ls & 0xFFFF}"


def process_image(pid: int | None) -> str | None:
    """The executable of a running process, or None when the process has ended."""
    if not pid:
        return None
    handle = _k32.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    try:
        code = wintypes.DWORD()
        _k32.GetExitCodeProcess(handle, ctypes.byref(code))
        if code.value != 259:  # STILL_ACTIVE
            return None
        buf, size = ctypes.create_unicode_buffer(1024), wintypes.DWORD(1024)
        return buf.value if _k32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)) else None
    finally:
        _k32.CloseHandle(handle)


def window_alive(window: dict | None) -> bool:
    """True while the Connection process this helper started still runs (a reused pid does not count)."""
    if not window:
        return False
    image = process_image(window.get("pid"))
    return bool(image) and Path(image).name.lower() == DESKTOP_EXE.lower()


def _window_pid(hwnd) -> int:
    owner = wintypes.DWORD()
    _u32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
    return owner.value


def main_window(pid: int):
    """The largest visible top-level window without an owner (its title stays empty until a project is open)."""
    best, best_area = None, 0

    def callback(hwnd, _):
        nonlocal best, best_area
        if _window_pid(hwnd) == pid and _u32.IsWindowVisible(hwnd) and not _u32.GetWindow(hwnd, 4):  # GW_OWNER
            r = _RECT()
            _u32.GetWindowRect(hwnd, ctypes.byref(r))
            area = (r.right - r.left) * (r.bottom - r.top)
            if area > best_area:
                best, best_area = hwnd, area
        return True

    _u32.EnumWindows(_ENUM_PROC(callback), 0)
    return best


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", wintypes.LONG), ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]


_k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
_k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
_k32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
_k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]


def _ancestors() -> list:
    """Process ids from this helper up its parent chain: the shell, the agent, and the application hosting it."""
    parents = {}
    snapshot = _k32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if snapshot in (None, wintypes.HANDLE(-1).value):
        return []
    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        ok = _k32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            parents[entry.th32ProcessID] = entry.th32ParentProcessID
            ok = _k32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        _k32.CloseHandle(snapshot)
    chain, pid = [], os.getpid()
    while pid and pid not in chain and len(chain) < 32:
        image = process_image(pid) or ""
        if Path(image).name.lower() == "explorer.exe":  # the Windows shell started the host; never move its windows
            break
        chain.append(pid)
        pid = parents.get(pid)
    return chain[1:]


def agent_window():
    """The window of the application the agent runs in (VS Code, a terminal, Claude Desktop), not whatever window
    the user has switched to meanwhile. None when no ancestor process owns a window."""
    ancestors = set(_ancestors())
    foreground = _u32.GetForegroundWindow()
    if foreground and _window_pid(foreground) in ancestors:
        return foreground
    found = None

    def callback(hwnd, _):  # top-level windows come in z-order, the topmost first
        nonlocal found
        if (_window_pid(hwnd) in ancestors and _u32.IsWindowVisible(hwnd) and not _u32.GetWindow(hwnd, 4)
                and _u32.GetWindowTextLengthW(hwnd)):
            found = hwnd
            return False
        return True

    _u32.EnumWindows(_ENUM_PROC(callback), 0)
    return found


def _dpi_aware() -> None:
    """Physical pixels everywhere, so window rectangles and monitor work areas agree."""
    try:
        _u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
    except (AttributeError, OSError):
        pass


def _work_area(hwnd) -> _RECT:
    info = _MONITORINFO()
    info.cbSize = ctypes.sizeof(_MONITORINFO)
    _u32.GetMonitorInfoW(_u32.MonitorFromWindow(hwnd, 2), ctypes.byref(info))  # MONITOR_DEFAULTTONEAREST
    return info.rcWork


def _place(hwnd, x: int, y: int, w: int, h: int) -> None:
    """Move the visible frame to (x, y, w, h); Windows 10 and 11 frames carry invisible resize borders."""
    if _u32.IsZoomed(hwnd) or _u32.IsIconic(hwnd):
        _u32.ShowWindow(hwnd, 9)  # SW_RESTORE
    outer, visible = _RECT(), _RECT()
    _u32.GetWindowRect(hwnd, ctypes.byref(outer))
    try:
        ctypes.windll.dwmapi.DwmGetWindowAttribute(wintypes.HWND(hwnd), 9,  # DWMWA_EXTENDED_FRAME_BOUNDS
                                                   ctypes.byref(visible), ctypes.sizeof(_RECT))
    except OSError:
        visible = outer
    ml, mt = visible.left - outer.left, visible.top - outer.top
    mr, mb = outer.right - visible.right, outer.bottom - visible.bottom
    _u32.SetWindowPos(hwnd, None, x - ml, y - mt, w + ml + mr, h + mt + mb, 0x0004 | 0x0010)  # NOZORDER|NOACTIVATE


def side_by_side(app_pid: int, user_window) -> str:
    """Connection on the right 60 % of the monitor the agent's window is on, the agent's window on the left 40 %."""
    _dpi_aware()
    app = None
    for _ in range(20):  # the main window can appear a moment after the ready signal
        app = main_window(app_pid)
        if app:
            break
        time.sleep(0.5)
    if not app:
        return "The Connection window was not found, so no window was moved."
    anchor = user_window if user_window and _u32.IsWindow(user_window) and _window_pid(user_window) != app_pid else app
    work = _work_area(anchor)
    width, height = work.right - work.left, work.bottom - work.top
    if width < SIDE_BY_SIDE_MIN_WIDTH:
        return (f"This monitor is {width} px wide; side by side needs at least {SIDE_BY_SIDE_MIN_WIDTH} px, "
                f"so no window was moved.")
    left_w = round(width * (1 - CONNECTION_SHARE))
    _place(app, work.left + left_w, work.top, width - left_w, height)
    if anchor != app:
        _place(anchor, work.left, work.top, left_w, height)
        return f"Side by side: your window on the left {left_w} px, Connection on the right {width - left_w} px."
    return (f"Connection placed on the right {width - left_w} px. The window the agent runs in was not found, "
            f"so no other window was moved.")


def _activate(hwnd) -> None:
    """SetForegroundWindow from a background process works only while attached to the foreground thread."""
    fg = _u32.GetForegroundWindow()
    fg_thread = _u32.GetWindowThreadProcessId(fg, None) if fg else 0
    me = _k32.GetCurrentThreadId()
    attached = bool(fg_thread and fg_thread != me and _u32.AttachThreadInput(me, fg_thread, True))
    try:
        _u32.BringWindowToTop(hwnd)
        _u32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            _u32.AttachThreadInput(me, fg_thread, False)


def give_focus_back(previous, app_pid: int, minimize=None, settle: float = 3.0) -> None:
    """The application raises (and restores) its window after every open. Wait for that, minimize the
    window again when the user had minimized it, and hand the keyboard back to the window the user typed in."""
    user_window = previous if previous and _u32.IsWindow(previous) and _window_pid(previous) != app_pid else None
    if not user_window and not minimize:
        return
    deadline = time.time() + settle
    while time.time() < deadline:
        foreground = _u32.GetForegroundWindow()
        if foreground and _window_pid(foreground) == app_pid:
            time.sleep(0.3)
            break
        time.sleep(0.1)
    if minimize:
        _u32.ShowWindow(minimize, 7)  # SW_SHOWMINNOACTIVE
    if user_window:
        _activate(user_window)


def _spawn_detached(args: list, cwd: str) -> subprocess.Popen:
    """Start a process that outlives this script and the shell that ran it."""
    flags = 0x00000200 | 0x00000008  # CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS
    common = dict(cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                  close_fds=True)
    try:
        return subprocess.Popen(args, creationflags=flags | 0x01000000, **common)  # CREATE_BREAKAWAY_FROM_JOB
    except OSError:
        return subprocess.Popen(args, creationflags=flags, **common)


def _free_port(low: int = 50000, high: int = 50500) -> int:
    ports = list(range(low, high))
    random.shuffle(ports)
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise LiveViewError(f"no free local port in {low}-{high}")


# ---------- installation of the running service ----------

def service_version(url: str) -> str | None:
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/api/5/clients/idea-service-version", timeout=5) as r:
            text = r.read().decode("utf-8", "replace").strip().strip('"')
    except (OSError, ValueError):
        return None
    match = re.match(r"\d+(\.\d+){3}", text)
    return match.group(0) if match else None


def find_install(service_url: str | None, explicit: str | None) -> tuple:
    """(install folder, note). The desktop must come from the installation the service runs from:
    an older desktop refuses a file that a newer service wrote."""
    if explicit:
        folder = Path(explicit)
        if not (folder / DESKTOP_EXE).exists():
            raise LiveViewError(f"{folder} does not contain {DESKTOP_EXE}")
        return folder, None
    root = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "IDEA StatiCa"
    installs = [d for d in root.glob("StatiCa *") if (d / DESKTOP_EXE).exists() and (d / SERVICE_EXE).exists()]
    if not installs:
        raise LiveViewError(f"No IDEA StatiCa installation with {DESKTOP_EXE} under {root}; pass --install DIR")
    wanted = service_version(service_url) if service_url else None
    if wanted:
        for folder in installs:
            if file_version(folder / SERVICE_EXE) == wanted:
                return folder, None
        raise LiveViewError(f"The service at {service_url} is version {wanted}, and no installation under {root} "
                            f"has that version. Pass --install with the folder the service runs from.")
    newest = max(installs, key=lambda d: tuple(int(x) for x in re.findall(r"\d+", d.name)))
    note = (f"No service answered at {service_url}; using the newest installation, {newest.name}." if service_url
            else f"No --service given; using the newest installation, {newest.name}.")
    return newest, note


# ---------- gRPC: one reflection call to the application's automation service ----------

def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _encode(m: dict) -> bytes:
    """GrpcMessage (IdeaStatiCa.Plugin GrpcReflectionServiceContract.proto): string fields 1-5, messageType 6."""
    out = bytearray()
    for number, key in ((1, "messageName"), (2, "data"), (3, "clientId"), (4, "operationId"), (5, "dataType")):
        value = m.get(key)
        if value:
            raw = value.encode("utf-8")
            out += _varint((number << 3) | 2) + _varint(len(raw)) + raw
    return bytes(out)


def _decode(b: bytes) -> dict:
    names = {1: "messageName", 2: "data", 3: "clientId", 4: "operationId", 5: "dataType",
             6: "messageType", 7: "buffer", 8: "compression"}
    m, i = {}, 0

    def read_varint() -> int:
        nonlocal i
        shift = result = 0
        while True:
            byte = b[i]
            i += 1
            result |= (byte & 0x7F) << shift
            if not byte & 0x80:
                return result
            shift += 7

    while i < len(b):
        tag = read_varint()
        number, wire = tag >> 3, tag & 7
        key = names.get(number, str(number))
        if wire == 0:
            m[key] = read_varint()
        elif wire == 2:
            n = read_varint()
            raw, i = b[i:i + n], i + n
            m[key] = raw if key == "buffer" else raw.decode("utf-8", "replace")
        else:
            raise LiveViewError(f"unexpected protobuf wire type {wire} in the application's reply")
    if m.get("compression") and m.get("data"):
        m["data"] = gzip.decompress(base64.b64decode(m["data"])).decode("utf-8")
    return m


def invoke(port: int, method: str, *args, timeout: float = 60.0):
    """Call a public method of the application's automation service and return its decoded result."""
    try:
        import grpc
    except ImportError:
        raise LiveViewError("the live view needs the grpcio package: pip install grpcio") from None

    def argument(value) -> dict:
        kind = "System.UInt32" if isinstance(value, int) and not isinstance(value, bool) else "System.String"
        return {"ParameterType": kind, "Value": json.dumps(value)}

    operation_id = str(uuid.uuid4())
    request = _encode({"messageName": "Grpc.Handlers.Reflection",
                       "data": json.dumps({"MethodName": method, "Parameters": [argument(a) for a in args]}),
                       "clientId": str(os.getpid()), "operationId": operation_id,
                       "dataType": "GrpcReflectionInvokeData"})
    done = threading.Event()

    def requests():
        yield request
        done.wait(timeout)  # keep the stream open until the reply arrives

    channel = grpc.insecure_channel(f"localhost:{port}")
    try:
        responses = channel.stream_stream("/GrpcService/ConnectAsync", request_serializer=lambda x: x,
                                          response_deserializer=lambda x: x)(requests(), timeout=timeout)
        try:
            for raw in responses:
                reply = _decode(raw)
                if reply.get("operationId") != operation_id:
                    continue
                if reply.get("dataType") == "Exception":
                    try:
                        message = json.loads(reply.get("data") or "{}").get("Message")
                    except ValueError:
                        message = reply.get("data")
                    raise LiveViewError(f"{method} failed in the Connection application: {message}")
                data = reply.get("data")
                return json.loads(data) if data else None
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                raise LiveViewError(f"{method}: the Connection application did not answer within {timeout:.0f} s") from None
            raise LiveViewError(f"{method}: the Connection window does not answer ({e.code().name})",
                                EXIT_NO_WINDOW) from None
        finally:
            done.set()
            responses.cancel()
        raise LiveViewError(f"{method}: the Connection application closed the connection without a reply")
    finally:
        channel.close()


# ---------- completion of an open: the application logs it ----------

def _log_files() -> list:
    roots = [os.environ.get("TEMP"), os.environ.get("TMP")]
    if os.environ.get("LOCALAPPDATA"):
        roots.append(str(Path(os.environ["LOCALAPPDATA"]) / "Temp"))
    folders = set()
    for root in filter(None, roots):
        try:
            folders.add((Path(root) / "IdeaStatica" / "Logs").resolve())  # one entry per folder, 8.3 names expanded
        except OSError:
            pass
    files = []
    for folder in folders:
        try:
            files += list(folder.glob("IdeaConnection*.log"))
        except OSError:
            pass
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:3]


def _open_finished(pid: int, since: datetime) -> bool:
    for log in _log_files():
        try:
            lines = log.read_text(encoding="utf-8", errors="replace").splitlines()[-3000:]
        except OSError:
            continue
        for line in reversed(lines):
            if f"({pid}-" not in line or OPEN_DONE_MARK not in line:
                continue
            try:  # "2026-10-16 11:04:44.769 +02:00 (38984-12) ..."
                stamp = datetime.fromisoformat(line[:23] + line[24:30])
            except ValueError:
                continue
            if stamp >= since:
                return True
    return False


# ---------- commands ----------

def window_status(state: dict) -> str:
    window = state.get("window")
    if not window:
        return "not-started"
    return "open" if window_alive(window) else "closed"


def cmd_status(_a) -> int:
    state = load_state()
    window = state.get("window") or {}
    status = window_status(state)
    print(json.dumps({
        "preference": state["preference"],
        "window": status,
        "version": window.get("version") if status == "open" else None,
        "showing": window.get("last_shown") if status == "open" else None,
        "settings_file": str(STATE_FILE),
    }, indent=2, ensure_ascii=False))
    return 0


def cmd_remember(a) -> int:
    state = load_state()
    state["preference"] = {"mode": a.mode, "layout": a.layout or state["preference"]["layout"]}
    save_state(state)
    p = state["preference"]
    meaning = {"ask": "ask before the first model change of each conversation",
               "always": f"open the live view without asking ({p['layout']})",
               "never": "never offer the live view; it still opens when you ask for it"}[p["mode"]]
    print(f"Remembered: {meaning}. Stored in {STATE_FILE}.")
    return 0


def cmd_start(a) -> int:
    state = load_state()
    layout = a.layout or state["preference"]["layout"]
    window = state.get("window")
    if window_alive(window):
        print(f"The live view window is already open (IDEA StatiCa Connection {window.get('version')}).")
        return 0
    install, note = find_install(a.service, a.install)
    if note:
        print(note)
    exe = install / DESKTOP_EXE
    previous, host = _u32.GetForegroundWindow(), agent_window()
    automation_id, port = os.getpid(), _free_port()
    ready = _k32.CreateEventW(None, False, False, f"IdeaStatiCaEvent{automation_id}")
    closed = _k32.CreateEventW(None, True, False, f"IdeaStatiCaServerClosed{port}")
    began = time.time()
    try:
        proc = _spawn_detached([str(exe), f"-cmd:automation-{automation_id}", f"-grpcPort:{port}", "user-mode", "0"],
                               cwd=str(install))
        deadline = began + a.timeout
        while _k32.WaitForSingleObject(ready, 500) != 0:
            if proc.poll() is not None:
                raise LiveViewError(f"{DESKTOP_EXE} exited during start-up (exit code {proc.returncode})")
            if time.time() > deadline:
                raise LiveViewError(f"{DESKTOP_EXE} did not report ready within {a.timeout:.0f} s; a license or "
                                    f"first-run dialog may be waiting in its window")
    finally:
        _k32.CloseHandle(ready)
        _k32.CloseHandle(closed)
    version = file_version(exe)
    state["window"] = {"pid": proc.pid, "port": port, "exe": str(exe), "version": version, "last_shown": None}
    save_state(state)
    print(f"The live view window is open: IDEA StatiCa Connection {version}, ready in {time.time() - began:.0f} s.")
    if layout == "side-by-side":
        print(side_by_side(proc.pid, host))
    give_focus_back(previous, proc.pid)
    return 0


def cmd_show(a) -> int:
    file = Path(a.file).resolve()
    if not file.exists():
        raise LiveViewError(f"{file} does not exist", EXIT_ARGS)
    state = load_state()
    window = state.get("window")
    status = window_status(state)
    if status == "not-started":
        raise LiveViewError("No live view window is open, and show never opens one. Run `start` only when "
                            "the user wants the live view.", EXIT_NO_WINDOW)
    if status == "closed":
        raise LiveViewError("The user closed the Connection window. Do not reopen it; run `start` again only "
                            "when the user asks for the live view.", EXIT_NO_WINDOW)
    port, pid = window["port"], window["pid"]
    if not a.replace_edited and invoke(port, "GetIsEdited", timeout=30):
        raise LiveViewError(f"The Connection window holds edits the user has not saved ({window.get('last_shown')}). "
                            f"Nothing was replaced. Ask the user whether to save them in the window first or to "
                            f"replace them (show --replace-edited; the window then asks whether to save).", EXIT_EDITED)
    previous = _u32.GetForegroundWindow()
    app = main_window(pid)  # a minimized window still counts as visible
    minimized = app if app and _u32.IsIconic(app) else None  # the user put it away: update it, keep it there
    since = datetime.now().astimezone().replace(microsecond=0) - timedelta(seconds=1)
    began = time.time()
    invoke(port, "OpenProjectAsync", str(file), 0, timeout=a.timeout)  # 0 = the full user interface
    window["last_shown"] = str(file)
    save_state(state)
    while time.time() - began < a.timeout:  # OpenProjectAsync returns before the open finishes
        if _open_finished(pid, since):
            give_focus_back(previous, pid, minimize=minimized)
            kept = ", kept minimized as the user left it" if minimized else ""
            print(f"Shown in the Connection window: {file.name} ({time.time() - began:.0f} s{kept}).")
            return 0
        if not window_alive(window):
            raise LiveViewError("The Connection window closed while opening the file.", EXIT_NO_WINDOW)
        time.sleep(0.5)
    print(f"Sent {file.name} to the Connection window, but it did not confirm the open within {a.timeout:.0f} s. "
          f"A dialog may be waiting there, for example whether to save edits.")
    return 0


def cmd_arrange(_a) -> int:
    """Put the open window side by side with the user's window again, when the user asks."""
    state = load_state()
    window = state.get("window")
    if not window_alive(window):
        raise LiveViewError("No live view window is open.", EXIT_NO_WINDOW)
    previous = _u32.GetForegroundWindow()
    print(side_by_side(window["pid"], agent_window()))
    give_focus_back(previous, window["pid"])
    return 0


def cmd_stop(_a) -> int:
    state = load_state()
    window = state.get("window")
    if window_alive(window):
        try:
            invoke(window["port"], "Shutdown", timeout=30)
        except LiveViewError:
            pass
        print("The Connection window was asked to close; it asks the user about unsaved edits.")
    else:
        print("No live view window is open.")
    state["window"] = None
    save_state(state)
    return 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    if os.name != "nt":
        print("The live view needs Windows with IDEA StatiCa installed.", file=sys.stderr)
        return EXIT_ERROR
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(func=cmd_status)
    remember = sub.add_parser("remember")
    remember.add_argument("mode", choices=["ask", "always", "never"])
    remember.add_argument("--layout", choices=["side-by-side", "window"])
    remember.set_defaults(func=cmd_remember)
    start = sub.add_parser("start")
    start.add_argument("--service", default="http://localhost:5000",
                       help="the running Connection REST API service; its installation is used")
    start.add_argument("--install", help="installation folder with IdeaConnection.exe, instead of --service")
    start.add_argument("--layout", choices=["side-by-side", "window"],
                       help="default: the remembered layout, side-by-side at first")
    start.add_argument("--timeout", type=float, default=240.0)
    start.set_defaults(func=cmd_start)
    show = sub.add_parser("show")
    show.add_argument("file")
    show.add_argument("--replace-edited", action="store_true",
                      help="open even when the window holds unsaved edits; the window asks whether to save them")
    show.add_argument("--timeout", type=float, default=120.0)
    show.set_defaults(func=cmd_show)
    sub.add_parser("arrange").set_defaults(func=cmd_arrange)
    sub.add_parser("stop").set_defaults(func=cmd_stop)
    a = parser.parse_args()
    try:
        return a.func(a)
    except LiveViewError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return e.code


if __name__ == "__main__":
    sys.exit(main())
