"""
╔══════════════════════════════════════════════════════════════╗
║         GitHub PR Analytics + SonarQube MCP Server          ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  GitHub tools (7):                                           ║
║    • get_pr_summary           high-level PR counts/rates     ║
║    • list_open_prs            all open PRs with status       ║
║    • get_pr_detail            deep dive into one PR          ║
║    • get_contributor_pr_stats per-author breakdown           ║
║    • get_pr_review_stats      reviewer leaderboard           ║
║    • get_pr_merge_time_trend  weekly merge-time chart        ║
║    • get_stale_prs            PRs with no recent activity    ║
║                                                              ║
║  SonarQube tools (4):                                        ║
║    • get_sonar_pr_quality     quality gate for a PR          ║
║    • get_sonar_branch_health  main branch health metrics     ║
║    • get_sonar_pr_issues      new issues introduced by PR    ║
║    • get_sonar_pr_vs_main     PR vs main branch delta        ║
║                                                              ║
║  Environment variables required:                             ║
║    GITHUB_TOKEN      GitHub personal access token            ║
║    SONARCLOUD_TOKEN  SonarCloud token                        ║
║                      My Account > Security > Generate Token  ║
╚══════════════════════════════════════════════════════════════╝
"""

import asyncio
import importlib
import os
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


# ══════════════════════════════════════════════════════════════════════════════
#  SERVER INSTANCE & CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

app = Server("github-pr-analytics")

GITHUB_API   = "https://api.github.com"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

SONAR_BASE  = "https://sonarcloud.io/api"
SONAR_TOKEN = os.getenv("SONARCLOUD_TOKEN", "")


