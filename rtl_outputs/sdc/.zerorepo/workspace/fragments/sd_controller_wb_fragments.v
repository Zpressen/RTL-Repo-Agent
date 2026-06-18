// STAGE5_SUBTASK_BEGIN B1_decl_core: Declare all internal storage: individual registers for each configuration register per S005 (argument, cmd_setting, etc.
// Register address map
localparam [7:0] ADDR_ARGUMENT              = 8'h00;
localparam [7:0] ADDR_CMD_SETTING           = 8'h04;
localparam [7:0] ADDR_CARD_STATUS           = 8'h08;
localparam [7:0] ADDR_RESPONSE              = 8'h0c;
localparam [7:0] ADDR_CONTROLLER_SETTING    = 8'h1c;
localparam [7:0] ADDR_BLOCK_SIZE            = 8'h20;
localparam [7:0] ADDR_POWER_CONTROL         = 8'h24;
localparam [7:0] ADDR_SOFTWARE_RESET        = 8'h28;
localparam [7:0] ADDR_TIMEOUT               = 8'h2c;
localparam [7:0] ADDR_NORMAL_INT_STATUS     = 8'h30;
localparam [7:0] ADDR_ERROR_INT_STATUS      = 8'h34;
localparam [7:0] ADDR_NORMAL_INT_ENABLE     = 8'h38;
localparam [7:0] ADDR_ERROR_INT_ENABLE      = 8'h3c;
localparam [7:0] ADDR_CAPABILITY            = 8'h48;
localparam [7:0] ADDR_CLOCK_DIVIDER         = 8'h4c;
localparam [7:0] ADDR_BD_STATUS             = 8'h50;
localparam [7:0] ADDR_BD_ISR_STATUS         = 8'h54;
localparam [7:0] ADDR_BD_ISR_ENABLE         = 8'h58;
localparam [7:0] ADDR_BD_RX_BASE            = 8'h60;
localparam [7:0] ADDR_BD_TX_BASE            = 8'h80;

