"""Export deterministic Python production lifecycle fixtures; no credentials or network."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine
import production_evaluator as pe


def snapshot(audit):
    p = audit['next_prediction']
    return {
        'ai_rankings': p['tier_ranked_digits'],
        'ai_digits': {str(n): p[f'ai{n}'] for n in engine.AI_SIZES},
        'bbfs_digits': {str(n): p[f'bbfs{n}'] for n in engine.BBFS_SIZES},
        'paito': {k: v for k, v in p['paito'].items() if k not in ('overdue_shios', 'overdue_alerts')},
        'method_weights': p['tier_method_weights'],
        'factor_weights': p['bbfs_tier_weights'],
        'calibration': {
            'ai': {str(n): {k: audit['ai_tuning']['tier_audits'][f'ai{n}'][k] for k in ('status', 'action')} for n in engine.AI_SIZES},
            'bbfs': {str(n): {k: audit['bbfs_tuning']['tier_audits'][f'bbfs{n}'][k] for k in ('status', 'action')} for n in engine.BBFS_SIZES},
            'rewarded_methods': audit['rewarded_methods'],
            'penalized_methods': audit['penalized_methods'],
            'twin_status': audit['bbfs_tuning']['twin_status'],
        },
        'dead_digits': p['dead_digits'],
    }


def export(fixtures):
    cases = []
    for case in fixtures['cases']:
        previous = None
        steps = []
        for length in range(case['warmup'], len(case['history']) + 1):
            history = case['history'][:length]
            audit = engine.audit_and_tune(history, previous)
            steps.append({'history': history, 'previous_prediction': previous, 'python': snapshot(audit)})
            previous = audit['next_prediction']
        cases.append({'id': case['id'], 'steps': steps})
    return {'schema_version': 1, 'engine_version': engine.ENGINE_VERSION, 'evaluator_version': pe.EVALUATOR_VERSION, 'cases': cases}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixtures', type=Path, default=Path(__file__).resolve().parents[1] / 'tests/fixtures/parity_histories.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    bundle = export(json.loads(args.fixtures.read_text(encoding='utf-8')))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f"Exported {len(bundle['cases'])} cases to {args.output}")
