module sd_rx_fifo (
    input  wire [3:0] d,
    input  wire      wr,
    input  wire      wclk,
    output reg  [31:0] q,
    input  wire      rd,
    output wire      full,
    output wire      empty,
    output wire [1:0] mem_empt,
    input  wire      rclk,
    input  wire      rst
);

  // local parameters matching authoritative defines
  localparam FIFO_RX_MEM_DEPTH   = 16;
  localparam FIFO_RX_MEM_ADR_SIZE = 5;   // includes the extra wrap‑around toggle bit

  // ------------------------------------------------------------
  // Registers and RAM (unrolled to avoid unpacked arrays)
  // ------------------------------------------------------------
  reg [31:0] ram_0, ram_1, ram_2, ram_3, ram_4, ram_5, ram_6, ram_7;
  reg [31:0] ram_8, ram_9, ram_10, ram_11, ram_12, ram_13, ram_14, ram_15;

  reg [FIFO_RX_MEM_ADR_SIZE-1:0] adr_i, adr_o;
  reg [31:0] tmp;
  reg [7:0]  we;
  reg        ft;

  // ------------------------------------------------------------
  // Pointer synchronizers (2‑stage for full/empty)
  // ------------------------------------------------------------
  reg [FIFO_RX_MEM_ADR_SIZE-1:0] wptr_sync_r1, wptr_sync_r2;  // wclk → rclk
  reg [FIFO_RX_MEM_ADR_SIZE-1:0] rptr_sync_w1, rptr_sync_w2;  // rclk → wclk

  // ------------------------------------------------------------
  // Write domain (wclk)
  // ------------------------------------------------------------
  reg [31:0] tmp_next;
  always @(wr or d or we or tmp) begin
    tmp_next = tmp;
    if (wr) begin
      if (we[0]) tmp_next[3:0]   = d;
      if (we[1]) tmp_next[7:4]   = d;
      if (we[2]) tmp_next[11:8]  = d;
      if (we[3]) tmp_next[15:12] = d;
      if (we[4]) tmp_next[19:16] = d;
      if (we[5]) tmp_next[23:20] = d;
      if (we[6]) tmp_next[27:24] = d;
      if (we[7]) tmp_next[31:28] = d;
    end
  end

  always @(posedge wclk or posedge rst) begin
    if (rst) begin
      tmp   <= 32'd0;
      we    <= 8'h1;
      ft    <= 1'b0;
      adr_i <= 0;
    end else if (wr) begin
      tmp <= tmp_next;
      if (we[7]) begin                        // last byte of a word
        case (adr_i[3:0])
          4'd0:  ram_0  <= tmp_next;
          4'd1:  ram_1  <= tmp_next;
          4'd2:  ram_2  <= tmp_next;
          4'd3:  ram_3  <= tmp_next;
          4'd4:  ram_4  <= tmp_next;
          4'd5:  ram_5  <= tmp_next;
          4'd6:  ram_6  <= tmp_next;
          4'd7:  ram_7  <= tmp_next;
          4'd8:  ram_8  <= tmp_next;
          4'd9:  ram_9  <= tmp_next;
          4'd10: ram_10 <= tmp_next;
          4'd11: ram_11 <= tmp_next;
          4'd12: ram_12 <= tmp_next;
          4'd13: ram_13 <= tmp_next;
          4'd14: ram_14 <= tmp_next;
          4'd15: ram_15 <= tmp_next;
          default:;
        endcase
        ft <= 1'b1;
        if (adr_i[3:0] == (FIFO_RX_MEM_DEPTH - 1))
          adr_i <= {~adr_i[4], {4{1'b0}}};
        else
          adr_i <= {adr_i[4], adr_i[3:0] + 1'b1};
        we <= 8'h1;                            // back to first nibble
      end else begin
        we <= we << 1;                         // advance to next nibble
      end
    end
  end

  // ------------------------------------------------------------
  // Read domain (rclk)
  // ------------------------------------------------------------
  reg [31:0] q_nxt;
  always @(adr_o or ram_0 or ram_1 or ram_2 or ram_3 or ram_4 or ram_5 or ram_6 or ram_7 or
           ram_8 or ram_9 or ram_10 or ram_11 or ram_12 or ram_13 or ram_14 or ram_15) begin
    case (adr_o[3:0])
      4'd0:  q_nxt = ram_0;
      4'd1:  q_nxt = ram_1;
      4'd2:  q_nxt = ram_2;
      4'd3:  q_nxt = ram_3;
      4'd4:  q_nxt = ram_4;
      4'd5:  q_nxt = ram_5;
      4'd6:  q_nxt = ram_6;
      4'd7:  q_nxt = ram_7;
      4'd8:  q_nxt = ram_8;
      4'd9:  q_nxt = ram_9;
      4'd10: q_nxt = ram_10;
      4'd11: q_nxt = ram_11;
      4'd12: q_nxt = ram_12;
      4'd13: q_nxt = ram_13;
      4'd14: q_nxt = ram_14;
      4'd15: q_nxt = ram_15;
      default: q_nxt = 32'd0;
    endcase
  end

  always @(posedge rclk or posedge rst) begin
    if (rst) begin
      adr_o <= 0;
      q     <= 32'd0;
    end else if (rd && !empty) begin
      q <= q_nxt;
      if (adr_o[3:0] == (FIFO_RX_MEM_DEPTH - 1))
        adr_o <= {~adr_o[4], {4{1'b0}}};
      else
        adr_o <= {adr_o[4], adr_o[3:0] + 1'b1};
    end
  end

  // ------------------------------------------------------------
  // Flag synchronisation and status outputs
  // ------------------------------------------------------------
  // Write pointer → read domain
  always @(posedge rclk or posedge rst) begin
    if (rst) begin
      wptr_sync_r1 <= 0;
      wptr_sync_r2 <= 0;
    end else begin
      wptr_sync_r1 <= adr_i;
      wptr_sync_r2 <= wptr_sync_r1;
    end
  end

  // Read pointer → write domain
  always @(posedge wclk or posedge rst) begin
    if (rst) begin
      rptr_sync_w1 <= 0;
      rptr_sync_w2 <= 0;
    end else begin
      rptr_sync_w1 <= adr_o;
      rptr_sync_w2 <= rptr_sync_w1;
    end
  end

  assign full  = (adr_i[3:0] == rptr_sync_w2[3:0]) && (adr_i[4] != rptr_sync_w2[4]);
  assign empty = (adr_o == wptr_sync_r2);

  wire [FIFO_RX_MEM_ADR_SIZE-1:0] used_words = wptr_sync_r2 - adr_o;
  wire [FIFO_RX_MEM_ADR_SIZE-1:0] free_words = FIFO_RX_MEM_DEPTH - used_words;
  assign mem_empt = free_words[1:0];

endmodule
