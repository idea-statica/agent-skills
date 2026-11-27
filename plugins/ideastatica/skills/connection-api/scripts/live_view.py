"""
Live view: show the model the agent works on in the IDEA StatiCa Connection desktop application.

The agent runs this helper; the user does not need to. Windows only, Python 3.8 or later, and
`pip install grpcio` for start, show, arrange and stop.

    python live_view.py status
    python live_view.py remember ask|always|never [--layout side-by-side|window]
    python live_view.py start [--auto] [--service URL] [--install DIR] [--layout side-by-side|window]
    python live_view.py show FILE.ideaCon [--replace-edited]
    python live_view.py check [--adopt]
    python live_view.py arrange
    python live_view.py stop

`start` opens a Connection window that this helper can drive, from the installation of the
running Connection REST API service. With --auto (the remembered "always" choice) it refuses to
reopen a window the user closed while the same agent session runs. `show` copies a saved .ideaCon
to a preview copy and opens that copy in the window, so saving in the window never writes to the
agent's file. `show` never starts a window. `check` tells, before the next change, whether the
user edited the model in the window; `check --adopt` saves those edits into the preview copy and
names the file to open in the service.

Exit codes: 0 done; 1 error; 2 bad arguments; 3 the user closed the window; 4 the user edited the
model in the window (unsaved, or saved into the preview copy) and nothing was replaced; 5 the live
view is not on (never started, stopped, or still starting); 6 the file was sent but the window did
not confirm the open.

How it works: `IdeaConnection.exe -cmd:automation-<id> -grpcPort:<port> user-mode 0` makes the
application a gRPC server on localhost (contract: IdeaStatiCa.Plugin in
github.com/idea-statica/ideastatica-public). The helper calls its automation methods
(OpenProjectAsync, GetIsEdited, SaveCurrentItemAsync, Shutdown) by reflection, the channel IDEA StatiCa Checkbot uses.
The application cannot patch an open model, so every update reopens the file.
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
import shutil
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

EXIT_ERROR, EXIT_ARGS, EXIT_CLOSED, EXIT_EDITED, EXIT_OFF, EXIT_UNCONFIRMED = 1, 2, 3, 4, 5, 6

SERVICE_EXE = "IdeaStatiCa.ConnectionRestApi.exe"
DESKTOP_EXE = "IdeaConnection.exe"
HOME = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "IDEA StatiCa agent skills"
STATE_FILE = HOME / "connection-live-view.json"
PREVIEW_DIR = HOME / "live-view"
DEFAULT_PREFERENCE = {"mode": "ask", "layout": "side-by-side"}
SIDE_BY_SIDE_MIN_WIDTH = 1600  # logical px of the monitor work area; below it the ribbon of a 60 % window truncates
CONNECTION_SHARE = 0.6
OPEN_DONE_MARK = "runs in command mode"  # "Application <localised app name> runs in command mode"
SHELLS = {"python.exe", "pythonw.exe", "py.exe", "bash.exe", "sh.exe", "cmd.exe", "powershell.exe", "pwsh.exe",
          "conhost.exe", "openconsole.exe"}


class LiveViewError(RuntimeError):
    def __init__(self, message: str, code: int = EXIT_ERROR):
        super().__init__(message)
        self.code = code


def require_grpc():
    try:
        import grpc
        return grpc
    except ImportError:
        raise LiveViewError("The live view needs the Python package grpcio: pip install grpcio") from None


def grpc_available() -> bool:
    try:
        import grpc  # noqa: F401
        return True
    except ImportError:
        return False


# ---------- state: the remembered choice and the window this helper started ----------

def load_state() -> dict:
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    if not isinstance(state, dict):
        state = {}
    preference = state.get("preference") if isinstance(state.get("preference"), dict) else {}
    state["preference"] = {**DEFAULT_PREFERENCE, **preference}
    if not isinstance(state.get("window"), dict):
        state["window"] = None
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


class _RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG), ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", _RECT), ("rcWork", _RECT), ("dwFlags", wintypes.DWORD)]


class _FIXEDFILEINFO(ctypes.Structure):
    _fields_ = [(name, wintypes.DWORD) for name in (
        "signature", "struc_version", "file_ms", "file_ls", "product_ms", "product_ls", "flags_mask",
        "flags", "os", "type", "subtype", "date_ms", "date_ls")]


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", wintypes.LONG), ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]


_k32.CreateEventW.restype = wintypes.HANDLE
_k32.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
_k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_k32.CloseHandle.argtypes = [wintypes.HANDLE]
_k32.OpenProcess.restype = wintypes.HANDLE
_k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
_k32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
_k32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                            ctypes.POINTER(wintypes.DWORD)]
_k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
_k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
_k32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
_k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
_ver.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
_ver.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
_ver.VerQueryValueW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p),
                                ctypes.POINTER(wintypes.UINT)]
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


def process_info(pid: int | None) -> tuple:
    """(executable, creation time) of a running process, or (None, None) when it has ended."""
    if not pid:
        return None, None
    handle = _k32.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None, None
    try:
        code = wintypes.DWORD()
        _k32.GetExitCodeProcess(handle, ctypes.byref(code))
        if code.value != 259:  # STILL_ACTIVE
            return None, None
        buf, size = ctypes.create_unicode_buffer(1024), wintypes.DWORD(1024)
        image = buf.value if _k32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)) else None
        times = [wintypes.FILETIME() for _ in range(4)]
        created = None
        if _k32.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
            created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        return image, created
    finally:
        _k32.CloseHandle(handle)


def window_alive(window: dict | None) -> bool:
    """True while the Connection process this helper started still runs (a reused pid does not count)."""
    if not window:
        return False
    image, created = process_info(window.get("pid"))
    if not image or Path(image).name.lower() != DESKTOP_EXE.lower():
        return False
    return window.get("created") in (None, created)


def _ancestors() -> list:
    """(pid, exe name) from this helper's parent up to the application hosting the agent. Stops at
    explorer.exe: the Windows shell started the host, and its windows are never moved."""
    parents = {}
    snapshot = _k32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if not snapshot or snapshot == wintypes.HANDLE(-1).value:
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
    chain, seen, pid = [], {os.getpid()}, parents.get(os.getpid())
    while pid and pid not in seen and len(chain) < 32:
        seen.add(pid)
        image, _ = process_info(pid)
        name = Path(image).name.lower() if image else ""
        if name == "explorer.exe":
            break
        chain.append((pid, name))
        pid = parents.get(pid)
    return chain


def agent_pid() -> int | None:
    """The agent process (Claude Code, for example): the first ancestor that is not a shell or Python.
    It lives as long as the agent session, across /clear and context compaction."""
    for pid, name in _ancestors():
        if name and name not in SHELLS:
            return pid
    return None


def _window_pid(hwnd) -> int:
    owner = wintypes.DWORD()
    _u32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
    return owner.value


def agent_window():
    """The window of the application the agent runs in (VS Code, a terminal, Claude Desktop), never a window of
    another application the user switched to meanwhile. None when no ancestor owns a window."""
    ancestors = {pid for pid, _ in _ancestors()}
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


def main_window(pid: int):
    """The largest visible top-level window without an owner (its title stays empty until a project is open).
    A minimized window counts as visible."""
    best, best_area = None, 0

    def callback(hwnd, _):
        nonlocal best, best_area
        if _window_pid(hwnd) == pid and _u32.IsWindowVisible(hwnd) and not _u32.GetWindow(hwnd, 4):  # GW_OWNER
            r = _RECT()
            _u32.GetWindowRect(hwnd, ctypes.byref(r))
            area = max(1, (r.right - r.left) * (r.bottom - r.top))
            if area > best_area:
                best, best_area = hwnd, area
        return True

    _u32.EnumWindows(_ENUM_PROC(callback), 0)
    return best


def _dpi_aware() -> None:
    """Physical pixels everywhere, so window rectangles and monitor work areas agree."""
    try:
        _u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
    except (AttributeError, OSError):
        pass


def _dpi(hwnd) -> int:
    try:
        return _u32.GetDpiForWindow(wintypes.HWND(hwnd)) or 96
    except (AttributeError, OSError):
        return 96


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
        hr = ctypes.windll.dwmapi.DwmGetWindowAttribute(wintypes.HWND(hwnd), 9,  # DWMWA_EXTENDED_FRAME_BOUNDS
                                                        ctypes.byref(visible), ctypes.sizeof(_RECT))
    except OSError:
        hr = -1
    if hr != 0 or visible.right <= visible.left:
        visible = outer
    ml, mt = visible.left - outer.left, visible.top - outer.top
    mr, mb = outer.right - visible.right, outer.bottom - visible.bottom
    _u32.SetWindowPos(hwnd, None, x - ml, y - mt, w + ml + mr, h + mt + mb, 0x0004 | 0x0010)  # NOZORDER|NOACTIVATE


def side_by_side(app_pid: int) -> str:
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
    host = agent_window()
    anchor = host if host and _window_pid(host) != app_pid else app
    work = _work_area(anchor)
    width, height = work.right - work.left, work.bottom - work.top
    logical = round(width * 96 / _dpi(anchor))
    if logical < SIDE_BY_SIDE_MIN_WIDTH:
        return (f"This monitor is {logical} px wide at its display scaling; side by side needs at least "
                f"{SIDE_BY_SIDE_MIN_WIDTH} px, so no window was moved.")
    left_w = round(width * (1 - CONNECTION_SHARE))
    _place(app, work.left + left_w, work.top, width - left_w, height)
    if anchor != app:
        _place(anchor, work.left, work.top, left_w, height)
        return "Side by side: the agent's window on the left 40 % of the screen, Connection on the right 60 %."
    return ("Connection placed on the right 60 % of the screen. The window the agent runs in was not found, "
            "so no other window was moved.")


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


def settle_focus(previous, app_pid: int, minimize=None, settle: float = 3.0) -> None:
    """The application raises (and restores) its window after every open. Minimize it again when the user had
    minimized it, and give the keyboard back to the window the user was in, but only if Connection took it:
    a user who moved on to another window meanwhile keeps that window."""
    took_focus = False
    deadline = time.time() + settle
    while time.time() < deadline:
        foreground = _u32.GetForegroundWindow()
        if foreground and _window_pid(foreground) == app_pid:
            took_focus = True
            time.sleep(0.3)
            break
        time.sleep(0.1)
    if minimize:
        _u32.ShowWindow(minimize, 7)  # SW_SHOWMINNOACTIVE
    if took_focus and previous and _u32.IsWindow(previous) and _window_pid(previous) != app_pid:
        _activate(previous)


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


def find_install(service_url: str, explicit: str | None) -> tuple:
    """(installation folder, note for the user). The desktop must come from the installation the service runs
    from: an older desktop refuses a file that a newer service wrote."""
    if explicit:
        folder = Path(explicit)
        if not (folder / DESKTOP_EXE).exists():
            raise LiveViewError(f"{folder} does not contain {DESKTOP_EXE}", EXIT_ARGS)
        return folder, None
    root = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "IDEA StatiCa"
    installs = [d for d in root.glob("StatiCa *") if (d / DESKTOP_EXE).exists() and (d / SERVICE_EXE).exists()]
    if not installs:
        raise LiveViewError(f"No IDEA StatiCa installation with {DESKTOP_EXE} under {root}; pass --install DIR")
    wanted = service_version(service_url)
    if wanted:
        for folder in installs:
            if file_version(folder / SERVICE_EXE) == wanted:
                return folder, None
        raise LiveViewError(f"The service at {service_url} is version {wanted}, and no installation under {root} "
                            f"has that version. Pass --install with the folder the service runs from.")
    newest = max(installs, key=lambda d: tuple(int(x) for x in re.findall(r"\d+", d.name)))
    return newest, (f"No service answered at {service_url}, so the newest installation, {newest.name}, is used. "
                    f"Tell the user: if the service runs elsewhere, the window may not open its files.")


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
    """GrpcMessage (IdeaStatiCa.Plugin GrpcReflectionServiceContract.proto): string fields 1-5."""
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
    grpc = require_grpc()

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
            raise LiveViewError(f"{method}: the Connection window does not answer ({e.code().name})") from None
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


def _tail(path: Path, size: int = 512 * 1024) -> list:
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        f.seek(max(0, f.tell() - size))
        return f.read().decode("utf-8", "replace").splitlines()


def _open_finished(pid: int, since: datetime) -> bool:
    for log in _log_files():
        try:
            lines = _tail(log)
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

def window_status(window: dict | None) -> str:
    if not window:
        return "not-started"
    if not window_alive(window):
        return "closed"
    return "open" if window.get("ready") else "starting"


def cmd_status(_a) -> int:
    state = load_state()
    window = state["window"] or {}
    status = window_status(state["window"])
    print(json.dumps({
        "preference": state["preference"],
        "window": status,
        "version": window.get("version") if status in ("open", "starting") else None,
        "showing": (window.get("shown") or {}).get("source") if status == "open" else None,
        "grpcio": grpc_available(),
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
               "never": "never offer the live view; it still opens when the user asks for it"}[p["mode"]]
    print(f"Remembered: {meaning}. Stored in {STATE_FILE}.")
    return 0


def _user_foreground(previous, app_pid: int):
    """The window the user is in now, unless it is the Connection window: focus goes back there later."""
    foreground = _u32.GetForegroundWindow()
    return foreground if foreground and _window_pid(foreground) != app_pid else previous


def _wait_until_answers(window: dict, deadline: float, track=lambda: None) -> bool:
    """A window started by an earlier, interrupted `start`: ready once its gRPC server answers."""
    while time.time() < deadline:
        track()
        if not window_alive(window):
            raise LiveViewError("The Connection window closed during start-up.", EXIT_CLOSED)
        try:
            invoke(window["port"], "GetIsEdited", timeout=5)
            return True
        except LiveViewError:
            time.sleep(2)
    return False


def cmd_start(a) -> int:
    require_grpc()
    state = load_state()
    layout = a.layout or state["preference"]["layout"]
    window = state["window"]
    status = window_status(window)
    me = agent_pid()
    if a.auto and status == "closed" and window.get("agent_pid") and window.get("agent_pid") == me:
        raise LiveViewError("The user closed the Connection window in this session. Do not reopen it; start it "
                            "again only when the user asks (without --auto).", EXIT_CLOSED)
    began = time.time()
    if status == "open":
        print(f"The live view window is already open (IDEA StatiCa Connection {window.get('version')}).")
        return 0
    if status == "starting":
        print("A Connection window is still starting from an earlier start; waiting for it.")
        fresh = False
    else:
        install, note = find_install(a.service, a.install)
        if note:
            print(note)
        exe = install / DESKTOP_EXE
        automation_id, port = os.getpid(), _free_port()
        ready = _k32.CreateEventW(None, False, False, f"IdeaStatiCaEvent{automation_id}")
        closed = _k32.CreateEventW(None, True, False, f"IdeaStatiCaServerClosed{port}")
        proc = _spawn_detached([str(exe), f"-cmd:automation-{automation_id}", f"-grpcPort:{port}", "user-mode", "0"],
                               cwd=str(install))
        _, created = process_info(proc.pid)
        window = {"pid": proc.pid, "created": created, "port": port, "exe": str(exe), "version": file_version(exe),
                  "agent_pid": me, "ready": False, "shown": None}
        state["window"] = window
        save_state(state)  # recorded at once, so an interrupted start leaves no unknown window behind
        fresh = True
    previous = _u32.GetForegroundWindow()
    deadline = began + a.timeout
    try:
        if fresh:
            while _k32.WaitForSingleObject(ready, 500) != 0:
                previous = _user_foreground(previous, window["pid"])
                if proc.poll() is not None:
                    state["window"] = None
                    save_state(state)
                    raise LiveViewError(f"{DESKTOP_EXE} exited during start-up (exit code {proc.returncode})")
                if time.time() > deadline:
                    raise LiveViewError(f"The Connection window is still starting after {a.timeout:.0f} s; a license "
                                        f"or first-run dialog may be waiting in it. Run start again to keep waiting.")
        elif not _wait_until_answers(window, deadline, lambda: _user_foreground(previous, window["pid"])):
            raise LiveViewError(f"The Connection window is still starting after {a.timeout:.0f} s. Run start again "
                                f"to keep waiting.")
    finally:
        if fresh:
            _k32.CloseHandle(ready)
            _k32.CloseHandle(closed)
    previous = _user_foreground(previous, window["pid"])
    window["ready"] = True
    save_state(state)
    print(f"The live view window is open: IDEA StatiCa Connection {window.get('version')}, "
          f"ready in {time.time() - began:.0f} s. It shows a file after the first `show`.")
    if layout == "side-by-side":
        print(side_by_side(window["pid"]))
    settle_focus(previous, window["pid"])
    return 0


def _preview_changed(shown: dict | None) -> bool:
    """True when the preview copy was saved from the window after the last `show`."""
    if not shown:
        return False
    try:
        st = Path(shown["preview"]).stat()
    except (OSError, KeyError, TypeError):
        return False
    return (st.st_mtime_ns, st.st_size) != (shown.get("mtime_ns"), shown.get("size"))


def _record_shown(state: dict, source: Path, preview: Path) -> None:
    """Remember the preview copy as the window opened it, to notice a later save from the window."""
    st = preview.stat()
    state["window"]["shown"] = {"source": str(source), "preview": str(preview), "mtime_ns": st.st_mtime_ns,
                                "size": st.st_size}
    save_state(state)


def cmd_show(a) -> int:
    source = Path(a.file).resolve()
    if not source.exists():
        raise LiveViewError(f"{source} does not exist", EXIT_ARGS)
    require_grpc()
    state = load_state()
    window = state["window"]
    status = window_status(window)
    if status == "not-started":
        raise LiveViewError("The live view is not on. Do not mention it; start it only when the user wants it.",
                            EXIT_OFF)
    if status == "starting":
        raise LiveViewError("The Connection window is still starting; run start to wait for it.", EXIT_OFF)
    pid, port = window["pid"], window["port"]
    app = main_window(pid)
    if status == "closed" or not app:
        raise LiveViewError("The user closed the Connection window. Do not reopen it; start it again only when the "
                            "user asks for the live view.", EXIT_CLOSED)
    shown = window.get("shown")
    if not a.replace_edited:
        if invoke(port, "GetIsEdited", timeout=30):
            raise LiveViewError("The Connection window holds edits the user has not saved. Nothing was replaced. "
                                "Ask the user: save them in the window (they go to the preview copy) and continue "
                                "from them, or let the update replace them (show --replace-edited).", EXIT_EDITED)
        if _preview_changed(shown):
            raise LiveViewError(f"The user saved edits in the Connection window to the preview copy {shown['preview']}. "
                                f"Nothing was replaced. Ask the user: continue from their edits (open that copy in "
                                f"the service before the next change), or replace them (show --replace-edited).",
                                EXIT_EDITED)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    preview = PREVIEW_DIR / source.name
    if preview.resolve() != source:
        shutil.copyfile(source, preview)
    minimized = app if _u32.IsIconic(app) else None  # the user put it away: update it, keep it there
    previous = _u32.GetForegroundWindow()
    since = datetime.now().astimezone().replace(microsecond=0) - timedelta(seconds=1)
    began = time.time()
    invoke(port, "OpenProjectAsync", str(preview), 0, timeout=a.timeout)  # 0 = the full user interface
    wait = a.timeout if window.get("confirms", True) else min(a.timeout, 20.0)
    while time.time() - began < wait:  # OpenProjectAsync returns before the open finishes
        if _open_finished(pid, since):
            window["confirms"] = True
            _record_shown(state, source, preview)
            settle_focus(previous, pid, minimize=minimized)
            kept = ", kept minimized as the user left it" if minimized else ""
            print(f"Shown in the Connection window: {source.name} ({time.time() - began:.0f} s{kept}).")
            return 0
        if not window_alive(window):
            raise LiveViewError("The Connection window closed while opening the file.", EXIT_CLOSED)
        time.sleep(0.5)
    window["confirms"] = False  # no log line seen; wait less next time
    _record_shown(state, source, preview)
    settle_focus(previous, pid, minimize=minimized, settle=0.5)
    raise LiveViewError(f"Sent {source.name} to the Connection window, but it did not confirm the open within "
                        f"{wait:.0f} s. A dialog may be waiting there; usually the file opened anyway.",
                        EXIT_UNCONFIRMED)


def cmd_check(a) -> int:
    """Before the next change: did the user edit the model in the window? With --adopt, take the edits over."""
    state = load_state()
    window = state["window"]
    status = window_status(window)
    if status in ("not-started", "starting"):
        raise LiveViewError("The live view is not on.", EXIT_OFF)
    shown = window.get("shown")
    unsaved = False
    if status == "open" and main_window(window["pid"]):
        require_grpc()
        unsaved = bool(invoke(window["port"], "GetIsEdited", timeout=30))
    saved = _preview_changed(shown)
    if not unsaved and not saved:
        if status != "open":
            raise LiveViewError("The user closed the Connection window, without saving edits in it.", EXIT_CLOSED)
        print("No edits in the Connection window since the last update.")
        return 0
    if not shown:
        raise LiveViewError("The window holds edits, but it shows no file from this helper, so there is nothing to "
                            "take over. Ask the user to save their work in the window under a name of their own.")
    what = "edits they have not saved yet" if unsaved else "edits they saved there"
    if not a.adopt:
        raise LiveViewError(f"The user changed the model in the Connection window ({what}). Ask whether to continue "
                            f"from these edits or to replace them with your next update. To continue: check --adopt.",
                            EXIT_EDITED)
    preview = Path(shown["preview"])
    if unsaved:
        before = preview.stat().st_mtime_ns
        invoke(window["port"], "SaveCurrentItemAsync", timeout=120)
        deadline = time.time() + 30
        while time.time() < deadline and preview.stat().st_mtime_ns == before:
            time.sleep(0.5)
        if preview.stat().st_mtime_ns == before:
            raise LiveViewError("The window did not save the edits; a dialog may be waiting in it.")
    _record_shown(state, Path(shown["source"]), preview)  # the edits are now the agreed state
    print(f"Took over the user's edits. Before your next change, open this file in the service "
          f"(POST /api/5/projects/open), close the project you had open, and read the model again:\n{preview}")
    return 0


def cmd_arrange(_a) -> int:
    """Put the open window side by side with the agent's window again, when the user asks."""
    state = load_state()
    window = state["window"]
    if window_status(window) != "open":
        raise LiveViewError("No live view window is open.", EXIT_OFF)
    previous = _u32.GetForegroundWindow()
    print(side_by_side(window["pid"]))
    if previous and _u32.IsWindow(previous):
        _activate(previous)
    return 0


