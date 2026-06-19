---
name: browser-runtime-analysis
description: Use when Codex or another code agent needs browser runtime analysis for Network/API parameters or responses, HAR files, DOM or visual verification, frontend debugging, Chrome DevTools MCP, Chrome Extension, Computer Use, iframes, console errors, performance traces, deployment behavior, or source-to-page logic reconstruction.
---

# Browser Runtime Analysis

## Overview

Browser runtime analysis is about proving facts that only the running browser can reliably show. The goal is not to "operate a browser"; the goal is to capture browser-observable facts, map them back to source/config/deployment, and verify with the same class of evidence.

Core rule:

> Capture facts first. Interpret second. If one evidence channel fails, switch channels without changing the fact target.

## First: Check Infrastructure

Before doing real analysis, identify the agent environment and available browser tools. Do not skip this because the user says it is urgent.

1. Decide whether this is Codex.
   - Treat it as Codex if the instructions, tool list, or app context mention Codex, Codex Desktop, Codex plugins, or Codex MCP tools.
   - If it is not Codex, say that Computer Use and Codex Chrome Extension are Codex-only capabilities and do not try to prepare or use them.
   - Outside Codex, immediately check Chrome DevTools MCP. If it is available, continue with only Chrome DevTools MCP. If it is unavailable, follow the environment-level Chrome DevTools MCP setup rule below.

2. Check whether these are available:
   - Computer Use: tools such as `mcp__computer_use`, or plugin/skill metadata for Computer Use.
   - Chrome Extension: plugin/skill metadata for Chrome, or the Chrome Extension browser runtime.
   - Chrome DevTools MCP: tools such as `mcp__chrome_devtools`, `list_pages`, `list_network_requests`, `take_snapshot`, `performance_start_trace`.
   - For logged-in or already-reproduced pages, Chrome DevTools MCP is only "ready" if it is connected to the user's current Chrome. If it is installed but using an isolated browser/profile, warn that auth, extensions, open tabs, and reproduced state may be missing.

3. If something is missing, explain before starting:
   - Missing Computer Use or Chrome Extension in Codex: ask the user to enable the plugin from the Codex sidebar Plugins page. Reference: https://developers.openai.com/codex/plugins
   - Environment missing Chrome DevTools MCP: recommend configuring `chrome-devtools-mcp`, then opening a new session or restarting the agent/app so tools load. Outside Codex, do not recommend switching to Codex; guide the user through official Chrome DevTools MCP setup.
   - Environment missing all browser tooling: ask whether to prepare the missing tools first or proceed only with HAR/screenshots/logs supplied by the user.

## Chrome DevTools MCP Setup

Strong recommendation for Codex: configure Chrome DevTools MCP to connect to the user's current Chrome. Otherwise the agent loses the user's logged-in state, extensions, open tabs, and reproduced page state.

Recommended Codex command:

```bash
codex mcp add chrome-devtools -- npx -y chrome-devtools-mcp@latest \
  --autoConnect \
  --no-usage-statistics \
  --no-performance-crux \
  --redact-network-headers=true
```

Equivalent config:

```toml
[mcp_servers.chrome-devtools]
command = "npx"
args = [
  "-y",
  "chrome-devtools-mcp@latest",
  "--autoConnect",
  "--no-usage-statistics",
  "--no-performance-crux",
  "--redact-network-headers=true"
]
```

User-required Chrome steps:

1. Use Chrome 144+.
2. Open `chrome://inspect/#remote-debugging`.
3. Enable remote debugging for the running Chrome instance.
4. When Chrome asks whether to allow the debugging session, click `Allow`.
5. Start a new Codex session or restart Codex after adding the MCP server. New MCP tools usually do not appear in an already-running session.

Official references:

- https://developer.chrome.com/docs/devtools/agents/use-cases/auto-connect
- https://github.com/ChromeDevTools/chrome-devtools-mcp

If not using `--autoConnect`, the MCP server may launch or connect to an isolated browser/profile. That can be useful for clean reproduction, but it is the wrong default for logged-in runtime analysis.

## Evidence Directory

Create an analysis directory before collecting meaningful evidence. Tell the user the path; do not stop unless the path choice is risky or unclear.

