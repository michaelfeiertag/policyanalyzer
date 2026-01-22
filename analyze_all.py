#!/usr/bin/env python3
"""
Orchestration tool that:
1. Executes the Lindy agent import tool
2. Runs policy analysis on each imported agent
3. Matches agents with corresponding log files when available
"""

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def load_dotenv():
    """Load environment variables from .env file."""
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


load_dotenv()


# Default paths relative to this script
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
AGENT_IMPORT_DIR = PROJECT_ROOT / "agentimport" / "lindy"
AGENT_OUTPUT_DIR = AGENT_IMPORT_DIR / "output"
LOG_OUTPUT_DIR = PROJECT_ROOT / "agentlogimport" / "output"
POLICY_ANALYZER = SCRIPT_DIR / "policyanalyzer.py"
VENV_PYTHON = SCRIPT_DIR / "venv" / "bin" / "python"


def run_agent_import(skip_import: bool = False, verbose: bool = False) -> tuple[bool, float]:
    """Run the Lindy agent import tool. Returns (success, elapsed_seconds)."""
    if skip_import:
        if verbose:
            print("Skipping agent import (using existing output files)")
        return True, 0.0

    print("Running Lindy agent import...")
    start = time.time()

    if not AGENT_IMPORT_DIR.exists():
        print(f"Error: Agent import directory not found: {AGENT_IMPORT_DIR}", file=sys.stderr)
        return False, 0.0

    try:
        result = subprocess.run(
            ["npm", "start"],
            cwd=AGENT_IMPORT_DIR,
            capture_output=not verbose,
            text=True
        )
        elapsed = time.time() - start
        if result.returncode != 0:
            print(f"Error: Agent import failed with code {result.returncode}", file=sys.stderr)
            if not verbose and result.stderr:
                print(result.stderr, file=sys.stderr)
            return False, elapsed
        print(f"Agent import completed successfully ({elapsed:.1f}s)")
        return True, elapsed
    except FileNotFoundError:
        print("Error: npm not found. Please install Node.js and npm.", file=sys.stderr)
        return False, 0.0
    except Exception as e:
        print(f"Error running agent import: {e}", file=sys.stderr)
        return False, 0.0


def get_agent_files() -> list[Path]:
    """Get all agent JSON files from the output directory."""
    if not AGENT_OUTPUT_DIR.exists():
        return []

    return [
        f for f in AGENT_OUTPUT_DIR.glob("*.json")
        if f.name != "_summary.json"
    ]


def sanitize_for_filename(name: str) -> str:
    """Sanitize a name for filename matching."""
    # Replace spaces and special chars with underscores
    sanitized = ""
    for c in name:
        if c.isalnum():
            sanitized += c
        elif c in " -_":
            sanitized += "_"
    # Collapse multiple underscores
    while "__" in sanitized:
        sanitized = sanitized.replace("__", "_")
    return sanitized.strip("_")


def find_log_file(agent_name: str) -> Path | None:
    """Find a matching log file for an agent name."""
    if not LOG_OUTPUT_DIR.exists():
        return None

    # Try exact match with sanitized name
    sanitized_name = sanitize_for_filename(agent_name)

    for log_file in LOG_OUTPUT_DIR.glob("*.csv"):
        log_name = log_file.stem
        if log_name.lower() == sanitized_name.lower():
            return log_file
        # Also try without underscores
        if log_name.replace("_", "").lower() == sanitized_name.replace("_", "").lower():
            return log_file

    return None


def load_agent_info(agent_file: Path) -> dict | None:
    """Load agent information from JSON file."""
    try:
        with open(agent_file, "r") as f:
            data = json.load(f)
        return {
            "id": data.get("agentId", agent_file.stem),
            "name": data.get("agentName", data.get("config", {}).get("name", agent_file.stem)),
            "file": agent_file
        }
    except Exception as e:
        print(f"Warning: Could not load {agent_file}: {e}", file=sys.stderr)
        return None


