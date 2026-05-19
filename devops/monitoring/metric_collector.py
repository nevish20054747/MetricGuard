"""
==========================================================
MetricGuard - Metric Collector
==========================================================

Purpose:
    The heart of the monitoring system. This script:
    1. Collects live system metrics every 5 seconds using psutil.
    2. Packages the metrics as a JSON payload.
    3. Sends (POSTs) the payload to the backend API.
    4. Retries on failure with exponential backoff.
    5. Logs every step for full observability.
    6. Never crashes — all exceptions are caught.

Metrics collected:
    - CPU Usage (%)
    - RAM Usage (%)
    - Disk Usage (%)
    - Disk Read Speed (formatted KB/MB/GB)
    - Disk Write Speed (formatted KB/MB/GB)
    - Network Upload Speed (formatted KB/MB/GB)
    - Network Download Speed (formatted KB/MB/GB)
    - Process Count
    - System Load Average
    - System Uptime (seconds)

How to run:
    cd monitoring/
    pip install -r requirements.txt
    python metric_collector.py

Dependencies:
    - psutil          (system metrics)
    - requests        (HTTP POST to backend)
    - config.py       (configuration values)
    - logger.py       (centralized logging)
"""

import sys
import time
import platform
import json
import psutil
import requests

from config import Config
from logger import logger
from typing import Optional


# ======================================================
# METRIC COLLECTION FUNCTIONS
# ======================================================
# Each function collects one metric and handles its own
# errors so a single failure doesn't break the whole
# collection cycle.

# Initialize disk counters properly
disk_counters = psutil.disk_io_counters()

previous_disk_read = disk_counters.read_bytes
previous_disk_write = disk_counters.write_bytes

# Initialize network counters properly
net_counters = psutil.net_io_counters()

previous_net_sent = net_counters.bytes_sent
previous_net_recv = net_counters.bytes_recv


def get_cpu_usage() -> Optional[float]:
    """
    Get current CPU usage as a percentage.
    interval=1 means it measures over 1 second.

    Returns:
        float: CPU usage percentage (0.0 - 100.0)
    """
    try:
        usage = psutil.cpu_percent(interval=1)
        logger.debug("CPU usage: %.1f%%", usage)
        return round(usage,2)
    except Exception as e:
        logger.error("Failed to collect CPU usage: %s", e)
        return None


def get_ram_usage() -> Optional[float]:
    """
    Get current RAM usage as a percentage.

    Returns:
        float: RAM usage percentage (0.0 - 100.0)
    """
    try:
        usage = psutil.virtual_memory().percent
        logger.debug("RAM usage: %.1f%%", usage)
        return round(usage,2)
    except Exception as e:
        logger.error("Failed to collect RAM usage: %s", e)
        return None


def get_disk_usage() -> Optional[float]:
    """
    Get disk usage for the configured disk path.
    Default path is '/' (Linux) or 'C:\\' (Windows).

    Returns:
        float: Disk usage percentage (0.0 - 100.0)
    """
    try:
        usage = psutil.disk_usage(Config.DISK_PATH).percent
        logger.debug("Disk usage: %.1f%%", usage)
        return round(usage,2)
    except Exception as e:
        logger.error("Failed to collect Disk usage: %s", e)
        return None


def get_disk_io() -> tuple:

    global previous_disk_read
    global previous_disk_write

    try:
        counters = psutil.disk_io_counters()

        current_read = counters.read_bytes
        current_write = counters.write_bytes

        read_speed = current_read - previous_disk_read
        write_speed = current_write - previous_disk_write

        previous_disk_read = current_read
        previous_disk_write = current_write

        return (read_speed, write_speed)

    except Exception as e:
        logger.error("Failed to collect Disk I/O: %s", e)
        return (None, None)


def get_network_io() -> tuple:

    global previous_net_sent
    global previous_net_recv

    try:
        counters = psutil.net_io_counters()

        current_sent = counters.bytes_sent
        current_recv = counters.bytes_recv

        upload_speed = current_sent - previous_net_sent
        download_speed = current_recv - previous_net_recv

        previous_net_sent = current_sent
        previous_net_recv = current_recv

        return (upload_speed, download_speed)

    except Exception as e:
        logger.error("Failed to collect Network I/O: %s", e)
        return (None, None)


