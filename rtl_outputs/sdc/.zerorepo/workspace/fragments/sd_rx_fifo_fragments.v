// STAGE5_SUBTASK_BEGIN B1_decl_parameters_and_registers: Declare FIFO_RX_MEM_DEPTH and FIFO_RX_MEM_ADR_SIZE parameters; define RAM storage as an explicitly unrolled set of 32-bi
parameter FIFO_RX_MEM_DEPTH = 4;
parameter FIFO_RX_MEM_ADR_SIZE = 2;

reg [31:0] ram_0;
reg [31:0] ram_1;
reg [31:0] ram_2;
reg [31:0] ram_3;

reg [FIFO_RX_MEM_ADR_SIZE:0] adr_i;
reg [FIFO_RX_MEM_ADR_SIZE:0] adr_o;
reg [31:0] tmp;
reg [7:0] we;
reg ft;
// STAGE5_SUBTASK_END B1_decl_parameters_and_registers

// STAGE5_SUBTASK_BEGIN B2_seq_write_domain: On wclk rising edge, when wr is high, accumulate 4‑bit d into tmp according to we’s current bit position; shift we left 
always @(posedge wclk or posedge rst) begin
    if (rst) begin
        tmp <= 32'h00000000;
        we <= 8'h01;
        ft <= 1'b0;
        adr_i <= {FIFO_RX_MEM_ADR_SIZE + 1{1'b0}};
    end else begin
        if (wr) begin
            if (we[0]) begin
                tmp[3:0] <= d;
                we <= 8'h02;
            end else if (we[1]) begin
                tmp[7:4] <= d;
                we <= 8'h04;
            end else if (we[2]) begin
                tmp[11:8] <= d;
                we <= 8'h08;
            end else if (we[3]) begin
                tmp[15:12] <= d;
                we <= 8'h10;
            end else if (we[4]) begin
                tmp[19:16] <= d;
                we <= 8'h20;
            end else if (we[5]) begin
                tmp[23:20] <= d;
                we <= 8'h40;
            end else if (we[6]) begin
                tmp[27:24] <= d;
                we <= 8'h80;
            end else begin
                tmp[31:28] <= d;
                we <= 8'h01;
                ft <= 1'b1;

                if (adr_i[FIFO_RX_MEM_ADR_SIZE-1:0] == (FIFO_RX_MEM_DEPTH-1)) begin
                    adr_i[FIFO_RX_MEM_ADR_SIZE-1:0] <= {FIFO_RX_MEM_ADR_SIZE{1'b0}};
                    adr_i[FIFO_RX_MEM_ADR_SIZE] <= ~adr_i[FIFO_RX_MEM_ADR_SIZE];
                end else begin
                    adr_i[FIFO_RX_MEM_ADR_SIZE-1:0] <= adr_i[FIFO_RX_MEM_ADR_SIZE-1:0] + 1'b1;
                end

                if (adr_i[FIFO_RX_MEM_ADR_SIZE-1:0] == 2'd0) begin
                    ram_0 <= {d, tmp[27:0]};
                end else if (adr_i[FIFO_RX_MEM_ADR_SIZE-1:0] == 2'd1) begin
                    ram_1 <= {d, tmp[27:0]};
                end else if (adr_i[FIFO_RX_MEM_ADR_SIZE-1:0] == 2'd2) begin
                    ram_2 <= {d, tmp[27:0]};
                end else begin
                    ram_3 <= {d, tmp[27:0]};
                end
            end
        end
    end
end
// STAGE5_SUBTASK_END B2_seq_write_domain

// STAGE5_SUBTASK_BEGIN B3_seq_read_domain: On rclk rising edge, if rd is high and empty is deasserted, increment adr_o with wrap‑around and high‑bit toggle; presen
always @(posedge rclk or posedge rst) begin
    if (rst) begin
        adr_o <= {FIFO_RX_MEM_ADR_SIZE + 1{1'b0}};
        q <= 32'h00000000;
    end else begin
        if (rd && !empty) begin
            if (adr_o[FIFO_RX_MEM_ADR_SIZE-1:0] == 2'd0) begin
                q <= ram_0;
            end else if (adr_o[FIFO_RX_MEM_ADR_SIZE-1:0] == 2'd1) begin
                q <= ram_1;
            end else if (adr_o[FIFO_RX_MEM_ADR_SIZE-1:0] == 2'd2) begin
                q <= ram_2;
            end else begin
                q <= ram_3;
            end

            if (adr_o[FIFO_RX_MEM_ADR_SIZE-1:0] == (FIFO_RX_MEM_DEPTH-1)) begin
                adr_o[FIFO_RX_MEM_ADR_SIZE-1:0] <= {FIFO_RX_MEM_ADR_SIZE{1'b0}};
                adr_o[FIFO_RX_MEM_ADR_SIZE] <= ~adr_o[FIFO_RX_MEM_ADR_SIZE];
            end else begin
                adr_o[FIFO_RX_MEM_ADR_SIZE-1:0] <= adr_o[FIFO_RX_MEM_ADR_SIZE-1:0] + 1'b1;
            end
        end
    end
end
// STAGE5_SUBTASK_END B3_seq_read_domain

// STAGE5_SUBTASK_BEGIN B4_seq_flag_synchronization: Generate full, empty, and mem_empt flags. Synchronize write pointer adr_i into rclk domain and read pointer adr_o into w
reg adr_i_rclk_sync1_0;
reg adr_i_rclk_sync1_1;
reg adr_i_rclk_sync1_2;
reg adr_i_rclk_sync2_0;
reg adr_i_rclk_sync2_1;
reg adr_i_rclk_sync2_2;

reg adr_o_wclk_sync1_0;
reg adr_o_wclk_sync1_1;
reg adr_o_wclk_sync1_2;
reg adr_o_wclk_sync2_0;
reg adr_o_wclk_sync2_1;
reg adr_o_wclk_sync2_2;

wire [FIFO_RX_MEM_ADR_SIZE:0] adr_i_rclk_sync;
wire [FIFO_RX_MEM_ADR_SIZE:0] adr_o_wclk_sync;
wire [FIFO_RX_MEM_ADR_SIZE:0] used_words_ext;
wire [FIFO_RX_MEM_ADR_SIZE:0] free_words_ext;

assign adr_i_rclk_sync = {adr_i_rclk_sync2_2, adr_i_rclk_sync2_1, adr_i_rclk_sync2_0};
assign adr_o_wclk_sync = {adr_o_wclk_sync2_2, adr_o_wclk_sync2_1, adr_o_wclk_sync2_0};

always @(posedge rclk or posedge rst) begin
    if (rst) begin
        adr_i_rclk_sync1_0 <= 1'b0;
        adr_i_rclk_sync1_1 <= 1'b0;
        adr_i_rclk_sync1_2 <= 1'b0;
        adr_i_rclk_sync2_0 <= 1'b0;
        adr_i_rclk_sync2_1 <= 1'b0;
        adr_i_rclk_sync2_2 <= 1'b0;
        empty <= 1'b1;
    end else begin
        adr_i_rclk_sync1_0 <= adr_i[0];
        adr_i_rclk_sync1_1 <= adr_i[1];
        adr_i_rclk_sync1_2 <= adr_i[2];
        adr_i_rclk_sync2_0 <= adr_i_rclk_sync1_0;
        adr_i_rclk_sync2_1 <= adr_i_rclk_sync1_1;
        adr_i_rclk_sync2_2 <= adr_i_rclk_sync1_2;

        if ((adr_i_rclk_sync2_2 == adr_o[FIFO_RX_MEM_ADR_SIZE]) &&
            (adr_i_rclk_sync2_1 == adr_o[1]) &&
            (adr_i_rclk_sync2_0 == adr_o[0])) begin
            empty <= 1'b1;
        end else begin
            empty <= 1'b0;
        end
    end
end

always @(posedge wclk or posedge rst) begin
    if (rst) begin
        adr_o_wclk_sync1_0 <= 1'b0;
        adr_o_wclk_sync1_1 <= 1'b0;
        adr_o_wclk_sync1_2 <= 1'b0;
        adr_o_wclk_sync2_0 <= 1'b0;
        adr_o_wclk_sync2_1 <= 1'b0;
        adr_o_wclk_sync2_2 <= 1'b0;
        full <= 1'b0;
    end else begin
        adr_o_wclk_sync1_0 <= adr_o[0];
        adr_o_wclk_sync1_1 <= adr_o[1];
        adr_o_wclk_sync1_2 <= adr_o[2];
        adr_o_wclk_sync2_0 <= adr_o_wclk_sync1_0;
        adr_o_wclk_sync2_1 <= adr_o_wclk_sync1_1;
        adr_o_wclk_sync2_2 <= adr_o_wclk_sync1_2;

        if ((adr_i[FIFO_RX_MEM_ADR_SIZE] != adr_o_wclk_sync2_2) &&
            (adr_i[1] == adr_o_wclk_sync2_1) &&
            (adr_i[0] == adr_o_wclk_sync2_0)) begin
            full <= 1'b1;
        end else begin
            full <= 1'b0;
        end
    end
end

assign used_words_ext = adr_i_rclk_sync - adr_o;
assign free_words_ext = FIFO_RX_MEM_DEPTH[2:0] - used_words_ext;
assign mem_empt = free_words_ext[FIFO_RX_MEM_ADR_SIZE-1:0];
// STAGE5_SUBTASK_END B4_seq_flag_synchronization

// STAGE5_SUBTASK_BEGIN B5_comb_data_and_space_output: If q and mem_empt are not already driven in B3 or B4, provide purely combinational assignments: q from the RAM location 
// q is already driven in B3_seq_read_domain.
// mem_empt is already driven in B4_seq_flag_synchronization.
// STAGE5_SUBTASK_END B5_comb_data_and_space_output