// Reset values from the register specification and reset rules.
localparam [31:0] RESET_ARGUMENT_REG              = 32'h00000000;
localparam [15:0] RESET_CMD_SETTING_REG           = 16'h0000;
localparam [15:0] RESET_CONTROLLER_SETTING_REG    = 16'h0000;
localparam [15:0] RESET_BLOCK_SIZE_REG            = `BLOCK_SIZE;
localparam [7:0]  RESET_POWER_CONTROL_REG         = 8'h0f;
localparam [7:0]  RESET_SOFTWARE_RESET_REG        = 8'h00;
localparam [15:0] RESET_TIME_OUT_REG              = 16'h0000;
localparam [15:0] RESET_NORMAL_INT_ENABLE_REG     = 16'h0000;
localparam [15:0] RESET_ERROR_INT_ENABLE_REG      = 16'h0000;
localparam [15:0] RESET_CAPABILITY_REG            = 16'h0000;
localparam [7:0]  RESET_CLOCK_DIVIDER_REG         = `RESET_CLK_DIV;
localparam [7:0]  RESET_BD_ISR_ENABLE_REG         = 8'h00;
localparam [31:0] RESET_WB_DAT_O                  = 32'h00000000;
localparam        RESET_WB_ACK_O                  = 1'b0;
localparam        RESET_INT_ACK                   = 1'b1;
localparam        RESET_OUTPUT_ZERO               = 1'b0;
localparam [RAM_MEM_WIDTH-1:0] RESET_BD_DATA      = {RAM_MEM_WIDTH{1'b0}};

// Read-only register storage/constants local to the WISHBONE view.
reg [15:0] controller_setting_reg;
reg [15:0] block_size_reg;
reg [7:0]  power_control_reg;
reg [15:0] capability_reg;

// Buffer descriptor write side state and staging registers.
reg [1:0] bd_wr_state;
reg       bd_wr_is_rx;
reg       bd_wr_is_tx;
reg [7:0] bd_wr_addr;
reg [31:0] bd_wr_data;
reg [RAM_MEM_WIDTH-1:0] bd_rx_data_next;
reg [RAM_MEM_WIDTH-1:0] bd_tx_data_next;

localparam [1:0] BD_FSM_IDLE  = 2'b00;
localparam [1:0] BD_FSM_RX_WR = 2'b01;
localparam [1:0] BD_FSM_TX_WR = 2'b10;

// Decoded bus access wires and next-state/control intermediates.
wire wb_access;
wire wb_write_access;
wire wb_read_access;
wire [7:0] wb_addr;

reg [31:0] wb_dat_o_next;
reg        wb_ack_o_next;
reg        we_m_tx_bd_next;
reg        we_m_rx_bd_next;
reg        new_cmd_next;
reg        we_ack_next;
reg        int_ack_next;
reg        cmd_int_busy_next;
reg        int_busy_next;
reg        Bd_isr_reset_next;
reg        normal_isr_reset_next;
reg        error_isr_reset_next;

reg [31:0] argument_reg_next;
reg [15:0] cmd_setting_reg_next;
reg [7:0]  software_reset_reg_next;
reg [15:0] time_out_reg_next;
reg [15:0] normal_int_signal_enable_reg_next;
reg [15:0] error_int_signal_enable_reg_next;
reg [7:0]  clock_divider_next;
reg [7:0]  Bd_isr_enable_reg_next;
reg [15:0] controller_setting_reg_next;
reg [15:0] block_size_reg_next;
reg [7:0]  power_control_reg_next;
reg [15:0] capability_reg_next;
reg [RAM_MEM_WIDTH-1:0] dat_in_m_tx_bd_next;
reg [RAM_MEM_WIDTH-1:0] dat_in_m_rx_bd_next;
reg [1:0] bd_wr_state_next;
reg       bd_wr_is_rx_next;
reg       bd_wr_is_tx_next;
reg [7:0] bd_wr_addr_next;
reg [31:0] bd_wr_data_next;
// STAGE5_SUBTASK_END B1_decl_core

// STAGE5_SUBTASK_BEGIN B2_comb_decode_and_control: Generate combinational decode logic for address decoding (S005 register addresses), read data mux selecting from interna
assign wb_access       = wb_cyc_i & wb_stb_i;
assign wb_write_access = wb_cyc_i & wb_stb_i & wb_we_i;
assign wb_read_access  = wb_cyc_i & wb_stb_i & ~wb_we_i;
assign wb_addr         = wb_adr_i;

always @(wb_access or wb_write_access or wb_read_access or wb_addr or wb_dat_i or wb_ack_o or
         argument_reg or cmd_setting_reg or software_reset_reg or time_out_reg or
         normal_int_signal_enable_reg or error_int_signal_enable_reg or clock_divider or
         Bd_isr_enable_reg or controller_setting_reg or block_size_reg or power_control_reg or
         capability_reg or status_reg or cmd_resp_1 or normal_int_status_reg or error_int_status_reg or
         Bd_Status_reg or Bd_isr_reg or write_req_s or cmd_set_s or cmd_arg_s or int_ack or
         bd_wr_state or bd_wr_is_rx or bd_wr_is_tx or bd_wr_addr or bd_wr_data or
         dat_in_m_tx_bd or dat_in_m_rx_bd or bd_rx_data_next or bd_tx_data_next or
         wb_sel_i or we_m_tx_bd or we_m_rx_bd or new_cmd or we_ack or cmd_int_busy or int_busy or
         Bd_isr_reset or normal_isr_reset or error_isr_reset) begin
    wb_dat_o_next = wb_dat_o;
    wb_ack_o_next = 1'b0;
    we_m_tx_bd_next = 1'b0;
    we_m_rx_bd_next = 1'b0;
    new_cmd_next = 1'b0;
    we_ack_next = write_req_s;
    int_ack_next = 1'b1;
    cmd_int_busy_next = write_req_s;
    int_busy_next = 1'b0;
    Bd_isr_reset_next = 1'b0;
    normal_isr_reset_next = 1'b0;
    error_isr_reset_next = 1'b0;

    argument_reg_next = argument_reg;
    cmd_setting_reg_next = cmd_setting_reg;
    software_reset_reg_next = software_reset_reg;
    time_out_reg_next = time_out_reg;
    normal_int_signal_enable_reg_next = normal_int_signal_enable_reg;
    error_int_signal_enable_reg_next = error_int_signal_enable_reg;
    clock_divider_next = clock_divider;
    Bd_isr_enable_reg_next = Bd_isr_enable_reg;
    controller_setting_reg_next = controller_setting_reg;
    block_size_reg_next = block_size_reg;
    power_control_reg_next = power_control_reg;
    capability_reg_next = capability_reg;
    dat_in_m_tx_bd_next = dat_in_m_tx_bd;
    dat_in_m_rx_bd_next = dat_in_m_rx_bd;
    bd_wr_state_next = bd_wr_state;
    bd_wr_is_rx_next = bd_wr_is_rx;
    bd_wr_is_tx_next = bd_wr_is_tx;
    bd_wr_addr_next = bd_wr_addr;
    bd_wr_data_next = bd_wr_data;
    bd_rx_data_next = dat_in_m_rx_bd;
    bd_tx_data_next = dat_in_m_tx_bd;

    if (wb_read_access) begin
        case (wb_addr)
            ADDR_ARGUMENT:           wb_dat_o_next = argument_reg;
            ADDR_CMD_SETTING:        wb_dat_o_next = {16'h0000, cmd_setting_reg};
            ADDR_CARD_STATUS:        wb_dat_o_next = {16'h0000, status_reg};
            ADDR_RESPONSE:           wb_dat_o_next = cmd_resp_1;
            ADDR_CONTROLLER_SETTING: wb_dat_o_next = {16'h0000, controller_setting_reg};
            ADDR_BLOCK_SIZE:         wb_dat_o_next = {16'h0000, block_size_reg};
            ADDR_POWER_CONTROL:      wb_dat_o_next = {24'h000000, power_control_reg};
            ADDR_SOFTWARE_RESET:     wb_dat_o_next = {24'h000000, software_reset_reg};
            ADDR_TIMEOUT:            wb_dat_o_next = {16'h0000, time_out_reg};
            ADDR_NORMAL_INT_STATUS:  wb_dat_o_next = {15'h0000, normal_int_status_reg};
            ADDR_ERROR_INT_STATUS:   wb_dat_o_next = {15'h0000, error_int_status_reg};
            ADDR_NORMAL_INT_ENABLE:  wb_dat_o_next = {16'h0000, normal_int_signal_enable_reg};
            ADDR_ERROR_INT_ENABLE:   wb_dat_o_next = {16'h0000, error_int_signal_enable_reg};
            ADDR_CAPABILITY:         wb_dat_o_next = {16'h0000, capability_reg};
            ADDR_CLOCK_DIVIDER:      wb_dat_o_next = {24'h000000, clock_divider};
            ADDR_BD_STATUS:          wb_dat_o_next = {15'h0000, Bd_Status_reg};
            ADDR_BD_ISR_STATUS:      wb_dat_o_next = {24'h000000, Bd_isr_reg};
            ADDR_BD_ISR_ENABLE:      wb_dat_o_next = {24'h000000, Bd_isr_enable_reg};
            default:                 wb_dat_o_next = 32'h00000000;
        endcase
    end

    if (wb_write_access) begin
        case (wb_addr)
            ADDR_ARGUMENT: begin
                argument_reg_next = wb_dat_i;
                int_busy_next = 1'b1;
                new_cmd_next = 1'b1;
            end
            ADDR_CMD_SETTING: begin
                cmd_setting_reg_next = wb_dat_i[15:0];
            end
            ADDR_SOFTWARE_RESET: begin
                software_reset_reg_next = wb_dat_i[7:0];
            end
            ADDR_TIMEOUT: begin
                time_out_reg_next = wb_dat_i[15:0];
            end
            ADDR_NORMAL_INT_STATUS: begin
                normal_isr_reset_next = 1'b1;
            end
            ADDR_ERROR_INT_STATUS: begin
                error_isr_reset_next = 1'b1;
            end
            ADDR_NORMAL_INT_ENABLE: begin
                normal_int_signal_enable_reg_next = wb_dat_i[15:0];
            end
            ADDR_ERROR_INT_ENABLE: begin
                error_int_signal_enable_reg_next = wb_dat_i[15:0];
            end
            ADDR_CLOCK_DIVIDER: begin
                clock_divider_next = wb_dat_i[7:0];
            end
            ADDR_BD_ISR_STATUS: begin
                Bd_isr_reset_next = 1'b1;
            end
            ADDR_BD_ISR_ENABLE: begin
                Bd_isr_enable_reg_next = wb_dat_i[7:0];
            end
            default: begin
                if ((wb_addr >= ADDR_BD_RX_BASE) && (wb_addr < ADDR_BD_TX_BASE)) begin
                    bd_wr_state_next = BD_FSM_RX_WR;
                    bd_wr_is_rx_next = 1'b1;
                    bd_wr_is_tx_next = 1'b0;
                    bd_wr_addr_next = wb_addr;
                    bd_wr_data_next = wb_dat_i;
                    int_ack_next = 1'b0;
                end else if (wb_addr >= ADDR_BD_TX_BASE) begin
                    bd_wr_state_next = BD_FSM_TX_WR;
                    bd_wr_is_rx_next = 1'b0;
                    bd_wr_is_tx_next = 1'b1;
                    bd_wr_addr_next = wb_addr;
                    bd_wr_data_next = wb_dat_i;
                    int_ack_next = 1'b0;
                end
            end
        endcase
    end

    case (bd_wr_state)
        BD_FSM_IDLE: begin
            if (wb_write_access && (wb_addr >= ADDR_BD_RX_BASE) && (wb_addr < ADDR_BD_TX_BASE)) begin
                int_ack_next = 1'b0;
                we_m_rx_bd_next = 1'b1;
                dat_in_m_rx_bd_next = wb_dat_i[RAM_MEM_WIDTH-1:0];
                bd_rx_data_next = wb_dat_i[RAM_MEM_WIDTH-1:0];
                bd_wr_state_next = BD_FSM_IDLE;
                bd_wr_is_rx_next = 1'b0;
            end else if (wb_write_access && (wb_addr >= ADDR_BD_TX_BASE)) begin
                int_ack_next = 1'b0;
                we_m_tx_bd_next = 1'b1;
                dat_in_m_tx_bd_next = wb_dat_i[RAM_MEM_WIDTH-1:0];
                bd_tx_data_next = wb_dat_i[RAM_MEM_WIDTH-1:0];
                bd_wr_state_next = BD_FSM_IDLE;
                bd_wr_is_tx_next = 1'b0;
            end
        end
        BD_FSM_RX_WR: begin
            int_ack_next = 1'b1;
            we_m_rx_bd_next = 1'b0;
            bd_wr_state_next = BD_FSM_IDLE;
            bd_wr_is_rx_next = 1'b0;
            bd_wr_is_tx_next = 1'b0;
        end
        BD_FSM_TX_WR: begin
            int_ack_next = 1'b1;
            we_m_tx_bd_next = 1'b0;
            bd_wr_state_next = BD_FSM_IDLE;
            bd_wr_is_rx_next = 1'b0;
            bd_wr_is_tx_next = 1'b0;
        end
        default: begin
            int_ack_next = 1'b1;
            we_m_rx_bd_next = 1'b0;
            we_m_tx_bd_next = 1'b0;
            bd_wr_state_next = BD_FSM_IDLE;
            bd_wr_is_rx_next = 1'b0;
            bd_wr_is_tx_next = 1'b0;
        end
    endcase

    if (wb_access && ~wb_ack_o && int_ack_next) begin
        wb_ack_o_next = 1'b1;
    end else begin
        wb_ack_o_next = 1'b0;
    end
end
// STAGE5_SUBTASK_END B2_comb_decode_and_control

// STAGE5_SUBTASK_BEGIN B3_seq_all_clocked: Implement clocked processes (always @(posedge wb_clk_i or posedge wb_rst_i)) that update all registers: on reset, apply 
always @(posedge wb_clk_i or posedge wb_rst_i) begin
    if (wb_rst_i) begin
        wb_dat_o <= RESET_WB_DAT_O;
        wb_ack_o <= RESET_WB_ACK_O;

        we_m_tx_bd <= RESET_OUTPUT_ZERO;
        we_m_rx_bd <= RESET_OUTPUT_ZERO;
        new_cmd <= RESET_OUTPUT_ZERO;
        we_ack <= RESET_OUTPUT_ZERO;
        int_ack <= RESET_INT_ACK;
        cmd_int_busy <= RESET_OUTPUT_ZERO;
        int_busy <= RESET_OUTPUT_ZERO;
        Bd_isr_reset <= RESET_OUTPUT_ZERO;
        normal_isr_reset <= RESET_OUTPUT_ZERO;
        error_isr_reset <= RESET_OUTPUT_ZERO;

        argument_reg <= RESET_ARGUMENT_REG;
        cmd_setting_reg <= RESET_CMD_SETTING_REG;
        software_reset_reg <= RESET_SOFTWARE_RESET_REG;
        time_out_reg <= RESET_TIME_OUT_REG;
        normal_int_signal_enable_reg <= RESET_NORMAL_INT_ENABLE_REG;
        error_int_signal_enable_reg <= RESET_ERROR_INT_ENABLE_REG;
        clock_divider <= RESET_CLOCK_DIVIDER_REG;
        Bd_isr_enable_reg <= RESET_BD_ISR_ENABLE_REG;

        controller_setting_reg <= RESET_CONTROLLER_SETTING_REG;
        block_size_reg <= RESET_BLOCK_SIZE_REG;
        power_control_reg <= RESET_POWER_CONTROL_REG;
        capability_reg <= RESET_CAPABILITY_REG;

        dat_in_m_tx_bd <= RESET_BD_DATA;
        dat_in_m_rx_bd <= RESET_BD_DATA;
        bd_wr_state <= BD_FSM_IDLE;
        bd_wr_is_rx <= 1'b0;
        bd_wr_is_tx <= 1'b0;
        bd_wr_addr <= 8'h00;
        bd_wr_data <= 32'h00000000;
    end else begin
        wb_dat_o <= wb_dat_o_next;
        wb_ack_o <= wb_ack_o_next;

        we_m_tx_bd <= we_m_tx_bd_next;
        we_m_rx_bd <= we_m_rx_bd_next;
        new_cmd <= new_cmd_next;
        we_ack <= we_ack_next;
        int_ack <= int_ack_next;
        cmd_int_busy <= cmd_int_busy_next;
        int_busy <= int_busy_next;
        Bd_isr_reset <= Bd_isr_reset_next;
        normal_isr_reset <= normal_isr_reset_next;
        error_isr_reset <= error_isr_reset_next;

        argument_reg <= argument_reg_next;
        cmd_setting_reg <= cmd_setting_reg_next;
        software_reset_reg <= software_reset_reg_next;
        time_out_reg <= time_out_reg_next;
        normal_int_signal_enable_reg <= normal_int_signal_enable_reg_next;
        error_int_signal_enable_reg <= error_int_signal_enable_reg_next;
        clock_divider <= clock_divider_next;
        Bd_isr_enable_reg <= Bd_isr_enable_reg_next;

        controller_setting_reg <= controller_setting_reg_next;
        block_size_reg <= block_size_reg_next;
        power_control_reg <= power_control_reg_next;
        capability_reg <= capability_reg_next;

        dat_in_m_tx_bd <= dat_in_m_tx_bd_next;
        dat_in_m_rx_bd <= dat_in_m_rx_bd_next;
        bd_wr_state <= bd_wr_state_next;
        bd_wr_is_rx <= bd_wr_is_rx_next;
        bd_wr_is_tx <= bd_wr_is_tx_next;
        bd_wr_addr <= bd_wr_addr_next;
        bd_wr_data <= bd_wr_data_next;
    end
end
// STAGE5_SUBTASK_END B3_seq_all_clocked

// STAGE5_SUBTASK_BEGIN B4_port_assign: Directly assign internal register values to output ports as defined in interface S003. No extra logic; purely wire conne
// S003 output ports are implemented as registered outputs in the clocked block.
// No additional continuous port assignments are required here.
// STAGE5_SUBTASK_END B4_port_assign
