#!/usr/bin/env python3
"""Read-only acceptance check for the public website and database health route."""
import argparse
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def verify(base):
    success = True
    for path in ['/', '/api/health']:
        request = Request(base.rstrip('/') + path, headers={'User-Agent': 'CineMetrics-deployment-check/1.0'})
        try:
            with urlopen(request, timeout=30) as response:
                body = response.read().decode('utf-8')
                if path == '/':
                    if 'CineMetrics' not in body or '<html' not in body.lower():
                        raise ValueError('Homepage did not return CineMetrics HTML')
                elif json.loads(body).get('status') != 'ok':
                    raise ValueError('API did not report healthy database access')
                print(f'PASS {path}: HTTP {response.status}')
        except (HTTPError, URLError, ValueError) as exc:
            # Do not print response bodies or connection settings.
            code = f'HTTP {exc.code}' if isinstance(exc, HTTPError) else type(exc).__name__
            print(f'FAIL {path}: {code}')
            success = False
    return success


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base_url', help='Public deployment origin, without credentials')
    args = parser.parse_args()
    raise SystemExit(0 if verify(args.base_url) else 1)
