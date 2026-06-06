"""
==========================================================
MetricGuard Agent — Metric Collector  (collector.py)
==========================================================

Purpose
-------
Collects live system metrics using ``psutil`` and returns
them as a single JSON-serializable dictionary.

This module is a **pure data producer** — it has no
knowledge of the network, the backend, or retry logic.
``main.py`` calls ``collect()`` and hands the result to
``sender.py``.

Refactored from
~~~~~~~~~~~~~~~~
``monitoring/metric_collector.py`` — the original monolith
that mixed collection, sending, and the main loop.  All
metric-gathering functions and the ``format_bytes`` helper
are preserved here with the same logic and error handling.

Metrics collected
~~~~~~~~~~~~~~~~~
============  ========================================
Metric        psutil call
============  ========================================
CPU Usage     ``psutil.cpu_percent(interval=1)``
Memory Usage  ``psutil.virtual_memory().percent``
Disk Usage    ``psutil.disk_usage(path).percent``
Disk Read     ``psutil.disk_io_counters().read_bytes``
Disk Write    ``psutil.disk_io_counters().write_bytes``
Net Receive   ``psutil.net_io_counters().bytes_recv``
Net Transmit  ``psutil.net_io_counters().bytes_sent``
Process Count ``len(psutil.pids())``
System Load   ``psutil.getloadavg()[0]``
System Uptime ``time.time() - psutil.boot_time()``
============  ========================================

Usage
-----
    from collector import MetricCollector
    mc = MetricCollector(config, logger)
    payload = mc.collect()
"""

from __future__ import annotations

import time
import platform
import logging
from typing import Optional, Dict, Any, Tuple

import psutil

# ── Type alias for the full metrics payload ──────────────
MetricsPayload = Dict[str, Any]


