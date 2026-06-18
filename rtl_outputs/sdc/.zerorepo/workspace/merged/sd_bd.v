module sd_bd (
    clk,
    rst,
    we_m,
    dat_in_m,
    free_bd,
    re_s,
    ack_o_s,
    a_cmp,
    dat_out_s
);

parameter BD_SIZE = 8;
parameter BD_WIDTH = 5;
parameter RAM_MEM_WIDTH = 16;
parameter BD_MODE_16 = 1'b0;

localparam BD_MEM_SIZE = BD_SIZE * 4;

input clk;
input rst;
input we_m;
input [RAM_MEM_WIDTH-1:0] dat_in_m;
output [BD_WIDTH-1:0] free_bd;
input re_s;
output ack_o_s;
input a_cmp;
output [RAM_MEM_WIDTH-1:0] dat_out_s;

reg [BD_WIDTH-1:0] free_bd;
reg ack_o_s;
reg [RAM_MEM_WIDTH-1:0] dat_out_s;

reg [BD_WIDTH-1:0] m_wr_pnt;
reg [BD_WIDTH-1:0] s_rd_pnt;
reg [1:0] write_cnt;
reg [1:0] read_s_cnt;
reg read_cnt;
reg last_a_cmp;
reg new_bw;

reg [RAM_MEM_WIDTH-1:0] bd_mem [0:BD_MEM_SIZE-1];

wire write_accept;
wire a_cmp_rise;

integer i;

assign write_accept = we_m & (free_bd != {BD_WIDTH{1'b0}});
assign a_cmp_rise = a_cmp & ~last_a_cmp;

always @(posedge clk or posedge rst) begin
    if (rst) begin
        free_bd <= BD_SIZE;
        m_wr_pnt <= {BD_WIDTH{1'b0}};
        s_rd_pnt <= {BD_WIDTH{1'b0}};
        write_cnt <= 2'd0;
        read_s_cnt <= 2'd0;
        read_cnt <= 1'b0;
        last_a_cmp <= 1'b0;
        new_bw <= 1'b0;
    end else begin
        if (!new_bw) begin
            last_a_cmp <= a_cmp;
        end
        new_bw <= write_accept & (write_cnt == 2'd3);

        if (write_accept) begin
            bd_mem[m_wr_pnt] <= dat_in_m;

            if (m_wr_pnt == BD_MEM_SIZE - 1) begin
                m_wr_pnt <= {BD_WIDTH{1'b0}};
            end else begin
                m_wr_pnt <= m_wr_pnt + {{(BD_WIDTH-1){1'b0}}, 1'b1};
            end

            write_cnt <= write_cnt + 2'd1;
        end

        if (re_s) begin
            if (s_rd_pnt == BD_MEM_SIZE - 1) begin
                s_rd_pnt <= {BD_WIDTH{1'b0}};
            end else begin
                s_rd_pnt <= s_rd_pnt + {{(BD_WIDTH-1){1'b0}}, 1'b1};
            end

            read_s_cnt <= read_s_cnt + 2'd1;
            read_cnt <= 1'b0;
        end

        if (new_bw) begin
            free_bd <= free_bd - {{(BD_WIDTH-1){1'b0}}, 1'b1};
        end else if (a_cmp_rise) begin
            free_bd <= free_bd + {{(BD_WIDTH-1){1'b0}}, 1'b1};
        end else begin
            free_bd <= free_bd;
        end
    end
end

always @(posedge clk or posedge rst) begin
    if (rst) begin
        ack_o_s <= 1'b0;
    end else begin
        ack_o_s <= re_s;
        if (re_s) begin
            dat_out_s <= bd_mem[s_rd_pnt];
        end
    end
end

endmodule
