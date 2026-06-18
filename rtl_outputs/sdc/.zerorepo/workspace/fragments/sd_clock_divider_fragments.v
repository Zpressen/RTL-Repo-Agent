// STAGE5_SUBTASK_BEGIN B1_decl_core_objects: Declare internal counter register and intermediate sd_clk_o signal with widths sufficient for the division ratio (counte
// Internal signals
reg [7:0] counter;   // Counter for clock division
wire sd_clk_o;       // Intermediate output clock (pre-buffer)
// STAGE5_SUBTASK_END B1_decl_core_objects

// STAGE5_SUBTASK_BEGIN B2_seq_clock_division: Implement a sequential process sensitive to CLK and RST: on asynchronous reset, clear counter and sd_clk_o to 0; on risi
always @(posedge CLK or posedge RST) begin
    if (RST) begin
        counter <= 8'b0;
        sd_clk_o <= 1'b0;
    end else begin
        if (counter == DIVIDER) begin
            sd_clk_o <= ~sd_clk_o;
            counter <= 8'b0;
        end else begin
            counter <= counter + 1;
        end
    end
end
// STAGE5_SUBTASK_END B2_seq_clock_division

// STAGE5_SUBTASK_BEGIN B3_comb_output_path: Map the sd_clk_o signal to the top-level SD_CLK output using conditional compilation: in SIM, direct connect; in ACTEL, 
`ifdef SIM
    assign SD_CLK = sd_clk_o;
`elsif ACTEL
    CLKINT u_clk_buf (.A(sd_clk_o), .Y(SD_CLK));
`endif
// STAGE5_SUBTASK_END B3_comb_output_path
