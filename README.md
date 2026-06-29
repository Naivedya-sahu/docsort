# 📄 docsort

![python](https://img.shields.io/badge/python-3.9%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)
![offline](https://img.shields.io/badge/local%20pass-100%25%20offline-orange)
![ui](https://img.shields.io/badge/UI-CLI%20%2B%20dark%20GUI-7c5cff)

Local-LLM document tagger + sorter. Reads each academic document, classifies it into
a **STREAM** (CW / GATE / PROJ / RES / REC / REF) and a **SUBJECT** (your EE topic list),
stamps a `[STREAM-SUBJECT]` filename prefix, then moves files into a clean tree.

The whole classification pass runs **locally and free** against [LM Studio](https://lmstudio.ai).
A frontier model (Claude Code, on your subscription) is an **optional** fallback for the few
genuinely-ambiguous files. Ships with both a **CLI** (`docsort`) and a **modern dark GUI**
(`docsort-gui`).

---

## Install

**Option A — prebuilt executable (no Python).** Grab `docsort-gui.exe` (GUI) and/or `docsort.exe`
(CLI) from the [latest release](https://github.com/Naivedya-sahu/docsort/releases). Double-click the
GUI exe and go. You still need [LM Studio](https://lmstudio.ai) running with a VL model loaded.

**Option B — pip** (Python 3.9+, Windows):

```bash
git clone https://github.com/Naivedya-sahu/docsort.git
cd docsort
python -m venv .venv
.venv\Scripts\activate
pip install .            # or: pip install -e .   (editable, for hacking)
pip install ".[all]"     # add .doc/.docx/.pptx readers (python-docx, python-pptx, pywin32)
```

This installs two commands:

| Command | What |
|---|---|
| `docsort` | the CLI tagger / mover |
| `docsort-gui` | the dark folder-picker GUI |

If your Python's `Scripts\` dir is on PATH, both work in **any** cmd/PowerShell window with no venv.
Otherwise call them as `python -m docsort.cli ...` / `python -m docsort.gui`.

No-install option: from the cloned folder just run `run.bat` (GUI) or `run.bat "C:\folder"` (CLI).
`run.bat` auto-uses the repo's `.venv` and works from **both cmd and PowerShell**.

### What you need running
- **[LM Studio](https://lmstudio.ai)** with a **vision (VL) model loaded** and its local server started
  (defaults to `http://localhost:1234`). A 3B–8B Qwen-VL works well and reads both text and images.
  You don't have to name the exact model — docsort **auto-detects whatever VL model is loaded**.
- *(optional)* **Claude Code CLI** for the frontier fallback — see [Claude auth](#optional-claude-frontier--auth).

---

## Quickstart

**GUI** (easiest):
```bash
docsort-gui        # or: run.bat
```
Browse to a folder, leave **Create copy folder** ticked (works on a copy, originals safe),
hit **Run** for a dry-run, review the log, then tick **Apply** and Run again. **Edit Tags**
opens your tag list in-app.

**CLI**:
```bash
:: LM Studio: load a VL model, Start Server (localhost:1234)
docsort "C:\AcademicsCOPY"                 :: dry-run (preview)
docsort "C:\AcademicsCOPY" --apply         :: rename in place
docsort "C:\AcademicsCOPY" --copy --apply  :: tag a copy, originals untouched
docsort "C:\AcademicsCOPY" --move "C:\Archive\Academics" --apply   :: sort into tree
```

By default, files the model is unsure about (`99UNS`) are swept into a `misc\` subfolder of the
working directory (turn off with `--no-misc`).

---

## How tagging works — TAGS.md + system_prompt.md

docsort builds the model's prompt from **two files** every run:

| File | Role |
|---|---|
| **`TAGS.md`** | **The vocabulary — your editable single source of truth.** Lists the valid STREAM, SUBJECT, and TYPE codes. The codes are injected into the prompt, *and* the parser only accepts these codes (anything off-list → `99UNS`). |
| **`system_prompt.md`** | **The rules — how to decide.** The `<SYSTEM>` block holds the instructions and worked examples; `{{STREAMS}}`/`{{SUBJECTS}}`/`{{TYPES}}` placeholders are filled from `TAGS.md` at runtime. |

So `TAGS.md` controls **what the labels are**; `system_prompt.md` controls **how the model picks
between them**. Each file is read fresh per run — edit, save, re-run.

Per file the model gets two messages — the filled system prompt, and a user message with
`Filename / Folder / Text(≤4000 chars) [+ rendered page image]`. It must reply with one line:
`STREAM SUBJECT TYPE CONF` (e.g. `CW 12EMAG notes high`). Settings: `temperature=0`, `max_tokens=24`.

### Active tags (current `TAGS.md`)
- **STREAMS (6)** — `CW GATE PROJ RES REC REF`
- **SUBJECTS (19)** — `00MM 01CA 02SEMI 03PN 04BJT 05MOS 06OPAMP 07ANLG 08DIG 09SNS 10CTRL 11COMM 12EMAG 13TOOLS 90HUM 91PHY 92CHEM` + `NA` + `99UNS`
- **TYPES (11)** — `notes pyq book slides assignment lab report datasheet syllabus solution misc`

The filename prefix uses **STREAM-SUBJECT only** (`[CW-08DIG]`); TYPE + CONF go to the log.

### Edit / expand / refine the output
- **Add or rename a tag:** GUI **Edit Tags**, or `docsort --edit-tags`. Inside a ```` ```tags ```` block,
  the **first token on a line is the code**, the rest is a description. Add a `SUBJECT` line, save,
  re-run — it's instantly a valid label. (Your copy survives reinstalls.)
- **Sharpen decisions:** edit the rules/examples in `system_prompt.md` — add a worked example for a
  case the model gets wrong, or a rule (e.g. "lab manuals → TYPE lab"). Examples move accuracy most.
- **Let it self-grow:** when the model meets a clear recurring subject that isn't listed, it answers
  `99UNS PROPOSE:<LABEL>` → file written `[STREAM-~LABEL]` (the `~` = pending, not auto-moved).
  `docsort --review` tallies proposals; promote a frequent one into `TAGS.md`, then `--retag` re-files
  those `~LABEL` files under the new real code.
- **Read fewer/more pages, change render DPI:** `min_text` / `deep_pages` / `deep_cap` / `dpi` in
  `config.json`.
- **Use a stronger model** for hard sets (a 7B/8B VL), or turn on the Claude frontier (below).

---

## Where settings live

On first run, docsort seeds a per-user data dir from the bundled templates:

```
%APPDATA%\docsort\          (Windows)   ~/.docsort/   (other)
├── config.json          model host, named hosts/locations, archive root, options
├── TAGS.md              your editable tag vocabulary
└── system_prompt.md     model rules/examples (tags injected from TAGS.md)
```

Edit `config.json` to point at a non-default LM Studio host, name folders/locations, or set
`archive_root` for `--move @archive`. CLI flags override the config.

---

## Optional: Claude frontier — auth

For the handful of files the local model can't decide (`99UNS`), docsort can ask **Claude**
for a verdict. This uses the **Claude Code CLI on your Claude subscription — no API key, no
per-token cost.** It is bound to the **haiku** model (standard context, covered by the sub).

**Set it up once:**
1. Install Claude Code: see <https://claude.com/claude-code> (CLI). Confirm it's on PATH:
   ```bash
   claude --version
   ```
2. Log in to your Claude account (opens a browser the first time):
   ```bash
   claude            # follow the login prompt, then exit
   ```
3. Use it:
   ```bash
   docsort "C:\AcademicsCOPY" --frontier claude
   ```
   or pick **claude** in the GUI's *Frontier on hard 99UNS* dropdown, or set
   `"frontier": "claude"` in `config.json` to make it the default.

**If you don't have it / don't want it:** the frontier is **off by default** — docsort is fully
local. If you pass `--frontier claude` but the `claude` command isn't on PATH (or isn't logged in),
docsort prints a notice and **continues locally** instead of failing. Those few `99UNS` files just
stay `[STREAM-99UNS]` and get swept to `misc\` for you to hand-tag. Nothing ever leaves your machine.
There is **no OpenAI/ChatGPT backend** — a ChatGPT web subscription is not an API, so it can't be
driven programmatically.

---

## How it classifies (tiers)

`TEXT (2 pages)` → `ESCALATE (5 pages on 99UNS)` → `VISION (render page, +page 3)` →
`FRONTIER (claude, optional)` → `FILENAME (last resort)`. The `source` column in the run log
tells you which tier decided each file. See **GUIDE.md** for the full runbook.

## Pipeline position
`dupeGuru hashed-dedup` → **docsort tag** → **docsort move** → handle GATE/PROJ/RES folders apart.
Run dedup FIRST so the model never reads duplicate copies.

## Files
| Path | What |
|---|---|
| `docsort/cli.py` | the tagger + mover (CLI, `docsort`) |
| `docsort/gui.py` | the dark GUI (`docsort-gui`) |
| `docsort/config.py` | config + per-user file resolution |
| `docsort/data/` | bundled templates: `TAGS.md`, `system_prompt.md`, `config.example.json` |
| `run.bat` | cmd/PowerShell launcher (uses repo `.venv`) |
| `GUIDE.md` | detailed runbook — tiers, escalation, backends, flags |
| `TROUBLESHOOTING.md` | host/firewall/port 1234 and common fixes |
| `CHANGELOG.md` | version history |
| `docs/MODEL-GUIDE.md` | model shortlist + LM Studio tuning + benchmark method |
| `docs/ROADMAP.md` | shipped vs. planned vs. separate-project work |
| `docs/design/` | design notes: `council.md`, `taxonomy-generator.md`, `gui-vision.md` |

Edit tags in **`TAGS.md`** only (via **Edit Tags** / `--edit-tags`) — changes flow to both the
script and the model.
