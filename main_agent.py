"""
Main Orchestrator Agent
=======================
Combines ALL 11 tools — 4 SonarCloud + 7 GitHub PR analytics —
and runs them via a single Claude-powered agentic loop.

Usage:
    python main_agent.py \
        --repo  srivalligade04/ml-for-java-professionals \
        --project srivalligade04_ml-for-java-professionals \
        --pr 11

Usage (imported):
    from main_agent import run_main_agent
    report = run_main_agent(
        repo="srivalligade04/ml-for-java-professionals",
        project_key="srivalligade04_ml-for-java-professionals",
        pr_number=11
    )

Requirements:
    pip install anthropic requests
    export ANTHROPIC_API_KEY=...
    export SONARCLOUD_TOKEN=...
    export GITHUB_TOKEN=...     (optional but avoids GitHub rate limits)
"""

import os
import json
import argparse
import anthropic

# Import tool executors from the two sub-agents
from sonar_agent    import execute_tool as sonar_execute,    TOOLS as SONAR_TOOLS
from github_pr_agent import execute_tool as github_execute,  TOOLS as GITHUB_TOOLS

# ── Configuration ─────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ── Merge all 11 tools ────────────────────────────────────────────────────────

ALL_TOOLS = SONAR_TOOLS + GITHUB_TOOLS   # 4 Sonar + 7 GitHub = 11 total

# ── Unified Tool Router ───────────────────────────────────────────────────────

SONAR_TOOL_NAMES = {t["name"] for t in SONAR_TOOLS}
GITHUB_TOOL_NAMES = {t["name"] for t in GITHUB_TOOLS}

def execute_tool(name: str, inputs: dict) -> str:
    """Route tool call to the correct sub-agent executor."""
    if name in SONAR_TOOL_NAMES:
        return sonar_execute(name, inputs)
    elif name in GITHUB_TOOL_NAMES:
        return github_execute(name, inputs)
    return json.dumps({"error": f"Unknown tool: {name}"})

# ── Main Orchestrator Agent ───────────────────────────────────────────────────

def run_main_agent(repo: str, project_key: str, pr_number: int = None) -> str:
    """
    Run the full combined agent across all 11 tools.

    Args:
        repo:        GitHub repo in owner/repo format
        project_key: SonarCloud project key (owner_reponame)
        pr_number:   Optional PR number for PR-level analysis

    Returns:
        Full quality + PR analytics report as a string
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    system_prompt = """You are a senior DevOps quality analyst with access to 11 tools:

SONARCLOUD TOOLS (code quality):
  1. get_sonar_branch_health     — main branch health: bugs, smells, ratings
  2. get_sonar_pr_issues         — new issues introduced by a PR
  3. get_sonar_pr_quality        — quality gate PASSED/FAILED for a PR
  4. get_sonar_pr_vs_main        — PR vs main branch side-by-side comparison

GITHUB PR TOOLS (process health):
  5. get_pr_summary              — overall PR counts, merge rate, avg merge time
  6. list_open_prs               — all currently open PRs
  7. get_stale_prs               — PRs with no activity for 14+ days
  8. get_pr_merge_time_trend     — weekly trend of PR volume and merge time
  9. get_pr_review_stats         — reviewer leaderboard, approval rates
 10. get_contributor_pr_stats    — per-author PR breakdown
 11. get_pr_detail               — deep analytics for a single PR

When asked to run a full analysis:
- ALWAYS run all applicable tools
- For branch analysis: run tools 1, 5, 6, 7, 8, 9, 10
- For PR analysis: also run tools 2, 3, 4, 11
- Synthesize results into a clear structured report with:
    Section 1: Code Quality (SonarCloud)
    Section 2: PR Process Health (GitHub)
    Section 3: Team Performance
    Section 4: Risk & Recommendations
"""

    pr_context = f" and PR #{pr_number}" if pr_number else ""
    user_msg = (
        f"Run a complete analysis for GitHub repo '{repo}'{pr_context}. "
        f"SonarCloud project key is '{project_key}'. "
        f"Run ALL applicable tools and give me a full report."
    )

    messages = [{"role": "user", "content": user_msg}]

    print(f"\n{'='*65}")
    print(f"  MAIN ORCHESTRATOR AGENT")
    print(f"  GitHub  : {repo}")
    print(f"  Sonar   : {project_key}")
    if pr_number:
        print(f"  PR      : #{pr_number}")
    print(f"  Tools   : {len(ALL_TOOLS)} total (4 Sonar + 7 GitHub)")
    print(f"{'='*65}\n")

    final_response = ""

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            system=system_prompt,
            tools=ALL_TOOLS,
            messages=messages
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    final_response += block.text
            break

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
    parser = argparse.ArgumentParser(description="Main Orchestrator Agent — All 11 Tools")
    parser.add_argument("--repo",    required=True, help="GitHub owner/repo")
    parser.add_argument("--project", required=True, help="SonarCloud project key")
    parser.add_argument("--pr",      type=int,      help="PR number (optional)")
    args = parser.parse_args()

    if not ANTHROPIC_API_KEY:
        print("ERROR: Set ANTHROPIC_API_KEY environment variable")
        exit(1)

    report = run_main_agent(args.repo, args.project, args.pr)
    print("\n" + report)