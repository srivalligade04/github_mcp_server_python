"""
SonarCloud Quality Agent
========================
Runs all 4 SonarCloud tools using Claude as the orchestrator.

Usage:
    python sonar_agent.py --project srivalligade04_ml-for-java-professionals --pr 11

Requirements:
    pip install anthropic requests

Environment variables:
    ANTHROPIC_API_KEY   - Your Anthropic API key (console.anthropic.com)
    SONARCLOUD_TOKEN    - Your SonarCloud token (sonarcloud.io → My Account → Security)
"""

import os
import json
import argparse
import requests
import anthropic

# ── Configuration ─────────────────────────────────────────────────────────────

SONAR_BASE = "https://sonarcloud.io/api"
SONAR_TOKEN = os.environ.get("SONARCLOUD_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ── Tool Definitions (Claude sees these) ──────────────────────────────────────

TOOLS = [
    {
        "name": "get_sonar_branch_health",
        "description": (
            "Get overall code quality health of the main branch: bugs, vulnerabilities, "
            "code smells, coverage, duplications, security hotspots, and A-E ratings."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_key": {
                    "type": "string",
                    "description": "SonarCloud project key (e.g. myorg_my-repo)"
                }
            },
            "required": ["project_key"]
        }
    },
    {
        "name": "get_sonar_pr_issues",
        "description": (
            "List all new issues introduced by a PR with severity, type, message, "
            "and exact file + line number."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_key": {"type": "string", "description": "SonarCloud project key"},
                "pr_number":   {"type": "integer", "description": "GitHub pull request number"}
            },
            "required": ["project_key", "pr_number"]
        }
    },
    {
        "name": "get_sonar_pr_quality",
        "description": (
            "Fetch the SonarCloud quality gate result for a specific PR. "
            "Shows PASSED/FAILED and which conditions triggered a failure."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_key": {"type": "string", "description": "SonarCloud project key"},
                "pr_number":   {"type": "integer", "description": "GitHub pull request number"}
            },
            "required": ["project_key", "pr_number"]
        }
    },
    {
        "name": "get_sonar_pr_vs_main",
        "description": (
            "Side-by-side comparison of a PR's code quality against the main branch. "
            "Shows delta for bugs, vulnerabilities, code smells, coverage, and duplications."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_key": {"type": "string", "description": "SonarCloud project key"},
                "pr_number":   {"type": "integer", "description": "GitHub pull request number"}
            },
            "required": ["project_key", "pr_number"]
        }
    }
]

# ── Tool Implementations ───────────────────────────────────────────────────────

def _sonar_get(endpoint: str, params: dict) -> dict:
    """Helper: authenticated GET to SonarCloud API."""
    headers = {"Authorization": f"Bearer {SONAR_TOKEN}"}
    url = f"{SONAR_BASE}/{endpoint}"
    r = requests.get(url, params=params, headers=headers, timeout=15)
    try:
        return r.json()
    except Exception:
        return {"error": r.text, "status_code": r.status_code}


def get_sonar_branch_health(project_key: str) -> dict:
    """Fetch main branch health metrics."""
    metrics = [
        "bugs", "vulnerabilities", "security_hotspots",
        "code_smells", "coverage", "duplicated_lines_density",
        "reliability_rating", "security_rating", "sqale_rating"
    ]
    data = _sonar_get("measures/component", {
        "component": project_key,
        "metricKeys": ",".join(metrics)
    })

    if "errors" in data:
        return {"error": data["errors"]}

    measures = {m["metric"]: m.get("value", "N/A")
                for m in data.get("component", {}).get("measures", [])}

    def rating_letter(val):
        return {"1": "A", "2": "B", "3": "C", "4": "D", "5": "E"}.get(str(int(float(val))) if val != "N/A" else "", "N/A")

    return {
        "project": project_key,
        "bugs":                    measures.get("bugs", "N/A"),
        "vulnerabilities":         measures.get("vulnerabilities", "N/A"),
        "security_hotspots":       measures.get("security_hotspots", "N/A"),
        "code_smells":             measures.get("code_smells", "N/A"),
        "coverage":                measures.get("coverage", "N/A"),
        "duplicated_lines_density":measures.get("duplicated_lines_density", "N/A"),
        "reliability_rating":      rating_letter(measures.get("reliability_rating", "N/A")),
        "security_rating":         rating_letter(measures.get("security_rating", "N/A")),
        "maintainability_rating":  rating_letter(measures.get("sqale_rating", "N/A")),
    }


def get_sonar_pr_issues(project_key: str, pr_number: int) -> dict:
    """Fetch new issues introduced by a PR."""
    data = _sonar_get("issues/search", {
        "componentKeys": project_key,
        "pullRequest":   pr_number,
        "resolved":      "false",
        "ps":            50
    })

    if "errors" in data:
        return {"error": data["errors"]}

    issues = data.get("issues", [])
    return {
        "pr_number":   pr_number,
        "total_issues": data.get("total", 0),
        "issues": [
            {
                "type":     i.get("type"),
                "severity": i.get("severity"),
                "message":  i.get("message"),
                "file":     i.get("component", "").split(":")[-1],
                "line":     i.get("line")
            }
            for i in issues
        ]
    }


