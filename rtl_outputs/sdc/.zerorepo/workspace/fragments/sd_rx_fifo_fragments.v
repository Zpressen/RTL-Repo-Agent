// STAGE5_SUBTASK_BEGIN B1_decl_parameters_and_registers: Declare FIFO_RX_MEM_DEPTH and FIFO_RX_MEM_ADR_SIZE parameters; define RAM storage as an explicitly unrolled set of 32-bi
// Parameters
parameter FIFO_RX_MEM_DEPTH   = 8;   // default depth
parameter FIFO_RX_MEM_ADR_SIZE = 3;   // log2(DEPTH)

// RAM storage: explicitly unrolled 32-bit scalar registers
// (adjust list when DEPTH changes)
reg [31:0] ram_0;
reg [31:0] ram_1;
reg [31:0] ram_2;
reg [31:0] ram_3;
reg [31:0] ram_4;
reg [31:0] ram_5;
reg [31:0] ram_6;
reg [31:0] ram_7;

// Write and read pointers with extra high-bit for wrap-around detection
reg [FIFO_RX_MEM_ADR_SIZE:0] adr_i;
reg [FIFO_RX_MEM_ADR_SIZE:0] adr_o;

// Nibble accumulator (32-bit)
reg [31:0] tmp;

// Byte-write enable (8 bits)
reg [7:0]  we;

// Data-written flag (1 bit)
reg        ft;
// STAGE5_SUBTASK_END B1_decl_parameters_and_registers

// STAGE5_SUBTASK_BEGIN B2_seq_write_domain: On wclk rising edge, when wr is high, accumulate 4‑bit d into tmp according to we’s current bit position; shift we left 
reg [31:0] tmp_next;

always @* begin
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
    tmp   <= 0;
    we    <= 8'h1;
    ft    <= 1'b0;
    adr_i <= 0;
  end else begin
    if (wr) begin
      tmp <= tmp_next;
      we  <= we[7] ? 8'h1 : (we << 1);
      if (we[7]) begin
        case (adr_i[2:0])
          3'd0: ram_0 <= tmp_next;
          3'd1: ram_1 <= tmp_next;
          3'd2: ram_2 <= tmp_next;
          3'd3: ram_3 <= tmp_next;
          3'd4: ram_4 <= tmp_next;
          3'd5: ram_5 <= tmp_next;
          3'd6: ram_6 <= tmp_next;
          3'd7: ram_7 <= tmp_next;
        endcase
        ft <= 1'b1;
        if (adr_i[2:0] == (FIFO_RX_MEM_DEPTH - 1))
          adr_i <= {~adr_i[FIFO_RX_MEM_ADR_SIZE], {(FIFO_RX_MEM_ADR_SIZE){1'b0}}};
        else
          adr_i <= {adr_i[FIFO_RX_MEM_ADR_SIZE], (adr_i[2:0] + 1'b1)};
      end
    end
  end
end
// STAGE5_SUBTASK_END B2_seq_write_domain

// STAGE5_SUBTASK_BEGIN B3_seq_read_domain: On rclk rising edge, if rd is high and empty is deasserted, increment adr_o with wrap‑around and high‑bit toggle; presen
// combinational read-data mux
reg [31:0] q_nxt;
always @* begin
    case (adr_o[FIFO_RX_MEM_ADR_SIZE-1:0])
        3'd0: q_nxt = ram_0;
        3'd1: q_nxt = ram_1;
        3'd2: q_nxt = ram_2;
        3'd3: q_nxt = ram_3;
        3'd4: q_nxt = ram_4;
        3'd5: q_nxt = ram_5;
        3'd6: q_nxt = ram_6;
        3'd7: q_nxt = ram_7;
        default: q_nxt = 32'd0;
    endcase
end

// sequential read domain: read pointer and output data
always @(posedge rclk or posedge rst) begin
    if (rst) begin
        adr_o <= 0;
        q     <= 0;
    end else begin
        if (rd && !empty) begin
            // register read data from current address
            q <= q_nxt;
            // increment read address with wrap-around and high-bit toggle
            if (adr_o[FIFO_RX_MEM_ADR_SIZE-1:0] == (FIFO_RX_MEM_DEPTH - 1)) begin
                adr_o <= {~adr_o[FIFO_RX_MEM_ADR_SIZE], {(FIFO_RX_MEM_ADR_SIZE){1'b0}}};
            end else begin
                adr_o <= {adr_o[FIFO_RX_MEM_ADR_SIZE], (adr_o[FIFO_RX_MEM_ADR_SIZE-1:0] + 1'b1)};
            end
        end
    end
end
// STAGE5_SUBTASK_END B3_seq_read_domain

// STAGE5_SUBTASK_BEGIN B4_seq_flag_synchronization: Generate full, empty, and mem_empt flags. Synchronize write pointer adr_i into rclk domain and read pointer adr_o into w
// Synchronize write pointer adr_i into read clock domain (rclk) with 2-stage flip-flops
reg [FIFO_RX_MEM_ADR_SIZE:0] wptr_sync_r1, wptr_sync_r2;

always @(posedge rclk or posedge rst) begin
    if (rst) begin
        wptr_sync_r1 <= 0;
        wptr_sync_r2 <= 0;
    end else begin
        wptr_sync_r1 <= adr_i;
        wptr_sync_r2 <= wptr_sync_r1;
    end
end

// Synchronize read pointer adr_o into write clock domain (wclk) with 2-stage flip-flops
reg [FIFO_RX_MEM_ADR_SIZE:0] rptr_sync_w1, rptr_sync_w2;

always @(posedge wclk or posedge rst) begin
    if (rst) begin
        rptr_sync_w1 <= 0;
        rptr_sync_w2 <= 0;
    end else begin
        rptr_sync_w1 <= adr_o;
        rptr_sync_w2 <= rptr_sync_w1;
    end
end

// Full flag: wclk domain, write pointer caught up to read pointer
wire full;
assign full = (adr_i[FIFO_RX_MEM_ADR_SIZE-1:0] == rptr_sync_w2[FIFO_RX_MEM_ADR_SIZE-1:0]) &&
              (adr_i[FIFO_RX_MEM_ADR_SIZE] != rptr_sync_w2[FIFO_RX_MEM_ADR_SIZE]);

// Empty flag: rclk domain, read pointer caught up to write pointer
wire empty;
assign empty = (adr_o == wptr_sync_r2);

// mem_empt: combinational available word count (low 2 bits) from synchronized pointers in read domain
wire [FIFO_RX_MEM_ADR_SIZE:0] used_words;
wire [FIFO_RX_MEM_ADR_SIZE:0] free_words;
assign used_words = (wptr_sync_r2[FIFO_RX_MEM_ADR_SIZE:0] - adr_o[FIFO_RX_MEM_ADR_SIZE:0]);
assign free_words = FIFO_RX_MEM_DEPTH - used_words;

wire [1:0] mem_empt;
assign mem_empt = free_words[1:0];
// STAGE5_SUBTASK_END B4_seq_flag_synchronization

// STAGE5_SUBTASK_BEGIN B5_comb_data_and_space_output: If q and mem_empt are not already driven in B3 or B4, provide purely combinational assignments: q from the RAM location 
// q: driven sequentially in B3 (seq_read_domain) via q_nxt muxing the unrolled RAM.
// mem_empt: driven combinationally in B4 (seq_flag_synchronization) using synchronized pointers.
// No further combinational assignments required here.
// STAGE5_SUBTASK_END B5_comb_data_and_space_output
