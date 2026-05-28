module aes_cipher_top (
    input  wire        clk,
    input  wire        rst,
    input  wire        ld,
    output wire        done,
    input  wire [127:0] key,
    input  wire [127:0] text_in,
    output wire [127:0] text_out
);

    localparam IDLE        = 3'd0;
    localparam INIT_ROUND  = 3'd1;
    localparam ROUND_OP    = 3'd2;
    localparam FINAL_ROUND = 3'd3;
    localparam DONE        = 3'd4;

    reg [2:0]  state, next_state;
    reg [3:0]  dcnt;
    reg [7:0]  sa_00, sa_01, sa_02, sa_03;
    reg [7:0]  sa_10, sa_11, sa_12, sa_13;
    reg [7:0]  sa_20, sa_21, sa_22, sa_23;
    reg [7:0]  sa_30, sa_31, sa_32, sa_33;
    reg [127:0] text_out_r;
    reg         ld_cap;
    reg         kld;

    wire [31:0] wo_0, wo_1, wo_2, wo_3;

    wire [7:0]  sbox_00, sbox_01, sbox_02, sbox_03;
    wire [7:0]  sbox_10, sbox_11, sbox_12, sbox_13;
    wire [7:0]  sbox_20, sbox_21, sbox_22, sbox_23;
    wire [7:0]  sbox_30, sbox_31, sbox_32, sbox_33;

    wire [7:0]  sr_00, sr_01, sr_02, sr_03;
    wire [7:0]  sr_10, sr_11, sr_12, sr_13;
    wire [7:0]  sr_20, sr_21, sr_22, sr_23;
    wire [7:0]  sr_30, sr_31, sr_32, sr_33;

    wire [7:0]  mc_00, mc_01, mc_02, mc_03;
    wire [7:0]  mc_10, mc_11, mc_12, mc_13;
    wire [7:0]  mc_20, mc_21, mc_22, mc_23;
    wire [7:0]  mc_30, mc_31, mc_32, mc_33;

    wire [127:0] round_key;
    wire [127:0] sbox_out_flat;
    wire [127:0] shifted_state;
    wire [127:0] mixcol_out;
    wire [127:0] add_rkey_out;
    wire        bypass_mix;
    wire [127:0] round_data;

    // ---- ld capture at negedge ----
    always @(negedge clk) begin
        if (!rst)
            ld_cap <= 1'b0;
        else if (ld)
            ld_cap <= 1'b1;
    end

    // ---- Key expansion ----
    aes_key_expand_128 u_key_expand (
        .clk (clk), .kld (kld), .key (key),
        .wo_0(wo_0), .wo_1(wo_1), .wo_2(wo_2), .wo_3(wo_3)
    );

    assign round_key = {wo_0, wo_1, wo_2, wo_3};

    // ---- S-boxes ----
    aes_sbox u_sbox_00 (.a(sa_00), .b(sbox_00));
    aes_sbox u_sbox_10 (.a(sa_10), .b(sbox_10));
    aes_sbox u_sbox_20 (.a(sa_20), .b(sbox_20));
    aes_sbox u_sbox_30 (.a(sa_30), .b(sbox_30));
    aes_sbox u_sbox_01 (.a(sa_01), .b(sbox_01));
    aes_sbox u_sbox_11 (.a(sa_11), .b(sbox_11));
    aes_sbox u_sbox_21 (.a(sa_21), .b(sbox_21));
    aes_sbox u_sbox_31 (.a(sa_31), .b(sbox_31));
    aes_sbox u_sbox_02 (.a(sa_02), .b(sbox_02));
    aes_sbox u_sbox_12 (.a(sa_12), .b(sbox_12));
    aes_sbox u_sbox_22 (.a(sa_22), .b(sbox_22));
    aes_sbox u_sbox_32 (.a(sa_32), .b(sbox_32));
    aes_sbox u_sbox_03 (.a(sa_03), .b(sbox_03));
    aes_sbox u_sbox_13 (.a(sa_13), .b(sbox_13));
    aes_sbox u_sbox_23 (.a(sa_23), .b(sbox_23));
    aes_sbox u_sbox_33 (.a(sa_33), .b(sbox_33));

    assign sbox_out_flat = {
        sbox_03, sbox_13, sbox_23, sbox_33,
        sbox_02, sbox_12, sbox_22, sbox_32,
        sbox_01, sbox_11, sbox_21, sbox_31,
        sbox_00, sbox_10, sbox_20, sbox_30
    };

    // ---- ShiftRows ----
    assign sr_00 = sbox_00;  assign sr_01 = sbox_01;  assign sr_02 = sbox_02;  assign sr_03 = sbox_03;
    assign sr_10 = sbox_11;  assign sr_11 = sbox_12;  assign sr_12 = sbox_13;  assign sr_13 = sbox_10;
    assign sr_20 = sbox_22;  assign sr_21 = sbox_23;  assign sr_22 = sbox_20;  assign sr_23 = sbox_21;
    assign sr_30 = sbox_33;  assign sr_31 = sbox_30;  assign sr_32 = sbox_31;  assign sr_33 = sbox_32;

    assign shifted_state = {
        sr_03, sr_13, sr_23, sr_33,
        sr_02, sr_12, sr_22, sr_32,
        sr_01, sr_11, sr_21, sr_31,
        sr_00, sr_10, sr_20, sr_30
    };

    // ---- xtime ----
    function [7:0] xtime(input [7:0] x);
        xtime = (x[7] ? 8'h1b : 8'h00) ^ (x << 1);
    endfunction

    // ---- MixColumns ----
    assign mc_00 = xtime(sr_00) ^ (xtime(sr_10) ^ sr_10) ^ sr_20 ^ sr_30;
    assign mc_10 = sr_00 ^ xtime(sr_10) ^ (xtime(sr_20) ^ sr_20) ^ sr_30;
    assign mc_20 = sr_00 ^ sr_10 ^ xtime(sr_20) ^ (xtime(sr_30) ^ sr_30);
    assign mc_30 = (xtime(sr_00) ^ sr_00) ^ sr_10 ^ sr_20 ^ xtime(sr_30);

    assign mc_01 = xtime(sr_01) ^ (xtime(sr_11) ^ sr_11) ^ sr_21 ^ sr_31;
    assign mc_11 = sr_01 ^ xtime(sr_11) ^ (xtime(sr_21) ^ sr_21) ^ sr_31;
    assign mc_21 = sr_01 ^ sr_11 ^ xtime(sr_21) ^ (xtime(sr_31) ^ sr_31);
    assign mc_31 = (xtime(sr_01) ^ sr_01) ^ sr_11 ^ sr_21 ^ xtime(sr_31);

    assign mc_02 = xtime(sr_02) ^ (xtime(sr_12) ^ sr_12) ^ sr_22 ^ sr_32;
    assign mc_12 = sr_02 ^ xtime(sr_12) ^ (xtime(sr_22) ^ sr_22) ^ sr_32;
    assign mc_22 = sr_02 ^ sr_12 ^ xtime(sr_22) ^ (xtime(sr_32) ^ sr_32);
    assign mc_32 = (xtime(sr_02) ^ sr_02) ^ sr_12 ^ sr_22 ^ xtime(sr_32);

    assign mc_03 = xtime(sr_03) ^ (xtime(sr_13) ^ sr_13) ^ sr_23 ^ sr_33;
    assign mc_13 = sr_03 ^ xtime(sr_13) ^ (xtime(sr_23) ^ sr_23) ^ sr_33;
    assign mc_23 = sr_03 ^ sr_13 ^ xtime(sr_23) ^ (xtime(sr_33) ^ sr_33);
    assign mc_33 = (xtime(sr_03) ^ sr_03) ^ sr_13 ^ sr_23 ^ xtime(sr_33);

    assign mixcol_out = {
        mc_03, mc_13, mc_23, mc_33,
        mc_02, mc_12, mc_22, mc_32,
        mc_01, mc_11, mc_21, mc_31,
        mc_00, mc_10, mc_20, mc_30
    };

    // ---- Data path ----
    assign bypass_mix = (state != ROUND_OP);
    assign round_data = bypass_mix ? shifted_state : mixcol_out;
    assign add_rkey_out = round_data ^ round_key;

    // ---- text_out (registered, same as agent code) ----
    assign text_out = text_out_r;

    // ---- done ----
    assign done = (state == DONE);

    // ---- FSM next-state logic (combinational) ----
    always @(*) begin
        case (state)
            IDLE:        next_state = (ld_cap || kld) ? INIT_ROUND : IDLE;
            INIT_ROUND:  next_state = ROUND_OP;
            ROUND_OP:    next_state = (dcnt == 4'd1) ? FINAL_ROUND : ROUND_OP;
            FINAL_ROUND: next_state = DONE;
            DONE:        next_state = (ld_cap || kld) ? INIT_ROUND : DONE;
            default:     next_state = IDLE;
        endcase
    end

    // ---- FSM sequential logic ----
    always @(posedge clk) begin
        if (!rst) begin
            state     <= IDLE;
            dcnt      <= 4'd0;
            kld       <= 1'b0;
            ld_cap    <= 1'b0;
            text_out_r <= 128'd0;
            sa_00 <= 8'd0; sa_01 <= 8'd0; sa_02 <= 8'd0; sa_03 <= 8'd0;
            sa_10 <= 8'd0; sa_11 <= 8'd0; sa_12 <= 8'd0; sa_13 <= 8'd0;
            sa_20 <= 8'd0; sa_21 <= 8'd0; sa_22 <= 8'd0; sa_23 <= 8'd0;
            sa_30 <= 8'd0; sa_31 <= 8'd0; sa_32 <= 8'd0; sa_33 <= 8'd0;
        end else begin
            state <= next_state;

            // kld management
            if (state == IDLE && ld_cap && !kld) begin
                kld    <= 1'b1;
                ld_cap <= 1'b0;
            end else if (state == DONE && ld_cap && !kld) begin
                kld    <= 1'b1;
                ld_cap <= 1'b0;
            end else if (kld && (next_state == INIT_ROUND)) begin
                kld <= 1'b0;
            end

            // Data path (using next_state for timing matching)
            if (next_state == INIT_ROUND) begin
                // Initial AddRoundKey
                dcnt   <= 4'd10;
                sa_00 <= text_in[127:120] ^ wo_0[31:24];
                sa_10 <= text_in[119:112] ^ wo_0[23:16];
                sa_20 <= text_in[111:104] ^ wo_0[15:8];
                sa_30 <= text_in[103:96]  ^ wo_0[7:0];
                sa_01 <= text_in[95:88]   ^ wo_1[31:24];
                sa_11 <= text_in[87:80]   ^ wo_1[23:16];
                sa_21 <= text_in[79:72]   ^ wo_1[15:8];
                sa_31 <= text_in[71:64]   ^ wo_1[7:0];
                sa_02 <= text_in[63:56]   ^ wo_2[31:24];
                sa_12 <= text_in[55:48]   ^ wo_2[23:16];
                sa_22 <= text_in[47:40]   ^ wo_2[15:8];
                sa_32 <= text_in[39:32]   ^ wo_2[7:0];
                sa_03 <= text_in[31:24]   ^ wo_3[31:24];
                sa_13 <= text_in[23:16]   ^ wo_3[23:16];
                sa_23 <= text_in[15:8]    ^ wo_3[15:8];
                sa_33 <= text_in[7:0]     ^ wo_3[7:0];
            end else if ((next_state == ROUND_OP) || (next_state == FINAL_ROUND)) begin
                dcnt   <= dcnt - 4'd1;
                sa_00 <= add_rkey_out[127:120];
                sa_10 <= add_rkey_out[119:112];
                sa_20 <= add_rkey_out[111:104];
                sa_30 <= add_rkey_out[103:96];
                sa_01 <= add_rkey_out[95:88];
                sa_11 <= add_rkey_out[87:80];
                sa_21 <= add_rkey_out[79:72];
                sa_31 <= add_rkey_out[71:64];
                sa_02 <= add_rkey_out[63:56];
                sa_12 <= add_rkey_out[55:48];
                sa_22 <= add_rkey_out[47:40];
                sa_32 <= add_rkey_out[39:32];
                sa_03 <= add_rkey_out[31:24];
                sa_13 <= add_rkey_out[23:16];
                sa_23 <= add_rkey_out[15:8];
                sa_33 <= add_rkey_out[7:0];
            end

            // text_out capture (same timing as agent code)
            if (next_state == FINAL_ROUND)
                text_out_r <= add_rkey_out;
        end
    end

endmodule
