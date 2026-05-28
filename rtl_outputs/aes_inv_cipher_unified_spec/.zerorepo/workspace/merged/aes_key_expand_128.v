module aes_key_expand_128 (
    input clk,
    input kld,
    input [127:0] key,
    output [31:0] wo_0,
    output [31:0] wo_1,
    output [31:0] wo_2,
    output [31:0] wo_3
);

// Registers and wires
reg [31:0] rk0, rk1, rk2, rk3;
wire [31:0] rot_word;
wire [7:0] sbox_byte0, sbox_byte1, sbox_byte2, sbox_byte3;
wire [31:0] rcon_out;
wire [31:0] sub_word;
wire [31:0] T_word;
wire [31:0] rk0_next, rk1_next, rk2_next, rk3_next;

// Instantiate round constant generator
aes_rcon rcon_inst (
    .clk(clk),
    .kld(kld),
    .out(rcon_out)
);

// Instantiate four S-boxes for SubWord
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

// Combinational logic: RotWord, SubWord, Rcon XOR
assign rot_word = {rk3[23:0], rk3[31:24]};   // one-byte left rotate
assign sub_word = {sbox_byte3, sbox_byte2, sbox_byte1, sbox_byte0};  // correct byte order
assign T_word  = sub_word ^ rcon_out;

// Next key word computations
assign rk0_next = rk0 ^ T_word;
assign rk1_next = rk1 ^ rk0_next;
assign rk2_next = rk2 ^ rk1_next;
assign rk3_next = rk3 ^ rk2_next;

// Register update
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

// Output assignments
assign wo_0 = rk0;
assign wo_1 = rk1;
assign wo_2 = rk2;
assign wo_3 = rk3;

endmodule
