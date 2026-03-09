# OctoAuthor Threat Model

## Overview

OctoAuthor uses autonomous AI agents to generate user documentation. This document defines the threat model, trust boundaries, and security controls that protect against compromised or misbehaving agents.

**Core Principle: Zero Trust.** The documentation worker (OpenClaw) is treated as an untrusted external contractor. Everything it produces is inspected before it can affect any protected branch.

## Trust Levels

| Component | Trust Level | Rationale |
|-----------|------------|-----------|
| OpenClaw (worker) | **UNTRUSTED** | Autonomous agent with broad tool access. Susceptible to prompt injection, hallucination, and unpredictable behavior. |
| Auditor Agent | **TRUSTED** | Runs as separate process with own credentials. Not controllable by OpenClaw. |
| GitHub Actions | **TRUSTED** | Deterministic static analysis. No AI reasoning involved. |
| Human Reviewer | **AUTHORITY** | Final decision maker. Only entity that can merge to protected branches. |

## Threat Matrix

### T1: Prompt Injection via Documentation Content

**Threat:** Generated markdown contains hidden instructions that are picked up by AI tools (IDE assistants, chatbots, other agents) that read the docs.

**Attack Vector:** OpenClaw writes seemingly normal docs that contain invisible unicode characters, HTML comments, or markdown constructs that instruct other AI systems.

**Impact:** Code execution, data exfiltration, privilege escalation in downstream AI systems.

**Controls:**
- Gate 1 (static): Scan for hidden unicode (zero-width spaces, RTL overrides, homoglyphs)
- Gate 1 (static): Strip all HTML comments from markdown
- Gate 2 (auditor): AI scan for instruction-like patterns targeting other AI systems
- Gate 3 (human): Review rendered markdown for anything suspicious

### T2: Cross-Site Scripting (XSS) in Rendered Docs

**Threat:** Markdown contains `<script>`, event handlers, or other executable HTML that runs when docs are rendered in-app.

**Attack Vector:** OpenClaw injects `<script>alert(1)</script>`, `<img onerror="...">`, or `javascript:` URLs.

**Impact:** Session hijacking, credential theft, arbitrary code execution in user's browser.

**Controls:**
- Gate 1 (static): HTML tag allowlist enforcement (only `img`, `strong`, `em`, `code`, `table`, `thead`, `tbody`, `tr`, `td`, `th`, `ul`, `ol`, `li`, `p`, `h1`-`h6`, `blockquote`, `pre`, `hr`, `br`, `a`)
- Gate 1 (static): Strip all `on*` attributes, `javascript:` URLs, `data:` URLs
- SDK (react/fastapi): Sanitize HTML at render time as defense-in-depth
- Gate 2 (auditor): AI review for obfuscated XSS patterns

### T3: Data Leakage via Screenshots

**Threat:** Screenshots capture sensitive data (API keys, PII, real customer data, internal URLs) that gets committed to the repository.

**Attack Vector:** OpenClaw captures screenshots of a running app that has real data loaded, or captures browser UI showing bookmarks, extensions, or dev tools with sensitive info.

**Impact:** Credential exposure, PII compliance violations, internal infrastructure exposure.

**Controls:**
- Config: App MUST be running with demo/seed data during capture (enforced by capture config)
- Gate 1 (static): Secret scanner (detect-secrets, trufflehog) on all files including images (OCR)
- Gate 2 (auditor): Vision model scans screenshots for PII patterns, API keys, email addresses, dev tools
- Gate 2 (auditor): Verify screenshots match expected viewport (no unexpected UI elements)
- Process: Demo data seeding script is part of capture config, not left to the agent

### T4: Malicious External Links

**Threat:** Generated docs contain URLs pointing to phishing sites, malware downloads, or tracking pixels.

**Attack Vector:** OpenClaw inserts helpful-looking links that actually point to malicious domains.

**Impact:** User compromise, malware infection, tracking.

**Controls:**
- Gate 1 (static): URL allowlist — only domains explicitly configured are permitted
- Gate 1 (static): No external image URLs (all images must be local)
- Gate 2 (auditor): Verify all URLs resolve to expected domains
- Config: Allowlisted domains defined per-project in capture config

### T5: Supply Chain via Image Files

**Threat:** Image files contain steganographic payloads, malicious EXIF data, or are actually disguised file types.

**Attack Vector:** Agent generates or modifies PNG files that contain executable content in metadata or pixel data.

**Impact:** Exploitation of image parsing vulnerabilities, tracking via EXIF GPS data.

**Controls:**
- Gate 1 (static): Validate image file headers match declared MIME type
- Gate 1 (static): Strip all EXIF/metadata from images (Pillow re-save)
- Gate 1 (static): Enforce file size bounds (screenshots should be <500KB)
- Gate 2 (auditor): Compare image dimensions to expected viewport size

