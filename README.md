# Complete Setup Guide
## Claude + Python + PyCharm + MCP Server + Agents

---

## Table of Contents

1. [Get All Tokens & API Keys](#1-get-all-tokens--api-keys)
2. [Claude Setup](#2-claude-setup)
3. [Python Setup](#3-python-setup)
4. [PyCharm Setup](#4-pycharm-setup)
5. [MCP Server Setup](#5-mcp-server-setup)
6. [Project Structure](#6-project-structure)
7. [Agent Explanations](#7-agent-explanations)
8. [Run Your Agents](#8-run-your-agents)
9. [Push to GitHub](#9-push-to-github)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Get All Tokens & API Keys

You need **3 tokens** to run the full agent stack. Get them in this order.

---

### 1.1 Anthropic API Key

Used by: `sonar_agent.py`, `github_pr_agent.py`, `main_agent.py`

**Steps:**
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign up or log in
3. Click your profile (top right) → **API Keys**
4. Click **Create Key**
5. Name it: `agents-key`
6. Click **Create Key**
7. **Copy the key immediately** — shown only once!

```
Format: sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxx
Starts with: sk-ant-
```

> Free tier includes $5 credits. No credit card needed to start.

---

### 1.2 SonarCloud Token

Used by: `sonar_agent.py` (all 4 SonarCloud tools)

**Steps:**
1. Go to [sonarcloud.io](https://sonarcloud.io)
2. Log in with your GitHub account
3. Click your **avatar** (top right) → **My Account**
4. Click the **Security** tab
5. Under **Generate Tokens**, type name: `agents-token`
6. Click **Generate**
7. **Copy the token immediately** — shown only once!

```
Format: sqp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Starts with: sqp_
```

**Also find your SonarCloud Project Key:**
1. Go to your project on SonarCloud
2. Click **Project Information** (bottom left sidebar)
3. Copy the **Project Key** shown there

```
Format: owner_reponame
Example: srivalligade04_ml-for-java-professionals
```

---

### 1.3 GitHub Personal Access Token (PAT)

Used by: `github_pr_agent.py` (all 7 GitHub tools) + git push authentication

**Steps:**
1. Go to [github.com/settings/tokens](https://github.com/settings/tokens)
2. Click **Generate new token (classic)**
3. Name it: `agents-token`
4. Set expiration: **90 days**
5. Check these scopes:
   - ✅ `repo` (full repository access)
   - ✅ `workflow`
   - ✅ `read:org`
6. Click **Generate token**
7. **Copy the token immediately** — shown only once!

```
Format: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Starts with: ghp_
```

---

### 1.4 Token Summary Table

| Token | Used For | Where to Get | Format |
|-------|----------|--------------|--------|
| `ANTHROPIC_API_KEY` | Claude AI (all agents) | console.anthropic.com | `sk-ant-...` |
| `SONARCLOUD_TOKEN` | SonarCloud tools | sonarcloud.io → My Account → Security | `sqp_...` |
| `GITHUB_TOKEN` | GitHub PR tools + git push | github.com/settings/tokens | `ghp_...` |

> ⚠️ **Never share these tokens publicly or commit them to GitHub**

---

## 2. Claude Setup

Claude is the AI brain that orchestrates all 11 tools.

### 2.1 What Claude Does in This Project

```
You ask a question
      ↓
Claude decides which tools to call
      ↓
Tools fetch real data (GitHub API / SonarCloud API)
      ↓
Claude analyzes all results
      ↓
Claude writes a structured report
```

### 2.2 Claude Model Used

All agents use: **claude-sonnet-4-20250514**

This is the recommended model — fast, smart, cost-efficient for agentic tasks.

### 2.3 How Claude Is Called (API)

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

### 2.4 Agentic Loop Explained

```
┌─────────────────────────────────────────┐
│  User sends prompt                      │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│  Claude thinks: which tools do I need?  │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│  Claude calls tool(s)                   │
│  e.g. get_sonar_branch_health()         │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│  Tool results sent back to Claude       │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│  Claude calls more tools if needed      │
│  (loops until stop_reason = end_turn)   │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│  Claude writes final report             │
└─────────────────────────────────────────┘
```

---

## 3. Python Setup

### 3.1 Install Python

Download Python 3.10 or higher from [python.org/downloads](https://python.org/downloads)

Verify installation:
```bash
python --version
# Should show: Python 3.10.x or higher
```

### 3.2 Install Required Libraries

```bash
pip install anthropic requests python-dotenv
```

| Library | Purpose |
|---------|---------|
| `anthropic` | Calls Claude API |
| `requests` | Calls GitHub API and SonarCloud API |
| `python-dotenv` | Reads `.env` file for API keys |

### 3.3 Create Your `.env` File

In your project folder, create a file named `.env`:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
SONARCLOUD_TOKEN=sqp_your-token-here
GITHUB_TOKEN=ghp_your-token-here
```

> ⚠️ No quotes, no spaces around `=`

---

## 4. PyCharm Setup

### 4.1 Download and Install PyCharm

1. Go to [jetbrains.com/pycharm/download](https://jetbrains.com/pycharm/download)
2. Download **PyCharm Community Edition** (free)
3. Install and open PyCharm

### 4.2 Create a New Project

1. Open PyCharm
2. Click **New Project**
3. Choose folder: `PycharmProjects/github_mcp_server_python`
4. Select **New environment using Virtualenv**
5. Click **Create**

### 4.3 Set Up Python Interpreter

1. Go to **File → Settings → Project → Python Interpreter**
2. Click **Add Interpreter → Add Local Interpreter**
3. Select **Virtualenv Environment**
4. Click **OK**

### 4.4 Open Terminal in PyCharm

Press `Alt+F12` (Windows/Linux) or `Option+F12` (Mac)

Install dependencies in the terminal:
```bash
pip install anthropic requests python-dotenv
```

### 4.5 Connect PyCharm to GitHub

1. Go to **File → Settings → Version Control → GitHub**
2. Click **+** → **Log in with Token**
3. Paste your GitHub PAT (`ghp_...`)
4. Click **Add Account**

---

## 5. MCP Server Setup

### 5.1 What is an MCP Server?

MCP (Model Context Protocol) is a standard that lets Claude call external tools — like GitHub APIs and SonarCloud APIs — in a structured way.

```
Claude (AI brain)
      ↕
MCP Server (tool connector)
      ↕
External APIs (GitHub, SonarCloud)
```

### 5.2 MCP Tools Available (11 total)

#### SonarCloud Tools (4)

| Tool | What It Does |
|------|-------------|
| `get_sonar_branch_health` | Main branch health: bugs, smells, ratings A–E |
| `get_sonar_pr_issues` | New issues a PR introduces (file + line) |
| `get_sonar_pr_quality` | Quality gate PASSED/FAILED for a PR |
| `get_sonar_pr_vs_main` | Side-by-side PR vs main branch comparison |

#### GitHub PR Tools (7)

| Tool | What It Does |
|------|-------------|
| `get_pr_summary` | PR counts, merge rate, avg merge time |
| `list_open_prs` | All open PRs with age, author, draft status |
| `get_stale_prs` | PRs with no activity for 14+ days |
| `get_pr_merge_time_trend` | Weekly trend of PR volume and merge speed |
| `get_pr_review_stats` | Reviewer leaderboard, approval rates |
| `get_contributor_pr_stats` | Per-author breakdown of PRs |
| `get_pr_detail` | Deep analytics for a single PR |

### 5.3 How Tools Are Defined (Tool Schema)

Each tool is defined with a name, description, and input parameters:

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

Claude reads these definitions and knows exactly what parameters each tool needs.

---

## 6. Project Structure

Your final project folder should look like this:

```
github_mcp_server_python/
│
├── .env                    ← API keys (NEVER commit to GitHub)
├── .gitignore              ← tells git to ignore .env
│
├── sonar_agent.py          ← SonarCloud agent (4 tools)
├── github_pr_agent.py      ← GitHub PR agent (7 tools)
├── main_agent.py           ← Main orchestrator (all 11 tools)
├── run.py                  ← Launcher — run this!
│
├── raw_results_pr11.json   ← generated after running (raw tool data)
└── report_pr11.md          ← generated after running (AI report)
```

---

## 7. Agent Explanations

### 7.1 `sonar_agent.py` — SonarCloud Agent

**Purpose:** Analyzes code quality using SonarCloud

**Tools it uses:** 4 SonarCloud tools

**What it does:**
- Connects to SonarCloud API using your `SONARCLOUD_TOKEN`
- Fetches bugs, vulnerabilities, code smells, coverage for your main branch
- Checks if a PR passes the quality gate
- Lists every new issue a PR introduces with exact file and line number
- Compares PR quality vs main branch

**Example output:**
```
Bugs: 0        → Rating: A
Vulnerabilities: 0  → Rating: A
Code Smells: 78    → Rating: B
Coverage: N/A
Duplications: 0.0%
```

**Run standalone:**
```bash
python sonar_agent.py \
  --project srivalligade04_ml-for-java-professionals \
  --pr 11
```

---

### 7.2 `github_pr_agent.py` — GitHub PR Agent

**Purpose:** Analyzes PR process health on GitHub

**Tools it uses:** 7 GitHub PR tools

**What it does:**
- Fetches all open PRs and their age
- Finds stale PRs (no activity for 14+ days)
- Shows weekly trend of how fast PRs are being merged
- Shows reviewer leaderboard (who reviews most, approval rates)
- Shows per-contributor breakdown (who opens/merges most PRs)
- Deep analysis of a single PR (commits, files, review timeline)

**Example output:**
```
Open PRs: 3
Merged this month: 8
Avg merge time: 4.2 hours
Stale PRs: 1 (PR #5 — no activity for 18 days)
Top reviewer: srivalligade04 (12 reviews, 92% approval)
```

**Run standalone:**
```bash
python github_pr_agent.py \
  --repo srivalligade04/github_mcp_server_python \
  --pr 11
```

---

### 7.3 `main_agent.py` — Main Orchestrator Agent

**Purpose:** Combines all 11 tools into one complete analysis

**Tools it uses:** All 4 SonarCloud + All 7 GitHub = 11 tools total

**What it does:**
- Imports tools from both `sonar_agent.py` and `github_pr_agent.py`
- Sends one prompt to Claude with all 11 tools available
- Claude intelligently decides which tools to call and in what order
- Synthesizes all results into a 4-section structured report:
  1. Code Quality (SonarCloud)
  2. PR Process Health (GitHub)
  3. Team Performance
  4. Risk & Recommendations

**Run standalone:**
```bash
python main_agent.py \
  --repo    srivalligade04/github_mcp_server_python \
  --project srivalligade04_ml-for-java-professionals \
  --pr 11
```

---

### 7.4 `run.py` — Launcher

**Purpose:** Easiest way to run everything

**What it does:**
1. Loads `.env` file automatically
2. Runs all 11 tools individually and prints raw results
3. Runs the main agent for AI-synthesized summary
4. Saves two files:
   - `raw_results_pr11.json` — raw JSON from every tool
   - `report_pr11.md` — AI-written summary report

**Run:**
```bash
python run.py
```

---

## 8. Run Your Agents

### 8.1 First Time Setup (run once)

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

### 8.2 Run the Full Agent

```bash
python run.py
```

### 8.3 What You'll See

```
████ RUNNING ALL 11 TOOLS INDIVIDUALLY ████

>>> SONARCLOUD TOOLS (4)
=== TOOL: get_sonar_branch_health ===
{ "bugs": 0, "code_smells": 78, "reliability_rating": "A" ... }

=== TOOL: get_sonar_pr_issues ===
{ "total_issues": 0, "issues": [] }

>>> GITHUB PR TOOLS (7)
=== TOOL: get_pr_summary ===
{ "open_count": 3, "merged_count": 8, "merge_rate": "73%" }

... (all 11 tools) ...

████ RUNNING MAIN AGENT — AI SUMMARY ████
  → Calling: get_sonar_branch_health(...)
  → Calling: get_pr_summary(...)
  → Calling: get_contributor_pr_stats(...)
  ... (Claude calls tools automatically) ...

# Code Quality Report — PR #11
...
✓ Report saved to report_pr11.md
```

### 8.4 Change PR Number

Edit line 16 in `run.py`:
```python
PR_NUMBER = 11   # ← change to any PR number
```

---

## 9. Push to GitHub

### 9.1 First Time Push

```bash
cd /Users/venka/PycharmProjects/github_mcp_server_python

# Initialize git
git init

# Add remote (use your token in URL to avoid password prompts)
git remote add origin https://ghp_YOUR_TOKEN@github.com/srivalligade04/github_mcp_server_python.git

# Add files (NOT .env — that stays local)
git add sonar_agent.py github_pr_agent.py main_agent.py run.py .gitignore

# Commit
git commit -m "Add SonarCloud and GitHub PR agents"

# Push
git branch -M main
git push -u origin main
```

### 9.2 Future Pushes (after making changes)

```bash
git add .
git commit -m "Your commit message"
git push
```

### 9.3 Save Credentials (so you're never asked again)

```bash
git config --global credential.helper osxkeychain   # Mac
git config --global credential.helper manager       # Windows
```

---

## 10. Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `ANTHROPIC_API_KEY not set` | .env not loaded | Add `load_dotenv()` at top of script |
| `Remote: Write access denied` | Wrong GitHub token | Regenerate PAT with `repo` scope |
| `Repository not found` | Wrong repo name | Check exact name on github.com |
| `SonarCloud 404` | Wrong project key | Get key from SonarCloud → Project Information |
| `fatal: pathspec did not match` | Wrong directory | `cd` into your project folder first |
| `non-fast-forward` push error | Branch diverged | Run `git push origin main --force` |
| `pip: command not found` | Python not in PATH | Use `python -m pip install ...` |
| `ModuleNotFoundError: anthropic` | Not installed | Run `pip install anthropic` |

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
Sonar Project: srivalligade04_ml-for-java-professionals
```

---

*Generated with Claude Sonnet — Anthropic*
