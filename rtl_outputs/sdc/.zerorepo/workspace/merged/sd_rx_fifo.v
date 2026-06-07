module sd_rx_fifo (
    input [3:0] d,
    input wr,
    input wclk,
    output [31:0] q,
    input rd,
    output full,
    output empty,
    output [1:0] mem_empt,
    input rclk,
    input rst
);

localparam FIFO_RX_MEM_DEPTH = 8;
localparam FIFO_RX_MEM_ADR_SIZE = 4;

// RAM storage unrolled
reg [31:0] ram_0, ram_1, ram_2, ram_3, ram_4, ram_5, ram_6, ram_7;

// Write and read pointers (4 bits: [3] = wrap flag, [2:0] = index)
reg [FIFO_RX_MEM_ADR_SIZE-1:0] adr_i;
reg [FIFO_RX_MEM_ADR_SIZE-1:0] adr_o;

// Accumulation registers
reg [31:0] tmp;
reg [7:0] we;
reg ft;
reg ram_we_pend;  // pending RAM write

// Write domain: accumulate 4-bit data, build 32-bit words, write to RAM
always @(posedge wclk or posedge rst) begin
    if (rst) begin
        tmp <= 32'h0;
        we <= 8'h01;
        ft <= 1'b0;
        adr_i <= 4'h0;
        ram_we_pend <= 1'b0;
    end else begin
        if (wr) begin
            if (ram_we_pend) begin
                // Write the previously accumulated word to RAM
                case (adr_i[2:0])
                    3'd0: ram_0 <= tmp;
                    3'd1: ram_1 <= tmp;
                    3'd2: ram_2 <= tmp;
                    3'd3: ram_3 <= tmp;
                    3'd4: ram_4 <= tmp;
                    3'd5: ram_5 <= tmp;
                    3'd6: ram_6 <= tmp;
                    3'd7: ram_7 <= tmp;
                    default: ;
                endcase
                // increment write pointer with wrap
                if (adr_i[2:0] == 3'd7) begin
                    adr_i[2:0] <= 3'd0;
                    adr_i[3] <= ~adr_i[3];
                end else begin
                    adr_i[2:0] <= adr_i[2:0] + 1'b1;
                end
                // Clear pending flag
                ram_we_pend <= 1'b0;
                // Accumulate first byte of next word (MSB)
                tmp[31:28] <= d;
                we <= 8'h02;
            end else begin
                // Normal accumulation
                if (we[0]) begin
                    tmp[31:28] <= d;
                    we <= 8'h02;
                end else if (we[1]) begin
                    tmp[27:24] <= d;
                    we <= 8'h04;
                end else if (we[2]) begin
                    tmp[23:20] <= d;
                    we <= 8'h08;
                end else if (we[3]) begin
                    tmp[19:16] <= d;
                    we <= 8'h10;
                end else if (we[4]) begin
                    tmp[15:12] <= d;
                    we <= 8'h20;
                end else if (we[5]) begin
                    tmp[11:8] <= d;
                    we <= 8'h40;
                end else if (we[6]) begin
                    tmp[7:4] <= d;
                    we <= 8'h80;
                end else begin // we[7]
                    tmp[3:0] <= d;
                    we <= 8'h01;
                    ft <= 1'b1;
                    ram_we_pend <= 1'b1;
                end
            end
        end
    end
end

// Read domain: output data (combinational) and increment read pointer
assign q = (adr_o[2:0] == 3'd0) ? ram_0 :
           (adr_o[2:0] == 3'd1) ? ram_1 :
           (adr_o[2:0] == 3'd2) ? ram_2 :
           (adr_o[2:0] == 3'd3) ? ram_3 :
           (adr_o[2:0] == 3'd4) ? ram_4 :
           (adr_o[2:0] == 3'd5) ? ram_5 :
           (adr_o[2:0] == 3'd6) ? ram_6 :
           (adr_o[2:0] == 3'd7) ? ram_7 : 32'h0;

always @(posedge rclk or posedge rst) begin
    if (rst) begin
        adr_o <= 4'h0;
    end else begin
        if (rd && !empty) begin
            // increment read pointer with wrap
            if (adr_o[2:0] == 3'd7) begin
                adr_o[2:0] <= 3'd0;
                adr_o[3] <= ~adr_o[3];
            end else begin
                adr_o[2:0] <= adr_o[2:0] + 1'b1;
            end
        end
    end
end

// Combinational empty and full flags
assign empty = (adr_i == adr_o);
assign full = (adr_i[3] != adr_o[3]) && (adr_i[2:0] == adr_o[2:0]);

// Memory empty space output (used words, low 2 bits)
wire [3:0] used_words;
assign used_words = adr_i - adr_o;
assign mem_empt = used_words[1:0];

endmodule
