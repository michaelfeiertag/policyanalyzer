#!/usr/bin/env python3
"""Copy policy analysis .txt files to the UI data directory with ID-based filenames.

Files are copied to ../long-tail-experiment/src/data/policy-analyses/ as:
    {agentId}_{policyName}.txt

This allows the frontend to reference them by agent ID and policy name.
"""

import argparse
import csv
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path


def slugify(text: str) -> str:
    """Convert a policy name to a filename-safe slug."""
    text = text.strip()
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text)
    text = text.strip("_")
    return text


def main():
    parser = argparse.ArgumentParser(
        description="Copy analysis .txt files to the UI data directory with ID-based names",
    )
    parser.add_argument(
        "output_dir",
        help="Path to the policy analysis output directory (e.g. output.2026.1.25)",
    )
    parser.add_argument(
        "--agents-json",
        default=str(
            Path(__file__).parent.parent
            / "long-tail-experiment"
            / "src"
            / "data"
            / "agents.json"
        ),
        help="Path to agents.json (default: ../long-tail-experiment/src/data/agents.json)",
    )
    parser.add_argument(
        "--dest-dir",
        default=str(
            Path(__file__).parent.parent
            / "long-tail-experiment"
            / "src"
            / "data"
            / "policy-analyses"
        ),
        help="Destination directory for copied files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview copies without writing files",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    csv_path = output_dir / "policy_analysis_summary.csv"
    if not csv_path.exists():
        print(f"Error: {csv_path} not found", file=sys.stderr)
        return 1

    agents_json_path = Path(args.agents_json)
    if not agents_json_path.exists():
        print(f"Error: {agents_json_path} not found", file=sys.stderr)
        return 1

    # Load agent name -> id mapping
    agents = json.loads(agents_json_path.read_text(encoding="utf-8"))
    name_to_id: dict[str, str] = {a["name"]: a["id"] for a in agents}

    # Parse CSV to get agent name, policy, filename triples
    entries: list[tuple[str, str, str]] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            agent_name = row.get("Agent Name", "").strip().strip('"')
            policy = row.get("Policy", "").strip().strip('"')
            filename = row.get("File Name", "").strip().strip('"')
            if agent_name and policy and filename:
                entries.append((agent_name, policy, filename))

    dest_dir = Path(args.dest_dir)
    if not args.dry_run:
        dest_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    skipped = 0
    missing_agent = set()
    missing_file = 0

    for agent_name, policy, filename in entries:
        agent_id = name_to_id.get(agent_name)
        if not agent_id:
            missing_agent.add(agent_name)
            continue

        src = output_dir / filename
        if not src.exists():
            missing_file += 1
            continue

        dest_name = f"{agent_id}_{slugify(policy)}.txt"
        dest_path = dest_dir / dest_name

        if args.dry_run:
            print(f"  {filename} -> {dest_name}")
        else:
            shutil.copy2(src, dest_path)
        copied += 1

    print(f"\nCopied: {copied}")
    if missing_agent:
        print(f"Skipped (agent not in agents.json): {len(missing_agent)} agents: {', '.join(sorted(missing_agent))}")
    if missing_file:
        print(f"Skipped (source file missing): {missing_file}")
    if args.dry_run:
        print("\n[DRY RUN] No files written.")
    else:
        print(f"Destination: {dest_dir}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
