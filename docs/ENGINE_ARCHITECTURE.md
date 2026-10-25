# Engine architecture and binary map

Target image: `msttssyn.dll` (851 456 bytes, PE32 i386, preferred base
`0x63670000`, MD5 `306131d8ed2cf34bac1a3dc938e75163`), plus the SAPI4 wrapper
set in the same installer.

## 1. Modules and registration

| module | role |
|---|---|
| `msttssyn.dll` | SAPI4 engine `MSTTSSyn`, CLSID `{E0725551-286F-11d0-8E73-00A0C9083363}`, in-process, apartment. Exports only `DllGetClassObject` and `DllCanUnloadNow`. Contains the entire audio pipeline and the voice-file loader. |
| `wttsf22.dll`, `wttsm22.dll`, `wttss22.dll`, `wttsa22.dll`, `wttsmm.dll` | "Downloadable Whistler 4.0" ActiveX/voice helper modules, CLSIDs `{FD913800..FD913804-5CA2-11d2-A1E6-00A0C913D1EF}`. They export `DllRegisterServer` and register a type library; they are not on the sample-rendering path used here. |
| `wraptts.dll` | "Downloadable Whistler 3.0" wrapper, CLSID `{161FA782-A52C-11d0-8D7C-00A0C9034A7E}`. |
| `sam.vce` | Sam voice database (MD5 `205b87a3e056d8219f702272bb76b9b4`, see `FORMAT_SAM_VCE.md`). |
| `sam.cfg` | Sam voice configuration (CFG1, MD5 `f7b6e89451af34e3134abe42fb7d278d`). |

`msttssyn.dll` imports `StgOpenStorage` (ole32) and enumerates `*.vce` / `*.cfg`
in its install directory (`FUN_6367E0EE`, format strings `%s\*.vce` at
0x6371EFAC and `%s\*.cfg` at 0x6371EF98). `FUN_6367DE79` uses `CFG%hi`.
This is how voice tokens and their data files are discovered/registered.

## 2. Loading pipeline

```
DllGetClassObject
  └─ engine object
       ├─ FUN_63685471           voice data init (VcHeader, PhoneFile, TreeImage, Senone, AltUnits)
       └─ FUN_63681688           per-voice init (Inventory + resampler)
            ├─ open "VcHeader": read 0x8F8 bytes, free (format/version check)
            ├─ open "Inventory": FUN_636720F4
            │    ├─ FUN_63672010   header + 30 codebook matrices
            │    └─ unit block: count, byte length, offset table, sample area
            ├─ pick resampler by (sourceRate, outputRate)
            └─ FUN_63671063        voice state (rate, feature dims, scratch arrays)
```

Resampler selection in `FUN_63681688` (source → output):

| pair | constructor |
|---|---|
| 22050 → 8000 | `FUN_63678180` (0x19C bytes) |
| 11025 → 8000 | `FUN_63677EB8` (0x138 bytes) |
| 8000 → 11025 | `FUN_636782E4` (0xA0 bytes) |
| 22050 → 16000 | `FUN_6367801C` (0x138 bytes) |

The Sam database is 22 050 Hz, so the no-resample path is used when the voice
is rendered at 22 050 Hz.

## 3. Data structures

### Inventory object (`FUN_63672010` + `FUN_636720F4`)

```
+0x00  0
+0x04  sampleRate            (22050)
+0x08  nA = 6
+0x0C  nB = 11
+0x10  nC = 13
+0x14  A[nA]  -> { rows, cols, float *data }
+0x18  B[nB]
+0x1C  C[nC]
+0x20  unitCount             (3365)
+0x24  unitTable             pointer array; entry i points at unit i
+0x28  featureDim            (20)
+0x2C  fftSize                (512)
+0x30  aux                   (9)
+0x34  float table [aux*2]   (FUN_636850C0 init)
+0x38  float table           (FUN_63685172 init)
+0x3C  noise buffer (sampleRate bytes, deterministic rand())
+0x40  0
```

After the offset table is read, each entry is converted to an absolute pointer:

```
table[i] = buffer + 4*(count+1) + stored_offset[i]
```

### Voice state (`FUN_63671063`)

```
+0x00  Inventory*
+0x04  (float)sampleRate
+0x08  featureDim (20)
+0x14  float[featureDim+1]
+0x38  float[featureDim+1]
...
```

## 4. Unit rendering — `FUN_636719FA(inventory, unitIndex, state)`

Sequence (addresses are file RVA + base):

1. `unit = inventory->unitTable[unitIndex]` (`+0x24` array).
2. `n = *(u32*)unit`.
3. `FUN_63675C05(unit+4, n, pitch[], 0)` decodes `n` pitch values (see
   `FORMAT_SAM_VCE.md` §3.5). Returns bytes consumed.
4. Reads `6*n` bytes: per frame, six row indices into `A[0..5]`; copies
   `3+3+3+3+4+4 = 20` floats into the frame feature row.
5. `FUN_63678470(features, n, 20)` — feature conditioning
   (monotonicity fix-up `FUN_63688708`, cosine/cepstral transform, windowing;
   5.5 KB of code).
6. Copies `n` float32 gains from the stream.
7. Sums `|int(pitch[f])|` → `nSamples`; allocates output.
8. For each frame:
   * `pitch[f] <= 0` (unvoiced):
     `gain = gains[f] * 0.02`; copy `|pitch[f]|` bytes from
     `inventory->noiseBuffer` at a running phase, multiply by `gain`.
   * `pitch[f] > 0` (voiced):
     * if `f == 0` or `pitch[f-1] <= 0` → read **11** bytes and call
       `FUN_6368874C` for each of the 11 `B` matrices;
     * else → read **13** bytes and call `FUN_636887A7` for each of the 13
       `C` matrices;
     * `FUN_63684B60` performs the 512-point transform (split-radix FFT),
       `FUN_636886C6` scales by `gain`, `FUN_6368864B` overlap-adds into the
       output at `|pitch[f]|` hop.
