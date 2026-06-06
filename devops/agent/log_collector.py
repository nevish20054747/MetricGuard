"""
==========================================================
MetricGuard Agent — Log Collector  (log_collector.py)
==========================================================

Purpose
-------
Watches one or more application log files for **newly
appended lines**, parses them into structured JSON, and
sends them to the backend via ``POST /logs``.

How it works — two libraries in tandem
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
1. **watchdog** — a cross-platform filesystem-event library.
   We set up an ``Observer`` that monitors a directory (or
   specific files) and fires a callback every time a file is
   *modified* (i.e. new bytes are written).

2. **pygtail** — reads only the *new* lines appended since
   the last read.  It tracks its position by writing a small
   offset file (``<logfile>.offset``).  This guarantees:
   - No duplicate processing after restarts.
   - No need to re-read the entire file each time.

Together they give us **low-latency, exactly-once delivery**
of every new log line.

Architecture
~~~~~~~~~~~~
::

    ┌────────────┐  fs event   ┌───────────────┐
    │  watchdog  │────────────▶│ LogCollector   │
    │  Observer  │             │  ._on_modified │
    └────────────┘             └───────┬────────┘
                                       │
                                 pygtail (new lines)
                                       │
                                       ▼
                               ┌───────────────┐
                               │  LogParser     │
                               │  .parse_line() │
                               └───────┬────────┘
                                       │
                                       ▼
                               ┌───────────────┐
                               │  MetricSender  │
                               │  .send_log()   │
                               └───────────────┘
                                       │
                                  POST /logs
                                       │
                                       ▼
                                   Backend

Usage
-----
    from log_collector import LogCollector

    lc = LogCollector(config, logger, sender)
    lc.start()          # non-blocking (background thread)
    ...
    lc.stop()           # graceful shutdown

Dependencies
------------
    pip install watchdog pygtail
"""

from __future__ import annotations

import os
import time
import logging
import threading
from typing import List, Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent
from pygtail import Pygtail

from log_parser import LogParser


class _LogFileHandler(FileSystemEventHandler):
    """
    watchdog event handler that fires whenever one of the
    monitored log files is modified (new bytes appended).

    On each modification event it:
    1. Reads only the NEW lines via pygtail.
    2. Parses each line with ``LogParser``.
    3. Sends every parsed entry to the backend.
    """

    def __init__(
        self,
        watched_files: List[str],
        parser: LogParser,
        sender,                             # MetricSender instance
        logger: logging.Logger,
        offset_dir: str,
    ) -> None:
        super().__init__()
        self._watched   = {os.path.abspath(f) for f in watched_files}
        self._parser    = parser
        self._sender    = sender
        self._log       = logger
        self._offset_dir = offset_dir

        # Ensure offset directory exists
        os.makedirs(self._offset_dir, exist_ok=True)

    # ----------------------------------------------------------
    # watchdog callback — fires on *any* file change in the dir
    # ----------------------------------------------------------

    def on_modified(self, event):
        """
        Called by watchdog when a file in the watched directory
        is written to.  We filter to only our target files.
        """
        # Ignore directory events
        if event.is_directory:
            return

        filepath = os.path.abspath(event.src_path)

        # Only process files we are interested in
        if filepath not in self._watched:
            return

        filename = os.path.basename(filepath)
        self._log.debug("Detected modification: %s", filename)

        self._process_new_lines(filepath, filename)

    # ----------------------------------------------------------
    # Read new lines via pygtail and ship them
    # ----------------------------------------------------------

    def _process_new_lines(self, filepath: str, filename: str) -> None:
        """
        Use pygtail to read only lines appended since the
        last read, parse them, and POST each one to /logs.
        """
        # pygtail stores its offset file alongside the log,
        # or in a custom directory to keep things tidy.
        offset_file = os.path.join(
            self._offset_dir,
            f"{filename}.offset",
        )

        try:
            tail = Pygtail(filepath, offset_file=offset_file)
            new_lines = list(tail)
        except Exception as exc:
            self._log.error(
                "pygtail failed reading %s: %s", filename, exc,
            )
            return

        if not new_lines:
            return

        self._log.info(
            "Read %d new line(s) from %s", len(new_lines), filename,
        )

        # Parse and send each line individually so a single
        # bad line doesn't block the rest.
        sent = 0
        for raw_line in new_lines:
            try:
                entry = self._parser.parse_line(raw_line, filename=filename)
                if entry is None:
                    continue  # blank line

                ok = self._sender.send_log(entry)
                if ok:
                    sent += 1
                else:
                    self._log.warning(
                        "Failed to send log entry from %s: %.100s",
                        filename, entry.get("message", ""),
                    )
            except Exception as exc:
                self._log.error(
                    "Error processing line from %s: %s",
                    filename, exc,
                )

        self._log.info(
            "Sent %d/%d log entries from %s",
            sent, len(new_lines), filename,
        )


