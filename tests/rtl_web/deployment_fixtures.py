"""Synthetic reviewed records; deliberately contains unrelated private state."""
import json
from pathlib import Path
from zerorepo.rtl_web.store import Store
from zerorepo.rtl_web.artifacts import Artifacts, atomic_json
from zerorepo.rtl_web.cases import CASES


def historical_store(root: Path):
    store = Store(root)
    art = Artifacts(root, store)
    bundles = {}
    for cid, case in CASES.items():
        rid = 'history-' + cid
        src = root.parent / ('input-' + cid)
        src.mkdir()
        (src / 'dut.v').write_text('module dut(input clk, output y); assign y=clk; endmodule\n')
        before = art.snapshot(src, cid + '-v0', rid)
        after = art.snapshot(src, cid + '-v1', rid, parent=before['version_id'])
        tile_path = src / 'tile.json'
        atomic_json(tile_path, {'synthetic_fixture': True, 'signals': []})
        tile = art.add(tile_path, 'waveform_tile', display=True)
        index_path = src / 'index.json'
        atomic_json(index_path, {'validation_id': cid + '-check', 'tiles': [{'artifact_id': tile['artifact_id']}]})
        index = art.add(index_path, 'waveform', display=True)
        report_path = src / 'report.json'
        atomic_json(report_path, {'stdout': 'Summary:\n system_verify: PASS\n'})
        report = art.add(report_path, 'report', display=True)
        wave_path = src / 'wave.vcd'
        wave_path.write_text('$timescale 1ps $end\n$enddefinitions $end\n#0\n')
        wave = art.add(wave_path, 'vcd')
        vid = cid + '-check'
        val = {'validation_id': vid, 'run_id': rid, 'version_id': after['version_id'],
               'report_artifact_id': report['artifact_id'],
               'waveform_artifact_id': wave['artifact_id'],
               'waveform_sha256': wave['sha256'],
               'waveform_index_artifact_id': index['artifact_id'], 'verdict': 'pass', 'simulation_completed': True}
        store.put('validation', vid, val, immutable=True)
        store.put('run', rid, {'run_id': rid, 'case_id': cid, 'origin': 'historical',
                              'versions': [after['version_id']], 'validations': [vid]}, immutable=True)
        b = {'bundle_id': case['bundle_id'], 'case_id': cid, 'origin': 'historical',
             'source_run_id': rid, 'versions': [{'version_id': after['version_id']}],
             'validations': [val], 'artifacts': [], 'comparison_pair': {
                 'before_validation_id': vid, 'after_validation_id': vid}}
        store.put('bundle', b['bundle_id'], b, immutable=True)
        atomic_json(root / 'bundles' / b['bundle_id'] / 'manifest.json', b)
        bundles[cid] = b['bundle_id']
    session = store.create_session('fixture-session', {'case_id': 'e203'})
    store.put('run', 'private-fixture-run', {'run_id': 'private-fixture-run', 'origin': 'live'}, session['session_id'])
    return store, bundles
