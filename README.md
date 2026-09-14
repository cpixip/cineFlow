# cineFlow — Restoring Small-Gauge Film

![flowQt with real data](images/19-flowQtInUse.png)

*flowQt — the interactive front end, working out the settings for a scene.*

This software development started with a specific challenge: in 1981, about 20 rolls of Kodachrome 40
film stock were exposed. They were stored in an attic for over a year before they were finally
developed.

While Kodachrome 40 was one of the best film stocks one
could choose at that time, the long delay between exposure
and development created a unique film look with increased film grain. In fact, in darker parts of the image, grain overwhelms the image content completely, to the point where the footage becomes unwatchable.

This software, cineFlow, was developed in an effort to reconstruct as much as possible of the *original* image information.

Classical approaches to that task use noise profiles or grain
statistics. Newer, neural network-based approaches use good guesses ("Oh, that looks like hair, let's simulate it"). In cineFlow, no neural network is used to invent image content.

Instead of hunting the noise, cineFlow hunts the scene information directly. Follow a detail of a scene reliably across several frames, combine its signature from several samplings, and you end up with something that *was* in
the film but was never cleanly visible in any one frame.

cineFlow uses optical flow algorithms to track image features across several frames. Basically, for any given
scene, a spatio-temporal data set is created, which describes the scene. This data set is fed into the next stage of the algorithm, where a trust mechanism checks
the computed data for consistency and assigns a trust value
to each element of the data set.

That is where most of the work sits. Combining the frames
afterwards is mostly a weighted average and little else — it can stay simple because the trust values already carry the decision. Grain disappears because it has no
counterpart in neighbouring frames, not because the
program went looking for it. A final enhancement stage uses this intermediate image together with trust and texture values to create the
final output image.

That is also the reason why cineFlow works on a wide
variety of input material. Among others, it has been
tested on:

+ RAW 12 bit scans
+ HDR scans
+ Agfa/Kodak/Fuji and other reversal film scans
+ Negative film scans (Orwo 54 developed in Rodinal)

## The two programs

Restoration alternates between two very different activities: working
out the right settings for a scene, and applying them to a few thousand
frames. These are kept apart.

| | |
|---|---|
| **flowQt.py** | interactive front end. One frame at a time, sliders, a set of diagnostic views. This is where you work out the settings for a scene and save them as a recipe. |
| **cineFlow.py** | batch processor. No window, no sliders. Point it at a folder of scenes and it applies the recipes across all of them. |

Both use the same computation, so what you tune in flowQt is what the batch produces.

The standard exchange format is a directory of 16 bit TIFF files, but the software package can also operate on normal video files, writing FFV1, ProRes 4444 and 4444 XQ, or H.264.

Also in this repository: **compareQt.py**, a small viewer for putting two
versions of the same scene side by side — split, side by side, or with the
amplified difference — and rendering the comparison to a video. Undocumented
beyond its tooltips; there is not much to it.

## Getting started

- **[INSTALL.md](INSTALL.md)** — installation, from a machine with no
  Python on it to a first batch run.
- **[MANUAL.md](MANUAL.md)** — the manual.
  Chapter 2 gets you a degrained clip in five minutes without
  understanding anything; everything after that is about doing it well.

You need Python 3.11 or newer and four packages; INSTALL.md has the
details. Everything runs on the CPU; a CUDA GPU is optional and makes
it a great deal faster.

## Status

This is version 2.0 of the software: working software that one person uses on his own films, published in the hope that it is useful to others.

Some parts of the program — the dust removal modes in particular —
work but have had far less attention than the degraining itself.

**No support is promised.** Bug reports are welcome and will be read.
Questions of the form "it does not run on my machine" are best asked
with the console output of the failed run attached — the banner the
program prints on startup says what it found and what it did not.

## Licence

GPL-3.0-or-later. See [LICENSE](LICENSE).

Commercial licences are available for use cases the GPL does not cover.
Enquiries: license@pixelcircus.com

Copyright (C) 2026 Dr. R. Henkel
