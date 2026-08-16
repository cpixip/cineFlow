# Installing cineFlow

cineFlow is simply a set of Python scripts. There is nothing to compile
and no installer — you get the dependencies in place, drop the scripts
in a folder, and run them.

The software was installed and tested end to end under Win11, WSL2
and Linux Mint.

Three steps should get you going:

+ get a working Python interpreter
+ install four packages
+ try it out

> **Note:** for fast batch processing the software uses PyTorch with
> CUDA, so if there is an NVIDIA card in the machine, you will want to
> install those as well (See section 6: RAFT — the optional GPU part).

---

## 1. Python interpreter

Python 3.11 or 3.12 are the safe choice. Newer versions tend to run
ahead of PyTorch — the wheels for them arrive late, and for a recent
graphics card you want the current ones — but that gap closes over
time, and 3.13 works here today. If the version you have is newer than
this document, try it; section 6 is where it would show.

If you run something more elaborate — a portable distribution, conda,
an IDE with its own interpreter — you know what you are doing and the
commands below will need adapting.

## 2. A virtual environment

Recommended everywhere, and on Linux effectively required: pip there
refuses to install into the system directories, with `error:
externally-managed-environment`. That is the distribution protecting
its own packages, and the answer is a virtual environment rather than
`--break-system-packages`.

**Linux and WSL2:**
```
python3 -m venv ~/cineflow-env
source ~/cineflow-env/bin/activate
```
**Windows:**
```
python -m venv %USERPROFILE%\cineflow-env
%USERPROFILE%\cineflow-env\Scripts\activate
```

The prompt now starts with `(cineflow-env)`, and inside this shell the
interpreter answers to plain `python` — so every command below works
as written on either system. **You need the activation line once per
terminal session**, and forgetting it is by some distance the most
common reason for "but I installed that already".

## 3. The four packages

Install everything cineFlow needs with a single command:
```
pip install numpy opencv-python tifffile PyQt5
```

On x86_64 all four arrive as prebuilt wheels — no compiler needed,
about 160 MB of download.

> **`opencv-python`, not `opencv-python-headless`.** The headless
> variant deliberately ships without a GUI, and flowQt will not open a
> window. If `pip list` shows both, remove both and reinstall the
> normal one:
>
> ```
> pip uninstall -y opencv-python-headless opencv-python
> pip install opencv-python
> ```

Without an NVIDIA card this is the whole installation, and section 6
("RAFT — the optional GPU part") does not apply — cineFlow will use
the DIS flow estimator throughout.

## 4. ffmpeg

ffmpeg is needed if you work with video files rather than TIFF
sequences. cineFlow uses both `ffmpeg` and `ffprobe`.

On Linux, `sudo apt install ffmpeg` brings both. On Windows, fetch a
build from <https://ffmpeg.org/download.html> and unpack it anywhere:
cineFlow looks in the usual places by itself, and only an unusual
location needs adding to `PATH`. Check with `ffmpeg -version` and
`ffprobe -version`.

## 5. Check that it runs

To test the installation, simply run

```
python cineFlow.py --help
```

If that prints the option list, all four modules import cleanly and
cineFlow is ready to run — over SSH too, it needs no window.

Now the same test for flowQt. Note that **flowQt does need a window**,
so start it at the machine's own console:

```
python flowQt.py
```

The banner tells you what the program found:

```
[RAFT] not available -- install PyTorch + torchvision
[RAFT]   ModuleNotFoundError("No module named 'torchvision'")
[flowQt] 2.0  --  Python 3.9.0, numpy 2.0.2, OpenCV 5.0.0
[flowQt] flow: DIS  (unavailable: RAFT)
```

That is what a correct installation looks like at this point: the four
packages are in, DIS is running, and RAFT is not there yet because
section 6 has not happened. Once it has, the last line reads
`flow: RAFT, DIS`.

Anything else on the flow line is a real problem; see section 8 for
troubleshooting.

---

## 6. RAFT — the optional GPU part

RAFT needs PyTorch with CUDA, and **which** CUDA version depends on
your graphics card. This is the part that goes wrong most often, so it
is worth being careful. Activate your virtual environment first —
installing PyTorch outside it is a reliable way into section 8.5.

### 6.1 Which wheels

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
  mismatch described in 8.3.
- **A very new card may need the preview channel.** If the newest CUDA
  version offered is older than what your GPU needs, take the preview
  (nightly) build instead — same page, `Preview (Nightly)` instead of
  `Stable`. This was the case for the RTX 50 series for a while; by
  the time you read this it may not be any more.

If you are unsure what your card needs, install the stable build
first. If RAFT then fails with a message about `sm_...` or `no kernel
image`, that is the answer: your card is newer than the build, and the
preview channel is the fix.

> **RAFT works within a fixed pixel budget**, and that budget was
> measured on a card with 8 GB. On a smaller one you may run out of
> memory even at a setting the program allows — then raise `downscale`
> further, or use DIS, which runs on the CPU at any size. With the
> driver's default policy you may not get an error at all, just a run
> that crawls — see 8.6. What the budget means for your scans is in
> 8.1.C of [MANUAL.md](MANUAL.md).