### T6: Social Engineering via Documentation

**Threat:** Docs instruct users to perform dangerous actions disguised as normal procedures.

**Attack Vector:** "To complete setup, disable your firewall..." or "Enter your admin password in the field below..."

**Impact:** Privilege escalation, credential harvesting, security bypass.

**Controls:**
- Gate 2 (auditor): AI scan for behavioral red flags (disable security, share credentials, grant permissions, run commands)
- Spec enforcement: Doc standard prohibits terminal commands, config file changes, security modifications
- Gate 3 (human): Review for anything that asks users to do something unusual

### T7: Dependency/Command Injection via Code Snippets

**Threat:** Docs contain code snippets or install commands that pull malicious packages.

**Attack Vector:** "Run `pip install helpful-tool`" where `helpful-tool` is a malicious package.

**Impact:** Package hijacking, arbitrary code execution on user's machine.

**Controls:**
- Spec enforcement: User docs MUST NOT contain terminal commands or code snippets (that's developer docs)
- Gate 1 (static): Detect and flag code blocks (```) in generated user docs
- Gate 2 (auditor): Flag any text that looks like a command or install instruction

## Security Gates (Defense in Depth)

```
                    OpenClaw Output
                         │
                         ▼
              ┌─── GATE 1: Static Analysis ───┐
              │  markdownlint                  │
              │  HTML sanitizer check          │
              │  URL allowlist check           │
              │  Secret scanner (OCR + text)   │
              │  Image validation              │
              │  Unicode homoglyph check       │
              │  File size bounds check        │
              │                                │
              │  FAIL → PR blocked             │
              └────────────┬───────────────────┘
                           │ pass
                           ▼
              ┌─── GATE 2: Auditor Agent ─────┐
              │  Content safety scan           │
              │  Prompt injection detection    │
              │  Screenshot PII OCR            │
              │  Behavioral analysis           │
              │  Style guide compliance        │
              │  Visual diff (if update)       │
              │                                │
              │  BLOCKED → auto-close PR       │
              │  FLAGGED → label + details     │
              └────────────┬───────────────────┘
                           │ pass/flagged
                           ▼
              ┌─── GATE 3: Human Review ──────┐
              │  Reviews PR diff               │
              │  Reviews auditor report        │
              │  Checks flagged items          │
              │  Approves or rejects           │
              │                                │
              │  APPROVED → merge to dev       │
              └────────────────────────────────┘
```

## GitHub Repository Configuration

### Required Branch Protection (master)

- [ ] Require pull request before merging
- [ ] Require at least 1 approving review
- [ ] Require review from CODEOWNERS
- [ ] Dismiss stale reviews when new commits are pushed
- [ ] Require status checks to pass (auditor, static-analysis)
- [ ] Require branches to be up to date before merging
- [ ] Do NOT allow bypassing above settings
- [ ] No force pushes

### OpenClaw GitHub Token (Fine-Grained PAT)

**Permissions (minimum required):**
- Contents: Read/Write (scoped to `octoauthor/*` branches only)
- Pull Requests: Read/Write (create PRs only)
- **NO** admin access
- **NO** branch protection bypass
- **NO** workflow dispatch permissions
- **NO** actions write permissions
- Repository-scoped (only the documentation repo)

### CODEOWNERS

```
# All user guide changes require team review
/docs/user-guide/** @your-org/docs-team

# Specs changes require maintainer review
/specs/** @your-org/maintainers

# Security config changes require security review
/.github/workflows/** @your-org/security
```

## Audit Logging

All security-relevant events MUST be logged:

| Event | Log Level | Details |
|-------|-----------|---------|
| Audit finding (critical/high) | ERROR | Full finding details, evidence, file path |
| Audit finding (medium/low) | WARNING | Finding summary, file path |
| PR auto-blocked | ERROR | Reason, findings count, PR number |
| PR auto-flagged | WARNING | Flagged findings, PR number |
| Audit passed | INFO | Files reviewed, screenshots scanned, PR number |
| Gate 1 static check failure | ERROR | Check name, file path, details |
| OpenClaw branch push | INFO | Branch name, commit SHA, files changed |

## Incident Response

If a security issue is found in merged documentation:

1. **Revert immediately** — git revert the merge commit
2. **Audit trail** — check audit logs for the PR to understand what was missed
3. **Root cause** — determine if this was a gate failure (scanner didn't catch it) or a novel attack
4. **Update controls** — add detection rule to prevent recurrence
5. **Disclose** — if shipped to users, follow responsible disclosure process
