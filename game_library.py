#!/usr/bin/env python3
"""SAC23 Game Library: dependency-free local PS4/PS5 catalog server.

Personal, read-only file scanning; never copies/deletes/modifies game content.
Requires Python 3.10+, browser for UI. Optional API keys enhance artwork and trailers.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import difflib
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, quote, urlparse, urlencode
from urllib.request import Request, urlopen
import uuid
import webbrowser
import metadata
import pkg_art
import archive_art
import artwork_rescue

APP_NAME = "SAC23 Game Library"
APP_VERSION = "2.4.0"
APP_HOME = Path(__file__).resolve().parent
WEB_HOME = APP_HOME / "web"
DATA_HOME = Path(os.environ.get("SAC23_DATA_DIR") or (Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share") / "SAC23_Game_Library"))
DATA_FILE = DATA_HOME / "library.json"
COVER_CACHE = DATA_HOME / "covers"
ARTWORK_INBOX = DATA_HOME / "Cover Inbox"
COVER_EXTENSIONS = (".jpg", ".png", ".webp", ".gif")
EXTENSIONS = {".pkg", ".iso", ".zip", ".rar", ".7z", ".cso", ".chd", ".zso"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
IMAGE_NAMES = ("cover.jpg", "cover.png", "cover.webp", "poster.jpg", "poster.png", "folder.jpg", "folder.png", "icon0.png", "icon0_00.png", "icon.png", "game.jpg", "game.png", "thumbnail.jpg", "thumbnail.png")
SKIP_DIRS = {"$recycle.bin", "system volume information", ".git", "node_modules", "__pycache__", ".trash", "@eadir"}
FOLDER_GENERICS = {"ps4", "ps5", "ps4 games", "ps5 games", "ps4_games", "ps5_games", "playstation 4", "playstation 5", "games", "game", "base", "updates", "update", "dlc", "addons", "add-ons", "packages", "pkg", "downloads", "download", "archives", "backup", "backups", "content", "titles", "installed", "isos", "iso", "app", "patch", "sac23", "playstation"}
BAD_TITLE_WORDS = re.compile(r"\b(?:ps[45]|playstation[ -]?[45]|superpsx|dlpsgame|gamebato|cusa\d{4,6}|ppsa\d{4,7}|pcsa\d{4,7}|pcas\d{4,7}|pcsh\d{4,7}|us[ae]|eur|euro|jpn|asia|r[0-9]|repack|retail|duplex|opoisso|fake[ -]?pkg|fpkg|backport|all[ -]?dlc|game[ -]?base|base[ -]?game|patch|updates?|dlcs?|add[ -]?ons?|full[ -]?game|fix|release|scene|pkg|v\d+(?:\.\d+){0,3}|\d{1,2}\.\d{2}fw)\b", re.IGNORECASE)
TITLE_ID_RE = re.compile(r"(?<![A-Z0-9])(?:CUSA|PPSA|PCSA|PCAS|PCSH)[- _]?(\d{4,7})(?!\d)", re.IGNORECASE)
CATEGORY_RE = re.compile(r"(?:^|[\W_])(dlc|addon|add-on|add_on|expansion|season[ -]?pass|bonus[ -]?content|content[ -]?pack)(?:$|[\W_])", re.IGNORECASE)
UPDATE_RE = re.compile(r"(?:^|[\W_])(update|patch|hotfix|backport)(?:$|[\W_])", re.IGNORECASE)
KEY_LOCK = threading.RLock()
scan_running = False
scan_queued = False
scan_progress = {"running": False, "scanned_files": 0, "matched_files": 0, "current": "", "message": "Ready", "errors": [], "completed_at": None}
enrich_running = False
on_demand_ids = set()
enrich_progress = {"running": False, "done": 0, "total": 0, "message": "", "errors": []}


def empty_state():
    return {"folders": [], "games": [], "settings": {"steamgriddb_key": "", "rawg_key": "", "youtube_key": "", "wiki_fallback": True, "auto_artwork": True, "auto_trailers": True}, "last_scan": None}


def load_state():
    try:
        with DATA_FILE.open("r", encoding="utf8") as f:
            d = json.load(f)
        base = empty_state()
        base.update({k: v for k, v in d.items() if k in base})
        base["settings"] = {**empty_state()["settings"], **base["settings"]}
        return base
    except (OSError, ValueError, TypeError):
        return empty_state()


state = load_state()
state_revision = 0


def save_state():
    global state_revision
    DATA_HOME.mkdir(parents=True, exist_ok=True)
    temp = DATA_FILE.with_suffix(".tmp")
    with temp.open("w", encoding="utf8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(temp, DATA_FILE)
    state_revision += 1


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def human_title(s):
    # Remove scene-release labels before punctuation turns them into fake words.
    s = re.sub(r"(?i)[-_.]+game(?=[-_.]|$)", " ", s)
    s = re.sub(r"\(\s*\d{1,2}\.\d{2}\s*\)", " ", s)
    s = s.replace("_", " ").replace(".", " ")
    s = re.sub(r"(?i)^\s*(?:\[[^\]]*(?:superpsx|psx|scene|download)[^\]]*\][\s_-]*)+", "", s)
    s = re.sub(r"(?i)^\s*(?:www\.)?[^\s]+\.(?:com|net)[ -]+", "", s)
    s = re.sub(r"[\[\]{}()]", " ", s)
    s = re.sub(r"(?i)\b(?:\d{1,2}\.\d{2}\s*fw|\d{1,2}\.\d{2}\s*fix)\b", " ", s)
    s = BAD_TITLE_WORDS.sub(" ", s)
    s = re.sub(r"[-–—]", " ", s)
    s = re.sub(r"[^\w\s:'’&+!-]", " ", s, flags=re.UNICODE)
    s = " ".join(s.split()).strip("-_ .")
    return s or "Unknown game"


def canonical_title(s):
    s = re.sub(r"[^a-z0-9]+", "", human_title(s).lower())
    return s[:120]


def is_generic(s):
    s = re.sub(r"[\s_-]+", " ", s.lower()).strip()
    return s in FOLDER_GENERICS or bool(re.fullmatch(r"(?:ps[45][ -]?)?(?:games?|updates?|dlcs?|packages?|isos?)", s))


def file_platform(text, folder_choice):
    if folder_choice != "AUTO":
        return folder_choice
    if re.search(r"(?i)\bPPSA\s*[-_]?\d{4,7}\b", text):
        return "PS5"
    if re.search(r"(?i)\b(?:CUSA|PCSA|PCAS|PCSH)\s*[-_]?\d{4,7}\b", text):
        return "PS4"
    if re.search(r"(?i)(?:^|[/\\_\s.-])PS5(?:$|[/\\_\s.-])", text):
        return "PS5"
    if re.search(r"(?i)(?:^|[/\\_\s.-])PS4(?:$|[/\\_\s.-])", text):
        return "PS4"
    return "UNKNOWN"


def classification(filename, folder_parts):
    parts = [str(i) for i in folder_parts]
    if any(CATEGORY_RE.search(item) or item.lower() in ("dlc", "dlcs", "addons", "add-ons") for item in [filename] + parts):
        return "DLC"
    if any(UPDATE_RE.search(item) or item.lower() in ("updates", "update", "patch") for item in [filename] + parts):
        return "Update"
    return "Game"


def candidate_title(path: Path, relative_parts, folder_metadata=None):
    parts = list(relative_parts[:-1])
    meaningful = [part for part in parts if not is_generic(part) and part.lower() != "sce_sys"]
    if folder_metadata and folder_metadata.get("title"):
        return human_title(folder_metadata["title"])
    # A named game folder generally provides a cleaner title than a scene-release PKG.
    if meaningful:
        # Use first game-specific folder after the configured scan root.
        return human_title(meaningful[0])
    return human_title(path.stem if path.is_file() else path.name)


def game_id(platform, title, title_id=""):
    key = f"{platform}:{canonical_title(title) or title_id}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def local_cover(folder, root):
    parent = folder
    try:
        root_real = root.resolve()
    except OSError:
        root_real = root
    for _ in range(3):
        try:
            if not parent.resolve().is_relative_to(root_real):
                break
            # Extracted PlayStation games typically keep artwork BELOW the
            # game folder in sce_sys, not alongside the package itself.
            for image_name in ('icon0.png', 'icon0_00.png', 'cover.jpg', 'cover.png'):
                nested = parent / 'sce_sys' / image_name
                if nested.is_file():
                    return str(nested)
            file_map = {p.name.lower(): p for p in parent.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS}
            for name in IMAGE_NAMES:
                if name in file_map:
                    return str(file_map[name])
        except (OSError, PermissionError):
            pass
        if parent == root:
            break
        parent = parent.parent
    return ""


def parse_sfo(path):
    """Parse a small PS4 PARAM.SFO safely. No package unpacking/decryption."""
    import struct
    try:
        data = path.read_bytes()
        if len(data) < 20 or len(data) > 2_000_000 or data[:4] != b'\x00PSF':
            return {}
        _, _, key_offset, val_offset, count = struct.unpack_from('<IIIII', data, 0)
        if count > 300:
            return {}
        info = {}
        for i in range(count):
            k_off, fmt, length, max_length, v_off = struct.unpack_from('<HHIII', data, 20 + 16 * i)
            key = data[key_offset + k_off:].split(b'\x00', 1)[0].decode('utf8', 'replace')
            if key in {"TITLE", "TITLE_ID", "CONTENT_ID"}:
                raw = data[val_offset + v_off:val_offset + v_off + min(length, 4096)]
                info[key] = raw.split(b'\x00', 1)[0].decode('utf8', 'replace')
        return {'title': info.get('TITLE'), 'title_id': info.get('TITLE_ID'), 'content_id': info.get('CONTENT_ID')}
    except (OSError, ValueError, TypeError, struct.error, IndexError):
        return {}


def parse_ps5_json(path):
    try:
        if path.stat().st_size > 2_000_000:
            return {}
        d = json.loads(path.read_text(encoding='utf-8-sig'))
        titles = d.get('localizedParameters') or {}
        named = titles.get('en-US') or titles.get('en-GB') or (next(iter(titles.values()), {}) if isinstance(titles, dict) else {})
        return {'title': named.get('titleName') or d.get('titleName'), 'title_id': d.get('titleId'), 'content_id': d.get('contentId')}
    except (OSError, ValueError, AttributeError, TypeError):
        return {}


def scan_worker():
    global scan_running, scan_queued
    with KEY_LOCK:
        roots = list(state['folders'])
        old_games = {g['id']: g for g in state['games']}
        scan_progress.update({'running': True, 'scanned_files': 0, 'matched_files': 0, 'current': '', 'message': 'Scanning folders...', 'errors': []})
    grouped = {}
    total_files = 0
    try:
        for configured in roots:
            base = Path(configured['path'])
            forced_platform = configured.get('platform', 'AUTO')
            if not base.is_dir():
                with KEY_LOCK:
                    scan_progress['errors'].append(f"Folder unavailable: {base}")
                continue
            for rootstr, dirs, files in os.walk(base, followlinks=False):
                dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS and not d.startswith('.')]
                folder = Path(rootstr)
                with KEY_LOCK:
                    scan_progress['current'] = str(folder)
                relative_dir_parts = folder.relative_to(base).parts
                # Recognize extracted PS4 / PS5 game folders with game metadata.
                meta = {}
                try:
                    nset = {f.lower(): f for f in files}
                    if folder.name.lower() == 'sce_sys':
                        # metadata lives in sce_sys but the game title belongs to its parent
                        marker = nset.get('param.sfo') or nset.get('param.json')
                        if marker:
                            meta = parse_sfo(folder / marker) if marker.lower().endswith('.sfo') else parse_ps5_json(folder / marker)
                            dest = folder.parent
                            if dest != base and meta:
                                relparts = dest.relative_to(base).parts + ('folder',)
                                title = candidate_title(dest, relparts, meta)
                                ids = [str(meta.get('title_id') or ''), str(meta.get('content_id') or '')]
                                mid = TITLE_ID_RE.search(' '.join(ids) + ' ' + str(dest))
                                id_match = mid.group(0).replace('-', '').replace('_', '').replace(' ', '').upper() if mid else str(meta.get('title_id') or '')
                                platform = file_platform(str(dest) + ' ' + id_match, forced_platform)
                                if platform == 'UNKNOWN' and marker.lower() == 'param.json':
                                    platform = 'PS5'
                                if platform == 'UNKNOWN' and marker.lower() == 'param.sfo':
                                    platform = 'PS4'
                                add_group(grouped, platform, title, id_match, {'path': str(dest), 'kind': 'Folder', 'category': 'Game', 'size': 0, 'modified': 0}, base, dest)
                except (OSError, PermissionError):
                    pass
                for name in files:
                    total_files += 1
                    if total_files % 80 == 0:
                        with KEY_LOCK:
                            scan_progress['scanned_files'] = total_files
                    fpath = folder / name
                    if fpath.suffix.lower() not in EXTENSIONS:
                        continue
                    try:
                        st = fpath.stat()
                        if not fpath.is_file():
                            continue
                    except (OSError, PermissionError):
                        continue
                    rel_parts = fpath.relative_to(base).parts
                    title = candidate_title(fpath, rel_parts)
                    # Prefer game-specific folder, but fall back to filename for empty/generic names.
                    if title.lower() == 'unknown game':
                        title = human_title(fpath.stem)
                    found = TITLE_ID_RE.search(str(fpath))
                    product_id = re.sub(r'[-_ ]', '', found.group(0)).upper() if found else ''
                    platform = file_platform(str(fpath), forced_platform)
                    category = classification(name, rel_parts[:-1])
                    add_group(grouped, platform, title, product_id, {'path': str(fpath), 'kind': fpath.suffix[1:].upper(), 'category': category, 'size': st.st_size, 'modified': int(st.st_mtime)}, base, folder)
                    with KEY_LOCK:
                        scan_progress['matched_files'] += 1
        # Retain manual cover URL, favorites, trailer links, title edits and metadata enrichment by stable id.
        new_games = []
        for g in grouped.values():
            g['files'].sort(key=lambda f: {'Game': 0, 'Update': 1, 'DLC': 2}.get(f['category'], 3))
            g['size'] = sum(f['size'] for f in g['files'])
            g['file_count'] = len(g['files'])
            g['updated_at'] = max((f['modified'] for f in g['files']), default=0)
            g['update_count'] = sum(f['category'] == 'Update' for f in g['files'])
            g['dlc_count'] = sum(f['category'] == 'DLC' for f in g['files'])
            g['game_count'] = sum(f['category'] == 'Game' for f in g['files'])
            previous = old_games.get(g['id'])
            if not previous:
                # If the display title changed while keeping its titleId, retain data by unique id match.
                previous = next((x for x in old_games.values() if g.get('title_id') and x.get('title_id') == g['title_id'] and x.get('platform') == g['platform']), None)
            if previous:
                for field in ('custom_title', 'cover_url', 'custom_cover', 'trailer_url', 'favorite', 'description', 'year', 'genre', 'source', 'source_url', 'metadata_checked', 'metadata_error', 'artwork_v2_checked', 'artwork_v3_checked', 'artwork_v4_checked', 'artwork_v5_checked', 'manual_cover_url', 'matched_name', 'cover_quality', 'cover_error', 'cover_revision', 'identified_title'):
                    if field in previous:
                        g[field] = previous[field]
            new_games.append(g)
        with KEY_LOCK:
            state['games'] = sorted(new_games, key=lambda g: g['title'].casefold())
            state['last_scan'] = now_iso()
            save_state()
            # Repair exact-ID duplicate game cards *before* network matching.
            repaired = repair_cached_duplicate_covers()
            if repaired:
                print(f'[covers] Reused {len(repaired)} existing covers after rescan')
            scan_progress.update({'scanned_files': total_files, 'running': False, 'current': '', 'completed_at': state['last_scan'], 'message': f"Found {len(new_games)} games across {sum(len(g['files']) for g in new_games)} items"})
    except Exception as exc:
        with KEY_LOCK:
            scan_progress['errors'].append(f"Scan error: {type(exc).__name__}: {exc}")
            scan_progress.update({'running': False, 'message': 'Scan stopped with an error'})
    finally:
        with KEY_LOCK:
            scan_running = False
            needs_rescan = scan_queued
            scan_queued = False
        if needs_rescan:
            start_scan()
        elif not scan_progress.get('errors') and state.get('games') and state['settings'].get('auto_artwork', True):
            start_enrich()


def add_group(grouped, platform, title, title_id, fileitem, base, folder):
    key = f"{platform}|{canonical_title(title)}"
    if not canonical_title(title) and title_id:
        key = f"{platform}|{title_id.lower()}"
    g = grouped.get(key)
    if not g:
        gid = game_id(platform, title, title_id)
        g = grouped[key] = {'id': gid, 'platform': platform, 'title': title, 'title_id': title_id, 'files': [], 'local_cover': ''}
    if title_id and not g['title_id']:
        g['title_id'] = title_id
    if not any(f['path'] == fileitem['path'] for f in g['files']):
        g['files'].append(fileitem)
    if not g['local_cover']:
        g['local_cover'] = local_cover(folder, base)


def start_scan():
    global scan_running, scan_queued
    with KEY_LOCK:
        if scan_running:
            scan_queued = True
            return False
        scan_running = True
        threading.Thread(target=scan_worker, daemon=True).start()
        return True


def get_json(url, headers=None, timeout=10):
    req = Request(url, headers={"User-Agent": "SAC23-Game-Library/1.0 (desktop-local catalog; personal use)", "Accept": "application/json", **(headers or {})})
    with urlopen(req, timeout=timeout) as response:
        return json.load(response)


def find_art_steamgrid(title, key):
    base = 'https://www.steamgriddb.com/api/v2'
    headers = {'Authorization': f'Bearer {key}'}
    names = get_json(base + '/search/autocomplete/' + quote(title, safe=''), headers=headers).get('data') or []
    if not names:
        return {}
    best = max(names, key=lambda d: difflib.SequenceMatcher(None, title.lower(), str(d.get('name', '')).lower()).ratio())
    if difflib.SequenceMatcher(None, canonical_title(title), canonical_title(str(best.get('name') or ''))).ratio() < .64:
        return {}
    result = get_json(base + '/grids/game/' + str(best['id']) + '?' + urlencode({'dimensions': '600x900,342x482,660x930', 'types': 'static', 'nsfw': 'false'}), headers=headers)
    grids = result.get('data') or []
    img = next((g.get('url') for g in grids if g.get('url')), '')
    if img:
        return {'cover_url': img, 'source': 'SteamGridDB', 'source_url': 'https://www.steamgriddb.com/game/' + str(best['id'])}
    return {}


def find_art_rawg(title, key):
    url = 'https://api.rawg.io/api/games?' + urlencode({'key': key, 'search': title, 'page_size': 6})
    results = get_json(url).get('results') or []
    if not results:
        return {}
    best = max(results, key=lambda d: difflib.SequenceMatcher(None, canonical_title(title), canonical_title(str(d.get('name') or ''))).ratio())
    if difflib.SequenceMatcher(None, canonical_title(title), canonical_title(str(best.get('name') or ''))).ratio() < .61:
        return {}
    return {'cover_url': best.get('background_image') or '', 'source': 'RAWG', 'source_url': 'https://rawg.io/games/' + str(best.get('slug', '')), 'year': str(best.get('released') or '')[:4], 'genre': ', '.join(x.get('name', '') for x in best.get('genres', [])[:3])}


def find_art_wikipedia(title):
    queries = [f'"{title}" video game', f'{title} PlayStation game']
    for query in queries:
        data = get_json('https://en.wikipedia.org/w/api.php?' + urlencode({'action': 'query', 'generator': 'search', 'gsrsearch': query, 'gsrlimit': 5, 'prop': 'pageimages|info', 'pithumbsize': 650, 'format': 'json', 'formatversion': '2'}), timeout=8)
        pages = (data.get('query') or {}).get('pages') or []
        pages = [p for p in pages if p.get('thumbnail', {}).get('source')]
        if not pages:
            continue
        ranked = sorted(pages, key=lambda d: difflib.SequenceMatcher(None, canonical_title(title), canonical_title(d.get('title', '').replace('(video game)', ''))).ratio(), reverse=True)
        page = ranked[0]
        if difflib.SequenceMatcher(None, canonical_title(title), canonical_title(page.get('title', ''))).ratio() < .52:
            continue
        return {'cover_url': page['thumbnail']['source'], 'source': 'Wikipedia', 'source_url': 'https://en.wikipedia.org/?curid=' + str(page['pageid'])}
    return {}


def find_youtube_trailer(title, key):
    params = {'part': 'snippet', 'q': f'{title} official game trailer PS5 PS4', 'type': 'video', 'maxResults': 5, 'videoEmbeddable': 'true', 'key': key}
    results = get_json('https://www.googleapis.com/youtube/v3/search?' + urlencode(params)).get('items') or []
    results.sort(key=lambda p: ('official' in p.get('snippet', {}).get('title', '').lower()) + ('trailer' in p.get('snippet', {}).get('title', '').lower()), reverse=True)
    for item in results:
        video_id = (item.get('id') or {}).get('videoId', '')
        if re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
            return 'https://www.youtube.com/watch?v=' + video_id
    return ''


def valid_image_file(candidate):
    """Cheap magic-byte test so a bad local path is never called real artwork."""
    if not candidate:
        return False
    try:
        path = Path(candidate)
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            return False
        if path.stat().st_size < 256:
            return False
        with path.open('rb') as handle:
            head = handle.read(16)
        return (head[:3] == b'\xff\xd8\xff' or head[:8] == b'\x89PNG\r\n\x1a\n'
                or head[:4] == b'RIFF' and head[8:12] == b'WEBP'
                or head[:6] in (b'GIF89a', b'GIF87a'))
    except (OSError, ValueError, TypeError):
        return False


def cached_cover(gid):
    # Cover identifiers are derived from the game's title/platform hash, never
    # passed to the filesystem without checking.
    if not re.fullmatch(r"[0-9a-f]{16}", str(gid)):
        return None
    for ext in COVER_EXTENSIONS:
        path = COVER_CACHE / (gid + ext)
        if valid_image_file(path):
            return path
    return None


def game_has_cover(g):
    """Count images that actually exist; a stale URL isn't a downloaded cover."""
    return bool(any(valid_image_file(p) for p in
                    (g.get('custom_cover'), g.get('local_cover'))) or cached_cover(g['id']))


