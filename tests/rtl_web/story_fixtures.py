"""Synthetic UI/contract fixtures. Never eligible for public activation."""
def story_fixture(case_id='e203'):
    return dict(schema_version='rtl-demo-story-v1', case_id=case_id, origin='historical',
                material_kind='synthetic', source_fingerprint='0'*64,
                review=dict(status='approved', reviewer='test', evidence_refs=[]),
                memories=[], uses=[], lifecycle_events=[], comparisons=[], evidence_refs=[])


def story_scenario(kind='archived'):
    """Schema-only scenarios; their invented references cannot pass publication."""
    from zerorepo.rtl_web.stories import memory_digest
    data=story_fixture()
    memory=dict(memory_id='synthetic-memory',revision_id='synthetic-v1',title='Synthetic handshake rule',
                lesson='Test fixture only',applicability=['test'],limitations=['Not real execution'],
                source_run_id='synthetic-a',backend='synthetic',validation_level='unverified',state='approved_active',evidence_refs=[])
    memory['content_sha256']=memory_digest(memory)
    data['memories']=[memory]
    if kind in {'pass','fail','missing_reference','cross_case'}:
        data['uses']=[dict(use_id='synthetic-use',revision_id='synthetic-v1',run_id='synthetic-b',backend='synthetic',snapshot_sha256='1'*64,
                          events=[dict(event_id='synthetic-'+stage,kind=stage,event_artifact_id='synthetic-'+stage+'-proof',
                                       **({'candidate_version_id':'synthetic-candidate'} if stage=='applied' else {}),
                                       **({'validation_id':'synthetic-'+kind} if stage=='validation_observed' else {}))
                                  for stage in ['retrieved','provided','application_declared','applied','validation_observed']])]
    if kind=='revision':
        second={**memory,'revision_id':'synthetic-v2','parent_revision_id':'synthetic-v1','lesson':'Additional synthetic boundary'}
        second['content_sha256']=memory_digest(second);data['memories'].append(second)
        data['lifecycle_events']=[dict(event_id='synthetic-revision',revision_id='synthetic-v1',kind='superseded',replacement_revision_id='synthetic-v2',reason='Synthetic boundary',evidence_refs=[dict(kind='artifact',id='synthetic-new-proof')])]
    if kind=='cross_case': data['case_id']='sdc_controller_system'
    return data