def get_sonar_pr_quality(project_key: str, pr_number: int) -> dict:
    """Fetch quality gate result for a PR."""
    data = _sonar_get("qualitygates/project_status", {
        "projectKey":  project_key,
        "pullRequest": pr_number
    })

    if "errors" in data:
        return {"error": data["errors"]}

    ps = data.get("projectStatus", {})
    return {
        "pr_number": pr_number,
        "status":    ps.get("status", "N/A"),
        "conditions": [
            {
                "metric":          c.get("metricKey"),
                "status":          c.get("status"),
                "actual_value":    c.get("actualValue"),
                "error_threshold": c.get("errorThreshold")
            }
            for c in ps.get("conditions", [])
        ]
    }


def get_sonar_pr_vs_main(project_key: str, pr_number: int) -> dict:
    """Compare PR metrics against main branch."""
    metrics = "bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density,security_hotspots"

    main_data = _sonar_get("measures/component", {
        "component":  project_key,
        "metricKeys": metrics
    })
    pr_data = _sonar_get("measures/component", {
        "component":   project_key,
        "pullRequest": pr_number,
        "metricKeys":  metrics
    })

    if "errors" in main_data:
        return {"error": main_data["errors"]}
    if "errors" in pr_data:
        return {"error": pr_data["errors"]}

    def extract(data):
        return {m["metric"]: m.get("value", "N/A")
                for m in data.get("component", {}).get("measures", [])}

    main = extract(main_data)
    pr   = extract(pr_data)

    def delta(key):
        try:
            return round(float(pr.get(key, 0)) - float(main.get(key, 0)), 2)
        except Exception:
            return "N/A"

    return {
        "pr_number": pr_number,
        "comparison": {
            k: {"main": main.get(k, "N/A"), "pr": pr.get(k, "N/A"), "delta": delta(k)}
            for k in ["bugs", "vulnerabilities", "code_smells",
                      "coverage", "duplicated_lines_density", "security_hotspots"]
        }
    }


# ── Tool Router ────────────────────────────────────────────────────────────────

def execute_tool(name: str, inputs: dict) -> str:
    """Route tool call to the correct implementation and return JSON string."""
    print(f"  → Calling: {name}({inputs})")
    try:
        if name == "get_sonar_branch_health":
            result = get_sonar_branch_health(inputs["project_key"])
        elif name == "get_sonar_pr_issues":
            result = get_sonar_pr_issues(inputs["project_key"], inputs["pr_number"])
        elif name == "get_sonar_pr_quality":
            result = get_sonar_pr_quality(inputs["project_key"], inputs["pr_number"])
        elif name == "get_sonar_pr_vs_main":
            result = get_sonar_pr_vs_main(inputs["project_key"], inputs["pr_number"])
        else:
            result = {"error": f"Unknown tool: {name}"}
    except Exception as e:
        result = {"error": str(e)}

    return json.dumps(result, indent=2)


# ── Agentic Loop ───────────────────────────────────────────────────────────────

def run_sonar_agent(project_key: str, pr_number: int) -> str:
    """
    Run the SonarCloud agent for the given project and PR.
    Returns the final summary as a string.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    system_prompt = (
        "You are a code quality analyst. When asked to analyze a project, "
        "always run ALL 4 SonarCloud tools: get_sonar_branch_health, "
        "get_sonar_pr_issues, get_sonar_pr_quality, and get_sonar_pr_vs_main. "
        "After collecting all results, provide a clear, structured summary with: "
        "1) Branch health overview  2) PR quality gate status  "
        "3) New issues introduced  4) PR vs main comparison  5) Recommendations."
    )

    messages = [
        {
            "role": "user",
            "content": (
                f"Analyze SonarCloud quality for project '{project_key}', PR #{pr_number}. "
                f"Run all 4 tools and give me a full report."
            )
        }
    ]

    print(f"\n{'='*60}")
    print(f"  SonarCloud Agent  |  {project_key}  |  PR #{pr_number}")
    print(f"{'='*60}\n")

    final_response = ""

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system_prompt,
            tools=TOOLS,
            messages=messages
        )

        # Append assistant response to conversation history
        messages.append({"role": "assistant", "content": response.content})

        # If Claude is done, extract and return the final text
        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    final_response += block.text
            break

        # Handle tool calls
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result_str = execute_tool(block.name, block.input)
                tool_results.append({
                    "type":        "tool_result",
                    "tool_use_id": block.id,
                    "content":     result_str
                })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    return final_response


# ── Entry Point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SonarCloud Quality Agent")
    parser.add_argument("--project", required=True,  help="SonarCloud project key")
    parser.add_argument("--pr",      required=True,  type=int, help="PR number")
    args = parser.parse_args()

    if not SONAR_TOKEN:
        print("ERROR: Set SONARCLOUD_TOKEN environment variable")
        exit(1)
    if not ANTHROPIC_API_KEY:
        print("ERROR: Set ANTHROPIC_API_KEY environment variable")
        exit(1)

    report = run_sonar_agent(args.project, args.pr)
    print("\n" + report)