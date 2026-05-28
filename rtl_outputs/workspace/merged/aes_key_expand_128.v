module aes_key_expand_128 (
    input  clk,
    input  kld,
    input  [127:0] key,
    output [31:0] wo_0,
    output [31:0] wo_1,
    output [31:0] wo_2,
    output [31:0] wo_3
);

// Key word registers
reg [31:0] w0, w1, w2, w3;

// Combinational expansion wires
wire [31:0] rot_word;
wire [31:0] sub_word;
wire [31:0] T_word;
wire [31:0] next_w0, next_w1, next_w2, next_w3;

// Round constant (32‑bit, only high byte valid)
wire [31:0] rcon_out;
wire [7:0]  rcon_byte;

// S‑box outputs
wire [7:0] sb0_out, sb1_out, sb2_out, sb3_out;

// Instantiations
aes_rcon rcon_inst (
    .clk (clk),
    .kld (kld),
    .out (rcon_out)
);

aes_sbox sb0 (.a(rot_word[31:24]), .b(sb0_out));
aes_sbox sb1 (.a(rot_word[23:16]), .b(sb1_out));
aes_sbox sb2 (.a(rot_word[15:8]),  .b(sb2_out));
aes_sbox sb3 (.a(rot_word[7:0]),   .b(sb3_out));

// Round constant byte extraction
assign rcon_byte = rcon_out[31:24];

// Key expansion combinatorial network
assign rot_word = {w3[23:0], w3[31:24]};
assign sub_word = {sb0_out, sb1_out, sb2_out, sb3_out};
assign T_word   = {sub_word[31:24] ^ rcon_byte, sub_word[23:0]};
assign next_w0  = w0 ^ T_word;
assign next_w1  = w1 ^ next_w0;
assign next_w2  = w2 ^ next_w1;
assign next_w3  = w3 ^ next_w2;

// Sequential key load / update
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

// Output assignments
assign wo_0 = w0;
assign wo_1 = w1;
assign wo_2 = w2;
assign wo_3 = w3;

endmodule
