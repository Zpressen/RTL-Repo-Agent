// STAGE5_SUBTASK_BEGIN B1_decl_key_storage_and_signals: Declare four 32-bit registers w0, w1, w2, w3 and all internal combinational wires (rot_word, sub_word, T_word, next_w0..
// <block: decl_key_storage_and_signals>
reg  [31:0] w0, w1, w2, w3;
wire [31:0] rot_word;
wire [31:0] sub_word;
wire [31:0] T_word;
wire [31:0] next_w0;
wire [31:0] next_w1;
wire [31:0] next_w2;
wire [31:0] next_w3;
wire [31:0] rcon_out;
wire [7:0]  sb0_out;
wire [7:0]  sb1_out;
wire [7:0]  sb2_out;
wire [7:0]  sb3_out;
// <end: decl_key_storage_and_signals>
// STAGE5_SUBTASK_END B1_decl_key_storage_and_signals

// STAGE5_SUBTASK_BEGIN B2_inst_submodules: Instantiate one aes_rcon (clk, kld, out→rcon_out) and four aes_sbox modules (inputs from rotated w3 bytes, outputs sb0_o
// <block: inst_submodules>
aes_rcon rcon_inst (
  .clk(clk),
  .kld(kld),
  .out(rcon_out)
);

aes_sbox sbox0 (
  .a(rot_word[7:0]),
  .b(sb0_out)
);

aes_sbox sbox1 (
  .a(rot_word[15:8]),
  .b(sb1_out)
);

aes_sbox sbox2 (
  .a(rot_word[23:16]),
  .b(sb2_out)
);

aes_sbox sbox3 (
  .a(rot_word[31:24]),
  .b(sb3_out)
);
// <end: inst_submodules>
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
