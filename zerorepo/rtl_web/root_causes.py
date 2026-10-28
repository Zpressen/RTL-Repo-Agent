"""Read-only, version-bound annotations of recorded public Agent diagnoses."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re

from .agent_trace import clean
from .store import dump


@lru_cache(maxsize=1)
def annotations():
    path = Path(__file__).resolve().parents[2] / 'configs/rtl_demo_root_causes.json'
    return json.loads(path.read_text()) if path.is_file() else {}


def with_root_causes(bundle):
    """Keep immutable history intact; omit annotations if any binding is stale."""
    config = annotations()
    history = bundle.get('debug_history')
    case = config.get('cases', {}).get(bundle.get('case_id'))
    if not history or not case or config.get('schema_version') != 'rtl-root-causes-v1':
        return bundle
    original_fp = history.get('original_history_fingerprint', history['history_fingerprint'])
    if case['source_fingerprint'] != bundle.get('source_fingerprint') or case['history_fingerprint'] != original_fp:
        return bundle
    entries = {r['validation_id']: r for r in case['records']}
    if len(entries) != len(case['records']) or len(entries) != sum(len(r['attempts']) for r in history['runs']):
        return bundle
    runs = []
    for run in history['runs']:
        if run.get('origin') != 'historical':
            return bundle
        versions = {v['version_id']: v for v in run['versions']}
        attempts = []
        for attempt in run['attempts']:
            row = entries.get(attempt['validation_id'])
            baseline = versions.get(attempt['baseline_version_id'])
            if not row or not baseline or row.get('run_id') != run['run_id'] or row.get('journal_sha256') != run.get('journal_sha256'):
                return bundle
            if any(row.get(k) != attempt.get(k) for k in ['candidate_id', 'candidate_revision', 'validation_id', 'baseline_version_id', 'before_validation_id']):
                return bundle
            if row.get('baseline_tree_sha256') != baseline['tree_sha256']:
                return bundle
            statements = [{k: s[k] for k in ['kind', 'text', 'sha256', 'line', 'timing']} for s in row['statements']
                          if s.get('kind') in {'agent_message', 'patch_hypothesis', 'validation_reason'}
                          and s.get('timing') in {'before_code_edit', 'before_candidate_validation', 'at_validation_request'}
                          and re.fullmatch('[a-f0-9]{64}', s.get('sha256', '')) and isinstance(s.get('line'), int) and s['line'] > 0]
            for statement in statements:
                statement['text'] = clean(statement['text'], 2400)
            files = {f['path'] for f in baseline['file_manifest']}
            locations = [{k: loc[k] for k in ['file', 'start_line', 'end_line', 'source']} for loc in row['locations']
                         if loc.get('file') in files and isinstance(loc.get('start_line'), int) and isinstance(loc.get('end_line'), int)
                         and 0 < loc['start_line'] <= loc['end_line']
                         and loc.get('source') in {'agent_target', 'candidate_change_range'}]
            diagnosis = {'status': 'recorded_hypothesis' if statements else 'unrecorded',
                         'recorded_at': 'before_edit' if any(s['timing'] == 'before_code_edit' for s in statements) else 'validation_request' if statements else 'unrecorded',
                         'summary': clean(row['summary'], 800) if statements else '未保存本次修改前的独立根因判断。',
                         'baseline_version_id': baseline['version_id'], 'before_validation_id': attempt['before_validation_id'],
                         'statements': statements, 'locations': locations if statements else []}
            attempts.append({**attempt, 'diagnosis': diagnosis})
        runs.append({**run, 'attempts': attempts})
    fingerprint = hashlib.sha256(dump(case).encode()).hexdigest()
    return {**bundle, 'debug_history': {**history, 'runs': runs,
            'original_history_fingerprint': original_fp, 'diagnosis_fingerprint': fingerprint,
            'history_fingerprint': hashlib.sha256((original_fp + fingerprint).encode()).hexdigest()}}
