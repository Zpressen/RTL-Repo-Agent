// STAGE5_SUBTASK_BEGIN B1_decl_regs_and_wires: Declare the 4-bit rcnt register, 32-bit out register, and optional combinational wires next_rcnt (4-bit) and next_out (3
reg [3:0] rcnt;
reg [31:0] out;
wire [3:0] next_rcnt;
wire [31:0] next_out;
// STAGE5_SUBTASK_END B1_decl_regs_and_wires

// STAGE5_SUBTASK_BEGIN B2_comb_next_gen: Combinational logic to compute next_rcnt (counter increment/reset) and next_out (round constant or zero) based on kld an
function [7:0] rcon_byte;
        input [3:0] idx;
        begin
            case (idx)
                4'd0: rcon_byte = 8'h01;
                4'd1: rcon_byte = 8'h02;
                4'd2: rcon_byte = 8'h04;
                4'd3: rcon_byte = 8'h08;
                4'd4: rcon_byte = 8'h10;
                4'd5: rcon_byte = 8'h20;
                4'd6: rcon_byte = 8'h40;
                4'd7: rcon_byte = 8'h80;
                4'd8: rcon_byte = 8'h1b;
                4'd9: rcon_byte = 8'h36;
                default: rcon_byte = 8'h00;
            endcase
        end
    endfunction

    assign next_rcnt = kld ? 4'd0 : rcnt + 1'd1;
    assign next_out = { (kld ? 8'h01 : ((rcnt >= 4'd9) ? 8'h00 : rcon_byte(rcnt + 1'd1))) , 24'h000000 };
// STAGE5_SUBTASK_END B2_comb_next_gen

// STAGE5_SUBTASK_BEGIN B3_seq_update: Sequential always block that on posedge clk assigns next_rcnt to rcnt and next_out to out, implementing synchronous regi
always @(posedge clk) begin
    rcnt <= next_rcnt;
    out  <= next_out;
end
// STAGE5_SUBTASK_END B3_seq_update

// STAGE5_SUBTASK_BEGIN B1_decl_registers: Declare a 4-bit register rcnt, a 32-bit register out, and a 32-bit wire next_rcon that connects the combinational lookup
wire [31:0] next_rcon;
// STAGE5_SUBTASK_END B1_decl_registers

// STAGE5_SUBTASK_BEGIN B2_comb_rcon_lookup: Combinational lookup from rcnt to 32-bit next_rcon using a precomputed table. For rcnt 0-9 output the round constant wit
assign next_rcon = (rcnt == 4'd0) ? 32'h01000000 : (rcnt == 4'd1) ? 32'h02000000 : (rcnt == 4'd2) ? 32'h04000000 : (rcnt == 4'd3) ? 32'h08000000 : (rcnt == 4'd4) ? 32'h10000000 : (rcnt == 4'd5) ? 32'h20000000 : (rcnt == 4'd6) ? 32'h40000000 : (rcnt == 4'd7) ? 32'h80000000 : (rcnt == 4'd8) ? 32'h1B000000 : (rcnt == 4'd9) ? 32'h36000000 : 32'h00000000;
// STAGE5_SUBTASK_END B2_comb_rcon_lookup
