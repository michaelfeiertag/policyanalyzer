#!/usr/bin/env python3
"""
Web application to review policy analysis results.
"""

import json
import re
import os
from pathlib import Path
from flask import Flask, render_template_string, abort

app = Flask(__name__)

# Default results directory
RESULTS_DIR = Path(__file__).parent / "results"

# HTML Templates
BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Policy Analyzer{% endblock %}</title>
    <style>
        :root {
            --bg: #0d1117;
            --bg-secondary: #161b22;
            --border: #30363d;
            --text: #c9d1d9;
            --text-muted: #8b949e;
            --accent: #58a6ff;
            --green: #3fb950;
            --yellow: #d29922;
            --red: #f85149;
            --orange: #db6d28;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        header {
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border);
            padding: 16px 0;
            margin-bottom: 24px;
        }
        header .container {
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        header h1 { font-size: 20px; font-weight: 600; }
        header a { color: var(--text); text-decoration: none; }
        header nav a {
            color: var(--text-muted);
            margin-left: 24px;
            font-size: 14px;
        }
        header nav a:hover { color: var(--text); }

        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }
        .badge-compliant { background: var(--green); color: #000; }
        .badge-partial { background: var(--yellow); color: #000; }
        .badge-non-compliant { background: var(--red); color: #fff; }
        .badge-unknown { background: var(--border); color: var(--text); }

        .card {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 6px;
            margin-bottom: 16px;
        }
        .card-header {
            padding: 16px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .card-body { padding: 16px; }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 16px;
        }

        .agent-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 20px;
            transition: border-color 0.2s;
        }
        .agent-card:hover { border-color: var(--accent); }
        .agent-card h3 {
            font-size: 16px;
            margin-bottom: 8px;
        }
        .agent-card h3 a {
            color: var(--accent);
            text-decoration: none;
        }
        .agent-card h3 a:hover { text-decoration: underline; }
        .agent-card .meta {
            font-size: 13px;
            color: var(--text-muted);
            margin-bottom: 12px;
        }
        .agent-card .summary {
            font-size: 14px;
            color: var(--text-muted);
            margin-top: 12px;
        }

        .stats {
            display: flex;
            gap: 24px;
            margin-bottom: 24px;
        }
        .stat {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 20px 24px;
            text-align: center;
        }
        .stat-value {
            font-size: 32px;
            font-weight: 600;
        }
        .stat-label {
            font-size: 13px;
            color: var(--text-muted);
            margin-top: 4px;
        }
        .stat-compliant .stat-value { color: var(--green); }
        .stat-partial .stat-value { color: var(--yellow); }
        .stat-non-compliant .stat-value { color: var(--red); }

        .analysis-content {
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 24px;
            font-size: 14px;
        }
        .analysis-content h1, .analysis-content h2, .analysis-content h3 {
            color: var(--text);
            margin-top: 24px;
            margin-bottom: 12px;
        }
        .analysis-content h1:first-child,
        .analysis-content h2:first-child,
        .analysis-content h3:first-child { margin-top: 0; }
        .analysis-content h1 { font-size: 24px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
        .analysis-content h2 { font-size: 20px; }
        .analysis-content h3 { font-size: 16px; }
        .analysis-content p { margin-bottom: 12px; }
        .analysis-content ul, .analysis-content ol {
            margin-left: 24px;
            margin-bottom: 12px;
        }
        .analysis-content li { margin-bottom: 6px; }
        .analysis-content strong { color: var(--text); }
        .analysis-content code {
            background: var(--bg-secondary);
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 13px;
        }
        .analysis-content blockquote {
            border-left: 3px solid var(--border);
            padding-left: 16px;
            color: var(--text-muted);
            margin: 12px 0;
        }

        .breadcrumb {
            font-size: 14px;
            margin-bottom: 16px;
        }
        .breadcrumb a { color: var(--accent); text-decoration: none; }
        .breadcrumb a:hover { text-decoration: underline; }
        .breadcrumb span { color: var(--text-muted); }

        .sidebar {
            position: sticky;
            top: 20px;
        }
        .sidebar-nav {
            list-style: none;
        }
        .sidebar-nav li {
            margin-bottom: 4px;
        }
        .sidebar-nav a {
            display: block;
            padding: 8px 12px;
            color: var(--text-muted);
            text-decoration: none;
            border-radius: 4px;
            font-size: 14px;
        }
        .sidebar-nav a:hover {
            background: var(--bg);
            color: var(--text);
        }
        .sidebar-nav a.active {
            background: var(--accent);
            color: #000;
        }

        .two-column {
            display: grid;
            grid-template-columns: 250px 1fr;
            gap: 24px;
        }

        @media (max-width: 768px) {
            .two-column { grid-template-columns: 1fr; }
            .stats { flex-wrap: wrap; }
            .stat { flex: 1 1 150px; }
        }
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1><a href="/">Policy Analyzer</a></h1>
            <nav>
                <a href="/">Dashboard</a>
            </nav>
        </div>
    </header>
    <main class="container">
        {% block content %}{% endblock %}
    </main>
</body>
</html>
"""

DASHBOARD_TEMPLATE = """
{% extends "base" %}
{% block title %}Dashboard - Policy Analyzer{% endblock %}
{% block content %}
<h2 style="margin-bottom: 24px;">Analysis Results</h2>

<div class="stats">
    <div class="stat">
        <div class="stat-value">{{ total }}</div>
        <div class="stat-label">Total Agents</div>
    </div>
    <div class="stat stat-compliant">
        <div class="stat-value">{{ compliant }}</div>
        <div class="stat-label">Compliant</div>
    </div>
    <div class="stat stat-partial">
        <div class="stat-value">{{ partial }}</div>
        <div class="stat-label">Partially Compliant</div>
    </div>
    <div class="stat stat-non-compliant">
        <div class="stat-value">{{ non_compliant }}</div>
        <div class="stat-label">Non-Compliant</div>
    </div>
</div>

<div class="grid">
    {% for agent in agents %}
    <div class="agent-card">
        <h3><a href="/agent/{{ agent.id }}">{{ agent.name }}</a></h3>
        <div class="meta">
            {{ agent.regulation }}
            {% if agent.has_log %} &bull; Has execution log{% endif %}
        </div>
        <span class="badge badge-{{ agent.rating_class }}">{{ agent.rating }}</span>
        {% if agent.summary %}
        <div class="summary">{{ agent.summary }}</div>
        {% endif %}
    </div>
    {% endfor %}
</div>
{% endblock %}
"""

AGENT_TEMPLATE = """
{% extends "base" %}
{% block title %}{{ agent.name }} - Policy Analyzer{% endblock %}
{% block content %}
<div class="breadcrumb">
    <a href="/">Dashboard</a> <span>/</span> {{ agent.name }}
</div>

<div class="two-column">
    <div class="sidebar">
        <nav>
            <ul class="sidebar-nav">
                {% for a in all_agents %}
                <li>
                    <a href="/agent/{{ a.id }}" {% if a.id == agent.id %}class="active"{% endif %}>
                        {{ a.name }}
                    </a>
                </li>
                {% endfor %}
            </ul>
        </nav>
    </div>

    <div>
        <div class="card">
            <div class="card-header">
                <div>
                    <h2 style="font-size: 20px;">{{ agent.name }}</h2>
                    <div style="font-size: 13px; color: var(--text-muted); margin-top: 4px;">
                        {{ agent.regulation }}
                        {% if agent.has_log %} &bull; Analyzed with execution log{% endif %}
                    </div>
                </div>
                <span class="badge badge-{{ agent.rating_class }}">{{ agent.rating }}</span>
            </div>
            <div class="card-body">
                <div class="analysis-content">
                    {{ agent.content_html | safe }}
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
"""


def parse_analysis_file(filepath: Path) -> dict:
    """Parse an analysis result file."""
    content = filepath.read_text()
    lines = content.split('\n')

    # Parse header
    agent_name = ""
    agent_id = filepath.stem
    log_file = None
    regulation = ""

    header_end = 0
    for i, line in enumerate(lines):
        if line.startswith('Agent: '):
            agent_name = line[7:]
        elif line.startswith('ID: '):
            agent_id = line[4:]
        elif line.startswith('Log file: '):
            log_val = line[10:]
            log_file = log_val if log_val != 'None' else None
        elif line.startswith('Regulation: '):
            regulation = line[12:]
        elif line.startswith('=' * 10):
            header_end = i + 1
            break

    # Get analysis content
    analysis_content = '\n'.join(lines[header_end:]).strip()

    # Detect compliance rating
    rating = "Unknown"
    rating_class = "unknown"

    content_lower = content.lower()
    if 'non-compliant' in content_lower or 'non compliant' in content_lower:
        rating = "Non-Compliant"
        rating_class = "non-compliant"
    elif 'partially compliant' in content_lower:
        rating = "Partially Compliant"
        rating_class = "partial"
    elif 'compliant' in content_lower:
        # Check if it's actually compliant (not just mentioning the word)
        if re.search(r'rating[:\s]*(is\s+)?compliant|overall[:\s]*(is\s+)?compliant|\*\*compliant\*\*', content_lower):
            rating = "Compliant"
            rating_class = "compliant"
        else:
            rating = "Non-Compliant"
            rating_class = "non-compliant"

    # Extract summary (first paragraph of the analysis usually)
    summary = ""
    summary_match = re.search(r'summary.*?function[:\s]*\n+(.*?)(?:\n\n|\n###|\n\d\.)', analysis_content, re.IGNORECASE | re.DOTALL)
    if summary_match:
        summary = summary_match.group(1).strip()[:200]
        if len(summary_match.group(1).strip()) > 200:
            summary += "..."

    return {
        "id": agent_id,
        "name": agent_name or agent_id,
        "regulation": regulation,
        "has_log": log_file is not None,
        "rating": rating,
        "rating_class": rating_class,
        "summary": summary,
        "content": analysis_content,
    }


def markdown_to_html(text: str) -> str:
    """Convert markdown-like text to HTML."""
    import markdown
    # Convert markdown to HTML
    html = markdown.markdown(text, extensions=['tables', 'fenced_code'])
    return html


def get_all_agents() -> list[dict]:
    """Load all analysis results."""
    agents = []
    if RESULTS_DIR.exists():
        for f in sorted(RESULTS_DIR.glob("*.txt")):
            try:
                agents.append(parse_analysis_file(f))
            except Exception as e:
                print(f"Error parsing {f}: {e}")
    return agents


@app.route('/')
def dashboard():
    agents = get_all_agents()

    total = len(agents)
    compliant = sum(1 for a in agents if a['rating_class'] == 'compliant')
    partial = sum(1 for a in agents if a['rating_class'] == 'partial')
    non_compliant = sum(1 for a in agents if a['rating_class'] == 'non-compliant')

    return render_template_string(
        DASHBOARD_TEMPLATE,
        agents=agents,
        total=total,
        compliant=compliant,
        partial=partial,
        non_compliant=non_compliant,
        base=BASE_TEMPLATE
    )


@app.route('/agent/<agent_id>')
def agent_detail(agent_id: str):
    agents = get_all_agents()
    agent = next((a for a in agents if a['id'] == agent_id), None)

    if not agent:
        abort(404)

    # Convert content to HTML
    agent['content_html'] = markdown_to_html(agent['content'])

    return render_template_string(
        AGENT_TEMPLATE,
        agent=agent,
        all_agents=agents,
        base=BASE_TEMPLATE
    )


# Make Jinja2 recognize our base template
@app.context_processor
def inject_base():
    return {'base': BASE_TEMPLATE}


# Custom template loader to handle extends "base"
from jinja2 import BaseLoader, TemplateNotFound

class CustomLoader(BaseLoader):
    def get_source(self, environment, template):
        if template == "base":
            return BASE_TEMPLATE, None, lambda: True
        raise TemplateNotFound(template)

app.jinja_loader = CustomLoader()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Web app to review policy analysis results")
    parser.add_argument('--port', '-p', type=int, default=5000, help='Port to run on')
    parser.add_argument('--host', '-H', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--results-dir', '-r', type=Path, help='Results directory')
    parser.add_argument('--debug', '-d', action='store_true', help='Enable debug mode')
    args = parser.parse_args()

    global RESULTS_DIR
    if args.results_dir:
        RESULTS_DIR = args.results_dir

    print(f"Loading results from: {RESULTS_DIR}")
    print(f"Starting server at http://{args.host}:{args.port}")

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
