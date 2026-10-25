# Microsoft Sam (SAPI4) — voice database reverse engineering

Reverse engineering of the 1999 Microsoft Text-to-Speech 4.0 pack
(archive.org item `Sam_mike_and_mary`), focused on **Microsoft Sam**:
`sam.vce` container, unit inventory format, engine architecture, and a
bit-exact unit sample archive.

## Result

* `sam.vce` is an OLE Compound File holding a concatenative voice database:
  30 float codebook matrices, a **3365-unit** inventory, a CART tree, a
  senone table, a phone table, and alternate-unit descriptors.
* The unit record format was fully decoded and validated on every unit:
  frame count, delta/RLE pitch stream, six feature-codebook indices per frame,
  per-frame gains, and 11/13 extra codebook indices per voiced frame.
* All 3365 unit waveforms were rendered by the **original engine code**
  (`msttssyn.dll`, called directly from a 32-bit harness) and archived.

Parity (ground truth = original engine rendering, 22 050 Hz mono float32,
zeroed per-unit state):

| item | value |
|---|---|
| units | 3365 |
| samples | 7 638 248 (~346.4 s) |
| archive SHA-256 (unit files concatenated in index order) | `3c0cb515f17e79ee7a5b2401700314ef93d31521497a4275c3d849081a99b115` |
| fresh-process re-render | 0 mismatches |
| structural re-parse of `Inventory` | 0 mismatches |

## Repository layout

```
archive/manifest.json        per-unit metadata + SHA-256
archive/archive.json         aggregate result
archive/SHA256SUMS           hash of every file in the sample zip
sam_voice_samples.zip        3365 .f32 + 3365 .wav + manifests (30.9 MB)
omp-session-archive.zip      full omp session transcript, artifacts, viewer
docs/                        format, engine, reimplementation and parity docs
tools/                       oracle, extractor, verifiers, Ghidra dump script
mstts.json / wtts.json       full Ghidra decompilation dumps
```

## Documents

* [`docs/FORMAT_SAM_VCE.md`](docs/FORMAT_SAM_VCE.md) — container and
  `Inventory`/`Senone`/`PhoneFile`/`AltUnits`/`TreeImage` layouts.
* [`docs/ENGINE_ARCHITECTURE.md`](docs/ENGINE_ARCHITECTURE.md) — DLL roles,
  CLSIDs, loader/synthesis function map, determinism.
* [`docs/REIMPLEMENTATION.md`](docs/REIMPLEMENTATION.md) — exact algorithms,
  test vectors, unknowns.
* [`docs/PARITY.md`](docs/PARITY.md) — parity definition, measurements,
  reproduction.

## Verify the published archive

No original Microsoft binaries are needed:

```bash
python tools/verify_archive.py
```

It checks all 3365 entries, per-unit SHA-256, the `SHA256SUMS` list, and the
aggregate archive hash.

## Reproducing from scratch

1. Download the installer from
   `https://archive.org/download/Sam_mike_and_mary/microsoft_sam%2C_mike%2C_and_mary.exe`
   (MD5 `085971ddcc6a8252a28c59768a33e055`).
2. Carve the embedded MSCF cabinet at file offset `0x10658` and expand it
   (`expand pack.cab -F:* pack`).
3. Extract the `Inventory` stream from `pack/sam.vce` to `inv.bin`.
4. Run the oracle (32-bit Python required):

```bash
py32/python.exe tools/extract_archive.py    # renders every unit (~140 s)
py32/python.exe tools/verify_engine.py      # fresh-process parity check
python tools/verify_structure.py            # source-database parse check
```

`tools/verify_engine.py` and `tools/verify_structure.py` need the original
`pack/` and `inv.bin`; they are not redistributed here.

## Session archive

`omp-session-archive.zip` was produced with
[`omp-archive`](https://github.com/alosslessdev/omp-archive-main)
(`xd://export_session_archive`): main transcript, untruncated tool logs,
background-job state, and the standalone `viewer.html`.

SHA-256: `e3e326ab87d5426935840c9e17f2f59edcc6687cb5c040b18a2286d1ca56b09c`

It is **sanitized**: the local username in paths, personal names and all email
addresses were replaced (`user`, `[redacted-email]`). It was also scanned for
credential patterns; none were found. Other tool output and the full
conversation are preserved verbatim.

## Provenance and licensing

* Code and documentation in this repository: MIT (see `LICENSE`).
* Microsoft Sam voice data, the original `sam.vce`, `msttssyn.dll` and the
  installer are **not** included. The sample archive is derived output from
  those files and remains subject to Microsoft's rights; it is published for
  research and preservation. See `DATA_PROVENANCE.md`.

## Notes / limits

* Only Sam is analysed. Mike/Mary use the same format and engine.
* Archive samples are **isolated per-unit renderings** (zeroed engine state),
  not concatenated sentences.
* Phone→unit selection semantics (`TreeImage`, `AltUnits`, `Senone`) are
  documented structurally, not reimplemented.
* `Cdb` is authoring metadata and is never opened by the engine.
* A pure bit-exact DSP reimplementation is not provided; the engine oracle is
  the reference for the published hashes.
