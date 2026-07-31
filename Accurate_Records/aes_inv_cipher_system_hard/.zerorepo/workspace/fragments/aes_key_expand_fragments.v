// STAGE5_SUBTASK_BEGIN B1_decl_state_and_regs: Declare sequential state: 4-bit round counter rcnt (0–9) and four 32-bit registers w0, w1, w2, w3 holding the current ro
reg [3:0] rcnt;
reg [31:0] w0;
reg [31:0] w1;
reg [31:0] w2;
reg [31:0] w3;
// STAGE5_SUBTASK_END B1_decl_state_and_regs

// STAGE5_SUBTASK_BEGIN B2_inst_sbox: Instantiate a single aes_sbox module for combinational byte substitution used in SubWord. Connect byte input and output 
wire [7:0] sbox_request;
wire [7:0] sbox_response;

aes_sbox u_aes_sbox (
    .sbox_byte_request  (sbox_request),
    .sbox_byte_response (sbox_response)
);
// STAGE5_SUBTASK_END B2_inst_sbox

// STAGE5_SUBTASK_BEGIN B3_comb_round_const_gen: Derive an 8-bit round constant (Rcon) combinationally from rcnt, using a lookup table or shift-based method. Only the hi
reg [7:0] rcon_byte;
wire [31:0] rcon_word;

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
// STAGE5_SUBTASK_END B3_comb_round_const_gen

// STAGE5_SUBTASK_BEGIN B4_comb_key_expand_next: Implement pure combinational key expansion datapath: rotate w3, feed byte to sbox, XOR SubWord result with Rcon, then XO
wire [7:0] sbox_request_1;
wire [7:0] sbox_request_2;
wire [7:0] sbox_request_3;
wire [7:0] sbox_response_1;
wire [7:0] sbox_response_2;
wire [7:0] sbox_response_3;
wire [31:0] rotated_subword;
wire [31:0] transformed_w3;
wire [31:0] next_w0;
wire [31:0] next_w1;
wire [31:0] next_w2;
wire [31:0] next_w3;

assign sbox_request   = w3[23:16];
assign sbox_request_1 = w3[15:8];
assign sbox_request_2 = w3[7:0];
assign sbox_request_3 = w3[31:24];

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

assign rotated_subword[31:24] = sbox_response;
assign rotated_subword[23:16] = sbox_response_1;
assign rotated_subword[15:8]  = sbox_response_2;
assign rotated_subword[7:0]   = sbox_response_3;

assign transformed_w3 = rotated_subword ^ rcon_word;
assign next_w0 = w0 ^ transformed_w3;
assign next_w1 = w1 ^ next_w0;
assign next_w2 = w2 ^ next_w1;
assign next_w3 = w3 ^ next_w2;
// STAGE5_SUBTASK_END B4_comb_key_expand_next

// STAGE5_SUBTASK_BEGIN B5_seq_update: Sequential always block: on posedge clk with synchronous reset, if kld load initial_key into w0..w3 and clear rcnt; else
always @(posedge clk) begin
    if (rst) begin
        rcnt      <= 4'd0;
        w0        <= 32'd0;
        w1        <= 32'd0;
        w2        <= 32'd0;
        w3        <= 32'd0;
        round_key <= 128'd0;
    end else if (kld) begin
        rcnt <= 4'd0;
        w0   <= initial_key[127:96];
        w1   <= initial_key[95:64];
        w2   <= initial_key[63:32];
        w3   <= initial_key[31:0];
    end else if (rcnt < 4'd10) begin
        rcnt      <= rcnt + 4'd1;
        w0        <= next_w0;
        w1        <= next_w1;
        w2        <= next_w2;
        w3        <= next_w3;
        round_key <= {w0, w1, w2, w3};
    end
end
// STAGE5_SUBTASK_END B5_seq_update
