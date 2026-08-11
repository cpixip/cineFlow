# cineFlow — degraining small-gauge film scans

Grain removal for scanned Super 8, Double 8 and 16 mm film. It collects
detail across neighbouring frames rather than reconstructing it, so it
cannot show you anything that was not on the film.

The same machinery works on noisy video — in fact more easily, since
the higher frame rate provides more usable samples per frame. Film is
simply the harder case it was built for.

## What it does

Old small-gauge film is grainy, and in the darker parts of a frame the
grain is often stronger than the subject behind it.

Some programs solve this by rebuilding the picture: a model has learned
what skin, foliage and brickwork look like, and paints that over the
places where grain used to be. The result is impressively sharp, and it
shows things that were never on the film.

![flowQt with real data](images/19-flowQtInUse.png)

cineFlow takes the other route. A detail in a film almost never lives
in a single frame — the camera exposed the same corner of the house,
the same face, the same treetop two, five, twenty times. The grain fell
differently on every exposure; the corner of the house did not. Follow
a detail reliably across several frames, combine its signature from
several samplings, and you end up with something that *was* in the
film but was never cleanly visible in any one frame.

Every neighbouring frame is checked before it is used: is the motion
consistent, does the pixel still look like it belongs, does it disagree
with what the others agree on? Where the answers are bad, the neighbour
is discarded and the original frame stands. An area the software is
unsure about stays as grainy as it was. That is sometimes
unsatisfying — it is always honest.

## Who it is for

People who scan their own film and care whether what they end up with
is what was actually there. It assumes you can run a Python script and
are willing to look closely at your material; it does not assume you
know what optical flow is.

## The two programs

| | |
|---|---|
| **flowQt** | interactive front end. One frame at a time, sliders, a set of diagnostic views. This is where you work out the settings for a scene and save them as a recipe. |
| **cineFlow** | batch processor. No window, no sliders. Point it at a folder of scenes and it applies the recipes across all of them. |

Both use the same computation, so what you tune in flowQt is what the
batch produces.

## Getting started

- **[INSTALL.md](INSTALL.md)** — installation, from a machine with no
  Python on it to a first batch run. Tested end to end on Linux Mint
  and Windows.
- **[MANUAL.md](MANUAL.md)** — the manual. Chapter 2 gets you a
  degrained clip in five minutes without understanding anything;
  everything after that is about doing it well.

Short version: Python 3.11 or 3.12, then

```
pip install numpy opencv-python tifffile PyQt5
python flowQt.py
```

That runs everything, using the DIS optical-flow estimator. A CUDA GPU
plus PyTorch additionally enables RAFT, which is usually — but not
always — the better estimator. See INSTALL.md section 5.

Without a GPU, expect around 0.7 frames per second at 1800×1350: slow,
but fast enough to find out whether the software does anything for your
material.

## Status

Version 2.0. Working software that one person uses on his own film,
published in the hope that it is useful to others.

The manual is a first version and has gaps, all of them marked. Some
parts of the program — the dust removal modes in particular — work but
have had far less attention than the degraining itself.

**No support is promised.** Bug reports are welcome and will be read;
patches more so. Questions of the form "it does not run on my machine"
are best asked with the output of the startup banner attached, which
says what the program found and what it did not.

## Licence

GPL-3.0-or-later. See [LICENSE](LICENSE).

Commercial licences are available for use cases the GPL does not cover.
Enquiries: license@pixelcircus.com

Copyright (C) 2026 Dr. R. Henkel