def cmd_stop(_a) -> int:
    state = load_state()
    window = state["window"]
    if window_alive(window):
        require_grpc()
        invoke(window["port"], "Shutdown", timeout=30)  # an error leaves the state as it is: the window still runs
        print("The Connection window was asked to close; it asks the user about edits that are not saved.")
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
    start.add_argument("--auto", action="store_true",
                       help="started because of the remembered 'always': refuse when the user closed the window")
    start.add_argument("--service", default="http://localhost:5000",
                       help="base URL of the running Connection REST API service; its installation is used")
    start.add_argument("--install", help="installation folder with IdeaConnection.exe, instead of --service")
    start.add_argument("--layout", choices=["side-by-side", "window"],
                       help="default: the remembered layout, side-by-side at first")
    start.add_argument("--timeout", type=float, default=100.0,
                       help="seconds to wait for the window (default 100, inside a 120 s command limit)")
    start.set_defaults(func=cmd_start)
    show = sub.add_parser("show")
    show.add_argument("file")
    show.add_argument("--replace-edited", action="store_true",
                      help="replace edits in the window; only after the user agreed")
    show.add_argument("--timeout", type=float, default=100.0)
    show.set_defaults(func=cmd_show)
    check = sub.add_parser("check")
    check.add_argument("--adopt", action="store_true",
                       help="take the user's edits over: save them in the window and name the file to open")
    check.set_defaults(func=cmd_check)
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
