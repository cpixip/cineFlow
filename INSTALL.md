# Installing cineFlow

cineFlow is a set of Python scripts. There is nothing to compile and no
installer — you get the dependencies in place, drop the scripts in a
folder, and run them.

There are two levels, and the first one is enough to see whether the
software does anything for your material:

| | what runs | what you need |
|---|---|---|
| **Basic** | everything, with the DIS flow estimator | Python, four packages |
| **Full** | additionally the RAFT flow estimator | a CUDA GPU and PyTorch |

Start with Basic. RAFT is usually the better estimator, but it is not
always the better choice (5.8), and nothing in the program depends on
it: if RAFT is missing, DIS steps in and says so.

---

## 1. Python

**Use Python 3.11 or 3.12.**

3.13 works for the Basic level, but at the time of writing PyTorch
wheels for 3.13 lag behind — and for newer GPUs you need the very
latest ones. If you intend to use RAFT, 3.11 or 3.12 will save you an
afternoon.

Check what you have:

```
python3 --version
```

> **On Linux, use `python3`.** Modern Debian, Ubuntu and Mint do not
> provide the plain name `python` at all, and `python --version`
> answers `Command 'python' not found`. That does **not** mean Python
> is missing — it almost certainly is not, the system depends on it.
> Only the short name is absent. Section 2.1 takes care of it.

## 2. The four packages

### 2.1 A virtual environment (Linux, and a good idea everywhere)

On Debian-based systems pip refuses to install into the system
directories — `error: externally-managed-environment`. That is
deliberate: the distribution protects its own packages. The answer is
a virtual environment, not `--break-system-packages`.

```
sudo apt install python3-venv python3-pip
python3 -m venv ~/cineflow-env
source ~/cineflow-env/bin/activate
```

On Mint 22.1 the first line found both packages already installed; it
does no harm either way.

The prompt now starts with `(cineflow-env)`, and inside this shell the
interpreter answers to `python` again — so every command below works
as written. You need the `source` line once per terminal session.

### 2.2 The packages

```
pip install numpy opencv-python tifffile PyQt5
```

That is the Basic level, complete. On x86_64 all four arrive as
prebuilt wheels — no compiler needed, about 160 MB of download.

Verified working with numpy 2.5, OpenCV 5.0, tifffile 2026.7 and
PyQt5 5.15. OpenCV 5 is a major version step, but every call cineFlow
makes still behaves as before.

> **`opencv-python`, not `opencv-python-headless`.** The headless
> variant deliberately ships without a GUI, and flowQt will not open a
> window. If `pip list` shows both, remove both and reinstall the
> normal one:
>
> ```
> pip uninstall -y opencv-python-headless opencv-python
> pip install opencv-python
> ```

`PyQt5` is only needed for flowQt, the interactive front end. The
batch program cineFlow runs without it.

> **On Linux without a GPU** this is the whole installation. Section 5
> does not apply, and the banner in section 4 will say
> `flow: DIS  (unavailable: RAFT)` — which is correct and not a
> problem. Both programs were tested this way on Linux Mint 22.1: the
> window opens, DIS runs, no further packages needed.

## 3. ffmpeg (for video input and output)

Needed if you work with video files rather than TIFF sequences.
cineFlow uses both `ffmpeg` and `ffprobe`; the packages below contain
both.

**Linux:**

```
sudo apt install ffmpeg
```

**Windows:** fetch a build from <https://ffmpeg.org/download.html> and
unpack it anywhere. cineFlow does *not* require it on your `PATH` — it
looks in the usual places by itself, including `C:\ffmpeg`, the
Program Files folders and WinGet's link directory. Only if you put it
somewhere unusual do you need to add that folder to `PATH`.

Either way, check with:

```
ffmpeg -version | head -1
ffprobe -version | head -1
```

## 4. Check that it runs

The batch program loads everything without computing anything:

```
python cineFlow.py --help
```

If that prints the option list, all four modules import cleanly. This
works over SSH — cineFlow needs no window.

**flowQt does need a window**, so start it at the machine's own
console, not through a plain SSH session:

```
python flowQt.py
```

The banner tells you what you have:

