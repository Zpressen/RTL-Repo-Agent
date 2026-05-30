module sd_crc_7 (
    input BITVAL,
    input Enable,
    input CLK,
    input RST,
    output [6:0] CRC
);

    // Internal declarations
    reg [6:0] crc_reg;
    wire inv;

    // Connect internal register to output port
    assign CRC = crc_reg;

    // Combinational inversion signal
    assign inv = BITVAL ^ crc_reg[6];

    // Sequential CRC update with asynchronous reset
    always @(posedge CLK or posedge RST) begin
        if (RST)
            crc_reg <= 7'b0;
        else if (Enable)
            crc_reg <= {crc_reg[5], crc_reg[4], crc_reg[3],
                        (crc_reg[2] ^ inv), crc_reg[1], crc_reg[0],
                        inv};
    end

endmodule
