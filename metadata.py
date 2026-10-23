"""Artwork and trailer matching for SAC23 Game Library v2.

Everything is best-effort public metadata. No game package contents are modified.
Uses official public Steam Store search, Steam CDN library covers, Wikipedia,
and publicly viewable YouTube search results (subject to provider availability).
"""
from __future__ import annotations

from difflib import SequenceMatcher
from html import unescape
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from threading import RLock
import time
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

BROWSER_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
)


def normalize(text):
    text = (text or '').casefold().replace('’', "'")
    text = re.sub(r'\b(?:playstation|ps4|ps5|base game|full game|usa|eur|update|dlc|pkg)\b', ' ', text)
    return ' '.join(re.findall(r'[\w]+', text))


def similarity(wanted, result):
    a, b = normalize(wanted), normalize(result)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    # Avoid pairing games with sequels or DLC just because first words match.
    a_words, b_words = set(a.split()), set(b.split())
    tok = len(a_words & b_words) / max(len(a_words | b_words), 1)
    seq = SequenceMatcher(None, a, b).ratio()
    return round(0.62 * seq + 0.38 * tok, 4)


def request_bytes(url, timeout=9, limit=3_200_000, accept='*/*'):
    headers = {'User-Agent': BROWSER_UA, 'Accept': accept, 'Accept-Language': 'en-US,en;q=0.9'}
    req = Request(url, headers=headers)
    with urlopen(req, timeout=timeout) as res:
        if (res.headers.get('Content-Length') or '').isdigit() and int(res.headers['Content-Length']) > limit:
            raise ValueError('Response too large')
        content = res.read(limit + 1)
        if len(content) > limit:
            raise ValueError('Response too large')
        return content, res.headers.get('Content-Type', '')


def get_json(url, timeout=9):
    content, _ = request_bytes(url, timeout=timeout, accept='application/json')
    return json.loads(content.decode('utf-8-sig'))


def steam_cover_candidates(app_id):
    # Multiple known CDNs and sizes. Not every game supplies portrait artwork.
    prefix = 'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/'
    legacy = 'https://cdn.cloudflare.steamstatic.com/steam/apps/'
    return [
        f'{prefix}{app_id}/library_600x900_2x.jpg',
        f'{prefix}{app_id}/library_600x900.jpg',
        f'{legacy}{app_id}/library_600x900_2x.jpg',
        f'{legacy}{app_id}/library_600x900.jpg',
    ]


def find_steam_art(title):
    """Returns candidates, not unverified art; the caller must download a real image."""
    if len(normalize(title)) < 3:
        return {}
    # Start with full title, then drop the trailing edition if needed.
    variations = [title]
    short = re.sub(r'(?i)\s+(?:deluxe|ultimate|gold|complete|standard|game of the year|goty)\s+edition$', '', title).strip()
    if short and short != title:
        variations.append(short)
    best = None
    for query in variations:
        url = 'https://store.steampowered.com/api/storesearch/?' + urlencode({
            'term': query, 'l': 'english', 'cc': 'US'
        })
        results = get_json(url, timeout=9).get('items') or []
        valid = [x for x in results if x.get('type', 'app') == 'app' and x.get('id') and x.get('name')]
        if not valid:
            continue
        ranked = sorted(valid, key=lambda x: similarity(title, x['name']), reverse=True)
        if not best or similarity(title, ranked[0]['name']) > similarity(title, best['name']):
            best = ranked[0]
        if similarity(title, best['name']) >= .83:
            break
    if best and similarity(title, best['name']) >= .78:
        app_id = int(best['id'])
        return {
            'cover_candidates': steam_cover_candidates(app_id),
            'source': 'Steam',
            'source_url': f'https://store.steampowered.com/app/{app_id}/',
            'matched_name': best['name'],
            'confidence': similarity(title, best['name']),
        }
    return {}


# No API key required. The public libretro thumbnail repository has a PS4
# Named_Boxarts set. Cache the file manifest and download only good matches.
_libretro_lock = RLock()
_libretro_files = None
_libretro_error = None
_libretro_retry_at = 0.0


