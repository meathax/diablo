"""Compare indexed reference captures, including every RGB888 palette entry."""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def read_frame(path):
    raw = Path(path).read_bytes()
    if len(raw) != 32 + 768 + 640 * 480:
        raise ValueError(f'Invalid capture size: {path}')
    magic, width, height, frame, logic_ms = struct.unpack('<8sIIQQ', raw[:32])
    if (magic, width, height) != (b'D8RGB001', 640, 480):
        raise ValueError(f'Invalid capture header: {path}')
    return {'frame': frame, 'logic_ms': logic_ms,
            'palette': raw[32:800], 'pixels': raw[800:],
            'sha256': hashlib.sha256(raw).hexdigest()}


def compare(left, right):
    a, b = read_frame(left), read_frame(right)
    result = {'left_sha256': a['sha256'], 'right_sha256': b['sha256']}
    for key in ('frame', 'logic_ms'):
        if a[key] != b[key]:
            return result | {'equal': False, 'difference': key, 'left': a[key], 'right': b[key]}
    for key in ('palette', 'pixels'):
        for offset, (x, y) in enumerate(zip(a[key], b[key])):
            if x != y:
                location = {'entry': offset // 3, 'channel': 'RGB'[offset % 3]} if key == 'palette' else {'x': offset % 640, 'y': offset // 640}
                return result | {'equal': False, 'difference': key, **location, 'left': x, 'right': y}
    return result | {'equal': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('left', type=Path)
    parser.add_argument('right', type=Path)
    args = parser.parse_args()
    result = compare_series(args.left, args.right) if args.left.is_dir() or args.right.is_dir() else compare(args.left, args.right)
    print(json.dumps(result, indent=2))
    return 0 if result['equal'] else 1


def compare_series(left, right):
    left, right = Path(left), Path(right)
    if not left.is_dir() or not right.is_dir():
        raise ValueError('Both capture series must be directories')
    a = {p.name for p in left.glob('*.d8f')}
    b = {p.name for p in right.glob('*.d8f')}
    if list(left.glob('*.partial')) or list(right.glob('*.partial')):
        return {'equal': False, 'difference': 'incomplete captures'}
    if not a or not b:
        return {'equal': False, 'difference': 'empty capture series'}
    if a != b:
        return {'equal': False, 'difference': 'frame set', 'left_only': sorted(a - b), 'right_only': sorted(b - a)}
    for name in sorted(a):
        result = compare(left / name, right / name)
        if not result['equal']:
            return result | {'file': name}
    return {'equal': True, 'frames_compared': len(a), 'scope': 'All supplied indexed frames and all RGB888 palette entries'}


if __name__ == '__main__':
    raise SystemExit(main())
