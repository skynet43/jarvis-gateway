# Jarvis App Bridge Skill

## Purpose

Work on local app bridge services, FastAPI endpoints, Windows app control, local ports, GUI panels, and safe automation for Jarvis and CodexOS.

## Rules

- Check port conflicts first.
- Keep services local.
- Do not log secrets.
- Use safe mode for risky actions.

## Workflow

1. Identify local ports, processes, and service boundaries before starting app bridge services.
2. Bind to `127.0.0.1` unless a public bind is explicitly requested and reviewed.
3. Add confirmation or dry-run behavior for risky automation.
4. Avoid storing tokens, passwords, API keys, or private paths in logs.
5. Document endpoints, ports, and safety assumptions.
