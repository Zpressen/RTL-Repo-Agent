module sd_data_master (
    clk,
    rst,
    dat_in_tx,
    free_tx_bd,
    ack_i_s_tx,
    dat_in_rx,
    free_rx_bd,
    ack_i_s_rx,
    cmd_busy,
    we_ack,
    cmd_tsf_err,
    card_status,
    tx_empt,
    tx_full,
    rx_full,
    busy_n,
    transm_complete,
    crc_ok,
    Dat_Int_Status_rst,
    transfer_type,
    re_s_tx,
    a_cmp_tx,
    re_s_rx,
    a_cmp_rx,
    we_req,
    d_write,
    d_read,
    cmd_arg,
    cmd_set,
    start_tx_fifo,
    start_rx_fifo,
    sys_adr,
    ack_transfer,
    Dat_Int_Status,
    CIDAT
);

input clk;
input rst;
input [15:0] dat_in_tx;
input [4:0] free_tx_bd;
input ack_i_s_tx;
input [15:0] dat_in_rx;
input [4:0] free_rx_bd;
input ack_i_s_rx;
input cmd_busy;
input we_ack;
input cmd_tsf_err;
input [4:0] card_status;
input tx_empt;
input tx_full;
input rx_full;
input busy_n;
input transm_complete;
input crc_ok;
input Dat_Int_Status_rst;
input [1:0] transfer_type;

output reg re_s_tx;
output reg a_cmp_tx;
output reg re_s_rx;
output reg a_cmp_rx;
output reg we_req;
output reg d_write;
output reg d_read;
output reg [31:0] cmd_arg;
output reg [15:0] cmd_set;
output reg start_tx_fifo;
output reg start_rx_fifo;
output reg [31:0] sys_adr;
output reg ack_transfer;
output reg [7:0] Dat_Int_Status;
output reg CIDAT;

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

parameter RESEND_MAX_CNT = 3;
parameter READ_CYCLE = 4;
parameter BD_EMPTY = 8;

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
reg [2:0] bd_cnt;

always @(state or free_tx_bd or free_rx_bd or bd_cnt or tx_full or send_done or rec_done or rec_failed or trans_done or trans_failed) begin
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

