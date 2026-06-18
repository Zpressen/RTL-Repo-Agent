module sd_clock_divider (
    input        CLK,
    input  [7:0] DIVIDER,
    input        RST,
    output       SD_CLK
);

wire [7:0] next_counter;
reg  [7:0] counter;
reg        sd_clk_div;
wire       sd_clk_o;

assign next_counter = (counter == DIVIDER) ? 8'd0 : counter + 8'd1;

assign sd_clk_o = sd_clk_div;

always @(posedge CLK or posedge RST) begin
    if (RST) begin
        counter     <= 8'd0;
        sd_clk_div  <= 1'b0;
    end else begin
        counter    <= next_counter;
        sd_clk_div <= (next_counter == 8'd0) ? ~sd_clk_div : sd_clk_div;
    end
end

`ifdef SIM
    assign SD_CLK = sd_clk_o;
`elsif ACTEL
    CLKINT u_clk_buf (.A(sd_clk_o), .Y(SD_CLK));
`else
    assign SD_CLK = sd_clk_o;
`endif

endmodule
