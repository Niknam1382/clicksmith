# Profile file format

A profile is a single JSON file (`ProfileStore` saves one per file, named `<profile name>.json`,
in the folder shown by **File → Open profiles folder**). This is the exact shape written by
`Profile.to_dict()` / read by `Profile.from_dict()` in `src/clicksmith/core/models.py`, which
stays the source of truth - this document explains it, but that file's `SCHEMA_VERSION` and
dataclasses are authoritative if the two ever disagree.

Loading is forgiving on purpose: an unknown key is ignored, and a field with a value of the wrong
type falls back to its default rather than failing to load the whole file. So it's always safe to
hand-edit a profile, share one with someone on an older Clicksmith version, or delete a field
you don't want to think about.

```jsonc
{
  "schema": 1,
  "name": "My profile",
  "mode": "clicker",                 // "clicker" | "macro"

  "interval": {                       // time between repetitions
    "hours": 0, "minutes": 0, "seconds": 0, "millis": 100,
    "jitter_pct": 0                   // ± random variation, 0-100
  },

  "click": {                          // clicker mode only
    "button": "left",                 // "left" | "right" | "middle"
    "clicks": 1,                      // 1 = single, 2 = double, 3 = triple
    "hold_ms": 0                      // 0 = an ordinary click; >0 = press, wait, release
  },

  "target": {                         // clicker mode only
    "mode": "cursor",                 // "cursor" | "fixed" | "area"
    "x": 0, "y": 0,                   // "fixed": the point. "area": the first corner
    "x2": 0, "y2": 0,                 // "area": the opposite corner
    "jitter_px": 0                    // "fixed": random offset per click, in pixels
  },

  "stop": {
    "mode": "infinite",               // "infinite" | "count" | "duration"
    "count": 100,                     // repetitions, if mode == "count"
    "duration_s": 60                  // seconds, if mode == "duration"
  },

  "safety": {
    "failsafe_corner": true,          // stop instantly if the cursor hits (0, 0)
    "stop_on_mouse_move": false,      // stop if you move the mouse yourself
    "prevent_sleep": true,            // keep the PC awake while this profile runs
    "start_delay_s": 3                // countdown before a manually-started run begins
  },

  "steps": [ /* macro mode only - see below */ ],

  "schedule": {
    "enabled": false,
    "time": "09:00:00",               // 24-hour, local time
    "days": [0, 1, 2, 3, 4, 5, 6],     // 0 = Monday ... 6 = Sunday
    "once": true                      // turn "enabled" back off after it fires
  }
}
```

## Macro steps

Each entry in `"steps"` has a `"type"` and only the fields that type uses (all other fields are
still present with harmless defaults, since it's one shared JSON object shape):

| `type` | Relevant fields | Meaning |
| --- | --- | --- |
| `"click"` | `x`, `y`, `use_cursor`, `button`, `clicks`, `hold_ms` | Click at `(x, y)`, or at the cursor's current position if `use_cursor` is `true`. |
| `"move"` | `x`, `y`, `duration_ms` | Move to `(x, y)`; `0` = instant, otherwise an eased glide. |
| `"drag"` | `x`, `y`, `x2`, `y2`, `button`, `duration_ms` | Press at `(x, y)`, glide to `(x2, y2)`, release. |
| `"scroll"` | `x`, `y`, `use_cursor`, `dx`, `dy` | Scroll by `dx`/`dy` notches, at `(x, y)` or the cursor. |
| `"text"` | `text`, `char_delay_ms` | Type a Unicode string, one character every `char_delay_ms`. |
| `"key"` | `keys` | Press a combo, e.g. `"Ctrl+V"`, `"Enter"`, `"Alt+Tab"`. |
| `"wait"` | *(none)* | Does nothing itself - use `delay_after_ms` for the pause. |

Every step also has `delay_after_ms`: the pause **after** that step runs, before the next one (or
before the macro repeats). This is exactly what the recorder measures between your real actions.

## A minimal hand-written example

```json
{
  "schema": 1,
  "name": "Press F5 every 30 seconds",
  "mode": "macro",
  "interval": { "hours": 0, "minutes": 0, "seconds": 30, "millis": 0, "jitter_pct": 10 },
  "stop": { "mode": "infinite", "count": 100, "duration_s": 60 },
  "steps": [
    { "type": "key", "keys": "F5", "delay_after_ms": 0 }
  ]
}
```

Every field `Profile.from_dict` doesn't recognise (or that's simply missing, as `click`, `target`,
`safety`, and `schedule` are above) is filled in with its default - so this short file loads fine.

See `profiles/examples/` for more ready-made profiles, and `scripts/generate_examples.py` for the
Python that generates them (the same `Profile` classes this document describes).
