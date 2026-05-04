`timescale 1ns / 1ps

module aes_key_expand_128 (
    input  wire         clk,
    input  wire         kld,
    input  wire [127:0] key,
    output wire [31:0]  wo_0,
    output wire [31:0]  wo_1,
    output wire [31:0]  wo_2,
    output wire [31:0]  wo_3
);
    reg  [31:0] w0_reg;
    reg  [31:0] w1_reg;
    reg  [31:0] w2_reg;
    reg  [31:0] w3_reg;
    wire [31:0] rcon;

    wire [31:0] rot_word;
    wire [7:0]  sub_b0;
    wire [7:0]  sub_b1;
    wire [7:0]  sub_b2;
    wire [7:0]  sub_b3;
    wire [31:0] sub_word;

    wire [31:0] next_w0;
    wire [31:0] next_w1;
    wire [31:0] next_w2;
    wire [31:0] next_w3;

    aes_rcon u_rcon (
        .clk(clk),
        .kld(kld),
        .out(rcon)
    );

    assign rot_word = {w3_reg[23:0], w3_reg[31:24]};

    aes_sbox u_sbox0 (.a(rot_word[31:24]), .b(sub_b0));
    aes_sbox u_sbox1 (.a(rot_word[23:16]), .b(sub_b1));
    aes_sbox u_sbox2 (.a(rot_word[15:8]),  .b(sub_b2));
    aes_sbox u_sbox3 (.a(rot_word[7:0]),   .b(sub_b3));

    assign sub_word = {sub_b0, sub_b1, sub_b2, sub_b3};

    assign next_w0 = w0_reg ^ sub_word ^ rcon;
    assign next_w1 = w1_reg ^ next_w0;
    assign next_w2 = w2_reg ^ next_w1;
    assign next_w3 = w3_reg ^ next_w2;

    assign wo_0 = kld ? key[127:96] : next_w0;
    assign wo_1 = kld ? key[95:64]  : next_w1;
    assign wo_2 = kld ? key[63:32]  : next_w2;
    assign wo_3 = kld ? key[31:0]   : next_w3;

    always @(posedge clk) begin
        if (kld) begin
            w0_reg <= key[127:96];
            w1_reg <= key[95:64];
            w2_reg <= key[63:32];
            w3_reg <= key[31:0];
        end else begin
            w0_reg <= next_w0;
            w1_reg <= next_w1;
            w2_reg <= next_w2;
            w3_reg <= next_w3;
        end
    end
endmodule
