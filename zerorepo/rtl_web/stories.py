"""Audited historical stories; browser reads never run tools or write memory."""
from __future__ import annotations
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from .story_schemas import StoryBundle, StoryInput
from .schemas import DemoError, Validation
from .store import dump
from .artifacts import Artifacts, safe_path, sha, tree_manifest, atomic_json


def digest(value):
    return hashlib.sha256(dump(value).encode()).hexdigest()


def memory_digest(memory):
    return digest({k: memory[k] for k in ('title', 'lesson', 'applicability', 'limitations')})


def prepare_story(value):
    data = StoryBundle.model_validate(value).model_dump(mode='json')
    expected = 'story-' + digest({k: v for k, v in data.items() if k != 'story_id'})
    if data['story_id'] and data['story_id'] != expected:
        raise ValueError('Story digest mismatch')
    data['story_id'] = expected
    for memory in data['memories']:
        if memory['content_sha256'] != memory_digest(memory):
            raise ValueError('Memory content digest mismatch')
    return data


def story_references(data):
    """Typed roots, including internal entities; not a string-ID heuristic."""
    result = []
    def explicit(items):
        result.extend((i['kind'], i['id'], i.get('sha256')) for i in items)
    explicit(data['evidence_refs']); explicit(data['review']['evidence_refs'])
    for m in data['memories']:
        result.append(('run', m['source_run_id'], None))
        if m['source_version_id']: result.append(('version', m['source_version_id'], None))
        explicit(m['evidence_refs'])
    for use in data['uses']:
        result.append(('run', use['run_id'], None))
        for event in use['events']:
            result.append(('artifact', event['event_artifact_id'], None))
            for key, kind in [('candidate_version_id', 'version'), ('validation_id', 'validation')]:
                if event.get(key): result.append((kind, event[key], None))
    for event in data['lifecycle_events']: explicit(event['evidence_refs'])
    for item in data['comparisons']:
        result.extend(('run', item[k], None) for k in ['with_memory_run_id', 'without_memory_run_id'])
        explicit(item['evidence_refs'])
    return result


def check_public_text(value):
    encoded = dump(value)
    if re.search(r'sk-[A-Za-z0-9_-]{16,}|-----BEGIN .*PRIVATE KEY-----|(?:/home/|/etc/|/tmp/|/run/user/|[A-Za-z]:\\\\)', encoded):
        raise ValueError('Private content in public projection')


