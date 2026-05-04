`timescale 1ns / 1ps

module aes_cipher_top (
    input  wire         clk,
    input  wire         rst,
    input  wire         ld,
    output reg          done,
    input  wire [127:0] key,
    input  wire [127:0] text_in,
    output reg  [127:0] text_out
);
    localparam [2:0] ST_IDLE        = 3'd0;
    localparam [2:0] ST_INIT_ROUND  = 3'd1;
    localparam [2:0] ST_ROUND_OP    = 3'd2;
    localparam [2:0] ST_FINAL_ROUND = 3'd3;
    localparam [2:0] ST_DONE        = 3'd4;

    reg [2:0]   state;
    reg [127:0] text_in_r;
    reg [127:0] state_reg;
    reg [3:0]   dcnt;
    reg         ld_r;
    wire        load_pulse;

    wire [31:0] round_w0;
    wire [31:0] round_w1;
    wire [31:0] round_w2;
    wire [31:0] round_w3;
    wire [127:0] round_key;

    wire [127:0] subbytes_state;
    wire [127:0] shiftrows_state;
    wire [127:0] mixcolumns_state;
    wire [127:0] standard_round_state;
    wire [127:0] final_round_state;

    genvar gi;

    assign load_pulse = ld & ~ld_r;

    aes_key_expand_128 u_key_expand (
        .clk(clk),
        .kld(load_pulse),
        .key(key),
        .wo_0(round_w0),
        .wo_1(round_w1),
        .wo_2(round_w2),
        .wo_3(round_w3)
    );

    assign round_key = {round_w0, round_w1, round_w2, round_w3};

    generate
        for (gi = 0; gi < 16; gi = gi + 1) begin : gen_state_sbox
            aes_sbox u_sbox (
                .a(state_reg[127 - (gi * 8) -: 8]),
                .b(subbytes_state[127 - (gi * 8) -: 8])
            );
        end
    endgenerate

    assign shiftrows_state      = shiftrows(subbytes_state);
    assign mixcolumns_state     = mixcolumns(shiftrows_state);
    assign standard_round_state = mixcolumns_state ^ round_key;
    assign final_round_state    = shiftrows_state ^ round_key;

    function [7:0] xtime;
        input [7:0] a;
        begin
            xtime = {a[6:0], 1'b0} ^ (8'h1b & {8{a[7]}});
        end
    endfunction

    function [31:0] mix_single_column;
        input [31:0] col;
        reg [7:0] s0;
        reg [7:0] s1;
        reg [7:0] s2;
        reg [7:0] s3;
        begin
            s0 = col[31:24];
            s1 = col[23:16];
            s2 = col[15:8];
            s3 = col[7:0];

            mix_single_column[31:24] = xtime(s0) ^ (xtime(s1) ^ s1) ^ s2 ^ s3;
            mix_single_column[23:16] = s0 ^ xtime(s1) ^ (xtime(s2) ^ s2) ^ s3;
            mix_single_column[15:8]  = s0 ^ s1 ^ xtime(s2) ^ (xtime(s3) ^ s3);
            mix_single_column[7:0]   = (xtime(s0) ^ s0) ^ s1 ^ s2 ^ xtime(s3);
        end
    endfunction

    function [127:0] shiftrows;
        input [127:0] state_in;
        reg [7:0] s00;
        reg [7:0] s10;
        reg [7:0] s20;
        reg [7:0] s30;
        reg [7:0] s01;
        reg [7:0] s11;
        reg [7:0] s21;
        reg [7:0] s31;
        reg [7:0] s02;
        reg [7:0] s12;
        reg [7:0] s22;
        reg [7:0] s32;
        reg [7:0] s03;
        reg [7:0] s13;
        reg [7:0] s23;
        reg [7:0] s33;
        begin
            s00 = state_in[127:120];
            s10 = state_in[119:112];
            s20 = state_in[111:104];
            s30 = state_in[103:96];
            s01 = state_in[95:88];
            s11 = state_in[87:80];
            s21 = state_in[79:72];
            s31 = state_in[71:64];
            s02 = state_in[63:56];
            s12 = state_in[55:48];
            s22 = state_in[47:40];
            s32 = state_in[39:32];
            s03 = state_in[31:24];
            s13 = state_in[23:16];
            s23 = state_in[15:8];
            s33 = state_in[7:0];

            shiftrows = {
                s00, s11, s22, s33,
                s01, s12, s23, s30,
                s02, s13, s20, s31,
                s03, s10, s21, s32
            };
        end
    endfunction

    function [127:0] mixcolumns;
        input [127:0] state_in;
        begin
            mixcolumns = {
                mix_single_column(state_in[127:96]),
                mix_single_column(state_in[95:64]),
                mix_single_column(state_in[63:32]),
                mix_single_column(state_in[31:0])
            };
        end
    endfunction

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            state    <= ST_IDLE;
            text_in_r <= 128'd0;
            state_reg <= 128'd0;
            text_out <= 128'd0;
            dcnt     <= 4'd0;
            ld_r     <= 1'b0;
            done     <= 1'b0;
        end else begin
            ld_r <= ld;
            if (load_pulse) begin
            state    <= ST_INIT_ROUND;
            text_in_r <= text_in;
            state_reg <= text_in ^ key;
            text_out <= 128'd0;
            dcnt     <= 4'hb;
            done     <= 1'b0;
            end else begin
                case (state)
                    ST_IDLE: begin
                        done <= 1'b0;
                    end

                    ST_INIT_ROUND: begin
                        state_reg <= standard_round_state;
                        dcnt      <= dcnt - 4'd1;
                        state     <= ST_ROUND_OP;
                        done      <= 1'b0;
                    end

                    ST_ROUND_OP: begin
                        state_reg <= standard_round_state;
                        dcnt      <= dcnt - 4'd1;
                        done      <= 1'b0;
                        if (dcnt == 4'd3) begin
                            state <= ST_FINAL_ROUND;
                        end
                    end

                    ST_FINAL_ROUND: begin
                        state_reg <= final_round_state;
                        text_out  <= final_round_state;
                        dcnt      <= dcnt - 4'd1;
                        state     <= ST_DONE;
                        done      <= 1'b1;
                    end

                    ST_DONE: begin
                        done <= 1'b1;
                    end

                    default: begin
                        state <= ST_IDLE;
                        done  <= 1'b0;
                    end
                endcase
            end
        end
    end
endmodule
