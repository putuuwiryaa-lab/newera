"""Portable deterministic persisted market for browser/TypeScript regression tests."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.test_production_health import healthy_market

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(healthy_market(), indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
