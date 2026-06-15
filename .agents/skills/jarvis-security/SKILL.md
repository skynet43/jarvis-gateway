# Jarvis Security Skill

## Purpose

Review scripts, endpoints, secrets, commands, network binding, and destructive actions before running or committing Jarvis Gateway changes.

## Rules

- Inspect before running unknown code.
- Check for API keys, tokens, passwords, and private paths.
- Flag destructive commands.
- Avoid public bind `0.0.0.0` unless intentional.

## Workflow

1. Review changed scripts and endpoints for unsafe command execution, broad filesystem access, and public network binding.
2. Search changed files for likely secrets before committing.
3. Flag destructive commands such as recursive deletes, forced overwrites, credential changes, and external publishing.
4. Prefer least privilege, local-only defaults, and explicit operator confirmation.
5. Report security findings and any residual risk.
