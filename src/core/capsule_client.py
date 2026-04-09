"""CapsuleAPI SDK wrapper (ctypes) and a pure-Python MockSource.

Two concrete data sources are provided:
- ``CapsuleDLLSource``  – loads CapsuleClient.dll and drives the real SDK pipeline.
- ``MockSource``        – generates synthetic sine-wave data in a background thread;
                          no DLL required (useful for development and unit tests).

Both expose the same interface::

    source.start(on_data)   # on_data: Callable[[EEGRecord], None]
    source.stop()
"""

from __future__ import annotations

import ctypes
import logging
import math
import random
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from src.config import AppConfig
from src.models import EEGRecord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Callback type alias
# ---------------------------------------------------------------------------
OnDataCallback = Callable[[EEGRecord], None]


# ===========================================================================
# ctypes structures matching the C SDK structs
# ===========================================================================

class _ProductivityValues(ctypes.Structure):
    """Maps to ``clCNFBMetricsProductivityValues`` in CNFBMetricsProductivity.h."""

    _fields_ = [
        ("fatigueScore",       ctypes.c_float),
        ("gravityScore",       ctypes.c_float),
        ("concentrationScore", ctypes.c_float),
        ("relaxationScore",    ctypes.c_float),
        ("accumulatedFatigue", ctypes.c_float),
    ]


# ===========================================================================
# ctypes callback function-type declarations
# ===========================================================================

# void handler(clCNFBMetricProductivity nfb, const clCNFBMetricsProductivityValues* values)
_ProductivityValuesHandler = ctypes.CFUNCTYPE(
    None,                                  # return type
    ctypes.c_void_p,                       # nfb handle
    ctypes.POINTER(_ProductivityValues),   # values pointer
)

# void handler(clCNFBMetricProductivity nfb, const clCNFBUserArtifacts* artifacts)
# We only need the nfb handle here; artifact data fields are unused in MVP
_ArtifactsHandler = ctypes.CFUNCTYPE(
    None,
    ctypes.c_void_p,  # nfb handle
    ctypes.c_void_p,  # clCNFBUserArtifacts* (opaque – we only need the trigger)
)

# void handler(clCClient client)
_ClientHandler = ctypes.CFUNCTYPE(None, ctypes.c_void_p)

# void handler(clCDevice device, clCDeviceConnectionState state)
_DeviceConnectionHandler = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int)

# void handler(clCSession session)
_SessionHandler = ctypes.CFUNCTYPE(None, ctypes.c_void_p)

# void handler(clCDeviceLocator locator, clCDeviceInfoList list)
_DeviceListHandler = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)


# ===========================================================================
# DLL function signature setup
# ===========================================================================

