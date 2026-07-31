module aes_key_expand (
    input  wire         clk,
    input  wire         rst,
    input  wire         kld,
    input  wire [127:0] initial_key,
    output reg  [127:0] round_key
);

reg [3:0]  rcnt;
reg [31:0] w0;
reg [31:0] w1;
reg [31:0] w2;
reg [31:0] w3;

wire [7:0] sbox_request_0;
wire [7:0] sbox_request_1;
wire [7:0] sbox_request_2;
wire [7:0] sbox_request_3;
wire [7:0] sbox_response_0;
wire [7:0] sbox_response_1;
wire [7:0] sbox_response_2;
wire [7:0] sbox_response_3;

reg  [7:0]  rcon_byte;
wire [31:0] rcon_word;
wire [31:0] rotated_subword;
wire [31:0] transformed_w3;
wire [31:0] next_w0;
wire [31:0] next_w1;
wire [31:0] next_w2;
wire [31:0] next_w3;

assign sbox_request_0 = w3[23:16];
assign sbox_request_1 = w3[15:8];
assign sbox_request_2 = w3[7:0];
assign sbox_request_3 = w3[31:24];

aes_sbox u_aes_sbox_0 (
    .sbox_byte_request  (sbox_request_0),
    .sbox_byte_response (sbox_response_0)
);

aes_sbox u_aes_sbox_1 (
    .sbox_byte_request  (sbox_request_1),
    .sbox_byte_response (sbox_response_1)
);

aes_sbox u_aes_sbox_2 (
    .sbox_byte_request  (sbox_request_2),
    .sbox_byte_response (sbox_response_2)
);

aes_sbox u_aes_sbox_3 (
    .sbox_byte_request  (sbox_request_3),
    .sbox_byte_response (sbox_response_3)
);

always @(rcnt) begin
    case (rcnt)
        4'd0:    rcon_byte = 8'h01;
        4'd1:    rcon_byte = 8'h02;
        4'd2:    rcon_byte = 8'h04;
        4'd3:    rcon_byte = 8'h08;
        4'd4:    rcon_byte = 8'h10;
        4'd5:    rcon_byte = 8'h20;
        4'd6:    rcon_byte = 8'h40;
        4'd7:    rcon_byte = 8'h80;
        4'd8:    rcon_byte = 8'h1b;
        4'd9:    rcon_byte = 8'h36;
        default: rcon_byte = 8'h00;
    endcase
end

assign rcon_word = {rcon_byte, 24'h000000};

assign rotated_subword = {
    sbox_response_0,
    sbox_response_1,
    sbox_response_2,
    sbox_response_3
};

assign transformed_w3 = rotated_subword ^ rcon_word;
assign next_w0 = w0 ^ transformed_w3;
assign next_w1 = w1 ^ next_w0;
assign next_w2 = w2 ^ next_w1;
assign next_w3 = w3 ^ next_w2;

always @(posedge clk) begin
    if (!rst) begin
        rcnt      <= 4'd0;
        w0        <= 32'd0;
        w1        <= 32'd0;
        w2        <= 32'd0;
        w3        <= 32'd0;
        round_key <= 128'd0;
    end else if (kld) begin
        rcnt      <= 4'd0;
        w0        <= initial_key[127:96];
        w1        <= initial_key[95:64];
        w2        <= initial_key[63:32];
        w3        <= initial_key[31:0];
        round_key <= initial_key;
    end else if (rcnt < 4'd10) begin
        rcnt      <= rcnt + 4'd1;
        w0        <= next_w0;
        w1        <= next_w1;
        w2        <= next_w2;
        w3        <= next_w3;
        round_key <= {next_w0, next_w1, next_w2, next_w3};
    end
end

endmodule
