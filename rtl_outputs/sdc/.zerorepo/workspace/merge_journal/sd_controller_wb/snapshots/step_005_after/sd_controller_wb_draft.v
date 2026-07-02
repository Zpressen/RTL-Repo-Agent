`include "sd_defines.v"

// Essential macro definitions from authoritative sd_defines.v
// (values per global_defines manifest: RAM_MEM_WIDTH=16, BD_WIDTH=5, BD_SIZE=32)
// These are guarded so official sd_defines.v values take priority when found.
`ifndef RAM_MEM_WIDTH
  `define RAM_MEM_WIDTH 16
`endif
`ifndef RAM_MEM_WIDTH_16
  `define RAM_MEM_WIDTH_16
`endif
`ifndef BD_WIDTH
  `define BD_WIDTH 5
`endif
`ifndef BD_SIZE
  `define BD_SIZE 32
`endif

module sd_controller_wb (
    // WISHBONE slave interface
    input  wire             wb_clk_i,
    input  wire             wb_rst_i,
    input  wire [31:0]      wb_dat_i,
    output reg  [31:0]      wb_dat_o,
    input  wire [7:0]       wb_adr_i,
    input  wire [3:0]       wb_sel_i,
    input  wire             wb_we_i,
    input  wire             wb_cyc_i,
    input  wire             wb_stb_i,
    output reg              wb_ack_o,

    // Control outputs to other sub-modules
    output reg              we_m_tx_bd,
    output reg              we_m_rx_bd,
    output reg              new_cmd,
    output reg              we_ack,
    output reg              int_ack,
    output reg              cmd_int_busy,
    output reg              int_busy,
    output reg              Bd_isr_reset,
    output reg              normal_isr_reset,
    output reg              error_isr_reset,

    // Data master interface
    input  wire             write_req_s,
    input  wire [15:0]      cmd_set_s,
    input  wire [31:0]      cmd_arg_s,

    // Configuration registers exposed as outputs
    output reg  [31:0]      argument_reg,
    output reg  [15:0]      cmd_setting_reg,
    output reg  [7:0]       software_reset_reg,
    output reg  [15:0]      time_out_reg,
    output reg  [15:0]      normal_int_signal_enable_reg,
    output reg  [15:0]      error_int_signal_enable_reg,
    output reg  [7:0]       clock_divider,
    output reg  [7:0]       Bd_isr_enable_reg,

    // Status/response inputs from rest of design
    input  wire [15:0]      status_reg,
    input  wire [31:0]      cmd_resp_1,
    input  wire [16:0]      normal_int_status_reg,
    input  wire [16:0]      error_int_status_reg,
    input  wire [16:0]      Bd_Status_reg,
    input  wire [7:0]       Bd_isr_reg,

    // BD data outputs to buffer descriptor blocks
    output reg  [RAM_MEM_WIDTH-1:0] dat_in_m_tx_bd,
    output reg  [RAM_MEM_WIDTH-1:0] dat_in_m_rx_bd
);

// ===========================================================================
// STAGE5_SUBTASK_BEGIN B1_decl_core
// ===========================================================================
localparam [31:0] ARGUMENT_REG_RESET                  = 32'h00000000;
localparam [15:0] CMD_SETTING_REG_RESET               = 16'h0000;
localparam [15:0] CONTROLLER_SETTING_RESET            = 16'h0000;
localparam [15:0] BLOCK_SIZE_RESET                    = 16'h0200;
localparam [7:0]  POWER_CONTROL_RESET                 = 8'h0f;
localparam [7:0]  SOFTWARE_RESET_REG_RESET            = 8'h00;
localparam [15:0] TIME_OUT_REG_RESET                  = 16'h0000;
localparam [15:0] NORMAL_INT_SIGNAL_ENABLE_REG_RESET  = 16'h0000;
localparam [15:0] ERROR_INT_SIGNAL_ENABLE_REG_RESET   = 16'h0000;
localparam [15:0] CAPABILITY_REG_RESET                = 16'h0000;
localparam [7:0]  CLOCK_DIVIDER_RESET                 = 8'h00;
localparam [7:0]  BD_ISR_ENABLE_REG_RESET             = 8'h00;
localparam [1:0]  BD_FSM_IDLE                         = 2'b00;
localparam [1:0]  BD_FSM_RX_LOW                       = 2'b01;
localparam [1:0]  BD_FSM_RX_HIGH                      = 2'b10;
localparam [1:0]  BD_FSM_TX_LOW                       = 2'b11;

reg [31:0] argument_reg_next;
reg [15:0] cmd_setting_reg_next;
reg [7:0]  software_reset_reg_next;
reg [15:0] time_out_reg_next;
reg [15:0] normal_int_signal_enable_reg_next;
reg [15:0] error_int_signal_enable_reg_next;
reg [7:0]  clock_divider_next;
reg [7:0]  Bd_isr_enable_reg_next;

reg [1:0]  bd_fsm_state;
reg [1:0]  bd_fsm_state_next;
reg [31:0] bd_rx_low_word;
reg [31:0] bd_rx_high_word;
reg [31:0] bd_tx_low_word;
reg [31:0] bd_tx_high_word;
reg [31:0] bd_rx_low_word_next;
reg [31:0] bd_rx_high_word_next;
reg [31:0] bd_tx_low_word_next;
reg [31:0] bd_tx_high_word_next;

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
reg [RAM_MEM_WIDTH-1:0] dat_in_m_tx_bd_next;
reg [RAM_MEM_WIDTH-1:0] dat_in_m_rx_bd_next;

wire       wb_access;
wire       wb_write_access;
wire       wb_read_access;
wire [7:0] wb_addr;
wire       wb_sel_byte0;
wire       wb_sel_byte1;
wire       wb_sel_byte2;
wire       wb_sel_byte3;

wire       addr_argument;
wire       addr_cmd_setting;
wire       addr_card_status;
wire       addr_response;
wire       addr_controller_setting;
wire       addr_block_size;
wire       addr_power_control;
wire       addr_software_reset;
wire       addr_timeout;
wire       addr_normal_int_status;
wire       addr_error_int_status;
wire       addr_normal_int_enable;
wire       addr_error_int_enable;
wire       addr_capability;
wire       addr_clock_divider;
wire       addr_bd_status;
wire       addr_bd_isr_status;
wire       addr_bd_isr_enable;
wire       addr_bd_rx;
wire       addr_bd_tx;

wire [15:0] controller_setting_value;
wire [15:0] block_size_value;
wire [7:0]  power_control_value;
wire [15:0] capability_value;
wire [15:0] normal_int_status_value;
wire [15:0] error_int_status_value;
wire [15:0] bd_status_value;
wire [7:0]  bd_isr_status_value;

wire       command_write_pulse;
wire       argument_write_pulse;
wire       normal_isr_clear_pulse;
wire       error_isr_clear_pulse;
wire       bd_isr_clear_pulse;
wire       bd_rx_write_pulse;
wire       bd_tx_write_pulse;
// STAGE5_SUBTASK_END B1_decl_core

// ===========================================================================
// STAGE5_SUBTASK_BEGIN B2_comb_decode_and_control
// ===========================================================================
assign wb_access       = wb_cyc_i & wb_stb_i;
assign wb_write_access = wb_access & wb_we_i;
assign wb_read_access  = wb_access & ~wb_we_i;
assign wb_addr         = wb_adr_i;
assign wb_sel_byte0    = wb_sel_i[0];
assign wb_sel_byte1    = wb_sel_i[1];
assign wb_sel_byte2    = wb_sel_i[2];
assign wb_sel_byte3    = wb_sel_i[3];

assign addr_argument           = (wb_addr == 8'h00);
assign addr_cmd_setting        = (wb_addr == 8'h04);
assign addr_card_status        = (wb_addr == 8'h08);
assign addr_response           = (wb_addr == 8'h0c);
assign addr_controller_setting = (wb_addr == 8'h1c);
assign addr_block_size         = (wb_addr == 8'h20);
assign addr_power_control      = (wb_addr == 8'h24);
assign addr_software_reset     = (wb_addr == 8'h28);
assign addr_timeout            = (wb_addr == 8'h2c);
assign addr_normal_int_status  = (wb_addr == 8'h30);
assign addr_error_int_status   = (wb_addr == 8'h34);
assign addr_normal_int_enable  = (wb_addr == 8'h38);
assign addr_error_int_enable   = (wb_addr == 8'h3c);
assign addr_capability         = (wb_addr == 8'h48);
assign addr_clock_divider      = (wb_addr == 8'h4c);
assign addr_bd_status          = (wb_addr == 8'h50);
assign addr_bd_isr_status      = (wb_addr == 8'h54);
assign addr_bd_isr_enable      = (wb_addr == 8'h58);
assign addr_bd_rx              = (wb_addr == 8'h60);
assign addr_bd_tx              = (wb_addr == 8'h80);

assign controller_setting_value = CONTROLLER_SETTING_RESET;
assign block_size_value         = BLOCK_SIZE_RESET;
assign power_control_value      = POWER_CONTROL_RESET;
assign capability_value         = CAPABILITY_REG_RESET;
assign normal_int_status_value  = normal_int_status_reg[15:0];
assign error_int_status_value   = error_int_status_reg[15:0];
assign bd_status_value          = Bd_Status_reg[15:0];
assign bd_isr_status_value      = Bd_isr_reg;

assign argument_write_pulse     = wb_write_access & addr_argument & int_ack;
assign command_write_pulse      = wb_write_access & addr_cmd_setting & int_ack;
assign normal_isr_clear_pulse   = wb_write_access & addr_normal_int_status & int_ack;
assign error_isr_clear_pulse    = wb_write_access & addr_error_int_status & int_ack;
assign bd_isr_clear_pulse       = wb_write_access & addr_bd_isr_status & int_ack;
assign bd_rx_write_pulse        = wb_write_access & addr_bd_rx & int_ack;
assign bd_tx_write_pulse        = wb_write_access & addr_bd_tx & int_ack;

always @(wb_dat_i or wb_adr_i or wb_sel_i or wb_we_i or wb_cyc_i or wb_stb_i or wb_ack_o or int_ack or bd_fsm_state or bd_rx_high_word or bd_rx_low_word or bd_tx_high_word or bd_tx_low_word or argument_reg or cmd_setting_reg or software_reset_reg or time_out_reg or normal_int_signal_enable_reg or error_int_signal_enable_reg or clock_divider or Bd_isr_enable_reg or status_reg or cmd_resp_1 or normal_int_status_reg or error_int_status_reg or Bd_Status_reg or Bd_isr_reg or write_req_s or cmd_arg_s or cmd_set_s) begin
    // Default assignments: hold current register values
    argument_reg_next                 = argument_reg;
    cmd_setting_reg_next              = cmd_setting_reg;
    software_reset_reg_next           = software_reset_reg;
    time_out_reg_next                 = time_out_reg;
    normal_int_signal_enable_reg_next = normal_int_signal_enable_reg;
    error_int_signal_enable_reg_next  = error_int_signal_enable_reg;
    clock_divider_next                = clock_divider;
    Bd_isr_enable_reg_next            = Bd_isr_enable_reg;

    bd_fsm_state_next                 = bd_fsm_state;
    bd_rx_low_word_next               = bd_rx_low_word;
    bd_rx_high_word_next              = bd_rx_high_word;
    bd_tx_low_word_next               = bd_tx_low_word;
    bd_tx_high_word_next              = bd_tx_high_word;

    // Control signals default low, except int_ack high and we_ack follows write_req_s
    wb_dat_o_next                     = 32'h00000000;
    wb_ack_o_next                     = 1'b0;
    we_m_tx_bd_next                   = 1'b0;
    we_m_rx_bd_next                   = 1'b0;
    new_cmd_next                      = 1'b0;
    we_ack_next                       = write_req_s;
    int_ack_next                      = 1'b1;
    cmd_int_busy_next                 = write_req_s;
    int_busy_next                     = 1'b0;
    Bd_isr_reset_next                 = 1'b0;
    normal_isr_reset_next             = 1'b0;
    error_isr_reset_next              = 1'b0;
    dat_in_m_tx_bd_next               = {RAM_MEM_WIDTH{1'b0}};
    dat_in_m_rx_bd_next               = {RAM_MEM_WIDTH{1'b0}};

    // Read data mux
    if (wb_read_access) begin
        case (wb_addr)
            8'h00: wb_dat_o_next = argument_reg;
            8'h04: wb_dat_o_next = {16'h0000, cmd_setting_reg};
            8'h08: wb_dat_o_next = {16'h0000, status_reg};
            8'h0c: wb_dat_o_next = cmd_resp_1;
            8'h1c: wb_dat_o_next = {16'h0000, controller_setting_value};
            8'h20: wb_dat_o_next = {16'h0000, block_size_value};
            8'h24: wb_dat_o_next = {24'h000000, power_control_value};
            8'h28: wb_dat_o_next = {24'h000000, software_reset_reg};
            8'h2c: wb_dat_o_next = {16'h0000, time_out_reg};
            8'h30: wb_dat_o_next = {16'h0000, normal_int_status_value};
            8'h34: wb_dat_o_next = {16'h0000, error_int_status_value};
            8'h38: wb_dat_o_next = {16'h0000, normal_int_signal_enable_reg};
            8'h3c: wb_dat_o_next = {16'h0000, error_int_signal_enable_reg};
            8'h48: wb_dat_o_next = {16'h0000, capability_value};
            8'h4c: wb_dat_o_next = {24'h000000, clock_divider};
            8'h50: wb_dat_o_next = {16'h0000, bd_status_value};
            8'h54: wb_dat_o_next = {24'h000000, bd_isr_status_value};
            8'h58: wb_dat_o_next = {24'h000000, Bd_isr_enable_reg};
            default: wb_dat_o_next = 32'h00000000;
        endcase
    end

    // Register write decode — byte-lane aware per S008
    if (wb_write_access) begin
        if (addr_argument) begin
            if (wb_sel_byte0) argument_reg_next[7:0]   = wb_dat_i[7:0];
            if (wb_sel_byte1) argument_reg_next[15:8]  = wb_dat_i[15:8];
            if (wb_sel_byte2) argument_reg_next[23:16] = wb_dat_i[23:16];
            if (wb_sel_byte3) argument_reg_next[31:24] = wb_dat_i[31:24];
        end else if (addr_cmd_setting) begin
            if (wb_sel_byte0) cmd_setting_reg_next[7:0]   = wb_dat_i[7:0];
            if (wb_sel_byte1) cmd_setting_reg_next[15:8]  = wb_dat_i[15:8];
        end else if (addr_software_reset) begin
            if (wb_sel_byte0) software_reset_reg_next = wb_dat_i[7:0];
        end else if (addr_timeout) begin
            if (wb_sel_byte0) time_out_reg_next[7:0]   = wb_dat_i[7:0];
            if (wb_sel_byte1) time_out_reg_next[15:8]  = wb_dat_i[15:8];
        end else if (addr_normal_int_status) begin
            normal_isr_reset_next = 1'b1;
        end else if (addr_error_int_status) begin
            error_isr_reset_next = 1'b1;
        end else if (addr_normal_int_enable) begin
            if (wb_sel_byte0) normal_int_signal_enable_reg_next[7:0]  = wb_dat_i[7:0];
            if (wb_sel_byte1) normal_int_signal_enable_reg_next[15:8] = wb_dat_i[15:8];
        end else if (addr_error_int_enable) begin
            if (wb_sel_byte0) error_int_signal_enable_reg_next[7:0]  = wb_dat_i[7:0];
            if (wb_sel_byte1) error_int_signal_enable_reg_next[15:8] = wb_dat_i[15:8];
        end else if (addr_clock_divider) begin
            if (wb_sel_byte0) clock_divider_next = wb_dat_i[7:0];
        end else if (addr_bd_isr_status) begin
            Bd_isr_reset_next = 1'b1;
        end else if (addr_bd_isr_enable) begin
            if (wb_sel_byte0) Bd_isr_enable_reg_next = wb_dat_i[7:0];
        end
    end

    // BD multi-cycle write FSM (S008)
`ifdef RAM_MEM_WIDTH_32
    if (bd_rx_write_pulse) begin
        int_ack_next        = 1'b1;
        we_m_rx_bd_next     = 1'b1;
        dat_in_m_rx_bd_next = wb_dat_i[31:0];
        bd_rx_low_word_next = wb_dat_i;
        bd_fsm_state_next   = BD_FSM_IDLE;
    end else if (bd_tx_write_pulse) begin
        int_ack_next        = 1'b1;
        we_m_tx_bd_next     = 1'b1;
        dat_in_m_tx_bd_next = wb_dat_i[31:0];
        bd_tx_low_word_next = wb_dat_i;
        bd_fsm_state_next   = BD_FSM_IDLE;
    end