def validate_story(data, get, artifact_file=None, version_path=None):
    data = prepare_story(data)
    from .seed import _references
    pending = list(story_references(data))
    seen = set()
    while pending:
        kind, ident, expected = pending.pop()
        record = get(kind, ident)
        actual = record.get('tree_sha256') if kind == 'version' else record.get('sha256')
        if expected and actual != expected: raise ValueError('Evidence digest mismatch')
        if (kind, ident) in seen: continue
        seen.add((kind, ident))
        pending.extend((k, i, None) for k, i in _references(record))
        if kind == 'run':
            if record.get('case_id') != data['case_id'] or record.get('origin') != 'historical':
                raise ValueError('Foreign or nonhistorical run')
        if kind == 'version':
            run = get('run', record['run_id'])
            if run.get('case_id') != data['case_id'] or run.get('origin') != 'historical': raise ValueError('Foreign version')
            if version_path: version_path(record)
        if kind == 'validation':
            if record.get('verdict') == 'pass' and not record.get('simulation_completed'):
                raise ValueError('PASS requires completed simulation')
            version = get('version', record['version_id'])
            run = get('run', record['run_id'])
            if version['run_id'] != record['run_id'] or run.get('case_id') != data['case_id']:
                raise ValueError('Validation binding mismatch')
            report = get('artifact', record['report_artifact_id'])
            if artifact_file:
                from .artifacts import parse_report
                parsed = parse_report(artifact_file(report).read_text())
                if record.get('verdict') != parsed['verdict']: raise ValueError('Report verdict mismatch')
            if record.get('waveform_artifact_id'):
                wave = get('artifact', record['waveform_artifact_id'])
                if record.get('waveform_sha256') != wave['sha256']: raise ValueError('Wave binding mismatch')
                if artifact_file: artifact_file(wave)
        if kind == 'artifact' and artifact_file: artifact_file(record)
    revisions = {m['revision_id']: m for m in data['memories']}
    for memory in data['memories']:
        if memory['source_version_id'] and get('version',memory['source_version_id'])['run_id'] != memory['source_run_id']:
            raise ValueError('Memory source version mismatch')
        if memory['validation_level'] != 'unverified':
            vals=[get('validation',r['id']) for r in memory['evidence_refs'] if r['kind']=='validation']
            if memory['validation_level']=='formal' or not any(v['run_id']==memory['source_run_id'] and (memory['validation_level']!='final_system' or v['kind']=='final_system') for v in vals):
                raise ValueError('Unproven memory validation level')
    for use in data['uses']:
        provided = set()
        last_sequence = 0
        for event in use['events']:
            # The actual trusted journal is required, not a reviewer/model stage label.
            if not artifact_file: raise ValueError('Use journal unavailable')
            proof = json.loads(artifact_file(get('artifact', event['event_artifact_id'])).read_text())
            if any(proof.get(k) != v for k, v in [('revision_id', use['revision_id']), ('outer_run_id', use['run_id']), ('kind', event['kind'])]):
                raise ValueError('Use journal identity mismatch')
            if proof.get('snapshot_sha256') != use['snapshot_sha256']: raise ValueError('Use snapshot mismatch')
            if not isinstance(proof.get('sequence'),int) or proof['sequence']<=last_sequence:raise ValueError('Use event order mismatch')
            last_sequence=proof['sequence']
            if event['kind'] == 'provided': provided.add(use['revision_id'])
            if event['kind'] == 'applied':
                if use['revision_id'] not in provided or not proof.get('diff_sha256') or not proof.get('target_files'):
                    raise ValueError('No actual application evidence')
                if not event['candidate_version_id']: raise ValueError('Missing candidate version')
                v = get('version', event['candidate_version_id'])
                if v['run_id'] != use['run_id'] or v['tree_sha256'] != proof.get('tree_sha256'):
                    raise ValueError('Application version mismatch')
            if event['kind'] == 'validation_observed':
                if not event['validation_id']: raise ValueError('Missing validation')
                val = get('validation', event['validation_id'])
                if val['run_id'] != use['run_id'] or val['verdict'] != proof.get('verdict'):
                    raise ValueError('Observed verdict mismatch')
                if proof.get('tree_sha256') != get('version',val['version_id'])['tree_sha256']:
                    raise ValueError('Observed version mismatch')
                if proof.get('report_sha256') and proof['report_sha256'] != get('artifact',val['report_artifact_id'])['sha256']:
                    raise ValueError('Observed report mismatch')
        if use['revision_id'] not in revisions: raise ValueError('Missing revision')
    for change in data['lifecycle_events']:
        if change['kind'] in {'superseded','retired'}:
            if not change['evidence_refs']:raise ValueError('Revision requires new evidence')
            if change['kind']=='superseded':
                child=revisions.get(change['replacement_revision_id'])
                old=revisions[change['revision_id']]
                if not child or child['parent_revision_id']!=old['revision_id'] or child['content_sha256']==old['content_sha256']:
                    raise ValueError('No substantive revision')
    for comp in data['comparisons']:
        if comp['with_memory_run_id']==comp['without_memory_run_id']:raise ValueError('Comparison needs independent runs')
    check_public_text({k: data[k] for k in ('memories', 'lifecycle_events', 'comparisons')})
    return data


def publish_story(store, data, activate=False):
    data = prepare_story(data)
    if data['review']['status'] != 'approved' or not data['review']['reviewer']:
        raise ValueError('Maintainer review required')
    if data['material_kind'] != 'real':
        raise ValueError('Synthetic materials cannot be published')
    art = Artifacts(store.root, store)
    validate_story(data, lambda k, i: store.get(k, i), art.file, art.version_path)
    with store.connect(True) as c:
        old = c.execute('SELECT owner,payload FROM records WHERE kind=? AND id=?', ('story', data['story_id'])).fetchone()
        if old and (old[0] is not None or old[1] != dump(data)): raise ValueError('Immutable story conflict')
        if not old: c.execute('INSERT INTO records VALUES(?,?,NULL,?)', ('story', data['story_id'], dump(data)))
        if activate:
            c.execute('INSERT INTO controls VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', ('story:' + data['case_id'], dump(data['story_id'])))
    return data


def load_story(store, ident):
    try:
        data = prepare_story(store.get('story', ident))
    except DemoError:
        raise DemoError('not_found', '故事不存在或未公开。', 404) from None
    except (ValueError, KeyError, TypeError):
        raise DemoError('story_evidence_invalid', '故事内容已损坏，暂不展示。', 409) from None
    if data['review']['status'] != 'approved' or data['material_kind'] != 'real':
        raise DemoError('not_found', '故事不存在或未公开。', 404)
    art = Artifacts(store.root, store)
    try: return validate_story(data, lambda k, i: store.get(k, i), art.file, art.version_path)
    except (ValueError, OSError, KeyError, DemoError):
        raise DemoError('story_evidence_invalid', '故事证据不完整，暂不展示成功结论。', 409) from None


