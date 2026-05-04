`timescale 1ns / 1ps

module aes_rcon (
    input  wire       clk,
    input  wire       kld,
    output reg [31:0] out
);
    reg [3:0] rcnt;

    function [31:0] rcon_lut;
        input [3:0] idx;
        begin
            case (idx)
                4'd0:    rcon_lut = 32'h01_00_00_00;
                4'd1:    rcon_lut = 32'h02_00_00_00;
                4'd2:    rcon_lut = 32'h04_00_00_00;
                4'd3:    rcon_lut = 32'h08_00_00_00;
                4'd4:    rcon_lut = 32'h10_00_00_00;
                4'd5:    rcon_lut = 32'h20_00_00_00;
                4'd6:    rcon_lut = 32'h40_00_00_00;
                4'd7:    rcon_lut = 32'h80_00_00_00;
                4'd8:    rcon_lut = 32'h1b_00_00_00;
                4'd9:    rcon_lut = 32'h36_00_00_00;
                default: rcon_lut = 32'h00_00_00_00;
            endcase
        end
    endfunction

    always @(posedge clk) begin
        if (kld) begin
            rcnt <= 4'd0;
            out  <= 32'h01_00_00_00;
        end else begin
            rcnt <= rcnt + 4'd1;
            out  <= rcon_lut(rcnt + 4'd1);
        end
    end
endmodule
