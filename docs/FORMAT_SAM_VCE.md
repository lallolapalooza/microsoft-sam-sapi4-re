# `sam.vce` / SAPI4 voice database format

All integers little-endian. Offsets below are for the 22 050 Hz Sam database
(`sam.vce`, 1 623 552 bytes). The 8 kHz variants use the same layout.

## 1. Container

`sam.vce` is an OLE Compound File (CFB). Streams:

| stream | size | role |
|---|---|---|
| `VcHeader` | 2296 | identity/metadata block |
| `Inventory` | 1 395 733 | codebooks + unit inventory (the audio model) |
| `Senone` | 93 328 | 3333 senone records |
| `PhoneFile` | 1456 | ASCII phone table |
| `TreeImage` | 113 335 | serialized CART tree |
| `AltUnits` | 328 | per-phone alternate-unit descriptors |
| `Cdb` | 917 | ASCII cluster statistics (unused by the engine) |

`sam.cfg` (7680 bytes) is a separate CFB with `VcHeader` + `CFG1` (2876 bytes).

## 2. `VcHeader`

Fixed-size block:

* `0x000` 16-byte GUID: `c7 7c 50 a3 28 67 d1 11 84 7b 44 45 53 54 00 00`.
* `0x010` fixed-capacity UTF-16 fields: `Microsoft`, voice name (`Sam`),
  language (`US English`), voice class (`Second Male Voice`), description.
* trailer (last 0x30 bytes) contains `u16` parameter pairs and the rates
  `22050` (`0x5622`) and `44100` (`0xAC44`).

`msttssyn.dll` opens the stream, reads exactly `0x8F8` bytes and discards them
(`FUN_63681688`); it serves as validation/metadata only. Voice behaviour is
driven by `Inventory`.

## 3. `Inventory`

### 3.1 Header (7 × u32, 28 bytes)

| offset | value (Sam) | meaning |
|---|---|---|
| 0x00 | 22050 | source sample rate |
| 0x04 | 20 | feature dimension per frame |
| 0x08 | 6 | number of group-A codebooks |
| 0x0C | 11 | number of group-B codebooks |
| 0x10 | 13 | number of group-C codebooks |
| 0x14 | 512 | FFT size used by the synthesizer |
| 0x18 | 9 | auxiliary/table parameter |

### 3.2 Codebook matrices

Immediately after the header: `6 + 11 + 13 = 30` matrices, serialized as

```
u32 rows
u32 cols
float32 data[rows * cols]      // row-major
```

Sam's dimensions, in order:

* group A (6): `256×3, 256×3, 256×3, 256×3, 256×4, 256×4`
  (used as `3+3+3+3+4+4 = 20` features per frame)
* group B (11): `128×10, 128×10, 128×16, 128×22, 128×28,
  128×32, 128×36, 128×40, 128×60, 128×100, 128×156`
* group C (13): `128×10, 128×10, 128×10, 128×12, 128×12, 128×14,
  128×18, 128×32, 128×36, 128×40, 128×60, 128×100, 128×156`

Group A ends at `0x504C`, group B at `0x44CA4`, group C at `0x8490C`.

Group A vectors form the 20-dimensional spectral feature of a frame.
Groups B/C are the "first voiced frame after unvoiced" and "subsequent voiced
frame" spectral codebooks (see §3.5). A matrix row is a codebook entry.

### 3.3 Unit block (at `0x8490C`)

```
u32 unitCount           // 3365
u32 blockBytes          // 852737
u32 offset[unitCount+1] // byte offsets from sample-area base
u8  sampleArea[blockBytes - 4*(unitCount+1)]   // 839273 bytes
```

`offset[0] = offset[1] = 0`; unit indices are `1..unitCount`.
Unit `i` occupies `sampleArea[offset[i] .. offset[i+1])`; the last unit ends at
the end of the sample area.

### 3.4 Unit record

```
u32  nFrames                      // 2..47
u8   pitchStream[]                // delta/RLE encoding, nFrames values
u8   featureIndex[nFrames][6]     // rows into group-A matrices 0..5
f32  gain[nFrames]
u8   extra[]                      // per voiced frame: 11 or 13 bytes
```

Total record length is exactly

```
4 + len(pitchStream) + 6*nFrames + 4*nFrames + len(extra)
```

and this was verified for all 3365 units (0 mismatches).

### 3.5 Pitch stream codec

Decoded with `base = 0` (`FUN_63675C05` takes the base as its 4th argument):

```
for each of nFrames:
    c = signed_byte(stream[i])
    if c == 0x7F:
        v = base + 127.0
        while signed_byte(stream[i]) == 0x7F:
            v += signed_byte(stream[i+1]); i += 1
        emit(v); i += 1
    elif c == 0x80:              # -128
        v = -128.0 - base
        while signed_byte(stream[i]) == 0x80:
            v += signed_byte(stream[i+1]); i += 1
        emit(v); i += 1
    else:
        emit(c - base if c < 1 else base + c); i += 1
```

