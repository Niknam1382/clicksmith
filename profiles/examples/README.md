# Example profiles

Ready-made profiles you can import from **File → Import profile...** (or run headless with
`clicksmith run profiles/examples/<file>.json`).

| File | What it does |
| --- | --- |
| `fast-clicker.json` | Left click at the cursor, ~20 per second with 10 % random variation. |
| `human-like-area-clicker.json` | Clicks at random points inside a rectangle with irregular timing; stops if you move the mouse. |
| `daily-9am-click.json` | Clicks one fixed point every weekday at 09:00:00 (keep Clicksmith running). |
| `periodic-paste-and-send.json` | Click, click, type a Unicode message (Persian + emoji), click "send" - repeated every 5 h 1 min. |
| `refresh-page-every-30s.json` | Presses F5 every 30 seconds. |
| `slow-auto-scroll.json` | Scrolls down three notches every 2 seconds for 5 minutes. |
| `drag-and-drop.json` | Drags from one point to another with a smooth, human-like movement. |

> **Coordinates are placeholders.** Open the profile, then use *Pick on screen...* (or the capture
> hotkey) to point every step at the right place on **your** screen before you start.

Share your own profiles with a pull request: export one, put it here and add a row to the table.
