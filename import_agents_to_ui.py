#!/usr/bin/env python3
"""Import agents from policy analysis output into agents.json."""

import argparse
import csv
import json
import os
import random
import re
import sys
from collections import defaultdict
from pathlib import Path


def load_dotenv():
    """Load environment variables from policyanalyzer .env file."""
    env_file = Path(__file__).parent.parent / "policyanalyzer" / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


load_dotenv()

from google import genai
from google.genai import types


def parse_csv(csv_path: Path) -> dict[str, list[dict]]:
    """Parse policy_analysis_summary.csv and group rows by Agent Name."""
    agents: dict[str, list[dict]] = defaultdict(list)
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Agent Name", "").strip().strip('"')
            if name:
                agents[name].append({
                    "function": row.get("Agent Function", "").strip().strip('"'),
                    "policy": row.get("Policy", "").strip().strip('"'),
                    "applicable": row.get("Applicable Y/N", "").strip().strip('"'),
                    "compliant": row.get("Compliant?", "").strip().strip('"'),
                    "filename": row.get("File Name", "").strip().strip('"'),
                })
    return dict(agents)


def read_analysis_file(output_dir: Path, filename: str) -> str:
    """Read an analysis .txt file, return empty string if not found."""
    filepath = output_dir / filename
    if filepath.exists():
        return filepath.read_text(encoding="utf-8", errors="replace")
    return ""


def call_gemini(agent_name: str, agent_function: str, analyses: list[str], model: str) -> dict:
    """Call Gemini to derive platform, complianceRisk, securityRisk."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    # Truncate analyses to avoid hitting token limits
    combined = "\n\n---\n\n".join(analyses)
    if len(combined) > 100000:
        combined = combined[:100000] + "\n...[truncated]"

    prompt = f"""You are analyzing an AI agent to determine its development platform and risk scores.

Agent Name: {agent_name}
Agent Function: {agent_function}

Below are compliance analysis reports for this agent against various regulations:

{combined}

Based on the above, respond with ONLY a JSON object (no markdown, no explanation):
{{
  "platform": "<most likely development platform, e.g. 'Microsoft Copilot Studio', 'Salesforce AgentForce', 'Lindy', 'ServiceNow Now Assist', 'AWS Bedrock Agents', 'Google Vertex AI Agents', or other>",
  "complianceRisk": <1-5 integer, where 1=very low risk and 5=very high risk, based on the number and severity of compliance issues found>,
  "securityRisk": <1-5 integer, where 1=very low risk and 5=very high risk, based on data sensitivity and security concerns identified>
}}"""

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.3,
        ),
    )
    text = response.text.strip()
    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        result = json.loads(text)
        return {
            "platform": str(result.get("platform", "Unknown")),
            "complianceRisk": max(1, min(5, int(result.get("complianceRisk", 3)))),
            "securityRisk": max(1, min(5, int(result.get("securityRisk", 1)))),
        }
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        print(f"  Warning: Failed to parse Gemini response for {agent_name}: {e}", file=sys.stderr)
        print(f"  Response was: {text[:200]}", file=sys.stderr)
        return {"platform": "Unknown", "complianceRisk": 3, "securityRisk": 1}


def call_gemini_policy_details(
    agent_name: str, policy_name: str, analysis_text: str, model: str
) -> dict:
    """Call Gemini to derive suggestedReason, statusReason, and nextStep for a policy."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    if len(analysis_text) > 50000:
        analysis_text = analysis_text[:50000] + "\n...[truncated]"

    prompt = f"""You are analyzing a compliance report for an AI agent against a specific policy.

Agent Name: {agent_name}
Policy: {policy_name}

Below is the full compliance analysis report:

{analysis_text}

Based on the above, respond with ONLY a JSON object (no markdown, no explanation):
{{
  "suggestedReason": "<1-2 sentence explanation of why this policy is suggested/applicable for this agent>",
  "statusReason": "<1-2 sentence explanation of the current compliance status, summarizing key findings>",
  "nextStep": "<1 sentence actionable next step to improve or maintain compliance>"
}}"""

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.3,
        ),
    )
    text = response.text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        result = json.loads(text)
        return {
            "suggestedReason": str(result.get("suggestedReason", "")),
            "statusReason": str(result.get("statusReason", "")),
            "nextStep": str(result.get("nextStep", "")),
        }
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        print(f"  Warning: Failed to parse policy details for {agent_name}/{policy_name}: {e}", file=sys.stderr)
        return {"suggestedReason": "", "statusReason": "", "nextStep": ""}


def generate_id() -> str:
    """Generate a random 7-digit ID string."""
    return str(random.randint(1000000, 9999999))


