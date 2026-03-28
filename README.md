# GitHub MCP Server — AI Agent for PR and Code Quality Analysis

An AI agent that runs 11 tools across SonarCloud and GitHub to give you a complete code quality and PR process report in under 60 seconds. Powered by Claude (Anthropic).

---

## What This Does

You run one command. Claude calls 11 tools automatically — 4 SonarCloud tools and 7 GitHub PR tools — analyzes all the results, and writes a structured report covering code quality, open PRs, team performance, and recommendations.

No manual API calls. No switching between dashboards. One command, one report.

---

## How It Works

```
python run.py
      |
      v
main_agent.py  (Claude orchestrates everything)
      |
      |-- sonar_agent.py      (4 SonarCloud tools)
      |
      |-- github_pr_agent.py  (7 GitHub PR tools)
```

Claude reads the tool definitions, decides which to call, collects the results, and writes the final report. This is called an agentic loop — Claude keeps calling tools until it has everything it needs, then stops and writes the output.

---

## Table of Contents

1. [Get All Tokens and API Keys](#1-get-all-tokens-and-api-keys)
2. [Claude Setup](#2-claude-setup)
3. [Python Setup](#3-python-setup)
4. [PyCharm Setup](#4-pycharm-setup)
5. [MCP Server and Tools](#5-mcp-server-and-tools)
6. [Project Structure](#6-project-structure)
7. [Agent Explanations](#7-agent-explanations)
8. [Run Your Agents](#8-run-your-agents)
9. [Push to GitHub](#9-push-to-github)
10. [Troubleshooting](#10-troubleshooting)
11. [Sample Output](#11-sample-output)
12. [What to Build Next](#12-what-to-build-next)

---

## 1. Get All Tokens and API Keys

You need 3 tokens to run the full agent stack. Get them in this order.

### 1.1 Anthropic API Key

Used by: `sonar_agent.py`, `github_pr_agent.py`, `main_agent.py`

Steps:
1. Go to https://console.anthropic.com
2. Sign up or log in
3. Click your profile (top right) → API Keys
4. Click Create Key
5. Name it: `agents-key`
6. Click Create Key
7. Copy the key immediately — shown only once

```
Format: sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxx
Starts with: sk-ant-
```

Free tier includes $5 credits. No credit card needed to start.

---

### 1.2 SonarCloud Token

Used by: `sonar_agent.py` (all 4 SonarCloud tools)

Steps:
1. Go to https://sonarcloud.io
2. Log in with your GitHub account
3. Click your avatar (top right) → My Account
4. Click the Security tab
5. Under Generate Tokens, type name: `agents-token`
6. Click Generate
7. Copy the token immediately — shown only once

```
Format: sqp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Starts with: sqp_
```

Also find your SonarCloud Project Key:
1. Go to your project on SonarCloud
2. Click Project Information (bottom left sidebar)
3. Copy the Project Key shown there

```
Format: owner_reponame
Example: srivalligade04_ml-for-java-professionals
```

---

### 1.3 GitHub Personal Access Token (PAT)

Used by: `github_pr_agent.py` (all 7 GitHub tools) + git push authentication

Steps:
1. Go to https://github.com/settings/tokens
2. Click Generate new token (classic)
3. Name it: `agents-token`
4. Set expiration: 90 days
5. Check these scopes: repo, workflow, read:org
6. Click Generate token
7. Copy the token immediately — shown only once

```
Format: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Starts with: ghp_
```

---

### 1.4 Token Summary

| Token | Used For | Where to Get | Format |
|-------|----------|--------------|--------|
| ANTHROPIC_API_KEY | Claude AI (all agents) | console.anthropic.com | sk-ant-... |
| SONARCLOUD_TOKEN | SonarCloud tools | sonarcloud.io → My Account → Security | sqp_... |
| GITHUB_TOKEN | GitHub PR tools + git push | github.com/settings/tokens | ghp_... |

Never share these tokens publicly or commit them to GitHub.

---

## 2. Claude Setup

Claude is the AI brain that orchestrates all 11 tools.

### What Claude Does in This Project

```
You ask a question
      |
      v
Claude decides which tools to call
      |
      v
Tools fetch real data (GitHub API / SonarCloud API)
      |
      v
Claude analyzes all results
      |
      v
Claude writes a structured report
```

### Claude Model Used

All agents use: `claude-sonnet-4-20250514`

This is the recommended model — fast, smart, and cost-efficient for agentic tasks.

### How Claude Is Called

```python
import anthropic

client = anthropic.Anthropic(api_key="sk-ant-...")

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    tools=TOOLS,         # list of tools Claude can call
    messages=messages    # conversation history
)
```

### The Agentic Loop

Claude runs in a loop — calling tools, getting results, deciding if it needs more data, and finally writing the report when it has everything.

```
User sends prompt
      |
      v
Claude thinks: which tools do I need?
      |
      v
Claude calls tool(s) — e.g. get_sonar_branch_health()
      |
      v
Tool results sent back to Claude
      |
      v
Claude calls more tools if needed
(loops until stop_reason = end_turn)
      |
      v
Claude writes final report
```

---

## 3. Python Setup

### Install Python

Download Python 3.10 or higher from https://python.org/downloads

Verify installation:
```bash
python --version
# Should show: Python 3.10.x or higher
```

### Install Required Libraries

```bash
pip install anthropic requests python-dotenv
```

| Library | Purpose |
|---------|---------|
| anthropic | Calls Claude API |
| requests | Calls GitHub API and SonarCloud API |
| python-dotenv | Reads .env file for API keys |

### Create Your .env File

In your project folder, create a file named `.env`:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
SONARCLOUD_TOKEN=sqp_your-token-here
GITHUB_TOKEN=ghp_your-token-here
```

No quotes, no spaces around the equals sign.

---

## 4. PyCharm Setup

### Download and Install PyCharm

1. Go to https://jetbrains.com/pycharm/download
2. Download PyCharm Community Edition (free)
3. Install and open PyCharm

### Create a New Project

1. Open PyCharm
2. Click New Project
3. Choose folder: `PycharmProjects/github_mcp_server_python`
4. Select New environment using Virtualenv
5. Click Create

### Set Up Python Interpreter

1. Go to File → Settings → Project → Python Interpreter
2. Click Add Interpreter → Add Local Interpreter
3. Select Virtualenv Environment
4. Click OK

### Open Terminal in PyCharm

Press `Alt+F12` on Windows/Linux or `Option+F12` on Mac.

```bash
pip install anthropic requests python-dotenv
```

### Connect PyCharm to GitHub

1. Go to File → Settings → Version Control → GitHub
2. Click + → Log in with Token
3. Paste your GitHub PAT (ghp_...)
4. Click Add Account

---

## 5. MCP Server and Tools

### What is an MCP Server?

MCP (Model Context Protocol) is a standard that lets Claude call external tools — like GitHub APIs and SonarCloud APIs — in a structured way.

```
Claude (AI brain)
      |
MCP Server (tool connector)
      |
External APIs (GitHub, SonarCloud)
```

### All 11 Tools

#### SonarCloud Tools (4)

| Tool | What It Does |
|------|-------------|
| get_sonar_branch_health | Main branch health: bugs, smells, ratings A-E |
| get_sonar_pr_issues | New issues a PR introduces with file and line number |
| get_sonar_pr_quality | Quality gate PASSED/FAILED for a PR |
| get_sonar_pr_vs_main | Side-by-side PR vs main branch comparison |

#### GitHub PR Tools (7)

| Tool | What It Does |
|------|-------------|
| get_pr_summary | PR counts, merge rate, avg merge time |
| list_open_prs | All open PRs with age, author, draft status |
| get_stale_prs | PRs with no activity for 14+ days |
| get_pr_merge_time_trend | Weekly trend of PR volume and merge speed |
| get_pr_review_stats | Reviewer leaderboard, approval rates |
| get_contributor_pr_stats | Per-author breakdown of PRs |
| get_pr_detail | Deep analytics for a single PR |

### How Tools Are Defined

Each tool has a name, description, and input parameters. Claude reads these and knows exactly what to pass in.

```python
{
    "name": "get_sonar_branch_health",
    "description": "Get overall code quality health of the main branch.",
    "input_schema": {
        "type": "object",
        "properties": {
            "project_key": {
                "type": "string",
                "description": "SonarCloud project key"
            }
        },
        "required": ["project_key"]
    }
}
```

---

## 6. Project Structure

```
github_mcp_server_python/
|
|-- .env                    (your API keys — never commit this)
|-- .gitignore              (tells git to ignore .env)
|
|-- sonar_agent.py          (SonarCloud agent — 4 tools)
|-- github_pr_agent.py      (GitHub PR agent — 7 tools)
|-- main_agent.py           (Main orchestrator — all 11 tools)
|-- run.py                  (Launcher — run this)
|
|-- raw_results_pr11.json   (generated after running — raw tool data)
|-- report_pr11.md          (generated after running — AI report)
```

---

## 7. Agent Explanations

### sonar_agent.py — SonarCloud Agent

Purpose: Analyzes code quality using SonarCloud.

Tools it uses: get_sonar_branch_health, get_sonar_pr_issues, get_sonar_pr_quality, get_sonar_pr_vs_main.

What it does:
- Connects to SonarCloud API using your SONARCLOUD_TOKEN
- Fetches bugs, vulnerabilities, code smells, and coverage for your main branch
- Checks if a PR passes the quality gate
- Lists every new issue a PR introduces with exact file and line number
- Compares PR quality vs main branch

Example output:
```
Bugs: 0             Rating: A
Vulnerabilities: 0  Rating: A
Code Smells: 78     Rating: B
Coverage: N/A
Duplications: 0.0%
```

Run standalone:
```bash
python sonar_agent.py \
  --project srivalligade04_ml-for-java-professionals \
  --pr 11
```

---

### github_pr_agent.py — GitHub PR Agent

Purpose: Analyzes PR process health on GitHub.

Tools it uses: get_pr_summary, list_open_prs, get_stale_prs, get_pr_merge_time_trend, get_pr_review_stats, get_contributor_pr_stats, get_pr_detail.

What it does:
- Fetches all open PRs and their age
- Finds stale PRs with no activity for 14+ days
- Shows weekly trend of how fast PRs are being merged
- Shows reviewer leaderboard — who reviews most and approval rates
- Shows per-contributor breakdown of who opens and merges most PRs
- Deep analysis of a single PR including commits, files, and review timeline

Run standalone:
```bash
python github_pr_agent.py \
  --repo srivalligade04/github_mcp_server_python \
  --pr 11
```

---

### main_agent.py — Main Orchestrator Agent

Purpose: Combines all 11 tools into one complete analysis.

Tools it uses: All 4 SonarCloud + All 7 GitHub = 11 tools total.

What it does:
- Imports tools from both sonar_agent.py and github_pr_agent.py
- Sends one prompt to Claude with all 11 tools available
- Claude intelligently decides which tools to call and in what order
- Synthesizes all results into a 4-section structured report:
  1. Code Quality (SonarCloud)
  2. PR Process Health (GitHub)
  3. Team Performance
  4. Risk and Recommendations

Run standalone:
```bash
python main_agent.py \
  --repo    srivalligade04/github_mcp_server_python \
  --project srivalligade04_ml-for-java-professionals \
  --pr 11
```

---

### run.py — Launcher

Purpose: The easiest way to run everything with one command.

What it does:
1. Loads .env file automatically
2. Runs all 11 tools individually and prints raw results
3. Runs the main agent for AI-synthesized summary
4. Saves two output files

Run:
```bash
python run.py
```

Output files saved:
- `raw_results_pr11.json` — raw JSON from every tool
- `report_pr11.md` — AI-written summary report

---

## 8. Run Your Agents

### First Time Setup

```bash
# Navigate to your project
cd /Users/venka/PycharmProjects/github_mcp_server_python

# Install dependencies
pip install anthropic requests python-dotenv

# Create .env file
echo "ANTHROPIC_API_KEY=sk-ant-your-key" > .env
echo "SONARCLOUD_TOKEN=sqp_your-token" >> .env
echo "GITHUB_TOKEN=ghp_your-token" >> .env
```

### Run the Full Agent

```bash
python run.py
```

### What You Will See

```
RUNNING ALL 11 TOOLS INDIVIDUALLY

SONARCLOUD TOOLS (4)
TOOL: get_sonar_branch_health
{ "bugs": 0, "code_smells": 78, "reliability_rating": "A" ... }

TOOL: get_sonar_pr_issues
{ "total_issues": 0, "issues": [] }

GITHUB PR TOOLS (7)
TOOL: get_pr_summary
{ "open_count": 1, "merged_count": 1, "merge_rate": "50%" }

... (all 11 tools) ...

RUNNING MAIN AGENT — AI SUMMARY
  -> Calling: get_sonar_branch_health(...)
  -> Calling: get_pr_summary(...)
  -> Calling: get_contributor_pr_stats(...)

Report saved to report_pr11.md
```

### Change PR Number

Edit line 16 in run.py:
```python
PR_NUMBER = 11   # change to any PR number
```

---

## 9. Push to GitHub

### First Time Push

```bash
cd /Users/venka/PycharmProjects/github_mcp_server_python

git init

git remote add origin https://ghp_YOUR_TOKEN@github.com/srivalligade04/github_mcp_server_python.git

git add sonar_agent.py github_pr_agent.py main_agent.py run.py .gitignore README.md

git commit -m "Add SonarCloud and GitHub PR agents"

git branch -M main
git push -u origin main
```

### Future Pushes

```bash
git add .
git commit -m "Your commit message"
git push
```

### Save Credentials

```bash
git config --global credential.helper osxkeychain   # Mac
git config --global credential.helper manager       # Windows
```

---

## 10. Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| ANTHROPIC_API_KEY not set | .env not loaded | Add load_dotenv() at top of script |
| Remote: Write access denied | Wrong GitHub token | Regenerate PAT with repo scope |
| Repository not found | Wrong repo name | Check exact name on github.com |
| SonarCloud 404 | Wrong project key | Get key from SonarCloud → Project Information |
| fatal: pathspec did not match | Wrong directory | cd into your project folder first |
| non-fast-forward push error | Branch diverged | Run git push origin main --force |
| pip: command not found | Python not in PATH | Use python -m pip install ... |
| ModuleNotFoundError: anthropic | Not installed | Run pip install anthropic |

---

## 11. Sample Output

```
Bugs:               0    Reliability Rating:      A
Vulnerabilities:    0    Security Rating:         A
Code Smells:       78    Maintainability Rating:  B
Security Hotspots:  0
Duplications:     0.0%

Open PRs:   1
Merged PRs: 1
Merge Rate: 50%

PR #2 — Update github_pr_mcp_server.py
Author: srivalligade04 | Age: 21 hours | Awaiting review
```

---

## 12. What to Build Next

- GitHub Actions workflow to run the agent automatically on every pull request
- PR comment bot that posts the quality report directly on the PR page
- Slack notification when a quality gate fails
- Weekly email digest of team PR performance trends

---

## Quick Reference Card

```
# Get tokens from:
Anthropic  → console.anthropic.com/settings/keys
SonarCloud → sonarcloud.io → My Account → Security
GitHub     → github.com/settings/tokens

# Your .env file:
ANTHROPIC_API_KEY=sk-ant-...
SONARCLOUD_TOKEN=sqp_...
GITHUB_TOKEN=ghp_...

# Run agents:
python run.py

# Push to GitHub:
git add . && git commit -m "update" && git push

# Your project details:
GitHub Repo  : srivalligade04/github_mcp_server_python
Sonar Project: srivalligade04_github_mcp_server_python
```

---

## Author

Built by srivalligade04 taking help from Claude (Anthropic) as coding assistant, SonarCloud, and the GitHub API.

If this helped you, follow on GitHub and read the full walkthrough on Medium.

