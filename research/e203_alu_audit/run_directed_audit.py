"""Small, legal instruction witnesses with manually computed observations."""
from run_public_audit import OUT, v
from pathlib import Path
import os
import sys
import tempfile

BODY=r'''
  task automatic defaults;
    i_valid=0; nice_xs_off=0; oitf_empty=1; i_itag=0;
    i_rs1=0; i_rs2=0; i_imm=0; i_info=0; i_pc=32'h1000;
    i_instr=0; i_pc_vld=1; i_rdidx=1; i_rdwen=1;
    i_ilegl=0; i_buserr=0; i_misalgn=0; flush_req=0; flush_pulse=0;
    cmt_o_ready=1; wbck_o_ready=1; mdv_nob2b=1; nonflush_cmt_ena=1;
    csr_access_ilgl=0; read_csr_dat=32'h100;
    agu_icb_cmd_ready=1; agu_icb_rsp_valid=0; agu_icb_rsp_err=0;
    agu_icb_rsp_excl_ok=0; agu_icb_rsp_rdata=0;
    nice_req_ready=1; nice_rsp_multicyc_valid=0; nice_longp_wbck_ready=1;
    i_nice_cmt_off_ilgl=0; wavedrom_enable=0; wavedrom_title=0;
  endtask
  task automatic reset_case;
    @(negedge clk); defaults(); rst_n=0;
    repeat(3) @(negedge clk);
    rst_n=1;
    @(negedge clk);
  endtask
  task automatic observe(input string name,input integer kind,input logic[31:0] expected);
    logic[31:0] actual_ref,actual_dut;
    logic qualified_ref,qualified_dut;
    integer age;
    begin
      i_valid=1;
      #1;
      age=0;
      while(!tb.i_ready_ref && age<100) begin
        @(negedge clk); #1; age++;
      end
      qualified_ref=tb.cmt_o_valid_ref && tb.i_ready_ref;
      qualified_dut=tb.cmt_o_valid_dut && tb.i_ready_dut;
      case(kind)
        0: begin actual_ref=tb.wbck_o_wdat_ref; actual_dut=tb.wbck_o_wdat_dut;
          qualified_ref &= tb.wbck_o_valid_ref; qualified_dut &= tb.wbck_o_valid_dut; end
        1: begin actual_ref={29'b0,tb.cmt_o_wfi_ref,tb.cmt_o_ebreak_ref,tb.cmt_o_ecall_ref};
          actual_dut={29'b0,tb.cmt_o_wfi_dut,tb.cmt_o_ebreak_dut,tb.cmt_o_ecall_dut}; end
        2: begin actual_ref={28'b0,tb.agu_icb_cmd_wmask_ref}; actual_dut={28'b0,tb.agu_icb_cmd_wmask_dut};
          qualified_ref &= tb.agu_icb_cmd_valid_ref; qualified_dut &= tb.agu_icb_cmd_valid_dut; end
        3: begin actual_ref={31'b0,tb.cmt_o_bjp_rslv_ref}; actual_dut={31'b0,tb.cmt_o_bjp_rslv_dut}; end
        default: begin actual_ref=tb.wbck_csr_dat_ref; actual_dut=tb.wbck_csr_dat_dut;
          qualified_ref &= tb.csr_ena_ref && tb.csr_wr_en_ref;
          qualified_dut &= tb.csr_ena_dut && tb.csr_wr_en_dut; end
      endcase
      $display("WITNESS name=%s info=%08x rs1=%08x rs2=%08x expected=%08x golden=%08x dut=%08x golden_qualified=%0d dut_qualified=%0d golden_ok=%0d dut_ok=%0d age=%0d",
        name,i_info,i_rs1,i_rs2,expected,actual_ref,actual_dut,qualified_ref,qualified_dut,
        qualified_ref && actual_ref==expected,qualified_dut && actual_dut==expected,age);
      @(negedge clk); i_valid=0;
    end
  endtask
  initial begin
    rst_n=0; defaults();
    reset_case();
    i_info[`E203_DECINFO_GRP]=`E203_DECINFO_GRP_ALU;
    i_info[`E203_DECINFO_RV32]=1; i_info[`E203_DECINFO_ALU_ADD]=1;
    i_rs1=7; i_rs2=5; i_instr=32'h002080b3;
    observe("ADD_7_5",0,12);
    reset_case();
    i_info[`E203_DECINFO_GRP]=`E203_DECINFO_GRP_ALU;
    i_info[`E203_DECINFO_RV32]=1; i_info[`E203_DECINFO_ALU_ECAL]=1;
    i_rdwen=0; i_instr=32'h00000073; observe("ECALL",1,1);
    reset_case();
    i_info[`E203_DECINFO_GRP]=`E203_DECINFO_GRP_ALU;
    i_info[`E203_DECINFO_RV32]=1; i_info[`E203_DECINFO_ALU_EBRK]=1;
    i_rdwen=0; i_instr=32'h00100073; observe("EBREAK",1,2);
    reset_case();
    i_info[`E203_DECINFO_GRP]=`E203_DECINFO_GRP_AGU;
    i_info[`E203_DECINFO_RV32]=1; i_info[`E203_DECINFO_AGU_STORE]=1;
    i_info[`E203_DECINFO_AGU_SIZE]=2; i_rs1=32'h1000;
    i_rs2=32'h12345678; i_rdwen=0; i_instr=32'h0020a023;
    observe("SW_MASK",2,15);
    reset_case();
    i_info[`E203_DECINFO_GRP]=`E203_DECINFO_GRP_BJP;
    i_info[`E203_DECINFO_RV32]=1; i_info[`E203_DECINFO_BJP_BXX]=1;
    i_info[`E203_DECINFO_BJP_BGT]=1; i_rs1=7; i_rs2=7;
    i_rdwen=0; i_instr=32'h0020d263; i_imm=4;
    observe("BGE_EQUAL",3,1);
    reset_case();
    i_info[`E203_DECINFO_GRP]=`E203_DECINFO_GRP_CSR;
    i_info[`E203_DECINFO_RV32]=1; i_info[`E203_DECINFO_CSR_CSRRW]=1;
    i_info[`E203_DECINFO_CSR_RS1IMM]=1; i_info[`E203_DECINFO_CSR_ZIMMM]=31;
    i_info[`E203_DECINFO_CSR_CSRIDX]=12'h340; i_instr=32'h340fd0f3;
    observe("CSRRWI_31",4,31);
    reset_case();
    i_info[`E203_DECINFO_GRP]=`E203_DECINFO_GRP_MULDIV;
    i_info[`E203_DECINFO_RV32]=1; i_info[`E203_DECINFO_MULDIV_MUL]=1;
    i_rs1=7; i_rs2=5; i_instr=32'h022080b3;
    observe("MUL_7_5",0,35);
    reset_case();
    i_info[`E203_DECINFO_GRP]=`E203_DECINFO_GRP_MULDIV;
    i_info[`E203_DECINFO_RV32]=1; i_info[`E203_DECINFO_MULDIV_DIV]=1;
    i_rs1=20; i_rs2=3; i_instr=32'h0220c0b3;
    observe("DIV_20_3",0,6);
    $finish;
  end
endmodule
'''

