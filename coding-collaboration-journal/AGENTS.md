# Repository Guide

This repository contains an Agent Skill, not an installed journal instance.

- Keep `SKILL.md` concise and route detailed behavior to `references/`.
- Keep scripts dependency-free unless a dependency clearly earns its maintenance cost.
- Treat bootstrap output as a public contract: upgrades must be idempotent and preserve user-owned files.
- Add or update tests whenever generated paths, configuration keys, redaction behavior, or report contracts change.
- Never include live credentials, private project data, or example secrets in fixtures.
- Claims of runtime support require a corresponding doctor check, fixture, or explicitly marked `missing evidence`.
