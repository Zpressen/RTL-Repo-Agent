"""Independent differential probes. RTL and golden sources are never modified.

Run: python research/rtl_golden_audit_20261024/run_audit.py
Outputs and testbenches are kept next to this script; build products go to /tmp.
"""
from pathlib import Path
import re
import subprocess
import tempfile
import json
import os

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
GOLD = Path('/home/mokita/RealBench/system')
IV = '/home/mokita/miniconda3/envs/codex/bin/iverilog'
VVP = '/home/mokita/miniconda3/envs/codex/bin/vvp'
BUILD = Path(tempfile.mkdtemp(prefix='rtl_golden_audit_'))
results = {}


def merged(project):
    return ROOT / 'rtl_outputs' / project / '.zerorepo/workspace/merged'


def run(name, tb, sources, includes=(), defines=()):
    path = OUT / (name + '.sv')
    path.write_text(tb)
    cmd = [IV, '-g2012', '-gno-assertions', '-DDISABLE_SV_ASSERTION', '-s', 'tb', '-o', str(BUILD / name)]
    for inc in includes:
        cmd += ['-I', str(inc)]
    cmd += ['-D' + d for d in defines]
    cmd += [str(path)] + [str(s) for s in sources]
    backend = os.environ.get('AUDIT_SIMULATOR', 'iverilog')
    if backend == 'verilator':
        verilator = os.environ.get('AUDIT_VERILATOR', '/home/mokita/miniconda3/envs/codex/bin/verilator')
        cmd = [verilator, '--binary', '--timing',
               '--top-module', 'tb', '-Wno-fatal', '-j', '2', '--Mdir', str(BUILD / (name+'_obj')),
               '-o', str(BUILD / name), '-DDISABLE_SV_ASSERTION']
        cmd += ['-I' + str(inc) for inc in includes]
        cmd += ['-D' + d for d in defines]
        cmd += [str(path)] + [str(s) for s in sources]
    c = subprocess.run(cmd, text=True, capture_output=True, cwd=BUILD)
    (OUT / (name + '_compile.log')).write_text(c.stdout + c.stderr)
    if c.returncode:
        results[name] = {'compile_returncode': c.returncode, 'error': c.stderr[-4000:]}
    else:
        try:
            execute = [str(BUILD/name)] if backend == 'verilator' else [VVP, str(BUILD/name)]
            p = subprocess.run(execute, text=True, capture_output=True, timeout=45)
            (OUT / (name + '.log')).write_text(p.stdout + p.stderr)
            results[name] = {'returncode': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}
        except subprocess.TimeoutExpired:
            results[name] = {'error': 'simulation timeout'}
    print(name, json.dumps(results[name], ensure_ascii=False), flush=True)


