"""SAC23 v2.3: verified, read-only artwork rescue for stubborn PS4/PS5 titles.

Pages in this module are official publisher/store listings for *game art only*.
No game executables or packages are ever downloaded. All actual cover downloads
are validated by metadata.image_bytes before being stored in the local cache.
"""
from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
import re
import unicodedata
from urllib.parse import parse_qs, unquote, urlparse, urlunparse

import metadata

# These sources were reviewed against the actual games in the user's Cover Report.
# Prefix aliases are only used for art lookup, never to rename or merge game files.
VERIFIED_SOURCES = {
    'assassins creed black flag resynced': ('Assassin’s Creed Black Flag Resynced',
        'https://store.playstation.com/en-us/product/EP0001-PPSA28183_00-GAME000000000000'),
    'call of duty black ops 2': ('Call of Duty: Black Ops II',
        'https://store.playstation.com/en-us/product/UP0002-PPSA34502_00-CODBO2GAME000001'),
    'call of duty black ops': ('Call of Duty: Black Ops',
        'https://store.playstation.com/en-us/product/UP0002-PPSA34501_00-CODBO1GAME000001'),
    'call of duty modern warfare 3': ('Call of Duty: Modern Warfare III',
        'https://store.playstation.com/en-us/product/UP0002-PPSA01649_00-CODMW3CROSSGEN01'),
    'cyberpunk 2077': ('Cyberpunk 2077',
        'https://store.playstation.com/en-us/product/UP4497-PPSA03974_00-0000000000000CP1'),
    'ea sports fc 27': ('EA SPORTS FC 27',
        'https://store.playstation.com/en-us/product/UP0006-PPSA34015_00-27STANDARDBUNDLE'),
    'far cry 6': ('Far Cry 6 Game of the Year Edition',
        'https://store.playstation.com/en-us/product/UP0001-PPSA01876_00-FC6EDGOTY0000000'),
    'god of war 3 remastered': ('God of War III Remastered',
        'https://store.playstation.com/en-us/product/UP9000-CUSA01623_00-0000GODOFWAR3PS4/'),
    'god of war ragnarok': ('God of War Ragnarök',
        'https://store.playstation.com/en-us/product/UP9000-PPSA08329_00-GOWRAGNAROK00000'),
    'god of war sons of sparta': ('God of War Sons of Sparta',
        'https://store.playstation.com/en-us/product/UP9000-PPSA28997_00-SONSOFSPARTAPS50'),
    'halo campaign evolved': ('Halo: Campaign Evolved',
        'https://store.playstation.com/en-us/product/UP6312-PPSA28038_00-0375433414453693'),
    'hogwarts legacy': ('Hogwarts Legacy',
        'https://store.playstation.com/en-us/product/UP1018-PPSA01593_00-HOGWARTSLEGACY01/'),
    'horizon forbidden west': ('Horizon Forbidden West Complete Edition',
        'https://store.playstation.com/en-us/product/UP9000-PPSA17905_00-HFWCE00000000000/'),
    'lego party': ('LEGO Party!',
        'https://store.playstation.com/en-us/product/UB1599-PPSA29140_00-LEGOPARTYSIEA000/'),
    'marvels spider man miles morales': ('Marvel’s Spider-Man: Miles Morales',
        'https://store.playstation.com/en-us/product/UP9000-PPSA01411_00-MARVELSSMMORALES/'),
    'marvels spider man remastered': ('Marvel’s Spider-Man Remastered',
        'https://store.playstation.com/en-us/product/UP9000-PPSA01467_00-MARVELSSPIDERMAN'),
    'marvels wolverine': ('Marvel’s Wolverine',
        'https://store.playstation.com/en-us/concept/10002861/'),
    'metal gear solid v ground zeroes': ('Metal Gear Solid V: Ground Zeroes',
        'https://store.playstation.com/en-us/product/UP0101-CUSA00218_00-METALGEARSOLIDGZ/'),
    'ready or not': ('Ready or Not',
        'https://store.playstation.com/en-us/product/UP6322-PPSA18605_00-0342498734252743/'),
    'resident evil 4 remake': ('Resident Evil 4 (2023)',
        'https://store.playstation.com/en-us/product/UP0102-PPSA07411_00-RE4RMAINGAME0000'),
}

