// STAGE5_SUBTASK_BEGIN B1_decl_registers: Declare a 4-bit register rcnt, a 32-bit register out, and a 32-bit wire next_rcon that connects the combinational lookup
reg [3:0] rcnt;
reg [31:0] out;
wire [31:0] next_rcon;
// STAGE5_SUBTASK_END B1_decl_registers

// STAGE5_SUBTASK_BEGIN B2_comb_rcon_lookup: Combinational lookup from rcnt to 32-bit next_rcon using a precomputed table. For rcnt 0-9 output the round constant wit
assign next_rcon = (rcnt == 4'd0) ? 32'h01000000 :
                   (rcnt == 4'd1) ? 32'h02000000 :
                   (rcnt == 4'd2) ? 32'h04000000 :
                   (rcnt == 4'd3) ? 32'h08000000 :
                   (rcnt == 4'd4) ? 32'h10000000 :
                   (rcnt == 4'd5) ? 32'h20000000 :
                   (rcnt == 4'd6) ? 32'h40000000 :
                   (rcnt == 4'd7) ? 32'h80000000 :
                   (rcnt == 4'd8) ? 32'h1B000000 :
                   (rcnt == 4'd9) ? 32'h36000000 :
                                    32'h00000000;
// STAGE5_SUBTASK_END B2_comb_rcon_lookup

// STAGE5_SUBTASK_BEGIN B3_seq_update: Sequential update on posedge clk: if kld==1 set rcnt=0 and out=next_rcon (which corresponds to rcnt=0, i.e., 0x01000000)
always @(posedge clk) begin
    if (kld) begin
        rcnt <= 4'd0;
        out <= 32'h01000000;
    end else begin
        rcnt <= rcnt + 4'd1;
        out <= next_rcon;
    end
end
// STAGE5_SUBTASK_END B3_seq_update
