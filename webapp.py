#!/usr/bin/env python3
"""
Web application to review policy analysis results.
"""

import json
import re
import os
from pathlib import Path
from flask import Flask, render_template_string, abort, request, redirect, url_for, jsonify, Response
from functools import wraps

app = Flask(__name__)

# Basic authentication
AUTH_USERNAME = "demo"
AUTH_PASSWORD = "agentpolicy"


def check_auth(username, password):
    """Check if username/password combination is valid."""
    return username == AUTH_USERNAME and password == AUTH_PASSWORD


def authenticate():
    """Send a 401 response that enables basic auth."""
    return Response(
        'Authentication required.', 401,
        {'WWW-Authenticate': 'Basic realm="Policy Analyzer"'}
    )


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# Default results directory (can be overridden by env var or CLI arg)
RESULTS_DIR = Path(os.environ.get("RESULTS_DIR", Path(__file__).parent / "output"))
COMMENTS_FILE = Path(os.environ.get("COMMENTS_FILE", Path(__file__).parent / "comments.json"))


def load_comments() -> dict:
    """Load comments from JSON file."""
    if COMMENTS_FILE.exists():
        try:
            return json.loads(COMMENTS_FILE.read_text())
        except:
            return {}
    return {}


def save_comments(comments: dict):
    """Save comments to JSON file."""
    COMMENTS_FILE.write_text(json.dumps(comments, indent=2))


