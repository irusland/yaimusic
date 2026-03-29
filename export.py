import csv
import os
import time

from dotenv import load_dotenv
from tqdm import tqdm
from yandex_music import Client
from yandex_music.exceptions import TimedOutError

load_dotenv()

TOKEN = os.environ.get("YANDEX_MUSIC_TOKEN")

client = Client(TOKEN).init()
liked = client.users_likes_tracks()

fields = [
    "id",
    "title",
    "artists",
    "album",
    "album_id",
    "year",
    "genre",
    "duration_ms",
    "added_at",
    "available",
    "content_warning",
]


def fetch_track_with_retry(track_short, retries=5, delay=3):
    for attempt in range(retries):
        try:
            return track_short.fetch_track()
        except TimedOutError:
            if attempt + 1 == retries:
                raise
            time.sleep(delay * (attempt + 1))


with open("yandex_music.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()

    for track_short in tqdm(liked, desc="Экспорт треков"):
        track = fetch_track_with_retry(track_short)
        album = track.albums[0] if track.albums else None
        writer.writerow({
            "id": track.id,
            "title": track.title,
            "artists": ", ".join(a.name for a in track.artists),
            "album": album.title if album else "",
            "album_id": album.id if album else "",
            "year": album.year if album else "",
            "genre": album.genre if album else "",
            "duration_ms": track.duration_ms,
            "added_at": track_short.timestamp,
            "available": track.available,
            "content_warning": track.content_warning or "",
        })

print(f"Готово. Всего треков: {len(liked)}")
