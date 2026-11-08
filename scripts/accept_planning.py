#!/usr/bin/env python3
"""Run real Stage1--4 acceptance in an isolated, resumable case directory."""
from __future__ import annotations
import argparse
import hashlib
import json
import logging
import sys
import time
from pathlib import Path
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from zerorepo.rpg_gen.base.llm_client import LLMConfig
from zerorepo.rtl_impl.module_planner import PlannerRunner
from zerorepo.rtl_impl.module_planner.schemas import PlannerTaskInput
from zerorepo.rtl_impl.module_planner.utils.artifact_store import atomic_write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('case', choices=['aes', 'e203'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    case = {'aes': 'aes_inv_cipher_system_hard', 'e203': 'e203_exu_alu_system'}[args.case]
    spec_dir = 'aes_inv_cipher_top' if args.case == 'aes' else 'e203_exu_alu'
    root = args.root.resolve() / case
    if (root / 'plan/stage1/contracts.json').exists() and not args.resume:
        parser.error('Existing acceptance progress requires --resume or a new root')
    root.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger('planning-acceptance')
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(root / 'run.log', encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(handler)
    cfg = yaml.safe_load((project / 'configs/zerorepo_config.yaml').read_text())
    llm = LLMConfig.from_dict(cfg['llm'])
    opts = cfg.get('rtl_module_planner', {})
    runner = PlannerRunner(root, llm_config=llm, logger=logger,
        request_policy=opts.get('request_policy'), execution_policy=opts.get('execution_policy'),
        artifacts=opts.get('artifacts'), retrieval_limits=opts.get('retrieval_limits'))
    task = PlannerTaskInput(task_id=case, spec_md_files=[str(project / 'rtl_dataset' / spec_dir / f'{case}.md')],
                            project_type='light_repo_spec2rtl', notes='Real planning harness acceptance')
    started = time.monotonic()
    result = {'case': case, 'scope': 'stage1--stage4', 'real_model': True, 'resume': args.resume,
        'local_json_authority': True, 'external_kg_used': False,
        'model': runner.llm_client.executor.model,
        'model_config_fingerprint': hashlib.sha256(json.dumps(runner.llm_client.executor.model, sort_keys=True).encode()).hexdigest(),
        'config_fingerprint': hashlib.sha256(json.dumps({'planner':opts, 'model':runner.llm_client.executor.model}, sort_keys=True).encode()).hexdigest(),
        'functional_correctness_proven': False}
    try:
        runner.run(task, resume=args.resume, end_stage='stage4')
        first_metrics = json.loads((root/'plan/metrics.json').read_text())
        result['initial_run_metrics'] = first_metrics
        gate = json.loads((root/'plan/stage4/planning_gate_report.json').read_text())
        if gate['status'] != 'passed':
            raise ValueError('Stage4 returned without a passed planning gate')
        runner.run(task, resume=True, end_stage='stage4')
        reuse = json.loads((root/'plan/metrics.json').read_text())
        if reuse['api_attempts'] != first_metrics['api_attempts']:
            raise ValueError('Acceptance resume unexpectedly invoked the model')
        result.update(status='passed', resume_verification='passed', traceability_counts=gate['counts'])
    except Exception as exc:
        result.update(status='blocked', error_type=type(exc).__name__, error=str(exc))
        logger.exception('Acceptance blocked')
    result['elapsed_seconds'] = time.monotonic() - started
    for name, path in [('metrics', 'plan/metrics.json'), ('gate', 'plan/stage4/planning_gate_report.json')]:
        if (root / path).exists():
            result[name] = json.loads((root / path).read_text())
    atomic_write_json(root / 'acceptance_report.json', result)
    print(json.dumps({'case':case, 'status':result['status'], 'report':str(root/'acceptance_report.json')}, ensure_ascii=False))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
