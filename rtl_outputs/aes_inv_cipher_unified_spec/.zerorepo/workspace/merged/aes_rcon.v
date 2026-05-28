module aes_rcon (
    input         clk,
    input         kld,
    output [31:0] out
);

reg  [3:0]  rcnt;
reg  [31:0] out_reg;

localparam [79:0] RC_TABLE = {
    8'h01, 8'h02, 8'h04, 8'h08, 8'h10,
    8'h20, 8'h40, 8'h80, 8'h1B, 8'h36
};

wire [7:0]  rc_byte;
wire [31:0] next_out;

assign rc_byte  = (rcnt > 4'd9) ? 8'h00 : RC_TABLE[79 - rcnt*8 -: 8];
assign next_out = kld ? 32'h01000000 : {rc_byte, 24'h000000};

assign out = out_reg;

always @(posedge clk) begin
    if (kld) begin
        rcnt <= 4'd0;
        out_reg <= 32'h01000000;
    end else begin
        rcnt <= rcnt + 4'd1;
        case (rcnt + 4'd1)
            4'd0: out_reg <= 32'h01000000;
            4'd1: out_reg <= 32'h02000000;
            4'd2: out_reg <= 32'h04000000;
            4'd3: out_reg <= 32'h08000000;
            4'd4: out_reg <= 32'h10000000;
            4'd5: out_reg <= 32'h20000000;
            4'd6: out_reg <= 32'h40000000;
            4'd7: out_reg <= 32'h80000000;
            4'd8: out_reg <= 32'h1b000000;
            4'd9: out_reg <= 32'h36000000;
            default: out_reg <= 32'h00000000;
        endcase
    end
end

endmodule
