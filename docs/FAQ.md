# FAQ

**Does this work in games / fullscreen apps?**
The Windows backend calls the same `SendInput` API real hardware input goes through, so it works
with anything that accepts normal mouse/keyboard input, fullscreen included. It does **not**
bypass anti-cheat systems, and using an auto clicker violates the Terms of Service of many games
and online services - that's on you to check. See [SECURITY.md](../SECURITY.md).

**Why does it ask for Administrator sometimes?**
Windows blocks a normal-privilege process from clicking into a window that's running *as*
Administrator (a security feature called UIPI). If your target app runs elevated, use
**Tools → Restart as administrator**. Otherwise, you never need it.

**What's the "failsafe corner"?**
Slam your mouse into the top-left corner of the screen (`0, 0`) and Clicksmith stops immediately,
mid-action. It's on by default. It's a safety net, not a targeting restriction - profiles that
deliberately target `(0, 0)` are refused with an explanation instead of silently fighting it.

**Can it type Persian/Arabic/Chinese/emoji?**
Yes. The Windows backend types via `KEYEVENTF_UNICODE`, which sends the actual Unicode character
regardless of your active keyboard layout - see [docs/ARCHITECTURE.md](ARCHITECTURE.md).

**Does it work on Linux or macOS?**
Partially. The UI, engine, scheduler, and profiles are all cross-platform, and a `pynput`-based
input backend is included - but it's marked **experimental**: Unicode typing and global hotkeys
behave differently across window managers/display servers (X11 vs. Wayland, for instance) in ways
the Windows `SendInput` backend doesn't have to deal with. Windows is where Clicksmith is built,
tested, and released as a binary. Bug reports and fixes for other platforms are welcome.

**Does Clicksmith phone home?**
No telemetry, ever. The only network request it can make is an **opt-in** check against GitHub's
Releases API (Settings → "Check for updates when Clicksmith starts", off by default) to tell you
a newer version exists - it never downloads anything automatically. See `core/updater.py`.

**Where are my profiles and settings stored?**
`%APPDATA%\Clicksmith` on Windows by default (**File → Open data folder**), unless you're running
the portable build, in which case everything lives in a `data` folder next to `Clicksmith.exe`.
See the README's "Where things are stored" section.

**A profile I made in an older version won't load right.**
It should always *load* - unrecognized or invalid fields are dropped or reset to a default rather
than causing an error (see [docs/PROFILE_FORMAT.md](PROFILE_FORMAT.md)) - but a field with a new
meaning could behave differently. Please open an issue with the profile's JSON attached.

**Why PySide6 and not PyQt6/Tkinter/Electron?**
See "Why PySide6 over PyQt6" in [docs/ARCHITECTURE.md](ARCHITECTURE.md) for the licensing
reasoning. Tkinter can't produce the look this UI needs without a lot of custom widget work;
Electron/web-based UIs can't call `SendInput` without a native helper anyway, which defeats the
point of a lightweight, single-exe tool.

**How is this different from \[some other free auto clicker\]?**
See the comparison table in the README. Briefly: most free Windows auto-clickers are closed
source, Windows-only .exe downloads with no macro recorder, no Unicode typing, and no scheduler.
Clicksmith is a fully open-source rewrite that adds all of that, plus tests and CI you can
actually inspect.

**I found a bug / have an idea.**
Please open an issue - see [CONTRIBUTING.md](../CONTRIBUTING.md). Bug reports with the exact
steps to reproduce (and, if it's a macro problem, the profile's `.json`) are the most useful kind.
