# build_cascade_index.py
# Scan the STS EEG Quality Assurance Reviews tree and write a resume index
# (_IMAGECASCADE_INDEX.md) recording, per top-level year folder, how many
# renderable EDFs exist and how many already have an .imagecascade.pdf sibling.
# Re-runnable: regenerate anytime to refresh the status snapshot.
#
# Usage: py build_cascade_index.py ["<QA root>"]

import os
import sys
import glob
import datetime

DEFAULT_ROOT = r"C:\Users\tcollura\Dropbox\STS EEG Quality Assurance Reviews"


def renderable(p):
    low = p.lower()
    return not (low.endswith(".clean.edf") or low.endswith(".unclean.edf"))


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ROOT
    all_edfs = [p for p in glob.glob(os.path.join(root, "**", "*.edf"), recursive=True)
                if renderable(p)]

    # group by top-level subfolder under root
    groups = {}
    for p in all_edfs:
        rel = os.path.relpath(p, root)
        topc = rel.split(os.sep)[0]
        done = os.path.exists(p[:-4] + ".imagecascade.pdf")
        g = groups.setdefault(topc, {"edfs": 0, "done": 0})
        g["edfs"] += 1
        if done:
            g["done"] += 1

    # order year folders newest-first; non-year folders after, alpha
    def sort_key(name):
        digits = "".join(ch for ch in name[:12] if ch.isdigit())
        year = digits[:4] if len(digits) >= 4 else ""
        return (0, name) if year.startswith("20") is False else (-int(year), name)
    order = sorted(groups.keys(), key=sort_key)

    total_edfs = sum(g["edfs"] for g in groups.values())
    total_done = sum(g["done"] for g in groups.values())

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []
    lines.append("# Image-Cascade Render Index — STS EEG Quality Assurance Reviews")
    lines.append("")
    lines.append(f"_Last updated: {now}_")
    lines.append("")
    lines.append(f"**Corpus root:** `{root}`")
    lines.append("")
    lines.append(f"**Overall: {total_done} / {total_edfs} renderable EDFs have an "
                 f".imagecascade.pdf** "
                 f"({total_edfs - total_done} remaining).")
    lines.append("")
    lines.append("Renderable = every `*.edf` except `*.clean.edf` / `*.unclean.edf`. "
                 "Both EC and EO recordings are included.")
    lines.append("")
    lines.append("## Status by top-level folder (newest year first)")
    lines.append("")
    lines.append("| Folder | EDFs | Cascades done | Remaining | Complete? |")
    lines.append("|---|---:|---:|---:|:--:|")
    for name in order:
        g = groups[name]
        rem = g["edfs"] - g["done"]
        mark = "yes" if rem == 0 else ("in progress" if g["done"] else "not started")
        lines.append(f"| {name} | {g['edfs']} | {g['done']} | {rem} | {mark} |")
    lines.append("")
    lines.append("## How to resume")
    lines.append("")
    lines.append("The runner skips any EDF that already has an `.imagecascade.pdf` "
                 "sibling, so re-running is always safe and idempotent. Process one "
                 "year at a time, newest first, with `--top=`:")
    lines.append("")
    lines.append("```bash")
    lines.append("cd \"C:/BrainPanel/clean_eeg_project 2025\"")
    for y in ("2026", "2025", "2024", "2023", "2022"):
        lines.append(f"py batch_imagecascade.py --top={y} "
                     f"\"{root}\"")
    lines.append(f"# final mop-up: catch non-year folders (Christen's Data, "
                 f"tom misc testing, etc.)")
    lines.append(f"py batch_imagecascade.py \"{root}\"")
    lines.append("```")
    lines.append("")
    lines.append("`--list` previews without rendering; `--redo` re-renders existing; "
                 "`--limit=N` caps the run. Progress is appended to "
                 "`_imagecascade_batch.log` in the root. Regenerate this index "
                 "anytime with `py build_cascade_index.py`.")
    lines.append("")
    lines.append("## Notes / gotchas")
    lines.append("")
    lines.append("- **Per file:** ~1.5 min (EC) to ~2.5 min (EO); output PDF ~7–15 MB "
                 "(40–44 pages: overview + summary table + one viewer + one brain "
                 "page per ICA component).")
    lines.append("- **Screen capture:** each component page is grabbed from an "
                 "on-screen Tk window (`ImageGrab`). The run monopolizes the active "
                 "desktop and flashes windows; keep other windows off it. "
                 "`save_gui_screenshot` forces the render window topmost before each "
                 "grab so the capture never catches an overlapping window.")
    lines.append("- **Side artifacts** left next to each EDF: `<name>.ica.png`. "
                 "Transient `screenshot_N.png` / `brain_view_N.png` are left in each "
                 "folder (overwritten per file).")
    lines.append("- **Pre-existing cascades** in `output/` and `output old/` "
                 "subfolders (~65) come from older one-off runs and have no sibling "
                 "EDF; they are counted here only if a sibling EDF exists.")
    lines.append("- **Not rendered:** `.clean.edf` / `.unclean.edf` variants.")
    lines.append("")

    out = os.path.join(root, "_IMAGECASCADE_INDEX.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("wrote", out)
    print(f"overall {total_done}/{total_edfs} done")
    for name in order:
        g = groups[name]
        print(f"  {name}: {g['done']}/{g['edfs']}")


if __name__ == "__main__":
    main()