def get_process_count() -> Optional[int]:
    """
    Get the number of currently running processes.

    Returns:
        int: Number of active processes
    """
    try:
        count = len(psutil.pids())
        logger.debug("Process count: %d", count)
        return count
    except Exception as e:
        logger.error("Failed to collect process count: %s", e)
        return None


def get_system_load() -> Optional[float]:
    """
    Get system load average.

    On Windows:
        Returns None because load average is not reliable.

    On Linux/macOS:
        Returns 1-minute load average.
    """

    try:
        if platform.system() != "Windows":
            load_avg = psutil.getloadavg()[0]
            logger.debug("System load: %.2f", load_avg)
            return round(load_avg, 2)

        logger.debug("System load not supported on Windows")
        return None

    except Exception as e:
        logger.error("Failed to collect system load: %s", e)
        return None


def get_system_uptime() -> Optional[str]:
    """
    Get system uptime in readable format.
    """

    try:
        uptime_seconds = time.time() - psutil.boot_time()

        hours = int(uptime_seconds // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        seconds = int(uptime_seconds % 60)

        readable_uptime = f"{hours}h {minutes}m {seconds}s"

        logger.debug("System uptime: %s", readable_uptime)

        return readable_uptime

    except Exception as e:
        logger.error("Failed to collect system uptime: %s", e)
        return None
    
def format_bytes(bytes_value:Optional[int]) -> Optional[str]:
    """
    Convert bytes into readable KB/MB/GB format.
    """

    if bytes_value is None:
        return None

    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_value < 1024:
            return f"{bytes_value:.2f} {unit}"

        bytes_value /= 1024

    return f"{bytes_value:.2f} TB"

# ======================================================
# METRIC ASSEMBLY
# ======================================================

def collect_all_metrics():
    """
    Collect ALL system metrics and return them as a dict.

    This function calls every individual collector and
    assembles the results into a single JSON-serializable
    dictionary with a timestamp.

    Returns:
        dict: All collected metrics with a timestamp
    """
    logger.info("Collecting system metrics...")

    # Collect disk and network I/O (returns tuples)
    disk_read, disk_write = get_disk_io()
    net_sent, net_recv = get_network_io()

    # Build the payload
    metrics = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "cpu_usage": get_cpu_usage(),
        "ram_usage": get_ram_usage(),
        "disk_usage": get_disk_usage(),
        "disk_read_speed": format_bytes(disk_read),
        "disk_write_speed": format_bytes(disk_write),
        "network_upload_speed": format_bytes(net_sent),
        "network_download_speed": format_bytes(net_recv),
        "process_count": get_process_count(),
        "system_load": get_system_load(),
        "system_uptime": get_system_uptime(),
    }

    logger.info("Metrics collected successfully")
    logger.debug("Metrics payload: %s", json.dumps(metrics, indent=2))
    
    try:
        metrics_file = "metrics.json"

        # Load existing metrics
        try:
            with open(metrics_file, "r") as file:
                existing_metrics = json.load(file)

        except (FileNotFoundError, json.JSONDecodeError):
            existing_metrics = []

        # Add new metric
        existing_metrics.append(metrics)

        # Save back properly
        with open(metrics_file, "w") as file:
            json.dump(existing_metrics, file, indent=4)

        logger.info("Metrics saved locally")

    except Exception as e:
        logger.error("Failed to save metrics locally: %s", e)

    return metrics


# ======================================================
# BACKEND COMMUNICATION (with retry logic)
# ======================================================