def aes(inverse=False):
    name = 'aes_inv_cipher_top' if inverse else 'aes_cipher_top'
    proj = 'aes_inv_cipher_system_hard' if inverse else 'aes_cipher_system_hard'
    gd = GOLD/name
    sources = list(merged(proj).glob('*.v')) + [gd/(name+'_ref.sv')] + list(gd.glob('*.v'))
    common = '''`timescale 1ns/1ps
module tb;
reg clk=0; always #5 clk=~clk;
reg rst=0, ld=0, kld=0;
reg [127:0] key=0, text_in=0;
wire dr,dd; wire [127:0] tr,td;
integer n,j, samples=0, data_errors=0, done_errors=0, phase=0;
integer completion_errors=0, completions=0;
reg [127:0] expected_result;
'''
    ports = '.clk(clk),.rst(rst),.ld(ld),.key(key),.text_in(text_in)'
    if inverse:
        ports += ',.kld(kld)'
    common += f'ref_{name} ref_dut({ports},.done(dr),.text_out(tr));\n'
    common += f'{name} dut({ports},.done(dd),.text_out(td));\n'
    common += '''task sample;
begin
 @(negedge clk); samples=samples+1;
 if (dr !== dd) begin
   done_errors=done_errors+1;
   if(done_errors<8) $display("DONE_DIFF phase=%0d t=%0t ref=%b dut=%b",phase,$time,dr,dd);
 end
 if (dr === 1'b1 && (^tr !== 1'bx) && tr !== td) begin
   data_errors=data_errors+1;
   if(data_errors<8) $display("DATA_DIFF phase=%0d t=%0t ref=%h dut=%h",phase,$time,tr,td);
 end
 if (dr === 1'b1) expected_result=tr;
 if (dd === 1'b1 && (^expected_result !== 1'bx)) begin
  completions=completions+1;
  if(td !== expected_result) completion_errors=completion_errors+1;
 end
end
endtask
initial begin
 repeat(3) @(negedge clk); rst=1;
'''
    if inverse:
        common += '''// Full-width random keys and ciphertext, normal synchronous transactions.
 for(n=0;n<100;n=n+1) begin
  @(negedge clk); key={$random,$random,$random,$random}; kld=1;
  @(negedge clk); kld=0;
  repeat(14) sample;
  text_in={$random,$random,$random,$random}; ld=1;
  sample; ld=0; repeat(16) sample;
 end
 $display("NORMAL samples=%0d data_errors=%0d done_errors=%0d",samples,data_errors,done_errors);
 $display("NORMAL_COMPLETIONS count=%0d wrong_results=%0d",completions,completion_errors);
 // Repeat same-key decryptions without reloading the key.
 phase=1; samples=0; data_errors=0; done_errors=0;
 for(n=0;n<20;n=n+1) begin
  text_in={$random,$random,$random,$random}; ld=1;
  sample; ld=0; repeat(16) sample;
 end
 $display("REUSE samples=%0d data_errors=%0d done_errors=%0d",samples,data_errors,done_errors);
 // Restart decryption at every offset, rather than the published fixed offset 5.
 phase=2; samples=0; data_errors=0; done_errors=0;
 for(n=1;n<11;n=n+1) begin
  @(negedge clk); key={$random,$random,$random,$random}; kld=1;
  sample; kld=0; repeat(14) sample;
  text_in={$random,$random,$random,$random}; ld=1;
  sample; ld=0; repeat(n) sample;
  text_in={$random,$random,$random,$random}; ld=1;
  sample; ld=0; repeat(18) sample;
 end
 $display("RESTART samples=%0d data_errors=%0d done_errors=%0d",samples,data_errors,done_errors);
 // Pulse entirely between rising clock edges: reference must not accept it.
 phase=3; samples=0; data_errors=0; done_errors=0;
 @(negedge clk); #1 ld=1; #1 ld=0;
 repeat(20) sample;
 $display("OFFEDGE samples=%0d data_errors=%0d done_errors=%0d",samples,data_errors,done_errors);
'''
    else:
        common += '''for(n=0;n<100;n=n+1) begin
  @(negedge clk); key={$random,$random,$random,$random};
  text_in={$random,$random,$random,$random}; ld=1;
  sample; ld=0; repeat(18) sample;
 end
 $display("NORMAL samples=%0d data_errors=%0d done_errors=%0d",samples,data_errors,done_errors);
 phase=1; samples=0; data_errors=0; done_errors=0;
 @(negedge clk); ld=1;
 sample; ld=0;
 repeat(10) sample;
 rst=0; sample;
 $display("RESET_AT_COMPLETION ref_done=%b dut_done=%b",dr,dd);
'''
    common += '$finish; end\nendmodule\n'
    run(name, common, sources)


def aes_inv_original():
    gd=GOLD/'aes_inv_cipher_top'
    sources=list(merged('aes_inv_cipher_system_hard').glob('*.v'))
    sources += [gd/'aes_inv_cipher_top_ref.sv',gd/'aes_inv_cipher_top_stimulus_gen.sv']+list(gd.glob('*.v'))
    run('aes_inv_original',(gd/'aes_inv_cipher_top_testbench.sv').read_text(),sources)


def sdc():
    gd = GOLD/'sdc_controller'
    sources = list(merged('sdc_controller_system').glob('*.v')) + [gd/'sdc_controller_ref.sv'] + list(gd.glob('*.v'))
    ports = '''.wb_clk_i(clk),.wb_rst_i(rst),.wb_sel_i(4'hf),.wb_dat_i(data),
 .wb_adr_i(addr),.wb_we_i(we),.wb_cyc_i(cyc),.wb_stb_i(cyc),
 .m_wb_dat_i(32'h0),.m_wb_ack_i(1'b0),.card_detect(1'b1),
 .sd_cmd_dat_i(1'b1),.sd_dat_dat_i(4'hf)'''
    tb = '''`timescale 1ns/1ps
`include "ref_sd_defines.v"
module tb;
reg clk=0; always #5 clk=~clk;
reg rst=1,we=0,cyc=0; reg [31:0] data=0; reg [7:0] addr=0;
wire [31:0] rd,dd; wire ra,da;
'''
    tb += f'ref_sdc_controller ref_dut({ports},.wb_dat_o(rd),.wb_ack_o(ra));\n'
    tb += f'sdc_controller dut({ports},.sd_clk_i_pad(clk),.wb_dat_o(dd),.wb_ack_o(da));\n'
    tb += '''task readreg(input [7:0] a);
begin
 @(negedge clk); cyc=1;we=0;addr=a;
 repeat(2) @(negedge clk);
 $display("READ addr=%h ref=%h dut=%h ref_ack=%b dut_ack=%b",a,rd,dd,ra,da);
 cyc=0; repeat(2) @(negedge clk);
end endtask
task writereg(input [7:0] a,input [31:0] d);
begin
 @(negedge clk);cyc=1;we=1;addr=a;data=d;
 repeat(2) @(negedge clk);
 cyc=0;we=0;repeat(2) @(negedge clk);
end endtask
initial begin
 repeat(4) @(negedge clk);rst=0;
 repeat(6) @(negedge clk);
 readreg(8'h1c); readreg(8'h20); readreg(8'h24);readreg(8'h48);readreg(8'h50);
 writereg(8'h38,32'h12345678);readreg(8'h38);
 // Change descriptor data during its write handshake, as with 16-bit golden BD memory.
 @(negedge clk);cyc=1;we=1;addr=8'h60;data=32'h89abcdef;
 repeat(5) begin
  @(negedge clk);$display("BD_ACK ref=%b dut=%b",ra,da);
 end
 cyc=0;we=0;
 repeat(10) @(negedge clk); $finish;
end endmodule
'''
    run('sdc', tb, sources, [gd])


