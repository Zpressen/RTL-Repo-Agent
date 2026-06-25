`include "sd_defines.v"

module sd_cmd_master (
    CLK_PAD_IO,
    RST_PAD_I,
    New_CMD,
    data_write,
    data_read,
    ARG_REG,
    CMD_SET_REG,
    TIMEOUT_REG,
    STATUS_REG,
    RESP_1_REG,
    ERR_INT_REG,
    NORMAL_INT_REG,
    ERR_INT_RST,
    NORMAL_INT_RST,
    settings,
    go_idle_o,
    cmd_out,
    req_out,
    ack_out,
    req_in,
    ack_in,
    cmd_in,
    serial_status,
    card_detect
);
    input CLK_PAD_IO;
    input RST_PAD_I;
    input New_CMD;
    input data_write;
    input data_read;
    input [31:0] ARG_REG;
    input [13:0] CMD_SET_REG;
    input [15:0] TIMEOUT_REG;
    output reg [15:0] STATUS_REG;
    output reg [31:0] RESP_1_REG;
    output reg [4:0] ERR_INT_REG;
    output reg [15:0] NORMAL_INT_REG;
    input ERR_INT_RST;
    input NORMAL_INT_RST;
    output reg [15:0] settings;
    output reg go_idle_o;
    output reg [39:0] cmd_out;
    output reg req_out;
    output reg ack_out;
    input req_in;
    input ack_in;
    input [39:0] cmd_in;
    input [7:0] serial_status;
    input card_detect;

    localparam [2:0] IDLE    = 3'b001;
    localparam [2:0] SETUP   = 3'b010;
    localparam [2:0] EXECUTE = 3'b100;

    localparam [6:0] small_rsp = 7'b0101000;
    localparam [6:0] big_rsp   = 7'b1111111;

    localparam CICMD = 0;
    localparam CTE   = 0;
    localparam CCRCE = 1;
    localparam CIE   = 3;
    localparam CC    = 0;
    localparam EI    = 15;
    localparam CARD_INSERT_INT = 1;
    localparam CARD_REMOVE_INT = 2;
    localparam DAT_AVA_BIT     = 6;
    localparam CRC_VALID_BIT   = 5;

    reg [2:0] state;
    reg [2:0] next_state;

    reg [15:0] Watchdog_Cnt;
    reg [3:0] debounce;
    reg card_present;

    reg req_q;
    reg ack_q;
    reg req_in_int;
    reg ack_in_int;

    reg complete;
    reg CRC_check_enable;
    reg index_check_enable;
    reg [6:0] response_size;
    reg [7:0] status;

    reg [39:0] next_cmd_out;
    reg [15:0] next_settings;
    reg [6:0] next_response_size;

    wire [5:0] CMDI;
    wire [1:0] WORD_SELECT;
    wire CICE;
    wire CRCE;
    wire [1:0] RTS;

    wire dat_ava;
    wire crc_valid;
    wire command_index_mismatch;
    wire timeout_expired;
    wire response_present;

    assign CMDI = CMD_SET_REG[13:8];
    assign WORD_SELECT = CMD_SET_REG[7:6];
    assign CICE = CMD_SET_REG[4];
    assign CRCE = CMD_SET_REG[3];
    assign RTS = CMD_SET_REG[1:0];

    assign dat_ava = serial_status[DAT_AVA_BIT];
    assign crc_valid = serial_status[CRC_VALID_BIT];
    assign command_index_mismatch = (cmd_out[37:32] != cmd_in[37:32]);
    assign timeout_expired = ((Watchdog_Cnt + 16'b0000000000000001) > TIMEOUT_REG);
    assign response_present = (response_size != 7'b0000000);

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

    always @(posedge CLK_PAD_IO or posedge RST_PAD_I) begin
        if (RST_PAD_I) begin
            state <= #1 IDLE;
        end else begin
            state <= #1 next_state;
        end
    end

    always @(RTS or CMDI or WORD_SELECT or CRCE or ARG_REG or data_read or data_write) begin
        case (RTS)
            2'b10: begin
                next_response_size = small_rsp;
            end
            2'b11: begin
                next_response_size = small_rsp;
            end
            2'b01: begin
                next_response_size = big_rsp;
            end
            default: begin
                next_response_size = 7'b0000000;
            end
        endcase

        next_cmd_out = {2'b01, CMDI, ARG_REG};
        next_settings = {1'b0, WORD_SELECT, data_read, data_write, 3'b111, CRCE, next_response_size};
    end

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

            card_present <= (debounce == 4'b1111);
        end
    end

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

    always @(posedge CLK_PAD_IO or posedge RST_PAD_I) begin
        if (RST_PAD_I) begin
            CRC_check_enable <= 1'b0;
            complete <= 1'b0;
            RESP_1_REG <= 32'b00000000000000000000000000000000;
            ERR_INT_REG <= 5'b00000;
            NORMAL_INT_REG <= 16'b0000000000000000;
            STATUS_REG <= 16'b0000000000000000;
            status <= 8'b00000000;
            cmd_out <= 40'b0000000000000000000000000000000000000000;
            settings <= 16'b0000000000000000;
            response_size <= 7'b0000000;
            req_out <= 1'b0;
            index_check_enable <= 1'b0;
            ack_out <= 1'b0;
            Watchdog_Cnt <= 16'b0000000000000000;
            go_idle_o <= 1'b0;
        end else begin

            NORMAL_INT_REG[CARD_INSERT_INT] <= card_present;
            NORMAL_INT_REG[CARD_REMOVE_INT] <= ~card_present;
            complete <= 1'b0;

            case (state)
                IDLE: begin
                    go_idle_o <= 1'b0;
                    req_out <= 1'b0;
                    ack_out <= 1'b0;
                    STATUS_REG[CICMD] <= 1'b0;

                    if (req_in_int) begin
                        status <= serial_status;
                        ack_out <= 1'b1;
                    end
                end

                SETUP: begin
                    NORMAL_INT_REG <= 16'b0000000000000000;
                    ERR_INT_REG <= 5'b00000;
                    STATUS_REG <= 16'b0000000000000000;
                    STATUS_REG[CICMD] <= 1'b1;

                    index_check_enable <= CICE;
                    CRC_check_enable <= CRCE;
                    response_size <= next_response_size;
                    cmd_out <= next_cmd_out;
                    settings <= next_settings;
                    Watchdog_Cnt <= 16'b0000000000000000;
                    go_idle_o <= 1'b0;
                    req_out <= 1'b0;
                end

                EXECUTE: begin
                    Watchdog_Cnt <= Watchdog_Cnt + 16'b0000000000000001;
                    ack_out <= 1'b0;
                    req_out <= 1'b0;
                    if (timeout_expired) begin
                        ERR_INT_REG[CTE] <= 1'b1;
                        NORMAL_INT_REG[EI] <= 1'b1;
                        go_idle_o <= 1'b1;
                        req_out <= 1'b0;
                        if (ack_in) begin
                            complete <= 1'b1;
                        end
                    end
                    if (ack_in_int) begin
                        req_out <= 1'b1;
                    end else if (req_in_int) begin
                        status <= serial_status;
                        ack_out <= 1'b1;
                        req_out <= 1'b0;

                        if (dat_ava) begin
                            complete <= 1'b1;
                            NORMAL_INT_REG[EI] <= 1'b0;

                            if (CRC_check_enable && !crc_valid) begin
                                ERR_INT_REG[CCRCE] <= 1'b1;
                                NORMAL_INT_REG[EI] <= 1'b1;
                            end

                            if (index_check_enable && command_index_mismatch) begin
                                ERR_INT_REG[CIE] <= 1'b1;
                                NORMAL_INT_REG[EI] <= 1'b1;
                            end

                            NORMAL_INT_REG[CC] <= 1'b1;

                            if (response_present) begin
                                RESP_1_REG <= cmd_in[31:0];
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

            if (ERR_INT_RST) begin
                ERR_INT_REG <= 5'b00000;
            end
            if (NORMAL_INT_RST) begin
                NORMAL_INT_REG <= 16'b0000000000000000;
            end
        end
    end
endmodule
