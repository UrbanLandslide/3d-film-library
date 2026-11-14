#!/usr/bin/env python3
"""Download missing poster JPEGs for the 220-entry 3D Film Library.
Uses Cinemeta search results; existing poster files are never overwritten.
"""
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')
match = re.search(r'\bconst\s+(?:films|FILMS)\s*=\s*(\[.*?\])\s*;', HTML, re.S)
if not match:
    raise SystemExit('Could not locate film array in index.html')
films = json.loads(match.group(1))
if len(films) < 200:
    raise SystemExit(f'Expected full catalogue (at least 200 entries); found {len(films)}')
folder = ROOT / 'posters'
folder.mkdir(exist_ok=True)

def slug(title):
    return re.sub(r'^-|-$', '', re.sub(r'[^a-z0-9]+', '-', title.lower()))

def normal(title):
    return re.sub(r'[^a-z0-9]', '', title.lower())

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (3D Film Library personal catalogue)'})
    with urllib.request.urlopen(req, timeout=18) as response:
        return response.read()

success = []
missing = []
existing = []
for i, film in enumerate(films, 1):
    title = film['title']
    target = folder / (slug(title) + '.jpg')
    if target.exists() and target.stat().st_size > 1000:
        existing.append(title)
        continue
    try:
        search = 'https://v3-cinemeta.strem.io/catalog/movie/top/search=' + urllib.parse.quote(title, safe='') + '.json'
        entries = json.loads(get(search)).get('metas', [])
        # Do not attach a random unrelated poster to an uncertain catalogue entry.
        selected = next((m for m in entries if normal(m.get('name', '')) == normal(title) and m.get('poster')), None)
        if selected is None:
            missing.append(f'{title} — no exact poster match')
            continue
        poster = selected['poster']
        data = get(poster)
        if len(data) < 1000 or not (data.startswith(b'\xff\xd8') or data.startswith(b'\x89PNG')):
            missing.append(f'{title} — invalid poster image')
            continue
        # Poster URLs generally return JPEGs. PNG is skipped to preserve .jpg extension.
        if not data.startswith(b'\xff\xd8'):
            missing.append(f'{title} — poster not JPEG')
            continue
        target.write_bytes(data)
        success.append(title)
        print(f'[{i}/{len(films)}] Added {title}', flush=True)
    except Exception as exc:
        missing.append(f'{title} — {type(exc).__name__}: {exc}')
    time.sleep(0.1)

report = (f'Catalogue: {len(films)}\nExisting posters: {len(existing)}\nNew posters: {len(success)}\n'
          f'Not matched: {len(missing)}\n\n' + '\n'.join(missing) + '\n')
(ROOT / 'poster-report.txt').write_text(report, encoding='utf-8')
print(report, flush=True)
