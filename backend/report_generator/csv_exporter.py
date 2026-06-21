import os
import csv
import logging
from typing import Dict, Any

logger = logging.getLogger("metricguard.csv_exporter")

# Resolve root directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GENERATED_DIR = os.path.join(BASE_DIR, "reports", "generated")


def generate_csv(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a CSV export version of the incident report.

    Fields included:
      - incident_id
      - severity
      - root_cause
      - affected_services (semicolon separated)
      - recommendations (semicolon separated)
      - overall_status
    """
    report_id = report_data.get("report_id", "UNKNOWN")
    logger.info("[CSV_EXPORTER] Exporting CSV for %s.csv", report_id)

    # Resolve output filepath
    file_path = os.path.join(GENERATED_DIR, f"{report_id}.csv")
    os.makedirs(GENERATED_DIR, exist_ok=True)

    # Extract fields from the report_data payload
    incident_section = report_data.get("incident", {})
    incident_id = incident_section.get("incident_id", "N/A")
    severity = incident_section.get("severity", "N/A")

    rca_section = report_data.get("root_cause", {})
    root_cause = rca_section.get("cause", "N/A")

    affected_services_list = report_data.get("affected_services", [])
    affected_services = "; ".join(affected_services_list)

    recommendations_list = report_data.get("recommendations", [])
    recommendations = "; ".join(recommendations_list)

    health_section = report_data.get("service_health", {})
    overall_status = health_section.get("overall_status", "N/A")

    headers = [
        "incident_id",
        "severity",
        "root_cause",
        "affected_services",
        "recommendations",
        "overall_status"
    ]

    row = {
        "incident_id": incident_id,
        "severity": severity,
        "root_cause": root_cause,
        "affected_services": affected_services,
        "recommendations": recommendations,
        "overall_status": overall_status
    }

    try:
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerow(row)
        
        logger.info("[CSV_EXPORTER] Exported CSV %s.csv successfully", report_id)
        return {
            "file_path": file_path,
            "format": "csv"
        }
    except Exception as e:
        logger.error("[CSV_EXPORTER] Failed to write CSV file %s: %s", file_path, e)
        raise IOError(f"Failed to generate CSV export: {str(e)}")
