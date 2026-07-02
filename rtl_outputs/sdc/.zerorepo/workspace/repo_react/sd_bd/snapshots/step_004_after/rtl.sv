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

    reg [RAM_MEM_WIDTH-1:0] bd_mem [BD_SIZE-1:0];

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
            if (we_m && (free_bd > {BD_WIDTH{1'b0}})) begin
                bd_mem[m_wr_pnt] <= dat_in_m;
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
            dat_out_s <= {RAM_MEM_WIDTH{1'b0}};
            ack_o_s   <= 1'b0;
        end else if (re_s) begin
            case (s_rd_pnt)
                0: dat_out_s <= bd_mem_0;
                1: dat_out_s <= bd_mem_1;
        end else if (re_s) begin
            dat_out_s <= bd_mem[s_rd_pnt];
                ack_o_s <= 1'b0;
            end
        end else begin
            ack_o_s <= 1'b0;
        end
    end

endmodule
