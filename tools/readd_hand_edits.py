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
    lines = load_lines('funcs_0.c')
    if not any('[vpw2][rt]' in l for l in lines):
        rng = body_range(lines, 'func_80001768')
        if insert_after(lines, rng, '    ctx->r4 = ADD32(ctx->r6, 0);',
                        ['    { /* [vpw2][rt] camera latch: a1 = P, a2 = V */\n',
                         '      extern void wcw_rt_latch_camera(uint8_t* rdram, uint32_t proj_vaddr, uint32_t view_vaddr);\n',
                         '      wcw_rt_latch_camera(rdram, (uint32_t)ctx->r5, (uint32_t)ctx->r6); }\n'], 'rt-latch'):
            save_lines('funcs_0.c', lines)
            applied.append('rt camera latch (func_80001768)')
    lines = load_lines('funcs_1.c')
    if not any('[vpw2][rt]' in l for l in lines):
        rng = body_range(lines, 'func_800033D4')
        if insert_after(lines, rng, '    func_80002E40(rdram, ctx);',
                        ['    { /* [vpw2][rt] after the frame DL head is returned in v0 */\n',
                         '      extern uint32_t wcw_rt_emit_camera(uint8_t* rdram, uint32_t gfx);\n',
                         '      ctx->r2 = (int64_t)(int32_t)wcw_rt_emit_camera(rdram, (uint32_t)ctx->r2); }\n'], 'rt-emit'):
            save_lines('funcs_1.c', lines)
            applied.append('rt camera emit (func_800033D4)')
    print('readd_hand_edits: ' + ('; '.join(applied) if applied else 'nothing registered (bootstrap state)'))
    if failures:
        for f_ in failures:
            print('FAIL: ' + f_, file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