Default location:

- If `cwd` is inside a git work tree: `<git-root>/.browser-runtime-analysis/<timestamp>-<slug>/`
- If not in a project: `~/Documents/browser-runtime-analysis/<timestamp>-<slug>/`
- If the user specifies another location, use it.

Recommended structure:

```text
.browser-runtime-analysis/<timestamp>-<slug>/
  notes.md
  actions.md
  findings.md
  artifacts.md
  network/
  har/
  console/
  screenshots/
  traces/
  lighthouse/
  heap/
  raw/
```

Rules:

- Add `.browser-runtime-analysis/` to the project `.gitignore` if it is not already ignored.
- Do not commit HAR, screenshots, heap snapshots, trace files, raw responses, or request bodies by default.
- Append key findings to `findings.md` as they are discovered. Context compaction can erase memory; files preserve continuity.
- Record every browser action that changes state in `actions.md`.
- If a HAR or raw export first lands in Downloads or a user-selected folder, immediately move it into the analysis directory with a shell command.
- Keep a sanitized summary separate from raw artifacts if the user wants something committable.

Minimum `findings.md` entry:

```text
## <short finding title>
- Target fact:
- Evidence:
- Tool:
- Artifact:
- Interpretation:
- Next check:
```

## Tool Roles

| Tool | Use for | Do not use as |
|---|---|---|
| Chrome Extension | Real Chrome tabs, login state, DOM/text, screenshots, ordinary clicks/typing, existing user tab claim, clipboard/history/page assets when needed | Network request/response debugger |
| Chrome DevTools MCP | Network lists/details, request/response bodies, console stack details, screenshots, DOM/a11y snapshots, performance trace, Lighthouse, heap, emulation, file upload | Full HAR exporter or guaranteed non-disruptive user-tab controller |
| Computer Use | Real desktop UI, DevTools UI operations, complete HAR export, Downloads/save dialogs, file pickers, complex menus/popups, cases where APIs cannot see what screen shows | Default browser automation path |

Cost rule:

- Use Chrome Extension when it can answer the fact with less disruption.
- Use Chrome DevTools MCP for DevTools-grade facts.
- Use Computer Use only when browser/API tools cannot expose the needed UI or export.

## Fact-First Workflow

1. State the target fact in one sentence.
   - "Need the request body and response for this button."
   - "Need to know which bundle an iframe actually loaded."
   - "Need to prove whether visual state matches the source change."

2. Pick the lowest-cost direct evidence channel.

3. Create/announce the evidence directory.

4. Capture the browser fact.

5. Write key findings to disk immediately.

6. Map the fact back to source, configuration, build output, deployment, proxy, or backend.

7. Verify with the same evidence type.

Do not replace runtime facts with source guesses. Source code explains facts after the browser proves what happened.

## Task Routes

### API Parameters and Responses

Small number of requests:

1. Use Chrome Extension to reach or operate the real logged-in page if needed.
2. Use Chrome DevTools MCP `list_network_requests()` to identify new or relevant requests.
3. Use `get_network_request(reqid)` for request headers, query, post data, response headers, and response body.
4. Save important request/response artifacts under `network/`.
5. Map fields to UI state, filters, auth context, source code, and backend contract.

Many requests or full flow:

1. Use Computer Use to open Chrome DevTools Network UI.
2. Clear Network, enable Preserve log if needed, and perform the user flow.
3. Export HAR through the UI.
4. Move the HAR into `har/` immediately.
5. Use scripts to filter and summarize; do not manually read large HARs in the UI.

Avoid:

- Page-level XHR/fetch monkey patch as the first approach.
- Guessing payloads from source.
- Copying only one request without recording trigger conditions.

### Frontend Visual Verification

1. Use Chrome Extension for real logged-in entry and fast screenshots/DOM checks.
2. Use Chrome DevTools MCP for element/full-page screenshots, a11y snapshot, emulation, and viewport changes.
3. Use Computer Use only if true screen state, browser UI, or complex popups matter.
4. Save screenshots and record viewport/user state.
5. Verify in the same entry point where the bug appears, especially for iframes or deployed pages.