9. Returns `{nFrames, nSamples, 20, pitch, features, samples, gains, 0}`.

Output is float32, amplitude not normalized; the SAPI layer converts/scales it
for the audio device.

## 5. Function map (RVA = VA − 0x63670000)

| VA | RVA | name | role |
|---|---|---|---|
| 0x63672010 | 0x2010 | FUN_63672010 | Inventory header + codebook arrays |
| 0x636720F4 | 0x20F4 | FUN_636720F4 | Inventory full loader + unit table |
| 0x63671063 | 0x1063 | FUN_63671063 | voice state init |
| 0x63681688 | 0x1688 | FUN_63681688 | per-voice init, resampler choice |
| 0x63685471 | 0x5471 | FUN_63685471 | VcHeader/PhoneFile/TreeImage/Senone/AltUnits loader |
| 0x636719FA | 0x19FA | FUN_636719FA | unit renderer (audio) |
| 0x63675C05 | 0x5C05 | FUN_63675C05 | pitch delta/RLE decoder |
| 0x63675D45 | 0x5D45 | FUN_63675D45 | deterministic noise buffer (uses `rand()`) |
| 0x63675C95 | 0x5C95 | FUN_63675C95 | Gaussian pair generator (Box–Muller on `rand()`) |
| 0x6367E0EE | 0xE0EE | FUN_6367E0EE | voice-file discovery (`*.vce`, `*.cfg`) |
| 0x6367DE79 | 0xDE79 | FUN_6367DE79 | `CFG%hi` voice configuration reader |
| 0x6367F73D | 0xF73D | FUN_6367F73D | PhoneFile parser |
| 0x63685B25 | 0x15B25 | FUN_63685B25 | AltUnits stream loader |
| 0x6368587F | 0x1587F | FUN_6368587F | AltUnits descriptor parser (per-phone) |
| 0x636732FA | 0x32FA | FUN_636732FA | TreeImage loader (IStream) |
| 0x636727FD | 0x27FD | FUN_636727FD | TreeImage loader (stream name) |
| 0x63673312 | 0x3312 | FUN_63673312 | CART tree reader |
| 0x63672880 | 0x2880 | FUN_63672880 | CART tree reader variant |
| 0x63678470 | 0x8470 | FUN_63678470 | feature conditioning / spectral transform |
| 0x63684B60 | 0x14B60 | FUN_63684B60 | 512-point FFT |
| 0x636886C6 | 0x186C6 | FUN_636886C6 | per-frame gain scaling |
| 0x6368864B | 0x1864B | FUN_6368864B | overlap-add |
| 0x6368874C | 0x1874C | FUN_6368874C | group-B voiced-frame synthesis |
| 0x636887A7 | 0x187A7 | FUN_636887A7 | group-C voiced-frame synthesis |
| 0x636850C0 | 0x150C0 | FUN_636850C0 | init float table (inventory+0x34) |
| 0x63685172 | 0x15172 | FUN_63685172 | init float table (inventory+0x38) |
| 0x63688708 | 0x18708 | FUN_63688708 | monotonicity fix-up |
| 0x63678180 / 77EB8 / 782E4 / 7801C | — | resamplers | rate-pair resampling |

Decompiled dumps: `mstts.json` (784 functions, 1343 defined strings),
`wtts.json` (243 functions) — produced with Ghidra 12.2 headless/pyghidra.

## 6. Senone / phone / selection data

`FUN_63685471` reads:

* `VcHeader` — 0x8F8 bytes; first 16 bytes are compared with the version-1
  GUID `{11825730-70C8-11D1-B1CB-0000F803E456}` (`DAT_6369F168`); a mismatch
  selects layout version 2 (`voice+0x298 = 2`). Sam's `VcHeader` starts with
  `{A3507CC7-6728-11D1-847B-444553540000}` → version 2.
* `PhoneFile` — ASCII table (`FUN_6367F73D`), builds `voice+0x290`.
* `TreeImage` — CART (`FUN_636732FA`/`FUN_636727FD`), builds `voice+0x294`
  and a count at `voice+0x29C`.
* `Senone` — `u32 count` then 28-byte records; fills indexed arrays.
* `AltUnits` — `u32 byteSize` + payload; `FUN_63685B25` →
  `FUN_6368587F` builds per-phone descriptors at `voice+0x2C8`.

`Cdb` is never opened by this DLL.

## 7. Determinism

* `FUN_63675D45` fills the noise buffer with Gaussian pairs from MSVCRT
  `rand()` (`FUN_63675C95`). No `srand` call exists in the engine, so the CRT
  default seed (1) applies; the noise buffer is identical in every process.
* Rendering a unit with a zeroed 0x200-byte state is deterministic; verified
  across process boundaries for units 1, 5, 100, 2000, 3365 and for the full
  3365-unit archive hash.

## 8. Why the engine is called directly

Windows 10/11 has no SAPI4 runtime and the voice pack is 32-bit, so COM
registration is not required for analysis. `msttssyn.dll` exposes the loader
and renderer as ordinary cdecl functions; a 32-bit host can call them by RVA.
The only external setup is an `IStream` over the raw `Inventory` bytes
(`SHCreateMemStream`) and a zeroed state buffer.

This gives a bit-exact oracle without SAPI4, DirectSound, or the registry.
