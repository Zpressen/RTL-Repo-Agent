"""Construct two minimal controls from golden RTL, without changing golden."""
from pathlib import Path
import re
import shutil

ROOT=Path('/home/mokita/RealBench/e203_hbirdv2/e203_exu_alu')
DEST=Path('/tmp/e203_oracle_controls')
OUT=Path(__file__).resolve().parent
for name in ['idle_wb_zero','spurious_nice_on_add']:
    dst=DEST/name
    dst.mkdir(parents=True,exist_ok=True)
    for p in ROOT.glob('*.v'):
        if p.name not in ['config.v','e203_defines.v']: shutil.copy2(p,dst/p.name)
    for f in ['e203_exu_nice.v','sirv_gnrl_bufs.v','sirv_gnrl_dffs.v','sirv_gnrl_xchecker.v']:
        shutil.copy2(ROOT/'verification'/f,dst/f)
    p=dst/'e203_exu_alu.v'
    s=p.read_text()
    if name=='idle_wb_zero':
        anchor='  assign wbck_o_wdat = '
        assert s.count(anchor)==1
        s=s.replace(anchor,'  wire [31:0] audit_raw_wdat;\n  assign wbck_o_wdat = wbck_o_valid ? audit_raw_wdat : 32\'b0;\n  assign audit_raw_wdat = ')
        change="Only zero writeback payload when wbck_o_valid=0; preserve all handshakes and every valid payload."
    else:
        anchor='.nice_req_valid     (nice_req_valid)'
        assert s.count(anchor)==1
        s=s.replace(anchor,'.nice_req_valid     (audit_raw_nice_valid)')
        at=s.rfind('endmodule')
        new=r'''
  wire audit_raw_nice_valid;
  // Intentional defect: an ordinary ADD also issues an accelerator command.
  assign nice_req_valid = audit_raw_nice_valid |
    (i_valid && !(i_ilegl || i_buserr || i_misalgn) &&
     (i_info[`E203_DECINFO_GRP] == `E203_DECINFO_GRP_ALU) &&
     i_info[`E203_DECINFO_ALU_ADD]);
'''
        s=s[:at]+new+s[at:]
        change=new
    p.write_text(s)
    (OUT/(name+'_mutation.txt')).write_text(change+'\n')
    print(dst)