def run(label,candidate):
    with tempfile.TemporaryDirectory(prefix='e203_directed_',dir='/tmp') as td:
        _,support=v.collect_agent_files(candidate)
        if candidate=='/home/mokita/RealBench/e203_hbirdv2/e203_exu_alu':
            support += [str(Path(candidate)/'verification'/n) for n in ['e203_exu_nice.v','sirv_gnrl_bufs.v','sirv_gnrl_dffs.v','sirv_gnrl_xchecker.v']]
        sources,includes,error=v.stage_verification_files(td,support)
        if error: raise RuntimeError(error)
        stim=Path(sources[1]); header=stim.read_text().split('    task wavedrom_start')[0]
        stim.write_text('`include "e203_defines.v"\n'+header+BODY)
        (OUT/'directed_stimulus.sv').write_text(stim.read_text())
        env=os.environ.copy(); env['PATH']=v.CONDA_REALBENCH_BIN+':'+env['PATH']
        code,out,err=v.run_command(['verilator',*v.VERILATOR_FLAGS,*['-I'+p for p in includes],*sources],td,env,300)
        (OUT/f'{label}_directed_compile.log').write_text(out+err)
        if code!=0: raise RuntimeError(err[-3000:])
        code,out,err=v.run_command([str(Path(td)/'obj_dir/Vtb')],td,env,300)
        (OUT/f'{label}_directed.log').write_text(out+err)
        print('\n'.join(s for s in out.splitlines() if s.startswith('WITNESS')))

if __name__=='__main__': run(sys.argv[1],sys.argv[2])
