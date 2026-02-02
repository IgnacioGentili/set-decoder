import os
import re
import shutil
import tempfile
import urllib.parse
from difflib import SequenceMatcher
from typing import Optional

import requests
import yt_dlp
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydub import AudioSegment

app = FastAPI(title="Set Decoder API")

# CORS para el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Config
AUDD_API_TOKEN = "42d4de912f5b46ba837f61ed431587bc"
SEGMENT_DURATION = 30  # segundos entre cada sample
SAMPLE_LENGTH = 15  # segundos de audio para identificar

# Storage de jobs en memoria (para demo)
jobs = {}


class SetRequest(BaseModel):
    url: str
    segment_duration: Optional[int] = 30


class Track(BaseModel):
    timestamp: str
    timestamp_seconds: int
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    spotify_url: Optional[str] = None
    apple_music_url: Optional[str] = None
    deezer_url: Optional[str] = None
    status: str = "identified"


def clean_youtube_url(url: str) -> str:
    """Limpia la URL de YouTube removiendo parámetros de playlist/radio"""
    parsed = urllib.parse.urlparse(url)

    # Si es YouTube, extraer solo el video ID
    if "youtube.com" in parsed.netloc or "youtu.be" in parsed.netloc:
        query_params = urllib.parse.parse_qs(parsed.query)

        # Obtener el video ID
        video_id = query_params.get("v", [None])[0]

        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"

        # Para youtu.be/VIDEO_ID
        if "youtu.be" in parsed.netloc:
            video_id = parsed.path.strip("/")
            return f"https://www.youtube.com/watch?v={video_id}"

    return url


