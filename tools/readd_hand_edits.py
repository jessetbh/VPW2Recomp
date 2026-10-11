#!/usr/bin/env python3
"""Re-apply RecompiledFuncs hand-edit diagnostics after a regen — VPW2.

Every N64Recomp regen wipes hand-edits made directly in RecompiledFuncs/*.c.
This script is the ONLY sanctioned way to carry such edits: register each edit
here (idempotent, safe to re-run) instead of re-adding it by hand, and document
it in docs/bringup-plan.md. Run it AFTER tools/fix_stumps.py +
tools/fix_switches.py + tools/fix_backbranches.py + tools/fix_selfentry.py.

NO HAND-EDITS ARE REGISTERED YET for VPW2. The framework below is kept from
No Mercy's version (see that sister repo for worked examples: the dcc4 draw
airbag, and its retired hunt probes — plus the gotchas that ctx GPRs are 64-bit
SIGN-EXTENDED, so compare with 0xFFFFFFFF8xxxxxxxull constants, and that a
MEM_W base gpr must be sign-extended or it writes to rdram+4GB).

Anchors are exact generated lines (ending-agnostic: generated files are CRLF,
insertions are LF, the compiler doesn't care). If an anchor is missing the
script FAILS LOUDLY -- regen output changed shape; re-derive the edit and update
this script.
"""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUNCS = os.path.join(ROOT, 'RecompiledFuncs')

failures = []

def load_lines(fn):
    with open(os.path.join(FUNCS, fn), 'rb') as f:
        return f.read().decode('utf-8', errors='replace').splitlines(keepends=True)

def save_lines(fn, lines):
    with open(os.path.join(FUNCS, fn), 'wb') as f:
        f.write(''.join(lines).encode('utf-8'))

def body_range(lines, func_name):
    start = end = None
    sig = 'RECOMP_FUNC void %s(' % func_name
    for i, l in enumerate(lines):
        if start is None and l.startswith(sig):
            start = i
        elif start is not None and l.rstrip('\r\n') == ';}':
            end = i
            break
    if start is None or end is None:
        failures.append('%s: cannot locate %s' % (func_name, sig))
    return start, end

def insert_after(lines, idx_range, anchor, text, tag):
    """Insert text (list of LF-terminated lines) after the unique line whose
    stripped content == anchor, within idx_range."""
    lo, hi = idx_range
    if lo is None:
        return False
    hits = [i for i in range(lo, hi) if lines[i].rstrip('\r\n') == anchor]
    if len(hits) != 1:
        failures.append('%s: anchor %r matched %d times' % (tag, anchor, len(hits)))
        return False
    lines[hits[0] + 1:hits[0] + 1] = text
    return True

def ensure_include(lines, why):
    if not any(l.startswith('#include <stdio.h>') for l in lines):
        lines.insert(0, '#include <stdio.h>  /* [vpw2 HAND-EDIT] %s */\n' % why)


# ---------------- frame interpolation (60 fps) matrix hooks ----------------
# [vpw2][hfr] RT64 interpolates models from their camera-independent matrices, which the game only
# exposes when it multiplies them with the camera. func_80002108 (out = A * B) hands A and the camera to
# RT64 keyed by the output address; guMtxF2L (func_80034340) moves the entry to the fixed-point matrix that
# gSPForceMatrix uploads (lib/rt64/src/hle/rt64_rsp.cpp, wcw_interp_* functions). Neither function
# is hooked by a mod. The hooks only store matrices; RT64 uses them only at a framerate above 30.
def hfr_hand_edits():
    done = []
    lines = load_lines('funcs_0.c')
    if not any('wcw_interp_process_multiply(wcw_dst' in l for l in lines):
        rng = body_range(lines, 'func_80002108')
        if insert_after(lines, rng, '    int c1cs = 0;', [
                '    { /* [vpw2][hfr] func_80002108 is a 4x4 multiply (out = A * B). When B is the camera matrix\n',
                "         (0x80056F78), pass A (the object's camera-independent matrix) and B to RT64, keyed by\n",
                '         the output address; otherwise drop any stale entry for that address. */\n',
                '        extern void wcw_interp_process_multiply(uint32_t destAddr, uint32_t opBAddr, uint32_t srcAddr, const float* aMatrix16, const float* bMatrix16);\n',
                '        extern void wcw_interp_invalidate_local_matrix(uint32_t destAddr);\n',
                '        uint32_t wcw_dst = (uint32_t)ctx->r6;\n',
                '        if ((uint32_t)ctx->r5 == 0x80056F78u) {\n',
                '            union { uint32_t u; float f; } wcw_bits;\n',
                '            float wcw_a[16], wcw_b[16];\n',
                '            for (int wcw_i = 0; wcw_i < 16; wcw_i++) {\n',
                '                wcw_bits.u = (uint32_t)MEM_W(ctx->r4, wcw_i * 4); wcw_a[wcw_i] = wcw_bits.f;\n',
                '                wcw_bits.u = (uint32_t)MEM_W(ctx->r5, wcw_i * 4); wcw_b[wcw_i] = wcw_bits.f;\n',
                '            }\n',
                '            wcw_interp_process_multiply(wcw_dst, (uint32_t)ctx->r5, (uint32_t)ctx->r4, wcw_a, wcw_b);\n',
                '        }\n',
                '        else {\n',
                '            wcw_interp_invalidate_local_matrix(wcw_dst);\n',
                '        }\n',
                '    }\n'], 'hfr-matrix'):
            save_lines('funcs_0.c', lines)
            done.append('matrix hook (func_80002108)')
    lines = load_lines('funcs_14.c')
    if not any('wcw_interp_forward_local_matrix((uint32_t)' in l for l in lines):
        rng = body_range(lines, 'func_80034340')
        if insert_after(lines, rng, '    int c1cs = 0;', [
                "    { /* [vpw2][hfr] func_80034340 is guMtxF2L. Move the matrix hook's entry from the float source (a0)\n",
                '         to the fixed-point destination (a1) that gSPForceMatrix uploads. */\n',
                '      extern void wcw_interp_forward_local_matrix(uint32_t srcAddr, uint32_t dstAddr);\n',
                '      wcw_interp_forward_local_matrix((uint32_t)ctx->r4, (uint32_t)ctx->r5); }\n'], 'hfr-f2l'):
            save_lines('funcs_14.c', lines)
            done.append('F2L hook (func_80034340)')
    return 'frame interpolation hooks: ' + ('; '.join(done) if done else 'present')

