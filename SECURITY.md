# Security policy

## Responsible use

Clicksmith automates mouse and keyboard input. That capability is dual-use: it is legitimate for
testing, accessibility, repetitive-task relief, and QA automation, and is misused when it violates
a game's or service's Terms of Service, or when it's used to interact with systems without
authorization. Clicksmith:

- performs no network communication except an **explicit, opt-in** GitHub Releases check for
  updates (Settings, off by default) - see `core/updater.py`. Automation itself never touches the
  network.
- collects no telemetry or analytics of any kind.
- stores profiles and settings only in your local per-user data folder (or next to the executable
  in portable mode) - see the README's "Where things are stored" section.

Use it in accordance with the terms of whatever application, game, or service you point it at.
The maintainers do not endorse using Clicksmith to violate any third party's terms of service.

## Supported versions

Only the latest published release is supported with security fixes. Please update before
reporting an issue.

## Reporting a vulnerability

Please **do not** open a public issue for a security vulnerability (e.g. something that could let
a malicious profile file or a malicious macro achieve more than "click here, type this"; unsafe
handling of the update check; or a packaging/supply-chain issue).

Instead, use GitHub's private reporting:

1. Go to the repository's **Security** tab.
2. Click **"Report a vulnerability"** to open a private advisory with the maintainers.

If that isn't available, open a normal issue asking a maintainer to enable private reporting or
to share a contact address, without including exploit details.

Please include:

- Clicksmith version and OS.
- Steps to reproduce, or a minimal profile/macro `.json` that triggers the issue.
- What you'd expect to happen instead.

We aim to acknowledge reports within a few days. Fixes are released as a new tagged version
(see `CHANGELOG.md`); credit is given in the release notes unless you ask not to be named.
