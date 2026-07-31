// STAGE5_SUBTASK_BEGIN B1_decl_core_state: Declare all persistent storage: state_matrix (4x4 bytes) as a flat reg vector, round_key_buffer (11x128-bit) as a flat r
localparam [2:0] FSM_IDLE           = 3'd0;
localparam [2:0] FSM_KEY_LOAD       = 3'd1;
localparam [2:0] FSM_KEY_EXPANSION  = 3'd2;
localparam [2:0] FSM_KEY_STORED     = 3'd3;
localparam [2:0] FSM_INITIAL_ROUND  = 3'd4;
localparam [2:0] FSM_STANDARD_ROUND = 3'd5;
localparam [2:0] FSM_FINAL_ROUND    = 3'd6;
localparam [2:0] FSM_DONE           = 3'd7;

// Column-major byte layout: [127:120] is sa00, followed by sa10.
reg [127:0] state_matrix;

// Eleven 128-bit round keys: key 0 at [127:0], key 10 at [1407:1280].
reg [1407:0] round_key_buffer;

reg [3:0] dcnt;
reg [2:0] fsm_state;
reg [127:0] initial_key_reg;
// STAGE5_SUBTASK_END B1_decl_core_state

// STAGE5_SUBTASK_BEGIN B2_inst_child_modules: Instantiate aes_key_expand and aes_inv_sbox as submodules, connecting clk, rst, key, text_in, and other necessary contro
wire [127:0] key_expand_round_key;
reg          key_expand_kld;
reg  [7:0]   inv_sbox_byte_in;
wire [7:0]   inv_sbox_byte_out;

aes_key_expand inst_key_expand (
    .round_key  (key_expand_round_key),
    .initial_key(initial_key_reg),
    .kld        (key_expand_kld),
    .rst        (rst),
    .clk        (clk)
);

aes_inv_sbox inst_inv_sbox (
    .byte_out(inv_sbox_byte_out),
    .byte_in (inv_sbox_byte_in)
);
// STAGE5_SUBTASK_END B2_inst_child_modules

// STAGE5_SUBTASK_BEGIN B3_comb_round_network: Combinational network that computes next_state_comb from current state matrix and round key: apply InvShiftRows (byte re
// ------------------------------------------------------------
// Combinational round network (B3)
// ------------------------------------------------------------