`else
    if (bd_fsm_state == BD_FSM_IDLE) begin
        if (bd_rx_write_pulse) begin
            int_ack_next          = 1'b0;
            we_m_rx_bd_next       = 1'b1;
            dat_in_m_rx_bd_next   = wb_dat_i[15:0];
            bd_rx_low_word_next   = wb_dat_i;
            bd_rx_high_word_next  = wb_dat_i;
            bd_fsm_state_next     = BD_FSM_RX_HIGH;
        end else if (bd_tx_write_pulse) begin
            int_ack_next          = 1'b0;
            we_m_tx_bd_next       = 1'b1;
            dat_in_m_tx_bd_next   = wb_dat_i[15:0];
            bd_tx_low_word_next   = wb_dat_i;
            bd_tx_high_word_next  = wb_dat_i;
            bd_fsm_state_next     = BD_FSM_TX_LOW;
        end
    end else if (bd_fsm_state == BD_FSM_RX_HIGH) begin
        int_ack_next        = 1'b1;
        we_m_rx_bd_next     = 1'b1;
        dat_in_m_rx_bd_next = bd_rx_high_word[31:16];
        bd_fsm_state_next   = BD_FSM_IDLE;
    end else if (bd_fsm_state == BD_FSM_TX_LOW) begin
        int_ack_next        = 1'b1;
        we_m_tx_bd_next     = 1'b1;
        dat_in_m_tx_bd_next = bd_tx_high_word[31:16];
        bd_fsm_state_next   = BD_FSM_IDLE;
    end else begin
        int_ack_next      = 1'b1;
        bd_fsm_state_next = BD_FSM_IDLE;
    end
`endif

    // Wishbone acknowledge — gated by int_ack per S006
    if (wb_access && !wb_ack_o && int_ack_next) begin
        wb_ack_o_next = 1'b1;
    end
