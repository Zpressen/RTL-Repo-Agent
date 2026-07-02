`include "sd_defines.v"

module sd_bd (
    input  clk,
    input  rst,
    input  we_m,
    input  [RAM_MEM_WIDTH-1:0] dat_in_m,
    output reg [BD_WIDTH-1:0] free_bd,
    input  re_s,
    output reg ack_o_s,
    input  a_cmp,
    output reg [RAM_MEM_WIDTH-1:0] dat_out_s
);

    // --- B1: Parameter and local declarations ---
    parameter BD_SIZE       = 32;
    parameter RAM_MEM_WIDTH = 16;
    parameter BD_WIDTH      = 5;
    parameter MODE_16BIT    = 1'b1;

    localparam [BD_WIDTH-1:0] FREE_BD_INIT_32 = (BD_SIZE >> 1);
    localparam [BD_WIDTH-1:0] FREE_BD_INIT_16 = (BD_SIZE >> 2);
    localparam [BD_WIDTH-1:0] FREE_BD_INIT    = (MODE_16BIT != 1'b0) ? FREE_BD_INIT_16 : FREE_BD_INIT_32;

    reg [BD_WIDTH-1:0] m_wr_pnt;
    reg [BD_WIDTH-1:0] s_rd_pnt;
    reg                last_a_cmp;
    reg [BD_WIDTH-1:0] wr_cnt;
    reg [BD_WIDTH-1:0] rd_cnt;

    reg [RAM_MEM_WIDTH-1:0] bd_mem_0;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_1;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_2;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_3;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_4;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_5;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_6;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_7;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_8;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_9;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_10;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_11;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_12;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_13;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_14;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_15;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_16;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_17;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_18;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_19;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_20;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_21;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_22;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_23;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_24;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_25;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_26;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_27;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_28;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_29;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_30;
    reg [RAM_MEM_WIDTH-1:0] bd_mem_31;

    // --- B2: Write sequence ---
    reg new_bw;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            m_wr_pnt <= {BD_WIDTH{1'b0}};
            wr_cnt   <= {BD_WIDTH{1'b0}};
            new_bw   <= 1'b0;
        end else begin
            new_bw <= 1'b0;

            if (we_m && (free_bd > {BD_WIDTH{1'b0}})) begin
                case (m_wr_pnt)
                    0: bd_mem_0 <= dat_in_m;
                    1: bd_mem_1 <= dat_in_m;
                    2: bd_mem_2 <= dat_in_m;
                    3: bd_mem_3 <= dat_in_m;
                    4: bd_mem_4 <= dat_in_m;
                    5: bd_mem_5 <= dat_in_m;
                    6: bd_mem_6 <= dat_in_m;
                    7: bd_mem_7 <= dat_in_m;
                    8: bd_mem_8 <= dat_in_m;
                    9: bd_mem_9 <= dat_in_m;
                    10: bd_mem_10 <= dat_in_m;
                    11: bd_mem_11 <= dat_in_m;
                    12: bd_mem_12 <= dat_in_m;
                    13: bd_mem_13 <= dat_in_m;
                    14: bd_mem_14 <= dat_in_m;
                    15: bd_mem_15 <= dat_in_m;
                    16: bd_mem_16 <= dat_in_m;
                    17: bd_mem_17 <= dat_in_m;
                    18: bd_mem_18 <= dat_in_m;
                    19: bd_mem_19 <= dat_in_m;
                    20: bd_mem_20 <= dat_in_m;
                    21: bd_mem_21 <= dat_in_m;
                    22: bd_mem_22 <= dat_in_m;
                    23: bd_mem_23 <= dat_in_m;
                    24: bd_mem_24 <= dat_in_m;
                    25: bd_mem_25 <= dat_in_m;
                    26: bd_mem_26 <= dat_in_m;
                    27: bd_mem_27 <= dat_in_m;
                    28: bd_mem_28 <= dat_in_m;
                    29: bd_mem_29 <= dat_in_m;
                    30: bd_mem_30 <= dat_in_m;
                    31: bd_mem_31 <= dat_in_m;
                    default: bd_mem_0 <= dat_in_m;
                endcase

                if (m_wr_pnt == (BD_SIZE - 1)) begin
                    m_wr_pnt <= {BD_WIDTH{1'b0}};
                end else begin
                    m_wr_pnt <= m_wr_pnt + 1'b1;
                end

                if (MODE_16BIT != 1'b0) begin
                    if (wr_cnt == 3) begin
                        new_bw  <= 1'b1;
                        wr_cnt  <= {BD_WIDTH{1'b0}};
                    end else begin
                        wr_cnt  <= wr_cnt + 1'b1;
                    end
                end else begin
                    if (wr_cnt == 1) begin
                        new_bw  <= 1'b1;
                        wr_cnt  <= {BD_WIDTH{1'b0}};
                    end else begin
                        wr_cnt  <= wr_cnt + 1'b1;
                    end
                end
            end
        end
    end

    // --- B5: Release edge detect and free_bd update ---
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            free_bd    <= FREE_BD_INIT;
            last_a_cmp <= 1'b0;
        end else begin
            if (new_bw) begin
                free_bd <= free_bd - 1'b1;
            end else if ((a_cmp == 1'b1) && (last_a_cmp == 1'b0)) begin
                free_bd <= free_bd + 1'b1;
                last_a_cmp <= 1'b1;
            end else begin
                last_a_cmp <= a_cmp;
            end
        end
    end

    // --- B3: Read sequence ---
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            s_rd_pnt <= {BD_WIDTH{1'b0}};
            rd_cnt   <= {BD_WIDTH{1'b0}};
        end else begin
            if (re_s) begin
                if (s_rd_pnt == (BD_SIZE - 1)) begin
                    s_rd_pnt <= {BD_WIDTH{1'b0}};
                end else begin
                    s_rd_pnt <= s_rd_pnt + 1'b1;
                end

                if (MODE_16BIT != 1'b0) begin
                    if (rd_cnt == 3) begin
                        rd_cnt <= {BD_WIDTH{1'b0}};
                    end else begin
                        rd_cnt <= rd_cnt + 1'b1;
                    end
                end else begin
                    if (rd_cnt == 1) begin
                        rd_cnt <= {BD_WIDTH{1'b0}};
                    end else begin
                        rd_cnt <= rd_cnt + 1'b1;
                    end
                end
            end
        end
    end

    // --- B4: Combinational output ---
    // --- B4: Clocked read output ---
    always @(posedge clk or posedge rst) begin
         if (rst) begin
            ack_o_s   <= 1'b0;
        end else if (re_s) begin
        end else if (re_s) begin
            case (s_rd_pnt)
                0: dat_out_s <= bd_mem_0;
                1: dat_out_s <= bd_mem_1;
                2: dat_out_s <= bd_mem_2;
                3: dat_out_s <= bd_mem_3;
                4: dat_out_s <= bd_mem_4;
                5: dat_out_s <= bd_mem_5;
                6: dat_out_s <= bd_mem_6;
                7: dat_out_s <= bd_mem_7;
                8: dat_out_s <= bd_mem_8;
                9: dat_out_s <= bd_mem_9;
                10: dat_out_s <= bd_mem_10;
                11: dat_out_s <= bd_mem_11;
                12: dat_out_s <= bd_mem_12;
                13: dat_out_s <= bd_mem_13;
                14: dat_out_s <= bd_mem_14;
                15: dat_out_s <= bd_mem_15;
                16: dat_out_s <= bd_mem_16;
                17: dat_out_s <= bd_mem_17;
                18: dat_out_s <= bd_mem_18;
                19: dat_out_s <= bd_mem_19;
                20: dat_out_s <= bd_mem_20;
                21: dat_out_s <= bd_mem_21;
                22: dat_out_s <= bd_mem_22;
                23: dat_out_s <= bd_mem_23;
                24: dat_out_s <= bd_mem_24;
                25: dat_out_s <= bd_mem_25;
                26: dat_out_s <= bd_mem_26;
                27: dat_out_s <= bd_mem_27;
                28: dat_out_s <= bd_mem_28;
                29: dat_out_s <= bd_mem_29;
                30: dat_out_s <= bd_mem_30;
                31: dat_out_s <= bd_mem_31;
                default: dat_out_s <= {RAM_MEM_WIDTH{1'b0}};
            endcase
            if (MODE_16BIT != 1'b0) begin
                ack_o_s <= 1'b1;
            end else begin
                ack_o_s <= 1'b0;
            end
        end else begin
            ack_o_s <= 1'b0;
        end
    end

endmodule
