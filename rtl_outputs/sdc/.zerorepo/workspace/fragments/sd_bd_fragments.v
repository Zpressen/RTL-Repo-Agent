// STAGE5_SUBTASK_BEGIN B1_decl_objects: Declare all module parameters (BD_SIZE, RAM_MEM_WIDTH, BD_WIDTH, mode selection) and internal state: free_bd counter, m_
parameter BD_SIZE = 8;
parameter RAM_MEM_WIDTH = 32;
parameter BD_WIDTH = 8;
parameter MODE_16BIT = 0;

localparam FREE_BD_INIT = (MODE_16BIT) ? (BD_SIZE >> 2) : (BD_SIZE >> 1);

reg [BD_WIDTH-1:0] free_bd;
reg [BD_WIDTH-1:0] m_wr_pnt;
reg [BD_WIDTH-1:0] s_rd_pnt;
reg last_a_cmp;
reg [BD_WIDTH-1:0] wr_cnt;
reg [BD_WIDTH-1:0] rd_cnt;
reg [BD_SIZE*RAM_MEM_WIDTH-1:0] bd_mem;
// STAGE5_SUBTASK_END B1_decl_objects

// STAGE5_SUBTASK_BEGIN B2_write_sequence: Sequential block managing write operations: on reset, clear m_wr_pnt and wr_cnt; when we_m and free_bd>0, write dat_in_m
// B2_write_sequence
reg new_bw;

always @(posedge clk or posedge rst) begin
    if (rst) begin
        free_bd      <= FREE_BD_INIT;
        m_wr_pnt     <= {BD_WIDTH{1'b0}};
        wr_cnt       <= {BD_WIDTH{1'b0}};
        new_bw       <= 1'b0;
    end else begin
        new_bw <= 1'b0;
        if (we_m && (free_bd > 0)) begin
            // Write dat_in_m at offset m_wr_pnt * RAM_MEM_WIDTH
            bd_mem[m_wr_pnt * RAM_MEM_WIDTH +: RAM_MEM_WIDTH] <= dat_in_m;
            // Increment write pointer with wrap
            if (m_wr_pnt == (BD_SIZE - 1))
                m_wr_pnt <= 0;
            else
                m_wr_pnt <= m_wr_pnt + 1'b1;
            // Handle write sequence completion
            if (MODE_16BIT ? (wr_cnt == 3) : (wr_cnt == 1)) begin
                new_bw   <= 1'b1;
                free_bd  <= free_bd - 1'b1;
                wr_cnt   <= {BD_WIDTH{1'b0}};
            end else begin
                wr_cnt   <= wr_cnt + 1'b1;
            end
        end
    end
end
// STAGE5_SUBTASK_END B2_write_sequence