def e203():
    gd = GOLD/'e203_cpu_top'
    pp = BUILD/'e203_preprocessed.v'
    subprocess.run([IV,'-g2012','-E','-I',str(gd),'-o',str(pp),str(gd/'e203_exu_alu.v')], check=True)
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', pp.read_text(), flags=re.S)
    header = text.split('module ref_e203_exu_alu(',1)[1].split(');',1)[0]
    ports = re.findall(r'\b(input|output)\s*(\[[^\]]+\])?\s*(\w+)\s*(?:,|$)',header)
    assert len(ports)>60,len(ports)
    tb = '`timescale 1ns/1ps\n`include "e203_defines.v"\nmodule tb;\n'
    for kind,width,name in ports:
        tb += f'{"reg" if kind=="input" else "wire"} {width} {name}{"" if kind=="input" else "_r"};\n'
        if kind=='output': tb += f'wire {width} {name}_d;\n'
    for module,tag in [('ref_e203_exu_alu','r'),('e203_exu_alu_system','d')]:
        conn = ','.join(f'.{name}({name if kind=="input" else name+"_"+tag})' for kind,width,name in ports)
        tb += f'{module} {tag}({conn});\n'
    tb += 'always #5 clk=~clk;\ninitial begin\n'
    tb += '\n'.join(name+"=0;" for kind,width,name in ports if kind=='input')
    tb += '''
 cmt_o_ready=1;wbck_o_ready=1;agu_icb_cmd_ready=1;oitf_empty=1;
 repeat(3) @(negedge clk);rst_n=1;
 i_valid=1;i_rdwen=1;i_rdidx=1;i_pc_vld=1;i_info=0;
 i_info[`E203_DECINFO_GRP]=`E203_DECINFO_GRP_ALU;
 i_info[`E203_DECINFO_RV32]=1;i_info[`E203_DECINFO_ALU_ADD]=1;
 i_rs1=7;i_rs2=5;i_instr=32'h002080b3;
 @(negedge clk);$display("ADD ref=%h dut=%h ref_valid=%b dut_valid=%b",wbck_o_wdat_r,wbck_o_wdat_d,wbck_o_valid_r,wbck_o_valid_d);
 // Compare branch metadata while no valid instruction is offered.
 i_valid=0;i_info=0;i_info[`E203_DECINFO_GRP]=`E203_DECINFO_GRP_ALU;
 i_info[`E203_DECINFO_ALU_ADD]=1;
 i_info[`E203_DECINFO_ALU_OR]=1;
 @(negedge clk);$display("IDLE_BRANCH ref_prdt=%b dut_prdt=%b ref_rslv=%b dut_rslv=%b",cmt_o_bjp_prdt_r,cmt_o_bjp_prdt_d,cmt_o_bjp_rslv_r,cmt_o_bjp_rslv_d);
'''
    # Valid branch prediction should be preserved independently of i_valid in golden.
    tb += '''i_info=0;i_info[`E203_DECINFO_GRP]=`E203_DECINFO_GRP_BJP;
 i_info[`E203_DECINFO_BJP_BXX]=1;i_info[`E203_DECINFO_BJP_BEQ]=1;
 i_info[`E203_DECINFO_BJP_BPRDT]=1;i_rs1=7;i_rs2=7;
 @(negedge clk);$display("BJP_INVALID ref_prdt=%b dut_prdt=%b ref_rslv=%b dut_rslv=%b",cmt_o_bjp_prdt_r,cmt_o_bjp_prdt_d,cmt_o_bjp_rslv_r,cmt_o_bjp_rslv_d);
 i_valid=1;@(negedge clk);$display("BJP_VALID ref_prdt=%b dut_prdt=%b ref_rslv=%b dut_rslv=%b",cmt_o_bjp_prdt_r,cmt_o_bjp_prdt_d,cmt_o_bjp_rslv_r,cmt_o_bjp_rslv_d);
 i_rdwen=0;i_info=0;i_info[`E203_DECINFO_GRP]=`E203_DECINFO_GRP_BJP;
 i_info[`E203_DECINFO_BJP_FENCEI]=1;
 @(negedge clk);$display("FENCEI ref_cmt=%b dut_cmt=%b ref_bjp=%b dut_bjp=%b ref_fencei=%b dut_fencei=%b",cmt_o_valid_r,cmt_o_valid_d,cmt_o_bjp_r,cmt_o_bjp_d,cmt_o_fencei_r,cmt_o_fencei_d);
'''
    inputs = {name for kind,width,name in ports if kind=='input'}
    if 'nice_req_ready' in inputs:
        tb += '''i_info=0;i_info[`E203_DECINFO_GRP]=`E203_DECINFO_GRP_NICE;
 nice_xs_off=0;nice_req_ready=1;nice_longp_wbck_ready=0;nice_rsp_multicyc_valid=0;
 @(negedge clk);i_valid=0;nice_rsp_multicyc_valid=1;
 #1;$display("NICE_BACKPRESSURE ref_ready=%b dut_ready=%b ref_wbvalid=%b dut_wbvalid=%b",nice_rsp_multicyc_ready_r,nice_rsp_multicyc_ready_d,nice_longp_wbck_valid_r,nice_longp_wbck_valid_d);
 @(negedge clk);nice_rsp_multicyc_valid=0;
 #1;$display("NICE_RESPONSE_DROPPED ref_wbvalid=%b dut_wbvalid=%b",nice_longp_wbck_valid_r,nice_longp_wbck_valid_d);
'''
    tb += '$finish;end\nendmodule\n'
    sources = [gd/'e203_defines.v'] + list(merged('e203_exu_alu_system').glob('e203_exu*.v'))
    sources += list(gd.glob('e203_exu_alu*.v')) + [gd/'e203_exu_nice.v',gd/'sirv_gnrl_dffs.v',gd/'sirv_gnrl_bufs.v',gd/'sirv_gnrl_xchecker.v']
    run('e203',tb,sources,[gd])


