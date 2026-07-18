#!/usr/bin/env python3
"""Convert audit_coresidency.py findings into syms/extra_funcs.txt mid-entries.

For each "co-loadable <ovl> has no function start at <vram>" violation, add
"<ovl> func_<vram> 0x<vram> <size>" where size runs to the end of the
containing function in THAT overlay (or to the next function start if the
target sits in a gap) — recomp_loop.py's sizing convention. Idempotent:
skips entries already present. Run: pipe audit output in, or let it invoke
the audit itself (default)."""
import re, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

r = subprocess.run([sys.executable, 'tools/audit_coresidency.py'],
                   capture_output=True, text=True)
viol = set()
for m in re.finditer(r'calls 0x([0-9A-Fa-f]{8}): co-loadable (\w+) has no', r.stdout):
    viol.add((m.group(2), int(m.group(1), 16)))
if not viol:
    print('no violations to convert')
    sys.exit(0)

# functions per section from dump.toml
dump = open('syms/dump.toml', encoding='utf-8').read()
sec = None
funcs = {}  # sec -> sorted [(vram, size)]
for line in dump.split('\n'):
    mm = re.match(r'name = "(\w+)"', line)
    if mm: sec = mm.group(1)
    fm = re.search(r'\{ name = "\w+", vram = (0x[0-9A-Fa-f]+), size = (0x[0-9A-Fa-f]+)', line)
    if fm: funcs.setdefault(sec, []).append((int(fm.group(1), 16), int(fm.group(2), 16)))
for s in funcs: funcs[s].sort()

existing = open('syms/extra_funcs.txt').read() if os.path.exists('syms/extra_funcs.txt') else ''
added = 0
with open('syms/extra_funcs.txt', 'a', newline='\n') as f:
    for ovl, target in sorted(viol):
        line_key = f'{ovl} func_{target:08X}'
        if line_key in existing:
            continue
        fl = funcs.get(ovl, [])
        size = None
        for vram, sz in fl:
            if vram < target < vram + sz:
                size = vram + sz - target; break
        if size is None:
            nxts = [vram for vram, _ in fl if vram > target]
            if not nxts:
                print(f'SKIP {ovl} 0x{target:08X}: no containing function or successor')
                continue
            size = nxts[0] - target
        f.write(f'{ovl} func_{target:08X} 0x{target:08X} 0x{size:X}\n')
        print(f'added {ovl} func_{target:08X} 0x{target:08X} 0x{size:X}')
        added += 1
print(f'{added} entries added')
