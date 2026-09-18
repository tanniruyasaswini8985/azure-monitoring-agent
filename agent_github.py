"""
Azure Monitoring Assistant - free version using GitHub Models.

Works inside GitHub Codespaces with no API key to paste (GITHUB_TOKEN is
already set). Outside Codespaces, create a fine-grained personal access token
with the "Models: read" permission and export it as GITHUB_TOKEN.

Usage:
    python agent_github.py                      # AI agent via GitHub Models
    python agent_github.py "your question"      # custom question
    python agent_github.py --demo               # no AI, no token, rule-based summary
"""

import json
import os
import sys

from tools import list_alerts, run_tool

BASE_URL = "https://models.github.ai/inference"
MODEL = "openai/gpt-4.1"  # check github.com/marketplace/models if this changes
MAX_STEPS = 8

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
        "type": "function",
        "function": {
            "name": "list_alerts",
            "description": (
                "List monitoring alerts. Optionally filter by severity "
                "(Sev1 most critical, Sev4 least), status (Fired or Resolved), "
                "and environment (prod, dev, test)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["Sev1", "Sev2", "Sev3", "Sev4"]},
                    "status": {"type": "string", "enum": ["Fired", "Resolved"]},
                    "environment": {"type": "string", "enum": ["prod", "dev", "test"]},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_alert_details",
            "description": "Get full details of one alert by id, for example ALR-1001.",
            "parameters": {
                "type": "object",
                "properties": {"alert_id": {"type": "string"}},
                "required": ["alert_id"],
            },
        },
    },
]


def run_agent(question):
    from openai import OpenAI

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is not set. In Codespaces it is automatic; elsewhere create a "
                 "fine-grained token with 'Models: read' and export GITHUB_TOKEN. "
                 "Or run: python agent_github.py --demo")

    client = OpenAI(base_url=BASE_URL, api_key=token)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    for step in range(1, MAX_STEPS + 1):
        response = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOLS, max_tokens=1200
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            print(msg.content)
            return

        messages.append(msg)
        for call in msg.tool_calls:
            args = json.loads(call.function.arguments or "{}")
            print(f"[step {step}] tool: {call.function.name} {json.dumps(args)}", file=sys.stderr)
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": run_tool(call.function.name, args)}
            )

    print(f"Stopped after {MAX_STEPS} steps without a final answer.")


def run_demo():
    """Rule-based summary. No AI, no token, no cost."""
    active = list_alerts(status="Fired", environment="prod")
    order = {"Sev1": 1, "Sev2": 2, "Sev3": 3, "Sev4": 4}
    active.sort(key=lambda a: order[a["severity"]])

    print("Summary")
    print(f"- {len(active)} active production alerts")
    for a in active:
        print(f"  - [{a['severity']}] {a['name']} ({a['resource']})")

    names = " ".join(a["name"].lower() for a in active)
    print("\nLikely root cause")
    if "front door" in names and "apim" in names:
        print("- Front Door origin health and APIM 5xx errors fired together, so the APIM "
              "gateway (or its backend) is the most likely source. Front Door is probably a symptom.")
    else:
        print("- No obvious correlation found by the demo rules.")

    print("\nRecommended next steps")
    print("1. Investigate the highest-severity alert first (Sev1).")
    print("2. Check APIM backend health and recent deployments.")
    print("3. Review Azure OpenAI 429 throttling and quota if AI traffic is affected.")
    print("\n(Demo mode: fixed rules, not AI. Run without --demo for the AI agent.)")


def main():
    args = sys.argv[1:]
    if "--demo" in args:
        run_demo()
        return
    question = " ".join(args) or (
        "Summarize all active production alerts, find the likely root cause, and suggest next steps."
    )
    run_agent(question)


if __name__ == "__main__":
    main()
