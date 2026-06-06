"""
==========================================================
MetricGuard Agent — Logging Module  (logger.py)
==========================================================

Purpose
-------
Sets up a centralized, dual-output logger for the entire
MetricGuard Agent.  Every other module imports the helper
``setup_logger()`` and uses the returned ``logging.Logger``
for all output.

Log destinations
~~~~~~~~~~~~~~~~
1. **Console** (stdout) — coloured, real-time visibility
   while running interactively or inside ``docker logs``.
2. **File** (``logs/agent.log`` by default) — persistent
   history that survives restarts.

What gets logged
~~~~~~~~~~~~~~~~
* Agent startup banner and loaded configuration
* Every metric-collection cycle
* HTTP transmission successes and failures
* Retry attempts with backoff durations
* Graceful-shutdown events
* Unexpected exceptions with full tracebacks

Usage
-----
    from logger import setup_logger
    logger = setup_logger(log_file="logs/agent.log", log_level="INFO")
    logger.info("Agent started")

Design notes
------------
* The logger is NOT created at module-import time.
  ``main.py`` calls ``setup_logger()`` **after** loading
  config so the file path and level come from YAML.
* Idempotent — calling ``setup_logger()`` twice with the
  same arguments does not duplicate handlers.
"""

from __future__ import annotations

import os
import logging


def setup_logger(
    log_file: str = "logs/agent.log",
    log_level: str = "INFO",
) -> logging.Logger:
    """
    Create (or retrieve) the application-wide logger.

    Parameters
    ----------
    log_file : str
        Relative or absolute path to the log file.
        Parent directories are created automatically.
    log_level : str
        One of DEBUG, INFO, WARNING, ERROR, CRITICAL.

    Returns
    -------
    logging.Logger
        Configured logger named ``MetricGuard.Agent``.
    """

    # ── Resolve numeric level ────────────────────────────
    level = getattr(logging, log_level.upper(), logging.INFO)

    # ── Get or create the named logger ───────────────────
    agent_logger = logging.getLogger("MetricGuard.Agent")
    agent_logger.setLevel(level)

    # Prevent adding duplicate handlers on repeated calls
    if agent_logger.handlers:
        return agent_logger

    # ── Formatter ────────────────────────────────────────
    # [2026-06-05 21:15:00] INFO  — message
    formatter = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)-8s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── File handler ─────────────────────────────────────
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    # ── Console handler ──────────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    # ── Attach handlers ──────────────────────────────────
    agent_logger.addHandler(file_handler)
    agent_logger.addHandler(console_handler)

    return agent_logger
