<!-- Fill in the changelog, delete this comment, then publish the draft. -->
## Changes

- TODO changelog bullets

## Notes

- **No game assets are included.** You must supply your own Virtual Pro Wrestling 2
  (Japan) ROM — SHA1 `82DD25A044689EAB57AB362FE10C0DA6388C217A`. On first
  launch, click **Load ROM** and select it; the launcher validates and remembers
  it. VPW2 was Japan-only; fan-translation patched ROMs are not accepted (their hashes differ).
- **Windows SmartScreen**: the exe is unsigned, so Windows may warn on first run.
  Click "More info" → "Run anyway".
- **Saves and settings** live in `%LOCALAPPDATA%\Vpw2Recompiled\` — the cart's
  cartridge save (progress, created wrestlers) persists automatically. Save data is
  compatible across releases unless a release note says otherwise. For a portable
  install, create an empty `portable.txt` next to the exe.
- **GPU**: D3D12 by default. If you hit rendering issues, update your GPU drivers
  first, and please attach `%LOCALAPPDATA%\Vpw2Recompiled\Vpw2Recompiled.log`
  to any bug report.
- Known issues are tracked in the README.