def story_view(store, case_id, ident=None):
    from .cases import case_config
    from .story_schemas import Optimization
    case_config(case_id)
    ident = ident or store.control('story:' + case_id)
    data = load_story(store, ident) if ident else None
    if data and data['case_id'] != case_id: raise DemoError('story_context_invalid', '故事与案例不一致。', 422)
    memories = data['memories'] if data else []
    uses = data['uses'] if data else []
    lifecycle = data['lifecycle_events'] if data else []
    revisions = {m['revision_id']: m for m in memories}
    actual = [u for u in uses if u['run_id'] != revisions[u['revision_id']]['source_run_id'] and {'applied', 'validation_observed'} <= {e['kind'] for e in u['events']}]
    changed = [e for e in lifecycle if e['kind'] in {'superseded', 'retired'} and e['evidence_refs'] and e['revision_id'] in {u['revision_id'] for u in actual}]
    status = 'complete' if actual and changed else 'partial' if uses else 'archived_only' if memories else 'empty'
    comparisons = []
    for c in data['comparisons'] if data else []:
        fields = {'input', 'spec', 'model', 'profile', 'verifier', 'resources', 'budget'}
        comparable = fields <= c['with_conditions'].keys() and all(c['with_conditions'][k] == c['without_conditions'].get(k) for k in fields)
        comparisons.append({**c, 'state': 'single_observation' if comparable else 'not_attributable', 'message': '单案例一次观察，不能推论普遍收益' if comparable else '条件不一致，不能归因于记忆'})
    result = dict(schema_version='rtl-demo-story-view-v1', case_id=case_id, story_id=ident,
                  fingerprint=digest(data) if data else None, origin='historical',
                  optimization=Optimization().model_dump(), experience=dict(state=status,
                  missing_evidence=[] if status == 'complete' else ['真实跨运行采用及验证' if not actual else '有新证据支撑的修订或淘汰'],
                  memories=memories, uses=uses, lifecycle_events=lifecycle, comparisons=comparisons), runs=[])
    if data:
        from .seed import _references
        pending = [(k, i) for k, i, _ in story_references(data)]
        records = {}
        while pending:
            key = pending.pop()
            if key in records: continue
            records[key] = store.get(*key)
            pending.extend(_references(records[key]))
        run_ids = sorted(i for k, i in records if k == 'run')
        for rid in run_ids:
            r = records[('run', rid)]
            versions = []
            for (kind, _), v in records.items():
                if kind != 'version' or v['run_id'] != rid: continue
                versions.append({k: v[k] for k in ('version_id', 'run_id', 'tree_sha256', 'parent_version_id', 'file_manifest', 'modules') if k in v})
            vals = [v for (kind, _), v in records.items() if kind == 'validation' and v['run_id'] == rid]
            result['runs'].append(dict(run_id=rid, case_id=case_id, origin=r['origin'], versions=versions,
                                       validations=[{k: v[k] for k in Validation.model_fields if k in v} for v in vals]))
    check_public_text(result)
    return result


def validate_story_context(store, ctx):
    ident = ctx.get('story_id')
    if not ident:
        if ctx.get('memory_revision_id') or ctx.get('memory_use_id'):
            raise DemoError('story_context_invalid', '请选择经验所属故事。', 422)
        return ctx
    data = load_story(store, ident)
    if data['case_id'] != ctx['case_id']: raise DemoError('story_context_invalid', '故事属于其他案例。', 422)
    revisions = {m['revision_id']: m for m in data['memories']}
    if ctx.get('memory_revision_id') and ctx['memory_revision_id'] not in revisions:
        raise DemoError('story_context_invalid', '经验版本不属于当前故事。', 422)
    if ctx.get('memory_use_id'):
        use = next((u for u in data['uses'] if u['use_id'] == ctx['memory_use_id']), None)
        if not use or use['revision_id'] != ctx.get('memory_revision_id'):
            raise DemoError('story_context_invalid', '经验使用记录不一致。', 422)
        if ctx.get('run_id') and ctx['run_id'] != use['run_id']:
            raise DemoError('story_context_invalid', '经验与运行选择不一致。', 422)
    return ctx


