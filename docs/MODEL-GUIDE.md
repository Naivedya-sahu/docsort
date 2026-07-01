# docsort — model + tuning guide (LM Studio stack)

Goal: a more accurate/faster VL model for document reading + steerable tagging, on your
hardware (laptop 3050 4GB primary; desktop ~8GB secondary), staying in the LM Studio GGUF
stack. You measured ~40 tok/s on Qwen3-VL-8B / Qwen2.5-VL-7B.

**As of v0.13.0, model choice only matters for VISION-tier files** (scanned/handwritten, no
extractable text). Non-vision files classify via the model-free EMBED tier — no model loaded,
no tokens spent, regardless of which model is running in LM Studio. Everything below (model
pick, LM Studio tuning, benchmarking) is about the VISION tier specifically, not the whole
pipeline anymore. If your ground-truth set is mostly non-vision files, benchmarking against it
will show ~0 tok/s and near-instant wall time — that's correct behavior, not a broken run.

## TL;DR — what to download
Keep the **Qwen-VL family** — it's SOTA-open for OCR-in-context *and* stays promptable (it
classifies, not just transcribes). Prefer **Unsloth Dynamic (UD) GGUFs** — better accuracy per bit.

| Tier | Model (GGUF) | Quant to grab | Fits | Why |
|---|---|---|---|---|
| **Primary (laptop 4GB)** | **Qwen3-VL-4B** (Unsloth UD) | `Q4_K_XL` / `Q5_K_M` | ~3–4 GB w/ small ctx | best accuracy that fits 4GB; fast |
| **Quality (desktop 8GB)** | **Qwen3-VL-8B** (Unsloth UD) | `Q4_K_XL` | ~6–7 GB | your current best; SOTA OCR/doc |
| **Try as challenger** | **InternVL3-8B** or **MiniCPM-V 2.6 (8B)** | `Q4_K_M` | ~6–7 GB | strong doc/OCR; benchmark vs Qwen3 |

Notes:
- **Hermes is text-only** (Nous) — not vision. Not usable as the main backend here; skip for the VL pass.
- **Dedicated OCR models** (GOT-OCR2, dots.ocr, PaddleOCR-VL, Nanonets-OCR) transcribe but aren't
  chat-steerable for *your taxonomy* — you correctly rejected that path. Qwen-VL does the reading inline.
- Get GGUFs from `unsloth/Qwen3-VL-*-Instruct-GGUF` on Hugging Face (search inside LM Studio).

## LM Studio config tuning (this matters more than you'd think)
docsort sends only ~4000 chars of text + ONE rendered page, and asks for a 1-line answer
(`max_tokens=24`). So you do **not** need a big context window — that just wastes VRAM/KV cache.

- **Context length: 8192** (not 32k). Frees VRAM → more GPU layers → faster. docsort's payload fits easily.
- **GPU offload:** push as many layers to GPU as fit 4GB; rest to CPU/RAM. For 4B Q4 most layers fit.
- **Flash Attention: ON.** **KV cache quant: Q8** — both cut VRAM, keep quality.
- **Keep model loaded** (LM Studio "keep in memory") so per-file latency is just inference.
- Leave temperature 0 (docsort sets it). Leave `max_tokens` (docsort sets 24).

### docsort-side knobs (config.json)
- `dpi` (page render): **120 → 150–200** for dense/handwritten scans = sharper OCR, a few more
  image tokens. Bump only if vision-tier accuracy is weak.
- `deep_pages` / `deep_cap`: raise if books bury the topic past page 5.
- `min_text`: lower (e.g. 40) to push more thin-text PDFs to the model-free EMBED tier instead of
  the model-based VISION tier — fewer files touch the model at all.

## How to benchmark (clean comparison)
1. Build a **ground-truth set that's specifically scanned/handwritten PDFs** (VISION-tier
   material) — a mixed set will mostly hit EMBED and never touch the model you're testing.
2. For each candidate model: load in LM Studio, run `docsort "<set>" --copy --vision` (dry-run-ish),
   then compare the run journal/report labels to your ground truth → **accuracy %**, plus **tok/s**
   and **wall time** from the PROGRESS stats.
3. Pick the best accuracy-at-acceptable-speed. The Phase-4 report/stats (coming) makes this a
   one-glance comparison.

Rule of thumb: on 4GB, **Qwen3-VL-4B UD Q4_K_XL @ 8k ctx** is the sweet spot; move to 8B on the
desktop when accuracy on hard sets matters more than speed.