def cache_cover_bytes(gid, content, extension='.png', replace=False):
    if not re.fullmatch(r'[0-9a-f]{16}', str(gid)) or extension not in COVER_EXTENSIONS:
        return False
    if not content or len(content) < 256:
        return False
    if extension == '.png' and not content.startswith(b'\x89PNG\r\n\x1a\n'):
        return False
    if extension == '.jpg' and not content.startswith(b'\xff\xd8\xff'):
        return False
    if cached_cover(gid) and not replace:
        return True
    try:
        COVER_CACHE.mkdir(parents=True, exist_ok=True)
        target = COVER_CACHE / (gid + extension)
        tmp = target.with_suffix(extension + '.partial')
        tmp.write_bytes(content)
        os.replace(tmp, target)
        for ext in COVER_EXTENSIONS:
            old = COVER_CACHE / (gid + ext)
            if old != target and old.exists():
                old.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def cache_cover_urls(gid, urls, *, replace=False, errors=None):
    """Download/copy the FIRST valid result to disk; report failures explicitly."""
    if cached_cover(gid) and not replace:
        return True
    for url in dict.fromkeys(urls):
        if not url or not str(url).startswith('https://'):
            continue
        try:
            content, extension = metadata.image_bytes(url, timeout=11)
            if cache_cover_bytes(gid, content, extension, replace=replace):
                return True
            raise OSError('Unable to save artwork in your Windows cover cache')
        except Exception as exc:
            if errors is not None:
                from urllib.parse import urlsplit
                domain = urlsplit(url).hostname or 'image source'
                errors.append(f'{domain}: {str(exc)[:100]}')
    return False



