# Parity

## Definition

For this target, “voice samples archive parity” means:

1. Every unit in `sam.vce`’s Inventory (1..3365) is rendered.
2. Rendering uses the original engine code (`msttssyn.dll`, `FUN_636719FA`) with
   a zeroed voice state, at 22 050 Hz, float32 mono.
3. The concatenation of all unit samples in index order hashes exactly to the
   reference value.
4. Re-parsing `sam.vce` reproduces every unit’s record layout, frame count and
   sample count with no exceptions.

The WAV files are PCM16 derivatives for listening; **parity is measured on the
float32 `.f32` files**, not on the WAV encoding.

## Reference hash

```
units       = 3365
samples     = 7638248
rate        = 22050
sha256(concat(unit_00001.f32 .. unit_03365.f32))
            = 3c0cb515f17e79ee7a5b2401700314ef93d31521497a4275c3d849081a99b115
```

Per-unit hashes are in `archive/manifest.json`; `archive/archive.json` holds
the aggregate.

## Verification performed

### 1. Full re-render in a fresh process

`verify_engine.py` (32-bit Python, new process, new DLL load) renders all 3365
units and compares `nframes`, `nsamples` and SHA-256 per unit against
`manifest.json`:

```
units 3365 mismatches 0
archive_sha256 3c0cb515f17e79ee7a5b2401700314ef93d31521497a4275c3d849081a99b115
ENGINE_PARITY_OK
```

### 2. Structural parse of the source database

`verify.py` parses `Inventory` independently and checks, for all units:

* record length `== 4 + pitchBytes + 6*n + 4*n + extras`;
* `nframes` matches the engine;
* `nsamples == Σ |int(pitch)|`;
* every codebook index is within its matrix;
* each archived file has the expected length and SHA-256.

```
units 3365 samples 7638248 bad 0
STRUCTURAL_PARITY_OK
```

### 3. Determinism

* `FUN_63675D45` seeds the noise buffer from MSVCRT `rand()`; the engine never
  calls `srand`, so the CRT default seed (1) is used.
* Units 1, 5, 100, 2000, 3365 rendered identically in two separate processes.
* A zeroed 0x200-byte state makes each unit’s rendering independent of call
  order.

### 4. Frame count proof

Patching unit 1’s first `u32` from 8 to 5 in a copy of `Inventory` changes the
engine’s reported frame count to 5 and sample count from 1943 to 1176
(`206+221+235+249+265`). The first field is therefore the frame count, not a
phone id.

## What is not claimed

* Concatenated sentence rendering (state/phase carried across units, prosody,
  resampling, SAPI4 buffering) is not part of this archive.
* The archive contains isolated-unit renderings. They are deterministic and
  engine-exact for that definition.
* `AltUnits`, `TreeImage` and `Senone` selection semantics are documented
  structurally but not reimplemented.

## Reproduce

```bash
# 32-bit Python 3.12 embeddable at py32/
python - <<'PY'
import olefile
open('inv.bin','wb').write(olefile.OleFileIO('pack/sam.vce').openstream('Inventory').read())
PY
py32/python.exe tools/extract_archive.py   # ~140 s, writes archive/
py32/python.exe tools/verify_engine.py     # ~8 s
python tools/verify_structure.py           # ~2 s
```
