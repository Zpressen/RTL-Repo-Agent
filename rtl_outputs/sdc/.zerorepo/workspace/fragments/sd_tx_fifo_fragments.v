// STAGE5_SUBTASK_BEGIN B1_decl_core_objects: Declare RAM storage as a 32-bit wide array of depth FIFO_TX_MEM_DEPTH, write pointer adr_i (width FIFO_RX_MEM_ADR_SIZE) 
// RAM storage as a packed vector, depth FIFO_TX_MEM_DEPTH, each word 32-bit
reg [32*FIFO_TX_MEM_DEPTH-1:0] ram_storage;

// Binary write and read pointers (packed)
reg [FIFO_RX_MEM_ADR_SIZE-1:0] adr_i;
reg [FIFO_RX_MEM_ADR_SIZE-1:0] adr_o;

// Gray-encoded copies of the pointers
reg [FIFO_RX_MEM_ADR_SIZE-1:0] wptr_gray;
reg [FIFO_RX_MEM_ADR_SIZE-1:0] rptr_gray;

// Multi‑stage synchronizer flip-flops for gray pointers
reg [FIFO_RX_MEM_ADR_SIZE-1:0] rptr_gray_sync1, rptr_gray_sync2; // in wclk domain
reg [FIFO_RX_MEM_ADR_SIZE-1:0] wptr_gray_sync1, wptr_gray_sync2; // in rclk domain
// STAGE5_SUBTASK_END B1_decl_core_objects
