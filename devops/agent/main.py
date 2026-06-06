"""
==========================================================
MetricGuard Agent — Main Runner  (main.py)
==========================================================

Purpose
-------
This is the **entry point** for the MetricGuard Agent.

It orchestrates every other module:

    ┌────────────────┐
    │    main.py     │
    └──┬──┬──┬──┬──┬─┘
       │  │  │  │  │
       ▼  ▼  ▼  ▼  ▼
   config logger collector sender log_collector
   (.yaml)       (psutil)  (HTTP)  (watchdog)

Startup sequence
~~~~~~~~~~~~~~~~
1. Load configuration from ``config.yaml``.
2. Reset logs and watched files.
3. Initialise the logger.
4. Print startup banner.
5. Start log collector.
6. Enter monitoring loop.

Loop behaviour
~~~~~~~~~~~~~~
* Each cycle: collect → send → sleep.
* A failed send does NOT crash the loop.
* Ctrl+C triggers clean shutdown.
* Unexpected errors are logged and ignored.

How to run
----------
    cd devops/agent/
    pip install -r requirements.txt
    python main.py

Dependencies
------------
    config.py
    logger.py
    collector.py
    sender.py
    log_collector.py
"""

from __future__ import annotations

import os
import time
import signal
import platform

from config import load_config
from logger import setup_logger
from collector import MetricCollector
from sender import MetricSender
from log_collector import LogCollector


# ==============================================================
# Global shutdown flag
# ==============================================================

_shutdown_requested = False


# ==============================================================
# Graceful shutdown handler
# ==============================================================

def _handle_signal(signum, frame):
    """
    Handle Ctrl+C / SIGTERM gracefully.
    """
    global _shutdown_requested
    _shutdown_requested = True


# ==============================================================
# Reset runtime files
# ==============================================================

def reset_runtime_files(cfg) -> None:
    """
    Reset all runtime-generated files so every run starts
    with a clean environment.

    Resets:
    - watched log files
    - agent log file
    """

    # ----------------------------------------------------------
    # Reset watched log files
    # ----------------------------------------------------------

    for log_file in cfg.log_watch_files:

        try:
            os.makedirs(
                os.path.dirname(log_file),
                exist_ok=True
            )

            with open(log_file, "w", encoding="utf-8"):
                pass

        except Exception as exc:
            print(
                f"Failed to reset watched log file "
                f"{log_file}: {exc}"
            )

    # ----------------------------------------------------------
    # Reset agent log file
    # ----------------------------------------------------------

    try:
        os.makedirs(
            os.path.dirname(cfg.log_file),
            exist_ok=True
        )

        with open(cfg.log_file, "w", encoding="utf-8"):
            pass

    except Exception as exc:
        print(
            f"Failed to reset agent log file: {exc}"
        )


# ==============================================================
# Startup banner
# ==============================================================

def _print_banner(cfg, log) -> None:
    """
    Print startup configuration information.
    """

    log.info("=" * 58)
    log.info("  MetricGuard Agent — Starting Up")
    log.info("=" * 58)

    log.info("  Agent Name       : %s", cfg.agent_name)
    log.info("  Backend URL      : %s", cfg.backend_url)
    log.info("  Collect Interval : %d s", cfg.collection_interval)
    log.info("  Max Retries      : %d", cfg.max_retries)
    log.info("  Retry Delay      : %d s (exponential)", cfg.retry_delay)
    log.info("  Request Timeout  : %d s", cfg.request_timeout)
    log.info("  Log File         : %s", cfg.log_file)
    log.info("  Log Level        : %s", cfg.log_level)
    log.info("  Disk Path        : %s", cfg.disk_path)
    log.info("  Platform         : %s", platform.platform())

    log.info("  Enabled Metrics  :")

    for name, enabled in cfg.enabled_metrics.items():
        log.info(
            "      %-16s %s",
            name,
            "ON" if enabled else "OFF"
        )

    if cfg.log_watch_files:

        log.info("  Log Watch Files  :")

        for file_path in cfg.log_watch_files:
            log.info("      %s", file_path)

    else:
        log.info("  Log Collection   : DISABLED")

    log.info("=" * 58)


# ==============================================================
# Main agent runner
# ==============================================================

def run_agent() -> None:
    """
    Main MetricGuard runtime loop.
    """

    # ----------------------------------------------------------
    # 1. Load configuration
    # ----------------------------------------------------------

    cfg = load_config()

    # ----------------------------------------------------------
    # 2. Reset runtime files
    # ----------------------------------------------------------

    reset_runtime_files(cfg)

    # ----------------------------------------------------------
    # 3. Initialise logger
    # ----------------------------------------------------------

    log = setup_logger(
        log_file=cfg.log_file,
        log_level=cfg.log_level,
    )

    # ----------------------------------------------------------
    # 4. Print startup banner
    # ----------------------------------------------------------

    _print_banner(cfg, log)

    # ----------------------------------------------------------
    # 5. Register signal handlers
    # ----------------------------------------------------------

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # ----------------------------------------------------------
    # 6. Create core modules
    # ----------------------------------------------------------

    collector = MetricCollector(
        config=cfg,
        logger=log,
    )

    sender = MetricSender(
        config=cfg,
        logger=log,
    )

    log_collector = LogCollector(
        config=cfg,
        logger=log,
        sender=sender,
    )

    # ----------------------------------------------------------
    # 7. Start log collector
    # ----------------------------------------------------------

    log_collector.start()

    cycle = 0

    # ----------------------------------------------------------
    # 8. Main monitoring loop
    # ----------------------------------------------------------

    while not _shutdown_requested:

        try:
            cycle += 1

            log.info(
                "——— Collection Cycle #%d ———",
                cycle
            )

            # --------------------------------------------------
            # Collect metrics
            # --------------------------------------------------

            metrics = collector.collect()

            # --------------------------------------------------
            # Send metrics
            # --------------------------------------------------

            success = sender.send(metrics)

            if success:

                log.info(
                    "Cycle #%d completed successfully",
                    cycle
                )

            else:

                log.warning(
                    "Cycle #%d completed with errors "
                    "(metrics not delivered)",
                    cycle
                )

        except KeyboardInterrupt:

            log.info(
                "Shutdown requested "
                "(KeyboardInterrupt)"
            )

            break

        except Exception as exc:

            log.critical(
                "Unexpected error in cycle #%d: %s",
                cycle,
                exc,
                exc_info=True,
            )

        # ------------------------------------------------------
        # Sleep before next cycle
        # ------------------------------------------------------

        if _shutdown_requested:
            break

        try:

            log.info(
                "Sleeping %d seconds until next cycle...",
                cfg.collection_interval,
            )

            time.sleep(cfg.collection_interval)

        except KeyboardInterrupt:

            log.info(
                "Shutdown requested during sleep"
            )

            break

    # ----------------------------------------------------------
    # 9. Clean shutdown
    # ----------------------------------------------------------

    log_collector.stop()

    log.info("=" * 58)
    log.info(
        "  MetricGuard Agent — Stopped (%d cycles)",
        cycle
    )
    log.info("=" * 58)


# ==============================================================
# Entry point
# ==============================================================

if __name__ == "__main__":
    run_agent()