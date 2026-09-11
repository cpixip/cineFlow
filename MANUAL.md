# cineFlow — Manual
## Contents


- [cineFlow — Manual](#cineflow--manual)
  - [Contents](#contents)
- [1. What is it?](#1-what-is-it)
- [2. Simple Examples](#2-simple-examples)
  - [2.1 Degrained footage in less than 5 minutes](#21-degrained-footage-in-less-than-5-minutes)
    - [2.1.A Start flowQt](#21a-start-flowqt)
    - [2.1.B Load some material](#21b-load-some-material)
    - [2.1.C Switch to the Output view](#21c-switch-to-the-output-view)
    - [2.1.D Writing out the degrained result](#21d-writing-out-the-degrained-result)
  - [2.2 One slider to rule them all](#22-one-slider-to-rule-them-all)
    - [2.2.A Set amount to 0](#22a-set-amount-to-0)
    - [2.2.B Set amount to maximum](#22b-set-amount-to-maximum)
    - [2.2.C Set amount right](#22c-set-amount-right)
    - [2.2.D Saving the recipe](#22d-saving-the-recipe)
  - [2.3 From one scene to a hundred](#23-from-one-scene-to-a-hundred)
    - [2.3.A What goes in, what comes out](#23a-what-goes-in-what-comes-out)
    - [2.3.B What a run looks like](#23b-what-a-run-looks-like)
    - [2.3.C Where the recipe comes from](#23c-where-the-recipe-comes-from)
      - [The arrangement that saves you the most work](#the-arrangement-that-saves-you-the-most-work)
    - [2.3.D The output codec](#23d-the-output-codec)
    - [2.3.E Forcing the format](#23e-forcing-the-format)
    - [2.3.F What else you get](#23f-what-else-you-get)
  - [2.4 The full quality, finally](#24-the-full-quality-finally)
    - [2.4.A How it goes](#24a-how-it-goes)
    - [2.4.B How large should the scan be?](#24b-how-large-should-the-scan-be)
- [3. Principle of operation](#3-principle-of-operation)
  - [3.1 Basic Concept](#31-basic-concept)
  - [3.2 The four steps](#32-the-four-steps)
- [4. Getting around](#4-getting-around)
  - [4.1 Moving through the film](#41-moving-through-the-film)
  - [4.2 Moving between views](#42-moving-between-views)
  - [4.3 Zoom and pan](#43-zoom-and-pan)
  - [4.4 Flipping](#44-flipping)
  - [4.5 Split-View Mode](#45-split-view-mode)
- [5. Best Practices](#5-best-practices)
  - [5.1 Don't process a full reel](#51-dont-process-a-full-reel)
  - [5.2 Pick the right frame](#52-pick-the-right-frame)
  - [5.3 Get the flow right first](#53-get-the-flow-right-first)
  - [5.4 How many neighbours are worth having](#54-how-many-neighbours-are-worth-having)
  - [5.5 Then adjust the trusts](#55-then-adjust-the-trusts)
  - [5.6 Enhance last](#56-enhance-last)
  - [5.7 Always render a short test](#57-always-render-a-short-test)
  - [5.8 Save the recipe, then let the batch run](#58-save-the-recipe-then-let-the-batch-run)
  - [5.9 How to be wrong](#59-how-to-be-wrong)
- [6. The views in detail](#6-the-views-in-detail)
  - [6.1 Input](#61-input)
  - [6.2 Output](#62-output)
  - [6.3 Neighbour (warped)](#63-neighbour-warped)
  - [6.4 Neighbour × trust](#64-neighbour--trust)
  - [6.5 Trust geo · Trust photo](#65-trust-geo--trust-photo)
  - [6.6 Trust](#66-trust)
  - [6.7 Sharp gate](#67-sharp-gate)
  - [6.8 Flow fw · Warped flow bw · relative variants](#68-flow-fw--warped-flow-bw--relative-variants)
  - [6.9 Texture weight](#69-texture-weight)
- [7. How the Enhance stage decides](#7-how-the-enhance-stage-decides)
  - [7.1 What is measured](#71-what-is-measured)
  - [7.2 The histogram](#72-the-histogram)
  - [7.3 The curve](#73-the-curve)
  - [7.4 What it costs to get it wrong](#74-what-it-costs-to-get-it-wrong)
- [8. The settings in detail](#8-the-settings-in-detail)
  - [8.1 Engine](#81-engine)
    - [8.1.A `flow` — RAFT / DIS](#81a-flow--raft--dis)
    - [8.1.B `mode` — best / dustA / dustB](#81b-mode--best--dusta--dustb)
    - [8.1.C `downscale`](#81c-downscale)
    - [8.1.D `context`](#81d-context)
  - [8.2 Trust](#82-trust)
    - [8.2.A geo tab — `mismatch` \[px\] · `softness`](#82a-geo-tab--mismatch-px--softness)
    - [8.2.B photo tab — `mismatch` \[0..1\] · `softness` · `smooth` \[px\]](#82b-photo-tab--mismatch-01--softness--smooth-px)
    - [8.2.C dustA tab — `mismatch` \[MAD\] · `softness` · `center_weight`](#82c-dusta-tab--mismatch-mad--softness--center_weight)
    - [8.2.D dustB tab — `mismatch` \[spread\] · `softness` · `disagreement` \[0..1\] · `softness` \[0..1\]](#82d-dustb-tab--mismatch-spread--softness--disagreement-01--softness-01)
  - [8.3 Enhance](#83-enhance)
    - [8.3.A `amount`](#83a-amount)
    - [8.3.B texture tab — `full` · `gamma` · `base`](#83b-texture-tab--full--gamma--base)
    - [8.3.C filter tab — guided / gauss · `sigma` · `eps`](#83c-filter-tab--guided--gauss--sigma--eps)
  - [8.4 Slots](#84-slots)
  - [8.5 Autoplay and Record](#85-autoplay-and-record)
    - [8.5.A Step, play / pause](#85a-step-play--pause)
    - [8.5.B REC — mp4 / tif](#85b-rec--mp4--tif)
- [9. Export from your NLE](#9-export-from-your-nle)
  - [9.1 Image sequences — the full-quality route](#91-image-sequences--the-full-quality-route)
  - [9.2 Video clips — the quick route](#92-video-clips--the-quick-route)
  - [9.3 Coming back](#93-coming-back)
- [10. Dust and scratches](#10-dust-and-scratches)
- [Appendix — Keyboard reference](#appendix--keyboard-reference)
  - [A.1 Navigation](#a1-navigation)
  - [A.2 View](#a2-view)
  - [A.3 Autoplay and recording](#a3-autoplay-and-recording)
  - [A.4 Parameters and files](#a4-parameters-and-files)

---

# 1. What is it?

cineFlow removes grain and noise from digitised small-gauge film. The README says where it came from and how it works; this manual is about operating it.

Old small-gauge film was always grainy — sometimes so grainy that in the darker parts of the image real image content was hard to see. Projected onto a screen in a darkened room this worked out well enough — the human visual system is quite capable of seeing through the grain in this situation. Digitised media is however watched under different conditions: normally in a brightly lit office environment, on a normal computer display. It is much harder here to "see through the noise", and that is the gap this software is trying to close.

The manual has several chapters. Chapter 2 gets you a result without explaining anything. Chapter 3 explains what happens in between, and chapter 5 is the order in which to touch the settings. Chapter 7 describes the enhance stage in detail. The rest is reference: getting around flowQt in 4, its views in 6 and its settings in 8, exporting from and back into an NLE in 9.

---

# 2. Simple Examples

In the following, four different ways of using the cineFlow package are
described, each building on the last. We start with a simple example and finish with scene-specific processing of TIFF directories via fast batch-rendering.

## 2.1 Degrained footage in less than 5 minutes

The goal here is produce a degrained video without adjusting or understanding anything.

### 2.1.A Start flowQt

For this, flowQt is the right choice. It is the interactive front end of the software suite. Start it
by

```
python flowQt.py
```

The program window should show up, after a while (startup takes some time):

![The flowQt interface after start-up](images/01-startup.png)

On the right you will see a wall of sliders. Ignore them. We will not
touch a single one in this section.

### 2.1.B Load some material

In order to load some material, simply drag a video file onto the large area.

That is the entire loading procedure. If your material sits as .tif frames in a single folder, drop that folder instead — flowQt accepts both.

> **Note:** If you started flowQt under WSL2, a drag and drop of Windows folders is not possible; the **Load Tif** and **Load Video** buttons do the same job.

![Opening via Drag-and_Drop](images/02-DragDrop.png)

flowQt reads the file and shows you the first frame of the video.

### 2.1.C Switch to the Output view

Press key **2**. The Status box on the right reports that something is
being computed, and the view switches to *2. Output (best)*. Give it a
few seconds — this is the real computation, not a preview.

![The Output View](images/12-viewdisplay.png)

When the computed frame appears, have a look at it. Than press **cursor up**: you are back at the input image. **Cursor down** returns you to the output.

Go back and forth a few times; that comparison is what flowQt is for.

> **If you get lost in the views:** Key **1** always takes you to the
> input image, Key **2** always to the output. Whatever else is on screen,
> those two keys bring you back.

### 2.1.D Writing out the degrained result

Now it's time to write out a processed video file.

At the bottom right there is a box labelled **Autoplay | Record**.

![Preparing mp4-output](images/05-RecordMP4.png)


1. Go to the first frame of your footage (by pressing **Home**).
2. Make sure you are on the *2. Output (best)* view and that the split-view option is off — it is off when there is no vertical yellow line visibl. Press the **l**-key until the line disappears.
3. Set the selector next to REC to **mp4**.
4. Press **REC**. The button turns red: recording is armed and
   running.
5. Press the **space bar**.

flowQt now runs from the start to the end of the scene, computes every
frame and writes it to the video. When it reaches the end it stops on
its own and closes the file.

You will find the processed video next to your material, in a folder called `_clips`.

![the _clips-folder](images/06-_clipsFolder.png)

That is all. You now have a restored video, and you configured nothing.

---

## 2.2 One slider to rule them all

Now we adjust something. Exactly one thing.

In the **Enhance** box, at the top, there is a slider called
`amount`. This slider scales the effect of the whole Enhance stage.

![the Enhance Box](images/07-enhanceBox.png)

Stay on the `Output` view (Key **2**) and work through the steps below in order.

### 2.2.A Set amount to 0

Drag the amount slider all the way to the left, until the field
next to it reads 0. The sliders below it grey out: the last stage of
the processing is switched off, and what you see is the degrained
image before any sharpening.

### 2.2.B Set amount to maximum

Now pull the slider all the way to the right. The full force of the
Enhance stage is now acting on the image.

On most material this looks brutal — hard halos around every strong
edge. That is the point of looking at it: you have now seen both ends
of the range.

### 2.2.C Set amount right

Find the slider position where it looks right to you. For reference,
use Up and Down to switch between original (`Input`) and result (`Output`).

There is no correct value here, and the program will not find one for
you. Somebody who cannot stand halos will settle lower and accept a
softer overall image; somebody who wants a crisp result will accept a
little haloing around the strongest edges. Both are defensible, and
the same film may want different answers in different scenes.

What you just did is the real work with this software. But it is only
the beginning.

> **Nothing you can break.** Double-clicking any slider resets that slider
> to its default, and the **Default** button next to the slot buttons
> restores the factory settings altogether. Turn every knob you like;
> there is always a way back.


![The great Default button](images/S_005_2026.08.12.png)

### 2.2.D Saving the recipe

Look at the Save recipe button. It is highlighted whenever the
settings on screen are not the ones stored for this scene — either
because you changed something, or because this scene has no recipe
file at all yet. Hovering over it says which of the two it is.

![the Save Recipe button](images/08_SaveRecipe.png)

Now press it.

The moment you do this, flowQt writes a small text file: `cineflow.json` inside a scene folder, or, in case of a video file, a `<name>_cineflow.json` beside the video file.

This file contains the complete recipe the current result was computed
with. Once it is saved, the button returns to its normal colour.

The recipe file is more than a souvenir. It is the bridge to the next
section: **this is precisely the file the batch program `cineFlow.py`reads.** What you tuned by hand here, it will apply across a hundred scenes without you touching a slider again.

*(And if it is in your way, delete it. Everything then falls back to
the defaults.)*

---

## 2.3 From one scene to a hundred

flowQt is built for looking and adjusting. It computes each frame at
the moment you ask for it. That is right while you are tuning, and
useless once the settings are found.

That is where the second program comes in. **cineFlow** has no window
and no sliders: only throughput. It computes the same stages as
flowQt, scene after scene, applying whichever recipe covers each one.

### 2.3.A What goes in, what comes out

A call to cineFlow typically looks like this:
```
python cineFlow.py /path/to/scenes /path/to/output
```

That is the whole command. cineFlow is pointed at a folder, not at a
single scene, and everything it finds inside becomes one scene: a sub-folder full of TIFFs, a sub-folder full of video files, or a video file lying in the folder itself:

```
scans/
├── Szene_1/              ← a folder of TIFFs: one scene
│   ├── Frame_00000001.tif
│   ├── Frame_00000002.tif
│   └── ...
├── Szene_2/              ← another folder of TIFFs: a new scene
│   └── ...
├── Rolle_3/              ← a folder of videos: one scene per file
│   ├── clip_001.mp4
│   └── clip_002.mp4
└── USA_1981.mp4          ← a video file: one scene
```

The output folder works differently. cineFlow does not write into it
directly; it creates a sub-folder named after the moment the run
started, and everything from that run goes in there. Start a second
run and you get a second folder — nothing is ever overwritten.

```
out/
└── 2026-08-09_1835/
    ├── Szene_1/
    │   ├── Szene_1_000001.tiff
    │   └── ...
    ├── Szene_2/
    │   └── ...
    ├── Rolle_3/
    │   ├── clip_001.mkv
    │   └── clip_002.mkv
    └── USA_1981.mkv
```

Each scene comes back in the shape it went in: a folder of TIFFs stays
a folder of TIFFs, a video file stays a video file. The frame numbers
continue the numbering of the source, so a scene that started at frame
72 still starts at frame 72. Video output is written as FFV1 in an
`.mkv` — lossless, and read by DaVinci from version 19 on. Older
versions need `--video-codec prores4444` as command-line argument (2.3.D).

### 2.3.B What a run looks like

Once cineFlow has been started, it will become quite chatty on the command line. It will

1) scan the input directory, identify the scenes in it, and estimate how much output they will produce
2) ask whether to continue if the space on the output device looks tight — in a script nobody can answer that, and an unanswered question counts as no, so pass `--yes` as command-line flag there
3) work through the scenes one by one, reporting for each what it is doing, the frames per second it achieves and the time remaining — including which recipe it used, or nothing at all when the scene brought its own; where recipes come from is described in the next section
4) finish with a short summary table of what was done.

### 2.3.C Where the recipe comes from

Most of a reel wants the same treatment, and a few scenes do not. cineFlow is built around that: you set the general case once and deviate where you have to. A recipe can cover a whole run, a folder of scenes, or a single scene — and the more specific one wins.

The four levels, each overriding the previous one:

1. **Nothing at all** — the built-in defaults are used, and cineFlow
   says so:
   `[config] no cineflow.json -- using defaults (best, RAFT, context=+-2)`
2. **A `cineflow_folder.json` in the input folder** — applies to every
   scene in the run. This is the convenient route when most of your
   material should get the same treatment. cineFlow announces it in
   the header: `config:  cineflow_folder.json (applies to every scene)`
3. **A file named with `--config`** — the same thing, but taken from
   anywhere on disk and chosen per run rather than per folder. The
   route for a treatment you want to try across several folders
   without leaving a file in any of them.
4. **The scene's own recipe** — the file flowQt wrote in 2.2.D. Beside
   a folder of TIFFs it is `<scene>/cineflow.json`, beside a video
   file `<scene>_cineflow.json`. It overrides everything else, and
   cineFlow says nothing about it: silence means the scene has its own
   recipe.


#### The arrangement that saves you the most work

A reel usually consists of many scenes that were shot under similar
conditions and a handful that were not. That maps directly onto the
two files types ( one `cineflow_folder.json` and maybe several `cineflow.json`).

Tune one representative scene in flowQt — a normal one, nothing
special. Then **right-click** the **Save recipe** button. In the
dialog that opens, navigate up to your input folder, change the file
name to `cineflow_folder.json`, and save there.

```
scans/
├── cineflow_folder.json     ← the general treatment
├── Szene_1/
├── Szene_2/
├── Szene_3/
│   └── cineflow.json        ← this one needed different settings
├── Szene_4/
└── ...
```

Now every scene is processed with the general recipe contained in
`cineflow_folder.json`, except Szene_3, which brings its own —  saved there with a plain left-click on **Save recipe**,
as in 2.2.D. Twenty scenes, two files, one batch run.

One thing to know about this: flowQt writes always a complete recipe, every parameter that matters for the current mode, not just the ones you
changed. So a scene file does not inherit the folder settings and
adjust a few of them; it replaces them. If you tune a scene in flowQt,
tune it as a whole.

### 2.3.D The output codec

Video output is written as **FFV1** in a Matroska container (`.mkv`).
FFV1 is lossless: what comes back is bit-identical to what the
pipeline computed, with nothing spent on compression artefacts.
DaVinci reads it from version 19 on.

Older DaVinci versions do not, and for those there is ProRes 4444:

```
python cineFlow.py /path/to/scenes /path/to/output --video-codec prores4444
```

It costs 10 bit instead of 16 and a conversion to YUV — little enough
to keep working with, but not nothing. In exchange the files are about
four times smaller: 1.9 against 7.5 MB per frame at 1800 × 1350.
`prores4444xq` is the higher tier of the same format, larger again.
Both land in a `.mov`.

The fourth option, `h264`, is the only genuinely lossy one: 8 bit,
4:2:0, expect slight colour shifts. Take it for a quick look or for
sending someone a clip, not for anything that goes back into the edit.
It writes an `.mp4`.

### 2.3.E Forcing the format

Normally the output format follows the input, and that is almost
always what you want (2.3.A). The `--output-format` flag overrides it in both directions: `video` turns a folder of TIFFs into a video file, `tiff`
unpacks a video into a numbered sequence.

A TIFF folder has no frame rate to read, so writing video from one
uses `tiff_fps` from the config — 18 by default, the silent Super-8
norm. Set it if your material ran at something else.

### 2.3.F What else you get

Alongside the output, cineFlow leaves a run log: `cineflow_run.json` inside a scene folder, `<name>_cineflow_run.json` beside a video
file — the same rule as for the recipe. It records the numbers used,
how long it took, and which version did the work.

When you come across a result six months from now and cannot remember
how it was made, the answer is sitting next to it.

And it is not only a note to yourself. Drag the `cineflow_run.json`
onto the flowQt window and the settings of that run are back —
flowQt recognises the log and says in the status line which run it
came from. The same works for any recipe file.

---


## 2.4 The full quality, finally

So far it did not matter much which of the two you brought: a folder
of TIFFs or a video file, cineFlow takes both. For serious work it
does matter, and the video route is the wrong one.

Every video file is compressed. The codec decides what it considers
unimportant and throws it away — and what it considers unimportant is
fine, irregular structure. Which is precisely what this software sets
out to collect across frames. It can only recover what
is still there.

The full route therefore uses **image sequences**: a folder of TIFF
files, one frame per file, uncompressed, 16 bit.

### 2.4.A How it goes

1. Export a TIFF sequence per scene from your editing program
   (16 bit, no compression).
2. Drag the folder into flowQt, exactly as you did with the video
   file. Everything behaves identically: views, sliders, Save recipe,
   REC.
3. Point cineFlow at it. It recognises scene folders on its own.

The output is another TIFF sequence, uncompressed. The file names
carry the **global frame number** from your source material, so that
everything lands back in the right order when you re-import it. The
layout is the one from 2.3.A: one folder per scene, TIFFs inside.

> **On TIFF compression:** leave it off when you export. With grainy
> material LZW does not make the files smaller, it makes them
> *larger* — grain is essentially incompressible, so all you get is
> the overhead. Measured on one frame, identical content: 13.9 MB
> uncompressed, 17.0 MB with LZW. It also costs time on every write
> and every read.

> **On getting the sequences in and out of your editing program
> (NLE):** chapter 9 has a working recipe for DaVinci Resolve. Other
> NLEs have not been tested yet.

### 2.4.B How large should the scan be?

Larger is not automatically better, and for this software it is often
worse — larger frames cost time, and the extra pixels rarely carry
anything the smaller ones did not.

Super-8 has a ceiling, and it is lower than the format's reputation
suggests. Kodachrome 40 — the sharpest stock the format ever had —
holds 10 % modulation out to 80 lp/mm. That figure is off its own
datasheet, and it is the film on its own. The film never works on its
own: the zoom lenses of the period contribute their share, the (plastic)
pressure plate sits in the cartridge rather than in the camera, and at
18 fps every handheld pan adds motion blur.

Those contributions multiply rather than average, so the system always
ends up below its weakest part. Roughly 30 lp/mm with a period
consumer zoom, perhaps 50 with the best primes the format ever saw.
Across the 5.46 mm projector frame that is somewhere between 330 and
550 pixels of real picture.

There is still a good reason to scan at 4K or more, and it has nothing to do with detail: an archival scan should record as best as possible the
physical state of the film, grain and all, whatever the picture
underneath is worth. cineFlow does not sit there. It sits after
the archive, in the chain that turns the recorded state into
something an audience can watch — and for that, a scan around
1800 × 1350 is a comfortable working size.

---

# 3. Principle of operation

*(You can run the program without this chapter. But every view discussed in
chapter 6 and every setting in chapter 8 sits at one of the steps
described here, and without them they are hard to place.)*

## 3.1 Basic Concept

The world in front of the camera was coherent. A wall stays a wall
from one frame to the next; a face that crosses the picture crosses it
as one thing. Grain has no such history — position and amplitude are
drawn afresh on every exposure.

cineFlow is built around that difference. It looks for what behaves
coherently from frame to frame and keeps it; what does not survive the
comparison contributes little to the result. Grain is the clearest
case, because it cannot be followed at all.

Damage on the film itself — dust, developer marks, scratches — is a
different matter. In mode `best` it stays where it is, and that is
deliberate. Removing it takes a different comparison and a different
fusion; that is what the dust modes are for, and chapter 10 describes
them.

Coherence is a property over time, and so it can only be measured
across frames: within a single image there is no way of telling what
will still be there in the next one. cineFlow looks at up to eight
frames before and eight after the one it is computing.

## 3.2 The four steps

Each output frame is built in four steps. They are worth knowing
because every view in chapter 6 sits at one of them, and every
setting in chapter 8 acts on one of them. What follows describes mode
`best`; the dust modes keep the four steps but change what happens
inside step 2 and 3, and chapter 10 says how.

| | step | what it does | what it costs |
|---|---|---|---|
| 1 | **Flow** | for every neighbour, work out how the picture moved from there to here, and register it. Reconstructs geometry. | expensive |
| 2 | **Trust** | judge each registered neighbour, pixel by pixel: is the motion consistent, does it still look like it belongs? | medium |
| 3 | **Fusion** | combine what the neighbours measured of the same point, each as far as it can be trusted | medium |
| 4 | **Enhance** | restore contrast in the fine structure — but only where there is structure, and only as far as the fusion vouches for it | cheap |

The optical flow works out where every part of the picture went
between one frame and the next — the spatio-temporal variation of the
scene. Two ratings come out of that.

First, the flow field is checked against itself: follow it forward and then back again, and a trustworthy flow arrives where it started. What
is left over after that round trip becomes `trust geo`. Second, the
flow is used to warp every neighbouring frame onto the frame being
computed, and each warped neighbour is compared with it; that
comparison becomes `trust photo`.

Both are maps, one value per pixel and per neighbour, and the fusion
multiplies them into a weight.

The original frame enters the fusion with full weight. Wherever the
neighbours have nothing to contribute, it is what comes out — pixel
by pixel, not for the frame as a whole.

Step 3 is sensor fusion in the ordinary engineering sense, except that
the sensors are not different instruments but the same one at
different points in time — and that the weights do not come from a
noise model. Classical fusion knows how noisy each sensor is and
weights against that; cineFlow has no such model. Its weights come
from the two consistency checks of step 2, and from nothing else.

Step 4 sharpens, but adaptively: only where the picture holds fine
texture, and only where the coherence is high enough to trust what
is being lifted. Both conditions are maps, and their product decides
pixel by pixel how much sharpening a spot gets.

---

# 4. Getting around

The main display of flowQt always shows one frame. Two directions of
movement change what you see there: through the scene, frame by frame,
and through the views that show what the program computed for the
frame you are on. Both are driven from the keyboard.

What the individual views mean is described in chapter 6 ("The views in detail").

## 4.1 Moving through the film

Cursor-Left and Cursor-Right move through your footage, in steps that
depend on the modifier:

| key | |
|---|---|
| Cursor-Left / Right | one frame back / ahead |
| Shift + Cursor-Left / Right | 10 frames |
| `PageUp` / `PageDown` | frame −10 / +10, like Shift + Left/Right |
| Ctrl + Cursor-Left / Right | 100 frames |
| Home / End | first / last frame of the scene |

Paging to another frame is much faster on the `Input` view than
anywhere else, because nothing has to be computed there. Find the
passage you want on the `Input` view, then switch to the view you
need.

## 4.2 Moving between views

The views are arranged in a cycle. Cursor-Up and Cursor-Down step
through it, and it wraps around — keep going in one direction and you
come back to where you started. The keys `1`–`9` jump straight to a
certain view. The `View:` box shows which one you are on and how many
there are.

Out of the box the view cycle holds nine views:

| key | view | asks |
|---|---|---|
| 1 · 2 | Input · Output | how is the restoration doing? |
| 3 · 4 | Neighbour × trust · Neighbour (warped) | what actually went in? |
| 5 | Flow fw relative | was the flow to blame? |
| 6 · 7 | Trust geo · Trust photo | which of the two tests rejected it? |
| 8 | Trust | what did the neighbourhood as a whole give? |
| 9 | Sharp gate | and what does the sharpening make of it? |


Some views depend on which neighbour you are looking at — those carry
a ◆ in the list. Keys `n` and `m` step through the neighbours, and the
slider beside the view box does the same; the label shows which one
(`In+1`, `In-2`, …). Offset 0 is skipped, since the frame is not its
own neighbour. On views without a ◆ the slider is greyed out.

A view that is not in the view cycle cannot be called up at all — you
add it first, in the `Cyclic View Editor` (key `c`). The catalogue
holds more than the nine views above. The same view may appear more
than once, which is worth knowing if you work by flipping: put
`Output` between two diagnostic maps and Up/Down always brings you
back to the result.

If you get lost, `2` brings you back to the output — as long as you
have not rearranged the cycle.

## 4.3 Zoom and pan

Scroll wheel zooms around the pointer. `z` and `Shift+z` step through
the fixed zoom levels (Fit, 1×, 2×, 4×, 8×) forward and backward. A
double-click into the image toggles between `Fit` and the last level
you were on. Click and drag moves the frame.

`Fit` scales the frame to the window — enlarging it too, if there is
room — and the number beside the selector tells you what scale that
actually came out at. From `1×` on, the figure is image pixels per
screen pixel, not a percentage.

From 2× on the image is drawn unsmoothed — one image pixel becomes a
block of screen pixels, and the grain shows as it is rather than being
averaged away by the display.

> **Note:** most of what this program does happens below the size of a
> screen pixel at full-frame view. If you are judging grain, alignment
> or sharpening at `Fit`, you might have difficulty seeing it.

## 4.4 Flipping

Most views only mean something next to another one. Up-Down between
two neighbouring entries is the basic gesture of this program, which
is why the order matters more than it looks: put views you compare
next to each other.

This is also the fastest way to judge the result at all — flip between
`Input` and `Output` and watch what moves. The eye is far better at
spotting a change than at describing a difference.

For two views that are not neighbours in the cycle, the number keys do
the same job.

Flipping stops where flowQt stops: two settings, two runs of the
batch, two versions of a recipe cannot be shown side by side. Key `p`
extends it beyond the program. It writes the view you are looking at
to disk, as a PNG, into a `_snapshots` folder next to your material —
and in any image viewer you can flip between snapshots the way you
flip between views here.

The file name carries the frame, the view and the settings it was
computed with — `f00101_output_RAFT_best_sc2_ctx1_sx3.png` — so that
ten attempts later you can still tell which was which. That also
makes it the way to keep a record of a setting: the picture and its
recipe in one name. Nothing is ever overwritten; a counter is
appended instead.

## 4.5 Split-View Mode

Key `l` splits the frame between two views, with a divider you can
drag. Press it again to step through the different split layouts, and
once more to switch the mode off — the yellow line disappears.

![Split view: input against output](images/03-ResultPageSplitView.png)

A small control above the display area shows which layout is active,
and lets you set it with the mouse instead:

![The split-view controls](images/13-splitView.png)

The box next to it decides what the current view is compared against.
Three references are available, and `k` steps through them:

- **In** — the untouched input frame.
- **Out** — the final result of the current mode. Use it to hold an
  intermediate view against what actually comes out: a trust map on
  one side, the finished picture on the other.
- **best** — the blend without dedusting. Only meaningful in the dust
  modes; it shows what the dedusting changed, in both directions
  (chapter 10). In mode `best` it *is* the current result, so there is
  nothing to compare and the split stays off.

The split also switches itself off whenever view and reference are the
same thing — standing on `Output` with reference `Out`, for instance.
The control says so in its tooltip.

Now for the part that makes this worth using: the dragging. Park the
divider on a specific detail — an edge, a face, a caption — and sweep
it back and forth. Structure that sits in the same place on both sides
passes through the line without moving; anything misaligned jumps as
the line crosses it.


---

# 5. Best Practices

This chapter is about how to proceed and what to look for. The order
of the sections is the working order: it follows the four steps from
3.2, because each step reuses what the ones before it computed. Work
forwards and the program keeps up with you — change the flow after you
have set everything else, and all of it is thrown away.

## 5.1 Don't process a full reel

One recipe will get you through a whole reel, and the result will be
visibly better than the scan. It will not be the best result,
because a reel is not one thing. Scenes differ in what they ask of
the settings — a fast pan wants more generous trust than a static
shot, a dark scene wants a different balance than a bright one, and
where the stock changes, grain changes with it.

In the simplest workflow you find a good configuration for one scene
type, save it, and copy it to the scenes that resemble it.

How fine you cut is up to you. A recipe can cover a whole reel, a run
of scenes that were shot alike, or a single scene — the batch does
not care where the cuts inside a block fall, it handles them by
itself. Cut where the settings change, not where the film does.

## 5.2 Pick the right frame

Two choices, at two levels. For a run of scenes that will share a
recipe, tune on a typical one — not the darkest, not the fastest,
the one the others resemble. Inside that scene, do the opposite: pick
a hard frame, not a pretty one. Fast motion, a dark area, the edge
of a moving object — something that shows what the settings are up
against. What works there works on the easy frames as well; the
reverse is not true.

Take your test frame from **somewhere with neighbours on both sides**. Pressing Shift+Cursor-Right once from the start puts you on frame 10, which is enough for any `context` setting.

At the very first or last frame half of the full neighbourhood is missing, and you would be tuning against a case that does not represent the scene.

## 5.3 Get the flow right first

Go to `Neighbour (warped)` and flip against `Input`.

`Neighbour (warped)` should look like your input frame. That is the
whole point of the operation: a correctly warped neighbour is a second
photograph of the same moment. Wherever it does *not* — smeared edges,
doubled contours, something in the wrong place — the flow got it
wrong.

Two settings have the largest influence. Start with the flow method:

| material | what to do |
|---|---|
| normal scenes | RAFT |
| lots of small structure (branches, foliage, fences) | DIS at a low `downscale` — costly in the batch, see 8.1.A |
| dirty material | dust mode, see chapter 10 |
| dirt *and* fast motion | clean it up in the NLE first |

Then adjust `downscale`: larger values usually give smoother flow, at the cost of fine structure, and run faster. RAFT has a lower bound here that depends on your scan size; 8.1.C has the details.

DIS can operate at full resolution (`downscale` = 1). Be aware that
the batch then runs the whole scene on the processor — not just the
flow, but trust, fusion and sharpening as well — because the recipe
picks the computing path, not only the estimator. flowQt does not
show that: its preview computes the same way whichever backend you
choose. The frame rate you get from cineFlow with DIS will be
disappointing.

## 5.4 How many neighbours are worth having

`context` pulls in two directions. More neighbours give a more stable,
less noisy result; fewer of them cost less time. What decides the
upper end is the material: at some distance the flow no longer reaches
the centre frame, and any neighbour beyond that contributes nothing.

Stay on `Neighbour × trust` and step the neighbour outwards with `m`.
Watch where the map goes black: that is the reach of the flow on this
scene, and there is no point setting `context` beyond it.

Usually the reach is generous and compute time is the real limit. In
fast-moving scenes it can collapse at the very next neighbour — and
then you know it before the batch does.

The status bar puts a number on the same question:

```
Trust +-1:0.88  2:0.82  3:0.41
```

One entry per distance: `1` is the pair of neighbours next to the
frame, `2` the pair beyond, and so on out to `context`. The number
says how much that pair contributes to the result, from 0 for nothing
to 1 for everything. Here the immediate neighbours are in nearly
full, and the third pair is already carrying less than half.

Typically the numbers hold a plateau for a while and then
fall away. There is no point setting `context` beyond the point where
they drop: those neighbours add little to the result and cost flow
calls all the same.

How far the plateau reaches is entirely a matter of the scene. With a
lot of movement even the immediate neighbour can come out low — 0.6,
say — while on an essentially static scene the twentieth frame would
still have something to contribute. cineFlow allows ±8 at most.

## 5.5 Then adjust the trusts

The two gates ask different questions of the same neighbour, and the
maps look different because of it.

`geo` asks whether the flow is consistent with itself: followed
there and back, does it return to where it started? Where it does
not, the map goes dark — in patches, because that is what occlusion
does. A fast-moving object hides part of the scene, and behind it
there is nothing for the flow to return to.

`photo` asks whether the registered neighbour looks like the frame
it was brought onto, pixel by pixel. Its map is speckled rather than
patchy: the grain differs a little everywhere, and that is what the
speckle is.

Each gate has two sliders: `mismatch`, the threshold — how much error
is still acceptable — and `softness`, which decides whether the
transition from accepted to rejected is abrupt or gradual.

Aim for as much white as possible — every black area is where a
neighbour will not help — and as much black as necessary: everything
that looked wrong in `Neighbour (warped)` must be black here.

The maps alone will not tell you when you are right. Check the result
as well:

- geo too white — artefacts appear along object edges. Compare
  `Neighbour (warped)` against `Neighbour × trust`: whatever looks
  strange at the edge of a fast-moving object should be safely dark in
  the second.
- photo too white — double contours on small, fast-moving objects will appear.
- either one too dark — the noise in the output goes up. You have
  thrown away neighbours that would have helped.

This is the part to experiment with. The interaction between the two
gates is not obvious, and you need a feel for what each slider does to
the end result. If that is more work than you want: the defaults work
for most material.

## 5.6 Enhance last

The main control of the Enhance stage is `amount`. At 0 the stage is
switched off; useful values lie roughly between 1.5 and 4.0, and where
in that range is a matter of taste (2.2.C, "Set amount right").

Two comparisons help, and they show different things. Flip against
`Input` (keys `1` and `2`, or Up/Down) to see how far the picture has
moved from the scan — that is where halos show. Park your previous
setting in a slot (8.4, "Slots") and flip against that to see what the
last step actually changed — that is where you notice a step that did
nothing.

The status bar puts numbers on it:

```
HF -32% / +73% = +18%
```

Three figures: what the neighbour averaging took away, what the
Enhance stage gave back, and the net change against the input frame.
The first is normally negative — that is the grain going; strongly
negative means structure went with it. The second follows `amount`.
The third is the product of the two: 0.68 × 1.73 gives the 1.18.

It is not a quality measure: grain and detail are both high
frequency, and this number does not tell them apart. It tells you
what happened, not whether it was right. The line appears on the
`Output` view only; on the diagnostic views it stays empty.

## 5.7 Always render a short test

Everything so far was judged on a still. The mistakes that matter most
are not still ones: flicker, pumping, crawling grain exist only in
time, and no single frame will show them to you.

So render a piece and look at it:

1. Go to the passage you tuned on.
2. Set REC to **mp4**, press **REC**, press **space**.
3. Let it run for at least a hundred frames — five or six seconds.
4. Press **space** again. The status bar confirms the clip was written.

Then watch the clip properly, at normal speed. If something pumps or
crawls, go back and correct — usually the trust settings, sometimes
`context`.

## 5.8 Save the recipe, then let the batch run

Press **Save recipe**. The file lands next to your material and is
exactly what cineFlow reads (2.2.D).

From here on flowQt is out of the picture. Point cineFlow at the
folder holding your scenes, give it somewhere to write, and leave it
alone:

```
python cineFlow.py /path/to/scenes /path/to/output
```


## 5.9 How to be wrong

- **Forcing the black open on the trust maps.** Where the registered
  neighbour genuinely went wrong, the trust map is *supposed* to go
  dark there. Turning the sliders until the map is white does not fix
  the neighbour — it blends the bad data in at full weight.
- **Working backwards.** The four stages build on each other, and
  flowQt recomputes from the stage you touched onwards. Tune the
  sharpening first and then change the flow, and two things happen:
  everything after the flow is recomputed anyway, and the sharpening
  you tuned was tuned against a fusion that no longer exists. Follow
  the order of this chapter and every setting is made on top of the
  ones that stay.
- **Tuning on an easy frame.** It will look convincing everywhere
  except where it matters.
- **Overriding the Enhance stage.** It gets trust and texture from the
  stages before it precisely so that it can decide where to act; its
  sliders shape that decision, they are not meant to switch it off.
  `base` near 1 is the usual way this goes wrong: the texture curve
  then makes no difference, and what is left is uniform sharpening
  wherever the trust allows it — the one thing the stage was built
  not to be.
- **Reaching for `context` when the trust is wrong.** More neighbours
  do not repair a bad threshold; they add more frames judged by the
  same bad threshold, at four flow calls each. Fix the gate, then see
  whether more context still buys anything (5.4).

*(This list is short because one person's mistakes are a small sample.
If you have found a way to be wrong that is not on it, an issue on
GitHub is the place to say so — the list will grow from there.)*

---

# 6. The views in detail

This chapter goes through the views one by one: what each shows, and
what to look for in it. The order follows the processing chain, not
the cycle. Views that are not in the default cycle can be brought in
with the cycle editor (key `c`).

## 6.1 Input

The frame as it came off the film. Nothing computed here — no flow, no
trust, no blending.

This is the reference everything else is judged against, and it is
available inside all other views through the split-view option.

That also makes it the view to navigate in: paging through the scene
is much faster here, because nothing has to be computed. Find the
passage you want on `Input`, then switch to the view you need.

## 6.2 Output

The most important view: this is the picture that goes to disk. The
current mode appears in brackets — *Output (best)*, *Output (dustA)*.

`Out` in the split box refers to the same thing, so you can put the
final result beside any other view: a trust map on one side, what it
did to the picture on the other.

## 6.3 Neighbour (warped)

One neighbour frame, registered by the flow so that it should line up with the centre frame. This is where you see whether the flow worked:
a correct warp is a second photograph of the same moment, so this view
should look like `Input`. Smeared edges, doubled contours or something
sitting in the wrong place mean the flow got it wrong there.

Keys `n` and `m` pick which neighbour you are looking at, and the
slider beside the view box does the same; the label next to it says
which one (`In+1`, `In-2`, …). The slider runs from −30 to +30 and
skips 0, since the frame is not its own neighbour. On views that do
not depend on a neighbour it is greyed out.

![The neighbour selection slider](images/15-nbrslider.png)

The neighbour offset is not limited by `context` — you can step past
the blend window and see how far the flow still carries on this scene.
5.4 ("How many neighbours are worth having") says what to do with
that.

## 6.4 Neighbour × trust

The same warped neighbour, multiplied by the trust it was given. This
is what the neighbour actually contributes to the output: bright where
it was accepted, black where it was rejected.

Flip between this view and `Neighbour (warped)`. Everything that
looked wrong over there must be black here — that is the gate doing
its job. Large black patches come from geo, fine speckle from photo.

> **Read the black with care.** The image is the neighbour *times* the
> trust, so a dark area can mean two things: the trust rejected it, or
> the picture is simply dark there. For the trust on its own, use
> `Trust geo`, `Trust photo` and `Trust` (6.5, 6.6).

## 6.5 Trust geo · Trust photo

One view for each of the two gates, and like the neighbour views they
change with the neighbour you have selected. White means the neighbour
is trusted in full at that point, black means not at all, grey is
everything in between — these are the weights, each on its own,
before the two are multiplied together.

The two look different because they fail differently. `Trust geo` goes
dark in patches: where the flow could not find its way back, typically
behind a fast-moving object or where something has left the picture.
`Trust photo` is speckled, because the grain never matches between two
frames, and the speckle is that mismatch pixel by pixel. A large dark
area in `Trust photo` is something else — a change in brightness, a
reflection, something that genuinely differs in the neighbour.

The sliders of the geo and photo tabs (8.2, "Trust") act directly on
these two maps. `Neighbour × trust` (6.4) shows their product laid
over the picture, and `Trust` (6.6) averages that product over all
neighbours. After a while you will set both faster on
`Neighbour × trust`, where you see the picture and the weight at once.

## 6.6 Trust

The two gates combined and averaged over all the neighbours: one
number per pixel for how much the neighbourhood as a whole
contributed. `Neighbour × trust` asks the same question of a single
neighbour; this view asks it of all of them at once, which is why it
does not change when you step with `n` and `m`.

White means the neighbours came through at that point. Dark means they
did not, and the frame there is largely left to stand on its own —
which also means it is still as grainy as it started. This is the map
to look at when a region refuses to clean up: it shows at a glance
whether that region ever had anything to draw on.

The current mode appears in brackets, because the weights differ: in
`best` each neighbour counts as geo × photo, in the dust modes as
geo × group consensus (chapter 10, "Dust and scratches").

## 6.7 Sharp gate

The sharp gate is the interface between restoration and enhancement:
it is what the Enhance stage is fed with. In practical use it is the
most important display — but it takes a while to read.

Read it as a map of how much sharpening each spot gets: none where it
is dark, the full `amount` where it is bright, in proportion in
between. How that sharpening is done — edge-preserving with the guided
filter, or evenly with a classical unsharp mask — is the filter you
chose in the `filter` tab (8.3.C).

Two things shape the map. The `texture` tab decides where there is
structure worth lifting; the trust decides where the reconstruction
underneath is solid enough to carry it. `Texture weight` (6.9) shows
the first on its own, and that is where you tell the two apart.

## 6.8 Flow fw · Warped flow bw · relative variants

Both come in an absolute and a relative variant. The relative ones
subtract the dominant motion and show what is left over, which makes
small local movement visible under a camera pan; the absolute ones
show the full motion including the pan. Out of the box the cycle
carries only the forward relative view (4.2, "Moving between views");
the backward relative one and both absolute views sit in the
catalogue and come in with the cycle editor (key `c`).

That is the recipe — once the backward view is in the cycle next to
the forward one: flip between them. Whatever stays put is an estimate
the program can rely on. Whatever jumps as you switch is a place where
the two directions disagree — and that is exactly where the geo gate
will reject the neighbour.

The motion is drawn in colour: the hue gives the direction, the
brightness the amount. Which hue means which direction does not matter
much in practice — what you look at is whether neighbouring areas
share a colour or break up into a patchwork.

That is the recipe: flip between them. Whatever stays put is an
estimate the program can rely on. Whatever jumps as you switch is a
place where the two directions disagree — and that is exactly where
the geo gate will reject the neighbour.

Both come in an absolute and a relative variant. The relative ones
subtract the dominant motion and show what is left over, which makes
small local movement visible under a camera pan; the absolute ones
show the full motion including the pan. The view cycle carries the
forward relative view out of the box (4.2); the backward relative one
and both absolute views are in the catalogue.

Within a variant the scale is shared, so those views are directly
comparable: same colour means same direction, same brightness means
same speed — forward against backward, and neighbours at any
distance against each other, since the display divides by the
neighbour offset. Absolute and relative do *not* share a scale.
Comparing brightness across the two says nothing, because the
relative pair shows only the residual after the dominant motion has
been taken out.

## 6.9 Texture weight

The map behind the `texture` tab, shown on its own: bright where the
picture holds fine structure that might be worth lifting, dark where
it is smooth. Where that structure came from it cannot tell — it
measures local contrast in the fused image, so grain the fusion left
behind counts as texture too.

`full`, `gamma` and `base` shape the curve that turns measured texture
into this map (7.3, "The curve"), and this is the only view that shows
the curve unmixed. `Sharp gate` already has the trust multiplied in,
which makes the two a pair to read together:

- dark in both — the texture curve rejected the area
- bright here, dark in the gate — the structure is there, but the
  fusion was not trusted enough to sharpen it

That is the difference between adjusting the texture settings and
fixing the trust, and this is where you tell the two apart.

---

# 7. How the Enhance stage decides

Where the Enhance stage acts is decided by three controls and by a
measurement the program makes on your material. This chapter is about
that decision, because getting it right is most of what separates a
good result from a sharpened mess.

The display to work in is `Sharp gate` (6.7). It shows how the
enhancement varies across the frame, and it is the one view in which
every earlier stage appears at once — flow, trust and fusion all feed
into it. What the program worked out about the picture is summarised
there, and applied there.

The three controls below `amount` tune the stage to the material:
`full`, `gamma` and `base`, the shape of a curve that 7.3
("The curve") describes. Which values are right depends on your
footage — the histogram in 7.2 ("The histogram") is where you find
out.

## 7.1 What is measured

For every pixel, cineFlow computes the **local standard deviation** of
the image around it. Flat sky comes out near zero; a stand of birch
trees comes out high. That number, and nothing else, is what the stage
calls texture.

It is a measurement of the picture, not of the restoration — grain
raises it just as readily as real structure does. Telling the two
apart is not this stage's job; that is what the trust maps did, two
steps earlier.

The status bar carries the measurement:

```
Adaption 39%    Tex p90 0.047 vs full 0.049
```

`p90` is the 90th percentile of the texture across the frame: nine
tenths of the picture is less textured than this. `full` is the
control you set. Their relationship is the whole game, and 7.3 says
what to do with it.

**Adaption** is the short answer to the same question: how far up the
curve the frame actually sits, from the floor (0 %) to full strength
(100 %). High means the stage is following the texture — strong on
structure, gentle on smooth areas. Roughly 30 to 90 % is a working
range. Below that the curve is barely doing anything, and the display
turns orange to say so.

## 7.2 The histogram

Key `t` lays the distribution over the image:

![The texture histogram](images/S_001_2026.08.14.png)

The dashed lines mark `p50`, `p90` and `p99`, with the values spelled
out underneath; the red line is where `full` currently sits. That line
is the boundary: everything to the right of it gets the full
treatment, everything to the left is scaled down along the texture
curve — the further left, the less.

Setting `full` to the p90 is the usual choice, and that is what the
**full = p90** button in the corner does in one click. It is not
applied by itself, and deliberately so: where `full` belongs is half a
property of the material and half a matter of taste, and neither is
something the program can measure for you.

## 7.3 The curve

Between "no texture at all" and `full` the stage does not simply
switch on. It follows a curve, and `full`, `gamma` and `base` are its
shape:

- `full` — the texture value at which the curve reaches the top.
  Everything above it gets the full treatment.
- `gamma` — what happens in between. At 1 the rise is linear. Above
  1 the middle is pushed down, so only clear structure is lifted.
  Below 1 the curve rises steeply from the start, and faint texture
  already gets most of the treatment.
- `base` — the floor: what a completely textureless area still gets.
  Normally you want this at or near zero.

The plot on the right shows this curve while you work.

> **Note:** `base` is not a way of forcing sharpening into untrusted areas. Where the trust is zero, the gate is zero, whatever the floor says.

## 7.4 What it costs to get it wrong

**`full` far above the p90** (say 0.30 against 0.03): the curve never
leaves its base, and almost nothing is enhanced. The stage runs and
does nothing. This is the one case the program flags by itself —
Adaption drops towards zero and the display turns orange.

**`full` far below the p90**, down among the grain: flat areas reach
full strength, and grain gets lifted as though it were structure. This
is the failure that looks like the software is working — it is sharp,
but it is sharpening the wrong thing.

**`base` raised well above zero**: everything gets some treatment
regardless of its texture. That can be deliberate — a raised floor
brings back a fine, even structure in the flat areas instead of
leaving them smooth, which reads as film rather than as video. Values
around 0.4 to 0.5 do this without the result going noisy. It is a
finishing touch, not a starting point.

Which settings you end up with depends on the material and on taste.
Fine-grained stock takes different numbers from a coarse one — K40
against an Agfa emulsion is a noticeable step — and what looks right
on a screen is not what looks right projected.

---

# 8. The settings in detail

This chapter describes every setting in the right-hand panel, top to
bottom — the order in which you meet them, and roughly the order in
which you touch them.

## 8.1 Engine

The Engine box holds the settings that decide how much the program
computes before anything is judged: which flow estimator, at what
resolution, over how many neighbours, and in which mode. They are the
expensive ones — change one and the whole chain is recomputed.

### 8.1.A `flow` — RAFT / DIS

Two estimators are available. **RAFT** is a neural network and needs
PyTorch with CUDA (INSTALL.md, section 6); it is the default. **DIS**
comes with OpenCV and runs everywhere, on the processor. Key `r`
switches between them — on a machine without RAFT it has nothing to
switch to and says so in the status line.

The choice is part of the recipe, and the batch honours it: a recipe
tuned with DIS is computed with DIS. Where the recipe asks for RAFT on
a machine that lacks it, cineFlow says so and falls back to DIS
(INSTALL.md, section 8.2).

> **Note:** if RAFT is not available, DIS stands in for it. The
> selector then turns orange and its tooltip says what is missing; the
> preview computes with the other method while the recipe keeps what
> you chose. That is the point: you can work out most settings on a
> machine without a GPU and still write RAFT into the recipe for the
> batch machine. The result will not be identical, though — the two
> estimators fail in different places.

**In cineFlow, DIS costs far more than the flow step alone.** cineFlow
carries two complete implementations of the same four steps: one in
PyTorch, which keeps every frame on the graphics card from the flow
through to the sharpening, and one in numpy and OpenCV, which works a
frame at a time on the processor. RAFT exists in both. DIS exists only
in the second.

A recipe asking for DIS therefore does not swap the estimator and
leave the rest as it was — it moves the whole scene onto the
processor. Flow, trust, fusion and sharpening, all of it. In practice
such a scene runs at roughly a tenth of the frame rate of the same
scene with RAFT, and the flow estimator accounts for only part of that
difference.

This is also why the preview gives no hint of it: flowQt always uses
the numpy implementation, whichever estimator you pick. There you are
comparing two flow estimators inside one chain, and the difference is
modest. In a batch run you are comparing two entire programs.

The behaviour is deliberate. The alternative would be to accept a DIS
recipe and quietly compute RAFT — which would make every setting you
arrived at in the preview meaningless.

Two is not for lack of trying. Other estimators were tested — classic
ones from OpenCV, and newer network-based ones that refine RAFT's
approach — with mixed results, and they have been taken out of the
current version rather than left in as options nobody should pick. If
one of them earns its way back, it will come with a reason.

### 8.1.B `mode` — best / dustA / dustB

Defaults to `best`, which is the degraining mode. `dustA` and `dustB`
additionally go after dust and small damage; they are useful, but have
had far less attention than the degraining, so expect to do more of
the work by hand there. Chapter 10 covers them.

In the two dust modes the `photo` sliders lose their effect and are
greyed out. `Trust`, `Sharp gate` and `Output` carry the mode in
their title.

### 8.1.C `downscale`

A *divisor* of the flow input, not a scale: 2.0 means half the edge
length, 1.2 means 83 %, 1.0 would be full resolution. Cost grows
*quadratically* — going from 2.0 to 1.2 is about 2.8× the pixels.

The larger the value, the smoother the flow field: less grain for the
estimator to lock onto, but also less structure for it to follow.
Small, fast-moving detail is the first thing to go.

There is a lower bound, and it depends on the backend. RAFT works
within a fixed pixel budget, so at a given scan size it cannot go
below a certain value — at 1800 × 1350 that is about 1.2. flowQt
enforces this: it raises the slider by itself and says so in the
status bar. DIS runs on the CPU and allows 1.0 at any size.

> **Note:** If a GPU run slows to a crawl instead of failing, the GPU
> is out of memory and the driver is papering over it — see section
> 8.6 of [INSTALL.md](INSTALL.md).

### 8.1.D `context`

How many neighbour frames on each side are taken into account — for
the fusion in `best`, for the committee in the dust modes. Each one
costs two flow calls, so cost grows linearly, while the benefit grows
only with √N.

How to find the right value for a scene: see 5.4 ("How many neighbours
are worth having").

## 8.2 Trust

Each tab has the same two controls, and they always mean the same
thing. `mismatch` is the threshold: how much error is still acceptable,
or more precisely the error at which trust has fallen to 0.5 —
smaller values are stricter. `softness` decides whether the
transition from accepted to rejected is abrupt or gradual; smaller
values make it sharper.

Tabs that do not apply to the current mode are greyed out, and their
tooltip says which mode they belong to.

The unit of `mismatch` differs from tab to tab — it is shown in the
slider label, and it is why the same number means something else in
each of them.

### 8.2.A geo tab — `mismatch` [px] · `softness`

Measured in real pixels: the forward-backward inconsistency of the
flow. Follow the motion there and back again — how far from the
starting point do you land?

Judged on `Trust geo`, or faster on `Neighbour × trust`, where geo
failures show as *large connected patches*.

Values between 1.0 and 4.0 px cover most material.

### 8.2.B photo tab — `mismatch` [0..1] · `softness` · `smooth` [px]

`mismatch` is the allowed difference in normalised image intensities,
measured after smoothing over `smooth` pixels. That smoothing is what
keeps the test from reacting to grain — which differs between every
pair of frames by construction, and would otherwise fail the test
everywhere.

What the test catches are exposure and appearance changes at places
where the geometry is perfectly correct — that is the division of
labour between the two gates. A larger `smooth` also settles the map
in time: the trust flickers less from frame to frame.

Photo failures show as *fine speckle* on `Neighbour × trust`. Speckle
everywhere means the threshold is too tight for material this grainy.

The `photo` settings have no effect in the dust modes.

### 8.2.C dustA tab — `mismatch` [MAD] · `softness` · `center_weight`

Only active in `dustA`. Measured in multiples of the MAD — the spread
within the group of frames. A pixel that sits `mismatch` MADs away
from the group median is no longer trusted.

`center_weight` is how many votes the input frame gets in that group.
It balances dust removal against fast-moving objects: the more weight
the centre frame carries, the less readily the group can outvote it.
Normal value is 1.

### 8.2.D dustB tab — `mismatch` [spread] · `softness` · `disagreement` [0..1] · `softness` [0..1]

Only active in `dustB`. Same curve as dustA, but the spread comes from
a committee that *excludes* the input frame — which is what lets it
judge the input frame at all, and means a defect sitting *on* the
input frame can be caught too.

`disagreement` is a second gate on the committee itself: where the
neighbours do not agree among themselves, their verdict on the input
frame is worthless and is not acted on. Its effect is hard to see, and
no material has turned up so far where moving this slider made a
visible difference. It is there because the case exists, not because
you will need it.

## 8.3 Enhance

The `Enhance` box steers step 4 ("Enhance") of 3.2.

### 8.3.A `amount`

The master control of the stage: at 0 the stage is skipped entirely,
not merely set to no effect. Useful values are roughly between 1.5
and 4.0.

Chapter 2.2 ("One slider to rule them all") walks through it at 0, at
maximum, and in between; 5.6 ("Enhance last") says what to judge it
by.

### 8.3.B texture tab — `full` · `gamma` · `base`

These three decide *where* the Enhance stage does its work — the shape
of the curve it follows between smooth and textured.

Press `t` for the texture histogram. It appears over the image and
carries the measured `p50`/`p90`/`p99` of the current frame, together
with a **full = p90** button that sets `full` to that value — the
usual starting point.

What the three do, and how to read the plot and the histogram while
setting them, is chapter 7.

### 8.3.C filter tab — guided / gauss · `sigma` · `eps`

This tab defines the base filter of the Enhance process. Two are
available: a classical unsharp filter (here called `gauss`) and a
directional one (`guided`). Your usual choice should be `guided`. Key
`g` toggles between them.

- `sigma` — the size of the structure being lifted, in pixels. With
  `gauss` it is the frequency cutoff instead. Match it to the finest
  real detail you want to keep: at ~267 px/mm (a typical 2k resolution) the finest thing the film
  holds is about 3 px across, and `sigma` 0.5 puts the cutoff right
  there. Work out the equivalent for your own scan.
- `eps` — for the guided filter only: how strongly it distinguishes
  an edge from a flat area. Small (0.01) is strongly edge-preserving;
  at the top of its range (0.1) it approaches a box filter and loses
  exactly the property `guided` was chosen for. With `gauss` it has no
  effect.

Set `sigma` first and leave it: it also fixes the window the guided
filter works in, and therefore what `eps` is measured against.


## 8.4 Slots

There are six memories for complete parameter sets — kept inside
flowQt rather than next to your material. A slot holds every setting,
including the ones the current mode does not use; a recipe file keeps
only what the mode needs.

![The slot buttons](images/Screenshot_2026-08-13_125143.png)

- **Left click** loads a slot.
- **Right click** stores the current settings in it.
- **Shift + right** clears it, after asking.
- **Ctrl + right** attaches a short note, which then shows up in the
  tooltip along with the main values.

A slot that holds something carries a `●` behind its name, and it
lights up when its contents match what you have set right now. That is
worth watching: it tells you at a glance whether you are still on a
stored set or have drifted away from it.

`Default` (key `d`) restores the factory settings and behaves like a
slot in every other respect.

**Load …** reads settings from any JSON file that holds them — a
`cineflow.json`, the `cineflow_run.json` from a batch run, or a recipe
you renamed. The name does not matter, the content does: a file
without parameters in it is refused with a note in the status line.

Dropping a file onto the flowQt main window does the same and is quicker:
any `.json` is read as settings. That includes the `cineflow_run.json`
from a batch run — flowQt recognises the log and says in the status
line which run the settings came from.

Slots survive restarts and are independent of the material you happen
to have open — they are for the settings you keep coming back to.

> **Note:** **Save recipe** covers the other half: it writes the current settings where cineFlow will look for them, and it is highlighted whenever those differ from what is stored. Key `e`; 2.2.D covers the workflow.

## 8.5 Autoplay and Record

![The Autoplay | Record box](images/Screenshot_2026-08-13_125935.png)

### 8.5.A Step, play / pause

The two buttons run the scene backwards and forwards; `y` and `x` do
the same from the keyboard, and `space` starts and stops a forward
run. Pressing again stops it.

**Step** is how many frames each step advances, from a fixed list: 1,
2, 5, 10, 20, 50, 100, 200. At 1 you see every frame, which is the
setting for judging grain; larger values move through the scene
faster.

During a run you can change the view with Up/Down or 1–9 without
stopping it. However note: your modifications will be recorded.

### 8.5.B REC — mp4 / tif

Arms the recorder (key `u`) — nothing is written yet. Start a run and
every frame it computes goes to disk, into a `_clips` folder next to
your material: `<scene>/_clips/clip_NNN.mp4` for video, or a folder
`<scene>/_clips/clip_NNN/` of single TIFF frames, numbered in the
layout cineFlow itself uses.

What lands there is what is on screen. Change the view during a run,
switch the split on, drag the divider, move a slider — all of it goes
into the clip. That can be exactly what you want for showing someone
what a setting does, and it is a nuisance when you meant to record a
clean result.

The box beside it picks the format. Take **mp4** for a quick look —
written at 18 fps with the `mp4v` codec, which every player reads and
nobody would archive — and **tif** when the result has to survive. The
batch writes FFV1 instead (2.3.D).

---

# 9. Export from your NLE

*At this point in time this chapter is only applicable to DaVinci
Resolve. Other editing programs will have equivalent settings, but
none of them have been tested.*

Chapter 2.4 said the full route uses image sequences rather than video
files. Getting them out of the NLE in a form cineFlow can use is
mostly a matter of four settings, and one of them is easy to get
wrong.

## 9.1 Image sequences — the full-quality route

In the Deliver page, set:

| setting | value |
|---|---|
| Export | **Individual clips** |
| Filename | **Custom name**, `Frame_` |
| File subfolder | `Szene_` + the *Timeline Index* variable |
| Place clips in separate folders | **off** |
| Each clip starts at frame 1 | **off** |
| Format | TIFF, 16 bit, **no compression** (see 2.4) |

*Timeline Index* is an internal DaVinci variable, not text you type.
Type `%` in the field and DaVinci offers a list of variables that
narrows with every further letter:

![Picking a DaVinci variable](images/17-davinciVariableList.png)

Pick the one you want and it turns into a rounded chip inside the
field, next to whatever you typed yourself:

![The variable as a chip](images/18-davinciVariableChip.png)

So the subfolder field holds the literal text `Szene_` followed by the
*Timeline Index* chip — there are no square brackets anywhere, they
are only used in this manual to name the variable.

The result is one folder per scene, and inside it files named like

```
Szene_2/Frame_00000072.tif
```

> **The one setting that matters.** The checkbox at
> `Each clip starts at frame 1` must be **off**. With it on, every
> scene restarts its numbering at 1 and the connection to the source
> timeline is lost — the files still look fine, and you will not
> notice until you try to put the result back. With it off, the number
> in the filename is the frame's position in the whole timeline, and it
> stays true through the entire round trip.

*Timeline Index* does not pad with zeros, so you will get `Szene_2`
next to `Szene_10`. That is expected; cineFlow sorts scene folders
naturally and reads them in the right order.

## 9.2 Video clips — the quick route

Chapter 2 works with video clips because that is the shortest way to
a first result. It is not the way to the best one: the codec throws
away exactly the fine irregular structure cineFlow collects across
frames (2.4), and the frame numbers do not survive — a video clip
carries no per-frame names, so the output starts at 0 and the
connection to the source timeline is gone.

If you export video anyway, one setting matters. `Data Levels`, under
*Advanced Settings* in the Deliver page, defaults to `Auto` and writes
limited range — and DaVinci does not tag what it wrote. Set it to
**Full**. If a clip was exported without it, tell cineFlow instead of
letting it guess:

    python cineFlow.py /path/to/scenes /path/to/output --video-range pc

`pc` is full, `tv` is limited; the switch overrides both the
measurement and an existing tag.

## 9.3 Coming back

cineFlow writes another TIFF sequence, uncompressed, and keeps the
filenames. Because the numbers are global timeline positions rather
than per-scene counts, re-importing is unremarkable: every frame lands
where it came from.

Import the whole output folder into DaVinci — the one named after the
run, with all the scenes inside it. Each scene folder is recognised as
one clip, and the media pool will usually have them in the right order
already.

To be sure of it, go to the Cut page, sort the clips alphabetically,
select them all (`Ctrl+A`) and drag them onto the timeline. They land
in the order they were shot, with all the cuts where they were.

---

# 10. Dust and scratches

The same flow and trust machinery answers a second question. In
`best` the frame being computed is the reference: every neighbour is
judged by how well it agrees with it. The dust modes have no
reference. Every frame in the window is judged against what the group
as a whole agrees on, and the current frame is one of them — it can
lose that vote like any other. Whether it also has a say in forming
the consensus is the difference between `dustA` and `dustB`.

That changes the fusion, not just the criterion. In `best` the centre
frame is the anchor: it enters with full weight, and the neighbours
can only add to it. In the dust modes it is judged like everything
else and gets a weight of its own — which is what allows it to be
outvoted where it is the odd one out.

That catches short-lived damage: dust, hairs, a scratch that lasts a
frame or two.

There are two modes for it, `dustA` and `dustB`. They differ in how
the consensus among the neighbours is formed: in `dustA` the input
frame is a member of the committee that judges it, in `dustB` it is
not. Excluding it has a second effect — where the neighbours disagree
among themselves, the input frame is left alone, which protects it
exactly where the flow estimator is struggling. `dustA` is generally
the slightly better performer; `dustB` is the alternative for scenes
where A removes too much. Which one suits your material is something
you will have to try.

Here is an example — left the input, right the result of the dustA
mode. The dust is gone, and with it the grain: the dust modes do not
replace the degraining, they are the degraining with the question
turned around.

![DustA Example](images/16-dustAExample.png)

> **What it cannot tell apart.** The method has no idea what dust
> *is*. It knows only that something was there in one frame and in no
> other. A light that blinks for a single frame looks exactly like
> that — and will go the same way as the dirt. So will a spark, a
> camera flash, and the one frame in which someone blinked.

---


# Appendix — Keyboard reference

The same list the program shows on key `h`. If the two ever disagree,
believe the program.

## A.1 Navigation

| key | |
|---|---|
| `Left` / `Right` | frame ±1 |
| `Shift` + `Left` / `Right` | frame ±10 |
| `PageUp` / `PageDown` | frame −10 / +10, like Shift + Left/Right |
| `Ctrl` + `Left` / `Right` | frame ±100 |
| `Home` / `End` | first / last frame of the scene |
| `Up` / `Down` | step through the views |
| `1` … `9` | select a view directly (the number is shown in the list) |
| `n` / `m` | test neighbour, inward / outward |

## A.2 View

| key | |
|---|---|
| `z` / `Shift+z` | zoom step up / down (Fit, 1×, 2×, 4×, 8×) |
| Mouse wheel | zoom around the pointer |
| Double-click on the canvas | Fit ↔ last zoom step |
| Click and drag | pan |
| `l` | split: off → In \| View → View \| In |
| `k` | split reference: In / Out / best |
| `t` | texture histogram overlay on / off |
| `g` | detail filter (guided / gauss) |
| `r` | flow backend (RAFT / DIS) |
| `c` | edit the view sequence |
| `Esc` | leave the curve preview and go back to the cycle |

Dropping a config `.json` on the canvas applies it.

`Esc` belongs to the curve preview: with the preview box set to
`on-edit`, touching a trust or texture slider switches the display to
the matching map for as long as you are working on it. The view
counter turns cyan and shows the name of the map instead of the
position in the cycle. `Esc` ends it and puts you back where you were;
so do `Up`/`Down` and the number keys. The cycle itself is not
changed.

## A.3 Autoplay and recording

| key | |
|---|---|
| `space` | play / pause: start a forward run, or stop it |
| `x` / `y` | autoplay forward / back (again stops) |
| `u` | start / stop recording |

During a run, `Up`/`Down` and `1`–`9` change the view **without**
stopping it.

## A.4 Parameters and files

| key | |
|---|---|
| `d` | load defaults (all parameters) |
| Double-click on a slider | that slider's default (on the label or the slider, not the number field) |
| `e` | export `cineflow.json` |
| `p` | save the current view as PNG |
| `h` | this list |

Slot buttons: **L** = load · **R** = store · `Shift`+**R** = clear ·
`Ctrl`+**R** = note.