def libretro_cover_catalog(cache_path):
    global _libretro_files, _libretro_error, _libretro_retry_at
    with _libretro_lock:
        if _libretro_files is not None:
            return _libretro_files
        if _libretro_error is not None and time.monotonic() < _libretro_retry_at:
            raise RuntimeError(_libretro_error)
        cache_path = Path(cache_path)
        if cache_path.is_file():
            try:
                saved = json.loads(cache_path.read_text(encoding='utf8'))
                age = datetime.now(timezone.utc).timestamp() - float(saved.get('checked_at', 0))
                if 0 <= age < 30 * 86400 and isinstance(saved.get('files'), list):
                    _libretro_files = saved['files']
                    return _libretro_files
            except (OSError, ValueError, TypeError):
                pass
        url = 'https://api.github.com/repos/libretro-thumbnails/Sony_-_PlayStation_4/git/trees/master?recursive=1'
        try:
            data = get_json(url, timeout=8)
        except Exception as exc:
            _libretro_error = f'Public PS4 artwork catalog unavailable: {str(exc)[:120]}'
            _libretro_retry_at = time.monotonic() + 90
            raise RuntimeError(_libretro_error) from exc
        if data.get('truncated'):
            raise ValueError('PS4 cover catalog incomplete; retry later')
        names = [item['path'].split('/', 1)[1] for item in data.get('tree', [])
                 if item.get('type') == 'blob' and item.get('path', '').startswith('Named_Boxarts/')
                 and item['path'].lower().endswith('.png')]
        if not names:
            raise ValueError('PS4 cover catalog is unavailable')
        _libretro_files = names
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = cache_path.with_suffix('.tmp')
            tmp.write_text(json.dumps({'checked_at': datetime.now(timezone.utc).timestamp(),
                                       'files': names}), encoding='utf8')
            tmp.replace(cache_path)
        except OSError:
            pass
        return names


def find_libretro_cover(title, cache_path):
    """Return high-confidence PS4 boxart from Libretro's public image archive."""
    names = libretro_cover_catalog(cache_path)
    if not names:
        return {}
    # Region suffixes, punctuation, and versions are discarded for comparison.
    ranked = []
    for file_name in names:
        display_name = re.sub(r'\s*\([^)]*\)', ' ', file_name[:-4]).replace('_', ' ').strip()
        score = similarity(title, display_name)
        ranked.append((score, file_name, display_name))
    score, filename, matched = max(ranked, default=(0, '', ''))
    if score < .84:
        return {}
    url = ('https://raw.githubusercontent.com/libretro-thumbnails/Sony_-_PlayStation_4/'
           'master/Named_Boxarts/' + quote(filename))
    return {'cover_candidates': [url], 'source': 'Libretro PS4 Boxarts',
            'source_url': 'https://github.com/libretro-thumbnails/Sony_-_PlayStation_4',
            'matched_name': matched, 'confidence': score}



def find_gog_cover(title):
    """Extra key-free *portrait* source for titles also sold by GOG.

    A conservative similarity threshold prevents borrowing a cover from a
    similarly named unrelated game. Console exclusives may be absent entirely.
    """
    name = (title or '').strip()
    if len(normalize(name)) < 4:
        return {}
    url = 'https://catalog.gog.com/v1/catalog?' + urlencode({
        'query': 'like:' + name, 'limit': 15, 'page': 1,
        'productType': 'in:game,pack', 'locale': 'en-US', 'countryCode': 'US'
    })
    result = get_json(url, timeout=9)
    products = result.get('products') or []
    ranked = sorted((p for p in products if isinstance(p, dict) and p.get('title')),
                    key=lambda p: similarity(name, p['title']), reverse=True)
    for product in ranked[:4]:
        score = similarity(name, product['title'])
        # Try only confidently equivalent game names; an incorrect cover is
        # worse than a missing one.
        if score < .90:
            continue
        images = product.get('covers') or {}
        art = images.get('vertical') if isinstance(images, dict) else None
        art = art or product.get('coverVertical')
        if not isinstance(art, str) or not art:
            continue
        if art.startswith('//'):
            art = 'https:' + art
        if not art.startswith('https://'):
            continue
        return {'cover_candidates': [art], 'source': 'GOG catalog',
                'source_url': product.get('store_url') or '',
                'matched_name': product['title'], 'confidence': score}
    return {}


