// STAGE5_SUBTASK_BEGIN B1_decl_core_objects: Declare the 16-bit CRC register and the 1-bit combinational intermediate wire 'inv' as specified in S002 and S004.
reg [15:0] crc_reg;
wire inv;
// STAGE5_SUBTASK_END B1_decl_core_objects

// STAGE5_SUBTASK_BEGIN B2_comb_inv_logic: Implement combinational assignment: assign inv = BITVAL ^ CRC[15];
assign inv = BITVAL ^ crc_reg[15];
// STAGE5_SUBTASK_END B2_comb_inv_logic

// STAGE5_SUBTASK_BEGIN B3_seq_crc_update: Implement sequential always block with asynchronous reset (RST high sets CRC to 0) and on posedge CLK with Enable high, 
always @(posedge CLK or posedge RST) begin
    if (RST) begin
        crc_reg[15:0] <= 16'd0;
    end else if (Enable) begin
        crc_reg[0]  <= inv;
        crc_reg[1]  <= crc_reg[0];
        crc_reg[2]  <= crc_reg[1];
        crc_reg[3]  <= crc_reg[2];
        crc_reg[4]  <= crc_reg[3];
        crc_reg[5]  <= crc_reg[4] ^ inv;
        crc_reg[6]  <= crc_reg[5];
        crc_reg[7]  <= crc_reg[6];
        crc_reg[8]  <= crc_reg[7];
        crc_reg[9]  <= crc_reg[8];
        crc_reg[10] <= crc_reg[9];
        crc_reg[11] <= crc_reg[10];
        crc_reg[12] <= crc_reg[11] ^ inv;
        crc_reg[13] <= crc_reg[12];
        crc_reg[14] <= crc_reg[13];
        crc_reg[15] <= crc_reg[14];
    end
end
// STAGE5_SUBTASK_END B3_seq_crc_update