def _configure_dll(dll: ctypes.CDLL) -> None:
    """Annotate argtypes / restype for every DLL function we use."""

    vp = ctypes.c_void_p
    char_p = ctypes.c_char_p
    bp = ctypes.c_bool
    i32 = ctypes.c_int32
    i64 = ctypes.c_int64
    f64 = ctypes.c_double
    err_p = ctypes.POINTER(ctypes.c_int)  # clCError*

    # ── CString ──────────────────────────────────────────────────────────────
    dll.clCString_CStr.restype = char_p
    dll.clCString_CStr.argtypes = [vp]
    dll.clCString_Free.restype = None
    dll.clCString_Free.argtypes = [vp]

    # ── Client ───────────────────────────────────────────────────────────────
    dll.clCClient_CreateWithDataDirectoryAndName.restype = vp
    dll.clCClient_CreateWithDataDirectoryAndName.argtypes = [char_p, char_p]

    dll.clCClient_Destroy.restype = None
    dll.clCClient_Destroy.argtypes = [vp]

    dll.clCClient_SetAppVersion.restype = None
    dll.clCClient_SetAppVersion.argtypes = [vp, char_p]

    dll.clCClient_Connect.restype = None
    dll.clCClient_Connect.argtypes = [vp, char_p]

    dll.clCClient_Disconnect.restype = None
    dll.clCClient_Disconnect.argtypes = [vp]

    dll.clCClient_IsConnected.restype = bp
    dll.clCClient_IsConnected.argtypes = [vp]

    dll.clCClient_IsConnecting.restype = bp
    dll.clCClient_IsConnecting.argtypes = [vp]

    dll.clCClient_Update.restype = None
    dll.clCClient_Update.argtypes = [vp]

    dll.clCClient_GetOnConnectedEvent.restype = vp
    dll.clCClient_GetOnConnectedEvent.argtypes = [vp]

    dll.clCClientDelegate_Set.restype = None
    dll.clCClientDelegate_Set.argtypes = [vp, _ClientHandler]

    # ── Device locator ────────────────────────────────────────────────────────
    # clC_DT_NeiryAny = 4
    dll.clCClient_ChooseDeviceType.restype = vp
    dll.clCClient_ChooseDeviceType.argtypes = [vp, ctypes.c_int]

    dll.clCDeviceLocator_Destroy.restype = None
    dll.clCDeviceLocator_Destroy.argtypes = [vp]

    dll.clCDeviceLocator_RequestDevices.restype = None
    dll.clCDeviceLocator_RequestDevices.argtypes = [vp, i32]

    dll.clCDeviceLocator_GetOnDevicesEvent.restype = vp
    dll.clCDeviceLocator_GetOnDevicesEvent.argtypes = [vp]

    dll.clCDeviceLocatorDelegateDeviceInfoList_Set.restype = None
    dll.clCDeviceLocatorDelegateDeviceInfoList_Set.argtypes = [vp, _DeviceListHandler]

    # ── DeviceInfoList ────────────────────────────────────────────────────────
    dll.clCDeviceInfoList_GetCount.restype = i32
    dll.clCDeviceInfoList_GetCount.argtypes = [vp]

    dll.clCDeviceInfoList_GetDeviceInfo.restype = vp
    dll.clCDeviceInfoList_GetDeviceInfo.argtypes = [vp, i32]

    dll.clCDeviceInfo_GetID.restype = vp
    dll.clCDeviceInfo_GetID.argtypes = [vp]

    dll.clCDeviceInfo_GetName.restype = vp
    dll.clCDeviceInfo_GetName.argtypes = [vp]

    # ── Device ────────────────────────────────────────────────────────────────
    dll.clCDeviceLocator_CreateDevice.restype = vp
    dll.clCDeviceLocator_CreateDevice.argtypes = [vp, char_p]

    dll.clCDevice_Connect.restype = None
    dll.clCDevice_Connect.argtypes = [vp]

    dll.clCDevice_IsConnected.restype = bp
    dll.clCDevice_IsConnected.argtypes = [vp]

    dll.clCDevice_Release.restype = None
    dll.clCDevice_Release.argtypes = [vp]

    dll.clCDevice_GetOnConnectionStateChangedEvent.restype = vp
    dll.clCDevice_GetOnConnectionStateChangedEvent.argtypes = [vp]

    dll.clCDeviceDelegateConnectionState_Set.restype = None
    dll.clCDeviceDelegateConnectionState_Set.argtypes = [vp, _DeviceConnectionHandler]

    # ── Session ───────────────────────────────────────────────────────────────
    dll.clCClient_CreateSession.restype = vp
    dll.clCClient_CreateSession.argtypes = [vp, vp]

    dll.clCSession_Start.restype = None
    dll.clCSession_Start.argtypes = [vp]

    dll.clCSession_Stop.restype = None
    dll.clCSession_Stop.argtypes = [vp]

    dll.clCSession_IsActive.restype = bp
    dll.clCSession_IsActive.argtypes = [vp]

    dll.clCSession_Destroy.restype = None
    dll.clCSession_Destroy.argtypes = [vp]

    dll.clCSession_GetOnSessionStartedEvent.restype = vp
    dll.clCSession_GetOnSessionStartedEvent.argtypes = [vp]

    dll.clCSessionDelegate_Set.restype = None
    dll.clCSessionDelegate_Set.argtypes = [vp, _SessionHandler]

    # ── NFB Metrics Productivity ──────────────────────────────────────────────
    dll.clCNFBMetricsProductivity_Create.restype = vp
    dll.clCNFBMetricsProductivity_Create.argtypes = [
        vp,     # session
        char_p, # path
        f64,    # speed
        f64,    # maxSpeed
        f64,    # slowDown
        err_p,  # error out
    ]

    dll.clCNFBMetricsProductivity_InitializeNFB.restype = None
    dll.clCNFBMetricsProductivity_InitializeNFB.argtypes = [vp, char_p, err_p]

    dll.clCNFBMetricsProductivity_Destroy.restype = None
    dll.clCNFBMetricsProductivity_Destroy.argtypes = [vp]

    dll.clCNFBMetricsProductivity_GetOnProductivityValuesEvent.restype = vp
    dll.clCNFBMetricsProductivity_GetOnProductivityValuesEvent.argtypes = [vp]

    dll.clCNFBMetricsProductivity_ValuesEvent_Set.restype = None
    dll.clCNFBMetricsProductivity_ValuesEvent_Set.argtypes = [vp, _ProductivityValuesHandler]

    dll.clCNFBMetricsProductivity_GetOnArtifactsEvent.restype = vp
    dll.clCNFBMetricsProductivity_GetOnArtifactsEvent.argtypes = [vp]

    dll.clCNFBMetricsProductivity_ArtifactsEvent_Set.restype = None
    dll.clCNFBMetricsProductivity_ArtifactsEvent_Set.argtypes = [vp, _ArtifactsHandler]


