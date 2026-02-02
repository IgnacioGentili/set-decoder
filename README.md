# Set Decoder

[![Watch Demo](https://cdn.loom.com/sessions/thumbnails/4285eb6263dd40778ccdebed68f019ae-c30b057baf761225-full-play.gif)](https://www.loom.com/share/4285eb6263dd40778ccdebed68f019ae)

Identify tracks in DJ sets automatically using audio recognition. Paste a YouTube or SoundCloud URL and get a full tracklist with streaming links.

## How It Works

1. Downloads audio from YouTube/SoundCloud using yt-dlp
2. Splits the audio into segments (configurable interval)
3. Sends each segment to AudD API for recognition
4. Returns identified tracks with Spotify, Apple Music, and Deezer links

## Features

- YouTube and SoundCloud URL support
- Configurable sampling frequency (15-60 seconds)
- Real-time progress updates
- Direct links to streaming platforms
- Export tracklist as JSON
- Copy-to-clipboard functionality

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python, FastAPI, yt-dlp, pydub |
| Frontend | HTML, Tailwind CSS, Vanilla JS |
| Audio Recognition | AudD API |

## Quick Start

### Prerequisites
```bash
# Install ffmpeg (required for audio processing)
brew install ffmpeg  # macOS
# or: sudo apt install ffmpeg  # Linux
```

### Installation
```bash
# Clone the repo
git clone https://github.com/IgnacioGentili/set-decoder.git
cd set-decoder

# Install Python dependencies
cd backend
pip install -r requirements.txt
```

### Run

**Option 1: Use start script**
```bash
chmod +x start.sh
./start.sh
```

**Option 2: Run manually**

Terminal 1 - Backend:
```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

Terminal 2 - Frontend:
```bash
cd frontend
python3 -m http.server 3000
```

Open **http://localhost:3000** in your browser.

## Usage

1. Paste a YouTube or SoundCloud URL of a DJ set
2. Choose sampling frequency (30 sec recommended for balance of accuracy vs API calls)
3. Click "Identify Set"
4. Watch real-time progress as tracks are identified
5. Click streaming icons to find tracks on Spotify/Apple Music/Deezer
6. Copy tracklist or export as JSON

## API Limits

AudD free tier: 300 requests/month

| Set Length | 30s Sampling | Requests Used |
|------------|--------------|---------------|
| 1 hour | 120 samples | 120 requests |
| 2 hours | 240 samples | 240 requests |

You can process ~2-3 one-hour sets per month on the free tier.

## Project Structure
```
set-decoder/
├── backend/
│   ├── main.py           # FastAPI app, audio processing, AudD integration
│   └── requirements.txt  # Python dependencies
├── frontend/
│   └── index.html        # Single-page UI
├── start.sh              # Convenience script to run both servers
└── README.md
```

## License

MIT
