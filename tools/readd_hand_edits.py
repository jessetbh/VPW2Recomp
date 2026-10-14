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

# [wcw fix] Widescreen cull (aki-roadmap#47 / #5). func_800027F8 builds the visible-object lists of the
# layer passes and drops an object when |x| / (depth + 150) > 1.5 or |y| / (depth + 150) > 1.5
# (view space; the AKI engine's per-object cull, the same as No Mercy's func_800024F8). That is about
# 3.8x the 4:3 screen edge, but with Aspect Ratio = Expand RT64 shows a wider view, and large set pieces
# whose center is past the line while their geometry reaches into the extra width were culled at the
# screen edges (edge pop-in). Scale only the horizontal limit by the screen's widening
# (wcw_widescreen_cull_scale, src/game/recomp_api.cpp: 1 at Original). The projection is untouched
# (RT64's Expand widens it). Never hook func_800027F8 from a mod: a hooked function is recompiled from the
# ROM without this edit.
WCW_CULL_FUNC = 'func_800027F8'
WCW_CULL_X_LOAD = '    ctx->f12.u32l = MEM_W(ctx->r16, 0X18);'
WCW_CULL_COMPARE = '    c1cs = ctx->f22.d < ctx->f0.d;'
WCW_CULL_EDIT = [
    '    /* [wcw fix] widescreen cull: the horizontal limit follows the screen width (aki-roadmap#47). */\n',
    '    c1cs = (ctx->f22.d * wcw_widescreen_cull_scale()) < ctx->f0.d;\n',
]
WCW_CULL_DECLS = [
    '/* [wcw fix] widescreen cull scale, implemented in src/game/recomp_api.cpp. */\n',
    'extern double wcw_widescreen_cull_scale(void);\n',
]

def widescreen_cull_edit():
    """Replace the cull's horizontal compare (the first after the x load) in place. Fails loudly if the
    generated code changed shape."""
    import glob, os as _os, sys as _sys
    funcs = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), 'RecompiledFuncs')
    sig = 'RECOMP_FUNC void %s(' % WCW_CULL_FUNC
    for path in sorted(glob.glob(_os.path.join(funcs, 'funcs_*.c'))):
        with open(path, 'rb') as f:
            lines = f.read().decode('utf-8', errors='replace').splitlines(keepends=True)
        start = next((i for i, l in enumerate(lines) if l.startswith(sig)), None)
        if start is None:
            continue
        if any('wcw_widescreen_cull_scale' in l for l in lines):
            return 'widescreen cull (already present)'
        end = next(i for i in range(start, len(lines)) if lines[i].rstrip('\r\n') == ';}')
        loads = [i for i in range(start, end) if lines[i].rstrip('\r\n') == WCW_CULL_X_LOAD]
        compares = [i for i in range(loads[0], end) if lines[i].rstrip('\r\n') == WCW_CULL_COMPARE] if len(loads) == 1 else []
        if len(loads) != 1 or len(compares) != 2:
            _sys.exit('widescreen cull: %s changed shape (%d x loads, %d compares); re-derive the edit'
                      % (WCW_CULL_FUNC, len(loads), len(compares)))
        lines[compares[0]:compares[0] + 1] = WCW_CULL_EDIT
        last_include = max((i for i, l in enumerate(lines) if l.startswith('#include')), default=-1)
        lines[last_include + 1:last_include + 1] = WCW_CULL_DECLS
        with open(path, 'wb') as f:
            f.write(''.join(lines).encode('utf-8'))
        return 'widescreen cull -> %s %s' % (_os.path.basename(path), WCW_CULL_FUNC)
    _sys.exit('widescreen cull: %s not found in RecompiledFuncs' % WCW_CULL_FUNC)

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
    applied.append(widescreen_cull_edit())
    print('readd_hand_edits: ' + ('; '.join(applied) if applied else 'nothing registered (bootstrap state)'))
    if failures:
        for f_ in failures:
            print('FAIL: ' + f_, file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