def build_agent(
    name: str,
    rows: list[dict],
    gemini_result: dict,
    existing_id: str | None,
    policy_details: dict[str, dict] | None = None,
) -> dict:
    """Build an Agent object from CSV rows and Gemini-derived fields."""
    agent_function = rows[0]["function"]

    # Collect all policies and determine suggested/enabled/status per policy
    all_policies = sorted(set(r["policy"] for r in rows if r["policy"]))
    applicable_set = set(
        r["policy"] for r in rows if r["policy"] and r["applicable"].upper() == "Y"
    )

    # Build a compliance lookup from applicable rows
    compliance_lookup: dict[str, str] = {}
    for r in rows:
        pname = r["policy"]
        if pname and pname in applicable_set and pname not in compliance_lookup:
            compliance_lookup[pname] = (
                "compliant" if r["compliant"] == "Compliant" else "remediating"
            )

    # status: Compliant only if ALL applicable policies are Compliant
    applicable_rows = [r for r in rows if r["applicable"].upper() == "Y"]
    has_non_compliant = any(
        r["compliant"] in ("Non-Compliant", "Partially Compliant")
        for r in applicable_rows
    )
    status = "Remediating" if has_non_compliant else "Compliant"

    # policies array: all policies with suggested/enabled flags
    policy_details = policy_details or {}
    policy_entries = []
    for pname in all_policies:
        is_applicable = pname in applicable_set
        details = policy_details.get(pname, {})
        policy_entries.append({
            "name": pname,
            "status": compliance_lookup.get(pname, "compliant"),
            "suggested": True,
            "enabled": is_applicable,
            "suggestedReason": details.get("suggestedReason", ""),
            "statusReason": details.get("statusReason", ""),
            "nextStep": details.get("nextStep", ""),
        })

    return {
        "id": existing_id or generate_id(),
        "name": name,
        "platform": gemini_result["platform"],
        "function": agent_function,
        "blocked": 0,
        "warned": 0,
        "complianceRisk": gemini_result["complianceRisk"],
        "securityRisk": gemini_result["securityRisk"],
        "status": status,
        "policies": policy_entries,
        "synthetic": False,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Import agents from policy analysis output into agents.json",
    )
    parser.add_argument(
        "output_dir",
        help="Path to the policy analysis output directory containing policy_analysis_summary.csv",
    )
    parser.add_argument(
        "--agents-json",
        default=str(Path(__file__).parent.parent / "long-tail-experiment" / "src" / "data" / "agents.json"),
        help="Path to agents.json (default: ../long-tail-experiment/src/data/agents.json)",
    )
    parser.add_argument(
        "--model",
        default="gemini-2.0-flash",
        help="Gemini model to use (default: gemini-2.0-flash)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to agents.json",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    csv_path = output_dir / "policy_analysis_summary.csv"
    if not csv_path.exists():
        print(f"Error: {csv_path} not found", file=sys.stderr)
        return 1

    agents_json_path = Path(args.agents_json)

    # Load existing agents
    existing_agents: list[dict] = []
    if agents_json_path.exists():
        existing_agents = json.loads(agents_json_path.read_text(encoding="utf-8"))
    existing_by_name = {a["name"]: a for a in existing_agents}

    # Parse CSV
    grouped = parse_csv(csv_path)
    print(f"Found {len(grouped)} agents in CSV")

    # Process each agent
    new_agents = []
    updated_count = 0
    for name, rows in sorted(grouped.items()):
        print(f"Processing: {name} ({len(rows)} policies)")

        # Read analysis files
        analyses = []
        for r in rows:
            if r["filename"]:
                content = read_analysis_file(output_dir, r["filename"])
                if content:
                    analyses.append(content)

        # Call Gemini
        gemini_result = call_gemini(name, rows[0]["function"], analyses, args.model)
        print(f"  Platform: {gemini_result['platform']}, "
              f"Compliance Risk: {gemini_result['complianceRisk']}, "
              f"Security Risk: {gemini_result['securityRisk']}")

        # Get per-policy details from LLM
        policy_details: dict[str, dict] = {}
        for r in rows:
            pname = r["policy"]
            if pname and r["filename"]:
                content = read_analysis_file(output_dir, r["filename"])
                if content:
                    print(f"  Getting details for policy: {pname}")
                    policy_details[pname] = call_gemini_policy_details(
                        name, pname, content, args.model
                    )

        # Build agent
        existing_id = existing_by_name.get(name, {}).get("id")
        agent = build_agent(name, rows, gemini_result, existing_id, policy_details)

        if name in existing_by_name:
            # Update existing
            idx = next(i for i, a in enumerate(existing_agents) if a["name"] == name)
            existing_agents[idx] = agent
            updated_count += 1
            print(f"  Updated existing agent (id: {agent['id']})")
        else:
            new_agents.append(agent)
            print(f"  New agent (id: {agent['id']})")

    # Append new agents
    existing_agents.extend(new_agents)

    print(f"\nSummary: {updated_count} updated, {len(new_agents)} new, {len(existing_agents)} total")

    if args.dry_run:
        print("\n[DRY RUN] Would write the following new/updated agents:")
        for a in new_agents:
            print(f"  + {a['name']} (id: {a['id']}, status: {a['status']})")
        print("\nNo changes written.")
    else:
        agents_json_path.write_text(
            json.dumps(existing_agents, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {len(existing_agents)} agents to {agents_json_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
