// STAGE5_SUBTASK_BEGIN B1_main_declarations: Declare all internal wires, registers, and constants: state register, next_state wire, Watchdog_Cnt, debounce counter, c
input         CLK_PAD_IO;
    input         RST_PAD_I;
    input         New_CMD;
    input         data_write;
    input         data_read;
    input  [31:0] ARG_REG;
    input  [13:0] CMD_SET_REG;
    input  [15:0] TIMEOUT_REG;
    output [15:0] STATUS_REG;
    output [31:0] RESP_1_REG;
    output [4:0]  ERR_INT_REG;
    output [15:0] NORMAL_INT_REG;
    input         ERR_INT_RST;
    input         NORMAL_INT_RST;
    output [15:0] settings;
    output        go_idle_o;
    output [39:0] cmd_out;
    output        req_out;
    output        ack_out;
    input         req_in;
    input         ack_in;
    input  [39:0] cmd_in;
    input  [7:0]  serial_status;
    input         card_detect;

    localparam [2:0] IDLE    = 3'b001;
    localparam [2:0] SETUP   = 3'b010;
    localparam [2:0] EXECUTE = 3'b100;

    localparam [6:0] small_rsp = 7'b0101000;
    localparam [6:0] big_rsp   = 7'b1111111;

    reg  [2:0]  state;
    reg  [2:0]  next_state;
    reg  [15:0] Watchdog_Cnt;
    reg  [3:0]  debounce;
    reg         card_present;

    reg         req_q;
    reg         ack_q;
    reg         req_in_int;
    reg         ack_in_int;

    reg         complete;
    reg         CRC_check_enable;
    reg         index_check_enable;
    reg  [6:0]  response_size;
    reg  [7:0]  status;

    reg  [31:0] RESP_1_REG;
    reg  [15:0] STATUS_REG;
    reg  [15:0] NORMAL_INT_REG;
    reg  [4:0]  ERR_INT_REG;
    reg  [39:0] cmd_out;
    reg  [15:0] settings;
    reg         go_idle_o;
    reg         req_out;
    reg         ack_out;

    wire [5:0]  CMDI;
    wire [1:0]  WORD_SELECT;
    wire        CICE;
    wire        CRCE;
    wire [1:0]  RTS;
    wire        dat_ava;
    wire        crc_valid;
    wire        command_index_error;
    wire        watchdog_timeout;

    assign CMDI = CMD_SET_REG[13:8];
    assign WORD_SELECT = CMD_SET_REG[7:6];
    assign CICE = CMD_SET_REG[4];
    assign CRCE = CMD_SET_REG[3];
    assign RTS = CMD_SET_REG[1:0];
    assign dat_ava = status[6];
    assign crc_valid = status[5];
    assign command_index_error = (cmd_out[37:32] != cmd_in[37:32]);
    assign watchdog_timeout = (Watchdog_Cnt > TIMEOUT_REG);
// STAGE5_SUBTASK_END B1_main_declarations

// STAGE5_SUBTASK_BEGIN B2_comb_next_state: Pure combinational always block computing next_state from current state, New_CMD, ack_in_int, and complete using the sta
always @(state or New_CMD or ack_in_int or complete) begin
    next_state = IDLE;

    case (state)
        IDLE: begin
            if (New_CMD) begin
                next_state = SETUP;
            end else begin
                next_state = IDLE;
            end
        end

        SETUP: begin
            if (ack_in_int) begin
                next_state = EXECUTE;
            end else begin
                next_state = SETUP;
            end
        end

        EXECUTE: begin
            if (complete) begin
                next_state = IDLE;
            end else begin
                next_state = EXECUTE;
            end
        end

        default: begin
            next_state = IDLE;
        end
    endcase
end
// STAGE5_SUBTASK_END B2_comb_next_state

// STAGE5_SUBTASK_BEGIN B3_seq_state_register: Sequential always block with asynchronous reset; on reset set state to IDLE (3'b001), on clock edge update state with ne
always @(posedge CLK_PAD_IO or posedge RST_PAD_I) begin
    if (RST_PAD_I) begin
        state <= IDLE;
    end else begin
        state <= next_state;
    end
end
// STAGE5_SUBTASK_END B3_seq_state_register

// STAGE5_SUBTASK_BEGIN B4_comb_cmd_settings_assembly: Combinational block computing response_size from CMD_SET_REG[1:0], assembling 40-bit next_cmd_out = {2'b01, CMD_SET_REG[
reg [39:0] next_cmd_out;
reg [15:0] next_settings;