def import_inbox_cover(g, *, replace_icon=False):
    """Optionally import a real image keyed by exact game name or title ID.

    This is a one-folder fallback; no game files or supplied cover are moved.
    Covers are copied to the local cache and kept across app updates.
    """
    gid = g.get('id', '')
    if (not replace_icon) and cached_cover(gid):
        return False
    if not ARTWORK_INBOX.is_dir():
        return False
    titles = [str(g.get(k) or '') for k in ('custom_title', 'identified_title', 'title')]
    canonical = {canonical_title(t) for t in titles if t}
    title_id = re.sub(r'[^A-Z0-9]', '', str(g.get('title_id') or '').upper())
    if title_id and not re.fullmatch(r'(?:CUSA|PPSA|PCSA|PCAS|PCSH)\d{4,7}', title_id):
        title_id = ''
    try:
        images = [x for x in ARTWORK_INBOX.iterdir() if x.is_file() and x.suffix.lower() in IMAGE_EXTENSIONS][:2000]
    except OSError:
        return False
    matches = []
    for path in images:
        stem_id = re.sub(r'[^A-Z0-9]', '', path.stem.upper())
        if title_id and stem_id in {title_id, title_id + g.get('platform', '').upper()}:
            matches.append((2, path))
        elif canonical_title(path.stem) in canonical and canonical_title(path.stem):
            matches.append((1, path))
    for _, path in sorted(matches, key=lambda pair: -pair[0]):
        try:
            if not valid_image_file(path) or path.stat().st_size > 6_000_000:
                continue
            ext = path.suffix.lower()
            if ext == '.jpeg':
                ext = '.jpg'
            if cache_cover_bytes(gid, path.read_bytes(), ext, replace=replace_icon):
                return True
        except OSError:
            pass
    return False


