module sd_tx_fifo #(
    parameter FIFO_TX_MEM_DEPTH    = 8,
    parameter FIFO_RX_MEM_ADR_SIZE = 4
) (
    input  [31:0] d,
    input         wr,
    input         wclk,
    output reg [31:0] q,
    input         rd,
    output        full,
    output        empty,
    output [ 5:0] mem_empt,
    input         rclk,
    input         rst
);

    localparam PTR_WIDTH = FIFO_RX_MEM_ADR_SIZE;     // pointer width (binary + Gray)
    localparam ADDR_BITS = $clog2(FIFO_TX_MEM_DEPTH); // RAM address width

    // RAM storage (packed vector, depth * 32 bits)
    reg [32*FIFO_TX_MEM_DEPTH-1:0] ram;

    // Binary write / read pointers
    reg [PTR_WIDTH-1:0] wptr_bin;
    reg [PTR_WIDTH-1:0] rptr_bin;

    // Gray-encoded pointers (combinational)
    wire [PTR_WIDTH-1:0] wptr_gray;
    wire [PTR_WIDTH-1:0] rptr_gray;

    // Synchronizer flip-flops for cross-domain crossing
    reg [PTR_WIDTH-1:0] wptr_gray_sync1;
    reg [PTR_WIDTH-1:0] wptr_gray_sync2;
    reg [PTR_WIDTH-1:0] rptr_gray_sync1;
    reg [PTR_WIDTH-1:0] rptr_gray_sync2;

    // Write pointer and RAM write logic (wclk domain)
    wire [ADDR_BITS-1:0] waddr;
    assign waddr = wptr_bin[ADDR_BITS-1:0];

    always @(posedge wclk or posedge rst) begin
        if (rst) begin
            wptr_bin <= {PTR_WIDTH{1'b0}};
        end else if (wr && !full) begin
            ram[waddr*32 +: 32] <= d;
            wptr_bin <= wptr_bin + 1'b1;
        end
    end

    // Read pointer update (rclk domain)
    always @(posedge rclk or posedge rst) begin
        if (rst) begin
            rptr_bin <= {PTR_WIDTH{1'b0}};
        end else if (rd && !empty) begin
            rptr_bin <= rptr_bin + 1'b1;
        end
    end

    // Gray encode the binary pointers
    assign wptr_gray = wptr_bin ^ (wptr_bin >> 1);
    assign rptr_gray = rptr_bin ^ (rptr_bin >> 1);

    // Synchronizer chain: rptr_gray (from rclk domain) into wclk domain
    always @(posedge wclk or posedge rst) begin
        if (rst) begin
            rptr_gray_sync1 <= {PTR_WIDTH{1'b0}};
            rptr_gray_sync2 <= {PTR_WIDTH{1'b0}};
        end else begin
            rptr_gray_sync1 <= rptr_gray;
            rptr_gray_sync2 <= rptr_gray_sync1;
        end
    end

    // Synchronizer chain: wptr_gray (from wclk domain) into rclk domain
    always @(posedge rclk or posedge rst) begin
        if (rst) begin
            wptr_gray_sync1 <= {PTR_WIDTH{1'b0}};
            wptr_gray_sync2 <= {PTR_WIDTH{1'b0}};
        end else begin
            wptr_gray_sync1 <= wptr_gray;
            wptr_gray_sync2 <= wptr_gray_sync1;
        end
    end

    // Full flag (wclk domain) – compare Gray pointers with two MSBs inverted
    assign full = (wptr_bin[ADDR_BITS-1:0] == rptr_bin[ADDR_BITS-1:0]) 
                  && (wptr_bin[PTR_WIDTH-1] != rptr_bin[PTR_WIDTH-1]);

    // Empty flag (rclk domain)
    assign empty = (wptr_bin == rptr_bin);

    // Gray-to-binary conversion for the synchronized write pointer (unrolled for PTR_WIDTH=4)
    wire [PTR_WIDTH-1:0] wptr_bin_rclk;
    assign wptr_bin_rclk[3] = wptr_gray_sync2[3];
    assign wptr_bin_rclk[2] = wptr_bin_rclk[3] ^ wptr_gray_sync2[2];
    assign wptr_bin_rclk[1] = wptr_bin_rclk[2] ^ wptr_gray_sync2[1];
    assign wptr_bin_rclk[0] = wptr_bin_rclk[1] ^ wptr_gray_sync2[0];

    // Occupancy (rclk domain)
    wire [PTR_WIDTH:0] diff_raw;
    assign diff_raw = (wptr_bin_rclk >= rptr_bin) 
                      ? (wptr_bin_rclk - rptr_bin) 
                      : (2*FIFO_TX_MEM_DEPTH + wptr_bin_rclk - rptr_bin);
    // occupancy fits in 4 bits; zero-extend to 6-bit output
    assign mem_empt = wptr_bin - rptr_bin;

    // Data output (registered, rclk domain)
    wire [ADDR_BITS-1:0] raddr;
    assign raddr = rptr_bin[ADDR_BITS-1:0];

    always @(*) begin
        q = ram[raddr*32 +: 32];
    end

endmodule
