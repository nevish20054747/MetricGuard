import os
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.services.incident_service import get_incident_service
from backend.recommendation_engine.recommendation_service import get_recommendation_service
from backend.service_impact.service_health import get_service_health_engine
from backend.report_generator.report_storage import get_report_storage
from backend.report_generator.pdf_exporter import generate_pdf
from backend.report_generator.csv_exporter import generate_csv
from backend.models.correlation import Correlation
from backend.alerting.models import Alert

logger = logging.getLogger("metricguard.report_generator")


class ReportGenerator:
    """
    Service responsible for orchestrating incident report generation,
    aggregating data from multiple subsystems, and executing PDF/CSV exporters.
    """

    def generate_incident_report(self, db: Session, incident_id: str, formats: List[str]) -> Dict[str, Any]:
        """
        Aggregate incident data, create metadata record, and export desired file formats.
        """
        logger.info("[REPORT_GENERATOR] Generating report for incident %s", incident_id)

        # 1. Fetch the incident
        inc_service = get_incident_service()
        incident = inc_service.get_incident(db, incident_id)
        if not incident:
            logger.error("[REPORT_GENERATOR] Incident %s not found", incident_id)
            raise ValueError(f"Incident with ID '{incident_id}' does not exist.")

        # 2. Retrieve RCA Details
        correlation = db.query(Correlation).filter(
            Correlation.inferred_cause == incident.root_cause
        ).order_by(Correlation.created_at.desc()).first()

        if not correlation:
            # Fallback check on service name matching
            services_lower = [s.strip().lower() for s in incident.impacted_services.split(",") if s.strip()]
            if services_lower:
                correlation = db.query(Correlation).filter(
                    Correlation.service_name.in_(services_lower)
                ).order_by(Correlation.created_at.desc()).first()

        rca_confidence = correlation.confidence if correlation else 85.0
        rca_score = correlation.correlation_score if correlation else 0.85

        # 3. Retrieve affected/impacted services
        affected_services_list = [s.strip().title() for s in incident.impacted_services.split(",") if s.strip()]

        # 4. Generate recommendations
        rec_service = get_recommendation_service()
        recommendations = rec_service.get_recommendations(
            root_cause=incident.root_cause,
            severity=incident.severity,
            impacted_services=[s.strip() for s in incident.impacted_services.split(",") if s.strip()],
            confidence=rca_score,
        )

        # 5. Extract correlated alerts within timeline (30 minutes of incident creation)
        time_diff = timedelta(minutes=30)
        alerts = db.query(Alert).filter(
            Alert.timestamp >= incident.created_at - time_diff,
            Alert.timestamp <= incident.created_at + time_diff
        ).all()

        matching_alerts = []
        incident_services_lower = [s.strip().lower() for s in incident.impacted_services.split(",") if s.strip()]
        for alert in alerts:
            alert_services_lower = [s.strip().lower() for s in alert.affected_services.split(",") if s.strip()]
            same_cause = alert.title.strip().lower() == incident.root_cause.strip().lower()
            services_overlap = any(s in incident_services_lower for s in alert_services_lower)
            if same_cause or services_overlap:
                matching_alerts.append(alert)

        # 6. Service health status
        health_engine = get_service_health_engine()
        health_details = health_engine.compute_all_health()
        
        status_severity = {"critical": 4, "degraded": 3, "warning": 2, "healthy": 1}
        worst_status = "healthy"
        for svc_health in health_details:
            status = svc_health.get("status", "healthy")
            if status_severity.get(status, 1) > status_severity.get(worst_status, 1):
                worst_status = status

        # 7. Generate a unique report ID
        storage = get_report_storage()
        report_id = storage.generate_report_id()

        # 8. Assemble unified data payload
        report_payload = {
            "report_id": report_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "incident": {
                "incident_id": incident.incident_id,
                "root_cause": incident.root_cause,
                "severity": incident.severity,
                "priority": incident.priority,
                "status": incident.status,
                "alert_count": incident.alert_count,
                "created_at": incident.created_at.isoformat() + "Z",
                "updated_at": incident.updated_at.isoformat() + "Z" if incident.updated_at else None,
            },
            "root_cause": {
                "cause": incident.root_cause,
                "confidence": rca_confidence,
                "score": rca_score,
            },
            "affected_services": affected_services_list,
            "recommendations": [r["action"] for r in recommendations],
            "recommendations_detail": recommendations,
            "alerts": [
                {
                    "alert_id": a.alert_id,
                    "severity": a.severity,
                    "title": a.title,
                    "message": a.message,
                    "status": a.status,
                    "timestamp": a.timestamp.isoformat() + "Z",
                }
                for a in matching_alerts
            ],
            "service_health": {
                "overall_status": worst_status,
                "details": health_details,
            }
        }

        # 9. Trigger file exporters
        generated_files = []
        pdf_path = ""
        csv_path = ""

        formats_lower = [f.strip().lower() for f in formats]
        if "pdf" in formats_lower:
            pdf_res = generate_pdf(report_payload)
            pdf_path = pdf_res["file_path"]
            generated_files.append(os.path.basename(pdf_path))

        if "csv" in formats_lower:
            csv_res = generate_csv(report_payload)
            csv_path = csv_res["file_path"]
            generated_files.append(os.path.basename(csv_path))

        # 10. Persist metadata
        metadata = {
            "report_id": report_id,
            "incident_id": incident_id,
            "created_at": report_payload["created_at"],
            "available_formats": formats_lower,
            "pdf_path": pdf_path,
            "csv_path": csv_path,
        }
        storage.save_metadata(metadata)

        logger.info("[REPORT_GENERATOR] Report %s successfully created with formats %s", report_id, formats_lower)
        return {
            "status": "success",
            "report_id": report_id,
            "files": generated_files,
        }


# Global Singleton accessor
_generator_instance = None

def get_report_generator() -> ReportGenerator:
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = ReportGenerator()
    return _generator_instance