def find_embedded_pkg_art(g):
    """Find genuine local game icon in the small outer table of PS4-like PKGs.

    A PKG can be 100 GB: this reader only fetches a small index plus icon/SFO.
    Try base games first so updates/DLC aren't mistakenly used as the cover.
    """
    pkg_files = [f for f in g.get('files', []) if
                 Path(f['path']).suffix.lower() == '.pkg']
    pkg_files.sort(key=lambda f: {'Game': 0, 'Update': 1, 'DLC': 2}.get(f['category'], 3))
    details = {}
    for f in pkg_files[:5]:
        result = pkg_art.read_ps4_pkg_details(f['path'])
        if result.get('title') and not details.get('title'):
            details['title'] = result['title']
        if result.get('title_id') and not details.get('title_id'):
            details['title_id'] = result['title_id']
        if result.get('icon'):
            details['icon'] = result['icon']
            break
    return details



def find_archived_art(g):
    """Only inspect small artwork entries inside supported ZIP containers.

    Never extract whole archives or game data and never touch original files.
    """
    zips = [f for f in g.get('files', []) if Path(f['path']).suffix.lower() == '.zip']
    zips.sort(key=lambda f: {'Game': 0, 'Update': 1, 'DLC': 2}.get(f['category'], 3))
    for f in zips[:5]:
        cover = archive_art.read_zip_cover(f['path'])
        if cover.get('icon'):
            return cover
    return {}


def needs_enrichment(g):
    """Retry missing art after upgrading; do not redownload finished covers."""
    if not game_has_cover(g) and not g.get('artwork_v5_checked'):
        return True
    if game_has_cover(g) and g.get('cover_quality') == 'icon' and not g.get('artwork_v5_checked'):
        return True  # One attempt to upgrade square icons to portrait art.
    if not g.get('artwork_v3_checked'):
        return True
    if game_has_cover(g) and (g.get('trailer_url') or not state['settings'].get('auto_trailers', True)):
        # A genuine local icon can still be upgraded to better portrait art by
        # clicking Find Covers, but the automatic loop doesn't overdo it.
        return False
    try:
        checked = datetime.fromisoformat(g['artwork_v3_checked'])
        # Failed matches can be retried next time after an hour; no 72h deadlock.
        return (datetime.now(timezone.utc).astimezone() - checked).total_seconds() > 3600
    except (ValueError, TypeError):
        return True