# ===========================================================================
# CapsuleDLLSource
# ===========================================================================

class CapsuleDLLSource:
    """Wraps CapsuleClient.dll and drives the full SDK pipeline.

    Usage::

        source = CapsuleDLLSource(config, device_id="AA:BB:CC:DD:EE:FF")
        source.start(on_data=my_callback)
        # ... session runs ...
        source.stop()

    ``on_data`` is called from the update thread whenever new productivity
    values arrive from the SDK.
    """

    def __init__(self, config: AppConfig, device_id: Optional[str] = None) -> None:
        self._config = config
        self._device_id = device_id

        self._dll: Optional[ctypes.CDLL] = None
        self._client: int = 0
        self._locator: int = 0
        self._device: int = 0
        self._session: int = 0
        self._nfb: int = 0

        self._on_data: Optional[OnDataCallback] = None
        self._artifact_flag: bool = False

        # Strong references to ctypes callback objects (prevents GC)
        self._callbacks: dict[str, object] = {}

        self._update_thread: Optional[threading.Thread] = None
        self._running = threading.Event()

        # Synchronisation events for async SDK steps
        self._connected = threading.Event()
        self._device_list_received = threading.Event()
        self._device_list: list[tuple[str, str]] = []  # [(id, name), ...]
        self._device_connected = threading.Event()
        self._session_started = threading.Event()

    # ── Public interface ──────────────────────────────────────────────────────

    def start(self, on_data: OnDataCallback) -> None:
        """Connect to the SDK, initialise the session, and start streaming."""
        self._on_data = on_data
        self._dll = ctypes.CDLL(str(self._config.dll_path))
        _configure_dll(self._dll)

        self._create_client()
        self._connect_client()
        self._scan_devices()
        self._connect_device()
        self._create_session()
        self._start_nfb()

        # Start the update loop thread
        self._running.set()
        self._update_thread = threading.Thread(
            target=self._update_loop, name="CapsuleUpdateLoop", daemon=True
        )
        self._update_thread.start()
        logger.info("CapsuleDLLSource started.")

    def stop(self) -> None:
        """Stop the session and clean up all SDK resources."""
        self._running.clear()
        if self._update_thread:
            self._update_thread.join(timeout=5.0)

        dll = self._dll
        if dll is None:
            return

        if self._nfb:
            dll.clCNFBMetricsProductivity_Destroy(self._nfb)
            self._nfb = 0
        if self._session:
            dll.clCSession_Stop(self._session)
            dll.clCSession_Destroy(self._session)
            self._session = 0
        if self._device:
            dll.clCDevice_Release(self._device)
            self._device = 0
        if self._locator:
            dll.clCDeviceLocator_Destroy(self._locator)
            self._locator = 0
        if self._client:
            dll.clCClient_Disconnect(self._client)
            dll.clCClient_Destroy(self._client)
            self._client = 0

        self._callbacks.clear()
        logger.info("CapsuleDLLSource stopped.")

    # ── Internal setup steps (called sequentially in start()) ────────────────

    def _create_client(self) -> None:
        dll = self._dll
        data_dir = str(self._config.raw_dir).encode()
        app_name = self._config.app_name.encode()
        self._client = dll.clCClient_CreateWithDataDirectoryAndName(data_dir, app_name)
        if not self._client:
            raise RuntimeError("clCClient_CreateWithDataDirectoryAndName returned NULL")
        dll.clCClient_SetAppVersion(self._client, self._config.app_version.encode())

    def _connect_client(self) -> None:
        dll = self._dll

        @_ClientHandler
        def on_connected(client: int) -> None:
            logger.debug("SDK: client connected.")
            self._connected.set()

        self._callbacks["on_connected"] = on_connected

        delegate = dll.clCClient_GetOnConnectedEvent(self._client)
        dll.clCClientDelegate_Set(delegate, on_connected)

        address = self._config.capsule_address.encode()
        dll.clCClient_Connect(self._client, address)

        # Pump updates until connected (or timeout)
        deadline = time.monotonic() + 10.0
        while not self._connected.is_set() and time.monotonic() < deadline:
            dll.clCClient_Update(self._client)
            time.sleep(self._config.update_interval_ms / 1000.0)

        if not self._connected.is_set():
            raise RuntimeError("Timed out waiting for Capsule connection.")

    def _scan_devices(self) -> None:
        dll = self._dll
        # clC_DT_NeiryAny = 4
        self._locator = dll.clCClient_ChooseDeviceType(self._client, 4)

        @_DeviceListHandler
        def on_devices(locator: int, device_list: int) -> None:
            count = dll.clCDeviceInfoList_GetCount(device_list)
            result: list[tuple[str, str]] = []
            for i in range(count):
                info = dll.clCDeviceInfoList_GetDeviceInfo(device_list, i)
                id_str_handle = dll.clCDeviceInfo_GetID(info)
                name_str_handle = dll.clCDeviceInfo_GetName(info)
                dev_id = dll.clCString_CStr(id_str_handle).decode("utf-8", errors="replace")
                dev_name = dll.clCString_CStr(name_str_handle).decode("utf-8", errors="replace")
                dll.clCString_Free(id_str_handle)
                dll.clCString_Free(name_str_handle)
                result.append((dev_id, dev_name))
                logger.info("Found device: %s (%s)", dev_id, dev_name)
            self._device_list = result
            self._device_list_received.set()

        self._callbacks["on_devices"] = on_devices

        delegate = dll.clCDeviceLocator_GetOnDevicesEvent(self._locator)
        dll.clCDeviceLocatorDelegateDeviceInfoList_Set(delegate, on_devices)

        dll.clCDeviceLocator_RequestDevices(self._locator, self._config.device_search_seconds)

        deadline = time.monotonic() + self._config.device_search_seconds + 5.0
        while not self._device_list_received.is_set() and time.monotonic() < deadline:
            dll.clCClient_Update(self._client)
            time.sleep(self._config.update_interval_ms / 1000.0)

        if not self._device_list:
            raise RuntimeError("No EEG devices found.")

    def _connect_device(self) -> None:
        dll = self._dll
        target_id = self._device_id

        if target_id is None:
            target_id = self._device_list[0][0]
            logger.info("No device ID specified — using first found: %s", target_id)

        self._device = dll.clCDeviceLocator_CreateDevice(
            self._locator, target_id.encode()
        )
        if not self._device:
            raise RuntimeError(f"Failed to create device handle for {target_id!r}")

        @_DeviceConnectionHandler
        def on_connection_state(device: int, state: int) -> None:
            # clC_SE_Connected = 1
            if state == 1:
                logger.debug("Device connected (state=%d)", state)
                self._device_connected.set()

        self._callbacks["on_device_connection"] = on_connection_state

        delegate = dll.clCDevice_GetOnConnectionStateChangedEvent(self._device)
        dll.clCDeviceDelegateConnectionState_Set(delegate, on_connection_state)

        dll.clCDevice_Connect(self._device)

        deadline = time.monotonic() + 15.0
        while not self._device_connected.is_set() and time.monotonic() < deadline:
            dll.clCClient_Update(self._client)
            time.sleep(self._config.update_interval_ms / 1000.0)

        if not self._device_connected.is_set():
            raise RuntimeError(f"Timed out waiting for device {target_id!r} to connect.")

    def _create_session(self) -> None:
        dll = self._dll
        self._session = dll.clCClient_CreateSession(self._client, self._device)
        if not self._session:
            raise RuntimeError("clCClient_CreateSession returned NULL")

        @_SessionHandler
        def on_session_started(session: int) -> None:
            logger.debug("Session started.")
            self._session_started.set()

        self._callbacks["on_session_started"] = on_session_started

        delegate = dll.clCSession_GetOnSessionStartedEvent(self._session)
        dll.clCSessionDelegate_Set(delegate, on_session_started)

        dll.clCSession_Start(self._session)

        deadline = time.monotonic() + 15.0
        while not self._session_started.is_set() and time.monotonic() < deadline:
            dll.clCClient_Update(self._client)
            time.sleep(self._config.update_interval_ms / 1000.0)

        if not self._session_started.is_set():
            raise RuntimeError("Timed out waiting for session to start.")

    def _start_nfb(self) -> None:
        dll = self._dll
        error = ctypes.c_int(0)
        log_path = str(self._config.raw_dir).encode()

        self._nfb = dll.clCNFBMetricsProductivity_Create(
            self._session,
            log_path,
            self._config.nfb_speed,
            self._config.nfb_max_speed,
            self._config.nfb_slow_down,
            ctypes.byref(error),
        )
        if not self._nfb or error.value != 0:
            raise RuntimeError(
                f"clCNFBMetricsProductivity_Create failed (error={error.value})"
            )

        # Register productivity-values callback
        @_ProductivityValuesHandler
        def on_values(nfb: int, values_ptr: ctypes.POINTER(_ProductivityValues)) -> None:
            if values_ptr and self._on_data:
                v = values_ptr.contents
                record = EEGRecord(
                    timestamp=time.time(),
                    concentration=float(v.concentrationScore),
                    relaxation=float(v.relaxationScore),
                    fatigue=float(v.fatigueScore),
                    artifact=self._artifact_flag,
                )
                self._artifact_flag = False
                self._on_data(record)

        self._callbacks["on_values"] = on_values
        delegate = dll.clCNFBMetricsProductivity_GetOnProductivityValuesEvent(self._nfb)
        dll.clCNFBMetricsProductivity_ValuesEvent_Set(delegate, on_values)

        # Register artifacts callback
        @_ArtifactsHandler
        def on_artifacts(nfb: int, _artifacts: int) -> None:
            self._artifact_flag = True

        self._callbacks["on_artifacts"] = on_artifacts
        art_delegate = dll.clCNFBMetricsProductivity_GetOnArtifactsEvent(self._nfb)
        dll.clCNFBMetricsProductivity_ArtifactsEvent_Set(art_delegate, on_artifacts)

        # Initialize NFB (no platform address for local-only use)
        dll.clCNFBMetricsProductivity_InitializeNFB(
            self._nfb, None, ctypes.byref(error)
        )
        if error.value != 0:
            logger.warning("clCNFBMetricsProductivity_InitializeNFB error=%d", error.value)

    # ── Update loop ───────────────────────────────────────────────────────────

    def _update_loop(self) -> None:
        interval = self._config.update_interval_ms / 1000.0
        while self._running.is_set():
            try:
                self._dll.clCClient_Update(self._client)
            except Exception:
                logger.exception("Error in CapsuleClient_Update")
                break
            time.sleep(interval)