def get_comment_key(agent_id: str, regulation: str) -> str:
    """Generate a key for storing comments."""
    return f"{agent_id}::{regulation}"

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
        .agent-card .regulations {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 12px;
        }
        .agent-card .reg-badge {
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 12px;
            text-decoration: none;
        }

        .stats {
            display: flex;
            gap: 24px;
            margin-bottom: 24px;
            flex-wrap: wrap;
        }
        .stat {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 20px 24px;
            text-align: center;
            min-width: 120px;
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
        .sidebar h4 {
            font-size: 12px;
            text-transform: uppercase;
            color: var(--text-muted);
            margin-bottom: 8px;
            margin-top: 16px;
        }
        .sidebar h4:first-child { margin-top: 0; }
        .sidebar-nav {
            list-style: none;
        }
        .sidebar-nav li {
            margin-bottom: 2px;
        }
        .sidebar-nav a {
            display: block;
            padding: 6px 12px;
            color: var(--text-muted);
            text-decoration: none;
            border-radius: 4px;
            font-size: 13px;
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
            grid-template-columns: 280px 1fr;
            gap: 24px;
        }

        .filter-bar {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 16px;
            margin-bottom: 24px;
            display: flex;
            gap: 16px;
            align-items: center;
            flex-wrap: wrap;
        }
        .filter-bar label {
            font-size: 13px;
            color: var(--text-muted);
        }
        .filter-bar select {
            background: var(--bg);
            border: 1px solid var(--border);
            color: var(--text);
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 14px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }
        th {
            font-size: 12px;
            text-transform: uppercase;
            color: var(--text-muted);
            font-weight: 600;
        }
        td a {
            color: var(--accent);
            text-decoration: none;
        }
        td a:hover { text-decoration: underline; }

        .matrix {
            overflow-x: auto;
        }
        .matrix table {
            min-width: 100%;
        }
        .matrix th, .matrix td {
            text-align: center;
            padding: 8px;
            font-size: 13px;
        }
        .matrix th:first-child, .matrix td:first-child {
            text-align: left;
            position: sticky;
            left: 0;
            background: var(--bg-secondary);
        }
        .matrix .cell-compliant { background: rgba(63, 185, 80, 0.2); }
        .matrix .cell-partial { background: rgba(210, 153, 34, 0.2); }
        .matrix .cell-non-compliant { background: rgba(248, 81, 73, 0.2); }
        .matrix .cell-missing { background: var(--bg); color: var(--text-muted); }

        .comment-section {
            margin-top: 24px;
            padding-top: 24px;
            border-top: 1px solid var(--border);
        }
        .comment-section h3 {
            font-size: 14px;
            margin-bottom: 12px;
            color: var(--text-muted);
        }
        .comment-form textarea {
            width: 100%;
            min-height: 100px;
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 6px;
            color: var(--text);
            padding: 12px;
            font-family: inherit;
            font-size: 14px;
            resize: vertical;
        }
        .comment-form textarea:focus {
            outline: none;
            border-color: var(--accent);
        }
        .comment-form button {
            margin-top: 12px;
            background: var(--accent);
            color: #000;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
        }
        .comment-form button:hover {
            opacity: 0.9;
        }
        .comment-display {
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 16px;
            margin-bottom: 12px;
            white-space: pre-wrap;
            font-size: 14px;
        }
        .comment-meta {
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 8px;
        }
        .flash-message {
            background: var(--green);
            color: #000;
            padding: 12px 16px;
            border-radius: 6px;
            margin-bottom: 16px;
            font-size: 14px;
        }

        @media (max-width: 768px) {
            .two-column { grid-template-columns: 1fr; }
            .stats { flex-wrap: wrap; }
            .stat { flex: 1 1 100px; }
        }
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1><a href="/">Policy Analyzer</a></h1>
            <nav>
                <a href="/">Dashboard</a>
                <a href="/matrix">Compliance Matrix</a>
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
        <div class="stat-value">{{ total_analyses }}</div>
        <div class="stat-label">Total Analyses</div>
    </div>
    <div class="stat">
        <div class="stat-value">{{ total_agents }}</div>
        <div class="stat-label">Agents</div>
    </div>
    <div class="stat">
        <div class="stat-value">{{ total_regulations }}</div>
        <div class="stat-label">Regulations</div>
    </div>
    <div class="stat stat-compliant">
        <div class="stat-value">{{ compliant }}</div>
        <div class="stat-label">Compliant</div>
    </div>
    <div class="stat stat-partial">
        <div class="stat-value">{{ partial }}</div>
        <div class="stat-label">Partial</div>
    </div>
    <div class="stat stat-non-compliant">
        <div class="stat-value">{{ non_compliant }}</div>
        <div class="stat-label">Non-Compliant</div>
    </div>
</div>

<div class="filter-bar">
    <label>Filter by regulation:</label>
    <select onchange="window.location.href='/?regulation='+this.value">
        <option value="">All regulations</option>
        {% for reg in regulations %}
        <option value="{{ reg }}" {% if selected_regulation == reg %}selected{% endif %}>{{ reg }}</option>
        {% endfor %}
    </select>
</div>

<div class="grid">
    {% for agent in agents %}
    <div class="agent-card">
        <h3><a href="/agent/{{ agent.id }}">{{ agent.name }}</a></h3>
        <div class="meta">
            {{ agent.analysis_count }} analysis{% if agent.analysis_count != 1 %}es{% endif %}
            {% if agent.has_log %} &bull; Has execution log{% endif %}
        </div>
        <div class="regulations">
            {% for reg in agent.regulations %}
            <a href="/agent/{{ agent.id }}/{{ reg.name }}"
               class="reg-badge badge-{{ reg.rating_class }}"
               title="{{ reg.rating }}">{{ reg.name }}</a>
            {% endfor %}
        </div>
    </div>
    {% endfor %}
</div>
{% endblock %}
"""

MATRIX_TEMPLATE = """
{% extends "base" %}
{% block title %}Compliance Matrix - Policy Analyzer{% endblock %}
{% block content %}
<h2 style="margin-bottom: 24px;">Compliance Matrix</h2>

<div class="card">
    <div class="card-body matrix">
        <table>
            <thead>
                <tr>
                    <th>Agent</th>
                    {% for reg in regulations %}
                    <th>{{ reg }}</th>
                    {% endfor %}
                </tr>
            </thead>
            <tbody>
                {% for agent in agents %}
                <tr>
                    <td><a href="/agent/{{ agent.id }}">{{ agent.name }}</a></td>
                    {% for reg in regulations %}
                    {% set result = agent.by_regulation.get(reg) %}
                    {% if result %}
                    <td class="cell-{{ result.rating_class }}">
                        <a href="/agent/{{ agent.id }}/{{ reg }}" title="{{ result.rating }}">
                            {% if result.rating_class == 'compliant' %}&#10003;
                            {% elif result.rating_class == 'partial' %}~
                            {% elif result.rating_class == 'non-compliant' %}&#10007;
                            {% else %}?{% endif %}
                        </a>
                    </td>
                    {% else %}
                    <td class="cell-missing">-</td>
                    {% endif %}
                    {% endfor %}
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<div style="margin-top: 16px; font-size: 13px; color: var(--text-muted);">
    Legend:
    <span style="color: var(--green);">&#10003; Compliant</span> &bull;
    <span style="color: var(--yellow);">~ Partial</span> &bull;
    <span style="color: var(--red);">&#10007; Non-Compliant</span> &bull;
    <span>- Not analyzed</span>
</div>
{% endblock %}
"""

AGENT_TEMPLATE = """
{% extends "base" %}
{% block title %}{{ agent.name }} - Policy Analyzer{% endblock %}
{% block content %}
<div class="breadcrumb">
    <a href="/">Dashboard</a> <span>/</span> {{ agent.name }}
    {% if selected_regulation %}<span>/</span> {{ selected_regulation }}{% endif %}
</div>

<div class="two-column">
    <div class="sidebar">
        <h4>Regulations</h4>
        <nav>
            <ul class="sidebar-nav">
                {% for reg in agent.regulations %}
                <li>
                    <a href="/agent/{{ agent.id }}/{{ reg.name }}"
                       {% if reg.name == selected_regulation %}class="active"{% endif %}>
                        {{ reg.name }}
                        <span class="badge badge-{{ reg.rating_class }}" style="float:right; padding: 2px 6px; font-size: 10px;">
                            {{ reg.rating_short }}
                        </span>
                    </a>
                </li>
                {% endfor %}
            </ul>
        </nav>

        <h4>Other Agents</h4>
        <nav>
            <ul class="sidebar-nav">
                {% for a in all_agents %}
                {% if a.id != agent.id %}
                <li>
                    <a href="/agent/{{ a.id }}">{{ a.name }}</a>
                </li>
                {% endif %}
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
                        {% if selected_regulation %}{{ selected_regulation }}{% else %}Select a regulation{% endif %}
                        {% if analysis and analysis.has_log %} &bull; Analyzed with execution log{% endif %}
                    </div>
                </div>
                {% if analysis %}
                <span class="badge badge-{{ analysis.rating_class }}">{{ analysis.rating }}</span>
                {% endif %}
            </div>
            <div class="card-body">
                {% if analysis %}
                <div class="analysis-content">
                    {{ analysis.content_html | safe }}
                </div>

                <div class="comment-section">
                    <h3>Review Comments</h3>
                    {% if comment %}
                    <div class="comment-display">{{ comment.text }}</div>
                    <div class="comment-meta">Last updated: {{ comment.updated_at }}</div>
                    {% endif %}
                    <form class="comment-form" method="POST" action="/agent/{{ agent.id }}/{{ selected_regulation }}/comment">
                        <textarea name="comment" placeholder="Add your review comments here...">{{ comment.text if comment else '' }}</textarea>
                        <button type="submit">Save Comment</button>
                    </form>
                </div>
                {% else %}
                <p style="color: var(--text-muted);">Select a regulation from the sidebar to view the analysis.</p>
                {% endif %}
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
    agent_id = ""
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

    # Extract from filename if not in header
    # Format: {agent_id}_{regulation}_analysis.txt
    if not agent_id or not regulation:
        fname = filepath.stem  # e.g., "chat_68421cb7c22d7402e81f5fc9_GDPR_analysis"
        if fname.endswith('_analysis'):
            fname = fname[:-9]  # Remove _analysis
            # Find regulation (last part after final underscore that matches known patterns)
            parts = fname.rsplit('_', 1)
            if len(parts) == 2:
                potential_reg = parts[1]
                potential_id = parts[0]
                # Simple heuristic: regulations are usually uppercase or known names
                if potential_reg.isupper() or potential_reg in ['ePrivacy_Directive']:
                    if not regulation:
                        regulation = potential_reg.replace('_', '-')
                    if not agent_id:
                        agent_id = potential_id

    if not agent_id:
        agent_id = filepath.stem

    # Get analysis content
    analysis_content = '\n'.join(lines[header_end:]).strip()

    # Detect compliance rating - look for the actual rating declaration
    rating = "Unknown"
    rating_class = "unknown"
    rating_short = "?"

    content_lower = content.lower()

    # Look for explicit rating patterns (more specific first)
    # Pattern: "Overall Compliance Rating" or "5. Overall" followed by the rating
    rating_section = re.search(
        r'(?:overall\s+)?compliance\s+rating[:\s]*\n*\s*[#*]*\s*(non[- ]?compliant|partially\s+compliant|compliant)',
        content_lower
    )
    if not rating_section:
        # Try: **RATING: COMPLIANT** or **Non-Compliant** or **Compliant** or # Non-Compliant
        rating_section = re.search(
            r'\*\*(?:rating:\s*)?(non[- ]?compliant|partially\s+compliant|compliant)\*\*',
            content_lower
        )

    if rating_section:
        detected = rating_section.group(1).strip()
        if 'non' in detected:
            rating = "Non-Compliant"
            rating_class = "non-compliant"
            rating_short = "NC"
        elif 'partial' in detected:
            rating = "Partially Compliant"
            rating_class = "partial"
            rating_short = "PC"
        else:
            rating = "Compliant"
            rating_class = "compliant"
            rating_short = "C"
    else:
        # Fallback: count occurrences to determine overall sentiment
        non_compliant_count = len(re.findall(r'\*\*non[- ]?compliant\*\*', content_lower))
        compliant_count = len(re.findall(r'\*\*compliant\*\*', content_lower)) - non_compliant_count
        partial_count = len(re.findall(r'\*\*partially compliant\*\*', content_lower))

        if partial_count > 0 and partial_count >= non_compliant_count:
            rating = "Partially Compliant"
            rating_class = "partial"
            rating_short = "PC"
        elif non_compliant_count > compliant_count:
            rating = "Non-Compliant"
            rating_class = "non-compliant"
            rating_short = "NC"
        elif compliant_count > 0:
            rating = "Compliant"
            rating_class = "compliant"
            rating_short = "C"

    return {
        "file": filepath,
        "agent_id": agent_id,
        "agent_name": agent_name or agent_id,
        "regulation": regulation,
        "has_log": log_file is not None,
        "rating": rating,
        "rating_class": rating_class,
        "rating_short": rating_short,
        "content": analysis_content,
    }


def markdown_to_html(text: str) -> str:
    """Convert markdown-like text to HTML."""
    import markdown
    html = markdown.markdown(text, extensions=['tables', 'fenced_code'])
    return html


def get_all_analyses() -> list[dict]:
    """Load all analysis results."""
    analyses = []
    if RESULTS_DIR.exists():
        for f in sorted(RESULTS_DIR.glob("*.txt")):
            try:
                analyses.append(parse_analysis_file(f))
            except Exception as e:
                print(f"Error parsing {f}: {e}")
    return analyses


def group_by_agent(analyses: list[dict]) -> list[dict]:
    """Group analyses by agent."""
    agents = {}
    for a in analyses:
        aid = a['agent_id']
        if aid not in agents:
            agents[aid] = {
                'id': aid,
                'name': a['agent_name'],
                'has_log': a['has_log'],
                'regulations': [],
                'by_regulation': {},
                'analysis_count': 0
            }
        agents[aid]['regulations'].append({
            'name': a['regulation'],
            'rating': a['rating'],
            'rating_class': a['rating_class'],
            'rating_short': a['rating_short']
        })
        agents[aid]['by_regulation'][a['regulation']] = a
        agents[aid]['analysis_count'] += 1
        if a['has_log']:
            agents[aid]['has_log'] = True

    # Sort regulations within each agent
    for agent in agents.values():
        agent['regulations'].sort(key=lambda r: r['name'])

    return sorted(agents.values(), key=lambda a: a['name'].lower())


@app.route('/')
@requires_auth
def dashboard():
    analyses = get_all_analyses()
    agents = group_by_agent(analyses)

    # Get filter
    selected_regulation = request.args.get('regulation', '')

    # Filter if needed
    if selected_regulation:
        for agent in agents:
            agent['regulations'] = [r for r in agent['regulations'] if r['name'] == selected_regulation]
        agents = [a for a in agents if a['regulations']]

    # Stats
    all_regulations = sorted(set(a['regulation'] for a in analyses))
    total_analyses = len(analyses)
    total_agents = len(set(a['agent_id'] for a in analyses))
    total_regulations = len(all_regulations)
    compliant = sum(1 for a in analyses if a['rating_class'] == 'compliant')
    partial = sum(1 for a in analyses if a['rating_class'] == 'partial')
    non_compliant = sum(1 for a in analyses if a['rating_class'] == 'non-compliant')

    return render_template_string(
        DASHBOARD_TEMPLATE,
        agents=agents,
        regulations=all_regulations,
        selected_regulation=selected_regulation,
        total_analyses=total_analyses,
        total_agents=total_agents,
        total_regulations=total_regulations,
        compliant=compliant,
        partial=partial,
        non_compliant=non_compliant,
        base=BASE_TEMPLATE
    )


@app.route('/matrix')
@requires_auth
def matrix():
    analyses = get_all_analyses()
    agents = group_by_agent(analyses)
    all_regulations = sorted(set(a['regulation'] for a in analyses))

    return render_template_string(
        MATRIX_TEMPLATE,
        agents=agents,
        regulations=all_regulations,
        base=BASE_TEMPLATE
    )


@app.route('/agent/<agent_id>')
@app.route('/agent/<agent_id>/<regulation>')
@requires_auth
def agent_detail(agent_id: str, regulation: str = None):
    analyses = get_all_analyses()
    agents = group_by_agent(analyses)

    agent = next((a for a in agents if a['id'] == agent_id), None)
    if not agent:
        abort(404)

    # Get specific analysis if regulation specified
    analysis = None
    if regulation:
        analysis = agent['by_regulation'].get(regulation)
        if analysis:
            analysis['content_html'] = markdown_to_html(analysis['content'])
    elif agent['regulations']:
        # Default to first regulation
        first_reg = agent['regulations'][0]['name']
        analysis = agent['by_regulation'].get(first_reg)
        if analysis:
            analysis['content_html'] = markdown_to_html(analysis['content'])
            regulation = first_reg

    # Load comment for this agent/regulation
    comment = None
    if regulation:
        comments = load_comments()
        key = get_comment_key(agent_id, regulation)
        if key in comments:
            comment = comments[key]

    return render_template_string(
        AGENT_TEMPLATE,
        agent=agent,
        analysis=analysis,
        selected_regulation=regulation,
        all_agents=agents,
        comment=comment,
        base=BASE_TEMPLATE
    )


@app.route('/agent/<agent_id>/<regulation>/comment', methods=['POST'])
@requires_auth
def save_comment(agent_id: str, regulation: str):
    """Save a comment for an agent/regulation pair."""
    from datetime import datetime

    comment_text = request.form.get('comment', '').strip()
    comments = load_comments()
    key = get_comment_key(agent_id, regulation)

    if comment_text:
        comments[key] = {
            'text': comment_text,
            'agent_id': agent_id,
            'regulation': regulation,
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    elif key in comments:
        # Remove empty comments
        del comments[key]

    save_comments(comments)
    return redirect(url_for('agent_detail', agent_id=agent_id, regulation=regulation))


# Custom template loader
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
