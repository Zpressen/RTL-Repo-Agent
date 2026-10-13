"""Reproduce public traces with a passive protocol/transaction monitor.

Only staged copies under /tmp are edited. Original inputs and checker are intact.
"""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

OUT = Path(__file__).resolve().parent
P = Path('/home/mokita/RealBench/system_task/e203_exu_alu_hard/verify_test/e203_exu_alu_system_verify.py')
spec = importlib.util.spec_from_file_location('public_verifier', P)
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
MONITOR = r'''
  integer audit_valid=0, audit_normal=0, audit_exception=0;
  integer audit_accept[0:7], audit_selected[0:7];
  integer audit_cmd=0, audit_rsp=0, audit_nreq=0, audit_nrsp=0;
  integer audit_stall_change=0, audit_stalls=0, audit_flush=0;
  integer audit_mdv_wb=0, audit_amo_wb=0;
  logic audit_prev_stall=0;
  logic [235:0] audit_prev_payload;
  wire [235:0] audit_payload = {i_itag,i_rs1,i_rs2,i_imm,i_info,i_pc,i_instr,i_pc_vld,i_rdidx,i_rdwen,i_ilegl,i_buserr,i_misalgn};
  initial begin
    for(integer a=0;a<8;a++) begin audit_accept[a]=0; audit_selected[a]=0; end
  end
  always @(posedge clk) begin
    if (rst_n) begin
      if (audit_prev_stall && !flush_pulse && (!i_valid || audit_payload != audit_prev_payload))
        audit_stall_change++;
      audit_prev_stall = i_valid && !i_ready_ref;
      audit_prev_payload = audit_payload;
      if (audit_prev_stall) audit_stalls++;
      if (flush_pulse) audit_flush++;
      if (i_valid) begin
        audit_valid++;
        if (i_ilegl || i_buserr || i_misalgn) audit_exception++;
        else begin
          audit_normal++;
          audit_selected[i_info[2:0]]++;
          if (i_ready_ref) audit_accept[i_info[2:0]]++;
          if (i_info[2:0]==4 && wbck_o_valid_ref && wbck_o_ready) audit_mdv_wb++;
          if (i_info[2:0]==1 && i_info[10] && wbck_o_valid_ref && wbck_o_ready) audit_amo_wb++;
        end
      end
      if (agu_icb_cmd_valid_ref && agu_icb_cmd_ready) audit_cmd++;
      if (agu_icb_rsp_valid && agu_icb_rsp_ready_ref) audit_rsp++;
      if (nice_req_valid_ref && nice_req_ready) audit_nreq++;
      if (nice_rsp_multicyc_valid && nice_rsp_multicyc_ready_ref) audit_nrsp++;
    end else audit_prev_stall=0;
  end
  final begin
    $display("AUDIT valid=%0d normal=%0d exception=%0d stalls=%0d stall_changes_excluding_current_flush=%0d flush_cycles=%0d cmd=%0d rsp=%0d nice_req=%0d nice_rsp=%0d mdv_wb=%0d amo_wb=%0d",audit_valid,audit_normal,audit_exception,audit_stalls,audit_stall_change,audit_flush,audit_cmd,audit_rsp,audit_nreq,audit_nrsp,audit_mdv_wb,audit_amo_wb);
    for(integer a=0;a<8;a++) $display("AUDIT group=%0d selected_cycles=%0d accepted=%0d",a,audit_selected[a],audit_accept[a]);
  end
'''

def run(label, candidate):
    with tempfile.TemporaryDirectory(prefix='e203_audit_',dir='/tmp') as td:
        _, support = v.collect_agent_files(candidate)
        sources, includes, error = v.stage_verification_files(td,support)
        if error: raise RuntimeError(error)
        tb=Path(sources[0]); content=tb.read_text()
        at=content.rfind('endmodule')
        tb.write_text(content[:at]+MONITOR+content[at:])
        env=os.environ.copy(); env['PATH']=v.CONDA_REALBENCH_BIN+':'+env['PATH']
        code,out,err=v.run_command(['verilator',*v.VERILATOR_FLAGS,*['-I'+p for p in includes],*sources],td,env,300)
        (OUT/f'{label}_public_compile.log').write_text(out+err)
        if code != 0: raise RuntimeError(err[-3000:])
        results=[]
        for seed in [None,*range(1,101)]:
            name='default' if seed is None else str(seed)
            args=[str(Path(td)/'obj_dir/Vtb')]
            if seed is not None: args += [f'+verilator+seed+{seed}']
            code,out,err=v.run_command(args,td,env,300)
            passed,msg=v.parse_realbench_result(out)
            (OUT/f'{label}_public_{name}.log').write_text(out+err)
            results.append(dict(seed=name,passed=passed and code==0,reason=msg,audit=[s for s in out.splitlines() if s.startswith('AUDIT')]))
            if seed is None:
                wave=Path(td)/'wave.vcd'
                if wave.exists():
                    import shutil
                    shutil.copy2(wave,OUT/f'{label}_public_default.vcd')
        (OUT/f'{label}_public_results.json').write_text(json.dumps(results,indent=2))
        print(label,'default=',results[0]['passed'],'seeds=',sum(r['passed'] for r in results[1:]),'/100',flush=True)
        print('\n'.join(results[0]['audit']),flush=True)

if __name__=='__main__': run(sys.argv[1],sys.argv[2])