def sdc_serial():
    tb = '''`timescale 1ns/1ps
module tb;
reg wb_clk=0;always #5 wb_clk=~wb_clk;
reg sd_clk=0;always #7 sd_clk=~sd_clk;
reg rst=1,dat_rst=1;reg [1:0] start=0;
wire acquire; integer acquisitions=0;
always @(posedge sd_clk) if(acquire) acquisitions=acquisitions+1;
sdc_serial_engine dut(.wb_clk_i(wb_clk),.sd_clk_i(sd_clk),.wb_rst_i(rst),
 .sd_rst_i(rst),.cmd_reset_i(rst),.dat_reset_i(dat_rst),.forced_idle_i(1'b0),
 .cmd_content_i(40'b0),.cmd_settings_i(15'b0),.cmd_start_i(1'b0),.cmd_status_ack_i(1'b0),
 .data_start_i(start),.data_result_ack_i(1'b1),.tx_word_i(32'h12345678),
 .tx_word_valid_i(1'b1),.tx_word_acquire_o(acquire),.rx_capacity_i(1'b1),
 .cmd_dat_i(1'b1),.sd_dat_i(4'hf));
initial begin
 repeat(4) @(negedge wb_clk);rst=0;dat_rst=0;
 repeat(4) @(negedge wb_clk);start=2'b10;
 @(negedge wb_clk);start=0;
 repeat(20) @(negedge sd_clk);
 $display("POST_HW_RESET state=%0d read_wait_expected=4 req=%b ack=%b",dut.dat_state_sd,dut.dat_req_sync_sd,dut.dat_req_ack_sd);
 // A data-only reset releases this deadlock; exercise a normal write after it.
 dat_rst=1;repeat(3) @(negedge sd_clk);dat_rst=0;
 repeat(6) @(negedge wb_clk);start=2'b01;
 @(negedge wb_clk);start=0;
 repeat(100) @(negedge sd_clk);
 $display("TX_PROGRESS state=%0d nibbles=%0d acquisitions=%0d",dut.dat_state_sd,dut.dat_transfer_count_sd,acquisitions);
 $finish;
end endmodule
'''
    run('sdc_serial',tb,[merged('sdc_controller_system')/'sdc_serial_engine.v'])


if __name__ == '__main__':
    aes(); aes(True); sdc(); e203(); sdc_serial()
    (OUT/'results.json').write_text(json.dumps(results,indent=2,ensure_ascii=False))