def reuse_cover_from_library(g, *, strict_id=False):
    """Copy existing valid artwork to another entry for the SAME game.

    The game folders stay entirely read-only. This addresses archive / repack
    variants that were treated as independent game cards by the scanner.
    """
    with KEY_LOCK:
        candidates = artwork_rescue.matching_cover_games(g, state['games'], strict_id=strict_id)
    for other in candidates:
        original = next((p for p in (other.get('custom_cover'), other.get('local_cover'),
                                     cached_cover(other.get('id'))) if valid_image_file(p)), None)
        if not original:
            continue
        try:
            if original.stat().st_size > 6_000_000:
                continue
            ext = original.suffix.lower()
            if ext == '.jpeg':
                ext = '.jpg'
            if cache_cover_bytes(g['id'], original.read_bytes(), extension=ext):
                return {'cover_cached': True, 'cover_quality': other.get('cover_quality') or 'portrait',
                        'source': 'Shared existing artwork', 'matched_name': other.get('title') or '',
                        'source_url': other.get('source_url') or '', 'cover_revision': int(time.time())}
        except OSError:
            continue
    return {}



def repair_cached_duplicate_covers():
    """Offline cover fix: attach existing art to uncovered entries with exact PS IDs.

    This operation NEVER reads/writes PKGs, RARs or other game content; the
    image is copied from another entry's working image or our own cache.
    Same platform AND identical non-empty CUSA/PPSA ID are required; it
    intentionally does not guess near-title matches or overwrite any cover.

    Re-run it at launch and after every rescan so variants scanned later also
    benefit, without waiting for slow/rate-limited artwork providers.
    """
    repaired = []
    with KEY_LOCK:
        for target in state['games']:
            if game_has_cover(target):
                continue
            tid = re.sub(r'[^A-Z0-9]', '', str(target.get('title_id') or '').upper())
            if not re.fullmatch(r'(?:CUSA|PPSA|PCSA|PCAS|PCSH)\d{4,7}', tid):
                continue
            target_platform = target.get('platform')
            donor = None
            donor_image = None
            for candidate in state['games']:
                if candidate is target or candidate.get('id') == target.get('id'):
                    continue
                donor_tid = re.sub(r'[^A-Z0-9]', '', str(candidate.get('title_id') or '').upper())
                if donor_tid != tid or candidate.get('platform') != target_platform:
                    continue
                for path in (candidate.get('custom_cover'), candidate.get('local_cover'),
                             cached_cover(candidate.get('id'))):
                    if valid_image_file(path):
                        donor, donor_image = candidate, Path(path)
                        break
                if donor_image:
                    break
            if donor_image is None:
                continue
            # A cache file cannot be larger than the image accepted by the
            # app's existing metadata downloader; never copy game archives.
            try:
                if donor_image.stat().st_size > 6_000_000:
                    continue
                extension = donor_image.suffix.lower().replace('.jpeg', '.jpg')
                if extension not in COVER_EXTENSIONS:
                    continue
                payload = donor_image.read_bytes()
                # cache_cover_bytes independently checks the content/header.
                if not cache_cover_bytes(target['id'], payload, extension=extension):
                    continue
                target['cover_cached'] = True
                target['cover_quality'] = donor.get('cover_quality') or 'portrait'
                target['source'] = 'Shared existing artwork (exact PlayStation ID)'
                target['matched_name'] = donor.get('custom_title') or donor.get('title') or ''
                target['cover_error'] = ''
                target['cover_revision'] = int(time.time())
                target['artwork_v5_checked'] = now_iso()
                repaired.append((target.get('title', ''), tid))
            except (OSError, KeyError, ValueError):
                continue
        if repaired:
            save_state()
    return repaired