// Helper: GF(2^8) multiply by 2 (xtime)
function [7:0] xtime;
    input [7:0] b;
    xtime = {b[6:0], 1'b0} ^ (b[7] ? 8'h1B : 8'h00);
endfunction

// GF(2^8) multiply by 0x0E, 0x0B, 0x0D, 0x09
function [7:0] mul0E;
    input [7:0] a;
    reg [7:0] t1, t2, t3;
    begin
        t1 = xtime(a);
        t2 = xtime(t1);
        t3 = xtime(t2);
        mul0E = t3 ^ t2 ^ t1;
    end
endfunction

function [7:0] mul0B;
    input [7:0] a;
    reg [7:0] t1, t2, t3;
    begin
        t1 = xtime(a);
        t2 = xtime(t1);
        t3 = xtime(t2);
        mul0B = t3 ^ t1 ^ a;
    end
endfunction

function [7:0] mul0D;
    input [7:0] a;
    reg [7:0] t1, t2, t3;
    begin
        t1 = xtime(a);
        t2 = xtime(t1);
        t3 = xtime(t2);
        mul0D = t3 ^ t2 ^ a;
    end
endfunction

function [7:0] mul09;
    input [7:0] a;
    reg [7:0] t1, t2, t3;
    begin
        t1 = xtime(a);
        t2 = xtime(t1);
        t3 = xtime(t2);
        mul09 = t3 ^ a;
    end
endfunction

// ------------------------------------------------------------
// Round key selection from buffer (combinational)
// ------------------------------------------------------------
wire [127:0] round_key;
always @(*) begin
    case (dcnt)
        4'd1:  round_key = round_key_buffer[1279:1152];
        4'd2:  round_key = round_key_buffer[1151:1024];
        4'd3:  round_key = round_key_buffer[1023:896];
        4'd4:  round_key = round_key_buffer[895:768];
        4'd5:  round_key = round_key_buffer[767:640];
        4'd6:  round_key = round_key_buffer[639:512];
        4'd7:  round_key = round_key_buffer[511:384];
        4'd8:  round_key = round_key_buffer[383:256];
        4'd9:  round_key = round_key_buffer[255:128];
        4'd10: round_key = round_key_buffer[127:0];
        default: round_key = 128'd0;
    endcase
end

// ------------------------------------------------------------
// Extract state bytes from state_matrix (column-major)
// ------------------------------------------------------------
wire [7:0] sa_00 = state_matrix[127:120];
wire [7:0] sa_10 = state_matrix[119:112];
wire [7:0] sa_20 = state_matrix[111:104];
wire [7:0] sa_30 = state_matrix[103:96];
wire [7:0] sa_01 = state_matrix[95:88];
wire [7:0] sa_11 = state_matrix[87:80];
wire [7:0] sa_21 = state_matrix[79:72];
wire [7:0] sa_31 = state_matrix[71:64];
wire [7:0] sa_02 = state_matrix[63:56];
wire [7:0] sa_12 = state_matrix[55:48];
wire [7:0] sa_22 = state_matrix[47:40];
wire [7:0] sa_32 = state_matrix[39:32];
wire [7:0] sa_03 = state_matrix[31:24];
wire [7:0] sa_13 = state_matrix[23:16];
wire [7:0] sa_23 = state_matrix[15:8];
wire [7:0] sa_33 = state_matrix[7:0];

// ------------------------------------------------------------
// InvShiftRows
// ------------------------------------------------------------
wire [127:0] after_shift;
// Row 0: no shift
assign after_shift[127:120] = sa_00;
assign after_shift[95:88]   = sa_01;
assign after_shift[63:56]   = sa_02;
assign after_shift[31:24]   = sa_03;
// Row 1: right shift by 1
assign after_shift[119:112] = sa_30;
assign after_shift[87:80]   = sa_00;
assign after_shift[55:48]   = sa_10;
assign after_shift[23:16]   = sa_20;
// Row 2: right shift by 2
assign after_shift[111:104] = sa_20;
assign after_shift[79:72]   = sa_30;
assign after_shift[47:40]   = sa_00;
assign after_shift[15:8]    = sa_10;
// Row 3: right shift by 3
assign after_shift[103:96]  = sa_10;
assign after_shift[71:64]   = sa_20;
assign after_shift[39:32]   = sa_30;
assign after_shift[7:0]     = sa_00;

// ------------------------------------------------------------
// InvSubBytes – use 16 combinational inv_sbox instances
// ------------------------------------------------------------
wire [7:0] sbox_in_00, sbox_in_01, sbox_in_02, sbox_in_03;
wire [7:0] sbox_in_10, sbox_in_11, sbox_in_12, sbox_in_13;
wire [7:0] sbox_in_20, sbox_in_21, sbox_in_22, sbox_in_23;
wire [7:0] sbox_in_30, sbox_in_31, sbox_in_32, sbox_in_33;

wire [7:0] sbox_out_00, sbox_out_01, sbox_out_02, sbox_out_03;
wire [7:0] sbox_out_10, sbox_out_11, sbox_out_12, sbox_out_13;
wire [7:0] sbox_out_20, sbox_out_21, sbox_out_22, sbox_out_23;
wire [7:0] sbox_out_30, sbox_out_31, sbox_out_32, sbox_out_33;

assign sbox_in_00 = after_shift[127:120];
assign sbox_in_10 = after_shift[119:112];
assign sbox_in_20 = after_shift[111:104];
assign sbox_in_30 = after_shift[103:96];
assign sbox_in_01 = after_shift[95:88];
assign sbox_in_11 = after_shift[87:80];
assign sbox_in_21 = after_shift[79:72];
assign sbox_in_31 = after_shift[71:64];
assign sbox_in_02 = after_shift[63:56];
assign sbox_in_12 = after_shift[55:48];
assign sbox_in_22 = after_shift[47:40];
assign sbox_in_32 = after_shift[39:32];
assign sbox_in_03 = after_shift[31:24];
assign sbox_in_13 = after_shift[23:16];
assign sbox_in_23 = after_shift[15:8];
assign sbox_in_33 = after_shift[7:0];

wire [127:0] after_sub;
assign after_sub[127:120] = sbox_out_00;
assign after_sub[119:112] = sbox_out_10;
assign after_sub[111:104] = sbox_out_20;
assign after_sub[103:96]  = sbox_out_30;
assign after_sub[95:88]   = sbox_out_01;
assign after_sub[87:80]   = sbox_out_11;
assign after_sub[79:72]   = sbox_out_21;
assign after_sub[71:64]   = sbox_out_31;
assign after_sub[63:56]   = sbox_out_02;
assign after_sub[55:48]   = sbox_out_12;
assign after_sub[47:40]   = sbox_out_22;
assign after_sub[39:32]   = sbox_out_32;
assign after_sub[31:24]   = sbox_out_03;
assign after_sub[23:16]   = sbox_out_13;
assign after_sub[15:8]    = sbox_out_23;
assign after_sub[7:0]     = sbox_out_33;

// ------------------------------------------------------------
// AddRoundKey
// ------------------------------------------------------------
wire [127:0] after_add;
assign after_add = after_sub ^ round_key;

// ------------------------------------------------------------
// InvMixColumns (omitted during FinalRound)
// ------------------------------------------------------------
wire [127:0] after_mix;

// Column 0
wire [7:0] col0_j0 = after_add[127:120];
wire [7:0] col1_j0 = after_add[119:112];
wire [7:0] col2_j0 = after_add[111:104];
wire [7:0] col3_j0 = after_add[103:96];

wire [7:0] mix0_0 = mul0E(col0_j0) ^ mul0B(col1_j0) ^ mul0D(col2_j0) ^ mul09(col3_j0);
wire [7:0] mix1_0 = mul09(col0_j0) ^ mul0E(col1_j0) ^ mul0B(col2_j0) ^ mul0D(col3_j0);
wire [7:0] mix2_0 = mul0D(col0_j0) ^ mul09(col1_j0) ^ mul0E(col2_j0) ^ mul0B(col3_j0);
wire [7:0] mix3_0 = mul0B(col0_j0) ^ mul0D(col1_j0) ^ mul09(col2_j0) ^ mul0E(col3_j0);

assign after_mix[127:120] = mix0_0;
assign after_mix[119:112] = mix1_0;
assign after_mix[111:104] = mix2_0;
assign after_mix[103:96]  = mix3_0;

// Column 1
wire [7:0] col0_j1 = after_add[95:88];
wire [7:0] col1_j1 = after_add[87:80];
wire [7:0] col2_j1 = after_add[79:72];
wire [7:0] col3_j1 = after_add[71:64];

wire [7:0] mix0_1 = mul0E(col0_j1) ^ mul0B(col1_j1) ^ mul0D(col2_j1) ^ mul09(col3_j1);
wire [7:0] mix1_1 = mul09(col0_j1) ^ mul0E(col1_j1) ^ mul0B(col2_j1) ^ mul0D(col3_j1);
wire [7:0] mix2_1 = mul0D(col0_j1) ^ mul09(col1_j1) ^ mul0E(col2_j1) ^ mul0B(col3_j1);
wire [7:0] mix3_1 = mul0B(col0_j1) ^ mul0D(col1_j1) ^ mul09(col2_j1) ^ mul0E(col3_j1);

assign after_mix[95:88] = mix0_1;
assign after_mix[87:80] = mix1_1;
assign after_mix[79:72] = mix2_1;
assign after_mix[71:64] = mix3_1;

// Column 2
wire [7:0] col0_j2 = after_add[63:56];
wire [7:0] col1_j2 = after_add[55:48];
wire [7:0] col2_j2 = after_add[47:40];
wire [7:0] col3_j2 = after_add[39:32];

wire [7:0] mix0_2 = mul0E(col0_j2) ^ mul0B(col1_j2) ^ mul0D(col2_j2) ^ mul09(col3_j2);
wire [7:0] mix1_2 = mul09(col0_j2) ^ mul0E(col1_j2) ^ mul0B(col2_j2) ^ mul0D(col3_j2);
wire [7:0] mix2_2 = mul0D(col0_j2) ^ mul09(col1_j2) ^ mul0E(col2_j2) ^ mul0B(col3_j2);
wire [7:0] mix3_2 = mul0B(col0_j2) ^ mul0D(col1_j2) ^ mul09(col2_j2) ^ mul0E(col3_j2);

assign after_mix[63:56] = mix0_2;
assign after_mix[55:48] = mix1_2;
assign after_mix[47:40] = mix2_2;
assign after_mix[39:32] = mix3_2;

// Column 3
wire [7:0] col0_j3 = after_add[31:24];
wire [7:0] col1_j3 = after_add[23:16];
wire [7:0] col2_j3 = after_add[15:8];
wire [7:0] col3_j3 = after_add[7:0];

wire [7:0] mix0_3 = mul0E(col0_j3) ^ mul0B(col1_j3) ^ mul0D(col2_j3) ^ mul09(col3_j3);
wire [7:0] mix1_3 = mul09(col0_j3) ^ mul0E(col1_j3) ^ mul0B(col2_j3) ^ mul0D(col3_j3);
wire [7:0] mix2_3 = mul0D(col0_j3) ^ mul09(col1_j3) ^ mul0E(col2_j3) ^ mul0B(col3_j3);
wire [7:0] mix3_3 = mul0B(col0_j3) ^ mul0D(col1_j3) ^ mul09(col2_j3) ^ mul0E(col3_j3);

assign after_mix[31:24] = mix0_3;
assign after_mix[23:16] = mix1_3;
assign after_mix[15:8]  = mix2_3;
assign after_mix[7:0]   = mix3_3;

// ------------------------------------------------------------
// Final next-state mux
// ------------------------------------------------------------
wire [127:0] next_state_comb;
assign next_state_comb = (fsm_state == 3'd6) ? after_add : after_mix;
// STAGE5_SUBTASK_END B3_comb_round_network

// STAGE5_SUBTASK_BEGIN B4_seq_control: Sequential always block implementing FSM with phases: IDLE, KeyLoad, KeyExpansion, KeyStored, InitialRound, StandardRoun
// ------------------------------------------------------------
// Sequential control always block (B4)
// ------------------------------------------------------------
always @(posedge clk) begin
    if (rst) begin
        fsm_state         <= FSM_IDLE;
        dcnt               <= 4'd0;
        state_matrix       <= 128'd0;
        round_key_buffer   <= 1408'd0;
        initial_key_reg    <= 128'd0;
        key_expand_kld     <= 1'b0;
    end else begin
        // Default hold values
        key_expand_kld <= 1'b0;

        case (fsm_state)
            FSM_IDLE: begin
                if (kld) begin
                    fsm_state <= FSM_KEY_LOAD;
                    dcnt     <= 4'd0;
                end
            end

            FSM_KEY_LOAD: begin
                initial_key_reg <= key;
                key_expand_kld  <= 1'b1;
                fsm_state       <= FSM_KEY_EXPANSION;
            end

            FSM_KEY_EXPANSION: begin
                // Store current round key into buffer
                case (dcnt)
                    4'd0:  round_key_buffer[127:0]   <= key_expand_round_key;
                    4'd1:  round_key_buffer[255:128]  <= key_expand_round_key;
                    4'd2:  round_key_buffer[383:256]  <= key_expand_round_key;
                    4'd3:  round_key_buffer[511:384]  <= key_expand_round_key;
                    4'd4:  round_key_buffer[639:512]  <= key_expand_round_key;
                    4'd5:  round_key_buffer[767:640]  <= key_expand_round_key;
                    4'd6:  round_key_buffer[895:768]  <= key_expand_round_key;
                    4'd7:  round_key_buffer[1023:896] <= key_expand_round_key;
                    4'd8:  round_key_buffer[1151:1024]<= key_expand_round_key;
                    4'd9:  round_key_buffer[1279:1152]<= key_expand_round_key;
                    4'd10: round_key_buffer[1407:1280]<= key_expand_round_key;
                    default: /* no write */ ;
                endcase

                if (dcnt == 4'd10) begin
                    fsm_state <= FSM_KEY_STORED;
                    dcnt      <= 4'd0;
                end else begin
                    fsm_state <= FSM_KEY_EXPANSION;
                    dcnt      <= dcnt + 1;
                end
            end

            FSM_KEY_STORED: begin
                if (ld) begin
                    state_matrix <= text_in;
                    fsm_state    <= FSM_INITIAL_ROUND;
                end
            end

            FSM_INITIAL_ROUND: begin
                state_matrix <= next_state_comb;
                dcnt         <= dcnt + 1;
                fsm_state    <= FSM_STANDARD_ROUND;
            end

            FSM_STANDARD_ROUND: begin
                state_matrix <= next_state_comb;
                if (dcnt == 4'd9) begin
                    dcnt      <= dcnt + 1;
                    fsm_state <= FSM_FINAL_ROUND;
                end else begin
                    dcnt      <= dcnt + 1;
                    fsm_state <= FSM_STANDARD_ROUND;
                end
            end

            FSM_FINAL_ROUND: begin
                state_matrix <= next_state_comb;
                if (dcnt == 4'd10) begin
                    dcnt      <= dcnt + 1;
                    fsm_state <= FSM_DONE;
                end
            end

            FSM_DONE: begin
                fsm_state <= FSM_IDLE;
            end

            default: begin
                fsm_state <= FSM_IDLE;
            end
        endcase
    end
end
// STAGE5_SUBTASK_END B4_seq_control

// STAGE5_SUBTASK_BEGIN B5_final_output: Registered output block: on posedge clk, load text_out from the final state_matrix (after FinalRound) and assert done wh
always @(posedge clk) begin
    if (rst) begin
        text_out <= 128'd0;
        done     <= 1'b0;
    end else if (fsm_state == FSM_DONE) begin
        text_out <= state_matrix;
        done     <= 1'b1;
    end else begin
        done     <= 1'b0;
    end
end
// STAGE5_SUBTASK_END B5_final_output