def run_policy_analyzer(
    agent_file: Path,
    log_file: Path | None,
    regulation: str | None,
    custom_policy: Path | None,
    model: str | None,
    verbose: bool,
    output_dir: Path | None
) -> tuple[bool, str, float]:
    """Run the policy analyzer on a single agent. Returns (success, output, elapsed_seconds)."""
    # Use venv Python if available, otherwise fall back to system Python
    python_exe = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
    cmd = [python_exe, str(POLICY_ANALYZER), "--agent-definition", str(agent_file)]

    if regulation:
        cmd.extend(["--regulation", regulation])

    if custom_policy:
        cmd.extend(["--custom-policy", str(custom_policy)])

    if log_file:
        cmd.extend(["--sample-log", str(log_file)])

    if model:
        cmd.extend(["--model", model])

    if verbose:
        cmd.append("--verbose")

    try:
        start = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=SCRIPT_DIR)
        elapsed = time.time() - start
        output = result.stdout
        if result.returncode != 0:
            return False, result.stderr or "Unknown error", elapsed
        return True, output, elapsed
    except Exception as e:
        return False, str(e), 0.0


def main():
    parser = argparse.ArgumentParser(
        description="Run Lindy agent import and analyze all agents against compliance policies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --regulation GDPR
      Import agents and analyze against GDPR

  %(prog)s --regulation EU-AI-Act --skip-import
      Analyze existing agent files against EU AI Act

  %(prog)s --custom-policy my_policy.txt --output-dir results/
      Analyze against custom policy and save results to files
"""
    )

    parser.add_argument(
        "--regulation", "-r",
        help="Regulation to check against (e.g., GDPR, EU-AI-Act, HIPAA)"
    )
    parser.add_argument(
        "--custom-policy", "-p",
        type=Path,
        help="Path to custom policy text file"
    )
    parser.add_argument(
        "--skip-import", "-s",
        action="store_true",
        help="Skip agent import and use existing output files"
    )
    parser.add_argument(
        "--model", "-m",
        help="Gemini model to use for analysis"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=Path,
        help="Directory to save analysis results (default: print to stdout)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--list-agents",
        action="store_true",
        help="List available agents and exit"
    )
    parser.add_argument(
        "--agent", "-a",
        action="append",
        dest="agents",
        help="Specific agent ID(s) to analyze (can be used multiple times)"
    )
    parser.add_argument(
        "--parallel", "-j",
        type=int,
        default=1,
        metavar="N",
        help="Number of parallel analyses to run (default: 1)"
    )

    args = parser.parse_args()

    # Validate that at least one policy source is provided (unless just listing)
    if not args.list_agents and not args.regulation and not args.custom_policy:
        parser.error("At least one of --regulation or --custom-policy is required")

    # Track overall timing
    total_start = time.time()
    import_time = 0.0

    # Run agent import
    if not args.list_agents:
        success, import_time = run_agent_import(args.skip_import, args.verbose)
        if not success:
            sys.exit(1)

    # Get agent files
    agent_files = get_agent_files()
    if not agent_files:
        print(f"No agent files found in {AGENT_OUTPUT_DIR}", file=sys.stderr)
        sys.exit(1)

    # Load agent info
    agents = []
    for f in agent_files:
        info = load_agent_info(f)
        if info:
            info["log_file"] = find_log_file(info["name"])
            agents.append(info)

    # List agents if requested
    if args.list_agents:
        print(f"Found {len(agents)} agents:\n")
        for agent in agents:
            log_status = f"(log: {agent['log_file'].name})" if agent["log_file"] else "(no log)"
            print(f"  {agent['id']}: {agent['name']} {log_status}")
        sys.exit(0)

    # Filter agents if specific ones requested
    if args.agents:
        filtered = [a for a in agents if a["id"] in args.agents or a["name"] in args.agents]
        if not filtered:
            print(f"No matching agents found for: {args.agents}", file=sys.stderr)
            print("Use --list-agents to see available agents", file=sys.stderr)
            sys.exit(1)
        agents = filtered

    # Create output directory if specified
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)

    # Analyze each agent
    parallel = max(1, args.parallel)
    print(f"\nAnalyzing {len(agents)} agents (parallel={parallel})...\n")
    results = []

    def analyze_agent(agent_info: tuple[int, dict]) -> dict:
        """Analyze a single agent. Returns result dict."""
        idx, agent = agent_info
        agent_id = agent["id"]
        agent_name = agent["name"]
        log_file = agent["log_file"]

        success, output, elapsed = run_policy_analyzer(
            agent["file"],
            log_file,
            args.regulation,
            args.custom_policy,
            args.model,
            args.verbose,
            args.output_dir
        )

        return {
            "idx": idx,
            "agent_id": agent_id,
            "agent_name": agent_name,
            "success": success,
            "output": output,
            "had_log": log_file is not None,
            "elapsed": elapsed,
            "log_file": log_file
        }

    if parallel == 1:
        # Sequential execution with progress
        for i, agent in enumerate(agents, 1):
            log_info = f" with log {agent['log_file'].name}" if agent["log_file"] else ""
            print(f"[{i}/{len(agents)}] Analyzing: {agent['name']}{log_info}...", end=" ", flush=True)
            result = analyze_agent((i, agent))
            print(f"({result['elapsed']:.1f}s)")
            results.append(result)
    else:
        # Parallel execution
        print(f"Starting {len(agents)} analyses...")
        completed = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = {
                executor.submit(analyze_agent, (i, agent)): agent
                for i, agent in enumerate(agents, 1)
            }
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                completed += 1
                log_info = f" with log" if result["had_log"] else ""
                print(f"[{completed}/{len(agents)}] Done: {result['agent_name']}{log_info} ({result['elapsed']:.1f}s)")
                results.append(result)

    # Sort results by original order for consistent output
    results.sort(key=lambda x: x["idx"])

    # Save or print results
    for result in results:
        agent_name = result["agent_name"]
        agent_id = result["agent_id"]
        log_file = result["log_file"]
        output = result["output"]
        success = result["success"]

        if args.output_dir:
            output_file = args.output_dir / f"{sanitize_for_filename(agent_id)}_analysis.txt"
            with open(output_file, "w") as f:
                f.write(f"Agent: {agent_name}\n")
                f.write(f"ID: {agent_id}\n")
                f.write(f"Log file: {log_file.name if log_file else 'None'}\n")
                f.write(f"Regulation: {args.regulation or 'Custom policy'}\n")
                f.write("=" * 60 + "\n\n")
                f.write(output)
            print(f"  -> Saved: {output_file.name}")
        else:
            print("\n" + "=" * 60)
            print(f"ANALYSIS: {agent_name}")
            print("=" * 60)
            print(output)
            print()

        if not success:
            print(f"  Warning: Analysis failed - {output}", file=sys.stderr)

    # Summary
    total_elapsed = time.time() - total_start
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    successful = sum(1 for r in results if r["success"])
    with_logs = sum(1 for r in results if r["had_log"])
    analysis_time = sum(r["elapsed"] for r in results)

    print(f"Total agents analyzed: {len(results)}")
    print(f"Successful analyses: {successful}")
    print(f"Agents with log files: {with_logs}")

    print(f"\nTiming:")
    if import_time > 0:
        print(f"  Agent import:    {import_time:6.1f}s")
    print(f"  Analysis total:  {analysis_time:6.1f}s")
    print(f"  Total elapsed:   {total_elapsed:6.1f}s")

    if results:
        print(f"\nPer-agent timing:")
        for r in sorted(results, key=lambda x: x["elapsed"], reverse=True):
            status = "ok" if r["success"] else "FAILED"
            print(f"  {r['elapsed']:5.1f}s  [{status:6}]  {r['agent_name']}")

    if args.output_dir:
        print(f"\nResults saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