def import_story(settings, source, dry_run=False, activate=False):
    """Preflight entire closure, then copy immutable files in one DB transaction."""
    from .store import Store
    from .deployment_models import relative_path
    source = Path(source).absolute()
    if source.is_symlink() or source.stat().st_size > 8*1024**2: raise ValueError('Invalid manifest')
    value = StoryInput.model_validate_json(source.read_text()).model_dump(mode='json')
    story = prepare_story(value['story'])
    if story['case_id'] != settings.case['case_id']: raise ValueError('Input case mismatch')
    if story['material_kind'] != 'real' or story['review']['status'] != 'approved' or not story['review']['reviewer']:
        raise ValueError('Reviewed real materials required')
    store = Store(settings.data)
    new = {}
    for row in value['records']:
        if set(row) != {'kind', 'id', 'payload'} or row['kind'] not in {'run', 'version', 'validation', 'artifact'}:
            raise ValueError('Unknown input record')
        if row['payload'].get('owner_session') or row['payload'].get(row['kind']+'_id') != row['id']:
            raise ValueError('Private or mismatched input record')
        key = (row['kind'], row['id'])
        if key in new: raise ValueError('Duplicate input record')
        new[key] = row['payload']
    files = {}
    for f in value['files']:
        key = relative_path(f['storage_key'])
        if not key.startswith(('artifacts/', 'snapshots/')) or key in files: raise ValueError('Unsafe storage key')
        path = safe_path(source.parent, relative_path(f['source']))
        if path.is_symlink() or not path.is_file() or path.stat().st_size != f['size_bytes'] or sha(path) != f['sha256']:
            raise ValueError('Input file digest mismatch')
        files[key] = (path, f)
    def get(kind, ident):
        return new[(kind, ident)] if (kind, ident) in new else store.get(kind, ident)
    art = Artifacts(settings.data, store)
    used_files = set()
    def file_for(record):
        key = record['storage_key']
        if key in files:
            path, f = files[key]; used_files.add(key)
            if f['sha256'] != record['sha256'] or f['size_bytes'] != record['size_bytes']: raise ValueError('Artifact binding mismatch')
            return path
        return art.file(record)
    validate_story(story, get, file_for)
    # Validate transitive record/file closure, including module artifacts and tiles.
    from .seed import _references
    pending = [(k, i) for k, i, _ in story_references(story)]; seen = set()
    while pending:
        key = pending.pop()
        if key in seen: continue
        seen.add(key); record = get(*key)
        pending.extend(_references(record))
        if key[0] == 'artifact':
            path = file_for(record)
            if record.get('exposure') == 'display': check_public_text(path.read_text())
            if record['kind'] in {'waveform', 'waveform_tile'}: pending.extend(_references(json.loads(path.read_text())))
        if key[0] == 'version':
            storage = relative_path(record['storage_key'])
            manifest = record['file_manifest']
            if not manifest or digest(manifest) != record['tree_sha256']:
                raise ValueError('RTL tree digest mismatch')
            for entry in manifest:
                name = relative_path(storage + '/' + entry['path'])
                if name in files:
                    path, f = files[name]; used_files.add(name)
                    if sha(path) != entry['sha256']: raise ValueError('RTL source changed')
                else:
                    path = safe_path(settings.data, name)
                    if not path.is_file() or sha(path) != entry['sha256']: raise ValueError('RTL source missing or changed')
    if set(new) - seen or set(files) - used_files: raise ValueError('Unreachable story input')
    with store.connect() as c:
        for (kind, ident), payload in {**new, ('story', story['story_id']): story}.items():
            old = c.execute('SELECT owner,payload FROM records WHERE kind=? AND id=?', (kind, ident)).fetchone()
            if old and (old[0] is not None or old[1] != dump(payload)): raise ValueError('Immutable input conflict')
    if dry_run: return dict(story_id=story['story_id'], dry_run=True)
    created = []
    try:
        with store.connect(True) as c:
            for (kind, ident), payload in {**new, ('story', story['story_id']): story}.items():
                old = c.execute('SELECT owner,payload FROM records WHERE kind=? AND id=?', (kind, ident)).fetchone()
                if old and (old[0] is not None or old[1] != dump(payload)): raise ValueError('Immutable input conflict')
                if not old: c.execute('INSERT INTO records VALUES(?,?,NULL,?)', (kind, ident, dump(payload)))
            for key, (src, f) in files.items():
                dst = safe_path(settings.data, key)
                if dst.exists():
                    if dst.is_symlink() or sha(dst) != f['sha256']: raise ValueError('Immutable file conflict')
                else:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    fd, name = tempfile.mkstemp(dir=dst.parent)
                    try:
                        with os.fdopen(fd, 'wb') as stream: stream.write(src.read_bytes())
                        os.replace(name, dst); created.append(dst)
                    finally:
                        if os.path.exists(name): os.unlink(name)
            if activate: c.execute('INSERT INTO controls VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', ('story:'+story['case_id'], dump(story['story_id'])))
    except BaseException:
        for path in reversed(created): path.unlink(missing_ok=True)
        raise
    return dict(story_id=story['story_id'], dry_run=False, activated=activate)


