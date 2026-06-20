# Brand assets

Source/design assets for Calibrate — **not served** by the app (lives outside
`app/`), kept in the repo for reference and regeneration.

- **`Calibrate.png`** — the master app logo (1254×1254): dark-green rounded square,
  sage targeting ring, cream fork.
- **`generate_icons.py`** — regenerates the served PWA icons from the master.

## Regenerating the app icons

If you update `Calibrate.png`, rebuild the served icons from the repo root:

```bash
.venv/bin/python brand/generate_icons.py
```

This writes `icon-192.png`, `icon-512.png`, and `icon-maskable.png` into
`app/static/icons/` (referenced by `app/static/manifest.webmanifest` and the
`apple-touch-icon` link in `app/templates/base.html`).

After changing the icons, bump the service-worker cache version in
`app/static/sw.js`. Note that installed PWAs cache the home-screen icon at install
time — to see a new icon on a phone, remove the app and re-add it.
