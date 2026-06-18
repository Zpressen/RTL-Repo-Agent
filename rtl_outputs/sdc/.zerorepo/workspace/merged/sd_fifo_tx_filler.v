`define MEM_OFFSET 4

module sd_fifo_tx_filler (
  input  wire        clk,
  input  wire        rst,
  output wire [31:0] m_wb_adr_o,
  output wire        m_wb_we_o,
  input  wire [31:0] m_wb_dat_i,
  output wire        m_wb_cyc_o,
  output wire        m_wb_stb_o,
  input  wire        m_wb_ack_i,
  output wire [2:0]  m_wb_cti_o,
  output wire [1:0]  m_wb_bte_o,
  input  wire        en,
  input  wire [31:0] adr,
  input  wire        sd_clk,
  output wire [31:0] dat_o,
  input  wire        rd,
  output wire        empty,
  output wire        fe
);

  // Internal registers and wires
  reg [8:0] offset;
  reg [8:0] we;
  reg [31:0] din;
  reg       wr_tx;
  reg       reset_tx_fifo;
  reg       first;
  reg       ackd;
  reg       delay;
  wire [5:0] mem_empt;   // unused FIFO occupancy output

  // Wishbone master outputs driven sequentially
  reg       m_wb_cyc_o_r;
  reg       m_wb_stb_o_r;

  // Drive output ports from registers
  assign m_wb_cyc_o = m_wb_cyc_o_r;
  assign m_wb_stb_o = m_wb_stb_o_r;

  // Static Wishbone signals
  assign m_wb_adr_o = adr + offset;
  assign m_wb_we_o  = 1'b0;
  assign m_wb_cti_o = 3'b000;
  assign m_wb_bte_o = 2'b00;

  // Sequential Wishbone control and FIFO write logic
always @(posedge clk or negedge rst) begin
    if (rst) begin
      offset        <= 9'd0;
      din           <= 32'd0;
      wr_tx         <= 1'b0;
      reset_tx_fifo <= 1'b1;
      ackd          <= 1'b1;
      delay         <= 1'b0;
      m_wb_cyc_o_r  <= 1'b0;
      m_wb_stb_o_r  <= 1'b0;
    end else begin
      if (!en) begin
        reset_tx_fifo <= 1'b1;
        offset        <= 9'd0;
        m_wb_cyc_o_r  <= 1'b0;
        m_wb_stb_o_r  <= 1'b0;
      end else begin
        reset_tx_fifo <= 1'b0;

        // Delay / ack capture with priority (delay > ack)
        if (delay) begin
          offset       <= offset + `MEM_OFFSET;
          ackd         <= ~ackd;
          wr_tx        <= 1'b0;
          delay        <= 1'b0;
          m_wb_cyc_o_r <= 1'b0;
          m_wb_stb_o_r <= 1'b0;
        end else if (m_wb_ack_i) begin
          // Capture data and write to FIFO
          wr_tx        <= 1'b1;
          din          <= m_wb_dat_i;
          m_wb_cyc_o_r <= 1'b0;
          m_wb_stb_o_r <= 1'b0;
          delay        <= 1'b1;
        end

        // Start new Wishbone transaction (can happen same cycle as delay)
        if (ackd && !fe && !m_wb_ack_i) begin
          m_wb_cyc_o_r <= 1'b1;
          m_wb_stb_o_r <= 1'b1;
          ackd         <= 1'b0;
          wr_tx        <= 1'b0;
        end
      end
    end
  end

  // sd_tx_fifo instance (dual-clock FIFO)
  sd_tx_fifo inst_sd_tx_fifo (
    .d        (din),
    .wr       (wr_tx),
    .wclk     (clk),
    .q        (dat_o),
    .rd       (rd),
    .full     (fe),
    .empty    (empty),
    .mem_empt (mem_empt),
    .rclk     (sd_clk),
    .rst      (reset_tx_fifo)
  );

endmodule
