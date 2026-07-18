#!/usr/bin/env python3
"""Recon pass 3 for VPW2: resolve the fingerprint ambiguities using the
sisters' documented evidence patterns (same three groups No Mercy had):
 - osViGetCurrentFramebuffer/osViGetNextFramebuffer: adjacent pair 0x40 apart,
   source order Current first; Current loads field +0x40, Next +0x44.
 - osAiGetLength/osAiGetStatus: tiny MMIO leaves; Length reads AI_LEN 0xA4500004,
   Status reads AI_STATUS 0xA450000C.
 - __osSiDeviceBusy: lui 0xA480 / lw 0x18 / andi 3 (SI_STATUS); the other
   candidates are SP/DP variants.
Also dump the gfx-ucode identity-break neighborhood (run ended 0x3D497)."""
import struct

VPW2 = r"C:\Users\selki\depot\Vpw2Recomp\vpw2.z64"
vp = open(VPW2, "rb").read()

REG = ("zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 "
       "s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra").split()
def dis(w, pc):
    op = w >> 26
    rs, rt, rd = (w >> 21) & 31, (w >> 16) & 31, (w >> 11) & 31
    imm = w & 0xFFFF
    simm = imm - 0x10000 if imm & 0x8000 else imm
    if w == 0: return "nop"
    if op == 0:
        fn = w & 0x3F
        if fn == 8: return f"jr    ${REG[rs]}"
        if fn == 0x25: return f"or    ${REG[rd]}, ${REG[rs]}, ${REG[rt]}"
        if fn == 0x24: return f"and   ${REG[rd]}, ${REG[rs]}, ${REG[rt]}"
        return f"SPECIAL.{fn:02X} rd={REG[rd]} rs={REG[rs]} rt={REG[rt]}"
    if op == 0x0F: return f"lui   ${REG[rt]}, 0x{imm:04X}"
    if op == 0x09: return f"addiu ${REG[rt]}, ${REG[rs]}, {'0x%X' % imm if simm >= 0 else '-0x%X' % -simm}"
    if op == 0x0C: return f"andi  ${REG[rt]}, ${REG[rs]}, 0x{imm:04X}"
    if op == 0x0D: return f"ori   ${REG[rt]}, ${REG[rs]}, 0x{imm:04X}"
    if op == 0x23: return f"lw    ${REG[rt]}, {'0x%X' % imm if simm >= 0 else '-0x%X' % -simm}(${REG[rs]})"
    if op == 0x2B: return f"sw    ${REG[rt]}, {simm}(${REG[rs]})"
    if op == 0x04: return f"beq   ${REG[rs]}, ${REG[rt]}, 0x{pc+4+simm*4:08X}"
    if op == 0x05: return f"bne   ${REG[rs]}, ${REG[rt]}, 0x{pc+4+simm*4:08X}"
    if op == 0x02: return f"j     0x{(pc & 0xF0000000) | ((w & 0x3FFFFFF) << 2):08X}"
    if op == 0x03: return f"jal   0x{(pc & 0xF0000000) | ((w & 0x3FFFFFF) << 2):08X}"
    return f".word 0x{w:08X}"

def show(label, rom, n=10):
    print(f"--- {label} @ rom 0x{rom:06X} (vram 0x{0x80000400 + rom - 0x1000:08X})")
    for i in range(n):
        off = rom + i*4
        w = struct.unpack_from(">I", vp, off)[0]
        pc = 0x80000400 + (off - 0x1000)
        print(f"  {pc:08X}: {w:08X}  {dis(w, pc)}")

print("=== AI getters (Length=+0x04, Status=+0x0C) ===")
for c in (0x2D250, 0x2D260, 0x390F0):
    show("candidate", c, 4)

print("=== Vi getter pair (Current=+0x40, Next=+0x44) ===")
for c in (0x344E0, 0x34520):
    show("candidate", c, 12)

print("=== __osSiDeviceBusy (want lui 0xA480 / lw 0x18 / andi 3) ===")
for c in (0x390D0, 0x39C40):
    show("candidate", c, 6)

print("=== gfx ucode identity-break neighborhood (run vs NM ended at 0x3D497) ===")
for off in range(0x3D480, 0x3D4C0, 4):
    w = struct.unpack_from(">I", vp, off)[0]
    print(f"  0x{off:06X}: {w:08X}")
