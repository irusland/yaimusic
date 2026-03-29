"""
Добавляет треки из yandex-music/ в Apple Music:
  - вшивает cover art и lyrics в .m4a
  - добавляет файл в Apple Music через AppleScript
  - устанавливает date added через временное изменение системных часов (требует sudo)

Использование:
    python import_track.py --dry-run                        # первый найденный трек, без изменений
    sudo python import_track.py --file "path/to/track.m4a" # один трек
    sudo python import_track.py --dir "yandex-music/FACE"  # все треки в директории
    sudo python import_track.py --dir "yandex-music"       # вся библиотека
"""

import argparse
import csv
import os
import re
import subprocess
import tempfile
from pathlib import Path

from mutagen.mp4 import MP4, MP4Cover

YANDEX_DIR = Path(__file__).parent / "yandex-music"
CSV_PATH = Path(__file__).parent / "yandex_music.csv"


def load_csv(csv_path: Path) -> dict[str, dict]:
    """Загружает CSV, возвращает словарь title -> row."""
    tracks = {}
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tracks[row["title"].lower()] = row
    return tracks


def find_cover(album_dir: Path) -> Path | None:
    for ext in ("cover.png", "cover.jpg", "cover.jpeg"):
        p = album_dir / ext
        if p.exists():
            return p
    return None


def find_lrc(m4a_path: Path) -> Path | None:
    lrc = m4a_path.with_suffix(".lrc")
    return lrc if lrc.exists() else None


def parse_lrc(lrc_path: Path) -> str:
    """Убирает временные метки из .lrc и возвращает чистый текст."""
    lines = []
    for line in lrc_path.read_text(encoding="utf-8").splitlines():
        clean = re.sub(r"\[\d+:\d+\.\d+\]", "", line).strip()
        if clean:
            lines.append(clean)
    return "\n".join(lines)


def embed_metadata(m4a_path: Path, cover_path: Path | None, lyrics: str | None, dry_run: bool):
    """Вшивает обложку и текст в .m4a файл."""
    if dry_run:
        print(f"  [dry] embed cover={cover_path is not None}, lyrics={lyrics is not None}")
        return

    audio = MP4(m4a_path)

    if cover_path:
        img_format = MP4Cover.FORMAT_PNG if cover_path.suffix == ".png" else MP4Cover.FORMAT_JPEG
        audio["covr"] = [MP4Cover(cover_path.read_bytes(), imageformat=img_format)]

    if lyrics:
        audio["\xa9lyr"] = [lyrics]

    audio.save()
    print(f"  Метаданные вшиты: {m4a_path.name}")


def is_track_in_library(title: str, artist: str) -> bool:
    """Проверяет наличие трека в библиотеке Apple Music через AppleScript."""
    script = f"""
tell application "Music"
    set results to (every track of library playlist 1 whose name is "{title}" and artist is "{artist}")
    return (count of results) > 0
end tell
"""
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return result.stdout.strip() == "true"


def add_to_apple_music(m4a_path: Path, date_added: str, dry_run: bool):
    """Добавляет файл в Apple Music через AppleScript."""
    posix = str(m4a_path.resolve())  # абсолютный путь

    if dry_run:
        print(f"  [dry] osascript: add '{posix}' to Music")
        print(f"  [dry] date added будет: {date_added}")
        return

    from datetime import datetime, timezone
    dt = datetime.fromisoformat(date_added).astimezone(timezone.utc)
    date_str = dt.strftime("%m%d%H%M%Y.%S")

    # Запомнить текущее время до изменения
    original_dt = datetime.now(timezone.utc)
    original_date_str = original_dt.strftime("%m%d%H%M%Y.%S")

    try:
        subprocess.run(["date", date_str], check=True)

        script = f'tell application "Music" to add POSIX file "{posix}"'
        subprocess.run(["osascript", "-e", script], check=True)

        print(f"  Добавлено в Apple Music: {m4a_path.name}")
    finally:
        # Сначала пробуем NTP, при неудаче — восстанавливаем вручную
        ntp = subprocess.run(["sntp", "-sS", "time.apple.com"], capture_output=True)
        if ntp.returncode != 0:
            print("  NTP недоступен, восстанавливаем время вручную...")
            subprocess.run(["date", original_date_str], check=True)
            print(f"  Время восстановлено: {original_dt.strftime('%Y-%m-%d %H:%M:%S')} UTC")


def find_first_track() -> tuple[Path, Path] | None:
    """Возвращает первый найденный (m4a, album_dir)."""
    for artist_dir in sorted(YANDEX_DIR.iterdir()):
        if not artist_dir.is_dir() or artist_dir.name.startswith("."):
            continue
        for album_dir in sorted(artist_dir.iterdir()):
            if not album_dir.is_dir():
                continue
            for f in sorted(album_dir.iterdir()):
                if f.suffix == ".m4a":
                    return f, album_dir
    return None


def collect_tracks(args) -> list[tuple[Path, Path]]:
    """Возвращает список (m4a_path, album_dir) в зависимости от аргументов."""
    if args.file:
        m4a = Path(args.file)
        return [(m4a, m4a.parent)]

    if args.dir:
        root = Path(args.dir)
        files = sorted(root.rglob("*.m4a"))
        return [(f, f.parent) for f in files]

    result = find_first_track()
    return [result] if result else []


def process_track(m4a_path: Path, album_dir: Path, csv_tracks: dict, dry_run: bool):
    title = re.sub(r"^\d+\s*-\s*", "", m4a_path.stem).strip()
    csv_row = csv_tracks.get(title.lower())
    artist = csv_row["artists"] if csv_row else m4a_path.parent.parent.name

    print(f"Трек:       {title}")
    print(f"Исполнитель:{artist}")
    print(f"Файл:       {m4a_path}")
    print(f"В CSV:      {'найден' if csv_row else 'НЕ найден'}")

    # Проверка дубликата
    if not dry_run and is_track_in_library(title, artist):
        print(f"  Пропущен: уже есть в Apple Music\n")
        return

    cover_path = find_cover(album_dir)
    lrc_path = find_lrc(m4a_path)
    lyrics = parse_lrc(lrc_path) if lrc_path else None
    date_added = csv_row["added_at"] if csv_row else None

    print(f"Обложка:    {cover_path}")
    print(f"Lyrics:     {'есть' if lyrics else 'нет'}")
    print(f"Date Added: {date_added}")

    embed_metadata(m4a_path, cover_path, lyrics, dry_run=dry_run)

    if date_added:
        add_to_apple_music(m4a_path, date_added, dry_run=dry_run)
    else:
        print("  Предупреждение: дата не найдена в CSV, добавление пропущено")

    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Только показать план, ничего не менять")
    parser.add_argument("--file", help="Путь к конкретному .m4a файлу")
    parser.add_argument("--dir", help="Директория — обработать все .m4a рекурсивно")
    args = parser.parse_args()

    csv_tracks = load_csv(CSV_PATH)
    tracks = collect_tracks(args)

    if not tracks:
        print("Файлы .m4a не найдены")
        return

    print(f"Найдено треков: {len(tracks)}\n")

    for i, (m4a_path, album_dir) in enumerate(tracks, 1):
        print(f"[{i}/{len(tracks)}]")
        process_track(m4a_path, album_dir, csv_tracks, dry_run=args.dry_run)

    print("Готово." if not args.dry_run else "Dry run завершён.")


if __name__ == "__main__":
    main()