def _all_yt_renderers(obj):
    if isinstance(obj, dict):
        for key in ('videoRenderer', 'gridVideoRenderer', 'compactVideoRenderer'):
            if key in obj and isinstance(obj[key], dict):
                yield obj[key]
        # Walk all because YouTube nests renderers in multiple result layouts.
        for val in obj.values():
            yield from _all_yt_renderers(val)
    elif isinstance(obj, list):
        for v in obj:
            yield from _all_yt_renderers(v)


def _yt_text(item):
    if isinstance(item, dict):
        if 'simpleText' in item:
            return item['simpleText']
        return ''.join(x.get('text', '') for x in (item.get('runs') or []) if isinstance(x, dict))
    return ''


def parse_youtube_search(html, wanted):
    """Extracts and ranks videoRenderer matches from a public search HTML page."""
    prefix = re.search(r'(?:var\s+ytInitialData\s*=|window\["ytInitialData"\]\s*=|ytInitialData\s*=)\s*', html)
    if not prefix:
        return ''
    idx = html.find('{', prefix.end())
    if idx == -1:
        return ''
    try:
        document, _ = json.JSONDecoder().raw_decode(html[idx:])
    except (json.JSONDecodeError, ValueError):
        return ''
    options = []
    for renderer in _all_yt_renderers(document):
        vid = renderer.get('videoId', '')
        if not re.fullmatch(r'[\w-]{11}', vid):
            continue
        title = unescape(_yt_text(renderer.get('title')))
        channel = unescape(_yt_text(renderer.get('ownerText') or renderer.get('longBylineText'))).casefold()
        name = normalize(title)
        wanted_name = normalize(wanted)
        target_words = [w for w in wanted_name.split() if len(w) >= 3]
        overlap = len([w for w in target_words if w in name.split()]) / max(len(target_words), 1)
        if overlap < .55:
            continue
        score = overlap * 7
        if 'official' in name:
            score += 3
        if 'trailer' in name:
            score += 3
        if 'launch' in name or 'reveal' in name:
            score += 1
        if 'gameplay' in name:
            score += .7
        if 'playstation' in channel or 'official' in channel:
            score += 2
        if 'review' in name or 'reaction' in name or 'fan made' in name or 'concept' in name:
            score -= 6
        if 'walkthrough' in name or 'part 1' in name or 'no commentary' in name:
            score -= 3
        options.append((score, vid))
    return max(options, default=(0, ''))[1]


def find_public_youtube_trailer(title, platform='PS5'):
    query = f'{title} {platform if platform in ("PS4", "PS5") else "PlayStation"} official launch trailer'
    url = 'https://www.youtube.com/results?' + urlencode({'search_query': query})
    data, _ = request_bytes(url, timeout=11, limit=4_200_000, accept='text/html')
    return parse_youtube_search(data.decode('utf8', 'replace'), title)


def image_bytes(url, timeout=10):
    data, mime = request_bytes(url, timeout=timeout, limit=5_000_000, accept='image/avif,image/webp,image/png,image/jpeg,image/*')
    kind = None
    if data[:3] == b'\xff\xd8\xff':
        kind = '.jpg'
    elif data[:8] == b'\x89PNG\r\n\x1a\n':
        kind = '.png'
    elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        kind = '.webp'
    elif data[:6] in (b'GIF89a', b'GIF87a'):
        kind = '.gif'
    if not kind or len(data) < 256:
        raise ValueError('Cover URL did not return valid image data')
    if kind == '.png' and len(data) >= 24:
        w, h = int.from_bytes(data[16:20], 'big'), int.from_bytes(data[20:24], 'big')
        if min(w, h) < 64 or max(w, h) > 10000:
            raise ValueError('Image is too small or invalid')
    return data, kind