def format_timestamp(seconds: int) -> str:
    """Convierte segundos a formato MM:SS o HH:MM:SS"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def normalize_track_name(artist: str, title: str) -> str:
    """Normaliza el nombre para comparar tracks similares"""
    if not artist or not title:
        return ""

    # Convertir a minúsculas
    artist = artist.lower().strip()
    title = title.lower().strip()

    # Remover contenido entre paréntesis y corchetes (remixes, edits, etc)
    title = re.sub(r"\([^)]*\)", "", title)
    title = re.sub(r"\[[^\]]*\]", "", title)

    # Remover palabras comunes de remixes
    remove_words = [
        "remix",
        "edit",
        "bootleg",
        "mix",
        "version",
        "extended",
        "original",
        "radio",
        "club",
        "dub",
        "instrumental",
        "vip",
        "flip",
        "rework",
        "remaster",
        "remastered",
        "feat",
        "ft",
        "featuring",
        "prod",
        "produced",
    ]
    for word in remove_words:
        title = re.sub(rf"\b{word}\b", "", title)
        artist = re.sub(rf"\b{word}\b", "", artist)

    # Remover caracteres especiales y espacios extra
    title = re.sub(r"[^\w\s]", "", title)
    artist = re.sub(r"[^\w\s]", "", artist)
    title = " ".join(title.split())
    artist = " ".join(artist.split())

    return f"{artist} - {title}"


def tracks_are_similar(
    track1_artist: str, track1_title: str, track2_artist: str, track2_title: str
) -> bool:
    """Compara si dos tracks son esencialmente el mismo tema"""
    norm1 = normalize_track_name(track1_artist, track1_title)
    norm2 = normalize_track_name(track2_artist, track2_title)

    if not norm1 or not norm2:
        return False

    # Si son exactamente iguales después de normalizar
    if norm1 == norm2:
        return True

    # Si tienen alta similitud (>80%)
    similarity = SequenceMatcher(None, norm1, norm2).ratio()
    if similarity > 0.8:
        return True

    # Comparar solo el título (a veces el artista varía)
    title1 = norm1.split(" - ")[-1] if " - " in norm1 else norm1
    title2 = norm2.split(" - ")[-1] if " - " in norm2 else norm2

    title_similarity = SequenceMatcher(None, title1, title2).ratio()
    if title_similarity > 0.85:
        return True

    return False


def download_audio(url: str, output_path: str) -> dict:
    """Descarga audio de YouTube/SoundCloud"""
    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "outtmpl": output_path,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,  # Solo descargar el video, no la playlist
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return {
            "title": info.get("title", "Unknown"),
            "duration": info.get("duration", 0),
            "uploader": info.get("uploader", "Unknown"),
        }


def identify_segment(audio_path: str) -> dict:
    """Identifica un segmento de audio usando AudD API"""
    try:
        with open(audio_path, "rb") as f:
            data = {"api_token": AUDD_API_TOKEN, "return": "spotify,apple_music,deezer"}
            files = {"file": f}
            response = requests.post(
                "https://api.audd.io/", data=data, files=files, timeout=30
            )
            result = response.json()

            # Log para debugging
            print(f"[AudD] Status: {result.get('status')}")
            if result.get("status") == "error":
                print(f"[AudD] Error: {result.get('error')}")
                return {"found": False, "error": result.get("error")}

            if result.get("status") == "success" and result.get("result"):
                track = result["result"]
                return {
                    "found": True,
                    "title": track.get("title"),
                    "artist": track.get("artist"),
                    "album": track.get("album"),
                    "spotify_url": (
                        track.get("spotify", {}).get("external_urls", {}).get("spotify")
                        if track.get("spotify")
                        else None
                    ),
                    "apple_music_url": (
                        track.get("apple_music", {}).get("url")
                        if track.get("apple_music")
                        else None
                    ),
                    "deezer_url": (
                        f"https://www.deezer.com/track/{track.get('deezer', {}).get('id')}"
                        if track.get("deezer", {}).get("id")
                        else None
                    ),
                }
            return {"found": False}
    except Exception as e:
        print(f"[AudD] Exception: {e}")
        return {"found": False, "error": str(e)}


def process_set(job_id: str, url: str, segment_duration: int = 30):
    """Procesa un set completo"""
    temp_dir = tempfile.mkdtemp()

    try:
        jobs[job_id]["status"] = "downloading"
        jobs[job_id]["message"] = "Descargando audio..."

        # Descargar audio
        audio_base = os.path.join(temp_dir, "audio")
        info = download_audio(url, audio_base)
        audio_file = audio_base + ".mp3"

        # Verificar que el archivo existe
        if not os.path.exists(audio_file):
            raise Exception(f"Audio file not found: {audio_file}")

        jobs[job_id]["set_info"] = info
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["message"] = "Procesando audio..."

        # Cargar audio
        audio = AudioSegment.from_mp3(audio_file)
        duration_seconds = len(audio) // 1000

        jobs[job_id]["total_duration"] = duration_seconds
        jobs[job_id][
            "message"
        ] = f"Identificando tracks (0/{duration_seconds // segment_duration})..."

        tracks = []
        last_track = None
        consecutive_not_found = 0

        # Procesar cada segmento
        for i, start_time in enumerate(range(0, duration_seconds, segment_duration)):
            jobs[job_id]["current_position"] = start_time
            jobs[job_id][
                "message"
            ] = f"Identificando tracks ({i + 1}/{duration_seconds // segment_duration + 1})..."

            # Extraer segmento
            start_ms = start_time * 1000
            end_ms = min(start_ms + (SAMPLE_LENGTH * 1000), len(audio))
            segment = audio[start_ms:end_ms]

            # Guardar segmento temporal
            segment_path = os.path.join(temp_dir, f"segment_{i}.mp3")
            segment.export(segment_path, format="mp3")

            # Identificar
            result = identify_segment(segment_path)

            # Limpiar archivo temporal
            os.remove(segment_path)

            if result.get("found"):
                current_artist = result.get("artist", "")
                current_title = result.get("title", "")

                # Verificar si es similar al último track
                is_similar = False
                if last_track and last_track.get("status") == "identified":
                    is_similar = tracks_are_similar(
                        last_track.get("artist", ""),
                        last_track.get("title", ""),
                        current_artist,
                        current_title,
                    )

                if not is_similar:
                    new_track = {
                        "timestamp": format_timestamp(start_time),
                        "timestamp_seconds": start_time,
                        "title": current_title,
                        "artist": current_artist,
                        "album": result.get("album"),
                        "spotify_url": result.get("spotify_url"),
                        "apple_music_url": result.get("apple_music_url"),
                        "deezer_url": result.get("deezer_url"),
                        "status": "identified",
                    }
                    tracks.append(new_track)
                    last_track = new_track
                    consecutive_not_found = 0

            else:
                consecutive_not_found += 1

                if consecutive_not_found >= 2 and (
                    not last_track or last_track.get("status") != "not_found"
                ):
                    new_track = {
                        "timestamp": format_timestamp(
                            max(0, start_time - segment_duration)
                        ),
                        "timestamp_seconds": max(0, start_time - segment_duration),
                        "title": None,
                        "artist": None,
                        "status": "not_found",
                    }
                    tracks.append(new_track)
                    last_track = new_track

            jobs[job_id]["tracks"] = tracks

        jobs[job_id]["status"] = "completed"
        jobs[job_id]["message"] = "Completado!"

    except Exception as e:
        print(f"[Error] {e}")
        jobs[job_id]["status"] = "error"
        jobs[job_id]["message"] = f"Error: {str(e)}"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@app.post("/api/identify")
async def identify_set(request: SetRequest, background_tasks: BackgroundTasks):
    """Inicia la identificación de un set"""
    import uuid

    job_id = str(uuid.uuid4())

    # Limpiar la URL (remover parámetros de playlist/radio)
    clean_url = clean_youtube_url(request.url)

    jobs[job_id] = {
        "status": "queued",
        "message": "En cola...",
        "url": clean_url,
        "tracks": [],
        "set_info": None,
        "total_duration": 0,
        "current_position": 0,
    }

    background_tasks.add_task(
        process_set, job_id, clean_url, request.segment_duration or 30
    )

    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    """Obtiene el estado de un job"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
