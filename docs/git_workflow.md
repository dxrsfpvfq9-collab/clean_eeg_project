# Git workflow for clean_eeg_project

This document explains how this project is set up in git + GitHub, how to
work with it day-to-day, and how to recover if something goes wrong.

Written 2026-05-19 after setting up the GitHub remote.

---

## What's set up

| What | Where |
|---|---|
| **Local repo** | `C:\BrainPanel\clean_eeg_project 2025\.git\` on this PC |
| **GitHub remote** | https://github.com/dxrsfpvfq9-collab/clean_eeg_project (private) |
| **Branch** | `main`, tracking `origin/main` |
| **Authentication** | Git Credential Manager (already installed with Git for Windows); token stored after first push. Uses "Sign in with Apple" because the GitHub account was created via Apple Private Relay. |

The two `CleanEEGProject - production/` and `CleanEEGProject - development/`
sibling folders are **not** under git. Only `clean_eeg_project 2025/` is the
version-controlled copy.

---

## One-time setup on another PC

When you want to work on this project from a different machine:

```
git clone https://github.com/dxrsfpvfq9-collab/clean_eeg_project.git
cd clean_eeg_project
py -m pip install -r requirements.txt
py -m pip install -r requirements-dev.txt
py -m pytest -v
```

The first `git clone` will prompt for authentication (browser will open, "Sign
in with Apple"). After that, push/pull work without prompting.

If you want the project in a specific folder name (e.g. matching this PC):

```
git clone https://github.com/dxrsfpvfq9-collab/clean_eeg_project.git "clean_eeg_project 2025"
```

---

## Day-to-day workflow

### Making a change

```
# Edit some files...
git status                          # see what changed
git diff                            # see the actual changes
git add <file1> <file2> ...         # stage specific files
git commit -m "Short description of what changed and why"
git push                            # send to GitHub
```

### Pulling in changes made elsewhere

```
git pull                            # fetch + merge from GitHub
```

If you've been editing locally AND someone else pushed, `git pull` will try
to merge. If it can't auto-merge, it'll tell you which files have conflicts
and you'll need to edit them by hand.

### Seeing history

```
git log --oneline                   # short list of recent commits
git log -p <file>                   # detailed history of one file
git show <commit-hash>              # see what one specific commit changed
```

---

## Writing good commit messages

The commits in this project's history follow this pattern:

```
Short imperative title (under ~70 chars)

Optional longer explanation:
- What changed (the diff is usually obvious)
- WHY it changed (the important part)
- Anything tricky or surprising
- Verification that was done (e.g. "pytest 7/7 green",
  "page 1 metrics still match production reference")
