# docsort — Guide

## 1. What the LLM receives (per file)
Two messages:
- **SYSTEM** = the `<SYSTEM>` block of `system_prompt.md` with `{{STREAMS}}/{{SUBJECTS}}/{{TYPES}}`
  filled from `TAGS.md` (single source). Same every call.
- **USER** = per file:
  - *text tier:* `Filename / Folder / Text(<=4000 chars) / Answer (STREAM SUBJECT TYPE CONF):`
  - *vision tier:* same + the page rendered to PNG.
  - *filename tier:* same with empty text.
Settings: `temperature=0`, `max_tokens=24`. Reply is one line, e.g. `CW 12EMAG notes high`
(or with a discovery: `CW 99UNS notes high PROPOSE:THERMO`).

## 2. Classification tiers (in order)
1. **TEXT** — first 2 pages; if ≥80 chars → text model.
2. **ESCALATE** — if SUBJECT is `99UNS` on a PDF, re-read **up to 5 pages** (past cover/preface/TOC)
   and retry → `source=text5`.
3. **VISION** — no extractable text → render page 1 → vision model; still `99UNS`? page 3 → `vision3`.
4. **FRONTIER** *(optional)* — if still `99UNS` and `--frontier` set, ask a frontier model → `source=frontier:<be>`.
5. **FILENAME** — last resort.
Trust order: `text > text5 > vision > vision3 > frontier > filename` (the `source` column).

## 3. The tag scheme — known + discovered
- **Prefix `[STREAM-SUBJECT]`** is the only thing added to the name. STREAM peels GATE/PROJ/RES/REC
  from CW; SUBJECT unifies coursework by topic. TYPE/CONF go to the log only.
- **Known tags** live in `TAGS.md` (6 streams · 17 subjects + NA/99UNS · 11 types). The model is
  constrained to these → mutually exclusive, decisive.
- **Discovered tags**: a coherent subject not in the list → `99UNS PROPOSE:<LABEL>` → file written
  `[STREAM-~LABEL]` (the `~` = pending review, **not auto-moved**). `--review` tallies them; promote a
  recurring one into `TAGS.md`, then `--retag` re-files the `~LABEL` files into the new real code.

## 4. Full workflow
```
0. DEDUP         dupeGuru: Scan Type Folders, then Contents; Re-Prioritize (suffix down);
                 Move Marked to quarantine. Kill copies BEFORE tagging.
1. CONFIG        %APPDATA%\docsort\config.json: host -> your LM Studio; locations -> folder(s)
2. TAG dry-run   docsort --location academics            (or a raw path)
                 -> review _doc_handler_log.csv   (or: --review -> TAG-REVIEW.md)
3. TAG apply     docsort --location academics --copy --apply    (--copy keeps originals safe)
4. (optional)    promote any ~PROPOSE tags via --edit-tags, then:  ... --retag --apply
5. MOVE          docsort --location academics --move @archive          (dry-run)
                 docsort --location academics --move @archive --apply
6. SPECIAL       handle <archive>/{GATE,PROJ,RES,REC} folders separately
```
GUI equivalent: `docsort-gui` (or `run.bat`) — folder picker + the same toggles.

## 5. Flags
| Flag | Purpose |
|---|---|
| `--location NAME` / `root` | folder from config, or a raw path |
| `--host NAME\|URL` | model endpoint (config `hosts` name or URL) |
| `--vision [--vision-model M]` | enable image tier for no-text PDFs (config default: on) |
| `--copy` | copy the folder to `<name>COPY` and tag the copy (originals untouched) |
| `--apply` | rename (default is dry-run) |
| `--misc` / `--no-misc` | sweep `99UNS` files into a `misc\` subfolder (**default ON**) |
| `--move DEST` / `--move @archive` | relocate prefixed files into DEST/STREAM/SUBJECT |
| `--edit-tags` | open your `TAGS.md` in an editor, then exit |
| `--review` | aggregate log → TAG-REVIEW.md (offline) |
| `--retag` | re-classify already-prefixed files (after tuning/promoting) |
| `--frontier claude\|cmd` | hard-99UNS fallback (see §6); `claude` is bound to haiku |
| `--backend local` | main backend |

## 6. Backends (all key-free)
- **local** — LM Studio (default). Free, no key. The recommended main backend.
- **frontier claude** — Claude Code CLI on your **Claude subscription, NO API key**. Bound to the
  **haiku** model (standard context, sub-covered). Slower (~30 s/file) — use only for hard cases.
- **frontier cmd** — `--frontier-cmd "<shell template>"`, prompt piped via stdin → wire ANY local/
  sub CLI without a key.
- *(No OpenAI/ChatGPT backend — the API path was removed; a ChatGPT web sub is not an API.)*

## 7. Tuning
- Add/edit tags in **`TAGS.md`** only — via **Edit Tags** (GUI) or `docsort --edit-tags`.
  Changes flow to both the script and the model prompt. Sharpen rules/examples in `system_prompt.md`.
- User files live in `%APPDATA%\docsort\` (Windows) / `~/.docsort/`. `config.json` holds
  endpoints, named hosts, locations, archive_root, and `min_text/deep_pages/dpi`. Reinstalling never
  overwrites your edited copies.
- **Models auto-resolve for any user:** if the model id in config isn't loaded in LM Studio, the app
  picks whatever VL model *is* loaded (see the `[model] ->` / `[vision] ->` line). You rarely need to
  set the exact id.

## 8. Reviewing & reversibility
- `--review` → TAG-REVIEW.md: distribution, proposed (`~`) tags, low-confidence list.
- Eyeball `conf=low`, `source=filename/vision/frontier`, `subject=99UNS`.
- Renames reversible via the log `old`/`new`; moves via `_move_log.csv` (`from`/`to`).

## 9. Troubleshooting
| Symptom | Fix |
|---|---|
| Server unreachable / hangs | start LM Studio; enable LAN + firewall TCP 1234 (see TROUBLESHOOTING.md) |
| Every file `99UNS` | weak model — use a 7B/8B vision model, or `--frontier claude` |
| Configured model not used | not loaded; auto-resolve picked a loaded one (see `[model] ->` line) |
| PDFs skipped | `pip install pymupdf` (bundled as a dependency; reinstall if missing) |
| `.docx/.pptx` skipped | `pip install "docsort[office]"` |
| `.doc` filename-only | needs Word + `pip install "docsort[doc]"` (pywin32), or convert .doc→.docx |
| frontier claude empty / not found | install Claude Code, run `claude` once to log in; it uses `--model haiku` |
| GUI won't start | needs Tkinter (ships with standard CPython on Windows; on Linux `apt install python3-tk`) |
