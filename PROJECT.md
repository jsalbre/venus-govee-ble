# PROJECT

**Version:** 1.0 | **Updated:** 2026-09-01

---

## Overview

Govee H510x BLE temperature/humidity sensor bridge for Victron Venus OS (Cerbo
GX). Reads BLE advertisements via `btmon`, decodes temperature/humidity/battery
data, and publishes readings to Venus OS's D-Bus as
`com.victronenergy.temperature` services.

---

## Documentation Structure

| File | Role | Visibility |
|------|------|------------|
| `PROJECT.md` | This file — doc structure and roles | Public |
| `LICENSE` | MIT | Public |
| `README.md` | User-facing setup, configuration, and installation | Public |
| `CHANGELOG.md` | Append-only release history | Public |
| `TODO.md` | Active planned work | Public |
| `ARCHITECTURE.md` | Design decisions and rationale, D-Bus service structure, BLE decoding reference | Public |
| `samples/` | Raw BLE/btmon captures containing real device MAC addresses | Private, gitignored |

Platform-wide Venus OS/Cerbo GX facts (BusyBox quirks, SetupHelper packaging
conventions, D-Bus conventions, runit service management) live in the shared
`Development/environment-notes/venus-os-cerbo-gx.md`, not duplicated here.

No `docs-private/` currently exists — nothing yet warrants a gitignored
private-notes directory beyond `samples/`.
