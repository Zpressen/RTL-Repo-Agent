module aes_key_expand_128 (
    clk,
    kld,
    key,
    wo_0,
    wo_1,
    wo_2,
    wo_3
);

input clk;
input kld;
input [127:0] key;
output [31:0] wo_0;
output [31:0] wo_1;
output [31:0] wo_2;
output [31:0] wo_3;

// Round key registers
reg [31:0] r0, r1, r2, r3;

// Internal wires
wire [31:0] rcon_out;
wire [31:0] rot_word;
wire [31:0] sub_word;
wire [31:0] T;
wire [31:0] nxt_r0;
wire [31:0] nxt_r1;
wire [31:0] nxt_r2;
wire [31:0] nxt_r3;

// Instantiate aes_rcon for round constant generation
aes_rcon u_aes_rcon (
    .clk (clk),
    .kld (kld),
    .out (rcon_out)
);

// RotWord: cyclic left byte shift of r3
assign rot_word = {r3[23:0], r3[31:24]};

// SubWord: apply S-box to each byte of the rotated word
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

// Compute T = SubWord(RotWord(r3)) XOR Rcon
assign T = sub_word ^ rcon_out;

// Next round key words (standard AES-128 key expansion)
assign nxt_r0 = r0 ^ T;
assign nxt_r1 = r1 ^ nxt_r0;
assign nxt_r2 = r2 ^ nxt_r1;
assign nxt_r3 = r3 ^ nxt_r2;

// Sequential register update
always @(posedge clk) begin
    if (kld) begin
        // Load initial key
        r0 <= key[127:96];
        r1 <= key[95:64];
        r2 <= key[63:32];
        r3 <= key[31:0];
    end else begin
        // Generate next round key
        r0 <= nxt_r0;
        r1 <= nxt_r1;
        r2 <= nxt_r2;
        r3 <= nxt_r3;
    end
end

// Output combinational assignments
assign wo_0 = r0;
assign wo_1 = r1;
assign wo_2 = r2;
assign wo_3 = r3;

endmodule
