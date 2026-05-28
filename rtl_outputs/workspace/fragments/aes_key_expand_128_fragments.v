// STAGE5_SUBTASK_BEGIN B1_decl_key_storage_and_signals: Declare four 32-bit registers w0, w1, w2, w3 and all internal combinational wires (rot_word, sub_word, T_word, next_w0..
reg [31:0] w0, w1, w2, w3;
wire [31:0] rot_word;
wire [31:0] sub_word;
wire [31:0] T_word;
wire [31:0] next_w0;
wire [31:0] next_w1;
wire [31:0] next_w2;
wire [31:0] next_w3;
wire [7:0] rcon_out;
wire [7:0] sb0_out;
wire [7:0] sb1_out;
wire [7:0] sb2_out;
wire [7:0] sb3_out;
// STAGE5_SUBTASK_END B1_decl_key_storage_and_signals

// STAGE5_SUBTASK_BEGIN B2_inst_submodules: Instantiate one aes_rcon (clk, kld, out→rcon_out) and four aes_sbox modules (inputs from rotated w3 bytes, outputs sb0_o
aes_rcon rcon_inst (
    .clk (clk),
    .kld (kld),
    .out (rcon_out)
);

aes_sbox sb0 (
    .a (rot_word[31:24]),
    .b (sb0_out)
);
aes_sbox sb1 (
    .a (rot_word[23:16]),
    .b (sb1_out)
);
aes_sbox sb2 (
    .a (rot_word[15:8]),
    .b (sb2_out)
);
aes_sbox sb3 (
    .a (rot_word[7:0]),
    .b (sb3_out)
);
// STAGE5_SUBTASK_END B2_inst_submodules

// STAGE5_SUBTASK_BEGIN B3_seq_load_update: Implement the synchronous register load/update process: on posedge clk, if kld=1 load w0..w3 from key[127:0] with specif
always @(posedge clk) begin
    if (kld) begin
        w0 <= key[127:96];
        w1 <= key[95:64];
        w2 <= key[63:32];
        w3 <= key[31:0];
    end else begin
        w0 <= next_w0;
        w1 <= next_w1;
        w2 <= next_w2;
        w3 <= next_w3;
    end
end
// STAGE5_SUBTASK_END B3_seq_load_update

// STAGE5_SUBTASK_BEGIN B4_comb_expansion_network: Compute RotWord, SubWord (using sbox outputs), T_word (SubWord XOR rcon_out), and next round key words next_w0..next_w3 
assign rot_word = {w3[23:0], w3[31:24]};
assign sub_word = {sb0_out, sb1_out, sb2_out, sb3_out};
assign T_word   = {sub_word[31:24] ^ rcon_out, sub_word[23:0]};
assign next_w0  = w0 ^ T_word;
assign next_w1  = w1 ^ next_w0;
assign next_w2  = w2 ^ next_w1;
assign next_w3  = w3 ^ next_w2;
// STAGE5_SUBTASK_END B4_comb_expansion_network

// STAGE5_SUBTASK_BEGIN B5_output_assignment: Drive output ports wo_0, wo_1, wo_2, wo_3 with the current values of the key word registers w0, w1, w2, w3 continuously.
assign wo_0 = w0;
assign wo_1 = w1;
assign wo_2 = w2;
assign wo_3 = w3;
// STAGE5_SUBTASK_END B5_output_assignment