### 6.2 The weights

Unlike DIS, which computes optical flow from first principles, RAFT is
a neural network: it needs a trained set of weights before it can do
anything. cineFlow uses `raft_small` from torchvision, and you do not
have to fetch those weights yourself — torchvision downloads them on
first use and keeps them in its own cache. So the first RAFT run is
slower and needs an internet connection; every run after that is
local.

---

That is the installation done. From here on, chapter 2 of
[MANUAL.md](MANUAL.md) ("Simple examples") takes over: it walks
through a first scene in flowQt and gets you a degrained clip without
requiring you to understand what the sliders do.

---

## 7. If you run WSL2

Nothing about the installation changes — follow sections 1 to 5 as for
any Linux. Two things are specific to it:

**flowQt needs a GUI.** Under WSLg that works out of the box, but if
the window does not appear:

```
sudo apt install libxcb-cursor0 libxkbcommon-x11-0
```

**Keep both environments in step.** If you use WSL2 *and* native
Windows on the same machine, put the same torch and torchvision
versions in both. Recipes transfer between them; broken environments
do not.

---

## 8. When something goes wrong

### 8.1 `[RAFT] not available`

If the console says this, look at the line right below it: that is
where the actual exception appears, and it decides what to do. **Read
it** — the usual answers are quite different from each other, and only
one of them is about your graphics card:

| what the line says | what it means |
|---|---|
| `No module named 'torch'` | PyTorch is not in *this* Python. You are probably starting from a different interpreter than the one you installed into — or from outside your virtual environment. |
| `No module named 'torchvision'` | torch alone is not enough. RAFT lives in torchvision. Install both, in one command (6.1). |
| `cannot import name '_broadcast_to_and_flatten' ... circular import` | torch and torchvision do not match. See 8.3. |
| something about `sm_120` or `no kernel image` | your card is newer than this PyTorch build. Take the preview channel (6.1). |

### 8.2 `recipe says RAFT, running DIS`

Not an error. A recipe carries the flow method it was tuned with; if
that method is not available here, cineFlow says so and carries on
with DIS. The result is valid, it is just not the one the recipe
describes. On a machine without a GPU this is the normal state of
affairs.

### 8.3 torch and torchvision do not match

The symptom is the circular-import error above. The cure is to remove
both and reinstall them together:

```
pip uninstall -y torch torchvision torchaudio
pip uninstall -y torch torchvision torchaudio
pip install torch torchvision ...          # the command from 6.1
```

Run the uninstall **twice**. Overlaid nightly installations leave
remains that the first pass does not catch; when the second pass says
"not installed" for all three, it is clean.

### 8.4 No window appears

Two causes, in order of likelihood:

1. `opencv-python-headless` is installed. See the box in section 3.
2. Under WSL2, the X libraries are missing. See section 7.

On a normal Linux desktop this does not come up — the Qt libraries
arrive with the wheel, and the rest is already there.

### 8.5 Two Python installations

A recurring theme in all of the above. If flowQt says RAFT is missing
while you are sure you installed PyTorch, check that you installed
into the interpreter you are actually starting:

```
python -c "import sys; print(sys.executable)"
```

Compare with where your packages went. Editors and distributions that
bring their own Python are the usual reason for a mismatch — not
because they are wrong, but because it is easy to install in one shell
and start from another.

### 8.6 A run slows to a crawl

The symptom: a run that started at a sensible speed drops to a
fraction of it after a few hundred frames. No error, the frame
counter keeps advancing, the ETA climbs into the hours. Task Manager
shows the GPU near 100 % with its memory nearly full, and a non-zero
figure under *shared GPU memory*.

That last number is the diagnosis. Since driver release 536 the
NVIDIA driver no longer fails when CUDA runs out of video memory: it
moves the allocation into system RAM instead. The run carries on over
the PCIe bus — correct results, two to three orders of magnitude
slower.

Make it fail properly. In the NVIDIA control panel (or the NVIDIA
app), under the 3D settings, set **CUDA — Sysmem Fallback Policy** to
**Prefer No Sysmem Fallback**. A run that then exceeds the card stops
within seconds with a CUDA out-of-memory error and says how much it
asked for. The setting is global; if that gets in the way of other
CUDA software, set it for `python.exe` alone under the per-program
tab.

Then give it less to hold: raise `downscale`, or lower `context`.
`downscale` is the stronger lever, since cost grows quadratically.
DIS is unaffected — it runs on the CPU.

---

## 9. What gets written where

cineFlow is deliberately quiet about your disk. It writes:

- `flowQt_settings.json` — your view cycle and slots, next to the
  scripts.
- `cineflow.json` — the recipe, next to your material, and only when
  you press **Save recipe**. Beside a video file it is called
  `<name>_cineflow.json` instead.
- whatever you record with **REC**, in a `_clips` folder next to your
  material.
- whatever you capture with `p`, as a PNG in a `_snapshots` folder
  next to your material.
- the output of a batch run, in the output folder you name on the
  command line, together with a `cineflow_run.json` recording the
  numbers that produced it.

Your original material is never touched.
