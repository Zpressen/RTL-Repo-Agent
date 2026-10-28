`timescale 1ns/1ps
`include "ref_sd_defines.v"
module tb;
reg clk=0; always #5 clk=~clk;
reg rst=1,we=0,cyc=0; reg [31:0] data=0; reg [7:0] addr=0;
wire [31:0] rd,dd; wire ra,da;
ref_sdc_controller ref_dut(.wb_clk_i(clk),.wb_rst_i(rst),.wb_sel_i(4'hf),.wb_dat_i(data),
 .wb_adr_i(addr),.wb_we_i(we),.wb_cyc_i(cyc),.wb_stb_i(cyc),
 .m_wb_dat_i(32'h0),.m_wb_ack_i(1'b0),.card_detect(1'b1),
 .sd_cmd_dat_i(1'b1),.sd_dat_dat_i(4'hf),.wb_dat_o(rd),.wb_ack_o(ra));
sdc_controller dut(.wb_clk_i(clk),.wb_rst_i(rst),.wb_sel_i(4'hf),.wb_dat_i(data),
 .wb_adr_i(addr),.wb_we_i(we),.wb_cyc_i(cyc),.wb_stb_i(cyc),
 .m_wb_dat_i(32'h0),.m_wb_ack_i(1'b0),.card_detect(1'b1),
 .sd_cmd_dat_i(1'b1),.sd_dat_dat_i(4'hf),.sd_clk_i_pad(clk),.wb_dat_o(dd),.wb_ack_o(da));
task readreg(input [7:0] a);
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