```

Why this matters: a year from now, `git log` is the only record of why a
line of code looks the way it does. "Fixed bug" is useless;
"Restored detect_band_with_rms to original arithmetic because the
downstream metric functions are calibrated to the float-distance shape
of the artifact_mask" is gold.

---

## Substituting a file into production

The procedure that worked during the May 2026 review session:

1. **On dev PC**, make and commit the change, push to GitHub.
2. **On production server**, before swapping any file:
   ```
   copy "files\create_report_pdf.py" "files\create_report_pdf.py.bak"
   ```
3. **Compare** the production file against the dev version:
   ```
   diff "files\create_report_pdf.py" "C:\path\to\dev\files\create_report_pdf.py"
   ```
   Confirm only the intended changes appear.
4. **Substitute** the file (copy dev → production).
5. **Run one verification EDF** through `module61.py` on production.
6. **Open the resulting PDF** and confirm:
   - Page 1 metric values are identical to a previous run on the same EDF
     (any numerical drift means something else changed).
   - Page 3 layout looks right (may render slightly differently from dev
     due to matplotlib version differences).
7. If anything is off: `move "create_report_pdf.py.bak" "create_report_pdf.py"`
   and you're back where you started.

---

## Recovery — "I messed something up"

### "I accidentally edited a file and want to undo my changes"

If you HAVEN'T committed yet:
```
git checkout -- path/to/file       # discard uncommitted changes to that file
git status                         # confirm it's gone
```

### "I want to undo the last commit but keep the changes in my files"

```
git reset --soft HEAD~1            # uncommit but keep changes staged
# or
git reset HEAD~1                   # uncommit, unstage, but keep changes in working dir
```

### "I want to completely throw away the last commit"

```
git reset --hard HEAD~1            # DANGEROUS — loses changes
```

Don't do `--hard` unless you really mean it. The change is gone.

### "I want to see what a file looked like at a previous commit"

```
git show <commit-hash>:path/to/file > recovered_file.py
```

Useful for getting back a deleted file or seeing what was different before
a change.

### "I want to undo a commit that's already pushed"

The safest way is to make a NEW commit that undoes the changes:

```
git revert <commit-hash>           # creates an inverse commit
git push                           # send the inverse commit to GitHub
```

This preserves history (everyone can see both the bad commit and the
revert). The alternative is `git push --force` which rewrites history —
**don't do this** unless you're absolutely certain no one else has pulled
the bad commit.

---

## Files NOT in git (intentionally)

These are excluded by `.gitignore`:

- `__pycache__/`, `*.pyc` — Python bytecode (regenerated automatically)
- `mne_data/` — MNE's auto-downloaded brain template (~221 MB)
- `old dataset nflaa/` — old example output files
- `qq_plot_dataset_*.png` — temp visualization files
- `get-pip.py`, `pip.exe` — installer artifacts
- `.claude/` — Claude Code session state
- `*conflicted copy*` — Dropbox sync conflicts (we deleted the legacy ones,
  this pattern prevents new ones from being committed)
- Test/build caches (`.pytest_cache/`, `.coverage`, `htmlcov/`, etc.)

If you need to commit one of these for some reason, edit `.gitignore`.

---

## What's actually on GitHub

Browse https://github.com/dxrsfpvfq9-collab/clean_eeg_project to see:

- `README.md` — short project overview
- `CLAUDE.md` — detailed architecture and gotchas (the operational guide)
- Source: `module7.py`, `module61.py`, `tomwatchdog.py`, `files/`,
  `plot/`, `process/`
- Reference data: `EC_191.out_file.icale.xlsx` (the 192-EEG reference
  database used for z-scores), `19chan.sLoreta.none.csv`,
  `MNI-BAs-6239-voxels.csv`
- Tests: `tests/unit/`
- Config: `requirements.txt`, `requirements-dev.txt`, `pytest.ini`,
  `.gitignore`
- Docs: this file (`docs/git_workflow.md`)

Sample EDF files (`C:\BrainPanel\edf file samples\`) are **NOT** in the
repo — they live outside the project directory and aren't tracked. If
you need them on another PC, copy them separately.

---

## Forgetting the GitHub account

If you ever can't sign in, the account is:

- **Username:** `dxrsfpvfq9-collab`
- **Email (for sign-in via Apple):** `dxrsfpvfq9@privaterelay.appleid.com`
  (a Private Relay address — your real email is hidden behind it)
- **Auth method:** Sign in with Apple

GitHub's password recovery flow won't work because there's no password;
use Apple's account recovery if you lose access to the Apple ID.

---

## Quick reference card

| Goal | Command |
|---|---|
| See what's changed | `git status` and `git diff` |
| Commit changes | `git add <files>` then `git commit -m "msg"` |
| Push to GitHub | `git push` |
| Pull from GitHub | `git pull` |
| Browse history | `git log --oneline` |
| Discard uncommitted change | `git checkout -- <file>` |
| Recover an old file version | `git show <hash>:<path> > file.py` |
| Clone on another PC | `git clone https://github.com/dxrsfpvfq9-collab/clean_eeg_project.git` |
| Where the GitHub repo lives | https://github.com/dxrsfpvfq9-collab/clean_eeg_project |
