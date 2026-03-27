# github_pr_mcp_server.py
# Requirements: pip install mcp PyGithub python-dotenv

import os
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
from github import Github, Auth
from mcp.server.fastmcp import FastMCP

load_dotenv()

auth = Auth.Token(os.getenv("GITHUB_TOKEN"))
g = Github(auth=auth)

mcp = FastMCP("github-pr-analytics")

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def hours_between(dt1, dt2):
    if dt1 and dt2:
        if dt1.tzinfo is None:
            dt1 = dt1.replace(tzinfo=timezone.utc)
        if dt2.tzinfo is None:
            dt2 = dt2.replace(tzinfo=timezone.utc)
        return round(abs((dt2 - dt1).total_seconds()) / 3600, 2)
    return None

def format_pr(pr):
    return {
        "number": pr.number,
        "title": pr.title,
        "author": pr.user.login,
        "state": pr.state,
        "created_at": pr.created_at.isoformat(),
        "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
        "closed_at": pr.closed_at.isoformat() if pr.closed_at else None,
        "open_hours": hours_between(pr.created_at, pr.merged_at or pr.closed_at or datetime.now(timezone.utc)),
        "url": pr.html_url,
    }

# ─────────────────────────────────────────────
# TOOLS
# ─────────────────────────────────────────────

@mcp.tool()
def get_prs_by_user(repo: str, username: str, state: str = "all") -> str:
    """Get all PRs raised by a specific GitHub user in a repo. repo format: owner/repo-name"""
    r = g.get_repo(repo)
    prs = [format_pr(pr) for pr in r.get_pulls(state=state) if pr.user.login == username]
    return json.dumps({"user": username, "total": len(prs), "prs": prs}, indent=2)


@mcp.tool()
def get_top_contributors(repo: str, top_n: int = 5) -> str:
    """Get top PR contributors in a repo ranked by number of PRs. repo format: owner/repo-name"""
    r = g.get_repo(repo)
    counts = {}
    for pr in r.get_pulls(state="all"):
        user = pr.user.login
        counts[user] = counts.get(user, 0) + 1
    sorted_c = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:top_n]
    return json.dumps({"top_contributors": [{"user": u, "pr_count": c} for u, c in sorted_c]}, indent=2)


@mcp.tool()
def get_pr_merge_time(repo: str, limit: int = 50) -> str:
    """Get average time to merge PRs in a repo (in hours). repo format: owner/repo-name"""
    r = g.get_repo(repo)
    times = []
    for pr in r.get_pulls(state="closed")[:limit]:
        if pr.merged_at:
            times.append(hours_between(pr.created_at, pr.merged_at))
    avg = round(sum(times) / len(times), 2) if times else None
    return json.dumps({"average_merge_time_hours": avg, "prs_analyzed": len(times)}, indent=2)


@mcp.tool()
def get_stale_prs(repo: str, days: int = 7) -> str:
    """List PRs that have been open for more than N days with no activity. repo format: owner/repo-name"""
    r = g.get_repo(repo)
    now = datetime.now(timezone.utc)
    stale = []
    for pr in r.get_pulls(state="open"):
        updated = pr.updated_at.replace(tzinfo=timezone.utc) if pr.updated_at.tzinfo is None else pr.updated_at
        age = (now - updated).days
        if age >= days:
            stale.append({**format_pr(pr), "days_since_activity": age})
    return json.dumps({"stale_prs": stale, "total": len(stale)}, indent=2)


@mcp.tool()
def get_open_prs(repo: str) -> str:
    """List all currently open PRs in a repo. repo format: owner/repo-name"""
    r = g.get_repo(repo)
    prs = [format_pr(pr) for pr in r.get_pulls(state="open")]
    return json.dumps({"open_prs": prs, "total": len(prs)}, indent=2)


@mcp.tool()
def get_merged_vs_closed(repo: str, limit: int = 100) -> str:
    """Compare how many PRs were merged vs closed without merging. repo format: owner/repo-name"""
    r = g.get_repo(repo)
    merged, closed = 0, 0
    for pr in r.get_pulls(state="closed")[:limit]:
        if pr.merged_at:
            merged += 1
        else:
            closed += 1
    return json.dumps({"merged": merged, "closed_without_merge": closed, "total_analyzed": merged + closed}, indent=2)


@mcp.tool()
def get_pr_size_stats(repo: str, top_n: int = 10) -> str:
    """Get PRs ranked by lines of code changed (additions + deletions). repo format: owner/repo-name"""
    r = g.get_repo(repo)
    pr_sizes = []
    for pr in r.get_pulls(state="all")[:50]:
        pr_sizes.append({
            "number": pr.number,
            "title": pr.title,
            "author": pr.user.login,
            "additions": pr.additions,
            "deletions": pr.deletions,
            "total_changes": pr.additions + pr.deletions,
            "url": pr.html_url,
        })
    pr_sizes.sort(key=lambda x: x["total_changes"], reverse=True)
    return json.dumps({"largest_prs": pr_sizes[:top_n]}, indent=2)


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")