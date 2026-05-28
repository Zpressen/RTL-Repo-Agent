// STAGE5_SUBTASK_BEGIN B1_decl_round_key_registers: Declare four 32-bit registers (r0, r1, r2, r3) to hold the current 128-bit round key. These registers are the central st
reg [31:0] r0, r1, r2, r3;
// STAGE5_SUBTASK_END B1_decl_round_key_registers

// STAGE5_SUBTASK_BEGIN B2_inst_aes_rcon: Instantiate a single aes_rcon module to generate 32-bit round constants. Connect clk and kld directly from module inputs
wire [31:0] rcon_out;
aes_rcon u_aes_rcon (
    .clk (clk),
    .kld (kld),
    .out (rcon_out)
);
// STAGE5_SUBTASK_END B2_inst_aes_rcon

// STAGE5_SUBTASK_BEGIN B3_inst_aes_sbox_x4: Instantiate four aes_sbox modules to perform SubWord on the rotated bytes. Connect each instance's input port a to a dis
// Declare the rotated word wire and the SubWord result wire
wire [31:0] rot_word;
wire [31:0] sub_word;

// Four aes_sbox instances for SubWord
aes_sbox u_sbox0 (
    .a (rot_word[31:24]),
    .b (sub_word[31:24])
);
aes_sbox u_sbox1 (
    .a (rot_word[23:16]),
    .b (sub_word[23:16])
);
aes_sbox u_sbox2 (
    .a (rot_word[15:8]),
    .b (sub_word[15:8])
);
aes_sbox u_sbox3 (
    .a (rot_word[7:0]),
    .b (sub_word[7:0])
);
// STAGE5_SUBTASK_END B3_inst_aes_sbox_x4

// STAGE5_SUBTASK_BEGIN B4_comb_new_round_words: Combinational logic to compute next-round words. Apply RotWord to r3 (cyclic left byte shift), route each rotated byte t
// RotWord: cyclic left shift of bytes in r3
assign rot_word = {r3[23:0], r3[31:24]};

// Compute T = SubWord XOR Rcon
wire [31:0] T;
assign T = sub_word ^ rcon_out;

// Next round key word calculation according to cumulative XOR pattern
wire [31:0] nxt_r0;
wire [31:0] nxt_r1;
wire [31:0] nxt_r2;
wire [31:0] nxt_r3;

assign nxt_r0 = r0 ^ T;
assign nxt_r1 = r1 ^ nxt_r0 ^ T;
assign nxt_r2 = r2 ^ nxt_r0 ^ nxt_r1 ^ T;
assign nxt_r3 = r3 ^ nxt_r0 ^ nxt_r1 ^ nxt_r2 ^ T;
// STAGE5_SUBTASK_END B4_comb_new_round_words

// STAGE5_SUBTASK_BEGIN B5_seq_register_update: On rising clock edge, if kld is high, load r0 from key[127:96], r1 from key[95:64], r2 from key[63:32], r3 from key[31:0
always @(posedge clk) begin
    if (kld) begin
        r0 <= key[127:96];
        r1 <= key[95:64];
        r2 <= key[63:32];
        r3 <= key[31:0];
    end else begin
        r0 <= nxt_r0;
        r1 <= nxt_r1;
        r2 <= nxt_r2;
        r3 <= nxt_r3;
    end
end
// STAGE5_SUBTASK_END B5_seq_register_update

// STAGE5_SUBTASK_BEGIN B6_comb_output_assignment: Continuous combinational assignments: assign wo_0 = r0, wo_1 = r1, wo_2 = r2, wo_3 = r3. Outputs follow the register val
assign wo_0 = r0;
assign wo_1 = r1;
assign wo_2 = r2;
assign wo_3 = r3;
// STAGE5_SUBTASK_END B6_comb_output_assignment
