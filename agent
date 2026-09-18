"""
Azure Monitoring Assistant - a small, read-only AI agent.

The agent reads Azure Monitor style alerts (sample data), decides which tools
to call, and produces an incident-style summary with likely causes and next steps.

Usage:
    python agent.py
    python agent.py "Which prod alerts are Sev1 and what is the likely root cause?"
"""

import json
import sys
from pathlib import Path

import anthropic

MODEL = "claude-sonnet-5"
MAX_STEPS = 8  # safety limit on the tool loop
ALERTS_FILE = Path(__file__).parent / "sample_alerts.json"

SYSTEM_PROMPT = """You are an Azure platform operations assistant.
You investigate monitoring alerts using ONLY the tools provided.
Rules:
- You are read-only. Never claim to have changed, restarted, or fixed anything.
- Base every statement on tool results. If data is missing, say so.
- Look for relationships between alerts (for example a failing backend
  causing an unhealthy Front Door origin).
- Finish with: 1) Summary, 2) Likely root cause, 3) Recommended next steps,
  ordered by priority. Keep it concise."""

TOOLS = [
    {
        "name": "list_alerts",
        "description": (
            "List monitoring alerts. Optionally filter by severity "
            "(Sev1 is most critical, Sev4 least), status (Fired or Resolved), "
            "and environment (prod, dev, test)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "severity": {"type": "string", "enum": ["Sev1", "Sev2", "Sev3", "Sev4"]},
                "status": {"type": "string", "enum": ["Fired", "Resolved"]},
                "environment": {"type": "string", "enum": ["prod", "dev", "test"]},
            },
        },
    },
    {
        "name": "get_alert_details",
        "description": "Get the full details of one alert by its id, for example ALR-1001.",
        "input_schema": {
            "type": "object",
            "properties": {"alert_id": {"type": "string"}},
            "required": ["alert_id"],
        },
    },
]


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
    # Return a compact view; details come from get_alert_details
    return [
        {k: a[k] for k in ("id", "name", "severity", "status", "resource", "environment")}
        for a in alerts
    ]


def get_alert_details(alert_id):
    for a in load_alerts():
        if a["id"].lower() == alert_id.lower():
            return a
    return {"error": f"Alert {alert_id} not found"}


TOOL_FUNCTIONS = {
    "list_alerts": list_alerts,
    "get_alert_details": get_alert_details,
}


def run_tool(name, tool_input):
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return json.dumps({"error": f"Unknown tool {name}"})
    try:
        return json.dumps(func(**tool_input))
    except Exception as exc:  # return errors to the model instead of crashing
        return json.dumps({"error": str(exc)})


def main():
    question = (
        " ".join(sys.argv[1:])
        or "Summarize all active production alerts, find the likely root cause, and suggest next steps."
    )
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    messages = [{"role": "user", "content": question}]

    for step in range(1, MAX_STEPS + 1):
        response = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            print("\n".join(b.text for b in response.content if b.type == "text"))
            return

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"[step {step}] tool: {block.name} {json.dumps(block.input)}", file=sys.stderr)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": run_tool(block.name, block.input),
                    }
                )
        messages.append({"role": "user", "content": tool_results})

    print(f"Stopped after {MAX_STEPS} steps without a final answer.")


if __name__ == "__main__":
    main()