# Exact image assets published on the corresponding official PlayStation game
# pages. Keeping verified direct links avoids repeated HTML requests and Wiki
# 429s. If a publisher rotates its images, the site parser remains a fallback.
# These are not copied into the ZIP: the app downloads them to its local cache.
DIRECT_COVERS = {
    'assassins creed black flag resynced': 'https://image.api.playstation.com/vulcan/ap/rnd/202603/1215/f1fe921628640e04e0019a7c874a0215dbe26bec1f4b6df2.jpg',
    'call of duty black ops 2': 'https://image.api.playstation.com/vulcan/ap/rnd/202605/1922/9c953e771b77e507dfb3a3cf079dfed4c73557ee05537981.png',
    'call of duty black ops': 'https://image.api.playstation.com/vulcan/ap/rnd/202606/0222/7a6725cca3b800df01a0cbbc77f7913c43218d961a0e8368.png',
    'call of duty modern warfare 3': 'https://image.api.playstation.com/vulcan/ap/rnd/202308/1415/8d9af953f938ba6cb9f9e73cd94424df2d33b0f313794739.png',
    'cyberpunk 2077': 'https://image.api.playstation.com/vulcan/ap/rnd/202111/3013/UjQ1pWQiHwymgQQ6q4pWQkMC.png',
    'ea sports fc 27': 'https://image.api.playstation.com/vulcan/ap/rnd/202607/2321/fa7db8b40ed671bce4046b335beb5a0ab327c33edbca8351.jpg',
    'far cry 6': 'https://image.api.playstation.com/vulcan/ap/rnd/202209/3022/c2nYHjnBwBI44M9TVFRMZkb3.jpg',
    'god of war 3 remastered': 'https://image.api.playstation.com/vulcan/img/rnd/202010/2917/qKv4pRqoGFvnoUKyDSLg17ne.png',
    'god of war ragnarok': 'https://image.api.playstation.com/vulcan/ap/rnd/202503/2016/1f4bf1ee42276b3841e71ebb812510493ce78bfc307d3296.jpg',
    'god of war sons of sparta': 'https://image.api.playstation.com/vulcan/ap/rnd/202602/0618/2fee30cf3febc58730657a23d3899823cb4d62e966b1f827.jpg',
    'halo campaign evolved': 'https://image.api.playstation.com/vulcan/ap/rnd/202606/1523/5102f2929b3357cb4af79022f4fc2234fc5756710947e91a.png',
    'hogwarts legacy': 'https://image.api.playstation.com/vulcan/ap/rnd/202208/0921/3XopdGAJGRy3xNQKnQDvaCRs.png',
    'horizon forbidden west': 'https://image.api.playstation.com/vulcan/ap/rnd/202309/2015/d67aa11d5dea3ac14efd91ab1c82227eab2b370436090fa9.jpg',
    'lego party': 'https://image.api.playstation.com/vulcan/ap/rnd/202505/2217/9fc3bf3631e98ff7b5cc9c443f07d9a6c5ea6014e2dd3dc5.jpg',
    'marvels spider man miles morales': 'https://image.api.playstation.com/vulcan/img/rnd/202010/2417/tnCutdREPv6Pa7atqb8MTxGW.png',
    'marvels spider man remastered': 'https://image.api.playstation.com/vulcan/ap/rnd/202009/3021/5ayReKkz8RaBVuTvrxgA3rvh.png',
    'marvels wolverine': 'https://image.api.playstation.com/vulcan/ap/rnd/202605/2221/2e98d11ecc5fc86cf404d0f4b7b4a1ba5774a51bf3db0020.jpg',
    'metal gear solid v ground zeroes': 'https://image.api.playstation.com/vulcan/ap/rnd/202010/0205/O0nZTTG9CvR72oVUv6QYXXy9.png',
    'ready or not': 'https://image.api.playstation.com/vulcan/ap/rnd/202504/0914/263dd759a82791236ec990ec3e0930b9dbd5cca948b25c75.jpg',
    'resident evil 4 remake': 'https://image.api.playstation.com/vulcan/ap/rnd/202210/0712/PjIoeaMt833otj5HukAWGfui.png',
}


def direct_verified_cover(game):
    key = verified_match(game)
    url = DIRECT_COVERS.get(key)
    if not url:
        return {}
    title, store_page = VERIFIED_SOURCES[key]
    return {'cover_candidates': [url, url + '?w=600', url + '?thumb=true&w=600'],
            'source': 'Verified PlayStation Store artwork',
            'matched_name': title, 'source_url': store_page}