def lookup_enrichment(g, settings, publish_cover=False, artwork_only=False):
    """Read local PKG icon first, then attempt multiple portrait-art providers.

    All covers are stored on the computer rather than hotlinked in the browser.
    A missing cover, server rejection, or offline machine is visible in a report.
    """
    found, errs, cover_errs = {}, [], []
    gid = g['id']
    manual_local = any(valid_image_file(p) for p in (g.get('custom_cover'), g.get('local_cover')))
    previously_cached = bool(cached_cover(gid))
    # Cover Inbox has highest priority for fixes the user has deliberately
    # named to this title or CUSA/PPSA ID.
    if not manual_local and import_inbox_cover(g, replace_icon=g.get('cover_quality') == 'icon'):
        previously_cached = True
        found.update(cover_cached=True, cover_quality='portrait',
                     source='Cover Inbox (local)', cover_revision=int(time.time()))
    embedded = {}
    if not manual_local:
        # A recovered internal title can fix a bad filename even when a square
        # icon has already been downloaded. Reads only small PKG header items.
        try:
            embedded = find_embedded_pkg_art(g)
            if not previously_cached and embedded.get('icon') and cache_cover_bytes(gid, embedded['icon']):
                found.update(cover_cached=True, cover_quality='icon', source='PKG icon (local)',
                             cover_revision=int(time.time()))
        except Exception as exc:
            cover_errs.append('Local PKG: ' + str(exc)[:95])
        # When PKG artwork is missing or unsupported, check inside ZIP archives
        # for a small cover/icon without unpacking any game files.
        if not previously_cached and not cached_cover(gid):
            try:
                inside = find_archived_art(g)
                if inside.get('icon') and cache_cover_bytes(gid, inside['icon']):
                    found.update(cover_cached=True, cover_quality=inside['cover_quality'],
                                 source=inside['source'], cover_revision=int(time.time()))
            except Exception as exc:
                cover_errs.append('ZIP artwork: ' + str(exc)[:95])
    title = str(g.get('custom_title') or g.get('identified_title') or embedded.get('title') or g.get('title') or '').strip()
    if embedded.get('title') and not g.get('custom_title'):
        found['identified_title'] = embedded['title']
        title = embedded['title']
    has_cover = manual_local or bool(cached_cover(gid))
    is_icon = (found.get('cover_quality') == 'icon' or
               (g.get('cover_quality') == 'icon' and not found.get('cover_quality') == 'portrait'))

    # The user's manually specified URL always gets the first download attempt.
    if not manual_local and g.get('manual_cover_url') and g.get('cover_url'):
        if cache_cover_urls(gid, [g['cover_url']], replace=is_icon, errors=cover_errs):
            found.update(cover_cached=True, cover_quality='portrait',
                         cover_revision=int(time.time()), source='User cover URL')
            has_cover, is_icon = True, False

    if not manual_local and not g.get('manual_cover_url') and g.get('cover_url') and not has_cover:
        if cache_cover_urls(gid, [g['cover_url']], errors=cover_errs):
            found.update(cover_cached=True, cover_quality='portrait', cover_revision=int(time.time()))
            has_cover = True

    # v2.3 rescue pass #1: a second archive or duplicate with the same
    # PlayStation title ID can reuse a cached cover immediately without any API.
    if not manual_local and not has_cover:
        shared = reuse_cover_from_library(g, strict_id=True)
        if shared:
            found.update(shared)
            has_cover = True

    # v2.3 rescue pass #2: curated official PlayStation game pages for entries
    # whose scene/repack/update names defeat normal title searches.
    # Importantly, we download and verify actual images; HTML/404 never counts.
    if not manual_local and not has_cover and not g.get('manual_cover_url'):
        if artwork_rescue.verified_match(g):
            # Use a verified direct Sony cover image first. Only if the image
            # fails do we request the HTML page (which can be rate-limited).
            sources = []
            direct = artwork_rescue.direct_verified_cover(g)
            if direct:
                sources.append(direct)
            if sources:
                result = sources[0]
                if cache_cover_urls(gid, result.get('cover_candidates', []), errors=cover_errs):
                    found.update({k: v for k, v in result.items() if k != 'cover_candidates'})
                    found.update(cover_cached=True, cover_quality='portrait',
                                 cover_revision=int(time.time()))
                    has_cover, is_icon = True, False
            if not has_cover:
                try:
                    result = artwork_rescue.fetch_official_images(g)
                    if cache_cover_urls(gid, result.get('cover_candidates', []), errors=cover_errs):
                        found.update({k: v for k, v in result.items() if k != 'cover_candidates'})
                        found.update(cover_cached=True, cover_quality='portrait',
                                     cover_revision=int(time.time()))
                        has_cover, is_icon = True, False
                except Exception as exc:
                    cover_errs.append('Official PlayStation artwork: ' + str(exc)[:105])

    # v2.3 rescue pass #3: share artwork with an unambiguously named base game.
    # Edition/release-group suffixes do not create a different underlying game.
    if not manual_local and not has_cover:
        shared = reuse_cover_from_library(g)
        if shared:
            found.update(shared)
            has_cover = True

    # A local PKG icon is a perfectly good recognition thumbnail, but try to
    # upgrade it to a proper portrait game-box image when public services work.
    if not manual_local and (not has_cover or is_icon):
        providers = []
        if g.get('platform') == 'PS4':
            providers.append(('PS4 boxart archive', lambda: metadata.find_libretro_cover(
                title, DATA_HOME / 'libretro_ps4_catalog.json')))
        providers.append(('Steam Store', lambda: metadata.find_steam_art(title)))
        providers.append(('GOG store', lambda: metadata.find_gog_cover(title)))
        if settings.get('steamgriddb_key'):
            providers.append(('SteamGridDB', lambda: find_art_steamgrid(title, settings['steamgriddb_key'])))
        if settings.get('rawg_key'):
            providers.append(('RAWG', lambda: find_art_rawg(title, settings['rawg_key'])))
        if settings.get('wiki_fallback', True):
            providers.append(('Wikipedia', lambda: find_art_wikipedia(title)))
        for provider_name, callback in providers:
            try:
                result = callback()
                candidates = list(result.get('cover_candidates') or [])
                if result.get('cover_url'):
                    candidates.append(result['cover_url'])
                if not candidates:
                    continue
                if cache_cover_urls(gid, candidates, replace=is_icon, errors=cover_errs):
                    found.update({k: v for k, v in result.items() if k != 'cover_candidates'})
                    found.update(cover_cached=True, cover_quality='portrait',
                                 cover_revision=int(time.time()))
                    if not result.get('cover_url'):
                        found['cover_url'] = candidates[0]
                    has_cover, is_icon = True, False
                    break
            except Exception as exc:
                cover_errs.append(f'{provider_name}: {str(exc)[:100]}')

    if publish_cover:
        # Cover tiles update immediately as each file is cached, even when a
        # site's trailer search is very slow or temporarily unavailable.
        partial = {k: v for k, v in found.items() if k in (
            'cover_cached', 'cover_quality', 'source', 'source_url', 'cover_revision',
            'cover_url', 'matched_name', 'identified_title')}
        if partial:
            apply_enrichment(g, partial)
    if not artwork_only and settings.get('auto_trailers', True) and not g.get('trailer_url'):
        try:
            yt = metadata.find_public_youtube_trailer(title, g.get('platform', 'PS5'))
            if yt:
                found['trailer_url'] = 'https://www.youtube.com/watch?v=' + yt
                found['trailer_source'] = 'YouTube search'
        except Exception as exc:
            errs.append('YouTube search: ' + str(exc)[:85])
        if not found.get('trailer_url') and settings.get('youtube_key'):
            try:
                yt = find_youtube_trailer(title, settings['youtube_key'])
                if yt:
                    found['trailer_url'] = yt
                    found['trailer_source'] = 'YouTube Data API'
            except Exception as exc:
                errs.append('YouTube API: ' + str(exc)[:85])

    found['artwork_v5_checked'] = now_iso()
    found['artwork_v4_checked'] = found['artwork_v5_checked']
    found['artwork_v3_checked'] = found['artwork_v4_checked']
    found['metadata_checked'] = found['artwork_v3_checked']
    found['cover_error'] = '; '.join(dict.fromkeys(cover_errs))[:620]
    found['metadata_error'] = '; '.join(errs)[:260]
    if not has_cover and not found['cover_error']:
        found['cover_error'] = 'No confident artwork match was found for this filename.'
    return found


def apply_enrichment(g, result):
    with KEY_LOCK:
        target = next((x for x in state['games'] if x['id'] == g['id']), None)
        if not target:
            return
        for k, v in result.items():
            if k in ('cover_url', 'source', 'source_url', 'matched_name', 'cover_cached') and (target.get('custom_cover') or target.get('local_cover') or target.get('manual_cover_url')):
                continue
            if k in ('trailer_url', 'trailer_source') and target.get('trailer_url') and not g.get('trailer_url'):
                continue
            if v or k in ('artwork_v2_checked', 'artwork_v3_checked', 'artwork_v4_checked', 'artwork_v5_checked', 'metadata_checked', 'metadata_error', 'cover_error'):
                target[k] = v
        if cached_cover(g['id']):
            target['cover_cached'] = True
        save_state()


def enrich_one(g, artwork_only=False):
    with KEY_LOCK:
        if g['id'] in on_demand_ids:
            return None
        on_demand_ids.add(g['id'])
    try:
        result = lookup_enrichment(g, state['settings'].copy(), publish_cover=True, artwork_only=artwork_only)
        apply_enrichment(g, result)
        return result
    finally:
        with KEY_LOCK:
            on_demand_ids.discard(g['id'])


def enrich_worker(only_id=None, force=False, missing_only=False, artwork_only=False):
    global enrich_running
    try:
        with KEY_LOCK:
            pending = [g.copy() for g in state['games'] if
                       (not only_id or g['id'] == only_id) and
                       (not missing_only or not game_has_cover(g)) and
                       (force or only_id or needs_enrichment(g))]
            enrich_progress.update({'running': bool(pending), 'done': 0,
                                    'total': len(pending), 'errors': [],
                                    'message': 'Searching missing covers...' if missing_only else 'Matching covers and trailers in the background...'})
        if pending:
            with ThreadPoolExecutor(max_workers=4, thread_name_prefix='game-art') as executor:
                futures = {executor.submit(enrich_one, g, artwork_only): g for g in pending}
                for i, future in enumerate(as_completed(futures), 1):
                    g = futures[future]
                    try:
                        result = future.result() or {}
                        if result.get('cover_error') and not cached_cover(g['id']):
                            # Missing artwork / network issues are visible in a cover report.
                            with KEY_LOCK:
                                enrich_progress['errors'].append(g['title'] + ': ' + result['cover_error'][:190])
                    except Exception as exc:
                        with KEY_LOCK:
                            enrich_progress['errors'].append(g['title'] + ': ' + str(exc)[:130])
                    with KEY_LOCK:
                        enrich_progress['done'] = i
                        enrich_progress['message'] = f'Processed {i} of {len(pending)} games — {g["title"]}'
        with KEY_LOCK:
            cover_count = sum(game_has_cover(x) for x in state['games'])
            total_count = len(state['games'])
            enrich_progress.update({'running': False, 'message': (
                f'Artwork ready for {cover_count} of {total_count} games. '
                f'{total_count - cover_count} still unmatched.')})
    except Exception as exc:
        with KEY_LOCK:
            enrich_progress.update({'running': False, 'message': 'Artwork matching interrupted',
                                    'errors': [str(exc)]})
    finally:
        with KEY_LOCK:
            enrich_running = False


