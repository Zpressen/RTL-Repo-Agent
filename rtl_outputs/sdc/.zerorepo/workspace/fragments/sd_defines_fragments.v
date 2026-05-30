// STAGE5_SUBTASK_BEGIN B1_decl_macros_and_defines: Generate preprocessor `define` statements for all configuration macros listed in the spec table, including mutual exclus
// Endianness: choose one
`define BIG_ENDIAN
//`define LITTLE_ENDIAN

// Simulation or Synthesis: choose one
//`define SIM
`define SYN

// Enable three extra interrupt pins
`define SDC_IRQ_ENABLE

// Actel-specific settings (predefine)
`define ACTEL

// Block Descriptor (BD) buffer size and width
`define BD_SIZE 8
// BD_WIDTH must equal $clog2(BD_SIZE)
`define BD_WIDTH 3

// RAM memory width and mode
`define RAM_MEM_WIDTH 32
//`define RAM_MEM_WIDTH_16  // define only when RAM_MEM_WIDTH == 16

// Maximum number of resend retries
`define RESEND_MAX_CNT 3

// Memory address offset between two words (in word addresses)
`define MEM_OFFSET 2

// Reset value for the clock divider
`define RESET_CLK_DIV 7

// SD Clock selection: choose one
`define SD_CLK_BUS_CLK
//`define SD_CLK_SEP
//`define SD_CLK_STATIC
//`define SD_CLK_DYNAMIC

// Block size (fixed)
`define BLOCK_SIZE 512

// SD bus width: only 4-bit supported
`define SD_BUS_WIDTH_4
`define SD_BUS_W 4

// FIFO depths and address sizes
`define FIFO_RX_MEM_DEPTH 16
// FIFO_RX_MEM_ADR_SIZE = $clog2(FIFO_RX_MEM_DEPTH) + 1
`define FIFO_RX_MEM_ADR_SIZE 5

`define FIFO_TX_MEM_DEPTH 8
`define FIFO_TX_MEM_ADR_SIZE 4
// STAGE5_SUBTASK_END B1_decl_macros_and_defines