# ===========================================================================
# MockSource — pure-Python synthetic data generator
# ===========================================================================

class MockSource:
    """Generates synthetic EEG metrics using sine waves with added noise.

    Requires no DLL. Suitable for development, demos, and unit tests.
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._on_data: Optional[OnDataCallback] = None

    def start(self, on_data: OnDataCallback) -> None:
        self._on_data = on_data
        self._running.set()
        self._thread = threading.Thread(
            target=self._generate, name="MockDataSource", daemon=True
        )
        self._thread.start()
        logger.info("MockSource started.")

    def stop(self) -> None:
        self._running.clear()
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("MockSource stopped.")

    def _generate(self) -> None:
        interval = 1.0 / self._config.mock_emit_hz
        t = 0.0
        while self._running.is_set():
            concentration = _clamp(0.5 + 0.4 * math.sin(t * 0.3) + _noise(0.05))
            relaxation    = _clamp(0.5 + 0.4 * math.sin(t * 0.2 + 1.0) + _noise(0.05))
            fatigue       = _clamp(0.2 + 0.3 * math.sin(t * 0.1 + 2.0) + _noise(0.04))
            artifact      = random.random() < 0.02  # 2 % of samples flagged

            record = EEGRecord(
                timestamp=time.time(),
                concentration=concentration,
                relaxation=relaxation,
                fatigue=fatigue,
                artifact=artifact,
            )
            if self._on_data:
                self._on_data(record)

            t += interval
            time.sleep(interval)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _noise(amplitude: float) -> float:
    return (random.random() * 2.0 - 1.0) * amplitude
