import json
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

tracks = []


def fetch_track_with_retry(track_short, retries=5, delay=3):
    for attempt in range(retries):
        try:
            return track_short.fetch_track()
        except TimedOutError:
            if attempt + 1 == retries:
                raise
            time.sleep(delay * (attempt + 1))


for track_short in tqdm(liked, desc="Экспорт треков"):
    track = fetch_track_with_retry(track_short)
    tracks.append(track)

json.dump(tracks, open('tracks.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=4)

print(f"Готово. Всего треков: {len(liked)}")
