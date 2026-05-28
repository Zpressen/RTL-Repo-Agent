module aes_rcon (
    input  clk,
    input  kld,
    output reg [31:0] out
);
reg [3:0] rcnt;
wire [3:0] next_rcnt;
wire [31:0] next_out;

function [7:0] rcon_byte;
    input [3:0] idx;
    begin
        case (idx)
            4'd0: rcon_byte = 8'h01;
            4'd1: rcon_byte = 8'h02;
            4'd2: rcon_byte = 8'h04;
            4'd3: rcon_byte = 8'h08;
            4'd4: rcon_byte = 8'h10;
            4'd5: rcon_byte = 8'h20;
            4'd6: rcon_byte = 8'h40;
            4'd7: rcon_byte = 8'h80;
            4'd8: rcon_byte = 8'h1b;
            4'd9: rcon_byte = 8'h36;
            default: rcon_byte = 8'h00;
        endcase
    end
endfunction

assign next_rcnt = kld ? 4'd0 : rcnt + 4'd1;
assign next_out = kld ? 32'h01000000 : 
                  (next_rcnt > 4'd9) ? 32'h0 : 
                  {rcon_byte(next_rcnt), 24'h000000};

always @(posedge clk) begin
    rcnt <= next_rcnt;
    out  <= next_out;
end

endmodule
