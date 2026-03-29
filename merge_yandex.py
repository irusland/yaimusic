import csv
import plistlib
import xml.sax.saxutils as saxutils
from datetime import datetime, timezone

import click


def parse_date(s: str) -> str:
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def esc(value: str) -> str:
    return saxutils.escape(str(value))


def track_xml(track_id: int, row: dict) -> str:
    lines = [
        f"\t\t<key>{track_id}</key>",
        "\t\t<dict>",
        f"\t\t\t<key>Track ID</key><integer>{track_id}</integer>",
        f"\t\t\t<key>Name</key><string>{esc(row['title'])}</string>",
    ]
    if row.get("artists"):
        lines.append(f"\t\t\t<key>Artist</key><string>{esc(row['artists'])}</string>")
        lines.append(f"\t\t\t<key>Album Artist</key><string>{esc(row['artists'])}</string>")
    if row.get("album"):
        lines.append(f"\t\t\t<key>Album</key><string>{esc(row['album'])}</string>")
    if row.get("genre"):
        lines.append(f"\t\t\t<key>Genre</key><string>{esc(row['genre'].capitalize())}</string>")
    if row.get("year"):
        try:
            lines.append(f"\t\t\t<key>Year</key><integer>{int(row['year'])}</integer>")
        except ValueError:
            pass
    if row.get("duration_ms"):
        try:
            lines.append(f"\t\t\t<key>Total Time</key><integer>{int(row['duration_ms'])}</integer>")
        except ValueError:
            pass
    if row.get("added_at"):
        lines.append(f"\t\t\t<key>Date Added</key><date>{parse_date(row['added_at'])}</date>")
    if row.get("content_warning") == "explicit":
        lines.append("\t\t\t<key>Explicit</key><true/>")
    lines.append("\t\t\t<key>Track Type</key><string>Remote</string>")
    lines.append("\t\t</dict>")
    return "\n".join(lines)


def playlist_xml(pl_id: int, track_ids: list[int]) -> str:
    items = "\n".join(
        f"\t\t\t\t<dict>\n\t\t\t\t\t<key>Track ID</key><integer>{tid}</integer>\n\t\t\t\t</dict>"
        for tid in track_ids
    )
    return (
        "\t\t<dict>\n"
        f"\t\t\t<key>Name</key><string>Yandex Music Liked</string>\n"
        f"\t\t\t<key>Playlist ID</key><integer>{pl_id}</integer>\n"
        "\t\t\t<key>Playlist Persistent ID</key><string>YANDEXMUSICLKD0</string>\n"
        "\t\t\t<key>All Items</key><true/>\n"
        "\t\t\t<key>Playlist Items</key>\n"
        "\t\t\t<array>\n"
        f"{items}\n"
        "\t\t\t</array>\n"
        "\t\t</dict>"
    )


@click.command()
@click.option("--csv", "csv_path", default="yandex_music.csv", show_default=True,
              type=click.Path(exists=True, dir_okay=False), help="Yandex Music CSV файл")
@click.option("--xml", "xml_path", default="Library.xml", show_default=True,
              type=click.Path(exists=True, dir_okay=False), help="iTunes Library XML файл")
@click.option("--out", "out_path", default="Library_merged.xml", show_default=True,
              type=click.Path(dir_okay=False), help="Путь для сохранения результата")
def merge(csv_path: str, xml_path: str, out_path: str) -> None:
    with open(xml_path, "r", encoding="utf-8") as f:
        content = f.read()

    with open(xml_path, "rb") as f:
        library = plistlib.load(f)

    existing_ids = [int(k) for k in library.get("Tracks", {}).keys()]
    next_id = (max(existing_ids) + 2) if existing_ids else 1

    playlists = library.get("Playlists", [])
    max_pl_id = max((p.get("Playlist ID", 0) for p in playlists), default=0)

    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    new_track_ids: list[int] = []
    tracks_xml_parts: list[str] = []

    with click.progressbar(rows, label="Импорт треков") as bar:
        for row in bar:
            track_id = next_id
            next_id += 2
            tracks_xml_parts.append(track_xml(track_id, row))
            new_track_ids.append(track_id)

    new_tracks_block = "\n".join(tracks_xml_parts)

    tracks_marker = "\t</dict>\n\t<key>Playlists</key>"
    if tracks_marker not in content:
        raise click.ClickException("Не найден маркер конца секции Tracks в XML.")

    content = content.replace(
        tracks_marker,
        f"{new_tracks_block}\n{tracks_marker}",
        1,
    )

    pl_marker = "\t</array>\n</dict>\n</plist>"
    if pl_marker not in content:
        raise click.ClickException("Не найден маркер конца секции Playlists в XML.")

    new_pl = playlist_xml(max_pl_id + 1, new_track_ids)
    content = content.replace(
        pl_marker,
        f"{new_pl}\n{pl_marker}",
        1,
    )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    click.secho(
        f"Готово. Добавлено {len(new_track_ids)} треков → {out_path}", fg="green"
    )


if __name__ == "__main__":
    merge()
