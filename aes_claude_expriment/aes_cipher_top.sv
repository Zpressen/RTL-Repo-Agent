module aes_cipher_top (
    input           clk,
    input           rst,
    input           ld,
    output reg      done,
    input  [127:0]  key,
    input  [127:0]  text_in,
    output [127:0]  text_out
);

    localparam IDLE        = 3'd0;
    localparam INIT_ROUND  = 3'd1;
    localparam ROUND_OP    = 3'd2;
    localparam FINAL_ROUND = 3'd3;
    localparam DONE_STATE  = 3'd4;

    reg [2:0]  state;
    reg [3:0]  dcnt;
    reg [127:0] text_in_r;
    reg [7:0]  sa [0:3][0:3];

    reg         kld;
    wire [31:0] wo_0, wo_1, wo_2, wo_3;

    // ld captured at negedge to avoid race with stimulus de-assertion
    reg         ld_cap;

    wire [7:0]  sbox_out [0:3][0:3];
    reg  [7:0]  sr [0:3][0:3];
    wire [7:0]  mc [0:3][0:3];

    // ---- text_out: column-major ordering ----
    assign text_out = {
        sa[0][0], sa[1][0], sa[2][0], sa[3][0],
        sa[0][1], sa[1][1], sa[2][1], sa[3][1],
        sa[0][2], sa[1][2], sa[2][2], sa[3][2],
        sa[0][3], sa[1][3], sa[2][3], sa[3][3]
    };

    // ---- Capture ld at negedge ----
    always @(negedge clk) begin
        if (!rst)
            ld_cap <= 1'b0;
        else if (ld)
            ld_cap <= 1'b1;
    end

    // ---- Key expansion instance ----
    aes_key_expand_128 u_key_expand (
        .clk (clk),
        .kld (kld),
        .key (key),
        .wo_0(wo_0),
        .wo_1(wo_1),
        .wo_2(wo_2),
        .wo_3(wo_3)
    );

    // ---- 16 S-box instances ----
    genvar gi, gj;
    generate
        for (gi = 0; gi < 4; gi = gi + 1) begin : sbox_row
            for (gj = 0; gj < 4; gj = gj + 1) begin : sbox_col
                aes_sbox u_sbox (
                    .a(sa[gi][gj]),
                    .b(sbox_out[gi][gj])
                );
            end
        end
    endgenerate

    function [7:0] xtime(input [7:0] x);
        xtime = (x[7] ? 8'h1b : 8'h00) ^ (x << 1);
    endfunction

    // ---- MixColumns per column ----
    genvar gc;
    generate
        for (gc = 0; gc < 4; gc = gc + 1) begin : mixcol
            assign mc[0][gc] = xtime(sr[0][gc]) ^ (xtime(sr[1][gc]) ^ sr[1][gc]) ^ sr[2][gc] ^ sr[3][gc];
            assign mc[1][gc] = sr[0][gc] ^ xtime(sr[1][gc]) ^ (xtime(sr[2][gc]) ^ sr[2][gc]) ^ sr[3][gc];
            assign mc[2][gc] = sr[0][gc] ^ sr[1][gc] ^ xtime(sr[2][gc]) ^ (xtime(sr[3][gc]) ^ sr[3][gc]);
            assign mc[3][gc] = (xtime(sr[0][gc]) ^ sr[0][gc]) ^ sr[1][gc] ^ sr[2][gc] ^ xtime(sr[3][gc]);
        end
    endgenerate

    // ---- ShiftRows (combinational) ----
    always @(*) begin
        sr[0][0] = sbox_out[0][0];
        sr[0][1] = sbox_out[0][1];
        sr[0][2] = sbox_out[0][2];
        sr[0][3] = sbox_out[0][3];
        sr[1][0] = sbox_out[1][1];
        sr[1][1] = sbox_out[1][2];
        sr[1][2] = sbox_out[1][3];
        sr[1][3] = sbox_out[1][0];
        sr[2][0] = sbox_out[2][2];
        sr[2][1] = sbox_out[2][3];
        sr[2][2] = sbox_out[2][0];
        sr[2][3] = sbox_out[2][1];
        sr[3][0] = sbox_out[3][3];
        sr[3][1] = sbox_out[3][0];
        sr[3][2] = sbox_out[3][1];
        sr[3][3] = sbox_out[3][2];
    end

    // ---- State machine ----
    always @(posedge clk) begin
        if (!rst) begin
            state    <= IDLE;
            dcnt     <= 4'd0;
            done     <= 1'b0;
            kld      <= 1'b0;
            ld_cap   <= 1'b0;
            sa[0][0] <= 8'd0; sa[0][1] <= 8'd0; sa[0][2] <= 8'd0; sa[0][3] <= 8'd0;
            sa[1][0] <= 8'd0; sa[1][1] <= 8'd0; sa[1][2] <= 8'd0; sa[1][3] <= 8'd0;
            sa[2][0] <= 8'd0; sa[2][1] <= 8'd0; sa[2][2] <= 8'd0; sa[2][3] <= 8'd0;
            sa[3][0] <= 8'd0; sa[3][1] <= 8'd0; sa[3][2] <= 8'd0; sa[3][3] <= 8'd0;
        end else begin
            case (state)
                IDLE: begin
                    done <= 1'b0;
                    if (ld_cap && !kld) begin
                        // Phase 1: trigger key load, consume captured ld
                        kld     <= 1'b1;
                        ld_cap  <= 1'b0;
                    end else if (kld) begin
                        // Phase 2: key was loaded last cycle, proceed
                        kld    <= 1'b0;
                        state  <= INIT_ROUND;
                        dcnt   <= 4'd10;
                    end
                end

                INIT_ROUND: begin
                    kld  <= 1'b0;
                    dcnt <= dcnt - 4'd1;
                    $display("[%0t] INIT: text_in=%h key=%h wo={%h,%h,%h,%h}", $time, text_in, key, wo_0, wo_1, wo_2, wo_3);
                    // wo = K0 (loaded 2 cycles ago via kld=1)
                    sa[0][0] <= text_in[127:120] ^ wo_0[31:24];
                    sa[1][0] <= text_in[119:112] ^ wo_0[23:16];
                    sa[2][0] <= text_in[111:104] ^ wo_0[15:8];
                    sa[3][0] <= text_in[103:96]  ^ wo_0[7:0];
                    sa[0][1] <= text_in[95:88]   ^ wo_1[31:24];
                    sa[1][1] <= text_in[87:80]   ^ wo_1[23:16];
                    sa[2][1] <= text_in[79:72]   ^ wo_1[15:8];
                    sa[3][1] <= text_in[71:64]   ^ wo_1[7:0];
                    sa[0][2] <= text_in[63:56]   ^ wo_2[31:24];
                    sa[1][2] <= text_in[55:48]   ^ wo_2[23:16];
                    sa[2][2] <= text_in[47:40]   ^ wo_2[15:8];
                    sa[3][2] <= text_in[39:32]   ^ wo_2[7:0];
                    sa[0][3] <= text_in[31:24]   ^ wo_3[31:24];
                    sa[1][3] <= text_in[23:16]   ^ wo_3[23:16];
                    sa[2][3] <= text_in[15:8]    ^ wo_3[15:8];
                    sa[3][3] <= text_in[7:0]     ^ wo_3[7:0];
                    state <= ROUND_OP;
                end

                ROUND_OP: begin
                    if (dcnt == 4'd1)
                        state <= FINAL_ROUND;
                    dcnt <= dcnt - 4'd1;
                    $display("[%0t] ROUND_OP dcnt=%0d: wo={%h,%h,%h,%h}", $time, dcnt, wo_0, wo_1, wo_2, wo_3);
                    // SubBytes -> ShiftRows -> MixColumns -> AddRoundKey
                    sa[0][0] <= mc[0][0] ^ wo_0[31:24];
                    sa[1][0] <= mc[1][0] ^ wo_0[23:16];
                    sa[2][0] <= mc[2][0] ^ wo_0[15:8];
                    sa[3][0] <= mc[3][0] ^ wo_0[7:0];
                    sa[0][1] <= mc[0][1] ^ wo_1[31:24];
                    sa[1][1] <= mc[1][1] ^ wo_1[23:16];
                    sa[2][1] <= mc[2][1] ^ wo_1[15:8];
                    sa[3][1] <= mc[3][1] ^ wo_1[7:0];
                    sa[0][2] <= mc[0][2] ^ wo_2[31:24];
                    sa[1][2] <= mc[1][2] ^ wo_2[23:16];
                    sa[2][2] <= mc[2][2] ^ wo_2[15:8];
                    sa[3][2] <= mc[3][2] ^ wo_2[7:0];
                    sa[0][3] <= mc[0][3] ^ wo_3[31:24];
                    sa[1][3] <= mc[1][3] ^ wo_3[23:16];
                    sa[2][3] <= mc[2][3] ^ wo_3[15:8];
                    sa[3][3] <= mc[3][3] ^ wo_3[7:0];
                end

                FINAL_ROUND: begin
                    state <= DONE_STATE;
                    dcnt  <= dcnt - 4'd1;
                    // SubBytes -> ShiftRows -> AddRoundKey (no MixColumns)
                    sa[0][0] <= sr[0][0] ^ wo_0[31:24];
                    sa[1][0] <= sr[1][0] ^ wo_0[23:16];
                    sa[2][0] <= sr[2][0] ^ wo_0[15:8];
                    sa[3][0] <= sr[3][0] ^ wo_0[7:0];
                    sa[0][1] <= sr[0][1] ^ wo_1[31:24];
                    sa[1][1] <= sr[1][1] ^ wo_1[23:16];
                    sa[2][1] <= sr[2][1] ^ wo_1[15:8];
                    sa[3][1] <= sr[3][1] ^ wo_1[7:0];
                    sa[0][2] <= sr[0][2] ^ wo_2[31:24];
                    sa[1][2] <= sr[1][2] ^ wo_2[23:16];
                    sa[2][2] <= sr[2][2] ^ wo_2[15:8];
                    sa[3][2] <= sr[3][2] ^ wo_2[7:0];
                    sa[0][3] <= sr[0][3] ^ wo_3[31:24];
                    sa[1][3] <= sr[1][3] ^ wo_3[23:16];
                    sa[2][3] <= sr[2][3] ^ wo_3[15:8];
                    sa[3][3] <= sr[3][3] ^ wo_3[7:0];
                end

                DONE_STATE: begin
                    done <= 1'b1;
                    if (ld_cap && !kld) begin
                        // Phase 1: trigger key load for new encryption
                        kld     <= 1'b1;
                        ld_cap  <= 1'b0;
                        done    <= 1'b0;
                    end else if (kld) begin
                        // Phase 2: key loaded, proceed
                        kld   <= 1'b0;
                        state <= INIT_ROUND;
                        dcnt  <= 4'd10;
                    end
                end

                default: state <= IDLE;
            endcase
        end
    end

    // ---- text_in_r register ----
    always @(posedge clk) begin
        if (!rst)
            text_in_r <= 128'd0;
        else if (ld)
            text_in_r <= text_in;
    end

endmodule
