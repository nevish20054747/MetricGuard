"""
==========================================================
MetricGuard Agent — Configuration Loader  (config.py)
==========================================================

Purpose
-------
Reads ``config.yaml``, validates every field, and exposes a
single ``AgentConfig`` dataclass that the rest of the agent
imports.  If the YAML file is missing, malformed, or has
invalid values, the loader falls back to sensible defaults
so the agent can always start.

Design decisions
----------------
* **YAML-first** — config lives in a human-readable YAML
  file next to the code (``config.yaml``).  No environment
  variables or .env files are needed, but you can add that
  layer later if you want.
* **Frozen dataclass** — once loaded, config values cannot
  be accidentally mutated at runtime.
* **Eager validation** — bad values are caught at startup
  with a clear log message, not 20 minutes later in a
  random traceback.

Usage
-----
    from config import load_config
    cfg = load_config()          # reads config.yaml
    print(cfg.backend_url)
    print(cfg.enabled_metrics)

Dependencies
------------
    pip install pyyaml
"""

from __future__ import annotations

import os
import sys
import logging
from dataclasses import dataclass, field
from typing import Dict, List

# ── YAML import with graceful failure ────────────────────
try:
    import yaml
except ImportError:
    print(
        "[FATAL] PyYAML is not installed.\n"
        "        Run:  pip install pyyaml\n"
    )
    sys.exit(1)


# ----------------------------------------------------------
# Default values (used when a key is missing from the YAML)
# ----------------------------------------------------------
_DEFAULTS = {
    "backend_url":       "http://localhost:8000/metrics",
    "collection_interval": 30,
    "agent_name":        "machine-01",
    "max_retries":       3,
    "retry_delay":       2,
    "request_timeout":   10,
    "log_file":          "logs/agent.log",
    "log_level":         "INFO",
    "disk_path":         "/",
    "enabled_metrics": {
        "cpu":            True,
        "memory":         True,
        "disk":           True,
        "network":        True,
        "process_count":  True,
        "system_load":    True,
        "system_uptime":  True,
    },
    # Phase 7 — Log collection
    "log_watch_files":   [],
    "logs_backend_url":  "",
}


# ----------------------------------------------------------
# Dataclass that holds validated configuration
# ----------------------------------------------------------
@dataclass(frozen=True)
class AgentConfig:
    """
    Immutable container for every configuration value.

    After ``load_config()`` returns an ``AgentConfig``,
    no code can accidentally change a setting.

    Attributes
    ----------
    backend_url : str
        The full URL to POST metrics to.
    collection_interval : int
        Seconds between collection cycles.
    agent_name : str
        Human-readable identifier for this host.
    max_retries : int
        How many times to retry a failed POST.
    retry_delay : int
        Base seconds between retries (doubles each attempt).
    request_timeout : int
        Seconds before a single HTTP request times out.
    log_file : str
        Path to the agent's persistent log file.
    log_level : str
        Python logging level name (DEBUG, INFO, …).
    disk_path : str
        Filesystem path for ``psutil.disk_usage()``.
    enabled_metrics : dict
        Per-metric on/off toggles.
    """

    backend_url:        str             = _DEFAULTS["backend_url"]
    collection_interval: int            = _DEFAULTS["collection_interval"]
    agent_name:         str             = _DEFAULTS["agent_name"]
    max_retries:        int             = _DEFAULTS["max_retries"]
    retry_delay:        int             = _DEFAULTS["retry_delay"]
    request_timeout:    int             = _DEFAULTS["request_timeout"]
    log_file:           str             = _DEFAULTS["log_file"]
    log_level:          str             = _DEFAULTS["log_level"]
    disk_path:          str             = _DEFAULTS["disk_path"]
    enabled_metrics:    Dict[str, bool] = field(
        default_factory=lambda: dict(_DEFAULTS["enabled_metrics"])
    )
    # Phase 7 — Log collection
    log_watch_files:    List[str]       = field(
        default_factory=lambda: list(_DEFAULTS["log_watch_files"])
    )
    logs_backend_url:   str             = _DEFAULTS["logs_backend_url"]


# ----------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------

def _resolve_yaml_path() -> str:
    """
    Return the absolute path to ``config.yaml``.

    Strategy: look for the file in the same directory as
    *this* Python file (``agent/config.py``).
    """
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "config.yaml")


