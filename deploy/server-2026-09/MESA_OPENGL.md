# Software OpenGL (Mesa) for the cascade's brain pages

## The problem

Each cascade component gets a 3D source-localization page, rendered by
PyVista → VTK → OpenGL. VTK needs **OpenGL 3.2 or newer**. The AWS instances
have no GPU, and a Windows RDP session exposes only the generic GDI driver,
which is OpenGL 1.1. VTK fails to create a context and then crashes the whole
process:

```
failed to get wglChoosePixelFormatARB
failed to get valid pixel format
GLEW could not be initialized: Missing GL version
```

followed by "python.exe has stopped working". That is a **native crash**, not a
Python exception, so the try/except around the cascade block cannot catch it —
the panel is lost along with the cascade. This is why the cascade must stay off
on any server until this is fixed and tested.

Mesa's **llvmpipe** is a CPU implementation of OpenGL 4.5. Dropping it beside
`python.exe` gives VTK the context it needs, with no code change and no GPU.

## Before you start — what this affects

The DLL is loaded by whatever `python.exe` sits next to it, so it affects every
Python program run by that interpreter. In practice that is only this pipeline,
and only the cascade path actually uses OpenGL — the panel is drawn by
matplotlib's Agg backend, which never touches GL.

Rollback is deleting the DLLs. Nothing is installed, no registry is touched.

## Steps (development server first)

### 1. Find the interpreter folder

The watchdog prints it at startup — the `interpreter:` line. On the dev server
it is:

```
C:\Users\tcollura\AppData\Local\Programs\Python\Python312\
```

Confirm with:

```
py -c "import sys; print(sys.executable)"
```

The DLLs go in **that** folder, next to `python.exe`.

### 2. Download Mesa for Windows

Prebuilt Windows binaries come from `pal1000/mesa-dist-win` on GitHub
(a third-party build of upstream Mesa — check it is acceptable to you before
putting it on a server):

```
https://github.com/pal1000/mesa-dist-win/releases
```

Take the latest **`mesa3d-<version>-release-msvc.7z`**. Extract it on your
workstation; inside is an `x64` folder.

### 3. Copy the DLLs

Copy **every DLL from the `x64` folder** into the Python folder from step 1.
There are only a handful. Copy all of them rather than picking out
`opengl32.dll` alone — recent Mesa splits the implementation across
`opengl32.dll` plus companions such as `libgallium_wgl.dll`, and a missing
companion fails exactly like having no Mesa at all.

Do **not** put anything in `C:\Windows\System32`.

### 4. Force the software driver

Set a system environment variable so VTK does not try a hardware path that
isn't there:

```
GALLIUM_DRIVER = llvmpipe
```

System Properties → Advanced → Environment Variables → System variables → New.
Then close and reopen the console so it inherits the variable — the watchdog
must be restarted for its children to see it.

### 5. Check OpenGL before re-running a study

```
py -c "import vtk; w=vtk.vtkRenderWindow(); r=vtk.vtkRenderer(); w.AddRenderer(r); w.Render(); print('
'.join(l.strip() for l in w.ReportCapabilities().splitlines() if 'OpenGL vendor' in l or 'OpenGL renderer' in l or 'OpenGL version' in l)); w.Finalize()"
```

Expect something like:

```
OpenGL vendor string:  Mesa
OpenGL renderer string:  llvmpipe (LLVM 17.0.6, 256 bits)
OpenGL version string:  4.5 (Core Profile) Mesa 24.x
```

Any GL version of 3.3 or higher is enough. For comparison, the workstation
where cascades already render reports `Intel(R) UHD Graphics 770`, OpenGL
4.5 — that hardware context is exactly what the server is missing.

If this still crashes, Mesa is not being loaded: the DLLs are in the wrong
folder, or only some of them were copied. Nothing after this step will work
until it passes, so do not move on.

### 6. Turn the cascade back on

Copy `staged\files\edftotextbycommandplotproc.py` (4147 bytes,
`selstring[12] = 1`) over the panel-only version. Restart the watchdog, upload
one study, and time it.

### 7. Judge the cost

llvmpipe renders on the CPU, and the brain page is the heaviest part of each
component. A study took **~8 minutes** with hardware OpenGL on a workstation.
If the dev server lands anywhere near that, this is a good outcome. If it runs
to 30+ minutes per study, software rendering is not viable for live ingest —
note that the watchdog kills any study exceeding 25 minutes
(`PER_FILE_TIMEOUT`), so a slow render shows up as a `TIMED OUT` line rather
than a hang.

In that case the fallback is to keep the panel fix on the server with the
cascade off, and render cascades on a workstation with `batch_imagecascade.py`,
which already works there.

## Rolling back

Delete the DLLs you copied in step 3 and remove the `GALLIUM_DRIVER` variable.
If the cascade was turned on in step 6, put the panel-only
`edftotextbycommandplotproc.py` back (`staged-panel-only\files\`, 4219 bytes).

## Only after dev works

Repeat on production. Do not enable the cascade there until a dev study has
rendered end to end, with a cascade PDF whose brain pages show an actual brain
rather than black.