# ==============================================================
# Public LogCollector class
# ==============================================================

class LogCollector:
    """
    High-level orchestrator that sets up watchdog and
    exposes ``start()`` / ``stop()`` for ``main.py``.

    Parameters
    ----------
    config : AgentConfig
        Agent configuration (needs ``log_watch_files``
        and ``logs_backend_url``).
    logger : logging.Logger
        Logger instance.
    sender : MetricSender
        The existing sender (extended with ``send_log``).
    watch_files : list of str, optional
        Override the list of log files to watch.
    """

    def __init__(
        self,
        config,
        logger: logging.Logger,
        sender,
        watch_files: Optional[List[str]] = None,
    ) -> None:
        self._cfg      = config
        self._log      = logger
        self._sender   = sender
        self._observer: Optional[Observer] = None

        # Resolve which files to monitor
        self._watch_files = watch_files or getattr(
            config, "log_watch_files", []
        )

        # Directory for pygtail offset files
        self._offset_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            ".offsets",
        )

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------

    def start(self) -> None:
        """
        Start watching log files in a background thread.

        This method is **non-blocking** — it returns
        immediately while the observer runs in a daemon
        thread.
        """
        if not self._watch_files:
            self._log.warning(
                "No log files configured to watch "
                "(log_watch_files is empty) — log collector disabled"
            )
            return

        self._log.info("=" * 50)
        self._log.info("  Log Collector — Starting")
        self._log.info("=" * 50)

        # Ensure every watched file exists (create empty if not)
        existing = []
        for fpath in self._watch_files:
            abs_path = os.path.abspath(fpath)
            if not os.path.isfile(abs_path):
                self._log.warning(
                    "Watched file does not exist, creating: %s",
                    abs_path,
                )
                os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
                open(abs_path, "a").close()
            existing.append(abs_path)
            self._log.info("  Watching: %s", abs_path)

        # Build the parser
        parser = LogParser(self._log)

        # Build the watchdog handler
        handler = _LogFileHandler(
            watched_files=existing,
            parser=parser,
            sender=self._sender,
            logger=self._log,
            offset_dir=self._offset_dir,
        )

        # Determine unique directories to watch
        watch_dirs = {os.path.dirname(f) for f in existing}

        # Create and start the observer
        self._observer = Observer()
        for wd in watch_dirs:
            self._observer.schedule(handler, path=wd, recursive=False)
            self._log.info("  Observer scheduled on: %s", wd)

        self._observer.daemon = True  # stops when main thread exits
        self._observer.start()

        self._log.info("  Log Collector running (background thread)")
        self._log.info("=" * 50)

    def stop(self) -> None:
        """
        Stop the watchdog observer gracefully.
        """
        if self._observer and self._observer.is_alive():
            self._log.info("Stopping Log Collector observer...")
            self._observer.stop()
            self._observer.join(timeout=5)
            self._log.info("Log Collector stopped")

    @property
    def is_running(self) -> bool:
        """Return True if the observer thread is alive."""
        return (
            self._observer is not None
            and self._observer.is_alive()
        )
