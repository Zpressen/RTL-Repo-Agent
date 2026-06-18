// STAGE5_SUBTASK_BEGIN B1_decl_objects: Declare all module parameters (BD_SIZE, RAM_MEM_WIDTH, BD_WIDTH, mode selection) and internal state: free_bd counter, m_
parameter BD_SIZE = 8;
parameter RAM_MEM_WIDTH = 32;
parameter BD_WIDTH = 8;
parameter MODE_16BIT = 1'b0;

localparam [BD_WIDTH-1:0] FREE_BD_INIT_32 = (BD_SIZE >> 1);
localparam [BD_WIDTH-1:0] FREE_BD_INIT_16 = (BD_SIZE >> 2);
localparam [BD_WIDTH-1:0] FREE_BD_INIT = (MODE_16BIT != 1'b0) ? FREE_BD_INIT_16 : FREE_BD_INIT_32;

reg [BD_WIDTH-1:0] free_bd;
reg [BD_WIDTH-1:0] m_wr_pnt;
reg [BD_WIDTH-1:0] s_rd_pnt;
reg last_a_cmp;
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
// STAGE5_SUBTASK_END B1_decl_objects

// STAGE5_SUBTASK_BEGIN B2_write_sequence: Sequential block managing write operations: on reset, clear m_wr_pnt and wr_cnt; when we_m and free_bd>0, write dat_in_m
reg new_bw;

always @(posedge clk or posedge rst) begin
    if (rst) begin
        free_bd  <= FREE_BD_INIT;
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
    end
end
// STAGE5_SUBTASK_END B2_write_sequence

// STAGE5_SUBTASK_BEGIN B3_read_sequence: Sequential block for read pointer management: on reset, clear s_rd_pnt and rd_cnt. When re_s is high, increment s_rd_pnt
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
// STAGE5_SUBTASK_END B3_read_sequence

// STAGE5_SUBTASK_BEGIN B4_comb_output: Combinational block assigning dat_out_s from the flattened bd_mem at address s_rd_pnt, and generating ack_o_s. In 16‑bit
always @(s_rd_pnt or bd_mem_0 or bd_mem_1 or bd_mem_2 or bd_mem_3 or bd_mem_4 or bd_mem_5 or bd_mem_6 or bd_mem_7 or re_s) begin
    case (s_rd_pnt)
        0: dat_out_s = bd_mem_0;
        1: dat_out_s = bd_mem_1;
        2: dat_out_s = bd_mem_2;
        3: dat_out_s = bd_mem_3;
        4: dat_out_s = bd_mem_4;
        5: dat_out_s = bd_mem_5;
        6: dat_out_s = bd_mem_6;
        7: dat_out_s = bd_mem_7;
        default: dat_out_s = {RAM_MEM_WIDTH{1'b0}};
    endcase

    if (MODE_16BIT != 1'b0) begin
        ack_o_s = re_s;
    end else begin
        ack_o_s = 1'b0;
    end
end
// STAGE5_SUBTASK_END B4_comb_output

// STAGE5_SUBTASK_BEGIN B5_release_edge_detect: Sequential block that detects rising edge on a_cmp using last_a_cmp flip-flop. On reset clear last_a_cmp. Each cycle, up
always @(posedge clk or posedge rst) begin
    if (rst) begin
        last_a_cmp <= 1'b0;
    end else begin
        last_a_cmp <= a_cmp;
        if ((a_cmp == 1'b1) && (last_a_cmp == 1'b0)) begin
            free_bd <= free_bd + 1'b1;
        end
    end
end
// STAGE5_SUBTASK_END B5_release_edge_detect
