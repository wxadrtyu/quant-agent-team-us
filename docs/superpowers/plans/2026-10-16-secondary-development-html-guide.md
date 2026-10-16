# Secondary Development HTML Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a verified, offline Chinese HTML secondary-development manual for the entire current repository.

**Architecture:** One self-contained HTML document under `docs/`; no generated assets or runtime dependencies. Source claims come from current code and configuration, with explicit labels for historical plans and unverified behavior.

**Tech Stack:** HTML5, embedded CSS, Python standard-library verification, PowerShell and Git inspection.

## Global Constraints

- Output: `docs/secondary-development-guide.html`, self-contained, simplified Chinese, no external resources.
- Cover A-share daily core, US research/report extensions, and shared repository infrastructure.
- Check all cited paths, CLI commands, parameters, and configuration against this checkout.
- Do not run ingestion, backtests, broker/Paper operations, monitoring-pool edits, polling, paid APIs, or downloads.
- Preserve existing untracked data and memory files. Use `apply_patch` for editing.

---

### Task 1: Build the factual source map

**Files:**
- Read: `pyproject.toml`, `AGENTS.md`, `README.md`, `src/quant_agent_team/*.py`, selected `scripts/*.py`, `configs/*.yaml`, `tests/*.py`, `docs/*.md`
- Create: none

**Interfaces:**
- Consumes: approved design spec.
- Produces: verified table of paths, entry points, command syntax, limitations, and test targets for Task 2.

- [x] **Step 1:** List tracked modules and current Git branch/status with `rg --files` and `git status --short --branch`.
- [x] **Step 2:** Inspect actual CLI parser, workflow, database, research, evaluation, US report and pool boundaries. Confirm each path before citing it.
- [x] **Step 3:** Distinguish present implementation from old README/architecture drafts. Record only evidence-backed commands.

### Task 2: Author and validate the standalone HTML

**Files:**
- Create: `docs/secondary-development-guide.html`
- Read: `docs/superpowers/specs/2026-10-16-secondary-development-html-guide-design.md`

**Interfaces:**
- Consumes: Task 1 source map.
- Produces: a single valid HTML5 page with section anchors, responsive and print CSS, actual paths, and safe modification recipes.

- [x] **Step 1:** Write semantic HTML with `<html lang="zh-CN">`, UTF-8 metadata, page navigation, `<main>`, eight content sections, and embedded CSS. Separate the environment-writing install command from read-only inspection/test commands confirmed in Task 1.
- [x] **Step 2:** Validate HTML parsing and local anchors with Python standard-library `html.parser`; verify every repository path cited in the page exists or is explicitly labeled as a proposed output.
- [x] **Step 3:** Run `git diff --check`; inspect the rendered page if browser access permits. The browser security policy blocked local `file://` preview, so record that limitation and statically check narrow/print CSS instead.
- [x] **Step 4:** Add a structured local memory fallback for this stage if MCP memory remains unavailable; stage only task files, then commit the verified document and record.
