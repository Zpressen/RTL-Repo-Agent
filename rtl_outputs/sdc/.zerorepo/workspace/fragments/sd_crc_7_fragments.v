// STAGE5_SUBTASK_BEGIN B1_decl_core_objects: Declare the 7‑bit CRC register and any supporting combinational wires (e.g., for inv) according to the interface and clo
// 7-bit CRC register
reg [6:0] crc_reg;

// Combinational inversion signal (to be computed in comb_inv_compute)
wire inv;

// Connect internal register to output port
assign CRC = crc_reg;
// STAGE5_SUBTASK_END B1_decl_core_objects

// STAGE5_SUBTASK_BEGIN B2_comb_inv_compute: Combinationally compute inv = BITVAL ^ CRC[6] using a continuous assignment or combinational always block.
assign inv = BITVAL ^ crc_reg[6];
// STAGE5_SUBTASK_END B2_comb_inv_compute

// STAGE5_SUBTASK_BEGIN B3_seq_crc_update: Implement the sequential CRC update: on rising CLK, asynchronous RST resets CRC to 0; else if Enable is high, shift CRC 
always @(posedge CLK or posedge RST) begin
    if (RST)
        crc_reg <= 7'b0;
    else if (Enable)
        crc_reg <= {crc_reg[5], crc_reg[4], crc_reg[3], (crc_reg[2] ^ inv), crc_reg[1], crc_reg[0], inv};
end
// STAGE5_SUBTASK_END B3_seq_crc_update
