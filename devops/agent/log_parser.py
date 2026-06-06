"""
==========================================================
MetricGuard Agent — Log Parser  (log_parser.py)
==========================================================

Purpose
-------
Converts raw, unstructured log lines from application log
files into structured JSON dictionaries suitable for the
backend's ``POST /logs`` endpoint.

Expected input format
~~~~~~~~~~~~~~~~~~~~~
Most application logs follow this pattern::

    2026-06-05 10:15:00 ERROR Database timeout after 30s
    2026-06-05 10:15:01 INFO  Connection restored

The parser extracts:

* **timestamp** — the datetime string at the start
* **level**     — the severity keyword (DEBUG … CRITICAL)
* **message**   — everything after the level keyword

If a line does not match the expected format (e.g. a stack
trace continuation, or garbage bytes), the parser returns
it with ``level="UNKNOWN"`` so the backend still receives
the data, and logs a warning.

Service-name mapping
~~~~~~~~~~~~~~~~~~~~
The ``service_name`` field is inferred from the **filename**
being watched.  ``log_collector.py`` passes the filename to
the parser, which maps it using a configurable dictionary:

    application.log  →  application-service
    database.log     →  database-service
    server.log       →  server-service

Usage
-----
    from log_parser import LogParser

    parser = LogParser(logger)
    entry  = parser.parse_line(
        "2026-06-05 10:15:00 ERROR Disk full",
        filename="database.log",
    )
    # entry == {
    #     "timestamp": "2026-06-05 10:15:00",
    #     "level":     "ERROR",
    #     "message":   "Disk full",
    #     "service_name": "database-service",
    # }
"""

from __future__ import annotations

import re
import logging
from typing import Optional, Dict, Any


# ----------------------------------------------------------
# Compiled regex for the standard log format:
#   <datetime>  <LEVEL>  <message>
#
# Group 1: timestamp  (YYYY-MM-DD HH:MM:SS)
# Group 2: level      (DEBUG|INFO|WARNING|ERROR|CRITICAL)
# Group 3: message    (everything that follows)
# ----------------------------------------------------------
_LOG_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})"  # timestamp
    r"\s+"                                          # separator
    r"(DEBUG|INFO|WARNING|ERROR|CRITICAL)"          # level
    r"\s+"                                          # separator
    r"(.+)$",                                       # message
    re.IGNORECASE,
)

# ----------------------------------------------------------
# Default map from log filename → service_name
# ----------------------------------------------------------
_DEFAULT_SERVICE_MAP: Dict[str, str] = {
    "application.log": "application-service",
    "database.log":    "database-service",
    "server.log":      "server-service",
}


class LogParser:
    """
    Stateless parser that converts raw log lines into
    structured dictionaries.

    Parameters
    ----------
    logger : logging.Logger
        Logger for parse-error warnings.
    service_map : dict, optional
        Override the filename → service_name mapping.
    """

    def __init__(
        self,
        logger: logging.Logger,
        service_map: Optional[Dict[str, str]] = None,
    ) -> None:
        self._log = logger
        self._service_map = service_map or dict(_DEFAULT_SERVICE_MAP)

    # ======================================================
    # Public API
    # ======================================================

    def parse_line(
        self,
        line: str,
        filename: str = "unknown.log",
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a single log line into a structured dict.

        Parameters
        ----------
        line : str
            One raw line from a log file (with or without
            trailing newline).
        filename : str
            The basename of the log file this line came from.
            Used to resolve ``service_name``.

        Returns
        -------
        dict or None
            A dict with keys ``timestamp``, ``level``,
            ``message``, and ``service_name``.
            Returns ``None`` if the line is empty or
            whitespace-only (skip silently).
        """
        # Strip whitespace / newlines
        stripped = line.strip()

        # Skip blank lines silently
        if not stripped:
            return None

        # Determine the service name from the filename
        service = self._resolve_service(filename)

        # Try the regex match
        match = _LOG_PATTERN.match(stripped)

        if match:
            return {
                "timestamp":    match.group(1),
                "level":        match.group(2).upper(),
                "message":      match.group(3).strip(),
                "service_name": service,
            }

        # ── Malformed line — still capture it ────────────
        self._log.warning(
            "Malformed log line from %s: %.120s",
            filename, stripped,
        )
        return {
            "timestamp":    "",          # backend will use now()
            "level":        "UNKNOWN",
            "message":      stripped,
            "service_name": service,
        }

    def parse_lines(
        self,
        lines: list[str],
        filename: str = "unknown.log",
    ) -> list[Dict[str, Any]]:
        """
        Parse multiple lines in one call (convenience).

        Blank lines and ``None`` results are filtered out.

        Parameters
        ----------
        lines : list of str
            Raw log lines.
        filename : str
            The source log file name.

        Returns
        -------
        list of dict
            Parsed entries (may be shorter than *lines*).
        """
        entries = []
        for line in lines:
            try:
                entry = self.parse_line(line, filename=filename)
                if entry is not None:
                    entries.append(entry)
            except Exception as exc:
                self._log.error(
                    "Unexpected error parsing line from %s: %s",
                    filename, exc,
                )
        return entries

    # ======================================================
    # Internal helpers
    # ======================================================

    def _resolve_service(self, filename: str) -> str:
        """
        Map a log filename to a service name.

        Falls back to the filename itself (minus extension)
        if no explicit mapping exists.
        """
        # Direct lookup
        if filename in self._service_map:
            return self._service_map[filename]

        # Fallback: strip extension and add "-service"
        base = filename.rsplit(".", 1)[0] if "." in filename else filename
        return f"{base}-service"
