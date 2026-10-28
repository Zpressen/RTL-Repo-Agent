import copy
import json
from pathlib import Path

from zerorepo.rtl_web.root_causes import with_root_causes, annotations

REPO = Path(__file__).resolve().parents[2]


def raw_bundle(case):
    bundle = json.loads((REPO / 'web/rtl-demo/public/cases' / case / 'manifest.json').read_text())
    h = bundle['debug_history']
    h['history_fingerprint'] = h.pop('original_history_fingerprint', h['history_fingerprint'])
    h.pop('diagnosis_fingerprint', None)
    for r in h['runs']:
        for a in r['attempts']:
            a.pop('diagnosis', None)
    return bundle


def test_diagnoses_are_version_bound_without_mutating_archives():
    for case, total, recorded in [('e203', 39, 31), ('aes_cipher_system_hard', 8, 8),
                                  ('aes_inv_cipher_top_system', 4, 4), ('sdc_controller_system', 17, 17)]:
        bundle = raw_bundle(case)
        before = copy.deepcopy(bundle)
        expanded = with_root_causes(bundle)
        attempts = [a for r in expanded['debug_history']['runs'] for a in r['attempts']]
        assert len(attempts) == total
        assert sum(a['diagnosis']['status'] == 'recorded_hypothesis' for a in attempts) == recorded
        for a in attempts:
            assert a['diagnosis']['baseline_version_id'] == a['baseline_version_id']
            assert a['diagnosis']['before_validation_id'] == a['before_validation_id']
        assert bundle == before
        assert with_root_causes(expanded) == expanded
        # A passing candidate can have a preceding diagnosis; never filter it out.
        if case != 'e203':
            assert attempts[-1]['debug']['verdict'] == 'pass'
            assert attempts[-1]['diagnosis']['status'] == 'recorded_hypothesis'
        raw = json.dumps(expanded, ensure_ascii=False)
        assert '/home/mokita' not in raw and 'codex_private' not in raw


def test_stale_source_rtl_or_candidate_never_borrows_another_diagnosis():
    for change in ['source', 'tree', 'candidate', 'revision', 'journal']:
        bundle = raw_bundle('e203')
        run = bundle['debug_history']['runs'][0]
        if change == 'source': bundle['source_fingerprint'] = 'stale'
        elif change == 'tree': run['versions'][0]['tree_sha256'] = 'stale'
        elif change == 'candidate': run['attempts'][0]['candidate_id'] = 'other'
        elif change == 'revision': run['attempts'][0]['candidate_revision'] += 1
        else: run['journal_sha256'] = 'stale'
        assert with_root_causes(bundle) is bundle


def test_no_outcome_goal_or_private_reasoning_is_promoted_to_diagnosis():
    # The final E203 candidate has a goal but no separately saved diagnosis.
    expanded = with_root_causes(raw_bundle('e203'))
    a = expanded['debug_history']['runs'][-1]['attempts'][-1]
    assert a['debug']['expected_effect']
    assert a['diagnosis']['status'] == 'unrecorded'
    assert a['diagnosis']['statements'] == [] and a['diagnosis']['locations'] == []
    config = annotations()
    for case in config['cases'].values():
        for row in case['records']:
            for s in row['statements']:
                assert s['kind'] in {'agent_message', 'patch_hypothesis', 'validation_reason'}
                assert 'expected_effect' not in s and 'reasoning' not in s


def test_excerpts_match_pinned_original_public_messages_or_patch_hypotheses():
    from zerorepo.rtl_web.settings import Settings
    from zerorepo.rtl_web.agent_trace import clean
    s = Settings(REPO / 'configs/rtl_demo.example.yaml', create_data=False)
    for cid, name in [('e203', 'e203'), ('sdc_controller_system', 'sdc'),
                       ('aes_cipher_system_hard', 'aes_cipher'), ('aes_inv_cipher_top_system', 'aes_inverse')]:
        cfg = json.loads((REPO / f'configs/rtl_demo_{name}.history.json').read_text())
        source = s.for_case(cid).source / '.zerorepo/workspace'
        rows_by_sha = {}
        for run in cfg.get('runs', [cfg]):
            base = source / 'debug_system' / s.for_case(cid).case['planner_top'] if 'runs' in cfg else source
            journal = base / run['journal']['path']
            trace = journal.parent.parent / 'codex_trace.jsonl' if 'runs' in cfg else base / run['trace']['path']
            import hashlib
            for path in [journal, trace]:
                rows_by_sha[hashlib.sha256(path.read_bytes()).hexdigest()] = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        for row in annotations()['cases'][cid]['records']:
            for statement in row['statements']:
                original = rows_by_sha[statement['sha256']][statement['line'] - 1]
                if statement['kind'] == 'agent_message':
                    assert original['type'] == 'item.completed'
                    assert original['item']['type'] == 'agent_message'
                    assert clean(original['item']['text'], 1800) == statement['text']
                elif statement['kind'] == 'patch_hypothesis':
                    assert clean(original['hypothesis'].split('Expected effect:', 1)[0].strip(), 2400) == statement['text']
                else:
                    assert original['event'] == 'evaluate'
                    assert clean(original.get('reason') or original['result'].get('reason')) == statement['text']
