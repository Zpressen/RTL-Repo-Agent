// ============================================================================
// Module: sd_cmd_master
// SD Command Master – FSM-based command/response controller for SD/MMC cards
// ============================================================================

`include "sd_defines.v"

module sd_cmd_master (
    input           CLK_PAD_IO,
    input           RST_PAD_I,
    input           New_CMD,
    input           data_write,
    input           data_read,
    input  [31:0]   ARG_REG,
    input  [13:0]   CMD_SET_REG,
    input  [15:0]   TIMEOUT_REG,
    output reg [15:0] STATUS_REG,
    output reg [31:0] RESP_1_REG,
    output reg [4:0]  ERR_INT_REG,
    output reg [15:0] NORMAL_INT_REG,
    input           ERR_INT_RST,
    input           NORMAL_INT_RST,
    output reg [15:0] settings,
    output reg        go_idle_o,
    output reg [39:0] cmd_out,
    output reg        req_out,
    output reg        ack_out,
    input           req_in,
    input           ack_in,
    input  [39:0]   cmd_in,
    input  [7:0]    serial_status,
    input           card_detect
);

    // ========================================================================
    // B1 – Internal declarations: wires, registers, constants
    // ========================================================================

    // FSM state encodings
    localparam [2:0] IDLE    = 3'b001;
    localparam [2:0] SETUP   = 3'b010;
    localparam [2:0] EXECUTE = 3'b100;

    // Response-size constants
    localparam [6:0] small_rsp = 7'b0101000;
    localparam [6:0] big_rsp   = 7'b1111111;

    // STATUS_REG bit
    localparam CICMD = 0;
    // ERR_INT_REG bits
    localparam CTE   = 0;
    localparam CCRCE = 1;
    localparam CIE   = 3;
    // NORMAL_INT_REG bits
    localparam CC    = 0;
    localparam EI    = 15;
    localparam CARD_INSERT_INT = 1;
    localparam CARD_REMOVE_INT = 2;
    // serial_status bits
    localparam DAT_AVA_BIT   = 6;
    localparam CRC_VALID_BIT = 5;

    // FSM registers
    reg [2:0]  state;
    reg [2:0]  next_state;      // combinational next-state (declared as reg for procedural assignment)

    // Watchdog / debounce
    reg [15:0] Watchdog_Cnt;
    reg [3:0]  debounce;
    reg        card_present;

    // Synchroniser stages
    reg req_q;
    reg ack_q;
    reg req_in_int;
    reg ack_in_int;

    // Command-processing flags
    reg       complete;
    reg       CRC_check_enable;
    reg       index_check_enable;
    reg [6:0] response_size;        // registered response-size (latched in SETUP)
    reg [7:0] status;

    // B4 combinational pre-register signals
    reg [39:0] next_cmd_out;
    reg [15:0] next_settings;
    reg [6:0]  response_size_comb;  // combinational response_size (driven by B4 only)

    // CMD_SET_REG field breakout wires
    wire [5:0] CMDI;
    wire [1:0] WORD_SELECT;
    wire       CICE;
    wire       CRCE;
    wire [1:0] RTS;

    // Derived status/condition wires
    wire dat_ava;
    wire crc_valid;
    wire command_index_mismatch;
    wire timeout_expired;
    wire response_present;

    assign CMDI        = CMD_SET_REG[13:8];
    assign WORD_SELECT = CMD_SET_REG[7:6];
    assign CICE        = CMD_SET_REG[4];
    assign CRCE        = CMD_SET_REG[3];
    assign RTS         = CMD_SET_REG[1:0];

    assign dat_ava                = status[DAT_AVA_BIT];
    assign crc_valid              = status[CRC_VALID_BIT];
    assign command_index_mismatch = (cmd_out[37:32] != cmd_in[37:32]);
    assign timeout_expired        = (Watchdog_Cnt >= TIMEOUT_REG);
    assign response_present       = (response_size != 7'b0000000);


    // ========================================================================
    // B2 – Combinational next-state logic
    // ========================================================================
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


    // ========================================================================
    // B3 – Sequential FSM state register (async reset)
    // ========================================================================
    always @(posedge CLK_PAD_IO or posedge RST_PAD_I) begin
        if (RST_PAD_I) begin
            state <= #1 IDLE;
        end else begin
            state <= #1 next_state;
        end
    end


    // ========================================================================
    // B4 – Combinational command/settings assembly
    // ========================================================================
    always @(CMD_SET_REG or ARG_REG or data_read or data_write) begin
        case (CMD_SET_REG[1:0])
            2'b10: begin
                response_size_comb = small_rsp;
            end
            2'b11: begin
                response_size_comb = small_rsp;
            end
            2'b01: begin
                response_size_comb = big_rsp;
            end
            default: begin
                response_size_comb = 7'b0000000;
            end
        endcase

        next_cmd_out = {2'b01, CMD_SET_REG[13:8], ARG_REG};
        next_settings = {1'b0, CMD_SET_REG[7:6], data_read, data_write, 3'b111, CMD_SET_REG[3], response_size_comb};
    end


    // ========================================================================
    // B5 – Sequential debounce logic (async reset)
    // ========================================================================
    always @(posedge CLK_PAD_IO or posedge RST_PAD_I) begin
        if (RST_PAD_I) begin
            debounce     <= 4'b0000;
            card_present <= 1'b0;
        end else begin
            if (!card_detect) begin
                if (debounce != 4'b1111) begin
                    debounce <= debounce + 4'b0001;
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


    // ========================================================================
    // B6 – Sequential synchronisers for req_in / ack_in (async reset)
    // ========================================================================
    always @(posedge CLK_PAD_IO or posedge RST_PAD_I) begin
        if (RST_PAD_I) begin
            req_q      <= 1'b0;
            req_in_int <= 1'b0;
            ack_q      <= 1'b0;
            ack_in_int <= 1'b0;
        end else begin
            req_q      <= req_in;
            req_in_int <= req_q;
            ack_q      <= ack_in;
            ack_in_int <= ack_q;
        end
    end


    // ========================================================================
    // B7 – Sequential per-state operations (output updates, watchdog,
    //      handshake, interrupts, response capture)
    // ========================================================================
    always @(posedge CLK_PAD_IO or posedge RST_PAD_I) begin
        if (RST_PAD_I) begin
            CRC_check_enable   = 1'b0;
            complete           = 1'b0;
            RESP_1_REG         = 32'b00000000000000000000000000000000;
            ERR_INT_REG        = 5'b00000;
            NORMAL_INT_REG     = 16'b0000000000000000;
            STATUS_REG         = 16'b0000000000000000;
            status             = 8'b00000000;
            cmd_out            = 40'b0000000000000000000000000000000000000000;
            settings           = 16'b0000000000000000;
            response_size      = 7'b0000000;
            req_out            = 1'b0;
            index_check_enable = 1'b0;
            ack_out            = 1'b0;
            Watchdog_Cnt       = 16'b0000000000000000;
            go_idle_o          = 1'b0;
        end else begin
            NORMAL_INT_REG[CARD_INSERT_INT] = card_present;
            NORMAL_INT_REG[CARD_REMOVE_INT] = ~card_present;
            complete = 1'b0;

            case (state)
                IDLE: begin
                    go_idle_o            = 1'b0;
                    req_out              = 1'b0;
                    ack_out              = 1'b0;
                    STATUS_REG[CICMD]    = 1'b0;

                    if (req_in_int) begin
                        status  = serial_status;
                        ack_out = 1'b1;
                    end
                end

                SETUP: begin
                    NORMAL_INT_REG = 16'b0000000000000000;
                    ERR_INT_REG    = 5'b00000;

                    index_check_enable = CICE;
                    CRC_check_enable   = CRCE;

                    // Compute response_size inline (matching ref)
                    if ((RTS == 2'b10) || (RTS == 2'b11)) begin
                        response_size = small_rsp;
                    end else if (RTS == 2'b01) begin
                        response_size = big_rsp;
                    end else begin
                        response_size = 7'b0000000;
                    end

                    // Assemble cmd_out inline (matching ref)
                    cmd_out[39:38] = 2'b01;
                    cmd_out[37:32] = CMD_SET_REG[13:8];
                    cmd_out[31:0]  = ARG_REG;

                    // Assemble settings inline (matching ref)
                    settings[14:13] = CMD_SET_REG[7:6];
                    settings[12]    = data_read;
                    settings[11]    = data_write;
                    settings[10:8]  = 3'b111;
                    settings[7]     = CMD_SET_REG[3];
                    settings[6:0]   = response_size;

                    STATUS_REG[CICMD] = 1'b1;
                    Watchdog_Cnt       = 16'b0000000000000000;
                end

                EXECUTE: begin
                    Watchdog_Cnt = Watchdog_Cnt + 16'b0000000000000001;

                    if (Watchdog_Cnt > TIMEOUT_REG) begin
                        ERR_INT_REG[CTE] = 1'b1;
                        NORMAL_INT_REG[EI] = 1'b1;
                        go_idle_o = 1'b1;
                        if (ack_in) begin
                            complete = 1'b1;
                        end
                    end

                    req_out = 1'b0;
                    ack_out = 1'b0;

                    if (ack_in_int) begin
                        req_out = 1'b1;
                    end else if (req_in_int) begin
                        status  = serial_status;
                        ack_out = 1'b1;

                        if (dat_ava) begin
                            complete = 1'b1;
                            NORMAL_INT_REG[EI] = 1'b0;

                            if (CRC_check_enable & ~crc_valid) begin
                                ERR_INT_REG[CCRCE] = 1'b1;
                                NORMAL_INT_REG[EI] = 1'b1;
                            end

                            if (index_check_enable & (cmd_out[37:32] != cmd_in[37:32])) begin
                                ERR_INT_REG[CIE] = 1'b1;
                                NORMAL_INT_REG[EI] = 1'b1;
                            end

                            NORMAL_INT_REG[CC] = 1'b1;

                            if (response_size != 7'b0000000) begin
                                RESP_1_REG = cmd_in[31:0];
                            end
                        end
                    end
                end

                default: begin
                    go_idle_o = 1'b0;
                    req_out   = 1'b0;
                    ack_out   = 1'b0;
                end
            endcase

            if (ERR_INT_RST) begin
                ERR_INT_REG = 5'b00000;
            end
            if (NORMAL_INT_RST) begin
                NORMAL_INT_REG = 16'b0000000000000000;
            end
        end
    end

endmodule
