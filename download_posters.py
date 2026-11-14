
#!/usr/bin/env python3
"""Find missing posters for the 220-entry 3D Film Library.
Existing poster images are never overwritten.
"""

import io
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
HTML = (ROOT / "index.html").read_text(encoding="utf-8")

match = re.search(
    r"\bconst\s+(?:films|FILMS)\s*=\s*(\[.*?\])\s*;",
    HTML,
    re.S,
)

if not match:
    raise SystemExit("Could not find film list in index.html")

films = json.loads(match.group(1))

films.extend([
    {"title": "Dune (1984)"},
    {"title": "Blade Runner: The Final Cut"},
    {"title": "Blade Runner 2049"},
    {"title": "Avatar: The Way of Water"},
    {"title": "Space: 1999"}
])


if len(films) < 200:
    raise SystemExit(
        f"Expected at least 200 entries; found {len(films)}"
    )

folder = ROOT / "posters"
folder.mkdir(exist_ok=True)

ALIASES = {
    "A Better Tomorrow 2012": ["A Better Tomorrow"],
    "A Liar's Autobiography": [
        "A Liar's Autobiography: The Untrue Story of Monty Python's Graham Chapman"
    ],
    "Batman: The Dark Knight Rises": ["The Dark Knight Rises"],
    "Berättelsen om Pi": ["Life of Pi"],
    "Blue Ruin (2013)": ["Blue Ruin"],
    "Doctor Who: The Day of the Doctor": [
        "The Day of the Doctor"
    ],
    "Drive Angry": ["Drive Angry 3D"],
    "Frozen II": ["Frozen 2"],
    "Ice Age 3: Dawn of the Dinosaurs": [
        "Ice Age: Dawn of the Dinosaurs"
    ],
    "Ice Age 4: Continental Drift": [
        "Ice Age: Continental Drift"
    ],
    "Men in Black 3": ["Men in Black III"],
    "My Bloody Valentine": ["My Bloody Valentine 3D"],
    "Nurse 3D": ["Nurse"],
    "Saw 3D: The Final Chapter": [
        "Saw: The Final Chapter",
        "Saw VII",
    ],
    "Shark Night 3D": ["Shark Night"],
    "Shazam! 3D": ["Shazam!"],
    "Shock Labyrinth 3D": ["The Shock Labyrinth"],
    "Spiders 3D": ["Spiders"],
    "Star Wars: The Force Awakens": [
        "Star Wars: Episode VII - The Force Awakens"
    ],
    "The Thing (1982)": ["The Thing"],
    "The Thing (2011)": ["The Thing"],
    "The Three Musketeers (2011)": [
        "The Three Musketeers"
    ],
    "Titanic 3D": ["Titanic"],
    "Warcraft: The Beginning": ["Warcraft"],
    "Watchmen: The Ultimate Cut": ["Watchmen"],
}

# Collections and uncertain titles need manual verification.
MANUAL = {
    "Cousteau — 3 Film Collection",
    "Dunderhead (title uncertain)",
    "The Hobbit — 3D trilogy (collection reference)",
    "The Lord of the Rings (collection / edition uncertain)",
    "The Matrix Reloaded / The Matrix Revolutions",
    "Pirates of the Caribbean: Collection",
    "Planet Earth: The Complete Series (Episodes 1–9)",
    "Planet Earth: The Complete Series (Episodes 10–11 & Bonus)",
    "The Presence (title uncertain)",
    "Skarb: Death of Dora Land 3D",
    "Solomon Kane 2 (title uncertain)",
}


def slug(title):
    return re.sub(
        r"^-|-$",
        "",
        re.sub(r"[^a-z0-9]+", "-", title.lower()),
    )


def normal(title):
    title = unicodedata.normalize("NFKD", title)
    title = title.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", title.lower())


def get(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json,image/*,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=18) as response:
        return response.read()


def convert_image(data):
    with Image.open(io.BytesIO(data)) as image:
        image.load()

        if image.width < 100 or image.height < 140:
            raise ValueError("Poster image too small")

        image = image.convert("RGB")

        output = io.BytesIO()
        image.save(
            output,
            format="JPEG",
            quality=88,
            optimize=True,
        )
        return output.getvalue()


def cinemeta(query):
    url = (
        "https://v3-cinemeta.strem.io/catalog/movie/top/search="
        + urllib.parse.quote(query, safe="")
        + ".json"
    )
    return json.loads(get(url)).get("metas", [])


def imdb(query):
    first = urllib.parse.quote(query[0].lower())
    url = (
        "https://v2.sg.media-imdb.com/suggestion/"
        + first
        + "/"
        + urllib.parse.quote(query, safe="")
        + ".json"
    )
    return json.loads(get(url)).get("d", [])


def year_matches(candidate, wanted):
    if not candidate or not wanted:
        return True

    try:
        return abs(int(str(candidate)[:4]) - int(wanted)) <= 1
    except (ValueError, TypeError):
        return True


def poster_candidates(title, year):
    queries = list(dict.fromkeys(
        [title] + ALIASES.get(title, [])
    ))

    seen = set()

    for query in queries:
        try:
            for entry in cinemeta(query):
                if normal(entry.get("name", "")) != normal(query):
                    continue

                if not year_matches(
                    entry.get("releaseInfo"), year
                ):
                    continue

                url = entry.get("poster")

                if url and url not in seen:
                    seen.add(url)
                    yield url

        except Exception as exc:
            print(
                f"Cinemeta search failed for {query}: {exc}",
                flush=True,
            )

        try:
            for entry in imdb(query):
                if normal(entry.get("l", "")) != normal(query):
                    continue

                if not year_matches(entry.get("y"), year):
                    continue

                if entry.get("qid") not in (
                    None,
                    "movie",
                    "tvMovie",
                    "tvSpecial",
                    "video",
                    "tvMiniSeries",
                    "tvSeries",
                ):
                    continue

                url = (entry.get("i") or {}).get("imageUrl")

                if url and url not in seen:
                    seen.add(url)
                    yield url

        except Exception as exc:
            print(
                f"IMDb search failed for {query}: {exc}",
                flush=True,
            )


existing = []
added = []
missing = []

for number, film in enumerate(films, 1):
    title = film["title"]
    target = folder / (slug(title) + ".jpg")

    if target.exists() and target.stat().st_size > 1000:
        existing.append(title)
        continue

    if title in MANUAL:
        missing.append(
            f"{title} — collection or uncertain title"
        )
        continue

    found = False

    for url in poster_candidates(title, film.get("year")):
        try:
            data = get(url)
            jpeg = convert_image(data)

            target.write_bytes(jpeg)
            added.append(title)
            found = True

            print(
                f"[{number}/{len(films)}] Added {title}",
                flush=True,
            )
            break

        except Exception as exc:
            print(
                f"Image failed for {title}: {exc}",
                flush=True,
            )

    if not found:
        missing.append(
            f"{title} — no usable matching poster"
        )

    time.sleep(0.12)


report = (
    f"Catalogue: {len(films)}\n"
    f"Existing posters: {len(existing)}\n"
    f"New posters: {len(added)}\n"
    f"Still missing: {len(missing)}\n\n"
    + "\n".join(missing)
    + "\n"
)

(ROOT / "poster-report.txt").write_text(
    report,
    encoding="utf-8",
)

print(report, flush=True)
