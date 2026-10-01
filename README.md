# SnipScribe Worker

The background worker for [SnipScribe](https://github.com/Mostafa-Safwat/snipscribe-app), a web app that turns YouTube videos into short summaries with key points.

The worker takes pending summaries from SnipScribe's PostgreSQL database one at a time, checking again 60 seconds after each one. For each summary it:

1. Downloads the video's audio with [pytubefix](https://github.com/JuanBindez/pytubefix)
2. Transcribes it with [OpenAI Whisper](https://github.com/openai/whisper) (`large` model)
3. Summarizes the transcript with Qwen 3 running locally in [Ollama](https://ollama.com), as an overview paragraph plus key points in the requested language (English or Arabic)
4. Saves the summary, marks it completed and queues a "summary is ready" email, which the app sends

Everything runs on your own machine, so no paid AI APIs are involved.

## Requirements

- Python 3.12, ffmpeg and Ollama
- SnipScribe's database running: `docker compose up -d` in [snipscribe-app](https://github.com/Mostafa-Safwat/snipscribe-app)

PyTorch is installed CPU-only, so no GPU is needed. Whisper's `large` model is slow on a CPU, especially for long videos.

## Setup

```sh
sudo apt-get install -y python3-venv ffmpeg

# Ollama and the summarization model
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3

# Python dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running

```sh
source venv/bin/activate
python app/app.py
```

- The first transcription downloads the Whisper `large` model (about 3 GB).
- No YouTube login is needed. pytubefix passes YouTube's bot check using the Node.js it bundles.
- The database connection (`localhost:5432`, database `snipscribe`) is set in `app/app.py` and matches snipscribe-app's `docker-compose.yml`.
- If Ollama already runs as a system service, the worker prints `address already in use` when it tries to start its own. That message is harmless: the summary still goes to the running service.

## License

[MIT](LICENSE)
