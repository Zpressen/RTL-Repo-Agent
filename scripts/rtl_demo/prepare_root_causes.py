"""Publish bounded, source-pinned diagnosis annotations without changing runs.

Only explicit Agent messages and patch hypotheses are read. Reasoning items,
tool argument dictionaries and raw traces are never published. Run/RTL/report
bindings are taken from the reviewed historical export, not inferred by time.
"""
from __future__ import annotations

import difflib
import hashlib
import json
from pathlib import Path
import re

from zerorepo.rtl_web.agent_trace import clean
from zerorepo.rtl_web.settings import Settings

REPO = Path(__file__).resolve().parents[2]
NAMES = {'e203': 'e203', 'aes_cipher_system_hard': 'aes_cipher',
         'aes_inv_cipher_top_system': 'aes_inverse', 'sdc_controller_system': 'sdc'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked(path, digest):
    if sha(path) != digest:
        raise ValueError('Diagnosis source fingerprint mismatch: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def result(item):
    r = item.get('result') or {}
    if isinstance(r.get('structured_content'), dict):
        return r['structured_content']
    for block in r.get('content', []):
        if block.get('type') == 'text':
            try:
                return json.loads(block['text'])
            except (ValueError, KeyError):
                pass
    return {}


def codex_statements(rows):
    """Associate public messages before the first edit with its later check."""
    found, previous = {}, 0
    for index, row in enumerate(rows):
        item = row.get('item', {})
        if row.get('type') != 'item.completed' or item.get('type') != 'mcp_tool_call' or item.get('tool') != 'validate_rtl_changes':
            continue
        args, obs = item.get('arguments') or {}, result(item)
        if args.get('action') != 'evaluate' or not obs.get('validation_trial'):
            previous = index + 1
            continue
        boundary = index
        for n in range(previous, index):
            candidate = rows[n].get('item', {})
            if candidate.get('type') == 'file_change':
                boundary = n
                break
            if candidate.get('type') == 'command_execution' and re.search(
                    r'(?:write_text|write_bytes|apply_patch|cat\s*>|open\([^\n]+[\x27\"]w)', candidate.get('command', '')):
                boundary = n
                break
        messages = [(n + 1, clean(rows[n]['item'].get('text'), 1800)) for n in range(previous, boundary)
                    if rows[n].get('type') == 'item.completed' and rows[n].get('item', {}).get('type') == 'agent_message']
        messages = [(n, text) for n, text in messages if len(text) < 1800 and re.search(
            r'mismatch|incorrect|instead|root|cause|gated|shows|wrong|phase|counter|reset|writeback|flag|operand|divid|partial|state|boundary|mask|timing', text, re.I)]
        found[(obs['candidate_id'], obs.get('candidate_revision', 1))] = {
            'messages': messages[-3:], 'evaluation_line': index + 1,
            'edit_line': boundary + 1 if boundary < index else None,
            'validation_trial': obs['validation_trial'],
        }
        previous = index + 1
    return found


def build():
    settings = Settings(REPO / 'configs/rtl_demo.example.yaml', create_data=False)
    pins = json.loads((REPO / 'configs/rtl_demo_root_causes.sources.json').read_text())
    translations = json.loads((REPO / 'configs/rtl_demo_root_causes.summaries.json').read_text())
    output = {'schema_version': 'rtl-root-causes-v1', 'cases': {}}
    audit = {}
    for case_id, name in NAMES.items():
        selected = settings.for_case(case_id)
        config = json.loads((REPO / f'configs/rtl_demo_{name}.history.json').read_text())
        public = REPO / 'web/rtl-demo/public'
        bundle = json.loads((public / 'cases' / case_id / 'manifest.json').read_text())
        runs = bundle['debug_history']['runs']
        item = {'source_fingerprint': bundle['source_fingerprint'],
                'history_fingerprint': bundle['debug_history'].get('original_history_fingerprint', bundle['debug_history']['history_fingerprint']),
                'records': []}
        offset = 0
        for run_no, run in enumerate(runs):
            codex = case_id in {'e203', 'sdc_controller_system'}
            source = config['runs'][run_no] if codex else config
            base = selected.source / '.zerorepo/workspace'
            if codex:
                base = base / 'debug_system' / selected.case['planner_top']
            journal = base / source['journal']['path']
            journal_rows = checked(journal, source['journal']['sha256'])
            trace = journal.parent.parent / 'codex_trace.jsonl' if codex else base / source['trace']['path']
            trace_sha = pins['cases'][case_id][run_no]['trace_sha256']
            trace_rows = checked(trace, trace_sha)
            statements = codex_statements(trace_rows) if codex else {}
            evaluations = [(n, row) for n, row in enumerate(journal_rows, 1) if not codex or row.get('event') == 'evaluate']
            assert len(evaluations) == len(run['attempts'])
            versions = {v['version_id']: v for v in run['versions']}

            def rtl(version, name):
                module = next((m for m in version['modules'] if m['file'] == name), None)
                if not module:
                    return ''
                path = public / bundle['content_urls'][module['artifact_id']].lstrip('/')
                text = json.loads(path.read_text())['content']
                assert hashlib.sha256(text.encode()).hexdigest() == module['sha256']
                return text

            for attempt, (journal_line, row) in zip(run['attempts'], evaluations, strict=True):
                left, right = versions[attempt['baseline_version_id']], versions[attempt['candidate_version_id']]
                ordinal = offset + attempt['trial_no']
                evidence, locations = [], []
                if codex:
                    assert (row['candidate_id'], row.get('revision', 1)) == (attempt['candidate_id'], attempt['candidate_revision'])
                    record = statements.get((attempt['candidate_id'], attempt['candidate_revision']))
                    if record:
                        assert record['validation_trial'] == attempt['trial_no']
                        for line, text in record['messages']:
                            evidence.append({'kind': 'agent_message', 'text': text, 'sha256': trace_sha,
                                             'line': line, 'timing': 'before_code_edit' if record['edit_line'] else 'before_candidate_validation'})
                    reason = clean(row.get('reason') or row.get('result', {}).get('reason'))
                    if reason:
                        evidence.append({'kind': 'validation_reason', 'text': reason, 'sha256': source['journal']['sha256'],
                                         'line': journal_line, 'timing': 'at_validation_request'})
                else:
                    assert row['step'] == attempt['trial_no']
                    # The hypothesis is an action argument, not an outcome or lesson.
                    text = clean(row.get('hypothesis', '').split('Expected effect:', 1)[0].strip(), 2400)
                    if text:
                        evidence.append({'kind': 'patch_hypothesis', 'text': text, 'sha256': source['journal']['sha256'],
                                         'line': journal_line, 'timing': 'before_code_edit'})
                    for target in row.get('target', {}).get('files', [row.get('target', {})]):
                        name = Path(target.get('path', '')).name
                        start, end = target.get('start_line'), target.get('end_line')
                        if name in {m['file'] for m in left['modules']} and isinstance(start, int) and isinstance(end, int):
                            assert 0 < start <= end <= len(rtl(left, name).splitlines())
                            locations.append({'file': name, 'start_line': start, 'end_line': end, 'source': 'agent_target'})
                if not locations:
                    for changed in attempt['debug']['files']:
                        name = changed['path']
                        before, after = rtl(left, name).splitlines(), rtl(right, name).splitlines()
                        for group in list(difflib.SequenceMatcher(None, before, after, autojunk=False).get_grouped_opcodes(2))[:2]:
                            if before:
                                locations.append({'file': name, 'start_line': max(1, group[0][1] + 1),
                                                  'end_line': min(len(before), max(group[0][1] + 1, group[-1][2])),
                                                  'source': 'candidate_change_range'})
                        if len(locations) >= 6:
                            break
                item['records'].append({'run_id': run['run_id'], 'candidate_id': attempt['candidate_id'],
                    'candidate_revision': attempt['candidate_revision'], 'validation_id': attempt['validation_id'],
                    'baseline_version_id': left['version_id'], 'baseline_tree_sha256': left['tree_sha256'],
                    'before_validation_id': attempt['before_validation_id'], 'journal_sha256': run['journal_sha256'],
                    'status': 'recorded_hypothesis' if evidence else 'unrecorded',
                    'summary': translations[case_id][str(ordinal)] if evidence else '未保存本次修改前的独立根因判断。',
                    'statements': evidence, 'locations': locations if evidence else []})
            offset += len(run['attempts'])
        output['cases'][case_id] = item
        audit[case_id] = {'records': len(item['records']), 'recorded': sum(r['status'] == 'recorded_hypothesis' for r in item['records']),
                          'pre_edit': sum(any(s['timing'] == 'before_code_edit' for s in r['statements']) for r in item['records'])}
    target = REPO / 'configs/rtl_demo_root_causes.json'
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'output': target.name, 'sha256': sha(target), 'cases': audit}, ensure_ascii=False))


if __name__ == '__main__':
    build()