def main():
    # Register hand-edits here as bring-up demands them. Pattern per edit:
    #   lines = load_lines('funcs_NN.c')
    #   if not any('[vpw2][mytag]' in l for l in lines):
    #       ensure_include(lines, 'mytag diagnostics')
    #       rng = body_range(lines, 'func_XXXXXXXX')
    #       insert_after(lines, rng, '<exact generated anchor line>',
    #                    ['<LF-terminated diagnostic lines>\n'], 'mytag')
    #       save_lines('funcs_NN.c', lines)
    applied = []

    # [vpw2][rt] Ray tracing experiment (exp/raytracing; src/game/raytracing.cpp): hand
    # RT64 the real camera. Both calls are no-ops unless WCW_RT is set.
    # The latch sits in the matrix multiply func_80001768 calls, not in func_80001768 itself:
    # mods hook func_80001768 (AkiMods' camera) and a hooked function is recompiled from the
    # ROM without hand-edits. Older generated files had it in func_80001768: strip that site.
    lines = load_lines('funcs_0.c')
    old = next((i for i, l in enumerate(lines) if '[vpw2][rt] camera latch: a1 = P, a2 = V' in l), None)
    if old is not None:
        del lines[old:old + 3]
        save_lines('funcs_0.c', lines)
        applied.append('removed old rt camera latch (func_80001768)')
    if not any('[vpw2][rt] camera latch: a0 = V' in l for l in lines):
        rng = body_range(lines, 'func_80002108')
        if insert_after(lines, rng, '    int c1cs = 0;',
                        ['    { /* [vpw2][rt] camera latch: a0 = V, a1 = P, a2 = product (the camera matrix when called from the camera builder) */\n',
                         '      extern void wcw_rt_latch_camera_multiply(uint8_t* rdram, uint32_t view_vaddr, uint32_t proj_vaddr, uint32_t dest_vaddr);\n',
                         '      wcw_rt_latch_camera_multiply(rdram, (uint32_t)ctx->r4, (uint32_t)ctx->r5, (uint32_t)ctx->r6); }\n'], 'rt-latch'):
            save_lines('funcs_0.c', lines)
            applied.append('rt camera latch (func_80002108)')
    lines = load_lines('funcs_1.c')
    if not any('[vpw2][rt]' in l for l in lines):
        rng = body_range(lines, 'func_800033D4')
        if insert_after(lines, rng, '    func_80002E40(rdram, ctx);',
                        ['    { /* [vpw2][rt] after the frame DL head is returned in v0 */\n',
                         '      extern uint32_t wcw_rt_emit_camera(uint8_t* rdram, uint32_t gfx);\n',
                         '      ctx->r2 = (int64_t)(int32_t)wcw_rt_emit_camera(rdram, (uint32_t)ctx->r2); }\n'], 'rt-emit'):
            save_lines('funcs_1.c', lines)
            applied.append('rt camera emit (func_800033D4)')
    applied.append(hfr_hand_edits())
    print('readd_hand_edits: ' + ('; '.join(applied) if applied else 'nothing registered (bootstrap state)'))
    if failures:
        for f_ in failures:
            print('FAIL: ' + f_, file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
