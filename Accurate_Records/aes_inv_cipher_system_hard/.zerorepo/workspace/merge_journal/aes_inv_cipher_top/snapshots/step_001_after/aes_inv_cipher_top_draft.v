module aes_inv_cipher_top (
    input  wire         clk,
    input  wire         rst,
    input  wire         kld,
    input  wire         ld,
    output reg          done,
    input  wire [127:0] key,
    input  wire [127:0] text_in,
    output reg  [127:0] text_out
);

localparam [2:0] FSM_IDLE           = 3'd0;
localparam [2:0] FSM_KEY_LOAD       = 3'd1;
localparam [2:0] FSM_KEY_EXPANSION  = 3'd2;
localparam [2:0] FSM_KEY_STORED     = 3'd3;
localparam [2:0] FSM_INITIAL_ROUND  = 3'd4;
localparam [2:0] FSM_STANDARD_ROUND = 3'd5;
localparam [2:0] FSM_FINAL_ROUND    = 3'd6;
localparam [2:0] FSM_DONE           = 3'd7;

reg [127:0]  state_matrix;
reg [1407:0] round_key_buffer;
reg [3:0]    dcnt;
reg [2:0]    fsm_state;
reg [127:0]  initial_key_reg;
reg          key_expand_kld;

wire [127:0] key_expand_round_key;
wire [127:0] round_key;
wire [127:0] after_shift;
wire [127:0] after_sub;
wire [127:0] after_add;
wire [127:0] after_mix;
wire [127:0] next_state_comb;

wire [7:0] sbox_out_00;
wire [7:0] sbox_out_10;
wire [7:0] sbox_out_20;
wire [7:0] sbox_out_30;
wire [7:0] sbox_out_01;
wire [7:0] sbox_out_11;
wire [7:0] sbox_out_21;
wire [7:0] sbox_out_31;
wire [7:0] sbox_out_02;
wire [7:0] sbox_out_12;
wire [7:0] sbox_out_22;
wire [7:0] sbox_out_32;
wire [7:0] sbox_out_03;
wire [7:0] sbox_out_13;
wire [7:0] sbox_out_23;
wire [7:0] sbox_out_33;

wire [7:0] mix0_0;
wire [7:0] mix1_0;
wire [7:0] mix2_0;
wire [7:0] mix3_0;
wire [7:0] mix0_1;
wire [7:0] mix1_1;
wire [7:0] mix2_1;
wire [7:0] mix3_1;
wire [7:0] mix0_2;
wire [7:0] mix1_2;
wire [7:0] mix2_2;
wire [7:0] mix3_2;
wire [7:0] mix0_3;
wire [7:0] mix1_3;
wire [7:0] mix2_3;
wire [7:0] mix3_3;