The escape runs emit one value per loop iteration after accumulating all
following bytes in the run; the last byte of a run is the final delta and is
consumed. `v > 0` means voiced; the frame duration is `|int(v)|` samples.
`v <= 0` means unvoiced.

Sam unit 1 decodes to `[206, 221, 235, 249, 265, 293, 237, -237]`.

### 3.6 Extra per-frame indices

For frame `f = 0..nFrames-1`, if `pitch[f] > 0`:

* `f == 0` or `pitch[f-1] <= 0` → read **11** bytes, one row index into each
  group-B matrix;
* otherwise → read **13** bytes, one row index into each group-C matrix.

Unvoiced frames consume no extra bytes.

This exactly accounts for every remaining byte in every unit.

### 3.7 Unit waveform model

`FUN_636719FA(inventory, unitIndex, voiceState)` returns:

```
struct {
    int nFrames;        // +0x00
    int nSamples;       // +0x04  sum of |pitch|
    int featureDim;     // +0x08  = 20
    float *pitch;       // +0x0C  nFrames floats
    float *features;    // +0x10  nFrames * (20+1) floats
    float *samples;     // +0x14  nSamples float32
    float *gains;       // +0x18  nFrames floats
    int    reserved;    // +0x1C
}
```

* Unvoiced frame: `|pitch|` samples are taken from a deterministic noise buffer
  (`inventory+0x3C`, generated by `FUN_63675D45` using MSVCRT `rand()`), then
  scaled by `gain * 0.02`.
* Voiced frame: the 20 features (group-A rows) plus group-B/C rows are turned
  into a 512-point spectral frame, scaled by the gain, inverse-transformed and
  overlap-added; the frame contributes `|pitch|` samples.
* `nSamples == sum(|int(pitch[f])|)` for every unit.

## 4. `Senone`

```
u32 count                  // 3333
record[count] {            // 28 bytes each
    u32 marker;            // always 0x42
    u32 zero;
    u32 id;                // 1..3333
    f32 f0, f1, f2, f3;
}
```

The voice loader (around `0x63685620`) builds indexed tables from these
records. The four floats behave like spectral/formant prototypes; the exact
use belongs to the selection layer.

## 5. `PhoneFile`

ASCII, one phone per record, parsed with `"%s %d %d %d %d"`
(`FUN_6367F73D`):

```
+NOISE+          0 0  0  0
B                0 0  1  1
...
JH               0 0  8  8
...
AA1              0 1 26 26
...
UW0              0 1 51 51
```

51 phones plus `+NOISE+`. Columns 4 and 5 are identical for every record
(phone id / nominal value). Unit records do **not** store a phone id.

## 6. `AltUnits`

```
u32 payloadBytes           // 324
u8  payload[payloadBytes]
```

Parsed by `FUN_63685B25` → `FUN_6368587F` into one descriptor per phone
(indexed like `PhoneFile`). Each descriptor holds counts and parallel arrays
of alternate-unit attributes. It is part of the selection layer; the sample
renderer does not read it.

## 7. `TreeImage` (CART)

Observed header (Sam):

```
00 00 06 AB 00 00 00 02
"\\msr\speech\stg\whisper\senoclus\cart\standard.fea\0" (path, padded)
```

Then serialized nodes and 73 feature-name strings, e.g. `WDBNDRY_B`,
`WDBNDRY_E`, `ASPSEG`, `ALVSTP`, `DENTAL`, `LIQUID`, `NASAL`, `VELAR`,
`VOWEL`, `STRESS0`, `STRESS1`, `VOICED`, `MALONE`, `NALONE`, ...
Loaded by `FUN_636732FA` (IStream) / `FUN_636727FD` (stream name), parsed by
`FUN_63673312` / `FUN_63672880`.

## 8. `Cdb` and `sam.cfg`

* `Cdb` is ASCII cluster statistics (phone-like labels with `on/off` mean and
  standard deviation). No reference to the string `Cdb` exists in
  `msttssyn.dll`; treat it as authoring data.
* `sam.cfg` streams `CFG1` (2876 bytes) start with GUID
  `00 50 43 5B 52 97 D1 11 B1 CE 00 00 F8 03 E4 56` and contain voice
  parameter blocks. They are not parsed by `Inventory` loading; they belong to
  the SAPI4 voice configuration path (`CFG%hi`, `*.cfg` strings exist in the
  engine image but no code reference to them was found in the audio path).

## 9. Quick invariants

* `22050` source rate; `512` FFT; `20` features/frame.
* 3365 units; unit `i` uses `offset[i]`.
* `offset[0] = offset[1] = 0`.
* `nFrames` in `2..47`.
* `nSamples = Σ |int(pitch)|`.
* Sam archive hash (all unit float32 samples, unit order):
  `3c0cb515f17e79ee7a5b2401700314ef93d31521497a4275c3d849081a99b115`.
