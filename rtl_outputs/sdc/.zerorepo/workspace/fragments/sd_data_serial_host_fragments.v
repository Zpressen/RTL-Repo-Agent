// STAGE5_SUBTASK_BEGIN B1_decl_core_objects: Declare all internal registers, wires, and parameters needed by the module: FSM state, next_state, transf_cnt, crc_c, bu
parameter SD_BUS_W = `SD_BUS_W;
parameter BIT_BLOCK = (`BLOCK_SIZE * 8);
parameter CRC_OFF = 16;
parameter BIT_BLOCK_REC = (`BLOCK_SIZE * 8) + 16;
parameter BIT_CRC_CYCLE = 16;
parameter LITLE_ENDIAN = 1'b0;
parameter BIG_ENDIAN = 1'b1;
parameter SD_BUS_WIDTH_1 = 1;
parameter SD_BUS_WIDTH_4 = 4;

reg [5:0] state;
reg [5:0] next_state;
reg [10:0] transf_cnt;
reg [4:0] crc_c;
reg out_buff_ptr;
reg in_buff_ptr;
reg [31:0] write_buf_0;
reg [31:0] write_buf_1;
reg [31:0] sd_data_out;
reg [3:0] last_din;
reg [2:0] data_send_index;
reg [SD_BUS_W-1:0] crc_in;
reg crc_en;
reg crc_rst;
reg [2:0] crc_status;
reg [2:0] crc_s;
reg busy_int;
reg ack_transfer_int;
reg ack_q;
reg q_start_bit;
reg [SD_BUS_W-1:0] temp_in;

wire [(16*SD_BUS_W)-1:0] crc_out;

reg DAT_oe_o;
reg [SD_BUS_W-1:0] DAT_dat_o;
reg rd;
reg we;
reg [SD_BUS_W-1:0] data_out;
reg transm_complete;
reg crc_ok;
reg busy_n;
// STAGE5_SUBTASK_END B1_decl_core_objects

// STAGE5_SUBTASK_BEGIN B2_inst_CRC16_gen: Instantiate one sd_crc_16 per data line (SD_BUS_W instances). Connect crc_in[i] to BITVAL, crc_en to Enable, crc_rst to 
sd_crc_16 CRC_16_gen_0 (
    .BITVAL(crc_in[0]),
    .Enable(crc_en),
    .CLK(sd_clk),
    .RST(crc_rst),
    .CRC(crc_out[15:0])
);

sd_crc_16 CRC_16_gen_1 (
    .BITVAL(crc_in[1]),
    .Enable(crc_en),
    .CLK(sd_clk),
    .RST(crc_rst),
    .CRC(crc_out[31:16])
);

sd_crc_16 CRC_16_gen_2 (
    .BITVAL(crc_in[2]),
    .Enable(crc_en),
    .CLK(sd_clk),
    .RST(crc_rst),
    .CRC(crc_out[47:32])
);

sd_crc_16 CRC_16_gen_3 (
    .BITVAL(crc_in[3]),
    .Enable(crc_en),
    .CLK(sd_clk),
    .RST(crc_rst),
    .CRC(crc_out[63:48])
);
// STAGE5_SUBTASK_END B2_inst_CRC16_gen

// STAGE5_SUBTASK_BEGIN B3_seq_ACK_SYNC: Implement a two‑stage flip‑flop synchronizer for ack_transfer: on posedge sd_clk, ack_q <= ack_transfer, then ack_transf
always @(posedge sd_clk or posedge rst) begin
    if (rst) begin
        ack_q <= 1'b0;
        ack_transfer_int <= 1'b0;
    end else begin
        ack_q <= ack_transfer;
        ack_transfer_int <= ack_q;
    end
end
// STAGE5_SUBTASK_END B3_seq_ACK_SYNC

// STAGE5_SUBTASK_BEGIN B4_seq_START_SYNC: Register q_start_bit: reset to 1; on sd_clk edge, if state == READ_WAIT and DAT_dat_i[0] == 0, set q_start_bit to 0; oth
always @(posedge sd_clk or posedge rst) begin
    if (rst) begin
        q_start_bit <= 1'b1;
    end else begin
        if ((state == READ_WAIT) && (DAT_dat_i[0] == 1'b0)) begin
            q_start_bit <= 1'b0;
        end else begin
            q_start_bit <= 1'b1;
        end
    end
end
// STAGE5_SUBTASK_END B4_seq_START_SYNC

// STAGE5_SUBTASK_BEGIN B5_comb_FSM_COMBO: Combinational logic that computes next_state from current state and inputs (start_dat, transf_cnt, crc_status, busy_int,
parameter IDLE       = 6'b000001;
parameter WRITE_DAT  = 6'b000010;
parameter WRITE_CRC  = 6'b000100;
parameter WRITE_BUSY = 6'b001000;
parameter READ_WAIT  = 6'b010000;
parameter READ_DAT   = 6'b100000;
parameter OK         = 3'b001;

always @(state or start_dat or transf_cnt or crc_status or busy_int or DAT_dat_i) begin
    next_state = IDLE;

    case (state)
        IDLE: begin
            if (start_dat) begin
                next_state = WRITE_DAT;
            end else begin
                next_state = IDLE;
            end
        end

        WRITE_DAT: begin
            if (transf_cnt == SD_BUS_W) begin
                next_state = WRITE_CRC;
            end else begin
                next_state = WRITE_DAT;
            end
        end

        WRITE_CRC: begin
            if (crc_status == OK) begin
                next_state = WRITE_BUSY;
            end else begin
                next_state = WRITE_CRC;
            end
        end

        WRITE_BUSY: begin
            if (busy_int == 1'b0) begin
                next_state = IDLE;
            end else begin
                next_state = WRITE_BUSY;
            end
        end

        READ_WAIT: begin
            if (DAT_dat_i[0] == 1'b0) begin
                next_state = READ_DAT;
            end else begin
                next_state = READ_WAIT;
            end
        end

        READ_DAT: begin
            if (transf_cnt == SD_BUS_W) begin
                next_state = IDLE;
            end else begin
                next_state = READ_DAT;
            end
        end

        default: begin
            next_state = IDLE;
        end
    endcase
end
// STAGE5_SUBTASK_END B5_comb_FSM_COMBO

// STAGE5_SUBTASK_BEGIN B6_seq_FSM_SEQ: Sequential block: on posedge sd_clk, state <= next_state; asynchronous reset sets state to IDLE.
always @(posedge sd_clk or posedge rst) begin
    if (rst) begin
        state <= IDLE;
    end else begin
        state <= next_state;
    end
end
// STAGE5_SUBTASK_END B6_seq_FSM_SEQ

// STAGE5_SUBTASK_BEGIN B7_seq_FSM_OUT: Main output and control logic. On reset, assign all registers according to the S013 reset table. In normal operation, ma
always @(posedge sd_clk or posedge rst) begin
    if (rst) begin
        write_buf_0 <= 32'b0;
        write_buf_1 <= 32'b0;
        DAT_oe_o <= 1'b0;
        crc_en <= 1'b0;
        crc_rst <= 1'b1;
        transf_cnt <= 11'b0;
        rd <= 1'b0;
        last_din <= 4'b0;
        crc_c <= 5'b0;
        crc_in <= {SD_BUS_W{1'b0}};
        DAT_dat_o <= {SD_BUS_W{1'b0}};
        crc_status <= 3'd7;
        crc_s <= 3'b0;
        transm_complete <= 1'b0;
        busy_n <= 1'b1;
        we <= 1'b0;
        data_out <= {SD_BUS_W{1'b0}};
        crc_ok <= 1'b0;
        busy_int <= 1'b0;
        data_send_index <= 3'b0;
        out_buff_ptr <= 1'b0;
        in_buff_ptr <= 1'b0;
        sd_data_out <= 32'b0;
        temp_in <= {SD_BUS_W{1'b0}};
    end else begin
        rd <= 1'b0;
        we <= 1'b0;
        transm_complete <= 1'b0;

        case (state)
            IDLE: begin
                DAT_oe_o <= 1'b0;
                DAT_dat_o <= {SD_BUS_W{1'b1}};
                crc_en <= 1'b0;
                crc_rst <= 1'b1;
                crc_in <= {SD_BUS_W{1'b0}};
                last_din <= 4'b0;
                crc_c <= 5'b0;
                crc_status <= 3'd7;
                crc_s <= 3'b0;
                transf_cnt <= 11'b0;
                data_send_index <= 3'b0;
                out_buff_ptr <= 1'b0;
                in_buff_ptr <= 1'b0;
                busy_int <= 1'b0;
                busy_n <= 1'b1;
                crc_ok <= 1'b0;
            end

            WRITE_DAT: begin
                DAT_oe_o <= 1'b1;
                crc_rst <= 1'b0;
                busy_n <= 1'b0;
                transm_complete <= 1'b0;

                if (transf_cnt == 11'd0) begin
                    rd <= 1'b1;
                    write_buf_0 <= data_in;
                    sd_data_out <= data_in;
                    DAT_dat_o <= {SD_BUS_W{1'b0}};
                    crc_in <= {SD_BUS_W{1'b0}};
                    last_din <= {SD_BUS_W{1'b0}};
                    crc_en <= 1'b0;
                    data_send_index <= 3'b0;
                    in_buff_ptr <= 1'b1;
                    out_buff_ptr <= 1'b0;
                    transf_cnt <= transf_cnt + 11'd1;
                end else if (transf_cnt <= (BIT_BLOCK / SD_BUS_W)) begin
                    crc_en <= 1'b1;
                    DAT_dat_o <= last_din;
                    crc_in <= sd_data_out[31:28];
                    last_din <= sd_data_out[31:28];
                    sd_data_out <= {sd_data_out[27:0], 4'b0};

                    if (data_send_index == 3'd7) begin
                        rd <= 1'b1;
                        data_send_index <= 3'b0;
                        if (in_buff_ptr == 1'b0) begin
                            write_buf_0 <= data_in;
                            in_buff_ptr <= 1'b1;
                        end else begin
                            write_buf_1 <= data_in;
                            in_buff_ptr <= 1'b0;
                        end
                        if (out_buff_ptr == 1'b0) begin
                            sd_data_out <= write_buf_1;
                            out_buff_ptr <= 1'b1;
                        end else begin
                            sd_data_out <= write_buf_0;
                            out_buff_ptr <= 1'b0;
                        end
                    end else begin
                        data_send_index <= data_send_index + 3'd1;
                    end

                    transf_cnt <= transf_cnt + 11'd1;
                end else if (crc_c < BIT_CRC_CYCLE) begin
                    crc_en <= 1'b0;
                    DAT_dat_o[0] <= crc_out[15 - crc_c];
                    DAT_dat_o[1] <= crc_out[31 - crc_c];
                    DAT_dat_o[2] <= crc_out[47 - crc_c];
                    DAT_dat_o[3] <= crc_out[63 - crc_c];
                    crc_c <= crc_c + 5'd1;
                end else begin
                    crc_en <= 1'b0;
                    DAT_dat_o <= {SD_BUS_W{1'b1}};
                    crc_status <= 3'b0;
                    crc_c <= 5'b0;
                    transf_cnt <= 11'b0;
                end
            end

            WRITE_CRC: begin
                DAT_oe_o <= 1'b0;
                crc_en <= 1'b0;
                crc_rst <= 1'b1;
                if (crc_status < 3'd7) begin
                    crc_status <= crc_status + 3'd1;
                    if (crc_status == 3'd3) begin
                        crc_s[2] <= DAT_dat_i[0];
                    end else if (crc_status == 3'd4) begin
                        crc_s[1] <= DAT_dat_i[0];
                    end else if (crc_status == 3'd5) begin
                        crc_s[0] <= DAT_dat_i[0];
                    end
                end
            end

            WRITE_BUSY: begin
                DAT_oe_o <= 1'b0;
                crc_en <= 1'b0;
                crc_rst <= 1'b1;
                transm_complete <= 1'b1;
                if (crc_s == OK) begin
                    crc_ok <= 1'b1;
                end else begin
                    crc_ok <= 1'b0;
                end
                if (DAT_dat_i[0] == 1'b1) begin
                    busy_int <= 1'b0;
                    busy_n <= 1'b1;
                end else begin
                    busy_int <= 1'b1;
                    busy_n <= 1'b0;
                end
            end

            READ_WAIT: begin
                DAT_oe_o <= 1'b0;
                DAT_dat_o <= {SD_BUS_W{1'b1}};
                crc_rst <= 1'b0;
                crc_en <= 1'b1;
                crc_in <= {SD_BUS_W{1'b0}};
                transf_cnt <= 11'b0;
                crc_c <= 5'b0;
                crc_ok <= 1'b1;
                transm_complete <= 1'b0;
                busy_n <= 1'b0;
            end

            READ_DAT: begin
                DAT_oe_o <= 1'b0;
                crc_rst <= 1'b0;
                busy_n <= 1'b0;
                temp_in <= DAT_dat_i;

                if (transf_cnt < (BIT_BLOCK / SD_BUS_W)) begin
                    crc_en <= 1'b1;
                    crc_in <= DAT_dat_i;
                    data_out <= DAT_dat_i;
                    we <= 1'b1;
                    transf_cnt <= transf_cnt + 11'd1;
                end else if (crc_c < BIT_CRC_CYCLE) begin
                    crc_en <= 1'b0;
                    if (SD_BUS_W == SD_BUS_WIDTH_4) begin
                        if (DAT_dat_i[0] != crc_out[15 - crc_c]) begin
                            crc_ok <= 1'b0;
                        end
                        if (DAT_dat_i[1] != crc_out[31 - crc_c]) begin
                            crc_ok <= 1'b0;
                        end
                        if (DAT_dat_i[2] != crc_out[47 - crc_c]) begin
                            crc_ok <= 1'b0;
                        end
                        if (DAT_dat_i[3] != crc_out[63 - crc_c]) begin
                            crc_ok <= 1'b0;
                        end
                    end else begin
                        if (DAT_dat_i[0] != crc_out[15 - crc_c]) begin
                            crc_ok <= 1'b0;
                        end
                    end
                    crc_c <= crc_c + 5'd1;
                end else begin
                    crc_en <= 1'b0;
                    transm_complete <= 1'b1;
                    busy_n <= 1'b1;
                    transf_cnt <= 11'b0;
                    crc_c <= 5'b0;
                end
            end

            default: begin
                DAT_oe_o <= 1'b0;
                crc_en <= 1'b0;
                crc_rst <= 1'b1;
                busy_n <= 1'b1;
            end
        endcase
    end
end
// STAGE5_SUBTASK_END B7_seq_FSM_OUT