function automatic [7:0] xtime;
    input [7:0] value;
    begin
        xtime = {value[6:0], 1'b0} ^ (value[7] ? 8'h1b : 8'h00);
    end
endfunction

function automatic [7:0] mul0e;
    input [7:0] value;
    reg [7:0] value_x2;
    reg [7:0] value_x4;
    reg [7:0] value_x8;
    begin
        value_x2 = xtime(value);
        value_x4 = xtime(value_x2);
        value_x8 = xtime(value_x4);
        mul0e = value_x8 ^ value_x4 ^ value_x2;
    end
endfunction

function automatic [7:0] mul0b;
    input [7:0] value;
    reg [7:0] value_x2;
    reg [7:0] value_x4;
    reg [7:0] value_x8;
    begin
        value_x2 = xtime(value);
        value_x4 = xtime(value_x2);
        value_x8 = xtime(value_x4);
        mul0b = value_x8 ^ value_x2 ^ value;
    end
endfunction

function automatic [7:0] mul0d;
    input [7:0] value;
    reg [7:0] value_x2;
    reg [7:0] value_x4;
    reg [7:0] value_x8;
    begin
        value_x2 = xtime(value);
        value_x4 = xtime(value_x2);
        value_x8 = xtime(value_x4);
        mul0d = value_x8 ^ value_x4 ^ value;
    end
endfunction

function automatic [7:0] mul09;
    input [7:0] value;
    reg [7:0] value_x2;
    reg [7:0] value_x4;
    reg [7:0] value_x8;
    begin
        value_x2 = xtime(value);
        value_x4 = xtime(value_x2);
        value_x8 = xtime(value_x4);
        mul09 = value_x8 ^ value;
    end
endfunction

aes_key_expand inst_key_expand (
    .clk         (clk),
    .rst         (rst),
    .kld         (key_expand_kld),
    .initial_key (initial_key_reg),
    .round_key   (key_expand_round_key)
);

assign round_key =
    (dcnt == 4'd1)  ? round_key_buffer[1279:1152] :
    (dcnt == 4'd2)  ? round_key_buffer[1151:1024] :
    (dcnt == 4'd3)  ? round_key_buffer[1023:896]  :
    (dcnt == 4'd4)  ? round_key_buffer[895:768]   :
    (dcnt == 4'd5)  ? round_key_buffer[767:640]   :
    (dcnt == 4'd6)  ? round_key_buffer[639:512]   :
    (dcnt == 4'd7)  ? round_key_buffer[511:384]   :
    (dcnt == 4'd8)  ? round_key_buffer[383:256]   :
    (dcnt == 4'd9)  ? round_key_buffer[255:128]   :
    (dcnt == 4'd10) ? round_key_buffer[127:0]     :
                       128'd0;

// InvShiftRows for the column-major state representation.
assign after_shift = {
    state_matrix[127:120], state_matrix[23:16],  state_matrix[47:40], state_matrix[71:64],
    state_matrix[95:88],   state_matrix[119:112], state_matrix[15:8],  state_matrix[39:32],
    state_matrix[63:56],   state_matrix[87:80],   state_matrix[111:104], state_matrix[7:0],
    state_matrix[31:24],   state_matrix[55:48],   state_matrix[79:72], state_matrix[103:96]
};

aes_inv_sbox inst_inv_sbox_00 (.byte_in(after_shift[127:120]), .byte_out(sbox_out_00));
aes_inv_sbox inst_inv_sbox_10 (.byte_in(after_shift[119:112]), .byte_out(sbox_out_10));
aes_inv_sbox inst_inv_sbox_20 (.byte_in(after_shift[111:104]), .byte_out(sbox_out_20));
aes_inv_sbox inst_inv_sbox_30 (.byte_in(after_shift[103:96]),  .byte_out(sbox_out_30));
aes_inv_sbox inst_inv_sbox_01 (.byte_in(after_shift[95:88]),   .byte_out(sbox_out_01));
aes_inv_sbox inst_inv_sbox_11 (.byte_in(after_shift[87:80]),   .byte_out(sbox_out_11));
aes_inv_sbox inst_inv_sbox_21 (.byte_in(after_shift[79:72]),   .byte_out(sbox_out_21));
aes_inv_sbox inst_inv_sbox_31 (.byte_in(after_shift[71:64]),   .byte_out(sbox_out_31));
aes_inv_sbox inst_inv_sbox_02 (.byte_in(after_shift[63:56]),   .byte_out(sbox_out_02));
aes_inv_sbox inst_inv_sbox_12 (.byte_in(after_shift[55:48]),   .byte_out(sbox_out_12));
aes_inv_sbox inst_inv_sbox_22 (.byte_in(after_shift[47:40]),   .byte_out(sbox_out_22));
aes_inv_sbox inst_inv_sbox_32 (.byte_in(after_shift[39:32]),   .byte_out(sbox_out_32));
aes_inv_sbox inst_inv_sbox_03 (.byte_in(after_shift[31:24]),   .byte_out(sbox_out_03));
aes_inv_sbox inst_inv_sbox_13 (.byte_in(after_shift[23:16]),   .byte_out(sbox_out_13));
aes_inv_sbox inst_inv_sbox_23 (.byte_in(after_shift[15:8]),    .byte_out(sbox_out_23));
aes_inv_sbox inst_inv_sbox_33 (.byte_in(after_shift[7:0]),     .byte_out(sbox_out_33));

assign after_sub = {
    sbox_out_00, sbox_out_10, sbox_out_20, sbox_out_30,
    sbox_out_01, sbox_out_11, sbox_out_21, sbox_out_31,
    sbox_out_02, sbox_out_12, sbox_out_22, sbox_out_32,
    sbox_out_03, sbox_out_13, sbox_out_23, sbox_out_33
};

assign after_add = after_sub ^ round_key;

assign mix0_0 = mul0e(after_add[127:120]) ^ mul0b(after_add[119:112]) ^
                mul0d(after_add[111:104]) ^ mul09(after_add[103:96]);
assign mix1_0 = mul09(after_add[127:120]) ^ mul0e(after_add[119:112]) ^
                mul0b(after_add[111:104]) ^ mul0d(after_add[103:96]);
assign mix2_0 = mul0d(after_add[127:120]) ^ mul09(after_add[119:112]) ^
                mul0e(after_add[111:104]) ^ mul0b(after_add[103:96]);
assign mix3_0 = mul0b(after_add[127:120]) ^ mul0d(after_add[119:112]) ^
                mul09(after_add[111:104]) ^ mul0e(after_add[103:96]);

assign mix0_1 = mul0e(after_add[95:88]) ^ mul0b(after_add[87:80]) ^
                mul0d(after_add[79:72]) ^ mul09(after_add[71:64]);
assign mix1_1 = mul09(after_add[95:88]) ^ mul0e(after_add[87:80]) ^
                mul0b(after_add[79:72]) ^ mul0d(after_add[71:64]);
assign mix2_1 = mul0d(after_add[95:88]) ^ mul09(after_add[87:80]) ^
                mul0e(after_add[79:72]) ^ mul0b(after_add[71:64]);
assign mix3_1 = mul0b(after_add[95:88]) ^ mul0d(after_add[87:80]) ^
                mul09(after_add[79:72]) ^ mul0e(after_add[71:64]);

assign mix0_2 = mul0e(after_add[63:56]) ^ mul0b(after_add[55:48]) ^
                mul0d(after_add[47:40]) ^ mul09(after_add[39:32]);
assign mix1_2 = mul09(after_add[63:56]) ^ mul0e(after_add[55:48]) ^
                mul0b(after_add[47:40]) ^ mul0d(after_add[39:32]);
assign mix2_2 = mul0d(after_add[63:56]) ^ mul09(after_add[55:48]) ^
                mul0e(after_add[47:40]) ^ mul0b(after_add[39:32]);
assign mix3_2 = mul0b(after_add[63:56]) ^ mul0d(after_add[55:48]) ^
                mul09(after_add[47:40]) ^ mul0e(after_add[39:32]);

assign mix0_3 = mul0e(after_add[31:24]) ^ mul0b(after_add[23:16]) ^
                mul0d(after_add[15:8]) ^ mul09(after_add[7:0]);
assign mix1_3 = mul09(after_add[31:24]) ^ mul0e(after_add[23:16]) ^
                mul0b(after_add[15:8]) ^ mul0d(after_add[7:0]);
assign mix2_3 = mul0d(after_add[31:24]) ^ mul09(after_add[23:16]) ^
                mul0e(after_add[15:8]) ^ mul0b(after_add[7:0]);
assign mix3_3 = mul0b(after_add[31:24]) ^ mul0d(after_add[23:16]) ^
                mul09(after_add[15:8]) ^ mul0e(after_add[7:0]);

assign after_mix = {
    mix0_0, mix1_0, mix2_0, mix3_0,
    mix0_1, mix1_1, mix2_1, mix3_1,
    mix0_2, mix1_2, mix2_2, mix3_2,
    mix0_3, mix1_3, mix2_3, mix3_3
};

assign next_state_comb = (fsm_state == FSM_FINAL_ROUND) ? after_add : after_mix;

always @(posedge clk) begin
    if (rst) begin
        fsm_state       <= FSM_IDLE;
        dcnt            <= 4'd0;
        state_matrix    <= 128'd0;
        round_key_buffer <= 1408'd0;
        initial_key_reg <= 128'd0;
        key_expand_kld  <= 1'b0;
    end else begin
        key_expand_kld <= 1'b0;
        case (fsm_state)
            FSM_IDLE: begin
                if (kld) begin
                    initial_key_reg <= key;
                    key_expand_kld  <= 1'b1;
                    dcnt            <= 4'd0;
                    fsm_state       <= FSM_KEY_LOAD;
                end
            end

            FSM_KEY_LOAD: begin
                dcnt      <= 4'd0;
                fsm_state <= FSM_KEY_EXPANSION;
            end

            FSM_KEY_EXPANSION: begin
                case (dcnt)
                    4'd0:  round_key_buffer[127:0]     <= key_expand_round_key;
                    4'd1:  round_key_buffer[255:128]   <= key_expand_round_key;
                    4'd2:  round_key_buffer[383:256]   <= key_expand_round_key;
                    4'd3:  round_key_buffer[511:384]   <= key_expand_round_key;
                    4'd4:  round_key_buffer[639:512]   <= key_expand_round_key;
                    4'd5:  round_key_buffer[767:640]   <= key_expand_round_key;
                    4'd6:  round_key_buffer[895:768]   <= key_expand_round_key;
                    4'd7:  round_key_buffer[1023:896]  <= key_expand_round_key;
                    4'd8:  round_key_buffer[1151:1024] <= key_expand_round_key;
                    4'd9:  round_key_buffer[1279:1152] <= key_expand_round_key;
                    4'd10: round_key_buffer[1407:1280] <= key_expand_round_key;
                    default: round_key_buffer <= round_key_buffer;
                endcase

                if (dcnt == 4'd10) begin
                    dcnt      <= 4'd0;
                    fsm_state <= FSM_KEY_STORED;
                end else begin
                    dcnt <= dcnt + 4'd1;
                end
            end

            FSM_KEY_STORED: begin
                if (kld) begin
                    initial_key_reg <= key;
                    key_expand_kld  <= 1'b1;
                    dcnt            <= 4'd0;
                    fsm_state       <= FSM_KEY_LOAD;
                end else if (ld) begin
                    state_matrix <= text_in;
                    dcnt         <= 4'd0;
                    fsm_state    <= FSM_INITIAL_ROUND;
                end
            end

            FSM_INITIAL_ROUND: begin
                state_matrix <= state_matrix ^ round_key_buffer[1407:1280];
                dcnt         <= 4'd1;
                fsm_state    <= FSM_STANDARD_ROUND;
            end

            FSM_STANDARD_ROUND: begin
                state_matrix <= next_state_comb;
                if (dcnt == 4'd9) begin
                    dcnt      <= 4'd10;
                    fsm_state <= FSM_FINAL_ROUND;
                end else begin
                    dcnt <= dcnt + 4'd1;
                end
            end

            FSM_FINAL_ROUND: begin
                state_matrix <= next_state_comb;
                fsm_state    <= FSM_DONE;
            end

            FSM_DONE: begin
                fsm_state <= FSM_IDLE;
            end

            default: begin
                fsm_state <= FSM_IDLE;
                dcnt      <= 4'd0;
            end
        endcase
    end
end

always @(posedge clk) begin
    if (rst) begin
        text_out <= 128'd0;
        done     <= 1'b0;
    end else if (fsm_state == FSM_DONE) begin
        text_out <= state_matrix;
        done     <= 1'b1;
    end else begin
        done <= 1'b0;
    end
end

endmodule
