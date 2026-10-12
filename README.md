# YouTube Transcript Summarizer

[![Powered by Supadata](https://supadata.ai/badge/powered-by-supadata-light.svg)](https://supadata.ai/r/HHD1MQYC)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A small Python CLI that turns any YouTube video into a short summary:

1. Fetches the video's **native transcript** in the language you ask for, using the official [Supadata](https://supadata.ai/r/HHD1MQYC) Python SDK (`supadata`).
2. Checks that the transcript really came back **in that language**, is **not empty** and is **not too long**. Otherwise it skips the video instead of wasting tokens.
3. Summarizes it with **Google Gemini** through the official `google-genai` SDK.

Built for [iadots.com](https://www.iadots.com), a portal that collects videos about AI, agents, robotics and humanoids in 4 languages. There, the same flow runs automatically for every new video and the summary is published next to it.

## How it works

```
YouTube URL ──► Supadata transcript (mode=native, lang=xx, text=true)
                    │
                    ├─ async job? ──► poll /transcript/{jobId} until completed
                    │
                    ├─ returned lang ≠ requested?  ──► skip (language_mismatch)
                    ├─ empty?                       ──► skip (empty_transcript)
                    ├─ larger than MAX bytes?       ──► skip (too_long)
                    ▼
               Gemini (google-genai) ──► summary (intro + 3-5 bullet points)
```

`mode="native"` only returns captions that already exist on YouTube, so you never pay for AI-generated transcripts by accident.

## Setup

Requirements: Python 3.9+, a [Supadata API key](https://supadata.ai/r/HHD1MQYC) (free tier available) and a [Gemini API key](https://aistudio.google.com/apikey).

```bash
git clone https://github.com/matheuslacerdacontas/youtube-transcript-summarizer.git
cd youtube-transcript-summarizer

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # then put your keys in .env
```

Environment variables (read from the shell or from `.env`):

| Variable | Required | Description |
| --- | --- | --- |
| `SUPADATA_API_KEY` | yes | Your Supadata API key |
| `GEMINI_API_KEY` | yes (unless `--transcript-only`) | Your Gemini API key |
| `GEMINI_MODEL` | no | Gemini model, default `gemini-3.8-flash` |
| `MAX_TRANSCRIPT_BYTES` | no | Skip transcripts bigger than this, default `180000` |

## Usage

```bash
# Summarize an English video
python summarize.py "https://www.youtube.com/watch?v=VIDEO_ID" --lang en

# Portuguese video, summary in English
python summarize.py "https://www.youtube.com/watch?v=VIDEO_ID" --lang pt --summary-lang en

# Just the transcript, no Gemini call
python summarize.py "https://youtu.be/VIDEO_ID" --lang es --transcript-only

# Machine-readable output (handy for automations)
python summarize.py "https://www.youtube.com/watch?v=VIDEO_ID" --lang en --json
```

All options: `python summarize.py --help`

Exit codes: `0` success, `1` API/network error, `2` missing configuration, `3` video skipped (no transcript, wrong language, empty or too long).

### Example output

> **⚠️ Placeholder:** the text below only illustrates the format. It is not a real summary of a real video.

```json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "status": "ok",
  "requested_lang": "en",
  "transcript_lang": "en",
  "transcript_chars": 18342,
  "model": "gemini-3.8-flash",
  "summary": "<PLACEHOLDER> One-paragraph overview of the video...\n- Key takeaway 1\n- Key takeaway 2\n- Key takeaway 3",
  "detail": null
}
```

## Use it as a library

```python
from summarize import main
main(["https://www.youtube.com/watch?v=VIDEO_ID", "--lang", "en", "--json"])
```

## Português (resumo)

CLI em Python que pega a **transcrição nativa** de um vídeo do YouTube no idioma original usando o SDK oficial da [Supadata](https://supadata.ai/r/HHD1MQYC), confere se o idioma devolvido é o pedido, ignora transcrições vazias ou longas demais e gera um **resumo com o Gemini** (`google-genai`). É o mesmo fluxo que roda automaticamente no [iadots.com](https://www.iadots.com) para cada vídeo novo.

```bash
pip install -r requirements.txt
cp .env.example .env   # coloque SUPADATA_API_KEY e GEMINI_API_KEY
python summarize.py "https://www.youtube.com/watch?v=VIDEO_ID" --lang pt
```

## Powered by Supadata

[![Powered by Supadata](https://supadata.ai/badge/powered-by-supadata-light.svg)](https://supadata.ai/r/HHD1MQYC)

Transcripts come from [Supadata](https://supadata.ai/r/HHD1MQYC), an API for YouTube, TikTok, Instagram, X and web content. It has transcripts, metadata and web scraping, plus an official SDK for Python (`pip install supadata`) and JavaScript (`@supadata/js`).

Get your API key: **https://supadata.ai/r/HHD1MQYC**

> **Disclosure:** the Supadata links in this README are my personal referral links. If you sign up through them, I may get account credits. It costs you nothing extra.

## License

[MIT](LICENSE) © 2026 Matheus Lacerda · Built for [iadots.com](https://www.iadots.com)
