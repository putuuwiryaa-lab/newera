"""Read-only health audit by default. --write persists only the health projection."""

import argparse
from collections import Counter
import json
from pathlib import Path

import requests

from production_health import assess_market_health

FIRESTORE_URL = 'https://firestore.googleapis.com/v1/projects/newera-94be7/databases/(default)/documents/markets'


def decode(value):
    for key in ('stringValue', 'timestampValue', 'booleanValue'):
        if key in value:
            return value[key]
    if 'integerValue' in value:
        return int(value['integerValue'])
    if 'doubleValue' in value:
        return float(value['doubleValue'])
    if 'arrayValue' in value:
        return [decode(v) for v in value['arrayValue'].get('values', [])]
    if 'mapValue' in value:
        return {k: decode(v) for k, v in value['mapValue'].get('fields', {}).items()}
    return None


def read_public_markets():
    token = ''
    seen = set()
    while True:
        params = {'pageSize': 1000}
        if token:
            params['pageToken'] = token
        response = requests.get(FIRESTORE_URL, params=params, timeout=30)
        response.raise_for_status()
        page = response.json()
        for doc in page.get('documents', []):
            yield {k: decode(v) for k, v in doc.get('fields', {}).items()}
        token = page.get('nextPageToken')
        if not token:
            break
        if token in seen:
            raise RuntimeError('Repeated Firestore page token')
        seen.add(token)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, default=Path('health-report.json'))
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--fail-on-error', action='store_true')
    args = parser.parse_args()
    if args.write:
        from scraper import init_firebase
        db = init_firebase()
        if db is None:
            raise RuntimeError('--write requires Firebase credentials')
        docs = list(db.collection('markets').stream())
        markets = [(doc.to_dict(), doc.reference) for doc in docs]
    else:
        markets = [(m, None) for m in read_public_markets()]
    report = []
    for market, ref in markets:
        health = assess_market_health(market)
        report.append({'market': market.get('id', market.get('name', 'unknown')), **health})
        if ref is not None:
            ref.set({'production_health': health}, merge=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    summary = dict(Counter(row['status'] for row in report))
    print(json.dumps({'markets': len(report), 'summary': summary, 'write': args.write}))
    if not report or (args.fail_on_error and summary.get('ERROR', 0)):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
