---
name: deploy-fresh-vps
description: Use when provisioning a brand-new Linux VPS from first SSH access through hardened key-only SSH, UFW rules, local SSH config aliasing, direct-IP 3x-ui panel setup, VLESS/Reality inbound creation, client export, and step-by-step guided verification.
---

# Deploy Fresh VPS

## Overview

Provision a fresh VPS as a guided, reversible workflow. The core rule is: never lock the user out, never lose credentials, and never proceed past a security boundary without a verified fallback.

This skill is a wizard, not a one-shot script. After each major phase, report what changed, what was verified, where secrets/configs were saved, and what comes next.

For concrete command templates and verification snippets, read `references/command-patterns.md` when execution begins.

## Operating Rules

- Call out that live VPS work changes remote authentication, firewall, and network exposure.
- Keep one working SSH session open while changing SSH or firewall rules.
- Prefer reversible drop-in config plus backups over overwriting system files.
- Redact secrets in chat: passwords, UUIDs, Reality private keys, panel credentials, subscription tokens.
- Store user-facing credentials and generated client configs only in the user-approved local directory.
- Do not paste secrets into final answers. Link local files and summarize contents.
- Do not assume 3x-ui install commands, distro package names, or service names are current. Verify them at run time from official sources or the target machine.
- If a verification gate fails, stop and debug before continuing.

## Wizard Phases

### Phase 0: Intake and Plan

Start by showing the user this plan in concise form:

1. Verify initial SSH access and OS.
2. Check or create a local SSH key pair.
3. Harden SSH: random high port, key-only login, local `~/.ssh/config` alias.
4. Install and configure UFW without breaking SSH.
5. Install 3x-ui and record panel access details.
6. Configure direct panel access by `IP:port/path` and optional direct subscription access.
7. Create a VLESS/Reality inbound and client.
8. Export local client files and verify server/client-facing configuration.

Ask for or confirm:

- Initial host/IP, login user, and temporary credential method.
- Preferred local SSH identity file, or permission to generate one.
- Desired SSH alias, for example `vps-us-1`.
- Local storage directory for runbook, SSH alias notes, panel credentials, and client exports.
- Whether to expose the 3x-ui panel directly on a random high port, restrict it to specific source IPs, or keep it private behind an SSH tunnel.
- Whether to enable direct subscription access, and which random high port/path to use.
- Whether the VLESS client should use the bare VPS IP or a user-provided DNS-only hostname.
- Whether to rotate the root password after key-only SSH is confirmed.

Do not ask for everything again if the user already provided it. Fill reasonable defaults and explicitly state them.

### Phase 1: Local Environment

Check:

- `ssh`, `ssh-keygen`, `scp` or `sftp`
- local `~/.ssh` permissions
- existing key files and `~/.ssh/config`
- whether the requested alias already exists

If no suitable public/private key pair exists, ask whether to generate one or use a provided key. When generating, require a named key path and remind the user to preserve the private key securely.

Gate before continuing:

- A public key path is known.
- The private key path exists locally and is not read or printed.
- A storage directory is chosen.

### Phase 2: Initial SSH Verification

Connect using the temporary credential. Run only read-only checks first:

- `whoami`
- `hostname`
- `/etc/os-release`
- `uptime`
- SSH service name (`ssh` or `sshd`)
- active SSH config values and listeners

Report OS, hostname, current SSH port/auth state, and whether root is being used.

Gate before continuing:

- Initial login works.
- The agent has a persistent SSH session open or a verified reconnect path.
- The target is a supported Linux system for this workflow.

### Phase 3: SSH Hardening

Choose a random high port that is not listening on the VPS. Avoid common alternatives such as `2222`; prefer an unpredictable port in a high range.

Use a two-stage SSH migration:

1. Bootstrap stage:
   - Back up SSH config.
   - Install the user's public key in `authorized_keys`.
   - Enable public key login.
   - Keep the old port and password login temporarily available.
   - Add the new port.
   - Run `sshd -t`.
   - Restart SSH.
   - Verify new-port key login from a separate local connection.

2. Final stage:
   - Back up again.
   - Make the new port the only active SSH port.
   - Disable `PasswordAuthentication` and keyboard-interactive login.
   - Permit root only by key if root is used.
   - Run `sshd -t`.
   - Restart SSH.
   - Verify new-port key login.
   - Verify old port no longer works.
   - Verify password auth is no longer offered.

