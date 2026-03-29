import csv
import json
import os

from dotenv import load_dotenv
from tqdm import tqdm
from yandex_music import Client
load_dotenv()

TOKEN = os.environ.get("YANDEX_MUSIC_TOKEN")

client = Client(TOKEN).init()
liked = client.users_likes_tracks()

tracks = []


for track_short in tqdm(liked, desc="Экспорт треков"):
    track = track_short.fetch_track()
    tracks.append(track)

json.dump(tracks, open('tracks.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=4)


print(f"Готово. Всего треков: {len(liked)}")
