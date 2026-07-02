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

    // --- B2 + B5 merged: Write sequence + Release edge detect ---
    reg new_bw;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            free_bd    <= FREE_BD_INIT;
            m_wr_pnt   <= {BD_WIDTH{1'b0}};
            wr_cnt     <= {BD_WIDTH{1'b0}};
            new_bw     <= 1'b0;
            last_a_cmp <= 1'b0;
        end else begin
            new_bw <= 1'b0;

            // --- B2: Write sequence ---
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
                        free_bd <= free_bd - 1'b1;
                        wr_cnt  <= {BD_WIDTH{1'b0}};
                    end else begin
                        wr_cnt  <= wr_cnt + 1'b1;
                    end
                end else begin
                    if (wr_cnt == 1) begin
                        new_bw  <= 1'b1;
                        free_bd <= free_bd - 1'b1;
                        wr_cnt  <= {BD_WIDTH{1'b0}};
                    end else begin
                        wr_cnt  <= wr_cnt + 1'b1;
                    end
                end
            end

            // --- B5: Release edge detect ---
            if ((a_cmp == 1'b1) && (last_a_cmp == 1'b0)) begin
                free_bd <= free_bd + 1'b1;
            end
            last_a_cmp <= a_cmp;
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
            dat_out_s <= {RAM_MEM_WIDTH{1'b0}};
            ack_o_s   <= 1'b0;
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
