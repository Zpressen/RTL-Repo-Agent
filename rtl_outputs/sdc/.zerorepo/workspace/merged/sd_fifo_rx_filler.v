module sd_fifo_rx_filler (
    input  wire          clk,
    input  wire          rst,
    input  wire          en,
    input  wire [31:0]   adr,
    input  wire [SD_BUS_W-1:0] dat_i,
    input  wire          wr,
    input  wire          sd_clk,
    output wire          full,
    output wire          empty,
    output wire [31:0]   m_wb_adr_o,
    output wire          m_wb_we_o,
    output reg [31:0]   m_wb_dat_o,
    output wire          m_wb_cyc_o,
    output wire          m_wb_stb_o,
    output wire [2:0]    m_wb_cti_o,
    output wire [1:0]    m_wb_bte_o,
    input  wire          m_wb_ack_i
);

    parameter SD_BUS_W = 4;    // from global defines

    // Internal registers
    reg  [8:0] offset;
    reg        wb_free;
    reg        reset_rx_fifo;
    reg        rd;
    reg  [2:0] state;

    // Wires from sd_rx_fifo
    wire [31:0] fifo_q;
    wire        fifo_full;
    wire        fifo_empty;

    // Local memory offset constant (from global defines)
localparam MEM_OFFSET = 4;

    // Wishbone active request flag
    wire wb_request_active;

    // ---------- sd_rx_fifo instantiation ----------
    sd_rx_fifo inst_sd_rx_fifo (
        .d        (dat_i),
        .wr       (wr),
        .wclk     (sd_clk),
        .q        (fifo_q),
        .rd       (rd),
        .full     (fifo_full),
        .empty    (fifo_empty),
        .mem_empt (),
        .rclk     (clk),
        .rst      (reset_rx_fifo)
    );

    // ---------- Combinational Wishbone outputs ----------
    assign full         = fifo_full;
    assign empty        = fifo_empty;
    assign m_wb_adr_o   = adr + {23'b0, offset};
    // m_wb_dat_o is registered directly in the always block
    assign m_wb_we_o    = wb_request_active;
    assign m_wb_cyc_o   = wb_request_active;
    assign m_wb_stb_o   = wb_request_active;
    assign m_wb_cti_o   = 3'b000;
    assign m_wb_bte_o   = 2'b00;

assign wb_request_active = (state == ACTIVE);   // ACTIVE state

    // ---------- Control FSM (asynchronous reset) ----------
    localparam IDLE  = 3'd0;
    localparam ACTIVE = 3'd1;

    // dat_o register removed; using m_wb_dat_o directly

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            state        <= IDLE;
            offset       <= 9'h0;
            wb_free      <= 1'b1;
            reset_rx_fifo <= 1'b1;
            rd           <= 1'b0;
            m_wb_dat_o   <= 32'h0;
        end else if (!en) begin
            state        <= IDLE;
            offset       <= 9'h0;
            wb_free      <= 1'b1;
            reset_rx_fifo <= 1'b1;
            rd           <= 1'b0;
            // m_wb_dat_o retains its value when disabled
        end else begin
            case (state)
                IDLE: begin
                    rd           <= 1'b0;
                    reset_rx_fifo <= 1'b0;
                    if (!empty && wb_free) begin
                        rd       <= 1'b1;
                        m_wb_dat_o <= fifo_q;
                        wb_free  <= 1'b0;
                        state    <= ACTIVE;
                    end
                end
                ACTIVE: begin
                    rd           <= 1'b0;
                    if (m_wb_ack_i) begin
                        offset   <= offset + MEM_OFFSET;
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

endmodule