```
[flowQt] 2.0  --  Python 3.12.3, numpy 2.5.2, OpenCV 5.0.0
[flowQt] flow: RAFT, DIS
[flowQt] settings: .../flowQt_settings.json
```

If the second line says `flow: DIS  (unavailable: RAFT)`, the Basic
level is working and RAFT is not installed — see section 5. Anything
else on that line is a real problem; see section 6.

### 4.1 A first run

Point cineFlow at a folder of scenes and give it somewhere to write:

```
python cineFlow.py ../Public/ ../Out
```

A successful run looks like this — a real one, from a machine with no
GPU at all:

```
====================================================================
  CINEFLOW v2.0
  input:   ../Public/
  output:  ../Out
  run:     2026-08-11_2000/
====================================================================
[scenes] 4 scene(s) found
[space] estimated need: 18.99 GiB | free on ../Out: 126.67 GiB
  10_AnnaOma: 794 Frames, ~10.89 GiB
  ...
[1/4] 10_AnnaOma  (tiff_dir)
  [config] ERROR: unknown keys ['flow_scale', 'blend_radius', ...]
           -- scene skipped
  [config]   an old recipe? v2 renamed several keys -- re-export it
             from flowQt.
[3/4] 21_diffuse_Canyon  (tiff_dir)
  [config] no cineflow.json -- using defaults (best, RAFT, context=+-1)
[RAFT] not available -- install PyTorch + torchvision
  [best] 144 frames, 1800x1350 (TIFF) | CPU path, flow=DIS, context=+-1
  [best] NOTE: recipe says RAFT, running DIS -- the result differs
         from the recipe.
  [best]   6.9% | Frame 10/144 | 0.64 fps | ETA: 0:03:30
```

Four things worth reading in that:

- **Scenes are found by themselves.** Every video file, or every
  sub-folder of TIFFs, is one scene.
- **Disk space is estimated before anything runs**, per scene. If it
  does not fit, you are asked before the first frame is written.
- **A scene with an unusable recipe is skipped, loudly.** It is not
  quietly computed with defaults you never chose, and the message says
  what to do about it.
- **The fallback to DIS is stated, not hidden.** The recipe asked for
  RAFT, RAFT is not here; the result is valid but is not the one the
  recipe describes.

At the end you get a summary:

```
==============================================================================
  CINEFLOW v2.0  --  2 scene(s) in 0:05:38, 2 skipped
==============================================================================
  scene              mode   downscale context  frames    fps  output
------------------------------------------------------------------------------
  21_diffuse_Canyon  best        2.00     +-1     144   0.74  21_diffuse_Canyon
  22_Dark_..._Valley best        2.00     +-1     108   0.76  22_Dark_..._Valley
  10_AnnaOma         -                                        (skipped)
  18_Airplane        -                                        (skipped)
------------------------------------------------------------------------------
```

**About the speed.** 0.74 fps is what DIS manages on 1800×1350 on a
CPU — roughly 20 minutes for an 800-frame scene. Slow, but fast enough
to find out whether the software does anything for your material. With
RAFT on a GPU you are in a different league.

Alongside the frames, each output folder gets a `cineflow_run.json`
recording the numbers used, how long it took and which version did the
work.

---

## 5. RAFT — the optional GPU part

RAFT needs PyTorch with CUDA, and **which** CUDA version depends on
your graphics card. This is the part that goes wrong most often, so it
is worth being careful.

### 5.1 Which wheels

Do not copy a `pip install` line out of a manual for this — CUDA
versions and channels move, and a wrong one wastes an evening. PyTorch
has a configurator on its front page: pick your operating system,
package manager and CUDA version, and it prints the command that is
current today.

    https://pytorch.org/get-started/locally/

Two things that configurator does not tell you, and both matter:

- **Install torch and torchvision in one command.** Not one after the
  other. Only then does pip pick versions that fit each other, and
  installing them separately is the single most common way into the
  mismatch described in 6.3.
- **A very new card may need the preview channel.** If the newest CUDA
  version offered is older than what your GPU needs, take the preview
  (nightly) build instead — same page, `Preview (Nightly)` instead of
  `Stable`. This was the case for the RTX 50 series for a while; by
  the time you read this it may not be any more.