### Console, Network Errors, and Debugging

1. Use Chrome DevTools MCP `list_console_messages()` and `get_console_message()` for stack details.
2. Use `list_network_requests()` and `get_network_request()` for status, redirects, CORS, request body, and response body.
3. Split errors by layer: resource loading, runtime JS, auth/session, proxy/gateway, build artifact, dependency, test environment.
4. Map stack/request evidence back to code/config.
5. Re-run the same browser action and confirm the console/network evidence changed.

### iframe, Proxy, Deployment, and Bundle Questions

1. Check host page and iframe separately.
2. Record iframe `src`, final URL, origin, viewport, visible DOM, and resource requests.
3. Use Network to identify loaded JS/CSS bundles and API paths.
4. Compare source, local demo, package output, CDN URL, hash/version, proxy/base/public path.
5. If local works but deployed page does not, inspect the deployed bundle before changing source again.

### Performance, Streaming, and Timing

1. Define boundaries: user trigger, request start, server first byte, chunk arrival, parser, UI render.
2. Use DevTools MCP Network and performance trace for browser-side timing.
3. Add source-level timestamps where needed.
4. For streaming, record chunk intervals and where fixed pacing begins.
5. Use Computer Use only when a long real UI flow or full HAR is necessary.

### Source-to-Page Logic Reconstruction

1. Start from runtime evidence: DOM, requests, responses, console, loaded bundle, visible state.
2. Identify relevant components, hooks, routes, state stores, request wrappers, and proxy config.
3. Explain the page logic from browser facts back to source.
4. Verify by changing a controlled input, observing changed runtime facts, or reading loaded artifacts.

## Common Mistakes

| Mistake | Correction |
|---|---|
| "Time is tight, use whichever tool works first." | Still check infrastructure first; otherwise the agent may miss the best evidence channel. |
| Starting with Computer Use for every task | Use it only for real UI/export gaps; it is costly and disruptive. |
| Using Chrome Extension for Network details | Chrome Extension is great for real Chrome context, but DevTools MCP is the Network detail tool. |
| Assuming DevTools MCP has logged-in state | It only does when configured to connect to current Chrome, preferably with `--autoConnect`. |
| Exporting HAR to Downloads and leaving it there | Move it immediately into the analysis directory. |
| Waiting until the final answer to write findings | Append key findings as work progresses to survive compaction. |
| Treating local demo as proof for deployed iframe | Verify the deployed/embedded entry and loaded bundle. |
| Committing raw runtime artifacts | Keep raw artifacts ignored; commit only sanitized summaries when asked. |

## Red Flags

Stop and correct course if any of these happen:

- The agent has not said whether it is Codex or what browser tools are available.
- The agent begins analysis while Chrome DevTools MCP, Chrome Extension, or Computer Use availability is unknown.
- The agent uses Computer Use before explaining why API tools are insufficient.
- The task needs logged-in browser state but DevTools MCP is not connected to current Chrome.
- The agent performs multi-step browser work without an evidence directory.
- HAR/raw files remain outside the analysis directory.
- Findings exist only in conversation memory.
- The agent reads cookies, localStorage, sessionStorage, passwords, or browser profile stores without explicit need and permission.

## Safety Boundaries

- Read the minimum browser data required for the fact target.
- Avoid cookies, localStorage, sessionStorage, passwords, and Chrome profile stores.
- Treat HAR, heap snapshots, screenshots, request bodies, and response bodies as sensitive.
- Ask for user handoff or confirmation before risky Computer Use actions: file upload, deletion, account/permission changes, third-party submissions, sensitive data transmission, install/extension changes, CAPTCHA, or security interstitial bypass.
- Prefer user-completed login/SSO/MFA over trying to bypass authentication.

## Completion Standard

A browser runtime analysis is complete only when:

- Infrastructure status and selected tools are clear.
- Evidence directory path is recorded.
- Key observations are written to disk.
- Raw artifacts are stored in the analysis directory.
- The conclusion is tied to browser facts.
- The conclusion is mapped to source/config/deployment when relevant.
- The result is verified with the same kind of evidence, or the remaining blocker is explicitly stated.