def _read_yaml(path: str) -> dict:
    """
    Open and parse a YAML file.

    Returns
    -------
    dict
        Parsed contents, or an empty dict on any error.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        # yaml.safe_load returns None for an empty file
        if data is None:
            logging.warning(
                "config.yaml is empty — using all defaults"
            )
            return {}

        if not isinstance(data, dict):
            logging.warning(
                "config.yaml root is not a mapping — using defaults"
            )
            return {}

        return data

    except FileNotFoundError:
        logging.warning(
            "config.yaml not found at %s — using defaults", path
        )
        return {}

    except yaml.YAMLError as exc:
        logging.error(
            "Failed to parse config.yaml: %s — using defaults", exc
        )
        return {}


def _validate_positive_int(raw: object, name: str, default: int) -> int:
    """
    Coerce *raw* to a positive ``int``, falling back to *default*.
    """
    try:
        value = int(raw)
        if value <= 0:
            raise ValueError("must be > 0")
        return value
    except (TypeError, ValueError) as exc:
        logging.warning(
            "Invalid %s=%r (%s) — using default %d",
            name, raw, exc, default,
        )
        return default


def _validate_log_level(raw: object) -> str:
    """
    Ensure *raw* is a recognised Python log-level name.
    """
    valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if isinstance(raw, str) and raw.upper() in valid:
        return raw.upper()
    logging.warning(
        "Invalid log_level=%r — using default INFO", raw
    )
    return "INFO"


def _validate_enabled_metrics(raw: object) -> Dict[str, bool]:
    """
    Validate the ``enabled_metrics`` sub-dictionary.

    Missing keys are filled in from defaults.
    Non-boolean values are treated as ``True``.
    """
    defaults = dict(_DEFAULTS["enabled_metrics"])

    if not isinstance(raw, dict):
        logging.warning(
            "enabled_metrics is not a mapping — using defaults"
        )
        return defaults

    merged: Dict[str, bool] = {}
    for key, default_val in defaults.items():
        user_val = raw.get(key, default_val)
        # Accept truthy/falsy but always store a real bool
        merged[key] = bool(user_val)

    return merged


def _validate_file_list(raw: object) -> List[str]:
    """
    Validate that *raw* is a list of strings (file paths).

    Returns an empty list if the value is missing or invalid.
    """
    if raw is None:
        return []
    if not isinstance(raw, list):
        logging.warning(
            "log_watch_files is not a list — using empty default"
        )
        return []
    return [str(item) for item in raw if item]


# ----------------------------------------------------------
# Public API
# ----------------------------------------------------------

def load_config(path: str | None = None) -> AgentConfig:
    """
    Load, validate, and return the agent configuration.

    Parameters
    ----------
    path : str or None
        Override the YAML file path (useful in tests).
        When ``None``, uses ``config.yaml`` next to this file.

    Returns
    -------
    AgentConfig
        A frozen dataclass with all validated settings.

    Example
    -------
    >>> cfg = load_config()
    >>> cfg.backend_url
    'http://localhost:8000/metrics'
    >>> cfg.enabled_metrics["cpu"]
    True
    """
    yaml_path = path or _resolve_yaml_path()
    raw = _read_yaml(yaml_path)

    config = AgentConfig(
        backend_url=str(
            raw.get("backend_url", _DEFAULTS["backend_url"])
        ),
        collection_interval=_validate_positive_int(
            raw.get("collection_interval"),
            "collection_interval",
            _DEFAULTS["collection_interval"],
        ),
        agent_name=str(
            raw.get("agent_name", _DEFAULTS["agent_name"])
        ),
        max_retries=_validate_positive_int(
            raw.get("max_retries"),
            "max_retries",
            _DEFAULTS["max_retries"],
        ),
        retry_delay=_validate_positive_int(
            raw.get("retry_delay"),
            "retry_delay",
            _DEFAULTS["retry_delay"],
        ),
        request_timeout=_validate_positive_int(
            raw.get("request_timeout"),
            "request_timeout",
            _DEFAULTS["request_timeout"],
        ),
        log_file=str(
            raw.get("log_file", _DEFAULTS["log_file"])
        ),
        log_level=_validate_log_level(
            raw.get("log_level", _DEFAULTS["log_level"])
        ),
        disk_path=str(
            raw.get("disk_path", _DEFAULTS["disk_path"])
        ),
        enabled_metrics=_validate_enabled_metrics(
            raw.get("enabled_metrics")
        ),
        # Phase 7 — Log collection
        log_watch_files=_validate_file_list(
            raw.get("log_watch_files")
        ),
        logs_backend_url=str(
            raw.get("logs_backend_url", _DEFAULTS["logs_backend_url"])
        ),
    )

    return config
