`timescale 1ns / 1ps

module tb_aes_cipher_top;
    reg         clk;
    reg         rst;
    reg         ld;
    reg [127:0] key;
    reg [127:0] text_in;
    wire        done;
    wire [127:0] text_out;

    localparam [127:0] TV_KEY  = 128'h00010203_04050607_08090a0b_0c0d0e0f;
    localparam [127:0] TV_PT   = 128'h00112233_44556677_8899aabb_ccddeeff;
    localparam [127:0] TV_CT   = 128'h69c4e0d8_6a7b0430_d8cdb780_70b4c55a;

    aes_cipher_top dut (
        .clk(clk),
        .rst(rst),
        .ld(ld),
        .done(done),
        .key(key),
        .text_in(text_in),
        .text_out(text_out)
    );

    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    initial begin
        rst     = 1'b1;
        ld      = 1'b0;
        key     = 128'd0;
        text_in = 128'd0;

        repeat (2) @(posedge clk);
        rst <= 1'b0;

        @(posedge clk);
        key     <= TV_KEY;
        text_in <= TV_PT;
        ld      <= 1'b1;

        @(posedge clk);
        ld <= 1'b0;

        wait (done === 1'b1);
        @(posedge clk);

        if (text_out !== TV_CT) begin
            $display("AES-128 test vector mismatch");
            $display("Expected: %032x", TV_CT);
            $display("Actual  : %032x", text_out);
            $fatal(1);
        end

        $display("AES-128 test vector passed: %032x", text_out);
        $finish;
    end
endmodule
