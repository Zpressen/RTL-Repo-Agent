module sd_data_master (
    input         clk,
    input         rst,
    input  [31:0] dat_in_tx,
    input         ack_i_s_tx,
    input  [2:0]  free_tx_bd,
    input  [31:0] dat_in_rx,
    input         ack_i_s_rx,
    input  [2:0]  free_rx_bd,
    input         cmd_busy,
    input         we_ack,
    input         cmd_tsf_err,
    input  [4:0]  card_status,
    input         tx_empt,
    input         tx_full,
    input         rx_full,
    input         busy_n,
    input         transm_complete,
    input         crc_ok,
    input         Dat_Int_Status_rst,
    input  [1:0]  transfer_type,

    output reg         re_s_tx,
    output reg         a_cmp_tx,
    output reg         re_s_rx,
    output reg         a_cmp_rx,
    output reg         we_req,
    output reg         d_write,
    output reg         d_read,
    output reg [31:0]  cmd_arg,
    output reg [15:0]  cmd_set,
    output reg         start_tx_fifo,
    output reg         start_rx_fifo,
    output reg [31:0]  sys_adr,
    output reg         ack_transfer,
    output reg [7:0]   Dat_Int_Status,
    output reg         CIDAT
);

    // Parameters (authoritative values from global defines)
    localparam CMD24  = 16'h181A;
    localparam CMD17  = 16'h111A;
    localparam CMD12  = 16'h0C1A;
    localparam ACMD13 = 16'h0D1A;
    localparam ACMD51 = 16'h331A;

    localparam SIZE           = 9;
    localparam IDLE           = 9'b000000001;
    localparam GET_TX_BD      = 9'b000000010;
    localparam GET_RX_BD      = 9'b000000100;
    localparam SEND_CMD       = 9'b000001000;
    localparam RECIVE_CMD     = 9'b000010000;
    localparam DATA_TRANSFER  = 9'b000100000;
    localparam STOP           = 9'b001000000;
    localparam STOP_SEND      = 9'b010000000;
    localparam RESEND_MAX_CNT = 3;
    localparam BD_SIZE        = 8;
    localparam BD_EMPTY       = 2;        // BD_SIZE/4 (16-bit memory)
    localparam READ_CYCLE     = 4;
    // Internal registers
    reg          send_done;
    reg          rec_done;
    reg          rec_failed;
    reg          tx_cycle;
    reg          rx_cycle;
    reg [2:0]    resend_try_cnt;
    reg [8:0]    state;
    reg [8:0]    next_state;
    reg          trans_done;
    reg          trans_failed;
    reg          internal_transm_complete;
    reg          transm_complete_q;
    reg [2:0]    bd_cnt;                 // 3 bits for READ_CYCLE=4

    // Combinational next-state logic (explicit sensitivity list)
    always @(state or free_tx_bd or free_rx_bd or tx_full or send_done or
             rec_done or rec_failed or trans_done or trans_failed or bd_cnt) begin
        next_state = state;   // default hold
        case (state)
            IDLE: begin
                if (free_tx_bd != BD_EMPTY)
                    next_state = GET_TX_BD;
                else if (free_rx_bd != BD_EMPTY)
                    next_state = GET_RX_BD;
                else
                    next_state = IDLE;
            end
            GET_TX_BD: begin
                if ((bd_cnt > (READ_CYCLE - 1)) && (tx_full == 1'b1))
                    next_state = SEND_CMD;
                else
                    next_state = GET_TX_BD;
            end
            GET_RX_BD: begin
                if (bd_cnt > (READ_CYCLE - 1))
                    next_state = SEND_CMD;
                else
                    next_state = GET_RX_BD;
            end
            SEND_CMD: begin
                if (send_done == 1'b1)
                    next_state = RECIVE_CMD;
                else
                    next_state = SEND_CMD;
            end
            RECIVE_CMD: begin
                if (rec_done == 1'b1)
                    next_state = DATA_TRANSFER;
                else if (rec_failed == 1'b1)
                    next_state = SEND_CMD;
                else
                    next_state = RECIVE_CMD;
            end
            DATA_TRANSFER: begin
                if (trans_done == 1'b1)
                    next_state = IDLE;
                else if (trans_failed == 1'b1)
                    next_state = STOP;
                else
                    next_state = DATA_TRANSFER;
            end
            STOP: begin
                next_state = STOP_SEND;
            end
            STOP_SEND: begin
                if (send_done == 1'b1)
                    next_state = IDLE;
                else
                    next_state = STOP_SEND;
            end
            default: next_state = IDLE;
        endcase
    end

    // Sequential state register and output register update
    always @(posedge clk or posedge rst) begin
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
            sys_adr <= 32'b0;
            cmd_arg <= 32'b0;
            cmd_set <= 16'b0;
            CIDAT <= 1'b0;
            Dat_Int_Status <= 8'b0;
            bd_cnt <= 3'b0;
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

            // Default output values
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
            CIDAT <= 1'b0;

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
                    sys_adr <= 32'b0;
                    cmd_arg <= 32'b0;
                    cmd_set <= 16'b0;
                    CIDAT <= 1'b0;
                    bd_cnt <= 3'b0;
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
                    if (ack_i_s_tx) begin
                        if (bd_cnt == 3'd0) begin
                            sys_adr[15:0] <= dat_in_tx[15:0];
                            bd_cnt <= 3'd1;
                        end else if (bd_cnt == 3'd1) begin
                            sys_adr[31:16] <= dat_in_tx[15:0];
                            bd_cnt <= 3'd2;
                        end else if (bd_cnt == 3'd2) begin
                            cmd_arg[15:0] <= dat_in_tx[15:0];
                            bd_cnt <= 3'd3;
                        end else if (bd_cnt == 3'd3) begin
                            cmd_arg[31:16] <= dat_in_tx[15:0];
                            start_tx_fifo <= 1'b1;
                            bd_cnt <= 3'd4;
                        end
                    end
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
                    if (transfer_type == 2'b00)
                        cmd_set <= CMD17;
                    else if (transfer_type == 2'b01)
                        cmd_set <= ACMD13;
                    else
                        cmd_set <= ACMD51;
                    if (ack_i_s_rx) begin
                        if (bd_cnt == 3'd0) begin
                            sys_adr[15:0] <= dat_in_rx[15:0];
                            bd_cnt <= 3'd1;
                        end else if (bd_cnt == 3'd1) begin
                            sys_adr[31:16] <= dat_in_rx[15:0];
                            bd_cnt <= 3'd2;
                        end else if (bd_cnt == 3'd2) begin
                            cmd_arg[15:0] <= dat_in_rx[15:0];
                            bd_cnt <= 3'd3;
                        end else if (bd_cnt == 3'd3) begin
                            cmd_arg[31:16] <= dat_in_rx[15:0];
                            bd_cnt <= 3'd4;
                        end
                    end
                end

                SEND_CMD: begin
                    bd_cnt <= 3'b0;
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
                        if (we_ack)
                            send_done <= 1'b1;
                    end
                end

                RECIVE_CMD: begin
                    send_done <= 1'b0;
                    if (rx_cycle)
                        start_rx_fifo <= 1'b1;
                    if (!cmd_busy) begin
                        if (cmd_tsf_err) begin
                            rec_failed <= 1'b1;
                            rec_done <= 1'b0;
                            Dat_Int_Status[0] <= 1'b1;
                        end else if ((card_status[0] == 1'b1) &&
                                     ((card_status[4:1] == 4'd4) ||
                                      (card_status[4:1] == 4'd5) ||
                                      (card_status[4:1] == 4'd6))) begin
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
                            if (tx_cycle)
                                a_cmp_tx <= 1'b1;
                            if (rx_cycle)
                                a_cmp_rx <= 1'b1;
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
                    if (resend_try_cnt < RESEND_MAX_CNT)
                        resend_try_cnt <= resend_try_cnt + 3'd1;
                    else
                        Dat_Int_Status[1] <= 1'b1;
                    if (!cmd_busy) begin
                        we_req <= 1'b1;
                        if (we_ack)
                            send_done <= 1'b1;
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
                    bd_cnt <= 2'b0;
                end
            endcase

            // Dat_Int_Status_rst has highest priority – overrides any state-driven assignments
            if (Dat_Int_Status_rst)
                Dat_Int_Status <= 8'b0;
        end
    end

endmodule
