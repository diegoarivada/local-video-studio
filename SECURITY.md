# Security

## Reporting a vulnerability

Please report security issues privately through GitHub's **Report a vulnerability** button on the Security tab, not in a public issue. I'll reply within a week.

## How the tool is built

- **Secrets:** your Pixabay key lives in `.env`, which is git-ignored. Error messages never print the request URL, because the key travels in it.
- **Model output is data.** The topic and your notes are wrapped as untrusted input in every prompt. Model text is only ever spoken, captioned, or written to files, never run.
- **Downloads:** only from `pixabay.com` / `cdn.pixabay.com`, capped at 200 MB each, and cached under `out/.cache`. Output filenames are slugified, so a model-written title can't escape the `out/` folder.
- **Local by default:** scripts come from Ollama on `127.0.0.1`, and the voice runs on your machine. Nothing is uploaded anywhere.
- **Voice cloning is opt-in and gated.** `--voice` refuses to run without `--i-own-this-voice`. Chatterbox also adds an inaudible watermark to everything it generates.