end
// STAGE5_SUBTASK_END B2_comb_decode_and_control

// ===========================================================================
// STAGE5_SUBTASK_BEGIN B3_seq_all_clocked
// ===========================================================================
always @(posedge wb_clk_i or posedge wb_rst_i) begin
    if (wb_rst_i) begin
        argument_reg                 <= ARGUMENT_REG_RESET;
        cmd_setting_reg              <= CMD_SETTING_REG_RESET;
        software_reset_reg           <= SOFTWARE_RESET_REG_RESET;
        time_out_reg                 <= TIME_OUT_REG_RESET;
        normal_int_signal_enable_reg <= NORMAL_INT_SIGNAL_ENABLE_REG_RESET;
        error_int_signal_enable_reg  <= ERROR_INT_SIGNAL_ENABLE_REG_RESET;
        clock_divider                <= CLOCK_DIVIDER_RESET;
        Bd_isr_enable_reg            <= BD_ISR_ENABLE_REG_RESET;

        bd_fsm_state                 <= BD_FSM_IDLE;
        bd_rx_low_word               <= 32'h00000000;
        bd_rx_high_word              <= 32'h00000000;
        bd_tx_low_word               <= 32'h00000000;
        bd_tx_high_word              <= 32'h00000000;

        wb_dat_o                     <= 32'h00000000;
        wb_ack_o                     <= 1'b0;
        we_m_tx_bd                   <= 1'b0;
        we_m_rx_bd                   <= 1'b0;
        new_cmd                      <= 1'b0;
        we_ack                       <= 1'b0;
        int_ack                      <= 1'b1;
        cmd_int_busy                 <= 1'b0;
        int_busy                     <= 1'b0;
        Bd_isr_reset                 <= 1'b0;
        normal_isr_reset             <= 1'b0;
        error_isr_reset              <= 1'b0;
        dat_in_m_tx_bd               <= {RAM_MEM_WIDTH{1'b0}};
        dat_in_m_rx_bd               <= {RAM_MEM_WIDTH{1'b0}};
    end else begin
        argument_reg                 <= argument_reg_next;
        cmd_setting_reg              <= cmd_setting_reg_next;
        software_reset_reg           <= software_reset_reg_next;
        time_out_reg                 <= time_out_reg_next;
        normal_int_signal_enable_reg <= normal_int_signal_enable_reg_next;
        error_int_signal_enable_reg  <= error_int_signal_enable_reg_next;
        clock_divider                <= clock_divider_next;
        Bd_isr_enable_reg            <= Bd_isr_enable_reg_next;

        bd_fsm_state                 <= bd_fsm_state_next;
        bd_rx_low_word               <= bd_rx_low_word_next;
        bd_rx_high_word              <= bd_rx_high_word_next;
        bd_tx_low_word               <= bd_tx_low_word_next;
        bd_tx_high_word              <= bd_tx_high_word_next;

        wb_dat_o                     <= wb_dat_o_next;
        wb_ack_o                     <= wb_ack_o_next;
        we_m_tx_bd                   <= we_m_tx_bd_next;
        we_m_rx_bd                   <= we_m_rx_bd_next;
        new_cmd                      <= new_cmd_next;
        we_ack                       <= we_ack_next;
        int_ack                      <= int_ack_next;
        cmd_int_busy                 <= cmd_int_busy_next;
        int_busy                     <= int_busy_next;
        Bd_isr_reset                 <= Bd_isr_reset_next;
        normal_isr_reset             <= normal_isr_reset_next;
        error_isr_reset              <= error_isr_reset_next;
        dat_in_m_tx_bd               <= dat_in_m_tx_bd_next;
        dat_in_m_rx_bd               <= dat_in_m_rx_bd_next;
    end
end
// STAGE5_SUBTASK_END B3_seq_all_clocked

// ===========================================================================
// STAGE5_SUBTASK_BEGIN B4_port_assign
// Output ports are driven directly by the registered values updated in
// seq_all_clocked.  No extra logic; purely wire connections.
// ===========================================================================
// STAGE5_SUBTASK_END B4_port_assign

endmodule
