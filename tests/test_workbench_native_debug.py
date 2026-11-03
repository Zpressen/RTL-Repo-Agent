import json


def test_native_check_builds_debug_context_without_invented_failure_times(tmp_path):
    from zerorepo.rtl_impl.debug_agent.trace_report import build_trace_report
    rtl=tmp_path/'counter.v';rtl.write_text('module counter(input wire clk,output reg [7:0] count);always @(posedge clk) count<=count+1;endmodule')
    observation={'scope':'functional','execution_status':'completed','checks_executed':8,'failures':3,'simulation_completed':True,
                 'check_id':'check-actual','version_id':'version-actual','tree_sha256':'a'*64,'verification_spec_id':'verification-actual','testset_sha256':'b'*64}
    report,_=build_trace_report(rtl_path=rtl,sim_log_json=json.dumps(observation),output_dir=tmp_path,
                               planner_module_name='counter',runtime_top_module='counter')
    assert report['verification_ref']['check_id']=='check-actual'
    assert report['verification_ref']['checks_executed']==8 and report['total_mismatches']==3
    assert report['fail_time'] is None and report['raw_fail_outputs']==[]


def test_native_repository_diagnostics_keep_actual_failure_time():
    from zerorepo.rtl_impl.repo_react.tools import _extract_first_fail_time
    observation={'scope':'functional','diagnostic_excerpt':'Hint: Output done has 2 mismatches. First at time 150'}
    assert _extract_first_fail_time(json.dumps(observation))==150
