# Jarvis Gateway Skill

## Purpose

Work on the Jarvis Gateway local AI API for CodexOS.

Use this skill when creating, editing, debugging, or documenting the local Jarvis Gateway service, its API routes, Ollama integration, runtime scripts, or CodexOS control-layer behavior.

## Rules

- Keep files inside the repo.
- Use `127.0.0.1` by default.
- Do not expose services publicly unless explicitly asked.
- Check port conflicts before starting local services.
- Report exact files changed.

## Workflow

1. Inspect the requested files before editing when they already exist.
2. Prefer small, reviewable changes.
3. Keep defaults local-first and safe.
4. Run syntax checks or lightweight tests for changed Python files.
5. Summarize changed files and verification results.
