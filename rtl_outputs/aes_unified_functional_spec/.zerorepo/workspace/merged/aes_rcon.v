module aes_rcon (
    input clk,
    input kld,
    output reg [31:0] out
);

reg [3:0] rcnt;
wire [3:0] rcn_next;
wire [31:0] rcon_val;

// Next rcnt value: reset to 0 on key load, otherwise increment
assign rcn_next = kld ? 4'd0 : rcnt + 4'd1;

// Combinational lookup of round constant for the *next* rcnt
assign rcon_val = (rcn_next == 4'd0) ? 32'h01000000 :
                  (rcn_next == 4'd1) ? 32'h02000000 :
                  (rcn_next == 4'd2) ? 32'h04000000 :
                  (rcn_next == 4'd3) ? 32'h08000000 :
                  (rcn_next == 4'd4) ? 32'h10000000 :
                  (rcn_next == 4'd5) ? 32'h20000000 :
                  (rcn_next == 4'd6) ? 32'h40000000 :
                  (rcn_next == 4'd7) ? 32'h80000000 :
                  (rcn_next == 4'd8) ? 32'h1B000000 :
                  (rcn_next == 4'd9) ? 32'h36000000 :
                                       32'h00000000;

// Sequential update on clock edge
always @(posedge clk) begin
    rcnt <= rcn_next;
    out  <= rcon_val;
end

endmodule
