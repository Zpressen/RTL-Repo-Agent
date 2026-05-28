// STAGE5_SUBTASK_BEGIN B1_decl_core_objects: Declare 4-bit register rcnt, 32-bit register out_reg, and a constant array RC_TABLE[0:9] holding 8-bit round constants 0
reg [3:0] rcnt;
reg [31:0] out_reg;
localparam [79:0] RC_TABLE = {8'h01, 8'h02, 8'h04, 8'h08, 8'h10, 8'h20, 8'h40, 8'h80, 8'h1B, 8'h36};
// STAGE5_SUBTASK_END B1_decl_core_objects

// STAGE5_SUBTASK_BEGIN B2_comb_round_constant_lookup: Combinational logic to compute next_rc_byte: if kld=1, output 0x01; if rcnt>9, output 0x00; else output RC_TABLE[rcnt].
// <block: comb_round_constant_lookup>
assign next_out = kld ? 32'h01000000 :
                  (rcnt > 4'd9) ? 32'h00000000 :
                  {RC_TABLE[79 - rcnt*8 -: 8], 24'h000000};
// STAGE5_SUBTASK_END B2_comb_round_constant_lookup

// STAGE5_SUBTASK_BEGIN B3_seq_register_update: Sequential always block on posedge clk: if kld, rcnt <= 0; else rcnt <= rcnt+1; out_reg <= {next_rc_byte, 24'h000000}.
always @(posedge clk) begin
    if (kld) begin
        rcnt <= 4'd0;
    end else begin
        rcnt <= rcnt + 4'd1;
    end
    out_reg <= {next_rc_byte, 24'h000000};
end
// STAGE5_SUBTASK_END B3_seq_register_update