def urgent_enrich_worker(g):
    try:
        enrich_one(g)
    except Exception as exc:
        print('[artwork] Immediate lookup failed:', exc)


def start_enrich(only_id=None, force=False, missing_only=False, artwork_only=False):
    global enrich_running
    with KEY_LOCK:
        if only_id:
            g = next((x.copy() for x in state['games'] if x['id'] == only_id), None)
            if not g or only_id in on_demand_ids:
                return False
            threading.Thread(target=urgent_enrich_worker, args=(g,), daemon=True).start()
            return True
        if enrich_running:
            return False
        enrich_running = True
    threading.Thread(target=enrich_worker, args=(None, force, missing_only, artwork_only), daemon=True).start()
    return True


def allowed_path(path):
    try:
        requested = Path(path).resolve()
        with KEY_LOCK:
            roots = [Path(x['path']).resolve() for x in state['folders']]
        return any(requested == r or requested.is_relative_to(r) for r in roots)
    except (ValueError, OSError):
        return False


def explorer_open(path):
    path = Path(path)
    if not allowed_path(path) or not path.exists():
        raise ValueError('Path is not in a configured library folder')
    if sys.platform == 'win32':
        if path.is_file():
            subprocess.Popen(['explorer.exe', '/select,', str(path)])
        else:
            os.startfile(str(path))
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', '-R', str(path)])
    else:
        subprocess.Popen(['xdg-open', str(path if path.is_dir() else path.parent)])


def folder_dialog():
    try:
        import tkinter as tk
        from tkinter import filedialog
        master = tk.Tk()
        master.withdraw()
        master.attributes('-topmost', True)
        dirname = filedialog.askdirectory(title='Choose your PS4 or PS5 games folder', mustexist=True)
        master.destroy()
        return dirname
    except Exception:
        return ''


def image_dialog():
    try:
        import tkinter as tk
        from tkinter import filedialog
        master = tk.Tk()
        master.withdraw()
        master.attributes('-topmost', True)
        name = filedialog.askopenfilename(title='Select game cover image', filetypes=[('Image files', '*.png *.jpg *.jpeg *.webp *.gif')])
        master.destroy()
        return name
    except Exception:
        return ''


