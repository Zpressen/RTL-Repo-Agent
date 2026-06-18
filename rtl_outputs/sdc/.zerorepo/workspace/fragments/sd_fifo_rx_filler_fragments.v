// STAGE5_SUBTASK_BEGIN B1_decl_main_objects: Declare the module's registers (offset[8:0], wb_free, reset_rx_fifo, rd, state), wires (fifo_q[31:0], fifo_full, fifo_em
// Registers
reg [8:0] offset;
reg       wb_free;
reg       reset_rx_fifo;
reg       rd;
reg [2:0] state;

// Wires from sd_rx_fifo
wire [31:0] fifo_q;
wire        fifo_full;
wire        fifo_empty;

// Fixed address offset between consecutive memory words (from global define)
localparam MEM_OFFSET = `MEM_OFFSET;
// STAGE5_SUBTASK_END B1_decl_main_objects

// STAGE5_SUBTASK_BEGIN B2_inst_sd_rx_fifo: Instantiate sd_rx_fifo submodule and connect ports: d=dat_i, wr=wr, wclk=sd_clk, q=fifo_q, rd=rd, full=fifo_full, empty=
sd_rx_fifo inst_sd_rx_fifo (
    .d(dat_i),
    .wr(wr),
    .wclk(sd_clk),
    .q(fifo_q),
    .rd(rd),
    .full(fifo_full),
    .empty(fifo_empty),
    .mem_empt(2'b0),
    .rclk(clk),
    .rst(reset_rx_fifo)
);
// STAGE5_SUBTASK_END B2_inst_sd_rx_fifo

// STAGE5_SUBTASK_BEGIN B3_comb_wishbone_outputs: Generate all Wishbone master outputs combinationally: m_wb_adr_o = adr + offset, m_wb_dat_o = fifo_q, m_wb_we_o/cyc_o/st
// Wishbone master outputs (combinational)
assign full         = fifo_full;
assign empty        = fifo_empty;
assign m_wb_adr_o   = adr + offset;
assign m_wb_dat_o   = fifo_q;
assign m_wb_we_o    = wb_request_active;
assign m_wb_cyc_o   = wb_request_active;
assign m_wb_stb_o   = wb_request_active;
assign m_wb_cti_o   = 3'b000;   // classic single-cycle
assign m_wb_bte_o   = 2'b00;    // no burst
// STAGE5_SUBTASK_END B3_comb_wishbone_outputs

// STAGE5_SUBTASK_BEGIN B4_seq_control_fsm: Implement the control FSM with a single clocked always block, asynchronous reset, two states (IDLE, ACTIVE). Manage offs
localparam [2:0] IDLE  = 3'd0;
localparam [2:0] ACTIVE = 3'd1;

always @(posedge clk or posedge rst) begin
    if (rst) begin
        state        <= IDLE;
        offset       <= 9'h0;
        wb_free      <= 1'b1;
        reset_rx_fifo <= 1'b1;
        rd           <= 1'b0;
    end else if (!en) begin
        state        <= IDLE;
        offset       <= 9'h0;
        wb_free      <= 1'b1;
        reset_rx_fifo <= 1'b1;
        rd           <= 1'b0;
    end else begin
        case (state)
            IDLE: begin
                rd           <= 1'b0;
                reset_rx_fifo <= 1'b0;
                wb_free      <= 1'b1;
                if (!empty && wb_free) begin
                    rd       <= 1'b1;
                    wb_free  <= 1'b0;
                    state    <= ACTIVE;
                end
            end
            ACTIVE: begin
                if (m_wb_ack_i) begin
                    rd       <= 1'b0;
                    offset   <= offset + `MEM_OFFSET;
                    wb_free  <= 1'b1;
                    state    <= IDLE;
                end
            end
            default: begin
                state <= IDLE;
            end
        endcase
    end
end

assign wb_request_active = (state == ACTIVE);
// STAGE5_SUBTASK_END B4_seq_control_fsm
