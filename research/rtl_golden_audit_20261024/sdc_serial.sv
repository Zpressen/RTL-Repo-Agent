`timescale 1ns/1ps
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
