"""
GitHub PR Analytics Agent
=========================
Runs 7 GitHub PR analytics tools using Claude as the orchestrator.

Tools covered:
  1. get_pr_summary          - High-level PR counts, merge rate, avg merge time
  2. list_open_prs           - All currently open PRs with age & review state
  3. get_stale_prs           - Open PRs with no activity for N days
  4. get_pr_merge_time_trend - Weekly trend of PR volume and merge time
  5. get_pr_review_stats     - Reviewer leaderboard, approval rate, change-request ratio
  6. get_contributor_pr_stats- Per-author PR breakdown and merge rate
  7. get_pr_detail           - Deep analytics for a single PR

Usage (standalone):
    python github_pr_agent.py --repo srivalligade04/ml-for-java-professionals --pr 11

Usage (imported):
    from github_pr_agent import run_github_pr_agent
    report = run_github_pr_agent("srivalligade04/ml-for-java-professionals", pr_number=11)

Requirements:
    pip install anthropic requests
    export ANTHROPIC_API_KEY=...
    export GITHUB_TOKEN=...   (optional but avoids rate limits)
"""

import os
import json
import argparse
import requests
import anthropic

# ── Configuration ─────────────────────────────────────────────────────────────

GITHUB_API   = "https://api.github.com"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ── Tool Definitions ───────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "get_pr_summary",
        "description": (
            "High-level PR analytics: open/closed/merged counts, average merge time, "
            "merge rate, and top labels."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "repo":  {"type": "string",  "description": "owner/repo (e.g. facebook/react)"},
                "limit": {"type": "integer", "description": "Max closed PRs to analyse (default 100)"}
            },
            "required": ["repo"]
        }
    },
    {
        "name": "list_open_prs",
        "description": (
            "List every currently open PR with age, author, draft status, labels, "
            "and review state."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "owner/repo"},
                "sort": {
                    "type": "string",
                    "enum": ["created", "updated", "popularity", "long-running"],
                    "description": "Sort order (default: created)"
                }
            },
            "required": ["repo"]
        }
    },
    {
        "name": "get_stale_prs",
        "description": "Find open PRs with no activity for more than N days.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo":       {"type": "string",  "description": "owner/repo"},
                "stale_days": {"type": "integer", "description": "Inactivity threshold in days (default 14)"}
            },
            "required": ["repo"]
        }
    },
    {
        "name": "get_pr_merge_time_trend",
        "description": "Weekly trend of PR volume and median merge-time over past N weeks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo":  {"type": "string",  "description": "owner/repo"},
                "weeks": {"type": "integer", "description": "Number of weeks to look back (default 8)"}
            },
            "required": ["repo"]
        }
    },
    {
        "name": "get_pr_review_stats",
        "description": (
            "Review analytics: reviewer leaderboard, approval rate, change-request ratio."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "repo":  {"type": "string",  "description": "owner/repo"},
                "limit": {"type": "integer", "description": "Max closed PRs to analyse (default 100)"}
            },
            "required": ["repo"]
        }
    },
    {
        "name": "get_contributor_pr_stats",
        "description": (
            "Per-author PR breakdown: opened, merged, closed, merge rate, avg merge time."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "repo":  {"type": "string",  "description": "owner/repo"},
                "limit": {"type": "integer", "description": "Max PRs to analyse (default 200)"}
            },
            "required": ["repo"]
        }
    },
    {
        "name": "get_pr_detail",
        "description": (
            "Deep analytics for a single PR: commits, files changed, review timeline, "
            "merge time."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "repo":      {"type": "string",  "description": "owner/repo"},
                "pr_number": {"type": "integer", "description": "Pull request number"}
            },
            "required": ["repo", "pr_number"]
        }
    }
]

# ── GitHub API Helper ─────────────────────────────────────────────────────────

def _gh_get(path: str, params: dict = None) -> dict | list:
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    r = requests.get(f"{GITHUB_API}/{path}", params=params, headers=headers, timeout=15)
    try:
        return r.json()
    except Exception:
        return {"error": r.text}


def _pages(path: str, params: dict, max_items: int) -> list:
    """Fetch paginated GitHub results up to max_items."""
    results, page = [], 1
    while len(results) < max_items:
        p = {**params, "per_page": min(100, max_items - len(results)), "page": page}
        data = _gh_get(path, p)
        if not isinstance(data, list) or not data:
            break
        results.extend(data)
        page += 1
    return results[:max_items]


# ── Tool Implementations ───────────────────────────────────────────────────────

from datetime import datetime, timezone

def _parse_dt(s):
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

def _age_days(dt_str):
    dt = _parse_dt(dt_str)
    if not dt:
        return None
    return (datetime.now(timezone.utc) - dt).days

def _merge_minutes(pr):
    created = _parse_dt(pr.get("created_at"))
    merged  = _parse_dt(pr.get("merged_at"))
    if created and merged:
        return round((merged - created).total_seconds() / 60, 1)
    return None


