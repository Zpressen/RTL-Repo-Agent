// STAGE5_SUBTASK_BEGIN B1_decl_core_objects: Declare all Verilog ports, parameters, localparams (including INIT_DELAY, NCR, SEND_SIZE, SIZE, CONTENT_SIZE, Read_Delay
input SD_CLK_IN;
input RST_IN;
input [15:0] SETTING_IN;
input [39:0] CMD_IN;
input REQ_IN;
input ACK_IN;
input cmd_dat_i;

output reg [39:0] CMD_OUT;
output reg ACK_OUT;
output reg REQ_OUT;
output reg [7:0] STATUS;
output reg cmd_oe_o;
output reg cmd_out_o;
output reg [1:0] st_dat_t;

`ifdef SIM
localparam INIT_DELAY = 2;
`else
localparam INIT_DELAY = 64;
`endif
localparam NCR = 2;
localparam SEND_SIZE = 48;
localparam SIZE = 10;
localparam CONTENT_SIZE = 40;
localparam Read_Delay = 7;
localparam EIGHT_PAD = 8;

localparam [SIZE-1:0] INIT     = 10'b0000000001;
localparam [SIZE-1:0] IDLE     = 10'b0000000010;
localparam [SIZE-1:0] WRITE_WR = 10'b0000000100;
localparam [SIZE-1:0] DLY_WR   = 10'b0000001000;
localparam [SIZE-1:0] READ_WR  = 10'b0000010000;
localparam [SIZE-1:0] DLY_READ = 10'b0000100000;
localparam [SIZE-1:0] ACK_WR   = 10'b0001000000;
localparam [SIZE-1:0] WRITE_WO = 10'b0010000000;
localparam [SIZE-1:0] DLY_WO   = 10'b0100000000;
localparam [SIZE-1:0] ACK_WO   = 10'b1000000000;

reg [6:0] Response_Size;
reg [2:0] Delay_Cycler;
reg [CONTENT_SIZE-1:0] In_Buff;
reg [CONTENT_SIZE-1:0] Out_Buff;
reg Write_Read;
reg Write_Only;
reg [4:0] word_select_counter;
reg CRC_RST;
reg [6:0] CRC_IN;
wire [6:0] CRC_VAL;
reg CRC_Enable;
reg CRC_OUT;
reg CRC_Check_On;
reg Crc_Buffering;
reg CRC_Valid;
reg [7:0] Cmd_Cnt;
reg [2:0] Delay_Cnt;
reg [SIZE-1:0] state;
reg [SIZE-1:0] next_state;
reg block_write;
reg block_read;
reg [1:0] word_select;
reg FSM_ACK;
reg DECODER_ACK;
reg q;
reg Req_internal_in;
reg q1;
reg Ack_internal_in;
// STAGE5_SUBTASK_END B1_decl_core_objects

// STAGE5_SUBTASK_BEGIN B2_inst_crc7: Instantiate exactly one sd_crc_7 submodule with ports BITVAL, Enable, CLK, RST, CRC connected as described in S016. Conn
sd_crc_7 crc_7_inst (
    .BITVAL(CRC_IN[6]),
    .Enable(CRC_Enable),
    .CLK(SD_CLK_IN),
    .RST(CRC_RST),
    .CRC(CRC_VAL)
);
// STAGE5_SUBTASK_END B2_inst_crc7

// STAGE5_SUBTASK_BEGIN B3_sync_req: Implement a two-flip-flop synchronizer for REQ_IN to Req_internal_in using intermediate register q, clocked by SD_CLK_IN
always @(posedge SD_CLK_IN or posedge RST_IN) begin
    if (RST_IN) begin
        q <= 1'b0;
        Req_internal_in <= 1'b0;
    end else begin
        q <= REQ_IN;
        Req_internal_in <= q;
    end
end
// STAGE5_SUBTASK_END B3_sync_req

// STAGE5_SUBTASK_BEGIN B4_sync_ack: Implement a two-flip-flop synchronizer for ACK_IN to Ack_internal_in using intermediate register q1, clocked by SD_CLK_I
always @(posedge SD_CLK_IN or posedge RST_IN) begin
    if (RST_IN) begin
        q1 <= 1'b0;
        Ack_internal_in <= 1'b0;
    end else begin
        q1 <= ACK_IN;
        Ack_internal_in <= q1;
    end
end
// STAGE5_SUBTASK_END B4_sync_ack

// STAGE5_SUBTASK_BEGIN B5_command_decoder: Sequential command decoder block. On synchronous reset (RST_IN high), clear all internal registers and set DECODER_ACK=1
always @(posedge SD_CLK_IN) begin
    if (RST_IN) begin
        Delay_Cycler <= 3'b000;
        Response_Size <= 7'b0000000;
        DECODER_ACK <= 1'b1;
        Write_Read <= 1'b0;
        Write_Only <= 1'b0;
        CRC_Check_On <= 1'b0;
        In_Buff <= {CONTENT_SIZE{1'b0}};
        block_write <= 1'b0;
        block_read <= 1'b0;
        word_select <= 2'b00;
    end else if (Req_internal_in) begin
        Response_Size <= SETTING_IN[6:0];
        CRC_Check_On <= SETTING_IN[7];
        Delay_Cycler <= SETTING_IN[10:8];
        block_write <= SETTING_IN[11];
        block_read <= SETTING_IN[12];
        word_select <= SETTING_IN[14:13];
        In_Buff <= CMD_IN;
        if (SETTING_IN[6:0] != 7'b0000000) begin
            Write_Read <= 1'b1;
            Write_Only <= 1'b0;
        end else begin
            Write_Read <= 1'b0;
            Write_Only <= 1'b1;
        end
        DECODER_ACK <= 1'b0;
    end else begin
        Write_Read <= 1'b0;
        Write_Only <= 1'b0;
        DECODER_ACK <= 1'b1;
    end
end
// STAGE5_SUBTASK_END B5_command_decoder

// STAGE5_SUBTASK_BEGIN B6_fsm_combo: Combinational next-state logic for the ten-state FSM. Compute next_state from current state, Cmd_Cnt, Delay_Cnt, Write_R
always @(state or Cmd_Cnt or Delay_Cnt or Write_Read or Write_Only or Req_internal_in or Ack_internal_in or cmd_dat_i or Response_Size or Delay_Cycler or block_read or block_write) begin
    next_state = INIT;
    case (state)
        INIT: begin
            if (Cmd_Cnt >= INIT_DELAY) begin
                next_state = IDLE;
            end else begin
                next_state = INIT;
            end
        end
        IDLE: begin
            if (Write_Read) begin
                next_state = WRITE_WR;
            end else if (Write_Only) begin
                next_state = WRITE_WO;
            end else begin
                next_state = IDLE;
            end
        end
        WRITE_WR: begin
            if (Cmd_Cnt >= (SEND_SIZE - 1)) begin
                next_state = DLY_WR;
            end else begin
                next_state = WRITE_WR;
            end
        end
        DLY_WR: begin
            if ((Delay_Cnt >= NCR) && !cmd_dat_i) begin
                next_state = READ_WR;
            end else begin
                next_state = DLY_WR;
            end
        end
        READ_WR: begin
            if (Cmd_Cnt >= (Response_Size + EIGHT_PAD)) begin
                next_state = DLY_READ;
            end else begin
                next_state = READ_WR;
            end
        end
        DLY_READ: begin
            if (Ack_internal_in) begin
                next_state = ACK_WR;
            end else begin
                next_state = DLY_READ;
            end
        end
        ACK_WR: begin
            next_state = IDLE;
        end
        WRITE_WO: begin
            if (Cmd_Cnt >= (SEND_SIZE - 1)) begin
                next_state = DLY_WO;
            end else begin
                next_state = WRITE_WO;
            end
        end
        DLY_WO: begin
            if (Delay_Cnt >= Delay_Cycler) begin
                next_state = ACK_WO;
            end else begin
                next_state = DLY_WO;
            end
        end
        ACK_WO: begin
            next_state = IDLE;
        end
        default: begin
            next_state = INIT;
        end
    endcase
end
// STAGE5_SUBTASK_END B6_fsm_combo

// STAGE5_SUBTASK_BEGIN B7_fsm_seq_state_update: Sequential state register update. On posedge SD_CLK_IN with synchronous active-high reset (RST_IN), set state to INIT wh
always @(posedge SD_CLK_IN) begin
    if (RST_IN) begin
        state <= INIT;
    end else begin
        state <= next_state;
    end
end
// STAGE5_SUBTASK_END B7_fsm_seq_state_update

// STAGE5_SUBTASK_BEGIN B8_fsm_out: Registered output and counter control block. On posedge SD_CLK_IN with synchronous reset (RST_IN), initialize all regist
wire [7:0] Vector_Index;
wire [7:0] Bit_Nr;

assign Vector_Index = (CONTENT_SIZE - 1) - Cmd_Cnt;
assign Bit_Nr = (SEND_SIZE - 1) - Cmd_Cnt;

always @(posedge SD_CLK_IN) begin
    if (RST_IN) begin
        CRC_Enable <= 1'b0;
        word_select_counter <= 5'b00000;
        Delay_Cnt <= 3'b000;
        cmd_oe_o <= 1'b1;
        cmd_out_o <= 1'b1;
        Out_Buff <= {CONTENT_SIZE{1'b0}};
        FSM_ACK <= 1'b1;
        ACK_OUT <= 1'b0;
        REQ_OUT <= 1'b0;
        CRC_RST <= 1'b1;
        CRC_OUT <= 1'b0;
        CRC_IN <= 7'b0000000;
        CMD_OUT <= {CONTENT_SIZE{1'b0}};
        Crc_Buffering <= 1'b0;
        STATUS <= 8'b00000000;
        CRC_Valid <= 1'b0;
        Cmd_Cnt <= 8'b00000000;
        st_dat_t <= 2'b00;
    end else begin
        ACK_OUT <= FSM_ACK & DECODER_ACK;
        case (state)
            INIT: begin
                Cmd_Cnt <= Cmd_Cnt + 1'b1;
                cmd_oe_o <= 1'b1;
                cmd_out_o <= 1'b1;
                FSM_ACK <= 1'b1;
            end

            IDLE: begin
                cmd_oe_o <= 1'b0;
                cmd_out_o <= 1'b1;
                Delay_Cnt <= 3'b000;
                Cmd_Cnt <= 8'b00000000;
                CRC_RST <= 1'b1;
                CRC_Enable <= 1'b0;
                CRC_OUT <= 1'b0;
                CRC_IN <= 7'b0000000;
                CMD_OUT <= {CONTENT_SIZE{1'b0}};
                Crc_Buffering <= 1'b0;
                st_dat_t <= 2'b00;
                word_select_counter <= 5'b00000;
                FSM_ACK <= 1'b1;
                REQ_OUT <= 1'b0;
            end

            WRITE_WR: begin
                FSM_ACK <= 1'b0;
                CRC_RST <= 1'b0;
                CRC_Enable <= 1'b1;
                if (Cmd_Cnt == 8'b00000000) begin
                    STATUS <= 8'b00000001;
                    REQ_OUT <= 1'b1;
                end else if (Ack_internal_in) begin
                    REQ_OUT <= 1'b0;
                end

                if (Crc_Buffering) begin
                    cmd_oe_o <= 1'b1;
                    if (Bit_Nr > 8) begin
                        if (Vector_Index < CONTENT_SIZE) begin
                            cmd_out_o <= In_Buff[Vector_Index];
                            CRC_OUT <= In_Buff[Vector_Index];
                            CRC_IN[6] <= In_Buff[Vector_Index];
                        end else begin
                            cmd_out_o <= 1'b1;
                            CRC_OUT <= 1'b1;
                            CRC_IN[6] <= 1'b1;
                        end
                    end else if ((Bit_Nr <= 8) && (Bit_Nr >= 2)) begin
                        cmd_out_o <= CRC_VAL[Bit_Nr - 2];
                        CRC_OUT <= CRC_VAL[Bit_Nr - 2];
                        CRC_Enable <= 1'b0;
                        if (block_read && block_write) begin
                            st_dat_t <= 2'b11;
                        end else if (block_write) begin
                            st_dat_t <= 2'b01;
                        end else if (block_read) begin
                            st_dat_t <= 2'b10;
                        end
                    end else begin
                        cmd_out_o <= 1'b1;
                        CRC_OUT <= 1'b1;
                        CRC_Enable <= 1'b0;
                    end
                    Cmd_Cnt <= Cmd_Cnt + 1'b1;
                end else begin
                    Crc_Buffering <= 1'b1;
                    if (Vector_Index < CONTENT_SIZE) begin
                        CRC_OUT <= In_Buff[Vector_Index];
                        CRC_IN[6] <= In_Buff[Vector_Index];
                    end
                end
            end

            WRITE_WO: begin
                FSM_ACK <= 1'b0;
                CRC_RST <= 1'b0;
                CRC_Enable <= 1'b1;
                if (Cmd_Cnt == 8'b00000000) begin
                    STATUS[3:0] <= 4'b0010;
                    REQ_OUT <= 1'b1;
                end else if (Ack_internal_in) begin
                    REQ_OUT <= 1'b0;
                end

                if (Crc_Buffering) begin
                    cmd_oe_o <= 1'b1;
                    if (Bit_Nr > 8) begin
                        if (Vector_Index < CONTENT_SIZE) begin
                            cmd_out_o <= In_Buff[Vector_Index];
                            CRC_OUT <= In_Buff[Vector_Index];
                            CRC_IN[6] <= In_Buff[Vector_Index];
                        end else begin
                            cmd_out_o <= 1'b1;
                            CRC_OUT <= 1'b1;
                            CRC_IN[6] <= 1'b1;
                        end
                    end else if ((Bit_Nr <= 8) && (Bit_Nr >= 2)) begin
                        cmd_out_o <= CRC_VAL[Bit_Nr - 2];
                        CRC_OUT <= CRC_VAL[Bit_Nr - 2];
                        CRC_Enable <= 1'b0;
                        if (block_read && block_write) begin
                            st_dat_t <= 2'b11;
                        end else if (block_write) begin
                            st_dat_t <= 2'b01;
                        end else if (block_read) begin
                            st_dat_t <= 2'b10;
                        end
                    end else begin
                        cmd_out_o <= 1'b1;
                        CRC_OUT <= 1'b1;
                        CRC_Enable <= 1'b0;
                    end
                    Cmd_Cnt <= Cmd_Cnt + 1'b1;
                end else begin
                    Crc_Buffering <= 1'b1;
                    if (Vector_Index < CONTENT_SIZE) begin
                        CRC_OUT <= In_Buff[Vector_Index];
                        CRC_IN[6] <= In_Buff[Vector_Index];
                    end
                end
            end

            DLY_WR: begin
                if (Delay_Cnt == 3'b000) begin
                    STATUS[3:0] <= 4'b0011;
                    REQ_OUT <= 1'b1;
                end else if (Ack_internal_in) begin
                    REQ_OUT <= 1'b0;
                end
                CRC_Enable <= 1'b0;
                CRC_RST <= 1'b1;
                Cmd_Cnt <= 8'b00000001;
                cmd_oe_o <= 1'b0;
                cmd_out_o <= 1'b1;
                if (Delay_Cnt < 3'b111) begin
                    Delay_Cnt <= Delay_Cnt + 1'b1;
                end
                Crc_Buffering <= 1'b0;
            end

            DLY_WO: begin
                if (Delay_Cnt == 3'b000) begin
                    STATUS[3:0] <= 4'b0100;
                    STATUS[5] <= 1'b0;
                    STATUS[6] <= 1'b1;
                    REQ_OUT <= 1'b1;
                end else if (Ack_internal_in) begin
                    REQ_OUT <= 1'b0;
                end
                CRC_Enable <= 1'b0;
                CRC_RST <= 1'b1;
                Cmd_Cnt <= 8'b00000000;
                cmd_oe_o <= 1'b0;
                cmd_out_o <= 1'b1;
                Delay_Cnt <= Delay_Cnt + 1'b1;
                Crc_Buffering <= 1'b0;
            end

            READ_WR: begin
                Delay_Cnt <= 3'b000;
                CRC_RST <= 1'b0;
                CRC_Enable <= 1'b1;
                cmd_oe_o <= 1'b0;
                cmd_out_o <= 1'b1;
                if (Cmd_Cnt == 8'b00000001) begin
                    STATUS[3:0] <= 4'b0101;
                    REQ_OUT <= 1'b1;
                    Out_Buff[39] <= 1'b0;
                end else if (Ack_internal_in) begin
                    REQ_OUT <= 1'b0;
                end

                if (Cmd_Cnt < Response_Size) begin
                    CRC_OUT <= cmd_dat_i;
                    CRC_IN[6] <= cmd_dat_i;
                    if (word_select == 2'b00) begin
                        if (Cmd_Cnt < CONTENT_SIZE) begin
                            Out_Buff[(CONTENT_SIZE - 1) - Cmd_Cnt] <= cmd_dat_i;
                        end
                    end else if (word_select == 2'b01) begin
                        if ((Cmd_Cnt + 8) < CONTENT_SIZE) begin
                            Out_Buff[(CONTENT_SIZE - 1) - (Cmd_Cnt + 8)] <= cmd_dat_i;
                        end
                    end else if (word_select == 2'b10) begin
                        if ((Cmd_Cnt + 16) < CONTENT_SIZE) begin
                            Out_Buff[(CONTENT_SIZE - 1) - (Cmd_Cnt + 16)] <= cmd_dat_i;
                        end
                    end else begin
                        if ((Cmd_Cnt + 24) < CONTENT_SIZE) begin
                            Out_Buff[(CONTENT_SIZE - 1) - (Cmd_Cnt + 24)] <= cmd_dat_i;
                        end
                    end
                    Cmd_Cnt <= Cmd_Cnt + 1'b1;
                end else if ((Cmd_Cnt - Response_Size) <= 7'd6) begin
                    CRC_Enable <= 1'b0;
                    CRC_IN[6 - (Cmd_Cnt - Response_Size)] <= cmd_dat_i;
                    Cmd_Cnt <= Cmd_Cnt + 1'b1;
                end else begin
                    CRC_Enable <= 1'b0;
                    if ((CRC_IN != CRC_VAL) && CRC_Check_On) begin
                        CRC_Valid <= 1'b0;
                    end else begin
                        CRC_Valid <= 1'b1;
                    end
                    if (block_read && block_write) begin
                        st_dat_t <= 2'b11;
                    end else if (block_write) begin
                        st_dat_t <= 2'b01;
                    end
                    Cmd_Cnt <= Cmd_Cnt + 1'b1;
                end
            end

            DLY_READ: begin
                if (Delay_Cnt == 3'b000) begin
                    STATUS[3:0] <= 4'b0110;
                    STATUS[5] <= CRC_Valid;
                    STATUS[6] <= 1'b1;
                    REQ_OUT <= 1'b1;
                end else if (Ack_internal_in) begin
                    REQ_OUT <= 1'b0;
                end
                CRC_Enable <= 1'b0;
                CRC_RST <= 1'b1;
                Cmd_Cnt <= 8'b00000000;
                cmd_oe_o <= 1'b0;
                cmd_out_o <= 1'b1;
                CMD_OUT <= Out_Buff;
                Delay_Cnt <= Delay_Cnt + 1'b1;
            end

            ACK_WO: begin
                FSM_ACK <= 1'b1;
            end

            ACK_WR: begin
                FSM_ACK <= 1'b1;
                REQ_OUT <= 1'b0;
            end

            default: begin
                CRC_Enable <= 1'b0;
                CRC_RST <= 1'b1;
                REQ_OUT <= 1'b0;
                cmd_oe_o <= 1'b0;
                cmd_out_o <= 1'b1;
            end
        endcase
    end
end
// STAGE5_SUBTASK_END B8_fsm_out
