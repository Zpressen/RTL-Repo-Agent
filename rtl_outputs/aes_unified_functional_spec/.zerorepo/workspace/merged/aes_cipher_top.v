module aes_cipher_top (
    clk,
    rst,
    ld,
    done,
    key,
    text_in,
    text_out
);
    input clk;
    input rst;
    input ld;
    input [127:0] key;
    input [127:0] text_in;
    output done;
    output [127:0] text_out;

    // FSM state encoding
    localparam AES_ST_IDLE        = 3'd0;
    localparam AES_ST_INIT_ROUND  = 3'd1;
    localparam AES_ST_ROUND_OP    = 3'd2;
    localparam AES_ST_FINAL_ROUND = 3'd3;
    localparam AES_ST_DONE        = 3'd4;

    // Registers
    reg [127:0] text_in_r;
    reg [3:0] dcnt;
    reg ld_r;
    reg [127:0] text_out;
    reg [127:0] key_reg;
    reg [2:0] aes_state;
    reg [2:0] aes_state_next;
    reg [3:0] dcnt_next_mux;

    reg [7:0] sa_00;
    reg [7:0] sa_01;
    reg [7:0] sa_02;
    reg [7:0] sa_03;
    reg [7:0] sa_10;
    reg [7:0] sa_11;
    reg [7:0] sa_12;
    reg [7:0] sa_13;
    reg [7:0] sa_20;
    reg [7:0] sa_21;
    reg [7:0] sa_22;
    reg [7:0] sa_23;
    reg [7:0] sa_30;
    reg [7:0] sa_31;
    reg [7:0] sa_32;
    reg [7:0] sa_33;

    // Combinational datapath buses
    wire [127:0] state_bus;
    wire [127:0] sbox_bus;
    wire [127:0] shiftrows_bus;
    wire [127:0] mixcolumns_bus;
    wire [127:0] round_key_bus;
    wire [127:0] addroundkey_bus;
    wire [127:0] round_data_bus;
    wire [127:0] final_data_bus;
    wire [127:0] sa_next_bus;
    wire [127:0] text_in_r_next;
    wire [127:0] text_out_next;

    // SubBytes byte outputs
    wire [7:0] sbox_00;
    wire [7:0] sbox_10;
    wire [7:0] sbox_20;
    wire [7:0] sbox_30;
    wire [7:0] sbox_01;
    wire [7:0] sbox_11;
    wire [7:0] sbox_21;
    wire [7:0] sbox_31;
    wire [7:0] sbox_02;
    wire [7:0] sbox_12;
    wire [7:0] sbox_22;
    wire [7:0] sbox_32;
    wire [7:0] sbox_03;
    wire [7:0] sbox_13;
    wire [7:0] sbox_23;
    wire [7:0] sbox_33;

    // Round key word outputs from key expansion
    wire [31:0] wo_0;
    wire [31:0] wo_1;
    wire [31:0] wo_2;
    wire [31:0] wo_3;

    // Control signals
    wire kld;
    wire load_cycle;
    wire round_cycle;
    wire final_cycle;
    wire done_cycle;
    wire cipher_done;
    wire cipher_busy;
    wire dcnt_is_zero;
    wire dcnt_is_initial;
    wire dcnt_is_final;
    wire mixcolumns_bypass;

    // ShiftRows output bytes (unpacked from shiftrows_bus)
    wire [7:0] sr_00;
    wire [7:0] sr_10;
    wire [7:0] sr_20;
    wire [7:0] sr_30;
    wire [7:0] sr_01;
    wire [7:0] sr_11;
    wire [7:0] sr_21;
    wire [7:0] sr_31;
    wire [7:0] sr_02;
    wire [7:0] sr_12;
    wire [7:0] sr_22;
    wire [7:0] sr_32;
    wire [7:0] sr_03;
    wire [7:0] sr_13;
    wire [7:0] sr_23;
    wire [7:0] sr_33;

    // MixColumns multiplication by 02 partial products
    wire [7:0] mc2_00;
    wire [7:0] mc2_10;
    wire [7:0] mc2_20;
    wire [7:0] mc2_30;
    wire [7:0] mc2_01;
    wire [7:0] mc2_11;
    wire [7:0] mc2_21;
    wire [7:0] mc2_31;
    wire [7:0] mc2_02;
    wire [7:0] mc2_12;
    wire [7:0] mc2_22;
    wire [7:0] mc2_32;
    wire [7:0] mc2_03;
    wire [7:0] mc2_13;
    wire [7:0] mc2_23;
    wire [7:0] mc2_33;

    // MixColumns multiplication by 03 partial products
    wire [7:0] mc3_00;
    wire [7:0] mc3_10;
    wire [7:0] mc3_20;
    wire [7:0] mc3_30;
    wire [7:0] mc3_01;
    wire [7:0] mc3_11;
    wire [7:0] mc3_21;
    wire [7:0] mc3_31;
    wire [7:0] mc3_02;
    wire [7:0] mc3_12;
    wire [7:0] mc3_22;
    wire [7:0] mc3_32;
    wire [7:0] mc3_03;
    wire [7:0] mc3_13;
    wire [7:0] mc3_23;
    wire [7:0] mc3_33;

    // MixColumns result bytes
    wire [7:0] mc_00;
    wire [7:0] mc_10;
    wire [7:0] mc_20;
    wire [7:0] mc_30;
    wire [7:0] mc_01;
    wire [7:0] mc_11;
    wire [7:0] mc_21;
    wire [7:0] mc_31;
    wire [7:0] mc_02;
    wire [7:0] mc_12;
    wire [7:0] mc_22;
    wire [7:0] mc_32;
    wire [7:0] mc_03;
    wire [7:0] mc_13;
    wire [7:0] mc_23;
    wire [7:0] mc_33;

    // GF(2^8) multiply by 02 using AES reduction polynomial
    function [7:0] aes_xtime;
        input [7:0] xtime_in;
        reg [7:0] xtime_shifted;
        begin
            xtime_shifted = {xtime_in[6:0], 1'b0};
            if (xtime_in[7] == 1'b1)
                aes_xtime = xtime_shifted ^ 8'h1b;
            else
                aes_xtime = xtime_shifted;
        end
    endfunction

    // AES-128 round key expansion
    aes_key_expand_128 u_key_expand_128 (
        .clk(clk),
        .kld(kld),
        .key(key),
        .wo_0(wo_0),
        .wo_1(wo_1),
        .wo_2(wo_2),
        .wo_3(wo_3)
    );

    // Sixteen S-box instances for the 4x4 state matrix
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

    // Packed SubBytes result in column-major order
    assign sbox_bus = {sbox_00, sbox_10, sbox_20, sbox_30,
                        sbox_01, sbox_11, sbox_21, sbox_31,
                        sbox_02, sbox_12, sbox_22, sbox_32,
                        sbox_03, sbox_13, sbox_23, sbox_33};

    // ShiftRows applied after SubBytes, preserving column-major order
    assign shiftrows_bus = {sbox_00, sbox_11, sbox_22, sbox_33,
                            sbox_01, sbox_12, sbox_23, sbox_30,
                            sbox_02, sbox_13, sbox_20, sbox_31,
                            sbox_03, sbox_10, sbox_21, sbox_32};

    // Unpack shiftrows_bus into individual byte wires for MixColumns
    assign sr_00 = shiftrows_bus[127:120];
    assign sr_10 = shiftrows_bus[119:112];
    assign sr_20 = shiftrows_bus[111:104];
    assign sr_30 = shiftrows_bus[103:96];
    assign sr_01 = shiftrows_bus[95:88];
    assign sr_11 = shiftrows_bus[87:80];
    assign sr_21 = shiftrows_bus[79:72];
    assign sr_31 = shiftrows_bus[71:64];
    assign sr_02 = shiftrows_bus[63:56];
    assign sr_12 = shiftrows_bus[55:48];
    assign sr_22 = shiftrows_bus[47:40];
    assign sr_32 = shiftrows_bus[39:32];
    assign sr_03 = shiftrows_bus[31:24];
    assign sr_13 = shiftrows_bus[23:16];
    assign sr_23 = shiftrows_bus[15:8];
    assign sr_33 = shiftrows_bus[7:0];

    // Multiply-by-02 for all state bytes
    assign mc2_00 = aes_xtime(sr_00);
    assign mc2_10 = aes_xtime(sr_10);
    assign mc2_20 = aes_xtime(sr_20);
    assign mc2_30 = aes_xtime(sr_30);
    assign mc2_01 = aes_xtime(sr_01);
    assign mc2_11 = aes_xtime(sr_11);
    assign mc2_21 = aes_xtime(sr_21);
    assign mc2_31 = aes_xtime(sr_31);
    assign mc2_02 = aes_xtime(sr_02);
    assign mc2_12 = aes_xtime(sr_12);
    assign mc2_22 = aes_xtime(sr_22);
    assign mc2_32 = aes_xtime(sr_32);
    assign mc2_03 = aes_xtime(sr_03);
    assign mc2_13 = aes_xtime(sr_13);
    assign mc2_23 = aes_xtime(sr_23);
    assign mc2_33 = aes_xtime(sr_33);

    // Multiply-by-03 = (02 * byte) XOR original byte
    assign mc3_00 = mc2_00 ^ sr_00;
    assign mc3_10 = mc2_10 ^ sr_10;
    assign mc3_20 = mc2_20 ^ sr_20;
    assign mc3_30 = mc2_30 ^ sr_30;
    assign mc3_01 = mc2_01 ^ sr_01;
    assign mc3_11 = mc2_11 ^ sr_11;
    assign mc3_21 = mc2_21 ^ sr_21;
    assign mc3_31 = mc2_31 ^ sr_31;
    assign mc3_02 = mc2_02 ^ sr_02;
    assign mc3_12 = mc2_12 ^ sr_12;
    assign mc3_22 = mc2_22 ^ sr_22;
    assign mc3_32 = mc2_32 ^ sr_32;
    assign mc3_03 = mc2_03 ^ sr_03;
    assign mc3_13 = mc2_13 ^ sr_13;
    assign mc3_23 = mc2_23 ^ sr_23;
    assign mc3_33 = mc2_33 ^ sr_33;

    // MixColumns transformation for each of the four columns
    assign mc_00 = mc2_00 ^ mc3_10 ^ sr_20 ^ sr_30;
    assign mc_10 = sr_00 ^ mc2_10 ^ mc3_20 ^ sr_30;
    assign mc_20 = sr_00 ^ sr_10 ^ mc2_20 ^ mc3_30;
    assign mc_30 = mc3_00 ^ sr_10 ^ sr_20 ^ mc2_30;

    assign mc_01 = mc2_01 ^ mc3_11 ^ sr_21 ^ sr_31;
    assign mc_11 = sr_01 ^ mc2_11 ^ mc3_21 ^ sr_31;
    assign mc_21 = sr_01 ^ sr_11 ^ mc2_21 ^ mc3_31;
    assign mc_31 = mc3_01 ^ sr_11 ^ sr_21 ^ mc2_31;

    assign mc_02 = mc2_02 ^ mc3_12 ^ sr_22 ^ sr_32;
    assign mc_12 = sr_02 ^ mc2_12 ^ mc3_22 ^ sr_32;
    assign mc_22 = sr_02 ^ sr_12 ^ mc2_22 ^ mc3_32;
    assign mc_32 = mc3_02 ^ sr_12 ^ sr_22 ^ mc2_32;

    assign mc_03 = mc2_03 ^ mc3_13 ^ sr_23 ^ sr_33;
    assign mc_13 = sr_03 ^ mc2_13 ^ mc3_23 ^ sr_33;
    assign mc_23 = sr_03 ^ sr_13 ^ mc2_23 ^ mc3_33;
    assign mc_33 = mc3_03 ^ sr_13 ^ sr_23 ^ mc2_33;

    // Packed MixColumns result
    assign mixcolumns_bus = {mc_00, mc_10, mc_20, mc_30,
                              mc_01, mc_11, mc_21, mc_31,
                              mc_02, mc_12, mc_22, mc_32,
                              mc_03, mc_13, mc_23, mc_33};

    // Current round key bus (column-major)
    assign round_key_bus = {wo_0, wo_1, wo_2, wo_3};

    // State feedback uses regular-round data; text_out exposes the final-round datapath.
    assign round_data_bus = mixcolumns_bus;

    // AddRoundKey
    assign addroundkey_bus = round_data_bus ^ round_key_bus;

    // Datapath output for register commitment
    assign final_data_bus = shiftrows_bus ^ round_key_bus;
    assign sa_next_bus = addroundkey_bus;

    // Control signals
    assign load_cycle  = (aes_state == AES_ST_INIT_ROUND);
    assign round_cycle = (aes_state == AES_ST_ROUND_OP);
    assign final_cycle = (aes_state == AES_ST_FINAL_ROUND);
    assign done_cycle  = (aes_state == AES_ST_DONE);
    assign cipher_done = done_cycle;
    assign cipher_busy = (aes_state == AES_ST_INIT_ROUND) |
                         (aes_state == AES_ST_ROUND_OP)   |
                         (aes_state == AES_ST_FINAL_ROUND);
    assign dcnt_is_zero    = (dcnt == 4'h0);
    assign dcnt_is_initial = (dcnt == 4'hB);
    assign dcnt_is_final   = (dcnt == 4'h1);
    assign mixcolumns_bypass = final_cycle;

    assign kld = (((aes_state == AES_ST_IDLE) | (aes_state == AES_ST_DONE)) & ld);

    assign done = cipher_done;

    // FSM state register (asynchronous reset)
    always @(posedge clk or posedge rst) begin
        if (rst == 1'b1)
            aes_state <= AES_ST_IDLE;
        else
            aes_state <= aes_state_next;
    end

    // FSM next-state and round-counter sequencing
    always @(aes_state or ld or dcnt) begin
        aes_state_next = aes_state;
        dcnt_next_mux = dcnt;
        case (aes_state)
            AES_ST_IDLE: begin
                dcnt_next_mux = 4'h0;
                if (ld == 1'b1) begin
                    aes_state_next = AES_ST_INIT_ROUND;
                    dcnt_next_mux = 4'hB;
                end
            end
            AES_ST_INIT_ROUND: begin
                aes_state_next = AES_ST_ROUND_OP;
                dcnt_next_mux = 4'hA;
            end
            AES_ST_ROUND_OP: begin
                if (dcnt > 4'h0)
                    dcnt_next_mux = dcnt - 4'h1;
                else
                    dcnt_next_mux = 4'h0;
                if (dcnt == 4'h2)
                    aes_state_next = AES_ST_FINAL_ROUND;
                else
                    aes_state_next = AES_ST_ROUND_OP;
            end
            AES_ST_FINAL_ROUND: begin
                aes_state_next = AES_ST_DONE;
                if (dcnt > 4'h0)
                    dcnt_next_mux = dcnt - 4'h1;
                else
                    dcnt_next_mux = 4'h0;
            end
            AES_ST_DONE: begin
                dcnt_next_mux = 4'h0;
                if (ld == 1'b1) begin
                    aes_state_next = AES_ST_INIT_ROUND;
                    dcnt_next_mux = 4'hB;
                end else begin
                    aes_state_next = AES_ST_DONE;
                end
            end
            default: begin
                aes_state_next = AES_ST_IDLE;
                dcnt_next_mux = 4'h0;
            end
        endcase
    end

    assign text_in_r_next = load_cycle ? text_in : text_in_r;
    assign text_out_next  = {sa_00, sa_10, sa_20, sa_30,
                             sa_01, sa_11, sa_21, sa_31,
                             sa_02, sa_12, sa_22, sa_32,
                             sa_03, sa_13, sa_23, sa_33};

    // Central register commit (synchronous with synchronous reset)
    always @(posedge clk) begin
        ld_r      <= ld;
        dcnt      <= dcnt_next_mux;
        text_in_r <= text_in_r_next;

        if (kld)
            key_reg <= key;
        else
            key_reg <= key_reg;

        if (ld == 1'b1) begin
            text_out <= text_in ^ round_key_bus;
            sa_00 <= text_in[127:120] ^ round_key_bus[127:120];
            sa_10 <= text_in[119:112] ^ round_key_bus[119:112];
            sa_20 <= text_in[111:104] ^ round_key_bus[111:104];
            sa_30 <= text_in[103:96]  ^ round_key_bus[103:96];
            sa_01 <= text_in[95:88]   ^ round_key_bus[95:88];
            sa_11 <= text_in[87:80]   ^ round_key_bus[87:80];
            sa_21 <= text_in[79:72]   ^ round_key_bus[79:72];
            sa_31 <= text_in[71:64]   ^ round_key_bus[71:64];
            sa_02 <= text_in[63:56]   ^ round_key_bus[63:56];
            sa_12 <= text_in[55:48]   ^ round_key_bus[55:48];
            sa_22 <= text_in[47:40]   ^ round_key_bus[47:40];
            sa_32 <= text_in[39:32]   ^ round_key_bus[39:32];
            sa_03 <= text_in[31:24]   ^ round_key_bus[31:24];
            sa_13 <= text_in[23:16]   ^ round_key_bus[23:16];
            sa_23 <= text_in[15:8]    ^ round_key_bus[15:8];
            sa_33 <= text_in[7:0]     ^ round_key_bus[7:0];
        end else begin
            text_out <= final_data_bus;
            sa_00 <= sa_next_bus[127:120];
            sa_10 <= sa_next_bus[119:112];
            sa_20 <= sa_next_bus[111:104];
            sa_30 <= sa_next_bus[103:96];
            sa_01 <= sa_next_bus[95:88];
            sa_11 <= sa_next_bus[87:80];
            sa_21 <= sa_next_bus[79:72];
            sa_31 <= sa_next_bus[71:64];
            sa_02 <= sa_next_bus[63:56];
            sa_12 <= sa_next_bus[55:48];
            sa_22 <= sa_next_bus[47:40];
            sa_32 <= sa_next_bus[39:32];
            sa_03 <= sa_next_bus[31:24];
            sa_13 <= sa_next_bus[23:16];
            sa_23 <= sa_next_bus[15:8];
            sa_33 <= sa_next_bus[7:0];
        end
    end

endmodule
