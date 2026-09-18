"""Read-only alert tools shared by the agents. Uses fictional sample data."""

import json
from pathlib import Path

ALERTS_FILE = Path(__file__).parent / "sample_alerts.json"


def load_alerts():
    with open(ALERTS_FILE, encoding="utf-8") as f:
        return json.load(f)


def list_alerts(severity=None, status=None, environment=None):
    alerts = load_alerts()
    if severity:
        alerts = [a for a in alerts if a["severity"] == severity]
    if status:
        alerts = [a for a in alerts if a["status"] == status]
    if environment:
        alerts = [a for a in alerts if a["environment"] == environment]
    return [
        {k: a[k] for k in ("id", "name", "severity", "status", "resource", "environment")}
        for a in alerts
    ]


def get_alert_details(alert_id):
    for a in load_alerts():
        if a["id"].lower() == alert_id.lower():
            return a
    return {"error": f"Alert {alert_id} not found"}


TOOL_FUNCTIONS = {"list_alerts": list_alerts, "get_alert_details": get_alert_details}


def run_tool(name, tool_input):
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return json.dumps({"error": f"Unknown tool {name}"})
    try:
        return json.dumps(func(**tool_input))
    except Exception as exc:  # return errors to the model instead of crashing
        return json.dumps({"error": str(exc)})
