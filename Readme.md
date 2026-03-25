# Zoro Hex — Discord Uploader

**GitHub:** https://github.com/abdoabdalkhalk/Dis-Exp

A lightweight web tool to upload files and media directly to any Discord channel via URL or local file — no bots, no OAuth, just a clean interface.

---

## Features

- Upload multiple files in a single Discord message
- Supports direct URLs (streamed, zero temp file) and local device files
- Real-time upload progress with job tracking
- Optional custom message with Discord markdown support
- Credentials saved locally in your browser
- Zero-copy streaming architecture — remote files are piped directly to Discord

---

## Stack

- **Backend** — Python / Flask
- **Frontend** — Vanilla HTML, CSS, JS

---

## Setup

```bash
git clone https://github.com/abdoabdalkhalk/Dis-Exp.git
cd zoro-hex
pip install flask requests
python app.py
```

Then open `http://localhost:5000` in your browser.

---

## Usage

1. Paste your Discord **user token** and target **channel ID**
2. Add one or more files (URL or from device)
3. Optionally write a message
4. Hit **Upload to Discord**

---

## Notes

- This tool uses your **user token** directly — use it responsibly and never share it
- File size limits are enforced by Discord (25 MB for standard accounts)
- Credentials are stored only in your browser's `localStorage`

---

## License

MIT — see [LICENSE](./LICENSE)
