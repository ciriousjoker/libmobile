# Firmware protocol tests

Requires Python 3.10+ and a C11 compiler (`cc`, or `$CC`). From the repository root:

```sh
python3 tests/run.py
```

Put these private, unmodified dumps in `tests/firmware_emulator/roms/` (ignored by Git):

- `DDI_SST_39VF400_00-07FFFF.bin`
- `cdmaOne_SST_39VF400_00-07FFFF.bin`

Only the SHA-256 values in `firmware.py` are accepted. No Ghidra installation is
needed. `--target firmware` checks the dumps; `--target libmobile` checks the same
contracts without needing the dumps. Reports are written to `tests/reports/` as HTML,
Markdown, and JSON. Exit codes: **0** all pass, **1** contract/runtime failures,
**2** missing inputs or build errors. Current libmobile differences are real FAILs.

The tests exchange complete 8-bit game packets. `cpu.py` executes the original
serial and command routines. EEPROM operations, phone status/disconnect, and
socket calls are substituted; connected TCP/UDP cases explicitly seed an open
connection. These tests do not validate the AT path, physical timings, 32-bit
transfers, or the original network stack. The reported DDI AT dump corruption is
unverified. Each HTML result lists the substitutions it actually used.

Harness checks: `python3 -m unittest discover -s tests -p test_harness.py`.
