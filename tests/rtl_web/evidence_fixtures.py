"""Portable test-only evidence, never published as investor data."""
from pathlib import Path
from zerorepo.rtl_web.artifacts import Artifacts

def example_bundle(settings, store):
    art=Artifacts(settings.data,store)
    root=settings.data/'fixture-input';root.mkdir(exist_ok=True)
    def artifact(name,text,kind):
        path=root/name;path.write_text(text);return art.add(path,kind,display=True)
    spec=artifact('spec.md','# Test fixture\n','spec')
    planner=artifact('plan.json','{"modules":[]}','planning')
    versions=[];validations=[]
    for i in (1,2):
        rtl=root/f'rtl{i}';rtl.mkdir(exist_ok=True)
        (rtl/'dut.v').write_text(f'module dut; wire a = 1\'b{i-1}; endmodule\n')
        (rtl/'defines.v').write_text('`define WIDTH 32\n')
        v=art.snapshot(rtl,f'fixture-v{i}','fixture-history');versions.append(v)
        report=artifact(f'report{i}.txt',f'fixture: {"FAIL" if i==1 else "PASS"}\n','report')
        import json
        wave={'validation_id':f'fixture-check{i}','version_id':v['version_id'],'waveform_sha256':'a'*64,'timescale':{'value':1,'unit':'ps'},'start_ticks':'0','end_ticks':'20','signals':[],'sample_markers':[],'missing_signals':[],'marker_status':'verified'}
        w=artifact(f'wave{i}.json',json.dumps(wave),'waveform')
        val={'validation_id':wave['validation_id'],'version_id':v['version_id'],'run_id':'fixture-history','kind':'final_system' if i==2 else 'candidate','verdict':'pass' if i==2 else 'fail','simulation_completed':True,'total_samples':2,'mismatched_samples':0 if i==2 else 1,'first_failure_ticks':None if i==2 else '10','report_artifact_id':report['artifact_id'],'waveform_artifact_id':w['artifact_id'],'waveform_sha256':'a'*64}
        store.put('validation',val['validation_id'],val);validations.append(val)
    store.put('run','fixture-history',{'run_id':'fixture-history','case_id':'e203','origin':'historical'})
    b={'title':'Test-only fixture','summary':'Not investor evidence','case_id':'e203','bundle_id':settings.bundle_id,'source_run_id':'fixture-history','origin':'historical','source_fingerprint':'b'*64,'spec_artifact_id':spec['artifact_id'],'planner_artifact_id':planner['artifact_id'],'versions':versions,'validations':validations,'artifacts':store.list_records('artifact'),'modules':[],'events':[],'comparison_pair':{'before_validation_id':'fixture-check1','after_validation_id':'fixture-check2'}}
    store.put('bundle',b['bundle_id'],b)
    return b
