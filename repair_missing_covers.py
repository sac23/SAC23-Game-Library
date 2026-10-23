#!/usr/bin/env python3
"""Copy cached artwork between same-title-ID cards. Never touch game files."""
import game_library as lib


def main():
    if not lib.DATA_FILE.is_file():
        print('Library data was not found. Launch SAC23 Game Library first.')
        print('Expected data: ' + str(lib.DATA_FILE))
        return 1
    print('Using saved library: ' + str(lib.DATA_FILE))
    print('Covers are stored in: ' + str(lib.COVER_CACHE))
    repaired = lib.repair_cached_duplicate_covers()
    if repaired:
        for title, title_id in repaired:
            print('FIXED: ' + title + ' (' + title_id + ')')
    else:
        print('No additional matching cached artwork could be found.')
    total = len(lib.state['games'])
    covered = sum(lib.game_has_cover(g) for g in lib.state['games'])
    print(f'Artwork: {covered}/{total} covers available.')
    for game in lib.state['games']:
        if not lib.game_has_cover(game):
            print('STILL MISSING: ' + str(game.get('title')) + ' (' + str(game.get('title_id') or 'No ID') + ')')
    print('Game files were not changed.')
    return 0 if covered == total else 2


if __name__ == '__main__':
    raise SystemExit(main())
