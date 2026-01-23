#!/usr/bin/env python3
"""Policy Analyzer - A command-line utility for analyzing policies."""

import argparse
import os
from pathlib import Path
import sys


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

from google import genai
from google.genai import errors as genai_errors
from google.genai import types


def load_regulations() -> list[str]:
    """Load regulations from regulations.txt file."""
    regulations_file = Path(__file__).parent / "regulations.txt"
    if regulations_file.exists():
        return [line.strip() for line in regulations_file.read_text().splitlines() if line.strip()]
    return []


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        prog="policyanalyzer",
        description="A command-line utility for analyzing policies.",
        epilog="Authentication: Set the GEMINI_API_KEY environment variable with your Google AI API key. "
               "Get your key at https://aistudio.google.com/app/apikey",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )
    parser.add_argument(
        "--agent-definition",
        required=True,
        help="Path to the agent definition JSON file",
    )
    parser.add_argument(
        "--sample-log",
        help="Path to a sample log file",
    )
    parser.add_argument(
        "--custom-policy",
        help="Path to a custom policy file",
    )
    parser.add_argument(
        "--model",
        default="gemini-3-pro-preview",
        help="Gemini model to use (default: gemini-3-pro-preview)",
    )
    regulations = load_regulations()
    if regulations:
        parser.add_argument(
            "--regulation",
            choices=regulations,
            help="Regulation to check against",
        )

    return parser


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    has_regulation = hasattr(args, "regulation") and args.regulation
    if not args.custom_policy and not has_regulation:
        parser.error("at least one of --custom-policy or --regulation is required")

    if args.verbose:
        print("Verbose mode enabled", file=sys.stderr)

    # Read required files
    agent_definition = Path(args.agent_definition).read_text()
    prompt_file = Path(__file__).parent / "prompt.txt"
    prompt_template = prompt_file.read_text()

    # Read optional sample log
    sample_log = ""
    if args.sample_log:
        sample_log = Path(args.sample_log).read_text()

    # Read optional custom policy
    custom_policy = ""
    if args.custom_policy:
        custom_policy = Path(args.custom_policy).read_text()

    # Get regulation if specified
    regulation = ""
    if hasattr(args, "regulation") and args.regulation:
        regulation = args.regulation

    # Substitute variables in prompt template
    prompt_template = prompt_template.replace("$(REGULATION)", regulation)

    # Build content parts with labels
    parts = [
        types.Part.from_text(text=prompt_template),
        types.Part.from_text(text=f"[AGENT_DEFINITION]\n{agent_definition}"),
    ]
    if sample_log:
        parts.append(types.Part.from_text(text=f"[SAMPLE_LOG]\n{sample_log}"))
    if custom_policy:
        parts.append(types.Part.from_text(text=f"[CUSTOM_POLICY]\n{custom_policy}"))

    if args.verbose:
        total_len = sum(len(p.text) for p in parts)
        print(f"Total content length: {total_len} characters ({len(parts)} parts)", file=sys.stderr)

    # Configure and call Gemini
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set", file=sys.stderr)
        return 1

    client = genai.Client(api_key=api_key)
    try:
        if args.verbose:
            print(f"Using model: {args.model}", file=sys.stderr)

        # Use enhanced config for Gemini 3 Pro models
        generation_config = None
        if "gemini-3" in args.model and "pro" in args.model:
            generation_config = types.GenerateContentConfig(
                temperature=0.7,
                top_p=0.95,
                max_output_tokens=64000,
                thinking_config=types.ThinkingConfig(thinking_level="HIGH"),
            )
            if args.verbose:
                print("Using Gemini 3 Pro config with thinking enabled", file=sys.stderr)

        response = client.models.generate_content(
            model=args.model,
            contents=types.Content(role="user", parts=parts),
            config=generation_config,
        )
        print(response.text)
    except genai_errors.ClientError as e:
        print(f"API Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