class MetricCollector:
    """
    Stateful collector that tracks previous I/O counters so
    it can report **speed** (delta bytes since last call)
    rather than cumulative bytes since boot.

    Parameters
    ----------
    config : AgentConfig
        The loaded agent configuration (needs ``disk_path``
        and ``enabled_metrics``).
    logger : logging.Logger
        Logger instance for all output.
    """

    def __init__(self, config, logger: logging.Logger) -> None:
        self._cfg    = config
        self._log    = logger

        # ── Initialise I/O baselines ─────────────────────
        # First call to psutil gives cumulative-since-boot
        # values; we store them so the *next* call produces
        # a meaningful delta.
        disk = psutil.disk_io_counters()
        self._prev_disk_read:  int = disk.read_bytes  if disk else 0
        self._prev_disk_write: int = disk.write_bytes if disk else 0

        net = psutil.net_io_counters()
        self._prev_net_sent: int = net.bytes_sent if net else 0
        self._prev_net_recv: int = net.bytes_recv if net else 0

        self._log.debug("MetricCollector initialised — baselines captured")

    # ==========================================================
    # Individual metric functions
    # ==========================================================
    # Each one is self-contained: catches its own exceptions
    # and returns ``None`` on failure so a single broken metric
    # never stops the rest of the collection cycle.

    def _cpu_usage(self) -> Optional[float]:
        """Return CPU usage % (measured over 1 s)."""
        try:
            usage = psutil.cpu_percent(interval=1)
            self._log.debug("CPU usage: %.1f%%", usage)
            return round(usage, 2)
        except Exception as exc:
            self._log.error("Failed to collect CPU usage: %s", exc)
            return None

    def _memory_usage(self) -> Optional[float]:
        """Return RAM usage %."""
        try:
            usage = psutil.virtual_memory().percent
            self._log.debug("Memory usage: %.1f%%", usage)
            return round(usage, 2)
        except Exception as exc:
            self._log.error("Failed to collect memory usage: %s", exc)
            return None

    def _disk_usage(self) -> Optional[float]:
        """Return disk usage % for the configured path."""
        try:
            usage = psutil.disk_usage(self._cfg.disk_path).percent
            self._log.debug("Disk usage: %.1f%%", usage)
            return round(usage, 2)
        except Exception as exc:
            self._log.error("Failed to collect disk usage: %s", exc)
            return None

    def _disk_io(self) -> Tuple[Optional[int], Optional[int]]:
        """
        Return (read_speed, write_speed) in bytes since the
        previous collection cycle.
        """
        try:
            counters = psutil.disk_io_counters()
            if counters is None:
                self._log.warning("Disk I/O counters not available")
                return (None, None)

            read_speed  = counters.read_bytes  - self._prev_disk_read
            write_speed = counters.write_bytes - self._prev_disk_write

            # Update baselines for the next call
            self._prev_disk_read  = counters.read_bytes
            self._prev_disk_write = counters.write_bytes

            return (read_speed, write_speed)
        except Exception as exc:
            self._log.error("Failed to collect disk I/O: %s", exc)
            return (None, None)

    def _network_io(self) -> Tuple[Optional[int], Optional[int]]:
        """
        Return (upload_speed, download_speed) in bytes since
        the previous collection cycle.
        """
        try:
            counters = psutil.net_io_counters()
            if counters is None:
                self._log.warning("Network I/O counters not available")
                return (None, None)

            upload   = counters.bytes_sent - self._prev_net_sent
            download = counters.bytes_recv - self._prev_net_recv

            self._prev_net_sent = counters.bytes_sent
            self._prev_net_recv = counters.bytes_recv

            return (upload, download)
        except Exception as exc:
            self._log.error("Failed to collect network I/O: %s", exc)
            return (None, None)

    def _process_count(self) -> Optional[int]:
        """Return the number of running processes."""
        try:
            count = len(psutil.pids())
            self._log.debug("Process count: %d", count)
            return count
        except Exception as exc:
            self._log.error("Failed to collect process count: %s", exc)
            return None

    def _system_load(self) -> Optional[float]:
        """
        Return the 1-minute load average.

        On Windows ``psutil.getloadavg()`` is unreliable,
        so we return ``None`` instead of a misleading zero.
        """
        try:
            if platform.system() == "Windows":
                self._log.debug("System load not supported on Windows")
                return None
            load = psutil.getloadavg()[0]
            self._log.debug("System load: %.2f", load)
            return round(load, 2)
        except Exception as exc:
            self._log.error("Failed to collect system load: %s", exc)
            return None

    def _system_uptime(self) -> Optional[str]:
        """
        Return uptime as a human-readable string like
        ``"12h 34m 56s"``.
        """
        try:
            seconds = time.time() - psutil.boot_time()
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            readable = f"{h}h {m}m {s}s"
            self._log.debug("System uptime: %s", readable)
            return readable
        except Exception as exc:
            self._log.error("Failed to collect system uptime: %s", exc)
            return None

    # ==========================================================
    # Byte formatting helper (preserved from original)
    # ==========================================================

    @staticmethod
    def format_bytes(value: Optional[int]) -> Optional[str]:
        """
        Convert a raw byte count into a human-readable string.

        Examples
        --------
        >>> MetricCollector.format_bytes(1536)
        '1.50 KB'
        >>> MetricCollector.format_bytes(None)
        """
        if value is None:
            return None

        num = float(value)
        for unit in ("B", "KB", "MB", "GB"):
            if num < 1024:
                return f"{num:.2f} {unit}"
            num /= 1024
        return f"{num:.2f} TB"

    # ==========================================================
    # Main collection entry point
    # ==========================================================

    def collect(self) -> MetricsPayload:
        """
        Collect every enabled metric and return one dict.

        The returned dict always contains ``timestamp`` and
        ``agent_name``.  Individual metric keys are included
        only if the metric is **enabled** in config.yaml.

        Returns
        -------
        dict
            JSON-serializable payload ready for ``sender.py``.
        """
        self._log.info("Collecting system metrics...")

        enabled = self._cfg.enabled_metrics

        # ── Start with identity fields ───────────────────
        payload: MetricsPayload = {
            "timestamp":  time.strftime("%Y-%m-%dT%H:%M:%S"),
            "agent_name": self._cfg.agent_name,
        }

        # ── CPU ──────────────────────────────────────────
        if enabled.get("cpu", True):
            payload["cpu_usage"] = self._cpu_usage()

        # ── Memory ───────────────────────────────────────
        if enabled.get("memory", True):
            payload["ram_usage"] = self._memory_usage()

        # ── Disk ─────────────────────────────────────────
        if enabled.get("disk", True):
            payload["disk_usage"] = self._disk_usage()
            disk_read, disk_write = self._disk_io()
            payload["disk_read_speed"]  = self.format_bytes(disk_read)
            payload["disk_write_speed"] = self.format_bytes(disk_write)

        # ── Network ──────────────────────────────────────
        if enabled.get("network", True):
            net_up, net_down = self._network_io()
            payload["network_upload_speed"]   = self.format_bytes(net_up)
            payload["network_download_speed"] = self.format_bytes(net_down)

        # ── Process count ────────────────────────────────
        if enabled.get("process_count", True):
            payload["process_count"] = self._process_count()

        # ── System load ──────────────────────────────────
        if enabled.get("system_load", True):
            payload["system_load"] = self._system_load()

        # ── System uptime ────────────────────────────────
        if enabled.get("system_uptime", True):
            payload["system_uptime"] = self._system_uptime()

        self._log.info("Metrics collected successfully")
        return payload