always @(CMD_SET_REG or ARG_REG or data_read or data_write) begin
    case (CMD_SET_REG[1:0])
        2'b10: begin
            response_size = small_rsp;
        end
        2'b11: begin
            response_size = small_rsp;
        end
        2'b01: begin
            response_size = big_rsp;
        end
        default: begin
            response_size = 7'b0000000;
        end
    endcase

    next_cmd_out = {2'b01, CMD_SET_REG[13:8], ARG_REG};
    next_settings = {1'b0, CMD_SET_REG[7:6], data_read, data_write, 3'b111, CMD_SET_REG[3], response_size};
end
// STAGE5_SUBTASK_END B4_comb_cmd_settings_assembly

// STAGE5_SUBTASK_BEGIN B5_seq_debounce_logic: Sequential debounce logic: on reset clear 4‑bit counter and card_present; if !card_detect increment counter (saturating 
always @(posedge CLK_PAD_IO or posedge RST_PAD_I) begin
    if (RST_PAD_I) begin
        debounce <= 4'b0000;
        card_present <= 1'b0;
    end else begin
        if (!card_detect) begin
            if (debounce != 4'b1111) begin
                debounce <= debounce + 4'b0001;
            end else begin
                debounce <= 4'b1111;
            end
        end else begin
            debounce <= 4'b0000;
        end

        if (debounce == 4'b1111) begin
            card_present <= 1'b1;
        end else begin
            card_present <= 1'b0;
        end
    end
end
// STAGE5_SUBTASK_END B5_seq_debounce_logic

// STAGE5_SUBTASK_BEGIN B6_seq_synchronisers: Two-stage synchronizers for req_in and ack_in: on reset clear all stages; each clock edge shift req_in → req_q → req_in_
always @(posedge CLK_PAD_IO or posedge RST_PAD_I) begin
    if (RST_PAD_I) begin
        req_q <= 1'b0;
        req_in_int <= 1'b0;
        ack_q <= 1'b0;
        ack_in_int <= 1'b0;
    end else begin
        req_q <= req_in;
        req_in_int <= req_q;
        ack_q <= ack_in;
        ack_in_int <= ack_q;
    end
end
// STAGE5_SUBTASK_END B6_seq_synchronisers

// STAGE5_SUBTASK_BEGIN B7_seq_fsm_state_operations: Sequential block: on reset clear all outputs and internal state; on clock edge assign NORMAL_INT_REG[1]=card_present, NO
always @(posedge CLK_PAD_IO or posedge RST_PAD_I) begin
    if (RST_PAD_I) begin
        CRC_check_enable <= 1'b0;
        complete <= 1'b0;
        RESP_1_REG <= 32'b0;
        ERR_INT_REG <= 5'b0;
        NORMAL_INT_REG <= 16'b0;
        STATUS_REG <= 16'b0;
        status <= 8'b0;
        cmd_out <= 40'b0;
        settings <= 16'b0;
        response_size <= 7'b0;
        req_out <= 1'b0;
        index_check_enable <= 1'b0;
        ack_out <= 1'b0;
        Watchdog_Cnt <= 16'b0;
        go_idle_o <= 1'b0;
    end else begin
        NORMAL_INT_REG[1] <= card_present;
        NORMAL_INT_REG[2] <= ~card_present;
        complete <= 1'b0;

        case (state)
            IDLE: begin
                go_idle_o <= 1'b0;
                req_out <= 1'b0;
                ack_out <= 1'b0;
                STATUS_REG[0] <= 1'b0;

                if (req_in_int) begin
                    status <= serial_status;
                    STATUS_REG[7:0] <= serial_status;
                    ack_out <= 1'b1;
                end
            end

            SETUP: begin
                NORMAL_INT_REG <= 16'b0;
                ERR_INT_REG <= 5'b0;
                STATUS_REG <= 16'b0;
                index_check_enable <= CICE;
                CRC_check_enable <= CRCE;
                cmd_out <= next_cmd_out;
                settings <= next_settings;

                case (RTS)
                    2'b10: begin
                        response_size <= small_rsp;
                    end
                    2'b11: begin
                        response_size <= small_rsp;
                    end
                    2'b01: begin
                        response_size <= big_rsp;
                    end
                    default: begin
                        response_size <= 7'b0000000;
                    end
                endcase

                Watchdog_Cnt <= 16'b0;
                go_idle_o <= 1'b0;
                req_out <= 1'b0;
                ack_out <= 1'b0;
                STATUS_REG[0] <= 1'b1;
            end

            EXECUTE: begin
                Watchdog_Cnt <= Watchdog_Cnt + 16'b0000000000000001;
                ack_out <= 1'b0;

                if (watchdog_timeout) begin
                    ERR_INT_REG[0] <= 1'b1;
                    NORMAL_INT_REG[15] <= 1'b1;
                    if (ack_in) begin
                        complete <= 1'b1;
                    end
                    go_idle_o <= 1'b1;
                end else begin
                    if (ack_in_int) begin
                        req_out <= 1'b1;
                    end else if (req_in_int) begin
                        status <= serial_status;
                        STATUS_REG[7:0] <= serial_status;
                        ack_out <= 1'b1;

                        if (serial_status[6]) begin
                            complete <= 1'b1;
                            NORMAL_INT_REG[15] <= 1'b0;

                            if (CRC_check_enable && !serial_status[5]) begin
                                ERR_INT_REG[1] <= 1'b1;
                                NORMAL_INT_REG[15] <= 1'b1;
                            end

                            if (index_check_enable && command_index_error) begin
                                ERR_INT_REG[3] <= 1'b1;
                                NORMAL_INT_REG[15] <= 1'b1;
                            end

                            NORMAL_INT_REG[0] <= 1'b1;

                            if (response_size != 7'b0000000) begin
                                RESP_1_REG <= cmd_in[31:0];
                            end
                        end
                    end
                end
            end

            default: begin
                go_idle_o <= 1'b0;
                req_out <= 1'b0;
                ack_out <= 1'b0;
            end
        endcase
    end
end
// STAGE5_SUBTASK_END B7_seq_fsm_state_operations