class Handler(BaseHTTPRequestHandler):
    server_version = 'SAC23GameLibrary/2.4'

    def local_request_error(self, writing=False):
        """Protect the loopback interface against cross-origin writes / DNS rebinding."""
        port = self.server.server_address[1]
        if self.headers.get('Host', '').strip().lower() not in {
            f'127.0.0.1:{port}', f'localhost:{port}'
        }:
            return 'Requests must be addressed to the local game library'
        origin = self.headers.get('Origin')
        if origin:
            try:
                parsed_origin = urlparse(origin)
                if (parsed_origin.scheme != 'http' or
                    parsed_origin.hostname not in ('127.0.0.1', 'localhost') or
                    parsed_origin.port != port):
                    return 'Cross-origin requests are not allowed'
            except ValueError:
                return 'Invalid request origin'
        if writing and self.headers.get('Content-Type','').split(';',1)[0].strip().lower() != 'application/json':
            return 'This API only accepts JSON requests'
        return None

    def security_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Cross-Origin-Resource-Policy', 'same-origin')

    def log_message(self, fmt, *args):
        if not self.path.startswith('/api/status'):
            print('[web]', fmt % args)

    def json_response(self, obj, status=200):
        data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.security_headers()
        self.end_headers()
        self.wfile.write(data)

    def bad(self, message, status=400):
        self.json_response({'ok': False, 'error': message}, status)

    def read_json(self):
        length = int(self.headers.get('Content-Length', '0'))
        if length > 1_000_000:
            raise ValueError('Request too large')
        if not length:
            return {}
        parsed = json.loads(self.rfile.read(length).decode('utf8'))
        if not isinstance(parsed, dict):
            raise ValueError('Expected JSON object')
        return parsed

    def serve_file(self, filename, mime=None):
        try:
            with open(filename, 'rb') as f:
                contents = f.read()
            self.send_response(200)
            self.send_header('Content-Type', mime or mimetypes.guess_type(str(filename))[0] or 'application/octet-stream')
            self.send_header('Content-Length', str(len(contents)))
            self.send_header('Cache-Control', 'private, max-age=120')
            self.security_headers()
            self.end_headers()
            self.wfile.write(contents)
        except OSError:
            self.send_error(404)

    def do_GET(self):
        error = self.local_request_error()
        if error:
            return self.bad(error, 403)
        parsed = urlparse(self.path)
        pathname = parsed.path
        with KEY_LOCK:
            if pathname == '/api/library':
                public_games = state['games']
                stats = {'games': len(public_games), 'ps4': sum(x['platform'] == 'PS4' for x in public_games), 'ps5': sum(x['platform'] == 'PS5' for x in public_games), 'unknown': sum(x['platform'] == 'UNKNOWN' for x in public_games), 'files': sum(x.get('file_count', 0) for x in public_games), 'bytes': sum(x.get('size', 0) for x in public_games), 'favorites': sum(bool(x.get('favorite')) for x in public_games), 'covers': sum(game_has_cover(x) for x in public_games), 'trailers': sum(bool(x.get('trailer_url')) for x in public_games)}
                return self.json_response({'ok': True, 'games': [{**g, 'cover_cached': bool(cached_cover(g['id'])), 'cover_available': game_has_cover(g)} for g in public_games], 'stats': stats, 'folders': state['folders'], 'last_scan': state['last_scan'], 'version': APP_VERSION})
            if pathname == '/api/status':
                return self.json_response({'ok': True, 'scan': scan_progress.copy(), 'enrich': enrich_progress.copy(), 'active_lookups': list(on_demand_ids), 'revision': state_revision})
            if pathname == '/api/settings':
                return self.json_response({'ok': True, 'settings': state['settings']})
        if pathname.startswith('/api/image/'):
            gid = pathname.rsplit('/', 1)[-1]
            with KEY_LOCK:
                g = next((x for x in state['games'] if x['id'] == gid), None)
            if not g:
                return self.send_error(404)
            candidate = next((p for p in (g.get('custom_cover'), g.get('local_cover'), cached_cover(gid)) if valid_image_file(p)), None)
            if not candidate:
                return self.send_error(404)
            # For a custom cover selected by the file dialog, permit image paths outside library roots.
            return self.serve_file(Path(candidate))
        if pathname == '/api/cover-report':
            with KEY_LOCK:
                report = {
                    'created_at': now_iso(),
                    'version': APP_VERSION,
                    'total': len(state['games']),
                    'covered': sum(game_has_cover(x) for x in state['games']),
                    'games': [{'title': x.get('custom_title') or x['title'],
                               'embedded_title': x.get('identified_title', ''),
                               'title_id': x.get('title_id', ''),
                               'platform': x['platform'],
                               'has_cover': game_has_cover(x),
                               'source': x.get('source', ''),
                               'error': x.get('cover_error', ''),
                               'last_checked': x.get('artwork_v4_checked', ''),
                               'filename_samples': [Path(f['path']).name for f in x.get('files', [])[:3]]}
                              for x in state['games']]
                }
                payload = json.dumps(report, indent=2, ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Disposition', 'attachment; filename="SAC23_Cover_Report.json"')
            self.send_header('Content-Length', str(len(payload)))
            self.security_headers()
            self.end_headers()
            return self.wfile.write(payload)
        if pathname == '/api/export':
            with KEY_LOCK:
                result = json.dumps({'exported_at': now_iso(), 'games': state['games']}, indent=2, ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Disposition', 'attachment; filename="SAC23_Game_Library_Export.json"')
            self.send_header('Content-Length', str(len(result)))
            self.security_headers()
            self.end_headers()
            return self.wfile.write(result)
        if pathname in ('/', '/index.html'):
            pathname = '/index.html'
        # Whitelist exact frontend resources; no traversal.
        allowed = {'/index.html', '/styles.css', '/app.js'}
        if pathname in allowed:
            filepath = WEB_HOME / pathname.lstrip('/')
            return self.serve_file(filepath, mimetypes.guess_type(str(filepath))[0] or 'text/plain')
        return self.send_error(404)

    def do_POST(self):
        error = self.local_request_error(writing=True)
        if error:
            return self.bad(error, 403)
        parsed = urlparse(self.path)
        route = parsed.path
        try:
            body = self.read_json()
            if route == '/api/cover-inbox/open':
                ARTWORK_INBOX.mkdir(parents=True, exist_ok=True)
                if sys.platform == 'win32':
                    os.startfile(str(ARTWORK_INBOX))
                else:
                    # No browser exposure / arbitrary paths. Convenience only.
                    pass
                return self.json_response({'ok': True, 'path': str(ARTWORK_INBOX)})
            if route == '/api/folders/browse':
                return self.json_response({'ok': True, 'path': folder_dialog()})
            if route == '/api/cover/browse':
                return self.json_response({'ok': True, 'path': image_dialog()})
            if route == '/api/folders/add':
                name = str(body.get('path') or '').strip().strip('"')
                platform = str(body.get('platform') or 'AUTO').upper()
                if platform not in ('AUTO', 'PS4', 'PS5'):
                    return self.bad('Select Auto, PS4 or PS5')
                if not name or not os.path.isdir(name):
                    return self.bad('That folder does not exist or is not accessible on this computer')
                name = os.path.normpath(os.path.abspath(name))
                with KEY_LOCK:
                    if any(os.path.normcase(os.path.normpath(x['path'])) == os.path.normcase(name) for x in state['folders']):
                        return self.bad('That folder is already in your library')
                    state['folders'].append({'id': uuid.uuid4().hex[:12], 'path': name, 'platform': platform})
                    save_state()
                start_scan()
                return self.json_response({'ok': True, 'folders': state['folders']})
            if route == '/api/folders/remove':
                with KEY_LOCK:
                    before = len(state['folders'])
                    state['folders'] = [x for x in state['folders'] if x['id'] != body.get('id')]
                    if len(state['folders']) == before:
                        return self.bad('Folder not found', 404)
                    save_state()
                start_scan()
                return self.json_response({'ok': True})
            if route == '/api/scan':
                return self.json_response({'ok': True, 'started': start_scan()})
            if route == '/api/enrich':
                # This action first checks exact PS IDs against cached covers.
                # No internet/API key required, so previously known games fill instantly.
                fixed_now = repair_cached_duplicate_covers()
                gid = str(body.get('id') or '')
                if gid:
                    with KEY_LOCK:
                        if not any(x['id'] == gid for x in state['games']):
                            return self.bad('Game not found', 404)
                return self.json_response({'ok': True, 'reused_local_covers': len(fixed_now),
                    'started': start_enrich(
                    gid or None, force=bool(body.get('force', False)),
                    missing_only=bool(body.get('missing_only', False)),
                    artwork_only=bool(body.get('artwork_only', False)))})
            if route == '/api/settings':
                with KEY_LOCK:
                    for k in ('steamgriddb_key', 'rawg_key', 'youtube_key'):
                        if k in body:
                            val = str(body[k]).strip()
                            if len(val) > 300:
                                return self.bad('API key too long')
                            state['settings'][k] = val
                    for flag in ('wiki_fallback', 'auto_artwork', 'auto_trailers'):
                        if flag in body:
                            state['settings'][flag] = bool(body[flag])
                    save_state()
                return self.json_response({'ok': True})
            if route == '/api/game/update':
                gid = str(body.get('id') or '')
                with KEY_LOCK:
                    g = next((x for x in state['games'] if x['id'] == gid), None)
                    if not g:
                        return self.bad('Game not found', 404)
                    for field in ('custom_title', 'cover_url', 'custom_cover', 'trailer_url', 'description', 'genre', 'year'):
                        if field in body:
                            val = str(body[field]).strip()[:1000]
                            if field == 'cover_url' and val and not val.startswith(('http://', 'https://')):
                                return self.bad('Cover URL must begin with http:// or https://')
                            if field == 'custom_cover' and val and (not Path(val).is_file() or Path(val).suffix.lower() not in IMAGE_EXTENSIONS):
                                return self.bad('Cover image file not found')
                            if field == 'cover_url' and val != g.get('cover_url', ''):
                                g['manual_cover_url'] = bool(val)
                                oldcache = cached_cover(gid)
                                if oldcache:
                                    oldcache.unlink(missing_ok=True)
                            g[field] = val
                    if 'favorite' in body:
                        g['favorite'] = bool(body['favorite'])
                    save_state()
                return self.json_response({'ok': True, 'game': g})
            if route == '/api/open':
                wanted = str(body.get('path') or '')
                if not wanted:
                    return self.bad('No path specified')
                explorer_open(wanted)
                return self.json_response({'ok': True})
            return self.bad('Unknown API route', 404)
        except (ValueError, json.JSONDecodeError) as e:
            return self.bad(str(e))
        except OSError as e:
            return self.bad(str(e), 500)
        except Exception as e:
            return self.bad(f'{type(e).__name__}: {e}', 500)


def run(port=0, no_browser=False):
    # Immediate, offline repair using the user's already-downloaded images.
    repaired = repair_cached_duplicate_covers()
    if repaired:
        print(f'[covers] Repaired {len(repaired)} missing duplicates from your saved artwork')
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    url = f'http://127.0.0.1:{server.server_address[1]}'
    print(f'\n  {APP_NAME} v{APP_VERSION}')
    print(f'  Open: {url}')
    print(f'  Library data: {DATA_FILE}')
    print(f'  Close this window or press Ctrl+C to stop.\n')
    if state['folders']:
        start_scan()
    elif state['games'] and state['settings'].get('auto_artwork', True):
        start_enrich()
    if not no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=APP_NAME)
    ap.add_argument('--port', type=int, default=0, help='Local port (0=automatic)')
    ap.add_argument('--no-browser', action='store_true')
    args = ap.parse_args()
    run(args.port, args.no_browser)