def send_metrics(metrics):
    """
    Send collected metrics to the backend API via HTTP POST.

    Features:
        - Retries up to MAX_RETRIES times on failure.
        - Exponential backoff between retries (2s, 4s, 8s...).
        - Timeout protection on each request.
        - Never crashes — logs errors and moves on.

    Args:
        metrics (dict): The metrics payload to send.

    Returns:
        bool: True if the request succeeded, False otherwise.
    """
    url = Config.BACKEND_URL

    for attempt in range(1, Config.MAX_RETRIES + 1):
        try:
            logger.info(
                "Sending metrics to %s (attempt %d/%d)",
                url, attempt, Config.MAX_RETRIES
            )

            # POST the metrics as JSON with a timeout
            response = requests.post(
                url,
                json=metrics,
                timeout=Config.REQUEST_TIMEOUT,
                headers={"Content-Type": "application/json"}
            )

            # Check if the request was successful (2xx status)
            if response.ok:
                logger.info(
                    "Metrics sent successfully (status %d)",
                    response.status_code
                )
                return True
            else:
                logger.warning(
                    "Backend returned status %d: %s",
                    response.status_code, response.text
                )

        except requests.exceptions.ConnectionError:
            logger.error(
                "Connection failed (attempt %d/%d): "
                "Backend at %s is unreachable",
                attempt, Config.MAX_RETRIES, url
            )

        except requests.exceptions.Timeout:
            logger.error(
                "Request timed out (attempt %d/%d) after %ds",
                attempt, Config.MAX_RETRIES, Config.REQUEST_TIMEOUT
            )

        except requests.exceptions.RequestException as e:
            logger.error(
                "Request error (attempt %d/%d): %s",
                attempt, Config.MAX_RETRIES, e
            )

        # --- Retry delay with exponential backoff ---
        if attempt < Config.MAX_RETRIES:
            delay = Config.RETRY_DELAY * (2 ** (attempt - 1))
            logger.info("Retrying in %d seconds...", delay)
            time.sleep(delay)

    # All retries exhausted
    logger.error(
        "All %d attempts failed. Metrics will be lost for this cycle.",
        Config.MAX_RETRIES
    )
    return False


# ======================================================
# MAIN MONITORING LOOP
# ======================================================

def run_collector():
    """
    Main loop that runs forever:
        1. Collect metrics
        2. Send to backend
        3. Wait COLLECTION_INTERVAL seconds
        4. Repeat

    This function NEVER crashes. Any unexpected error is
    caught, logged, and the loop continues.
    """

    # ==================================================
    # CLEAR OLD FILES AT STARTUP
    # ==================================================

    try:
        # Reset metrics.json with empty JSON array
        with open("metrics.json", "w") as file:
            json.dump([], file)

    except Exception as e:
        print(f"Failed to clear metrics.json: {e}")

    try:
        # Clear old system.log
        with open(Config.LOG_FILE, "w") as file:
            pass

    except Exception as e:
        print(f"Failed to clear log file: {e}")

    # ==================================================
    # STARTUP LOGS
    # ==================================================

    logger.info("=" * 55)
    logger.info("MetricGuard Monitoring Collector - Starting Up")
    logger.info("=" * 55)

    logger.info("Old metrics.json cleared")
    logger.info("Old system.log cleared")

    logger.info("Backend URL    : %s", Config.BACKEND_URL)
    logger.info("Interval       : %d seconds", Config.COLLECTION_INTERVAL)
    logger.info("Max Retries    : %d", Config.MAX_RETRIES)
    logger.info("Log File       : %s", Config.LOG_FILE)
    logger.info("Platform       : %s", platform.platform())

    logger.info("=" * 55)

    cycle_count = 0

    # ==================================================
    # MAIN COLLECTION LOOP
    # ==================================================

    while True:
        try:
            cycle_count += 1

            logger.info(
                "--- Collection Cycle #%d ---",
                cycle_count
            )

            # Step 1: Collect all metrics
            metrics = collect_all_metrics()

            # Step 2: Send metrics to backend
            success = send_metrics(metrics)

            if success:
                logger.info(
                    "Cycle #%d completed successfully",
                    cycle_count
                )

            else:
                logger.warning(
                    "Cycle #%d completed with errors "
                    "(metrics not delivered)",
                    cycle_count
                )

        except KeyboardInterrupt:
            logger.info(
                "Shutdown requested (KeyboardInterrupt)"
            )

            logger.info(
                "MetricGuard Collector stopped."
            )

            sys.exit(0)

        except Exception as e:
            logger.critical(
                "Unexpected error in cycle #%d: %s",
                cycle_count,
                e,
                exc_info=True
            )

        # ==============================================
        # WAIT BEFORE NEXT COLLECTION
        # ==============================================

        try:
            logger.info(
                "Sleeping %d seconds until next cycle...",
                Config.COLLECTION_INTERVAL
            )

            time.sleep(Config.COLLECTION_INTERVAL)

        except KeyboardInterrupt:
            logger.info(
                "Shutdown requested during sleep"
            )

            logger.info(
                "MetricGuard Collector stopped."
            )

            sys.exit(0)


# ======================================================
# ENTRY POINT
# ======================================================

if __name__ == "__main__":
    """
    Run the collector when the script is executed directly:
        python metric_collector.py
    """
    run_collector()
