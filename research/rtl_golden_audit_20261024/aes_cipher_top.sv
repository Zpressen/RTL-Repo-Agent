`timescale 1ns/1ps
module tb;
reg clk=0; always #5 clk=~clk;
reg rst=0, ld=0, kld=0;
reg [127:0] key=0, text_in=0;
wire dr,dd; wire [127:0] tr,td;
integer n,j, samples=0, data_errors=0, done_errors=0, phase=0;
integer completion_errors=0, completions=0;
reg [127:0] expected_result;
ref_aes_cipher_top ref_dut(.clk(clk),.rst(rst),.ld(ld),.key(key),.text_in(text_in),.done(dr),.text_out(tr));
aes_cipher_top dut(.clk(clk),.rst(rst),.ld(ld),.key(key),.text_in(text_in),.done(dd),.text_out(td));
task sample;
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
for(n=0;n<100;n=n+1) begin
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
$finish; end
endmodule