After final verification, update local `~/.ssh/config` with the chosen alias, but never overwrite an existing alias silently. If the alias exists, show the conflict and ask for a new alias or permission to update it.

Gate before continuing:

- `ssh <alias>` works.
- The old port is closed or no longer accepted.
- Server authentication offers only public key.
- Backups are recorded in the local runbook.

### Phase 4: UFW and Network Boundary

Install UFW if absent. Always allow the final SSH port before enabling the firewall.

Use the user's intended exposure model. The default is direct IP access:

- Direct VLESS/Reality on `443`: allow `443/tcp` from anywhere, unless the user chooses a stricter source policy.
- Public 3x-ui panel: put the panel on a random high port, require a random path and strong credentials, and open that port directly.
- Subscription service: enable only if requested; use a random high port/path and open it directly or restrict by source IP.
- Private panel: do not open the panel port; use an SSH tunnel.

Gate before continuing:

- `ufw status verbose` shows SSH allowed.
- Direct service ports match the intended exposure.
- Panel and subscription ports are reachable or blocked exactly as intended.

### Phase 5: 3x-ui Installation and Panel Capture

Verify the current official 3x-ui project and install command before running network install scripts. Prefer the maintained upstream source and record the exact command used in the runbook.

After install:

- Capture panel port, random path, username, and password into the user-approved local secrets file.
- Redact those values in chat.
- Set or confirm a strong panel password.
- Confirm service status and listening ports.
- Confirm the panel can be reached by the chosen method: direct `IP:port/path` or SSH tunnel.

Gate before continuing:

- `x-ui` or the relevant 3x-ui service is active.
- Panel credentials and path are saved locally.
- Panel access works through the intended route.
- Unintended direct panel access is blocked if tunnel-only was selected.

### Phase 6: Inbound and Client

Create one VLESS inbound and one client. If the user does not understand protocol details, do not make them choose low-level options. State that the wizard will use the recommended direct-IP profile and proceed after the normal progress update.

Recommended default profile:

- Inbound remark: `<ssh-alias>-reality` or `US-VPS-Reality`
- Protocol: `VLESS`
- Port: `443`
- Transport: TCP/RAW
- Security: `Reality`
- Flow: `xtls-rprx-vision`
- Client: create exactly one enabled client by default, with a clear email/label such as `<ssh-alias>-client-1`
- Reality keys and short ID: generate through 3x-ui and save only the public/client-facing values in the client export
- SNI/serverName and Reality destination: use the current 3x-ui generated default if it passes validation; otherwise choose a stable HTTPS target and verify it resolves and accepts TLS
- Client route: bare VPS IP by default; a DNS-only hostname is also acceptable if the user provides one.
- Panel/subscription route: direct `IP:port/path` by default.

Use the direct client path by default. Add alternate routing only when the user explicitly asks for it.

Prefer configuring through the 3x-ui UI when the user wants visual confirmation. Use the panel API only after confirming request shape from the current panel version. Avoid direct SQLite writes except for read-only diagnosis.

Gate before continuing:

- Xray/3x-ui generated config contains exactly the expected inbound and at least one client.
- `443` is listening.
- Client UUID, flow, Reality public key, SNI/serverName, short ID, and target server value are present.
- UFW permits the intended client path.

### Phase 7: Local Client Export

Create a local export file in the approved directory containing:

- `vless://` URI
- Mihomo/Clash.Meta YAML snippet when relevant
- Notes explaining which values are sensitive
- The intended server value: bare IP by default, or DNS-only host if requested
- The subscription URL if enabled

Show the user:

- File path link.
- Redacted summary of protocol, port, transport, security, flow, and server target.
- Verification evidence, not secret material.

Gate before completion:

- Local export file is non-empty.
- YAML parses if a YAML snippet was produced.
- Subscription endpoint returns a valid config if subscription is enabled.
- Server-side config and listeners still match the export.

## Progress Updates

Use this format after every major phase:

```text
Status: Phase N complete - <short result>
Verified: <commands/results, redacted>
Saved: <local paths>
Next: <next phase and risk>
Need from you: <only if blocked or a decision is required>
```

## Completion Summary

End with:

- SSH alias command, for example `ssh <alias>`.
- Remote OS and hostname.
- SSH port and auth state.
- Firewall summary.
- 3x-ui panel access route, with credentials stored in local file only.
- VLESS inbound summary.
- Client export file link.
- Remaining risks: root password rotation, provider firewall/security group, exposed panel hardening, backup/restore notes.

Do not claim the deployment is complete unless every gate has been verified.
