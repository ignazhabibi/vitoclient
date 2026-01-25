---
description: switch to strict analysis and planning mode without code modifications
---

# Plan & Analyze Mode

This workflow restricts the agent to observation and planning tasks only. Use this when you want to discuss architecture, debug complex issues, or brainstorm features without touching the codebase.

## 1. Mode Switch
The agent MUST immediately call `task_boundary` with:
- `Mode`: **PLANNING**
- `TaskName`: "Analysis & Planning"
- `TaskStatus`: "Analyzing requested topic"

## 2. Rules of Engagement
1.  **READ-ONLY**: usage of `write_to_file`, `replace_file_content`, `run_command` (for modification), or `git` operations is **FORBIDDEN**.
2.  **Tools Allowed**: `view_file`, `grep_search`, `find_by_name`, `list_dir`, `read_url_content`, `search_web`.
3.  **Command Execution**: Only read-only commands (like `ls`, `cat`, `grep`) are allowed.

## 3. Output Structure
The agent should structure its response as follows:

### 🔍 Analysis
- What is the current state?
- What are the relevant files/components?
- Root cause analysis (if debugging).

### 💡 Options / Strategies
- **Option A**: Description + Pros/Cons
- **Option B**: Description + Pros/Cons

### 🎯 Recommendation
- Which option is best and why?
- High-level implementation steps (but DO NOT implement).
