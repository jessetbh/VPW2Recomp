#!/usr/bin/env python3
"""Generate N64Recomp symbol TOML (syms/dump.toml) from splat output — VPW2.

Same approach as WM2000/Revenge/VPW64's generator (symbol-TOML mode; spimdisasm
emits `nonmatching <name>, <size>` + per-instruction `/* ROM VRAM WORD */`
comments). One [[section]] per asm file; overlays are ordinary sections
(librecomp tracks their loads by rom address).

RENAME transfers libultra knowledge. VPW2 (Jan 2000) sits BETWEEN WM2000
(Oct 1999) and No Mercy (Nov 2000) — same AKI team, same era, so its libultra
should match one of theirs. Fingerprint the fixed segment against No Mercy
FIRST (adapt this repo's tools/nm_recon2.py, which matched WM2000->No Mercy
36/42 unique — the family record; the recon*.py/nm_recon*.py copies here are
verbatim method references pointing at Wm2kRecomp/NoMercyRecomp data — for
this game those repos ARE the fingerprint sources). Evidence method per function: WT's
disasm/libultra.md; record this game's evidence in ours. The map below is EMPTY
until recon fills it — see WM2000's tools/gen_symbols.py for the worked example
(including the boot-crash-loop identifications: osCreatePiManager/
osCartRomInit/osDriveRomInit/osAiSetNextBuffer and the osViGet*Framebuffer
adjacency pair).
Input invariant from ALL sisters: rename ONLY osContInit + __osSiRawStartDma +
__osSiDeviceBusy; do NOT rename osContStartReadData (kills the raw-SI path).
NEVER stub/mis-rename osGetCount (frozen game clock, WM2000 lesson).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASM = ROOT / "disasm" / "asm"
OUT = ROOT / "syms" / "dump.toml"

RENAME = {
    # TODO(recon): libultra names transfer from No Mercy (Nov 2000, closest build;
    # 43 names, family-record 36/42 unique fingerprint transfer) and WM2000.
    # Adapt tools/nm_recon*.py (kept verbatim as method references) into
    # vpw2_recon*.py pointing local=vpw2.z64, sister=../NoMercyRecomp.
    # EVERY entry needs an evidence line in disasm/libultra.md.
    # Boot invariants (all five sisters): rename ONLY osContInit +
    # __osSiRawStartDma + __osSiDeviceBusy for input (NOT osContStartReadData);
    # NEVER stub or fake osGetCount.
}

# Extra function entry points injected into dump.toml that splat cannot express:
# j-referenced entries living INSIDE another sized function (IDO multi-entry
# shared-tail clusters; Revenge's EXTRA_FUNCS mechanism — PERVASIVE in WM2000 and
# expected here). N64Recomp recompiles each independently from ROM bytes, so the
# overlap just duplicates a little code. Populated automatically by
# tools/recomp_loop.py from N64Recomp "Unhandled branch" errors and by
# tools/fix_backbranches.py audits, one "section name vram size" line per entry
# in syms/extra_funcs.txt. AUDIT after any re-split: a stale entry with a wrapped
# offset silently shadows the real function in the overlay lookup table (WM2000
# session 5 part 5).
EXTRA_FUNCS = {}
_extra_file = Path(__file__).resolve().parent.parent / "syms" / "extra_funcs.txt"
if _extra_file.exists():
    for l in open(_extra_file):
        parts = l.split()
        if len(parts) == 4:
            EXTRA_FUNCS.setdefault(parts[0], []).append(
                (parts[1], int(parts[2], 16), int(parts[3], 16)))

# Functions suppressed as symbols (continuation fragments merged into an earlier
# function).
SKIP = set()
_skip_file = ROOT / "syms" / "skip_functions.txt"
if _skip_file.exists():
    SKIP = {l.strip() for l in open(_skip_file) if l.strip()}

FUNC_RE = re.compile(r"^nonmatching (\S+), (0x[0-9A-Fa-f]+)")
GLABEL_RE = re.compile(r"^glabel (\S+)")
INSN_RE = re.compile(r"^\s*/\* ([0-9A-Fa-f]+) ([0-9A-Fa-f]{8}) ([0-9A-Fa-f]{8}) \*/")

# Overlays per the descriptor table at rom 0x539A0 (disasm/vpw2.yaml): five
# overlays across two vram slots (0x800D9960: a+e; 0x80106760: b/c/d).
# N64Recomp statics are `static_<section index>_<vram>` with the index = the
# section ORDER in dump.toml — keep fix_stumps' index-based resolution in mind
# (WM2000 session 7) when reading its "chained X -> Y" output.
SECTION_NAMES = {
    # TODO(recon): map splat asm filenames (rom-offset .s names) to section names
    # once the overlay descriptor table is found. No Mercy had FIVE overlays across
    # TWO swap slots (descriptors rom 0x539A0, 9-word entries); WM2000 had four.
    # Expect VPW2 (between them, Jan 2000) to follow the same architecture.
    "1000.s": "entry",
}

def parse_file(path):
    """Return (rom_start, vram_start, rom_end, [(name, vram, size)])."""
    funcs = []
    pending_size = None
    pending_name = None
    first = None
    last = None
    for line in open(path, encoding="utf-8"):
        m = FUNC_RE.match(line)
        if m:
            pending_name, pending_size = m.group(1), int(m.group(2), 16)
            continue
        m = GLABEL_RE.match(line)
        if m and pending_name == m.group(1):
            funcs.append([pending_name, None, pending_size])
            continue
        m = INSN_RE.match(line)
        if m:
            rom, vram = int(m.group(1), 16), int(m.group(2), 16)
            if first is None:
                first = (rom, vram)
            last = (rom, vram)
            if funcs and funcs[-1][1] is None:
                funcs[-1][1] = vram
    if first is None:
        return None
    return first[0], first[1], last[0] + 4, [(n, v, s) for n, v, s in funcs if v is not None]

def main():
    sections = []
    for path in sorted(ASM.glob("*.s")):
        parsed = parse_file(path)
        if not parsed:
            continue
        rom, vram, rom_end, funcs = parsed
        if path.name == "1000.s":
            name = "entry"
            funcs = [("entrypoint", vram, 0x38)] if not funcs else funcs
        elif path.name in SECTION_NAMES:
            name = SECTION_NAMES[path.name]
        else:
            name = f"main_{rom:X}"
        sections.append((name, rom, vram, rom_end - rom, funcs))

    OUT.parent.mkdir(exist_ok=True)
    unused = set(RENAME) - {"main"}
    with open(OUT, "w", newline="\n") as f:
        f.write("# Autogenerated from splat disassembly by tools/gen_symbols.py\n")
        total = 0
        seen = {}
        for name, rom, vram, size, funcs in sections:
            f.write(f"\n[[section]]\nname = \"{name}\"\n")
            f.write(f"rom = 0x{rom:08X}\nvram = 0x{vram:08X}\nsize = 0x{size:X}\n\n")
            f.write("functions = [\n")
            funcs = sorted(list(funcs) + EXTRA_FUNCS.get(name, []), key=lambda t: t[1])
            for fn, fv, fs in funcs:
                if fn in SKIP:
                    continue
                unused.discard(fn)
                fn = RENAME.get(fn, fn)
                # disambiguate names colliding across same-vram overlays (WT scheme)
                if fn in seen and seen[fn] != (name, fv):
                    fn = f"{fn}_{name}"
                seen[fn] = (name, fv)
                f.write(f"    {{ name = \"{fn}\", vram = 0x{fv:08X}, size = 0x{fs:X} }},\n")
                total += 1
            f.write("]\n")
    print(f"wrote {OUT}: {len(sections)} sections, {total} functions")
    if unused:
        print("WARNING: RENAME keys not found in splat output (splat merged/missed them):")
        for k in sorted(unused):
            print(f"  {k} -> {RENAME[k]}")

if __name__ == "__main__":
    main()
