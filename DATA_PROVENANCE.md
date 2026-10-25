# Provenance

## Source

* Archive.org item: `Sam_mike_and_mary` — “Microsoft Text To Speech Pack”
  (Microsoft, 1999).
* File: `microsoft_sam,_mike,_and_mary.exe`
  (7 674 104 bytes, MD5 `085971ddcc6a8252a28c59768a33e055`).
* Installer: WEXTRACT self-extractor; embedded LZX cabinet at file offset
  `0x10658`.
* Relevant extracted files: `sam.vce` (MD5 `205b87a3e056d8219f702272bb76b9b4`),
  `sam.cfg`, `msttssyn.dll`
  (MD5 `306131d8ed2cf34bac1a3dc938e75163`), `wttsm22.dll`.

The original installer, the extracted DLLs, and `sam.vce`/`sam.cfg` are **not**
redistributed in this repository. `inv.bin` is omitted as well.

## Published archive

`sam_voice_samples.zip` contains the 3365 unit waveforms produced by executing
the original `msttssyn.dll` rendering code. It is derived output from
Microsoft's voice database. Rights in the original voice recordings and data
remain with Microsoft; the archive is published for research, interoperability
and preservation purposes.

* zip SHA-256:
  `efc006eb2f8ec72d332a41826d91a0063ef501629c9f651215895cf6c5523c27`
* aggregate sample hash:
  `3c0cb515f17e79ee7a5b2401700314ef93d31521497a4275c3d849081a99b115`

## Session archive

`omp-session-archive.zip` is an omp session export produced with
[`omp-archive`](https://github.com/alosslessdev/omp-archive-main). Before
publication it was sanitized: the local username in paths, personal names, and
every email address were replaced with `user` / `[redacted-email]`. Command
lines, tool output, and the complete conversation are otherwise preserved. It
was also scanned for credential patterns (GitHub/OpenAI tokens, AWS keys,
private-key headers); none were found.

* zip SHA-256:
  `e3e326ab87d5426935840c9e17f2f59edcc6687cb5c040b18a2286d1ca56b09c`