def get_pr_summary(repo: str, limit: int = 100) -> dict:
    open_prs   = _gh_get(f"repos/{repo}/pulls", {"state": "open",   "per_page": 100})
    closed_prs = _pages(f"repos/{repo}/pulls", {"state": "closed"}, limit)

    merged = [p for p in closed_prs if p.get("merged_at")]
    merge_times = [t for t in (_merge_minutes(p) for p in merged) if t is not None]

    return {
        "repo":           repo,
        "open_count":     len(open_prs) if isinstance(open_prs, list) else "N/A",
        "closed_analysed":len(closed_prs),
        "merged_count":   len(merged),
        "merge_rate":     f"{round(len(merged)/len(closed_prs)*100, 1)}%" if closed_prs else "N/A",
        "avg_merge_time_hrs": round(sum(merge_times) / len(merge_times) / 60, 1) if merge_times else "N/A",
    }


def list_open_prs(repo: str, sort: str = "created") -> list:
    prs = _gh_get(f"repos/{repo}/pulls", {"state": "open", "sort": sort, "per_page": 50})
    if not isinstance(prs, list):
        return prs
    return [
        {
            "number":    p["number"],
            "title":     p["title"],
            "author":    p["user"]["login"],
            "draft":     p.get("draft", False),
            "age_days":  _age_days(p["created_at"]),
            "labels":    [l["name"] for l in p.get("labels", [])],
            "url":       p["html_url"]
        }
        for p in prs
    ]


def get_stale_prs(repo: str, stale_days: int = 14) -> list:
    prs = _gh_get(f"repos/{repo}/pulls", {"state": "open", "per_page": 100, "sort": "updated", "direction": "asc"})
    if not isinstance(prs, list):
        return prs
    stale = [p for p in prs if _age_days(p.get("updated_at")) >= stale_days]
    return [
        {
            "number":            p["number"],
            "title":             p["title"],
            "author":            p["user"]["login"],
            "days_since_update": _age_days(p.get("updated_at")),
            "url":               p["html_url"]
        }
        for p in stale
    ]