# Verified PlayStation game ID references override mangled release-group names.
ID_ALIASES = {
    'PPSA01649': 'call of duty modern warfare 3',
    'PPSA04029': 'cyberpunk 2077',
    'PPSA08331': 'god of war ragnarok',
    'PPSA08330': 'god of war ragnarok',
    'PPSA28997': 'god of war sons of sparta',
    'PPSA01603': 'hogwarts legacy',
    'PPSA29141': 'lego party',
    'PPSA01467': 'marvels spider man remastered',
    'PPSA03671': 'marvels wolverine',
    'CUSA00218': 'metal gear solid v ground zeroes',
    'PPSA18605': 'ready or not',
    'PPSA07411': 'resident evil 4 remake',
    'PPSA26344': 'ghost of yotei',
}

TRAILING_RELEASE_TAGS = re.compile(
    r'(?i)\s+(?:(?:incl(?:uding)?(?:\s+dlc)?)|(?:lizard)|(?:proper|prooper)|'
    r'(?:playable)|(?:only)|(?:resynced\s+ps5))\s*$'
)
EDITION_TAGS = re.compile(r'(?i)\s+(?:(?:premium|deluxe|ultimate|gold|complete|standard)\s+edition|'
                          r'(?:game\s+)?of\s+the\s+year\s+edition|goty\s+edition)\s*$')


def art_title_key(text):
    text = unicodedata.normalize('NFKD', str(text or '').casefold())
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace('™', ' ').replace('®', ' ').replace('©', ' ')
    text = re.sub(r"\bmarvel'?s\b", 'marvels', text)
    text = re.sub(r"\bassassin'?s\b", 'assassins', text)
    text = re.sub(r'(?i)\b(?:iii|3)\b', '3', text)
    text = re.sub(r'(?i)\b(?:ii|2)\b', '2', text)
    text = re.sub(r'[^a-z0-9]+', ' ', text).strip()
    return ' '.join(text.split())


def clean_for_match(title):
    t = str(title or '')
    # The `... incl DLC` and release-group suffixes are never the game title.
    for _ in range(4):
        prev = t
        t = TRAILING_RELEASE_TAGS.sub('', t).strip()
        t = EDITION_TAGS.sub('', t).strip()
        if t == prev:
            break
    # Version/build jargon sometimes follows the title, never part of box art.
    t = re.sub(r'(?i)\s+\d{2,3}\s+\d{3}\s+\d+\s+xx.*$', '', t)
    t = re.sub(r'(?i)\s+(?:10\s+0verflow|v1\s*10\s+0verflow)$', '', t)
    return art_title_key(t)


def verified_match(game):
    """Only exact title aliases/known IDs, never fuzzy prefix-matching sequels."""
    tid = re.sub(r'[^A-Z0-9]', '', str(game.get('title_id') or '').upper())
    if tid in ID_ALIASES and ID_ALIASES[tid] in VERIFIED_SOURCES:
        key = ID_ALIASES[tid]
        # If a title is specifically for a different game, don't override it.
        title_key = clean_for_match(game.get('custom_title') or game.get('title'))
        if title_key and not (title_key == key or title_key.startswith(key + ' ') or
                              key.startswith(title_key + ' ') or len(title_key) < 12):
            # This is safe for release-group errors only if the known title ID
            # otherwise unambiguously identifies the game; exact IDs win.
            pass
        return key
    given = [game.get(k) for k in ('custom_title', 'identified_title', 'title')]
    for title in given:
        if not title:
            continue
        key = clean_for_match(title)
        if key in VERIFIED_SOURCES:
            return key
        # Report variants that have consistent *known* extra words, not a
        # permissive fuzzy match (critical for Black Ops vs Black Ops II).
        if key.startswith('cyberpunk 2077 '):
            return 'cyberpunk 2077'
        if key.startswith('far cry 6 ') and 'year edition' in key:
            return 'far cry 6'
    return ''