# ══════════════════════════════════════════════════════════════════════════════
#  HTTP HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _headers() -> dict:
    h = {"Accept": "application/vnd.github.v3+json", "User-Agent": "github-pr-mcp/1.0"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"token {GITHUB_TOKEN}"
    return h

def _sonar_headers() -> dict:
    h = {"Content-Type": "application/json"}
    if SONAR_TOKEN:
        h["Authorization"] = f"Bearer {SONAR_TOKEN}"
    return h

async def gh_get(client: httpx.AsyncClient, path: str, params: dict = None) -> Any:
    r = await client.get(f"{GITHUB_API}{path}", headers=_headers(), params=params or {})
    r.raise_for_status()
    return r.json()

async def gh_get_all(client: httpx.AsyncClient, path: str, params: dict = None, max_pages: int = 5) -> list:
    items, p = [], {**(params or {}), "per_page": 100, "page": 1}
    for _ in range(max_pages):
        data = await gh_get(client, path, p)
        if not data: break
        items.extend(data)
        if len(data) < 100: break
        p["page"] += 1
    return items

async def sonar_get(client: httpx.AsyncClient, endpoint: str, params: dict = None) -> Any:
    r = await client.get(f"{SONAR_BASE}/{endpoint}", headers=_sonar_headers(), params=params or {})
    r.raise_for_status()
    return r.json()


# ══════════════════════════════════════════════════════════════════════════════
#  FORMATTING HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

def _age(created: str) -> str:
    d = datetime.now(timezone.utc) - _iso(created)
    if d.days >= 365: return f"{d.days//365}y {(d.days%365)//30}m"
    if d.days >= 30:  return f"{d.days//30}m {d.days%30}d"
    return f"{d.days}d {d.seconds//3600}h"

def _htime(h: float) -> str:
    if not h: return "N/A"
    return f"{int(h//24)}d {int(h%24)}h" if h >= 24 else f"{int(h)}h {int((h%1)*60)}m"

def _bar(val: int, mx: int, w: int = 22) -> str:
    f = int((val / mx) * w) if mx else 0
    return "█" * f + "░" * (w - f)

def _section(title: str) -> str:
    return f"\n{'═'*58}\n   {title}\n{'═'*58}"

def _to_rating(val: str) -> str:
    try:
        return {"1": "A", "2": "B", "3": "C", "4": "D", "5": "E"}[str(int(float(val)))]
    except Exception:
        return val

DIV  = "  " + "─" * 54
DIV2 = "  " + "─" * 52

SEVERITY_ICON = {
    "BLOCKER":  "🔴",
    "CRITICAL": "🟠",
    "MAJOR":    "🟡",
    "MINOR":    "🔵",
    "INFO":     "⚪",
}


# ══════════════════════════════════════════════════════════════════════════════
#  TOOL REGISTRY  — 7 GitHub + 4 SonarQube = 11 tools total
# ══════════════════════════════════════════════════════════════════════════════

TOOLS = [

    # ── GitHub tools ──────────────────────────────────────────────────────────

    Tool(
        name="get_pr_summary",
        description="High-level PR analytics: open/closed/merged counts, avg merge time, merge rate, top labels.",
        inputSchema={"type": "object", "properties": {
            "repo":  {"type": "string",  "description": "owner/repo  e.g. facebook/react"},
            "limit": {"type": "integer", "description": "Max closed PRs to analyse (default 100)", "default": 100},
        }, "required": ["repo"]},
    ),

    Tool(
        name="list_open_prs",
        description="List every currently open PR with age, author, draft status, labels, and review state.",
        inputSchema={"type": "object", "properties": {
            "repo": {"type": "string", "description": "owner/repo"},
            "sort": {"type": "string", "enum": ["created", "updated", "popularity", "long-running"], "default": "created"},
        }, "required": ["repo"]},
    ),

    Tool(
        name="get_pr_detail",
        description="Deep analytics for a single PR: commits, files changed, review timeline, merge time.",
        inputSchema={"type": "object", "properties": {
            "repo":      {"type": "string",  "description": "owner/repo"},
            "pr_number": {"type": "integer", "description": "Pull request number"},
        }, "required": ["repo", "pr_number"]},
    ),

    Tool(
        name="get_contributor_pr_stats",
        description="Per-author PR breakdown: opened, merged, closed, merge rate, avg merge time.",
        inputSchema={"type": "object", "properties": {
            "repo":  {"type": "string",  "description": "owner/repo"},
            "limit": {"type": "integer", "description": "Max PRs to analyse (default 200)", "default": 200},
        }, "required": ["repo"]},
    ),

    Tool(
        name="get_pr_review_stats",
        description="Review analytics: reviewer leaderboard, approval rate, change-request ratio.",
        inputSchema={"type": "object", "properties": {
            "repo":  {"type": "string",  "description": "owner/repo"},
            "limit": {"type": "integer", "description": "Max closed PRs to analyse (default 100)", "default": 100},
        }, "required": ["repo"]},
    ),

    Tool(
        name="get_pr_merge_time_trend",
        description="Weekly trend of PR volume and median merge-time over past N weeks.",
        inputSchema={"type": "object", "properties": {
            "repo":  {"type": "string",  "description": "owner/repo"},
            "weeks": {"type": "integer", "description": "Number of weeks to look back (default 8)", "default": 8},
        }, "required": ["repo"]},
    ),

    Tool(
        name="get_stale_prs",
        description="Find open PRs with no activity for more than N days.",
        inputSchema={"type": "object", "properties": {
            "repo":       {"type": "string",  "description": "owner/repo"},
            "stale_days": {"type": "integer", "description": "Inactivity threshold in days (default 14)", "default": 14},
        }, "required": ["repo"]},
    ),

    # ── SonarQube tools ───────────────────────────────────────────────────────

    Tool(
        name="get_sonar_pr_quality",
        description=(
            "Fetch the SonarQube quality gate result for a specific pull request. "
            "Shows PASSED/FAILED and which conditions triggered a failure. "
            "Requires SONARCLOUD_TOKEN environment variable."
        ),
        inputSchema={"type": "object", "properties": {
            "project_key": {"type": "string",  "description": "SonarQube project key (visible on SonarCloud dashboard)"},
            "pr_number":   {"type": "integer", "description": "GitHub pull request number"},
        }, "required": ["project_key", "pr_number"]},
    ),

    Tool(
        name="get_sonar_branch_health",
        description=(
            "Get overall code quality health of the main branch: bugs, vulnerabilities, "
            "code smells, coverage, duplications, security hotspots, and A-E ratings. "
            "Requires SONARCLOUD_TOKEN environment variable."
        ),
        inputSchema={"type": "object", "properties": {
            "project_key": {"type": "string", "description": "SonarQube project key"},
        }, "required": ["project_key"]},
    ),

    Tool(
        name="get_sonar_pr_issues",
        description=(
            "List all new issues introduced by a PR with severity icons, "
            "type, message, and exact file + line number. "
            "Requires SONARCLOUD_TOKEN environment variable."
        ),
        inputSchema={"type": "object", "properties": {
            "project_key": {"type": "string",  "description": "SonarQube project key"},
            "pr_number":   {"type": "integer", "description": "GitHub pull request number"},
        }, "required": ["project_key", "pr_number"]},
    ),

    Tool(
        name="get_sonar_pr_vs_main",
        description=(
            "Side-by-side comparison of a PR's code quality against the main branch. "
            "Shows delta for bugs, vulnerabilities, code smells, coverage, duplications, "
            "and security hotspots. Ends with a merge verdict. "
            "Requires SONARCLOUD_TOKEN environment variable."
        ),
        inputSchema={"type": "object", "properties": {
            "project_key": {"type": "string",  "description": "SonarQube project key"},
            "pr_number":   {"type": "integer", "description": "GitHub pull request number"},
        }, "required": ["project_key", "pr_number"]},
    ),
]


# ══════════════════════════════════════════════════════════════════════════════
#  GITHUB HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

async def handle_get_pr_summary(repo: str, limit: int = 100) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        open_prs   = await gh_get_all(client, f"/repos/{repo}/pulls", {"state": "open"})
        closed_prs = (await gh_get_all(client, f"/repos/{repo}/pulls", {"state": "closed"}))[:limit]
        merged     = [p for p in closed_prs if p.get("merged_at")]
        unmerged   = [p for p in closed_prs if not p.get("merged_at")]

        times = []
        for p in merged:
            try: times.append((_iso(p["merged_at"]) - _iso(p["created_at"])).total_seconds() / 3600)
            except: pass
        avg_h = sum(times) / len(times) if times else 0

        freq: dict[str, int] = {}
        for p in open_prs + closed_prs:
            for lbl in p.get("labels", []): freq[lbl["name"]] = freq.get(lbl["name"], 0) + 1
        top = sorted(freq.items(), key=lambda x: -x[1])[:6]

        total      = len(open_prs) + len(merged) + len(unmerged)
        merge_rate = round(100 * len(merged) / total, 1) if total else 0

        out = [
            _section(f"PR SUMMARY  |  {repo}"),
            "",
            f"  {'Metric':<32} Value",
            DIV,
            f"  {'Open PRs':<32} {len(open_prs)}",
            f"  {'Merged PRs':<32} {len(merged)}",
            f"  {'Closed (not merged)':<32} {len(unmerged)}",
            f"  {'Total Analysed':<32} {total}",
            f"  {'Merge Rate':<32} {merge_rate}%",
            f"  {'Avg Merge Time':<32} {_htime(avg_h)}",
            "",
            "  PR Status Breakdown",
            DIV,
            f"  Open   [{_bar(len(open_prs), total)}] {len(open_prs):>4}",
            f"  Merged [{_bar(len(merged),   total)}] {len(merged):>4}",
            f"  Closed [{_bar(len(unmerged), total)}] {len(unmerged):>4}",
        ]
        if top:
            out += ["", "  Top Labels", DIV]
            mx = top[0][1]
            for lbl, cnt in top:
                out.append(f"  {lbl:<30} [{_bar(cnt, mx, 14)}] {cnt}")
        out.append("")
        return "\n".join(out)


async def handle_list_open_prs(repo: str, sort: str = "created") -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        prs  = await gh_get_all(client, f"/repos/{repo}/pulls", {"state": "open", "sort": sort})
        rows = []
        for p in prs:
            revs     = await gh_get(client, f"/repos/{repo}/pulls/{p['number']}/reviews")
            approved = sum(1 for r in revs if r["state"] == "APPROVED")
            changes  = sum(1 for r in revs if r["state"] == "CHANGES_REQUESTED")
            rows.append((p, approved, changes))

        if sort == "long-running":
            rows.sort(key=lambda x: _iso(x[0]["created_at"]))

        out = [_section(f"OPEN PULL REQUESTS  |  {repo}"), f"  Total open: {len(rows)}   sorted by: {sort}", ""]
        for p, approved, changes in rows:
            draft  = " [DRAFT]" if p.get("draft") else ""
            labels = ("  Labels: " + ", ".join(l["name"] for l in p.get("labels", []))) if p.get("labels") else ""
            if approved:  review_status = f"APPROVED ({approved})"
            elif changes: review_status = f"CHANGES REQUESTED ({changes})"
            else:         review_status = "Awaiting review"
            out += [
                f"  #{p['number']}  {p['title']}{draft}",
                f"    Author : {p['user']['login']}",
                f"    Age    : {_age(p['created_at'])} old   |   Updated {_age(p['updated_at'])} ago",
                f"    Review : {review_status}{labels}",
                f"    URL    : {p['html_url']}",
                DIV2,
            ]
        out.append("")
        return "\n".join(out)


async def handle_get_pr_detail(repo: str, pr_number: int) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        pr      = await gh_get(client, f"/repos/{repo}/pulls/{pr_number}")
        commits = await gh_get(client, f"/repos/{repo}/pulls/{pr_number}/commits")
        reviews = await gh_get(client, f"/repos/{repo}/pulls/{pr_number}/reviews")
        files   = await gh_get(client, f"/repos/{repo}/pulls/{pr_number}/files")

        merge_time  = "Not merged"
        if pr.get("merged_at"):
            h = (_iso(pr["merged_at"]) - _iso(pr["created_at"])).total_seconds() / 3600
            merge_time = _htime(h)

        state_label = "MERGED" if pr.get("merged_at") else pr["state"].upper()
        labels      = ", ".join(l["name"] for l in pr.get("labels", [])) or "none"

        out = [
            _section(f"PR DETAIL  |  {repo}  |  #{pr_number}"), "",
            f"  {pr['title']}",
            f"  Status  : {state_label}{'  [DRAFT]' if pr.get('draft') else ''}", "",
            f"  {'Author':<20} {pr['user']['login']}",
            f"  {'Created':<20} {pr['created_at'][:10]}  ({_age(pr['created_at'])} ago)",
            f"  {'Merged At':<20} {pr['merged_at'][:10] if pr.get('merged_at') else 'N/A'}",
            f"  {'Time to Merge':<20} {merge_time}",
            f"  {'Labels':<20} {labels}", "",
            "  Code Changes", DIV,
            f"  {'Commits':<20} {len(commits)}",
            f"  {'Files Changed':<20} {pr.get('changed_files', len(files))}",
            f"  {'Additions':<20} +{pr.get('additions', 0)}",
            f"  {'Deletions':<20} -{pr.get('deletions', 0)}",
            f"  {'Net Lines':<20} {pr.get('additions', 0) - pr.get('deletions', 0):+}",
        ]

        if reviews:
            state_map = {"APPROVED": "APPROVED", "CHANGES_REQUESTED": "CHANGES REQUESTED", "COMMENTED": "COMMENTED"}
            out += ["", "  Review Timeline", DIV]
            for r in reviews:
                out.append(f"  {r['user']['login']:<22} {state_map.get(r['state'], r['state']):<24} {r['submitted_at'][:10]}")

        if files:
            out += ["", "  Files Changed (top 10)", DIV]
            for f in files[:10]:
                out.append(f"  [{f['status'].upper():<8}] {f['filename'][:46]:<46}  +{f['additions']} -{f['deletions']}")

        out += ["", f"  URL : {pr['html_url']}", ""]
        return "\n".join(out)


async def handle_get_contributor_pr_stats(repo: str, limit: int = 200) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        closed  = await gh_get_all(client, f"/repos/{repo}/pulls", {"state": "closed"})
        open_p  = await gh_get_all(client, f"/repos/{repo}/pulls", {"state": "open"})
        all_prs = (open_p + closed)[:limit]

        stats: dict[str, dict] = {}
        for p in all_prs:
            a = p["user"]["login"]
            if a not in stats:
                stats[a] = {"opened": 0, "merged": 0, "closed": 0, "times": []}
            stats[a]["opened"] += 1
            if p.get("merged_at"):
                stats[a]["merged"] += 1
                stats[a]["times"].append((_iso(p["merged_at"]) - _iso(p["created_at"])).total_seconds() / 3600)
            elif p["state"] == "closed":
                stats[a]["closed"] += 1

        rows = sorted(
            [(a, s["opened"], s["merged"], s["closed"], sum(s["times"])/len(s["times"]) if s["times"] else 0)
             for a, s in stats.items()],
            key=lambda x: -x[1]
        )
        max_opened = rows[0][1] if rows else 1

        out = [
            _section(f"CONTRIBUTOR PR STATS  |  {repo}"),
            f"  {len(rows)} contributors  |  {len(all_prs)} PRs analysed", "",
            f"  {'Author':<22} {'Opened':>7} {'Merged':>7} {'Closed':>7} {'Rate':>6}  {'Avg Merge Time':<16}  Activity",
            DIV,
        ]
        for author, opened, merged, closed, avg_h in rows[:20]:
            rate = f"{round(100*merged/opened)}%" if opened else "0%"
            out.append(f"  {author:<22} {opened:>7} {merged:>7} {closed:>7} {rate:>6}  {_htime(avg_h):<16}  [{_bar(opened, max_opened, 10)}]")
        out.append("")
        return "\n".join(out)


async def handle_get_pr_review_stats(repo: str, limit: int = 100) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        prs           = (await gh_get_all(client, f"/repos/{repo}/pulls", {"state": "closed"}))[:limit]
        rv_stats: dict[str, dict] = {}
        total_reviews = 0
        rpp:          list[int]   = []
        approvals     = change_reqs = 0

        for p in prs:
            revs = await gh_get(client, f"/repos/{repo}/pulls/{p['number']}/reviews")
            rpp.append(len(revs))
            total_reviews += len(revs)
            for r in revs:
                rv = r["user"]["login"]
                if rv not in rv_stats:
                    rv_stats[rv] = {"reviews": 0, "approvals": 0, "changes": 0}
                rv_stats[rv]["reviews"] += 1
                if r["state"] == "APPROVED":
                    rv_stats[rv]["approvals"] += 1; approvals += 1
                elif r["state"] == "CHANGES_REQUESTED":
                    rv_stats[rv]["changes"] += 1;   change_reqs += 1

        avg_rev  = round(sum(rpp) / len(rpp), 1) if rpp else 0
        app_rate = round(100 * approvals / total_reviews, 1) if total_reviews else 0
        board    = sorted(rv_stats.items(), key=lambda x: -x[1]["reviews"])[:10]
        max_rev  = board[0][1]["reviews"] if board else 1

        out = [
            _section(f"PR REVIEW STATS  |  {repo}"), "",
            f"  {'PRs Analysed':<30} {len(prs)}",
            f"  {'Total Reviews':<30} {total_reviews}",
            f"  {'Avg Reviews per PR':<30} {avg_rev}",
            f"  {'Total Approvals':<30} {approvals}",
            f"  {'Total Change Requests':<30} {change_reqs}",
            f"  {'Approval Rate':<30} {app_rate}%", "",
            "  Reviewer Leaderboard", DIV,
            f"  {'Reviewer':<22} {'Reviews':>8} {'Approved':>9} {'Changes':>8}  Activity", DIV,
        ]
        for rv, s in board:
            out.append(f"  {rv:<22} {s['reviews']:>8} {s['approvals']:>9} {s['changes']:>8}  [{_bar(s['reviews'], max_rev, 12)}]")
        out.append("")
        return "\n".join(out)


async def handle_get_pr_merge_time_trend(repo: str, weeks: int = 8) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        closed = await gh_get_all(client, f"/repos/{repo}/pulls", {"state": "closed"})
        merged = [p for p in closed if p.get("merged_at")]
        now    = datetime.now(timezone.utc)

        buckets: dict[str, list] = {}
        for i in range(weeks):
            ws = now - timedelta(weeks=i+1); we = now - timedelta(weeks=i)
            label = ws.strftime("%b %d")
            buckets[label] = [
                (_iso(p["merged_at"]) - _iso(p["created_at"])).total_seconds() / 3600
                for p in merged if ws <= _iso(p["merged_at"]) < we
            ]

        trend   = [(label, len(t), sorted(t)[len(t)//2] if t else 0) for label, t in reversed(list(buckets.items()))]
        max_prs = max(t[1] for t in trend) or 1

        out = [_section(f"PR MERGE TIME TREND  |  {repo}"), f"  Last {weeks} weeks", "",
               f"  {'Week':<10} {'PRs':>5}  Volume               Median Merge Time", DIV]
        for label, count, median in trend:
            out.append(f"  {label:<10} {count:>5}  [{_bar(count, max_prs, 14)}]  {_htime(median)}")

        total_m = sum(t[1] for t in trend)
        avg_med = sum(t[2] for t in trend) / len(trend) if trend else 0
        out += ["", f"  {'Total PRs merged':<30} {total_m}", f"  {'Overall avg median time':<30} {_htime(avg_med)}", ""]
        return "\n".join(out)


async def handle_get_stale_prs(repo: str, stale_days: int = 14) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        prs    = await gh_get_all(client, f"/repos/{repo}/pulls", {"state": "open"})
        now    = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=stale_days)
        stale  = sorted(
            [(p, (now - _iso(p["updated_at"])).days) for p in prs if _iso(p["updated_at"]) < cutoff],
            key=lambda x: -x[1]
        )

        out = [_section(f"STALE PRs  |  {repo}"),
               f"  Threshold : no activity > {stale_days} days",
               f"  Found     : {len(stale)} stale of {len(prs)} open PRs", ""]
        if not stale:
            out.append("  No stale PRs found!\n")
            return "\n".join(out)

        for p, idle in stale:
            labels = ("  Labels : " + ", ".join(l["name"] for l in p.get("labels", []))) if p.get("labels") else ""
            out += [
                f"  #{p['number']}  {p['title']}",
                f"    Author  : {p['user']['login']}",
                f"    Idle    : {idle} days   |   Opened {_age(p['created_at'])} ago",
                f"    {labels}",
                f"    URL     : {p['html_url']}",
                DIV2,
            ]
        out.append("")
        return "\n".join(out)


# ══════════════════════════════════════════════════════════════════════════════
#  SONARQUBE HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

async def handle_get_sonar_pr_quality(project_key: str, pr_number: int) -> str:
    if not SONAR_TOKEN:
        return "  ⚠  SONARCLOUD_TOKEN env var is not set. Please add it to your environment.\n"
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            data = await sonar_get(client, "qualitygates/project_status", {
                "projectKey": project_key, "pullRequest": str(pr_number),
            })
        except httpx.HTTPStatusError as e:
            return f"  SonarQube API error {e.response.status_code}: {e.response.text[:300]}\n"

        status    = data.get("projectStatus", {})
        gate      = status.get("status", "UNKNOWN")
        gate_icon = "✅ PASSED" if gate == "OK" else "❌ FAILED"

        out = [
            _section(f"SONAR PR QUALITY GATE  |  {project_key}  |  PR #{pr_number}"), "",
            f"  Quality Gate : {gate_icon}", "",
            f"  {'Metric':<35} {'Status':<10} {'Actual':>10}  {'Threshold':>10}", DIV,
        ]
        for c in status.get("conditions", []):
            c_status = "✅ OK" if c["status"] == "OK" else "❌ FAIL"
            metric   = c.get("metricKey", "").replace("_", " ").title()
            out.append(f"  {metric:<35} {c_status:<10} {c.get('actualValue','N/A'):>10}  {c.get('errorThreshold','N/A'):>10}")
        out.append("")
        return "\n".join(out)


async def handle_get_sonar_branch_health(project_key: str) -> str:
    if not SONAR_TOKEN:
        return "  ⚠  SONARCLOUD_TOKEN env var is not set. Please add it to your environment.\n"
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            data = await sonar_get(client, "measures/component", {
                "component":  project_key,
                "metricKeys": "bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density,security_hotspots,reliability_rating,security_rating,sqale_rating",
            })
        except httpx.HTTPStatusError as e:
            return f"  SonarQube API error {e.response.status_code}: {e.response.text[:300]}\n"

        m = {x["metric"]: x.get("value", "N/A") for x in data.get("component", {}).get("measures", [])}
        out = [
            _section(f"SONAR BRANCH HEALTH  |  {project_key}"), "",
            f"  {'Metric':<35} Value", DIV,
            f"  {'Bugs':<35} {m.get('bugs','N/A')}",
            f"  {'Vulnerabilities':<35} {m.get('vulnerabilities','N/A')}",
            f"  {'Security Hotspots':<35} {m.get('security_hotspots','N/A')}",
            f"  {'Code Smells':<35} {m.get('code_smells','N/A')}",
            f"  {'Coverage':<35} {m.get('coverage','N/A')}%",
            f"  {'Duplicated Lines Density':<35} {m.get('duplicated_lines_density','N/A')}%", "",
            "  Ratings  (A = best   E = worst)", DIV,
            f"  {'Reliability  (Bugs)':<35} {_to_rating(m.get('reliability_rating','N/A'))}",
            f"  {'Security     (Vulnerabilities)':<35} {_to_rating(m.get('security_rating','N/A'))}",
            f"  {'Maintainability (Code Smells)':<35} {_to_rating(m.get('sqale_rating','N/A'))}", "",
        ]
        return "\n".join(out)


async def handle_get_sonar_pr_issues(project_key: str, pr_number: int) -> str:
    if not SONAR_TOKEN:
        return "  ⚠  SONARCLOUD_TOKEN env var is not set. Please add it to your environment.\n"
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            data = await sonar_get(client, "issues/search", {
                "componentKeys": project_key, "pullRequest": str(pr_number),
                "resolved": "false", "ps": "50",
            })
        except httpx.HTTPStatusError as e:
            return f"  SonarQube API error {e.response.status_code}: {e.response.text[:300]}\n"

        issues = data.get("issues", [])
        total  = data.get("total", 0)
        by_type: dict[str, int] = {}
        by_sev:  dict[str, int] = {}
        for iss in issues:
            by_type[iss.get("type","UNKNOWN")]     = by_type.get(iss.get("type","UNKNOWN"), 0) + 1
            by_sev[iss.get("severity","UNKNOWN")]  = by_sev.get(iss.get("severity","UNKNOWN"), 0) + 1

        out = [_section(f"SONAR PR ISSUES  |  {project_key}  |  PR #{pr_number}"), "",
               f"  Total new issues : {total}  (showing up to 50)", "", "  By Type", DIV]
        for t, cnt in sorted(by_type.items(), key=lambda x: -x[1]):
            out.append(f"  {t:<30} {cnt}")
        out += ["", "  By Severity", DIV]
        for sev in ["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO"]:
            cnt = by_sev.get(sev, 0)
            if cnt:
                out.append(f"  {SEVERITY_ICON.get(sev,'')} {sev:<28} {cnt}")
        if issues:
            out += ["", "  Issue Details (top 20)", DIV]
            for iss in issues[:20]:
                sev  = iss.get("severity", "")
                comp = iss.get("component", "").split(":")[-1]
                out += [
                    f"  {SEVERITY_ICON.get(sev,'')} [{sev:<8}] {iss.get('type','')}",
                    f"    {iss.get('message','')[:55]}",
                    f"    📁 {comp}  line {iss.get('line','?')}", "",
                ]
        out.append("")
        return "\n".join(out)


async def handle_get_sonar_pr_vs_main(project_key: str, pr_number: int) -> str:
    if not SONAR_TOKEN:
        return "  ⚠  SONARCLOUD_TOKEN env var is not set. Please add it to your environment.\n"
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            gate_data, issues_data, main_data = await asyncio.gather(
                sonar_get(client, "qualitygates/project_status", {"projectKey": project_key, "pullRequest": str(pr_number)}),
                sonar_get(client, "issues/search", {"componentKeys": project_key, "pullRequest": str(pr_number), "resolved": "false", "ps": "1"}),
                sonar_get(client, "measures/component", {"component": project_key, "metricKeys": "bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density,security_hotspots"}),
            )
        except httpx.HTTPStatusError as e:
            return f"  SonarQube API error {e.response.status_code}: {e.response.text[:300]}\n"

        status     = gate_data.get("projectStatus", {})
        gate       = status.get("status", "UNKNOWN")
        gate_icon  = "✅ PASSED" if gate == "OK" else "❌ FAILED"
        pr_issues  = issues_data.get("total", 0)
        main_m     = {x["metric"]: x.get("value","N/A") for x in main_data.get("component",{}).get("measures",[])}
        pr_m       = {c["metricKey"]: c.get("actualValue","N/A") for c in status.get("conditions", [])}

        def delta(pv: str, mv: str) -> str:
            try:
                d = float(pv) - float(mv)
                return f"{'▲' if d>0 else '▼' if d<0 else '='} {abs(d):.1f}"
            except: return "N/A"

        out = [
            _section(f"SONAR PR vs MAIN  |  {project_key}  |  PR #{pr_number}"), "",
            f"  PR Quality Gate  : {gate_icon}",
            f"  New Issues in PR : {pr_issues}", "",
            f"  {'Metric':<35} {'Main Branch':>14}  {'PR Value':>10}  Delta", DIV,
        ]
        for key, label in [("bugs","Bugs"), ("vulnerabilities","Vulnerabilities"), ("code_smells","Code Smells"),
                           ("security_hotspots","Security Hotspots"), ("coverage","Coverage %"), ("duplicated_lines_density","Duplications %")]:
            mv = main_m.get(key,"N/A"); pv = pr_m.get(key,"N/A")
            out.append(f"  {label:<35} {mv:>14}  {pv:>10}  {delta(pv,mv) if pv!='N/A' and mv!='N/A' else 'N/A'}")

        verdict = ("✅ This PR improves or maintains code quality — safe to merge."
                   if gate == "OK" else
                   "❌ This PR degrades code quality — review issues before merging.")
        out += ["", f"  {verdict}", ""]
        return "\n".join(out)


# ══════════════════════════════════════════════════════════════════════════════
#  MCP PLUMBING
# ══════════════════════════════════════════════════════════════════════════════

@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    HANDLER_MAP = {
        "get_pr_summary":           handle_get_pr_summary,
        "list_open_prs":            handle_list_open_prs,
        "get_pr_detail":            handle_get_pr_detail,
        "get_contributor_pr_stats": handle_get_contributor_pr_stats,
        "get_pr_review_stats":      handle_get_pr_review_stats,
        "get_pr_merge_time_trend":  handle_get_pr_merge_time_trend,
        "get_stale_prs":            handle_get_stale_prs,
        "get_sonar_pr_quality":     handle_get_sonar_pr_quality,
        "get_sonar_branch_health":  handle_get_sonar_branch_health,
        "get_sonar_pr_issues":      handle_get_sonar_pr_issues,
        "get_sonar_pr_vs_main":     handle_get_sonar_pr_vs_main,
    }
    try:
        result = await HANDLER_MAP[name](**arguments) if name in HANDLER_MAP else f"Unknown tool: '{name}'"
    except httpx.HTTPStatusError as e:
        result = f"API error {e.response.status_code}: {e.response.text[:300]}"
    except Exception as e:
        result = f"Error in '{name}': {str(e)}"
    return [TextContent(type="text", text=result)]


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def _get_notification_options():
    for module_path in ["mcp.server.models", "mcp.types", "mcp.shared.context", "mcp.server"]:
        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, "NotificationOptions", None)
            if cls is not None:
                return cls()
        except Exception:
            continue
    class _Fallback:
        tools_changed = False; resources_changed = False; prompts_changed = False
    return _Fallback()


async def main():
    notif = _get_notification_options()
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream, write_stream,
            InitializationOptions(
                server_name    = "github-pr-analytics",
                server_version = "2.0.0",
                capabilities   = app.get_capabilities(
                    notification_options      = notif,
                    experimental_capabilities = {},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
