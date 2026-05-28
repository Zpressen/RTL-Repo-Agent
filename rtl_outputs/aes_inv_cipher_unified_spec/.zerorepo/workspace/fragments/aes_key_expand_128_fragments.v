// STAGE5_SUBTASK_BEGIN B1_decl_regs_wires: Declare the four 32-bit round key registers (rk0, rk1, rk2, rk3) and all intermediate wires: rot_word, sbox_byte0..3, rc
reg [31:0] rk0, rk1, rk2, rk3;
wire [31:0] rot_word;
wire [7:0] sbox_byte0, sbox_byte1, sbox_byte2, sbox_byte3;
wire [7:0] rcon_out;
wire [31:0] T_word;
wire [31:0] rk0_next, rk1_next, rk2_next, rk3_next;
// STAGE5_SUBTASK_END B1_decl_regs_wires

// STAGE5_SUBTASK_BEGIN B2_inst_submodules: Instantiate one aes_rcon and four aes_sbox submodules, connecting their ports to the declared wires according to the int
aes_rcon rcon_inst (
    .clk(clk),
    .kld(kld),
    .out(rcon_out)
);

aes_sbox sbox_byte0_inst (
    .a(rot_word[7:0]),
    .b(sbox_byte0)
);

aes_sbox sbox_byte1_inst (
    .a(rot_word[15:8]),
    .b(sbox_byte1)
);

aes_sbox sbox_byte2_inst (
    .a(rot_word[23:16]),
    .b(sbox_byte2)
);

aes_sbox sbox_byte3_inst (
    .a(rot_word[31:24]),
    .b(sbox_byte3)
);
// STAGE5_SUBTASK_END B2_inst_submodules

// STAGE5_SUBTASK_BEGIN B3_comb_rotword_subword_rcon: Compute rot_word as a one-byte left-rotate of rk3, assemble sub_word from the four sbox_byte outputs, and XOR with rcon_
// Compute RotWord: one-byte left rotate of rk3
assign rot_word = {rk3[23:0], rk3[31:24]};

// Assemble SubWord from the four S-box byte outputs
wire [31:0] sub_word = {sbox_byte0, sbox_byte1, sbox_byte2, sbox_byte3};

// XOR with rcon_out to produce T_word (rcon XOR with the highest byte)
assign T_word = {sub_word[31:24] ^ rcon_out, sub_word[23:0]};
// STAGE5_SUBTASK_END B3_comb_rotword_subword_rcon

// STAGE5_SUBTASK_BEGIN B4_comb_key_next: Compute next round key words using the AES expansion recurrence: rk0_next = rk0 ^ T_word; rk1_next = rk1 ^ rk0_next; rk2
assign rk0_next = rk0 ^ T_word;
assign rk1_next = rk1 ^ rk0_next;
assign rk2_next = rk2 ^ rk1_next;
assign rk3_next = rk3 ^ rk2_next;
// STAGE5_SUBTASK_END B4_comb_key_next

// STAGE5_SUBTASK_BEGIN B5_seq_reg_update: On rising clock edge, load rk0..rk3 with the input key when kld=1 (per key loading in S007), or update with computed nex
always @(posedge clk) begin
    if (kld) begin
        rk0 <= key[127:96];
        rk1 <= key[95:64];
        rk2 <= key[63:32];
        rk3 <= key[31:0];
    end else begin
        rk0 <= rk0_next;
        rk1 <= rk1_next;
        rk2 <= rk2_next;
        rk3 <= rk3_next;
    end
end
// STAGE5_SUBTASK_END B5_seq_reg_update

// STAGE5_SUBTASK_BEGIN B6_output_assign: Assign the output ports wo_0, wo_1, wo_2, wo_3 directly from the current register values rk0, rk1, rk2, rk3 respectively
assign wo_0 = rk0;
assign wo_1 = rk1;
assign wo_2 = rk2;
assign wo_3 = rk3;
// STAGE5_SUBTASK_END B6_output_assign
