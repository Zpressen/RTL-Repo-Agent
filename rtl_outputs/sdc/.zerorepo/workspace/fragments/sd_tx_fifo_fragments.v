// STAGE5_SUBTASK_BEGIN B1_decl_core_objects: Declare RAM storage as a 32-bit wide array of depth FIFO_TX_MEM_DEPTH, write pointer adr_i (width FIFO_RX_MEM_ADR_SIZE) 
// RAM storage as a single packed vector (depth * 32 bits)
reg [32*FIFO_TX_MEM_DEPTH-1:0] ram;

// Write and read binary pointers
reg [FIFO_RX_MEM_ADR_SIZE-1:0] adr_i;
reg [FIFO_RX_MEM_ADR_SIZE-1:0] adr_o;

// Gray-encoded pointers for cross-clock domain
reg [FIFO_RX_MEM_ADR_SIZE-1:0] wptr_gray;
reg [FIFO_RX_MEM_ADR_SIZE-1:0] rptr_gray;

// Synchronizer flip-flops for write pointer (to rclk domain)
reg [FIFO_RX_MEM_ADR_SIZE-1:0] wptr_gray_sync1;
reg [FIFO_RX_MEM_ADR_SIZE-1:0] wptr_gray_sync2;

// Synchronizer flip-flops for read pointer (to wclk domain)
reg [FIFO_RX_MEM_ADR_SIZE-1:0] rptr_gray_sync1;
reg [FIFO_RX_MEM_ADR_SIZE-1:0] rptr_gray_sync2;
// STAGE5_SUBTASK_END B1_decl_core_objects

// STAGE5_SUBTASK_BEGIN B2_write_pointer_update: On the rising edge of wclk, if rst is high, reset adr_i to 0. Otherwise, if wr is high and full is low, write the input 
always @(posedge wclk) begin
    if (rst) begin
        adr_i <= {FIFO_RX_MEM_ADR_SIZE{1'b0}};
    end else begin
        if (wr && !full) begin
            ram[adr_i*32 +: 32] <= d;
            if (adr_i == FIFO_TX_MEM_DEPTH - 1)
                adr_i <= {FIFO_RX_MEM_ADR_SIZE{1'b0}};
            else
                adr_i <= adr_i + 1;
        end
    end
end
// STAGE5_SUBTASK_END B2_write_pointer_update

// STAGE5_SUBTASK_BEGIN B3_read_pointer_update: On the rising edge of rclk, if rst is high, reset adr_o to 0. Otherwise, if rd is high and empty is low, increment adr_o
always @(posedge rclk) begin
    if (rst) begin
        adr_o <= {FIFO_RX_MEM_ADR_SIZE{1'b0}};
    end else begin
        if (rd && !empty) begin
            if (adr_o == FIFO_TX_MEM_DEPTH - 1)
                adr_o <= {FIFO_RX_MEM_ADR_SIZE{1'b0}};
            else
                adr_o <= adr_o + 1;
        end
    end
end
// STAGE5_SUBTASK_END B3_read_pointer_update

// STAGE5_SUBTASK_BEGIN B4_status_flag_gen_sync: Synchronize adr_i to the rclk domain and adr_o to the wclk domain using a safe cross-clock method such as gray encoding 
// Gray code conversion for write pointer (wclk domain)
always @(*) begin
    wptr_gray = adr_i ^ (adr_i >> 1);
end

// Next write pointer binary and its gray (wclk domain)
wire [FIFO_RX_MEM_ADR_SIZE-1:0] wptr_next_binary;
assign wptr_next_binary = (adr_i == FIFO_TX_MEM_DEPTH - 1) ? 0 : adr_i + 1;

wire [FIFO_RX_MEM_ADR_SIZE-1:0] wptr_next_gray;
assign wptr_next_gray = wptr_next_binary ^ (wptr_next_binary >> 1);

assign full = (wptr_next_gray == rptr_gray_sync2);

// Two-stage synchronizer for read gray pointer into wclk domain
always @(posedge wclk) begin
    rptr_gray_sync1 <= rptr_gray;
    rptr_gray_sync2 <= rptr_gray_sync1;
end

// Gray code conversion for read pointer (rclk domain)
always @(*) begin
    rptr_gray = adr_o ^ (adr_o >> 1);
end

// Two-stage synchronizer for write gray pointer into rclk domain
always @(posedge rclk) begin
    wptr_gray_sync1 <= wptr_gray;
    wptr_gray_sync2 <= wptr_gray_sync1;
end

// Empty flag (rclk domain)
assign empty = (wptr_gray_sync2 == rptr_gray);

// Gray-to-binary conversion of synchronized write pointer (rclk domain)
wire [FIFO_RX_MEM_ADR_SIZE-1:0] wptr_bin_rclk;
integer i;
always @(*) begin
    wptr_bin_rclk[FIFO_RX_MEM_ADR_SIZE-1] = wptr_gray_sync2[FIFO_RX_MEM_ADR_SIZE-1];
    for (i = FIFO_RX_MEM_ADR_SIZE-2; i >= 0; i = i - 1) begin
        wptr_bin_rclk[i] = wptr_bin_rclk[i+1] ^ wptr_gray_sync2[i];
    end
end

// Occupancy (rclk domain)
wire [FIFO_RX_MEM_ADR_SIZE:0] diff_raw;
assign diff_raw = (wptr_bin_rclk >= adr_o) ? (wptr_bin_rclk - adr_o) : (FIFO_TX_MEM_DEPTH + wptr_bin_rclk - adr_o);
assign mem_empt = diff_raw[5:0];
// STAGE5_SUBTASK_END B4_status_flag_gen_sync

// STAGE5_SUBTASK_BEGIN B5_data_output: Drive output q from the RAM at address adr_o. The data output may be combinational (assign q = ram[adr_o]) or registered
// Data output register: registered output to avoid glitches; reads from RAM at adr_o
always @(posedge rclk or posedge rst) begin
    if (rst) begin
        q <= 32'b0;
    end else begin
        q <= ram[adr_o*32 +: 32];
    end
end
// STAGE5_SUBTASK_END B5_data_output
