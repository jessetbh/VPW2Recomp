# VPW2 libultra function identification — evidence log

Recon 2026-07-17, tools/vpw2_recon2.py + vpw2_recon3.py. Fingerprint source:
../NoMercyRecomp/syms/dump.toml named fixed-segment set (51 functions), masked
full-body match (j/jal opcodes masked to opcode-only, immediate-class ops masked
to opcode+regs) against VPW2's fixed segment (rom 0x1000..0x3A214). Result:
**36/51 unique transfers, 0 wrong-looking, 5 ambiguous (resolved below), 9
osFlash* no-match (expected — SRAM title), osGetCount too-small (resolved
below)**. VPW2 (Jan 2000) sits between WM2000 (Oct 1999) and No Mercy (Nov
2000); the transfer confirms the same libultra generation as No Mercy's.

## Unique full-body fingerprint transfers (36)

Each matched No Mercy's masked body at exactly one fixed-segment address:

| Function | VPW2 rom | VPW2 vram |
|---|---|---|
| game_main | 0x001060 | 0x80000460 |
| osDriveRomInit | 0x023F10 | 0x80023310 |
| __osDisableInt | 0x02BC20 | 0x8002B020 |
| __osRestoreInt | 0x02BC90 | 0x8002B090 |
| osSetIntMask | 0x02BCB0 | 0x8002B0B0 |
| osCreatePiManager | 0x02BD50 | 0x8002B150 |
| osEPiStartDma | 0x02C0D0 | 0x8002B4D0 |
| osCartRomInit | 0x02C1C0 | 0x8002B5C0 |
| osAiSetFrequency | 0x02D270 | 0x8002C670 |
| osAiSetNextBuffer | 0x02D390 | 0x8002C790 |
| osContInit | 0x0312B0 | 0x800306B0 |
| osVirtualToPhysical | 0x031620 | 0x80030A20 |
| osCreateMesgQueue | 0x033210 | 0x80032610 |
| osJamMesg | 0x033240 | 0x80032640 |
| osRecvMesg | 0x033380 | 0x80032780 |
| osSendMesg | 0x0334B0 | 0x800328B0 |
| osSetEventMesg | 0x0335E0 | 0x800329E0 |
| osSpTaskLoad | 0x033690 | 0x80032A90 |
| osSpTaskStartGo | 0x03389C | 0x80032C9C |
| osSpTaskYield | 0x0338D0 | 0x80032CD0 |
| osSpTaskYielded | 0x0338F0 | 0x80032CF0 |
| __osSiRawStartDma | 0x033940 | 0x80032D40 |
| osCreateThread | 0x033BD0 | 0x80032FD0 |
| osGetThreadPri | 0x033CA0 | 0x800330A0 |
| osSetThreadPri | 0x033CC0 | 0x800330C0 |
| osStartThread | 0x033D90 | 0x80033190 |
| osGetTime | 0x033F40 | 0x80033340 |
| osCreateViManager | 0x034560 | 0x80033960 |
| osViSetEvent | 0x0348A0 | 0x80033CA0 |
| osViSetMode | 0x034900 | 0x80033D00 |
| osViSetSpecialFeatures | 0x034950 | 0x80033D50 |
| osViSetYScale | 0x034AC0 | 0x80033EC0 |
| osViSwapBuffer | 0x034B10 | 0x80033F10 |
| osViBlack | 0x034E70 | 0x80034270 |
| osInitialize | 0x037E78 | 0x80037278 |
| osDestroyThread | 0x039270 | 0x80038670 |

## Ambiguity resolutions (vpw2_recon3.py, sisters' evidence patterns)

- **osAiGetLength = rom 0x2D250 / vram 0x8002C650**: `lui $v0,0xA450; ori 0x0004;
  jr; lw` — reads AI_LEN 0xA4500004.
- **osAiGetStatus = rom 0x2D260 / vram 0x8002C660**: same shape reading
  AI_STATUS 0xA450000C. Third fingerprint candidate (0x390F0) reads SP_STATUS
  0xA4040010 — an SP helper, not AI.
- **osViGetCurrentFramebuffer = rom 0x344E0 / vram 0x800338E0** and
  **osViGetNextFramebuffer = rom 0x34520 / vram 0x80033920**: the adjacent
  0x40-apart pair, WT/NM source order (Current first). Current loads the global
  at 0x8005xxxx-0x65D0 (+0x9A30 page offset), Next the adjacent word +0x9A34
  (__osViCurr/__osViNext), then both `lw $s0, 0x4(ptr)` bracketed by
  jal __osDisableInt (0x8002B020) / __osRestoreInt (0x8002B090) — the jal
  targets match the transferred addresses (cross-consistency check passed).
- **__osSiDeviceBusy = rom 0x39C40 / vram 0x80039040**: exact `lui $v0,0xA480;
  ori 0x0018; lw; andi 0x3` = SI_STATUS busy bits. Other candidate (0x390D0)
  reads SP_STATUS 0xA4040010 andi 0x1C — the SP variant.
- **osGetCount = rom 0x39070 / vram 0x80038470**: too small to fingerprint;
  the `mfc0 $v0, $Count` word 0x40024800 appears at EXACTLY ONE fixed-segment
  offset (followed by `jr $ra`). NEVER stub (WM2000 frozen-clock lesson).

## Save type: SRAM confirmed

All NINE No Mercy osFlash* entry points (osFlashInit/ReadId/AllErase/
SectorErase/WriteBuffer/WriteArray/ReadArray/ReadStatus/ClearStatus) found NO
masked-body match anywhere in VPW2's fixed segment — the flash driver is not in
this ROM. NA2J's documented SRAM 256Kbit save stands; `SaveType::Sram` in
src/main/main.cpp is correct. (Final confirmation will come free at first boot:
a flash title crashes in raw PI_STATUS polling like No Mercy's did.)

## Input-path boot invariants (all sisters, applied here)

Rename ONLY osContInit + __osSiRawStartDma + __osSiDeviceBusy for input; do NOT
rename osContStartReadData (kills the raw-SI path). NEVER stub osGetCount.