def get_pr_merge_time_trend(repo: str, weeks: int = 8) -> list:
    from collections import defaultdict
    prs = _pages(f"repos/{repo}/pulls", {"state": "closed"}, 200)
    merged = [p for p in prs if p.get("merged_at")]

    weekly = defaultdict(list)
    for p in merged:
        dt = _parse_dt(p["merged_at"])
        week = dt.strftime("%Y-W%W")
        t = _merge_minutes(p)
        if t:
            weekly[week].append(t)

    sorted_weeks = sorted(weekly.keys())[-weeks:]
    return [
        {
            "week":            w,
            "pr_count":        len(weekly[w]),
            "median_merge_hrs": round(sorted(weekly[w])[len(weekly[w])//2] / 60, 1)
        }
        for w in sorted_weeks
    ]


def get_pr_review_stats(repo: str, limit: int = 100) -> dict:
    from collections import defaultdict
    prs = _pages(f"repos/{repo}/pulls", {"state": "closed"}, limit)
    reviewer_stats = defaultdict(lambda: {"approvals": 0, "changes_requested": 0, "total": 0})

    for p in prs:
        reviews = _gh_get(f"repos/{repo}/pulls/{p['number']}/reviews")
        if not isinstance(reviews, list):
            continue
        for r in reviews:
            login = r.get("user", {}).get("login", "unknown")
            state = r.get("state", "")
            reviewer_stats[login]["total"] += 1
            if state == "APPROVED":
                reviewer_stats[login]["approvals"] += 1
            elif state == "CHANGES_REQUESTED":
                reviewer_stats[login]["changes_requested"] += 1

    leaderboard = sorted(
        [{"reviewer": k, **v, "approval_rate": f"{round(v['approvals']/v['total']*100)}%" if v['total'] else "N/A"}
         for k, v in reviewer_stats.items()],
        key=lambda x: x["total"], reverse=True
    )
    return {"repo": repo, "reviewers_analysed": len(leaderboard), "leaderboard": leaderboard[:10]}


def get_contributor_pr_stats(repo: str, limit: int = 200) -> list:
    from collections import defaultdict
    prs = _pages(f"repos/{repo}/pulls", {"state": "closed"}, limit)
    stats = defaultdict(lambda: {"opened": 0, "merged": 0, "closed_unmerged": 0, "merge_times_hrs": []})

    for p in prs:
        author = p.get("user", {}).get("login", "unknown")
        stats[author]["opened"] += 1
        if p.get("merged_at"):
            stats[author]["merged"] += 1
            t = _merge_minutes(p)
            if t:
                stats[author]["merge_times_hrs"].append(round(t / 60, 1))
        else:
            stats[author]["closed_unmerged"] += 1

    result = []
    for author, s in stats.items():
        times = s["merge_times_hrs"]
        result.append({
            "author":          author,
            "opened":          s["opened"],
            "merged":          s["merged"],
            "closed_unmerged": s["closed_unmerged"],
            "merge_rate":      f"{round(s['merged']/s['opened']*100)}%" if s["opened"] else "N/A",
            "avg_merge_hrs":   round(sum(times)/len(times), 1) if times else "N/A"
        })
    return sorted(result, key=lambda x: x["opened"], reverse=True)


def get_pr_detail(repo: str, pr_number: int) -> dict:
    pr      = _gh_get(f"repos/{repo}/pulls/{pr_number}")
    commits = _gh_get(f"repos/{repo}/pulls/{pr_number}/commits")
    files   = _gh_get(f"repos/{repo}/pulls/{pr_number}/files")
    reviews = _gh_get(f"repos/{repo}/pulls/{pr_number}/reviews")

    return {
        "number":        pr_number,
        "title":         pr.get("title"),
        "author":        pr.get("user", {}).get("login"),
        "state":         pr.get("state"),
        "draft":         pr.get("draft"),
        "created_at":    pr.get("created_at"),
        "merged_at":     pr.get("merged_at"),
        "merge_time_hrs":_merge_minutes(pr) / 60 if _merge_minutes(pr) else None,
        "commits":       len(commits) if isinstance(commits, list) else "N/A",
        "files_changed": len(files)   if isinstance(files, list)   else "N/A",
        "additions":     pr.get("additions"),
        "deletions":     pr.get("deletions"),
        "reviews":       len(reviews) if isinstance(reviews, list) else "N/A",
        "review_states": list({r.get("state") for r in reviews}) if isinstance(reviews, list) else [],
        "url":           pr.get("html_url")
    }


# ── Tool Router ────────────────────────────────────────────────────────────────

def execute_tool(name: str, inputs: dict) -> str:
    print(f"  → Calling: {name}({inputs})")
    try:
        if name == "get_pr_summary":
            result = get_pr_summary(inputs["repo"], inputs.get("limit", 100))
        elif name == "list_open_prs":
            result = list_open_prs(inputs["repo"], inputs.get("sort", "created"))
        elif name == "get_stale_prs":
            result = get_stale_prs(inputs["repo"], inputs.get("stale_days", 14))
        elif name == "get_pr_merge_time_trend":
            result = get_pr_merge_time_trend(inputs["repo"], inputs.get("weeks", 8))
        elif name == "get_pr_review_stats":
            result = get_pr_review_stats(inputs["repo"], inputs.get("limit", 100))
        elif name == "get_contributor_pr_stats":
            result = get_contributor_pr_stats(inputs["repo"], inputs.get("limit", 200))
        elif name == "get_pr_detail":
            result = get_pr_detail(inputs["repo"], inputs["pr_number"])
        else:
            result = {"error": f"Unknown tool: {name}"}
    except Exception as e:
        result = {"error": str(e)}
    return json.dumps(result, indent=2)


# ── Agentic Loop ───────────────────────────────────────────────────────────────

def run_github_pr_agent(repo: str, pr_number: int = None) -> str:
    """
    Run the GitHub PR analytics agent for the given repo (and optional PR).
    Returns the final summary as a string.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    system_prompt = (
        "You are a GitHub PR analytics expert. When asked to analyze a repo, "
        "run ALL 7 tools: get_pr_summary, list_open_prs, get_stale_prs, "
        "get_pr_merge_time_trend, get_pr_review_stats, get_contributor_pr_stats, "
        "and get_pr_detail (if a PR number is provided). "
        "Provide a structured report with: 1) PR Summary  2) Open PRs  "
        "3) Stale PRs  4) Merge Time Trend  5) Review Stats  "
        "6) Contributor Breakdown  7) PR Detail (if applicable)  8) Recommendations."
    )

    user_msg = f"Analyze GitHub PR data for repo '{repo}'."
    if pr_number:
        user_msg += f" Also get deep detail for PR #{pr_number}."
    user_msg += " Run all applicable tools and give a full report."

    messages = [{"role": "user", "content": user_msg}]

    print(f"\n{'='*60}")
    print(f"  GitHub PR Agent  |  {repo}")
    if pr_number:
        print(f"  PR Detail        |  #{pr_number}")
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
    parser = argparse.ArgumentParser(description="GitHub PR Analytics Agent")
    parser.add_argument("--repo", required=True, help="owner/repo")
    parser.add_argument("--pr",   type=int,      help="PR number for deep detail (optional)")
    args = parser.parse_args()

    if not ANTHROPIC_API_KEY:
        print("ERROR: Set ANTHROPIC_API_KEY environment variable")
        exit(1)

    report = run_github_pr_agent(args.repo, args.pr)
    print("\n" + report)