always @(posedge clk or posedge rst) begin
    if (rst) begin
        state <= IDLE;
        send_done <= 1'b0;
        rec_done <= 1'b0;
        rec_failed <= 1'b0;
        tx_cycle <= 1'b0;
        rx_cycle <= 1'b0;
        resend_try_cnt <= 3'b000;
        bd_cnt <= 3'b000;
        trans_done <= 1'b0;
        trans_failed <= 1'b0;
        internal_transm_complete <= 1'b0;
        transm_complete_q <= 1'b0;
        sys_adr <= 32'h00000000;
        cmd_arg <= 32'h00000000;
        cmd_set <= 16'h0000;
        CIDAT <= 1'b0;
        Dat_Int_Status <= 8'h00;
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
        state <= #1 next_state;
        transm_complete_q <= transm_complete;
        internal_transm_complete <= transm_complete & ~transm_complete_q;

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
        trans_done <= 1'b0;
        trans_failed <= 1'b0;

        if (Dat_Int_Status_rst) begin
            Dat_Int_Status <= 8'h00;
        end

        case (state)
            IDLE: begin
                tx_cycle <= 1'b0;
                rx_cycle <= 1'b0;
                bd_cnt <= 3'b000;
                resend_try_cnt <= 3'b000;
                sys_adr <= 32'h00000000;
                cmd_arg <= 32'h00000000;
                cmd_set <= 16'h0000;
                CIDAT <= CIDAT;
                we_req <= we_req;
            end

            GET_TX_BD: begin
                tx_cycle <= 1'b1;
                rx_cycle <= 1'b0;
                cmd_set <= CMD24;
                re_s_tx <= 1'b1;

                if (bd_cnt >= READ_CYCLE[2:0]) begin
                    re_s_tx <= 1'b0;
                    start_tx_fifo <= 1'b1;
                end

                if (ack_i_s_tx) begin
                    if (bd_cnt == 3'd0) begin
                        sys_adr[15:0] <= dat_in_tx;
                        bd_cnt <= bd_cnt + 3'd1;
                    end else if (bd_cnt == 3'd1) begin
                        sys_adr[31:16] <= dat_in_tx;
                        bd_cnt <= bd_cnt + 3'd1;
                    end else if (bd_cnt == 3'd2) begin
                        cmd_arg[15:0] <= dat_in_tx;
                        re_s_tx <= 1'b0;
                        bd_cnt <= bd_cnt + 3'd1;
                    end else if (bd_cnt == 3'd3) begin
                        cmd_arg[31:16] <= dat_in_tx;
                        re_s_tx <= 1'b0;
                        start_tx_fifo <= 1'b1;
                        bd_cnt <= bd_cnt + 3'd1;
                    end else begin
                        re_s_tx <= 1'b0;
                        start_tx_fifo <= 1'b1;
                    end
                end
            end

            GET_RX_BD: begin
                tx_cycle <= 1'b0;
                rx_cycle <= 1'b1;
                re_s_rx <= 1'b1;

                if (transfer_type == 2'b00) begin
                    cmd_set <= CMD17;
                    CIDAT <= 1'b0;
                end else if (transfer_type == 2'b01) begin
                    cmd_set <= ACMD13;
                    CIDAT <= 1'b1;
                end else begin
                    cmd_set <= ACMD51;
                    CIDAT <= 1'b1;
                end

                if (ack_i_s_rx) begin
                    if (bd_cnt == 3'd0) begin
                        sys_adr[15:0] <= dat_in_rx;
                        bd_cnt <= bd_cnt + 3'd1;
                    end else if (bd_cnt == 3'd1) begin
                        sys_adr[31:16] <= dat_in_rx;
                        bd_cnt <= bd_cnt + 3'd1;
                    end else if (bd_cnt == 3'd2) begin
                        cmd_arg[15:0] <= dat_in_rx;
                        re_s_rx <= 1'b0;
                        bd_cnt <= bd_cnt + 3'd1;
                    end else if (bd_cnt == 3'd3) begin
                        cmd_arg[31:16] <= dat_in_rx;
                        re_s_rx <= 1'b0;
                        bd_cnt <= bd_cnt + 3'd1;
                    end else begin
                        re_s_rx <= 1'b0;
                    end
                end
            end

            SEND_CMD: begin
                rec_done <= 1'b0;
                we_req <= we_req;
                if (tx_cycle) begin
                    d_write <= 1'b1;
                    d_read <= 1'b0;
                    start_tx_fifo <= start_tx_fifo;
                end else if (rx_cycle) begin
                    d_write <= 1'b0;
                    d_read <= 1'b1;
                end

                if (!cmd_busy) begin
                    we_req <= 1'b1;
                end

                if (we_ack) begin
                    send_done <= 1'b1;
                    we_req <= 1'b1;
                end
            end

            RECIVE_CMD: begin
                send_done <= 1'b0;

                if (tx_cycle) begin
                    start_tx_fifo <= start_tx_fifo;
                end

                if (rx_cycle) begin
                    start_rx_fifo <= 1'b1;
                end
                if (cmd_busy) begin
                    d_write <= d_write;
                    d_read <= d_read;
                end else begin
                    d_write <= 1'b0;
                    d_read <= 1'b0;

                    if (cmd_tsf_err) begin
                        rec_failed <= 1'b1;
                        start_tx_fifo <= 1'b0;
                    end else if (card_status[0] == 1'b1) begin
                        if ((card_status[4:1] == 4'd4) ||
                            (card_status[4:1] == 4'd5) ||
                            (card_status[4:1] == 4'd6)) begin
                            rec_done <= 1'b1;
                        end else begin
                            rec_failed <= 1'b1;
                            start_tx_fifo <= 1'b0;
                            Dat_Int_Status[4] <= 1'b1;
                        end
                    end
                end
            end

            DATA_TRANSFER: begin
                CIDAT <= 1'b1;
                ack_transfer <= ack_transfer;
                if (tx_cycle && tx_empt) begin
                    trans_failed <= 1'b1;
                    ack_transfer <= 1'b1;
                end else if (rx_cycle && rx_full) begin
                    trans_failed <= 1'b1;
                    ack_transfer <= 1'b1;
                end else if (internal_transm_complete) begin
                    if (crc_ok && busy_n) begin
                        trans_done <= 1'b1;
                        ack_transfer <= 1'b1;

                        if (tx_cycle) begin
                            a_cmp_tx <= 1'b1;
                        end

                        if (rx_cycle) begin
                            a_cmp_rx <= 1'b1;
                        end
                    end else if (!crc_ok && busy_n) begin
                        trans_failed <= 1'b1;
                    end
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
                ack_transfer <= ack_transfer;
            end

            STOP_SEND: begin
                d_read <= 1'b1;
                d_write <= 1'b1;
                ack_transfer <= ack_transfer;

                if (!cmd_busy) begin
                    we_req <= 1'b1;
                end

                if (we_ack) begin
                    send_done <= 1'b1;

                    if (resend_try_cnt != RESEND_MAX_CNT[2:0]) begin
                        resend_try_cnt <= resend_try_cnt + 3'd1;
                    end

                    if (!Dat_Int_Status_rst && (resend_try_cnt >= RESEND_MAX_CNT[2:0])) begin
                        Dat_Int_Status[1] <= 1'b1;
                    end
                end
            end

            default: begin
                send_done <= 1'b0;
                rec_done <= 1'b0;
                rec_failed <= 1'b0;
                tx_cycle <= 1'b0;
                rx_cycle <= 1'b0;
                bd_cnt <= 3'b000;
                trans_done <= 1'b0;
                trans_failed <= 1'b0;
            end
        endcase
    end
end

endmodule
