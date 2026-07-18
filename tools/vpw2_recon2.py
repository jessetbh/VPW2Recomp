#!/usr/bin/env python3
"""Recon pass 2 for VPW2: exact code/data boundary, descriptor-table
neighborhood + termination, gfx-ucode identity run vs No Mercy, data pockets
in the fixed segment, and libultra fingerprint transfer from No Mercy
(adapted from tools/nm_recon2.py, No Mercy's WM2000->NM pass).

Pass-1 facts: rspboot text at 0x3A220 (byte-identical), audio text 0x3A2F0
(+0xC54, byte-identical newer-AKI), gfx text 0x3AF44 (NM's first 0x100
matched), audio dispatch table 0x4A730 (identical), overlay descriptor table
at rom 0x488C0 (4 entries seen, two vram slots), game_main 0x80000460."""
import re, struct

VPW2 = r"C:\Users\selki\depot\Vpw2Recomp\vpw2.z64"
NM   = r"C:\Users\selki\depot\NoMercyRecomp\nomercy.z64"
NM_DUMP = r"C:\Users\selki\depot\NoMercyRecomp\syms\dump.toml"

vp = open(VPW2, "rb").read()
nm = open(NM, "rb").read()

# --- exact end of fixed-segment CPU code: last jr $ra before rspboot (0x3A220)
last = vp.rfind(b"\x03\xe0\x00\x08", 0x1000, 0x3A220)
print(f"=== last jr $ra before rspboot: rom 0x{last:06X} (code ends 0x{last+8:06X}) ===")

# --- descriptor table neighborhood: entries before 0x488C0 / after 0x48950?
print("=== words around descriptor table 0x48850..0x489A8 ===")
for off in range(0x48854, 0x489A4, 0x24):
    w = struct.unpack_from(">9I", vp, off)
    print(f"  0x{off:06X}: " + " ".join(f"{x:08X}" for x in w))

# --- gfx ucode: how far byte-identical to No Mercy from rspboot on?
#     (nm rspboot 0x40F80 <-> vp 0x3A220). NM's gfx text ends where its data
#     begins; just measure the run.
print("=== ucode byte-identity run vs No Mercy ===")
n = 0
while vp[0x3A220+n] == nm[0x40F80+n] and n < 0x20000:
    n += 1
print(f"  byte-identical run from rspboot: 0x{n:X} bytes (vp 0x3A220..0x{0x3A220+n:X})")
# post-gfx-text comparison in 16-byte blocks for a fuller drift picture
same = 0
for off in range(0, 0x1000, 16):
    if vp[0x3AF44+off:0x3AF44+off+16] == nm[0x41CA4+off:0x41CA4+off+16]:
        same += 1
print(f"  gfx-text region (first 4KB): {same}/256 16-byte blocks identical to NM's")

# --- fixed-segment data pockets: valid-instruction ratio per 1KB window
def looks_insn(w):
    op = w >> 26
    if w == 0: return True
    if op == 0: return True
    return op in (1,2,3,4,5,6,7,8,9,0xA,0xB,0xC,0xD,0xE,0xF,0x10,0x11,0x14,0x15,0x16,0x17,
                  0x20,0x21,0x22,0x23,0x24,0x25,0x26,0x27,0x28,0x29,0x2A,0x2B,0x2E,0x2F,
                  0x31,0x35,0x39,0x3D)
print("=== low-validity 1KB windows in fixed-segment code (likely data pockets) ===")
run_start = None
CODE_END = last + 8
for base in range(0x1000, CODE_END, 0x400):
    cnt = ok = 0
    for o in range(base, min(base+0x400, CODE_END), 4):
        w = struct.unpack_from(">I", vp, o)[0]
        cnt += 1
        if looks_insn(w): ok += 1
    bad = ok / cnt < 0.9
    if bad and run_start is None: run_start = base
    if not bad and run_start is not None:
        print(f"  0x{run_start:06X} - 0x{base:06X}")
        run_start = None
if run_start is not None:
    print(f"  0x{run_start:06X} - 0x{CODE_END:06X}")

# --- fingerprint transfer from No Mercy ---
def mask_word(w):
    op = w >> 26
    if op in (2, 3):
        return w & 0xFC000000
    if op in (8,9,0xA,0xB,0xC,0xD,0xE,0xF) or 0x20 <= op <= 0x3F:
        return w & 0xFFFF0000
    return w

def masked(buf):
    return [mask_word(struct.unpack_from(">I", buf, i)[0]) for i in range(0, len(buf)//4*4, 4)]

vp_code = masked(vp[0x1000:CODE_END])

# parse No Mercy dump.toml: named (non-func_) functions in its FIXED segment only
# (NM code ends 0x40F80 = rspboot; keep sources below that to avoid rom/vram
# mapping confusion with overlays).
sec_rom = sec_vram = 0
targets = []
for line in open(NM_DUMP):
    m = re.match(r'rom = (0x[0-9A-Fa-f]+)', line)
    if m: sec_rom = int(m.group(1), 16)
    m = re.match(r'vram = (0x[0-9A-Fa-f]+)', line)
    if m: sec_vram = int(m.group(1), 16)
    m = re.search(r'\{ name = "([^"]+)", vram = (0x[0-9A-Fa-f]+), size = (0x[0-9A-Fa-f]+)', line)
    if m and not m.group(1).startswith("func_") and m.group(1) not in ("entrypoint",):
        name, vram, size = m.group(1), int(m.group(2), 16), int(m.group(3), 16)
        rom = sec_rom + (vram - sec_vram)
        if rom < 0x40F80:
            targets.append((name, rom, size))

print(f"=== fingerprint transfer: {len(targets)} named No Mercy fixed-seg functions -> VPW2 ===")
hits = 0
for name, rom, size in sorted(targets, key=lambda t: t[0]):
    pat = masked(nm[rom:rom+size])
    if len(pat) < 4:
        print(f"  {name:28s} too small, skipped"); continue
    matches = []
    first = pat[0]
    for i in range(len(vp_code) - len(pat) + 1):
        if vp_code[i] != first: continue
        if vp_code[i:i+len(pat)] == pat:
            matches.append(0x1000 + i*4)
            if len(matches) > 3: break
    if len(matches) == 1:
        vram = 0x80000400 + (matches[0] - 0x1000)
        print(f"  {name:28s} -> rom 0x{matches[0]:06X} vram 0x{vram:08X}")
        hits += 1
    elif matches:
        print(f"  {name:28s} AMBIGUOUS x{len(matches)}: " + " ".join(hex(m) for m in matches))
    else:
        print(f"  {name:28s} no match")
print(f"=== {hits}/{len(targets)} unique transfers ===")
