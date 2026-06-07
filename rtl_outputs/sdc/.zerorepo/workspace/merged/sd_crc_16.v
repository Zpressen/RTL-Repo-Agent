module sd_crc_16 (
    input BITVAL,
    input Enable,
    input CLK,
    input RST,
    output [15:0] CRC
);

reg [15:0] crc_reg;
wire inv;

assign inv = BITVAL ^ crc_reg[15];
assign CRC = crc_reg;

always @(posedge CLK or posedge RST) begin
    if (RST) begin
        crc_reg <= 16'd0;
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

endmodule
