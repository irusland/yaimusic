import csv
import os

from dotenv import load_dotenv
from tqdm import tqdm
from yandex_music import Client
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

with open("yandex_music.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()

    for track_short in tqdm(liked, desc="Экспорт треков"):
        track = track_short.fetch_track()
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