If you are unsure what your card needs, install the stable build
first. If RAFT then fails with a message about `sm_...` or `no kernel
image`, that is the answer: your card is newer than the build, and the
preview channel is the fix.

### 5.2 The weights

You do not have to fetch anything. cineFlow uses `raft_small` from
torchvision, and torchvision downloads the weights by itself on first
use, into its own cache. The first RAFT run is therefore slower and
needs an internet connection; after that it is local.

### 5.3 WSL2

If you run RAFT under WSL2 rather than native Windows, note that
flowQt needs a GUI. Under WSLg that works, but if the window does not
appear:

```
sudo apt install libxcb-cursor0 libxkbcommon-x11-0
```

Keep the WSL environment and the Windows environment on the **same**
torch and torchvision versions if you use both. Recipes transfer
between them; broken environments do not.

---

## 6. When something goes wrong

### 6.1 `[RAFT] not available`

A second line follows with the actual exception. **Read it** — the
usual answers are quite different from each other, and only one of
them is about your graphics card:

| what the line says | what it means |
|---|---|
| `No module named 'torch'` | PyTorch is not in *this* Python. You are probably starting from a different interpreter than the one you installed into — or from outside your virtual environment. |
| `No module named 'torchvision'` | torch alone is not enough. RAFT lives in torchvision. Install both, in one command (5.1). |
| `cannot import name '_broadcast_to_and_flatten' ... circular import` | torch and torchvision do not match. See 6.3. |
| something about `sm_120` or `no kernel image` | your card is newer than this PyTorch build. You need the CUDA 12.8 wheels from 5.1. |

### 6.2 `recipe says RAFT, running DIS`

Not an error. A recipe carries the flow method it was tuned with; if
that method is not available here, cineFlow says so and carries on
with DIS:

```
[best] NOTE: recipe says RAFT, running DIS (probe failed: ...)
       -- the result differs from the recipe.
```

The result is valid, it is just not the one the recipe describes. On a
machine without a GPU this is the normal state of affairs.

### 6.3 torch and torchvision do not match

The symptom is the circular-import error above. The cure is to remove
both and reinstall them together:

```
pip uninstall -y torch torchvision torchaudio
pip uninstall -y torch torchvision torchaudio
pip install torch torchvision ...          # the command from 5.1
```

Run the uninstall **twice**. Overlaid nightly installations leave
remains that the first pass does not catch; when the second pass says
"not installed" for all three, it is clean.

### 6.4 No window appears

Two causes, in order of likelihood:

1. `opencv-python-headless` is installed. See the box in section 2.2.
2. Under WSL2, the X libraries are missing. See 5.3.

On a normal Linux desktop this does not come up — the Qt libraries
arrive with the wheel, and the rest is already there. Tested on Linux
Mint 22.1 with nothing but the four packages from 2.2.

### 6.5 `Could not load the Qt platform plugin "xcb" ... even though it was found`

This one is worth knowing about even though the program handles it:
`opencv-python` ships its own private copy of Qt, and if it is
imported before PyQt5, Qt finds a plugin built against the wrong
library. flowQt therefore imports PyQt5 first, deliberately.

If you see this message anyway, something in your environment is
importing cv2 before flowQt does — a sitecustomize file, an IDE, a
wrapper script. Start flowQt directly from a plain shell to find out.

### 6.6 Two Python installations

A recurring theme in all of the above. If flowQt says RAFT is missing
while you are sure you installed PyTorch, check that you installed
into the interpreter you are actually starting:

```
python -c "import sys; print(sys.executable)"
```

Compare with where your packages went. IDEs with their own bundled
Python (Thonny, for instance) are the usual reason for a mismatch.

---

## 7. What gets written where

cineFlow is deliberately quiet about your disk. It writes:

- `flowQt_settings.json` — your view cycle and slots, next to the
  scripts.
- `cineflow.json` — the recipe, next to your material, and only when
  you press **Save recipe**.
- whatever you record with **REC**, in a `_clips` folder next to your
  material.
- the output of a batch run, in the output folder you name on the
  command line.

Your original material is never touched.