def _sanitize_sony_url(url):
    if not url:
        return ''
    url = unescape(url).replace(r'\/', '/').replace(r'\u002F', '/')
    for _ in range(2):
        if url.startswith('//'):
            url = 'https:' + url
        parts = urlparse(url)
        if parts.hostname == 'image.api.playstation.com' and parts.scheme == 'https':
            # Thumbnails can be tiny; the underlying Vulcan image is full size.
            path = parts.path
            if re.search(r'\.(?:png|jpe?g|webp)(?:$|/)', path, re.I):
                return urlunparse(('https', 'image.api.playstation.com', path, '', '', ''))
            return ''
        if parts.hostname and (parts.hostname.endswith('playstation.com') or parts.hostname == 'store.playstation.com'):
            # Next.js optimized image URL has the actual vulcan URL in ?url=...
            unwrapped = parse_qs(parts.query).get('url', [])
            if unwrapped:
                url = unquote(unwrapped[0])
                continue
        return ''
    return ''


class _OfficialImages(HTMLParser):
    def __init__(self, wanted):
        super().__init__(convert_charrefs=True)
        self.images = []
        self.wanted_key = art_title_key(wanted)
    def handle_starttag(self, tag, attrs):
        if tag not in ('img', 'meta'):
            return
        props = dict(attrs)
        if tag == 'meta':
            kind = (props.get('property') or props.get('name') or '').lower()
            if kind not in ('og:image', 'twitter:image'):
                return
            raw = props.get('content') or ''
            src = _sanitize_sony_url(raw)
            if src:
                self.images.append((1, src))
            return
        alt = art_title_key(props.get('alt') or '')
        # Prefer the product box image, not generic PlayStation logos.
        if not alt or not self.wanted_key:
            return
        if not (self.wanted_key in alt or (alt in self.wanted_key and
                                               len(alt) > 14 and
                                               len(alt) >= .8 * len(self.wanted_key))):
            return
        for raw in (props.get('src') or '', props.get('data-src') or ''):
            src = _sanitize_sony_url(raw)
            if src:
                self.images.append((3, src))
        # srcset can contain full-res sizes even when src is a thumbnail.
        for segment in (props.get('srcset') or '').split(',')[:12]:
            src = _sanitize_sony_url(segment.strip().split(' ')[0])
            if src:
                self.images.append((2, src))


def parse_official_images(html, title):
    parser = _OfficialImages(title)
    parser.feed(html[:7_000_000])
    # Only use images with a matching product title or the site's own social
    # thumbnail. Do not select unlabelled carousel screenshots.
    ordered = sorted(enumerate(parser.images), key=lambda x: (-x[1][0], x[0]))
    return list(dict.fromkeys(src for _, (_, src) in ordered))[:8]


def fetch_official_images(game, timeout=12):
    key = verified_match(game)
    if not key:
        return {}
    matched_title, url = VERIFIED_SOURCES[key]
    from urllib.parse import urlsplit
    hostname = urlsplit(url).hostname or ''
    if hostname not in ('store.playstation.com', 'www.playstation.com'):
        return {}
    data, _ = metadata.request_bytes(url, timeout=timeout, limit=7_000_000, accept='text/html')
    images = parse_official_images(data.decode('utf8', 'replace'), matched_title)
    if not images:
        raise ValueError('The official store page did not provide a usable box image')
    return {'cover_candidates': images, 'source': 'Official PlayStation artwork',
            'matched_name': matched_title, 'source_url': url}


def matching_cover_games(game, existing, strict_id=False):
    """Find cached game covers that can be shared without an online request.

    Same PlayStation title ID is preferred. Never mix Black Ops 1/2, sequels,
    base games with unrelated DLC packs, or generic English collections.
    """
    gid = game.get('id')
    platform = game.get('platform')
    tid = re.sub(r'[^A-Z0-9]', '', str(game.get('title_id') or '').upper())
    normalized = clean_for_match(game.get('custom_title') or game.get('identified_title') or game.get('title'))
    matches = []
    for candidate in existing:
        if candidate.get('id') == gid:
            continue
        other_tid = re.sub(r'[^A-Z0-9]', '', str(candidate.get('title_id') or '').upper())
        exact_id = bool(tid and other_tid and tid == other_tid)
        if exact_id and platform == candidate.get('platform'):
            matches.append((5, candidate))
            continue
        if strict_id:
            continue
        if not normalized or len(normalized) < 8 or normalized.startswith('collection '):
            continue
        other_name = clean_for_match(candidate.get('custom_title') or candidate.get('identified_title') or candidate.get('title'))
        if normalized == other_name:
            score = 3 if platform == candidate.get('platform') else 2
            matches.append((score, candidate))
    return [x[1] for x in sorted(matches, key=lambda r: -r[0])]