def review_memory(settings, source, dry_run=False):
    from .store import Store
    from zerorepo.rtl_impl.rtl_memory.ledger import MemoryLedger
    source=Path(source)
    if source.is_symlink() or source.stat().st_size>128*1024:raise ValueError('Invalid review manifest')
    data=json.loads(source.read_text())
    allowed={'schema_version','revision','reviewer','decision','reason','evidence_refs','replacement_revision_id'}
    if set(data)-allowed or data.get('schema_version')!='rtl-memory-review-v1' or not data.get('reviewer'):
        raise ValueError('Maintainer review required')
    revision=data['revision']
    if revision['case_id']!=settings.case['case_id']:raise ValueError('Memory case mismatch')
    store=Store(settings.data);art=Artifacts(settings.data,store)
    run=store.get('run',revision['source_run_id'],revision.get('owner'))
    if run['case_id']!=revision['case_id']:raise ValueError('Memory source mismatch')
    refs=revision.get('evidence_refs',[])+data.get('evidence_refs',[])
    if not refs:raise ValueError('Source evidence required')
    for ref in refs:
        record=store.get(ref['kind'],ref['id'],revision.get('owner'))
        if ref['kind']=='artifact':
            art.file(record)
            if not ref.get('sha256') or record['sha256']!=ref['sha256']:raise ValueError('Memory evidence changed')
    level=revision.get('validation_level','unverified')
    if level!='unverified':
        vals=[store.get('validation',r['id'],revision.get('owner')) for r in refs if r['kind']=='validation']
        if not any(v['run_id']==run['run_id'] and (level!='final_system' or v['kind']=='final_system') and v.get('simulation_completed') for v in vals):
            raise ValueError('Unproven validation level')
    if not data.get('reason') or not data.get('evidence_refs') or data.get('decision') not in {'approved','superseded','retired'}:raise ValueError('Invalid review decision')
    library=MemoryLedger(settings.memory_library)
    value=library.add(revision,dry_run=True)
    if data['decision']=='superseded':
        child=library.get(data.get('replacement_revision_id'))
        if child.get('parent_revision_id') != value['revision_id']:raise ValueError('Unrelated replacement')
    if value['revision_id'] in library.state()['revisions']:
        library.review(value['revision_id'],data['decision'],data['reason'],data['evidence_refs'],data.get('replacement_revision_id'),dry_run=True)
    if not dry_run:value=library.add(revision)
    if not dry_run:library.review(value['revision_id'],data['decision'],data['reason'],data['evidence_refs'],data.get('replacement_revision_id'))
    return dict(revision_id=value['revision_id'],dry_run=dry_run)


def export_story_static(settings, store, case_id, out):
    view=story_view(store,case_id)
    contents={};waves={};out=Path(out);dest=out/'stories'/(view['story_id'] or 'empty')
    if view['story_id']:
        data=load_story(store,view['story_id']);art=Artifacts(settings.data,store)
        from .seed import _references
        pending=[(k,i) for k,i,_ in story_references(data)];seen=set()
        while pending:
            key=pending.pop()
            if key in seen:continue
            seen.add(key);record=store.get(*key);pending.extend(_references(record))
            if key[0]!='artifact' or record.get('exposure')!='display':continue
            path=art.file(record);raw=path.read_text();check_public_text(raw)
            name=record['artifact_id']+'.json';url=f'/cases/{case_id}/stories/{view["story_id"]}/{name}'
            if record['kind']=='waveform_tile':atomic_json(dest/name,json.loads(raw))
            elif record['kind']=='waveform':
                wave=json.loads(raw)
                for tile in wave.get('tiles',[]):
                    aid=tile['artifact_id'];a=store.get('artifact',aid)
                    if a.get('exposure')!='display':raise ValueError('Private waveform tile')
                    atomic_json(dest/(aid+'.json'),json.loads(art.file(a).read_text()))
                    tile['url']=f'/cases/{case_id}/stories/{view["story_id"]}/{aid}.json'
                waves[wave['validation_id']]=url;atomic_json(dest/name,wave)
            else:
                contents[record['artifact_id']]=url;atomic_json(dest/name,dict(content=raw,sha256=record['sha256']))
    view.update(content_urls=contents,waveform_urls=waves)
    atomic_json(out/'stories/manifest.json',view)
    return view
