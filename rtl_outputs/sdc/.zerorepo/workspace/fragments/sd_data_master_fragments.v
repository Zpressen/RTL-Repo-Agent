// STAGE5_SUBTASK_BEGIN B1_param_decl: Declare all parameters and localparams including FSM one‑hot state encoding (SIZE, IDLE, STOP_SEND, …), command constant
parameter CMD24 = 16'h181A;
parameter CMD17 = 16'h111A;
parameter CMD12 = 16'h0C1A;
parameter ACMD13 = 16'h0D1A;
parameter ACMD51 = 16'h331A;

parameter SIZE = 9;
parameter IDLE = 9'b000000001;
parameter GET_TX_BD = 9'b000000010;
parameter GET_RX_BD = 9'b000000100;
parameter SEND_CMD = 9'b000001000;
parameter RECIVE_CMD = 9'b000010000;
parameter DATA_TRANSFER = 9'b000100000;
parameter STOP = 9'b001000000;
parameter STOP_SEND = 9'b010000000;
parameter RESEND_MAX_CNT = `RESEND_MAX_CNT;

`ifdef RAM_MEM_WIDTH_32
parameter READ_CYCLE = 2;
parameter BD_EMPTY = (`BD_SIZE / 2);
reg [1:0] bd_cnt;
`elsif RAM_MEM_WIDTH_16
parameter READ_CYCLE = 4;
parameter BD_EMPTY = (`BD_SIZE / 4);
reg [2:0] bd_cnt;
`else
parameter READ_CYCLE = 2;
parameter BD_EMPTY = (`BD_SIZE / 2);
reg [1:0] bd_cnt;
`endif
// STAGE5_SUBTASK_END B1_param_decl

// STAGE5_SUBTASK_BEGIN B2_decl_registers: Declare all internal registers listed in S007 with their exact bit‑widths: state, next_state (9 bits), bd_cnt (width fro
reg send_done;
reg rec_done;
reg rec_failed;
reg tx_cycle;
reg rx_cycle;
reg [2:0] resend_try_cnt;
reg [8:0] state;
reg [8:0] next_state;
reg trans_done;
reg trans_failed;
reg internal_transm_complete;
reg transm_complete_q;
reg [31:0] sys_adr;
reg [31:0] cmd_arg;
reg [15:0] cmd_set;
reg CIDAT;
reg [7:0] Dat_Int_Status;
// STAGE5_SUBTASK_END B2_decl_registers

// STAGE5_SUBTASK_BEGIN B3_comb_fsm_ns: Combinational logic block that computes next_state from current state and relevant inputs/registers exactly as specified
always_comb begin
    next_state = state;

    case (state)
        IDLE: begin
            if (free_tx_bd != BD_EMPTY) begin
                next_state = GET_TX_BD;
            end else if (free_rx_bd != BD_EMPTY) begin
                next_state = GET_RX_BD;
            end else begin
                next_state = IDLE;
            end
        end

        GET_TX_BD: begin
            if ((bd_cnt > (READ_CYCLE - 1)) && (tx_full == 1'b1)) begin
                next_state = SEND_CMD;
            end else begin
                next_state = GET_TX_BD;
            end
        end

        GET_RX_BD: begin
            if (bd_cnt >= (READ_CYCLE - 1)) begin
                next_state = SEND_CMD;
            end else begin
                next_state = GET_RX_BD;
            end
        end

        SEND_CMD: begin
            if (send_done == 1'b1) begin
                next_state = RECIVE_CMD;
            end else begin
                next_state = SEND_CMD;
            end
        end

        RECIVE_CMD: begin
            if (rec_done == 1'b1) begin
                next_state = DATA_TRANSFER;
            end else if (rec_failed == 1'b1) begin
                next_state = SEND_CMD;
            end else begin
                next_state = RECIVE_CMD;
            end
        end

        DATA_TRANSFER: begin
            if (trans_done == 1'b1) begin
                next_state = IDLE;
            end else if (trans_failed == 1'b1) begin
                next_state = STOP;
            end else begin
                next_state = DATA_TRANSFER;
            end
        end

        STOP: begin
            next_state = STOP_SEND;
        end

        STOP_SEND: begin
            if (send_done == 1'b1) begin
                next_state = IDLE;
            end else begin
                next_state = STOP_SEND;
            end
        end

        default: begin
            next_state = IDLE;
        end
    endcase
end
// STAGE5_SUBTASK_END B3_comb_fsm_ns

// STAGE5_SUBTASK_BEGIN B4_seq_fsm_and_reg_update: Single sequential always_ff block with asynchronous reset: on reset set state <= IDLE and clear all registers; on posedg
always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
        state <= IDLE;
        send_done <= 1'b0;
        rec_done <= 1'b0;
        rec_failed <= 1'b0;
        tx_cycle <= 1'b0;
        rx_cycle <= 1'b0;
        resend_try_cnt <= 3'b000;
        trans_done <= 1'b0;
        trans_failed <= 1'b0;
        internal_transm_complete <= 1'b0;
        transm_complete_q <= 1'b0;
        sys_adr <= 32'h00000000;
        cmd_arg <= 32'h00000000;
        cmd_set <= 16'h0000;
        CIDAT <= 1'b0;
        Dat_Int_Status <= 8'h00;
        bd_cnt <= {READ_CYCLE{1'b0}};
        re_s_tx <= 1'b0;
        a_cmp_tx <= 1'b0;
        re_s_rx <= 1'b0;
        a_cmp_rx <= 1'b0;
        we_req <= 1'b0;
        d_write <= 1'b0;
        d_read <= 1'b0;
        start_tx_fifo <= 1'b0;
        start_rx_fifo <= 1'b0;
        ack_transfer <= 1'b0;
    end else begin
        state <= next_state;
        transm_complete_q <= transm_complete;
        internal_transm_complete <= transm_complete & ~transm_complete_q;

        re_s_tx <= 1'b0;
        a_cmp_tx <= 1'b0;
        re_s_rx <= 1'b0;
        a_cmp_rx <= 1'b0;
        we_req <= 1'b0;
        start_tx_fifo <= 1'b0;
        start_rx_fifo <= 1'b0;
        ack_transfer <= 1'b0;

        if (Dat_Int_Status_rst) begin
            Dat_Int_Status <= 8'h00;
        end

        case (state)
            IDLE: begin
                send_done <= 1'b0;
                rec_done <= 1'b0;
                rec_failed <= 1'b0;
                tx_cycle <= 1'b0;
                rx_cycle <= 1'b0;
                resend_try_cnt <= 3'b000;
                trans_done <= 1'b0;
                trans_failed <= 1'b0;
                internal_transm_complete <= 1'b0;
                sys_adr <= 32'h00000000;
                cmd_arg <= 32'h00000000;
                cmd_set <= 16'h0000;
                CIDAT <= 1'b0;
                bd_cnt <= {READ_CYCLE{1'b0}};
                d_write <= 1'b0;
                d_read <= 1'b0;
            end

            GET_TX_BD: begin
                re_s_tx <= 1'b1;
                tx_cycle <= 1'b1;
                rx_cycle <= 1'b0;
                cmd_set <= CMD24;
                send_done <= 1'b0;
                rec_done <= 1'b0;
                rec_failed <= 1'b0;
                trans_done <= 1'b0;
                trans_failed <= 1'b0;
`ifdef RAM_MEM_WIDTH_16
                if (ack_i_s_tx) begin
                    if (bd_cnt == 3'd0) begin
                        sys_adr[31:16] <= dat_in_tx[15:0];
                        bd_cnt <= 3'd1;
                    end else if (bd_cnt == 3'd1) begin
                        sys_adr[15:0] <= dat_in_tx[15:0];
                        bd_cnt <= 3'd2;
                    end else if (bd_cnt == 3'd2) begin
                        cmd_arg[31:16] <= dat_in_tx[15:0];
                        bd_cnt <= 3'd3;
                    end else if (bd_cnt == 3'd3) begin
                        cmd_arg[15:0] <= dat_in_tx[15:0];
                        start_tx_fifo <= 1'b1;
                        bd_cnt <= 3'd4;
                    end
                end
`else
                if (ack_i_s_tx) begin
                    if (bd_cnt == 2'd0) begin
                        sys_adr <= dat_in_tx[31:0];
                        bd_cnt <= 2'd1;
                    end else if (bd_cnt == 2'd1) begin
                        cmd_arg <= dat_in_tx[31:0];
                        start_tx_fifo <= 1'b1;
                        bd_cnt <= 2'd2;
                    end
                end
`endif
            end

            GET_RX_BD: begin
                re_s_rx <= 1'b1;
                tx_cycle <= 1'b0;
                rx_cycle <= 1'b1;
                send_done <= 1'b0;
                rec_done <= 1'b0;
                rec_failed <= 1'b0;
                trans_done <= 1'b0;
                trans_failed <= 1'b0;
                if (transfer_type == 2'b00) begin
                    cmd_set <= CMD17;
                end else if (transfer_type == 2'b01) begin
                    cmd_set <= ACMD13;
                end else begin
                    cmd_set <= ACMD51;
                end
`ifdef RAM_MEM_WIDTH_16
                if (ack_i_s_rx) begin
                    if (bd_cnt == 3'd0) begin
                        sys_adr[31:16] <= dat_in_rx[15:0];
                        bd_cnt <= 3'd1;
                    end else if (bd_cnt == 3'd1) begin
                        sys_adr[15:0] <= dat_in_rx[15:0];
                        bd_cnt <= 3'd2;
                    end else if (bd_cnt == 3'd2) begin
                        cmd_arg[31:16] <= dat_in_rx[15:0];
                        bd_cnt <= 3'd3;
                    end else if (bd_cnt == 3'd3) begin
                        cmd_arg[15:0] <= dat_in_rx[15:0];
                        bd_cnt <= 3'd4;
                    end
                end
`else
                if (ack_i_s_rx) begin
                    if (bd_cnt == 2'd0) begin
                        sys_adr <= dat_in_rx[31:0];
                        bd_cnt <= 2'd1;
                    end else if (bd_cnt == 2'd1) begin
                        cmd_arg <= dat_in_rx[31:0];
                        bd_cnt <= 2'd2;
                    end
                end
`endif
            end

            SEND_CMD: begin
                bd_cnt <= {READ_CYCLE{1'b0}};
                send_done <= 1'b0;
                rec_done <= 1'b0;
                rec_failed <= 1'b0;
                if (rx_cycle) begin
                    d_read <= 1'b1;
                    d_write <= 1'b0;
                end else if (tx_cycle) begin
                    d_read <= 1'b0;
                    d_write <= 1'b1;
                end else begin
                    d_read <= 1'b0;
                    d_write <= 1'b0;
                end
                if (!cmd_busy) begin
                    we_req <= 1'b1;
                    if (we_ack) begin
                        send_done <= 1'b1;
                    end
                end
            end

            RECIVE_CMD: begin
                send_done <= 1'b0;
                if (rx_cycle) begin
                    start_rx_fifo <= 1'b1;
                end
                if (!cmd_busy) begin
                    if (cmd_tsf_err) begin
                        rec_failed <= 1'b1;
                        rec_done <= 1'b0;
                        Dat_Int_Status[0] <= 1'b1;
                    end else if ((card_status[0] == 1'b1) && ((card_status[4:1] == 4'd4) || (card_status[4:1] == 4'd5) || (card_status[4:1] == 4'd6))) begin
                        rec_done <= 1'b1;
                        rec_failed <= 1'b0;
                    end else begin
                        rec_done <= 1'b0;
                        rec_failed <= 1'b1;
                    end
                end
            end

            DATA_TRANSFER: begin
                rec_done <= 1'b0;
                rec_failed <= 1'b0;
                if (tx_cycle && tx_empt) begin
                    trans_failed <= 1'b1;
                    Dat_Int_Status[2] <= 1'b1;
                end else if (rx_cycle && rx_full) begin
                    trans_failed <= 1'b1;
                    Dat_Int_Status[2] <= 1'b1;
                end else if (internal_transm_complete) begin
                    if (crc_ok) begin
                        trans_done <= 1'b1;
                        trans_failed <= 1'b0;
                        ack_transfer <= 1'b1;
                        if (tx_cycle) begin
                            a_cmp_tx <= 1'b1;
                        end
                        if (rx_cycle) begin
                            a_cmp_rx <= 1'b1;
                        end
                    end else begin
                        trans_done <= 1'b0;
                        trans_failed <= 1'b1;
                        Dat_Int_Status[3] <= 1'b1;
                    end
                end
            end

            STOP: begin
                cmd_set <= CMD12;
                rec_done <= 1'b0;
                rec_failed <= 1'b0;
                send_done <= 1'b0;
                trans_failed <= 1'b0;
                trans_done <= 1'b0;
                d_read <= 1'b1;
                d_write <= 1'b1;
                start_rx_fifo <= 1'b0;
                start_tx_fifo <= 1'b0;
            end

            STOP_SEND: begin
                send_done <= 1'b0;
                if (resend_try_cnt < RESEND_MAX_CNT[2:0]) begin
                    resend_try_cnt <= resend_try_cnt + 3'd1;
                end else begin
                    Dat_Int_Status[1] <= 1'b1;
                end
                if (!cmd_busy) begin
                    we_req <= 1'b1;
                    if (we_ack) begin
                        send_done <= 1'b1;
                    end
                end
            end

            default: begin
                send_done <= 1'b0;
                rec_done <= 1'b0;
                rec_failed <= 1'b0;
                tx_cycle <= 1'b0;
                rx_cycle <= 1'b0;
                resend_try_cnt <= 3'b000;
                trans_done <= 1'b0;
                trans_failed <= 1'b0;
                bd_cnt <= {READ_CYCLE{1'b0}};
                d_write <= 1'b0;
                d_read <= 1'b0;
            end
        endcase
    end
end
// STAGE5_SUBTASK_END B4_seq_fsm_and_reg_update

// STAGE5_SUBTASK_BEGIN B5_comb_output_assign: Combinational block that drives output ports re_s_tx, re_s_rx, we_req, d_write, d_read, start_tx_fifo, start_rx_fifo, ac
always_comb begin
    re_s_tx = 1'b0;
    re_s_rx = 1'b0;
    we_req = 1'b0;
    d_write = 1'b0;
    d_read = 1'b0;
    start_tx_fifo = 1'b0;
    start_rx_fifo = 1'b0;
    ack_transfer = 1'b0;
    a_cmp_tx = 1'b0;
    a_cmp_rx = 1'b0;

    case (state)
        IDLE: begin
            re_s_tx = 1'b0;
            re_s_rx = 1'b0;
            we_req = 1'b0;
            d_write = 1'b0;
            d_read = 1'b0;
            start_tx_fifo = 1'b0;
            start_rx_fifo = 1'b0;
            ack_transfer = 1'b0;
            a_cmp_tx = 1'b0;
            a_cmp_rx = 1'b0;
        end

        GET_TX_BD: begin
            re_s_tx = 1'b1;
            if (ack_i_s_tx && (bd_cnt == (READ_CYCLE - 1))) begin
                start_tx_fifo = 1'b1;
            end
        end

        GET_RX_BD: begin
            re_s_rx = 1'b1;
        end

        SEND_CMD: begin
            if (tx_cycle) begin
                d_write = 1'b1;
                d_read = 1'b0;
            end else if (rx_cycle) begin
                d_write = 1'b0;
                d_read = 1'b1;
            end else begin
                d_write = 1'b0;
                d_read = 1'b0;
            end

            if (!cmd_busy) begin
                we_req = 1'b1;
            end
        end

        RECIVE_CMD: begin
            if (rx_cycle) begin
                start_rx_fifo = 1'b1;
            end
        end

        DATA_TRANSFER: begin
            if (internal_transm_complete && crc_ok) begin
                ack_transfer = 1'b1;
                if (tx_cycle) begin
                    a_cmp_tx = 1'b1;
                end
                if (rx_cycle) begin
                    a_cmp_rx = 1'b1;
                end
            end
        end

        STOP: begin
            d_write = 1'b1;
            d_read = 1'b1;
            start_tx_fifo = 1'b0;
            start_rx_fifo = 1'b0;
        end

        STOP_SEND: begin
            if (!cmd_busy) begin
                we_req = 1'b1;
            end
        end

        default: begin
            re_s_tx = 1'b0;
            re_s_rx = 1'b0;
            we_req = 1'b0;
            d_write = 1'b0;
            d_read = 1'b0;
            start_tx_fifo = 1'b0;
            start_rx_fifo = 1'b0;
            ack_transfer = 1'b0;
            a_cmp_tx = 1'b0;
            a_cmp_rx = 1'b0;
        end
    endcase
end
// STAGE5_SUBTASK_END B5_comb_output_assign
