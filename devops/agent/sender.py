"""
==========================================================
MetricGuard Agent — Sender Module  (sender.py)
==========================================================

Purpose
-------
Transmits collected payloads (metrics **and** logs) to the
MetricGuard backend via ``requests.post()``.

This module is a **pure network client** — it knows nothing
about *what* the data is or *how* it was gathered.

Two public methods:
    send(metrics)     →  POST /metrics
    send_log(entry)   →  POST /logs

Resilience features
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* **Retry with exponential backoff** — if the first POST
  fails, the sender waits ``retry_delay`` seconds, then
  ``retry_delay × 2``, then ``retry_delay × 4``, etc.
* **Timeout protection** — every HTTP call has a hard
  deadline so a hung backend can't block the agent forever.
* **Graceful degradation** — if all retries are exhausted
  the sender returns ``False`` and the caller moves on.
  The agent **never crashes**.
* **Detailed logging** — every attempt, every failure
  reason, and every retry delay is logged.

Usage
-----
    from sender import MetricSender
    s = MetricSender(config, logger)
    s.send(metrics_payload)     # → POST /metrics
    s.send_log(log_entry)       # → POST /logs
"""

from __future__ import annotations

import time
import logging
from typing import Dict, Any

import requests


class MetricSender:
    """
    HTTP client that ships metrics and logs to the backend.

    Parameters
    ----------
    config : AgentConfig
        Needs ``backend_url``, ``max_retries``,
        ``retry_delay``, and ``request_timeout``.
        Optionally ``logs_backend_url`` for the logs endpoint.
    logger : logging.Logger
        Logger instance for transmission logs.
    """

    def __init__(self, config, logger: logging.Logger) -> None:
        self._cfg = config
        self._log = logger

        # ── Derive the logs endpoint URL ─────────────────
        # If the config has an explicit logs_backend_url, use it.
        # Otherwise, replace the trailing path segment of
        # backend_url:  .../metrics  →  .../logs
        self._logs_url: str = getattr(
            config, "logs_backend_url", ""
        )
        if not self._logs_url:
            base = self._cfg.backend_url
            if base.rstrip("/").endswith("/metrics"):
                self._logs_url = base.rstrip("/").rsplit("/metrics", 1)[0] + "/logs"
            else:
                self._logs_url = base.rstrip("/") + "/logs"

    # ==========================================================
    # Internal: generic POST with retry
    # ==========================================================

    def _post_with_retry(
        self,
        url: str,
        payload: Dict[str, Any],
        label: str = "payload",
    ) -> bool:
        """
        POST *payload* to *url* with retry + exponential backoff.

        Parameters
        ----------
        url : str
            The full endpoint URL.
        payload : dict
            JSON-serializable data to send.
        label : str
            Human-readable label for log messages
            (e.g. "metrics" or "log entry").

        Returns
        -------
        bool
            ``True`` on success, ``False`` when all retries fail.
        """
        max_retries = self._cfg.max_retries
        base_delay  = self._cfg.retry_delay
        timeout     = self._cfg.request_timeout

        for attempt in range(1, max_retries + 1):

            # ── Try to POST ──────────────────────────────
            try:
                self._log.info(
                    "Sending %s to %s (attempt %d/%d)",
                    label, url, attempt, max_retries,
                )

                response = requests.post(
                    url,
                    json=payload,
                    timeout=timeout,
                    headers={"Content-Type": "application/json"},
                )

                # ── Evaluate response ────────────────────
                if response.ok:                       # 2xx
                    self._log.info(
                        "%s sent successfully (status %d)",
                        label.capitalize(), response.status_code,
                    )
                    return True

                # Non-2xx — log but still retry
                self._log.warning(
                    "Backend returned status %d: %s",
                    response.status_code,
                    response.text[:200],
                )

            # ── Specific failure modes ───────────────────
            except requests.exceptions.ConnectionError:
                self._log.error(
                    "Connection failed (attempt %d/%d): "
                    "Backend at %s is unreachable",
                    attempt, max_retries, url,
                )

            except requests.exceptions.Timeout:
                self._log.error(
                    "Request timed out (attempt %d/%d) after %ds",
                    attempt, max_retries, timeout,
                )

            except requests.exceptions.RequestException as exc:
                self._log.error(
                    "Request error (attempt %d/%d): %s",
                    attempt, max_retries, exc,
                )

            # ── Exponential backoff before next attempt ──
            if attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1))
                self._log.info("Retrying in %d seconds...", delay)
                time.sleep(delay)

        # ── All attempts exhausted ───────────────────────
        self._log.error(
            "All %d attempts failed. "
            "%s will be lost for this cycle.",
            max_retries, label.capitalize(),
        )
        return False

    # ==========================================================
    # Public API — Metrics
    # ==========================================================

    def send(self, metrics: Dict[str, Any]) -> bool:
        """
        POST *metrics* to the backend ``/metrics`` endpoint.

        Parameters
        ----------
        metrics : dict
            JSON-serializable payload from ``collector.collect()``.

        Returns
        -------
        bool
            ``True`` if the backend accepted the payload,
            ``False`` after all retries are exhausted.
        """
        return self._post_with_retry(
            url=self._cfg.backend_url,
            payload=metrics,
            label="metrics",
        )

    # ==========================================================
    # Public API — Logs  (Phase 7)
    # ==========================================================

    def send_log(self, log_entry: Dict[str, Any]) -> bool:
        """
        POST a single parsed log entry to ``/logs``.

        Parameters
        ----------
        log_entry : dict
            A structured log dict with keys: ``timestamp``,
            ``level``, ``message``, ``service_name``.

        Returns
        -------
        bool
            ``True`` on success, ``False`` on failure.
        """
        return self._post_with_retry(
            url=self._logs_url,
            payload=log_entry,
            label="log entry",
        )
