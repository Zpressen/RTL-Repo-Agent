module sd_controller_wb (
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

    input  wire             write_req_s,
    input  wire [15:0]      cmd_set_s,
    input  wire [31:0]      cmd_arg_s,

    output reg  [31:0]      argument_reg,
    output reg  [15:0]      cmd_setting_reg,
    output reg  [7:0]       software_reset_reg,
    output reg  [15:0]      time_out_reg,
    output reg  [15:0]      normal_int_signal_enable_reg,
    output reg  [15:0]      error_int_signal_enable_reg,
    output reg  [7:0]       clock_divider,
    output reg  [7:0]       Bd_isr_enable_reg,

    input  wire [15:0]      status_reg,
    input  wire [31:0]      cmd_resp_1,
    input  wire [16:0]      normal_int_status_reg,
    input  wire [16:0]      error_int_status_reg,
    input  wire [16:0]      Bd_Status_reg,
    input  wire [7:0]       Bd_isr_reg,

    output reg  [15:0]      dat_in_m_tx_bd,
    output reg  [15:0]      dat_in_m_rx_bd
);

localparam [31:0] ARGUMENT_REG_RESET                 = 32'h00000000;
localparam [15:0] CMD_SETTING_REG_RESET              = 16'h0000;
localparam [15:0] CONTROLLER_SETTING_RESET           = 16'h0002;
localparam [15:0] BLOCK_SIZE_RESET                   = 16'h0200;
localparam [7:0]  POWER_CONTROL_RESET                = 8'h0f;
localparam [7:0]  SOFTWARE_RESET_REG_RESET           = 8'h00;
localparam [15:0] TIME_OUT_REG_RESET                 = 16'h0000;
localparam [15:0] NORMAL_INT_SIGNAL_ENABLE_REG_RESET = 16'h0000;
localparam [15:0] ERROR_INT_SIGNAL_ENABLE_REG_RESET  = 16'h0000;
localparam [15:0] CAPABILITY_REG_RESET               = 16'h0000;
localparam [7:0]  CLOCK_DIVIDER_RESET                = 8'h00;
localparam [7:0]  BD_ISR_ENABLE_REG_RESET            = 8'h00;

localparam [1:0]  BD_IDLE                            = 2'b00;
localparam [1:0]  BD_RX_HIGH                         = 2'b01;
localparam [1:0]  BD_TX_HIGH                         = 2'b10;

reg [31:0] argument_reg_next;
reg [15:0] cmd_setting_reg_next;
reg [7:0]  software_reset_reg_next;
reg [15:0] time_out_reg_next;
reg [15:0] normal_int_signal_enable_reg_next;
reg [15:0] error_int_signal_enable_reg_next;
reg [7:0]  clock_divider_next;
reg [7:0]  Bd_isr_enable_reg_next;

reg [1:0]  bd_state;
reg [1:0]  bd_state_next;
reg [15:0] bd_high_word;
reg [15:0] bd_high_word_next;

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
reg [15:0] dat_in_m_tx_bd_next;
reg [15:0] dat_in_m_rx_bd_next;

wire       wb_access;
wire       wb_write_access;
wire       wb_read_access;
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

assign wb_access       = wb_cyc_i & wb_stb_i;
assign wb_write_access = wb_access & wb_we_i;
assign wb_read_access  = wb_access & ~wb_we_i;

assign addr_argument           = (wb_adr_i == 8'h00);
assign addr_cmd_setting        = (wb_adr_i == 8'h04);
assign addr_card_status        = (wb_adr_i == 8'h08);
assign addr_response           = (wb_adr_i == 8'h0c);
assign addr_controller_setting = (wb_adr_i == 8'h1c);
assign addr_block_size         = (wb_adr_i == 8'h20);
assign addr_power_control      = (wb_adr_i == 8'h24);
assign addr_software_reset     = (wb_adr_i == 8'h28);
assign addr_timeout            = (wb_adr_i == 8'h2c);
assign addr_normal_int_status  = (wb_adr_i == 8'h30);
assign addr_error_int_status   = (wb_adr_i == 8'h34);
assign addr_normal_int_enable  = (wb_adr_i == 8'h38);
assign addr_error_int_enable   = (wb_adr_i == 8'h3c);
assign addr_capability         = (wb_adr_i == 8'h48);
assign addr_clock_divider      = (wb_adr_i == 8'h4c);
assign addr_bd_status          = (wb_adr_i == 8'h50);
assign addr_bd_isr_status      = (wb_adr_i == 8'h54);
assign addr_bd_isr_enable      = (wb_adr_i == 8'h58);
assign addr_bd_rx              = (wb_adr_i == 8'h60);
assign addr_bd_tx              = (wb_adr_i == 8'h80);

always @(*) begin
    argument_reg_next                 = argument_reg;
    cmd_setting_reg_next              = cmd_setting_reg;
    software_reset_reg_next           = software_reset_reg;
    time_out_reg_next                 = time_out_reg;
    normal_int_signal_enable_reg_next = normal_int_signal_enable_reg;
    error_int_signal_enable_reg_next  = error_int_signal_enable_reg;
    clock_divider_next                = clock_divider;
    Bd_isr_enable_reg_next            = Bd_isr_enable_reg;

    bd_state_next                     = bd_state;
    bd_high_word_next                 = bd_high_word;

    wb_dat_o_next                     = wb_dat_o;
    wb_ack_o_next                     = 1'b0;
    we_m_tx_bd_next                   = 1'b0;
    we_m_rx_bd_next                   = 1'b0;
    new_cmd_next                      = 1'b0;
    we_ack_next                       = 1'b0;
    int_ack_next                      = 1'b1;
    cmd_int_busy_next                 = 1'b0;
    int_busy_next                     = int_busy;
    Bd_isr_reset_next                 = Bd_isr_reset;
    normal_isr_reset_next             = normal_isr_reset;
    error_isr_reset_next              = error_isr_reset;
    dat_in_m_tx_bd_next               = dat_in_m_tx_bd;
    dat_in_m_rx_bd_next               = dat_in_m_rx_bd;

    if (wb_access) begin
        if (addr_argument) begin
            wb_dat_o_next = argument_reg;
        end else if (addr_cmd_setting) begin
            wb_dat_o_next = {16'h0000, cmd_setting_reg};
        end else if (addr_card_status) begin
            wb_dat_o_next = {16'h0000, status_reg};
        end else if (addr_response) begin
            wb_dat_o_next = cmd_resp_1;
        end else if (addr_controller_setting) begin
            wb_dat_o_next = {16'h0000, CONTROLLER_SETTING_RESET};
        end else if (addr_block_size) begin
            wb_dat_o_next = {16'h0000, BLOCK_SIZE_RESET};
        end else if (addr_power_control) begin
            wb_dat_o_next = {24'h000000, POWER_CONTROL_RESET};
        end else if (addr_software_reset) begin
            wb_dat_o_next = {24'h000000, software_reset_reg};
        end else if (addr_timeout) begin
            wb_dat_o_next = {16'h0000, time_out_reg};
        end else if (addr_normal_int_status) begin
            wb_dat_o_next = {16'h0000, normal_int_status_reg[15:0]};
        end else if (addr_error_int_status) begin
            wb_dat_o_next = {16'h0000, error_int_status_reg[15:0]};
        end else if (addr_normal_int_enable) begin
            wb_dat_o_next = {16'h0000, normal_int_signal_enable_reg};
        end else if (addr_error_int_enable) begin
            wb_dat_o_next = {16'h0000, error_int_signal_enable_reg};
        end else if (addr_capability) begin
            wb_dat_o_next = {16'h0000, CAPABILITY_REG_RESET};
        end else if (addr_clock_divider) begin
            wb_dat_o_next = {24'h000000, clock_divider};
        end else if (addr_bd_status) begin
            wb_dat_o_next = {16'h0000, Bd_Status_reg[15:0]};
        end else if (addr_bd_isr_status) begin
            wb_dat_o_next = {24'h000000, Bd_isr_reg};
        end else if (addr_bd_isr_enable) begin
            wb_dat_o_next = {24'h000000, Bd_isr_enable_reg};
        end
    end

    if (write_req_s && !(wb_access || wb_ack_o)) begin
        argument_reg_next    = cmd_arg_s;
        cmd_setting_reg_next = cmd_set_s;
        new_cmd_next         = 1'b1;
        we_ack_next          = 1'b1;
        cmd_int_busy_next    = 1'b1;
    end

    if (wb_access || wb_ack_o) begin
        Bd_isr_reset_next     = 1'b0;
        normal_isr_reset_next = 1'b0;
        error_isr_reset_next  = 1'b0;
    end

    if (((wb_access || wb_ack_o) && wb_we_i) && int_ack) begin
        end else if (addr_software_reset) begin
            software_reset_reg_next = wb_dat_i[7:0];
            cmd_setting_reg_next = wb_dat_i[15:0];
            int_busy_next        = 1'b1;
        end else if (addr_software_reset) begin
            if (wb_sel_i[0]) begin
                software_reset_reg_next = wb_dat_i[7:0];
            end
        end else if (addr_timeout) begin
            time_out_reg_next = wb_dat_i[15:0];
        end else if (addr_normal_int_status) begin
            normal_isr_reset_next = 1'b1;
        end else if (addr_error_int_status) begin
            error_isr_reset_next = 1'b1;
        end else if (addr_normal_int_enable) begin
            normal_int_signal_enable_reg_next = wb_dat_i[15:0];
        end else if (addr_error_int_enable) begin
            error_int_signal_enable_reg_next = wb_dat_i[15:0];
        end else if (addr_clock_divider) begin
            clock_divider_next = wb_dat_i[7:0];
        end else if (addr_bd_isr_status) begin
            Bd_isr_reset_next = 1'b1;
        end else if (addr_bd_isr_enable) begin
            if (wb_sel_i[0]) begin
                Bd_isr_enable_reg_next = wb_dat_i[7:0];
            end
        end
    end

    if (((wb_access || wb_ack_o) && wb_we_i) && (addr_bd_rx || addr_bd_tx)) begin
        bd_state_next = bd_state + 2'b01;
        int_ack_next  = 1'b0;

        if (bd_state == BD_IDLE) begin
            // Reference RAM_MEM_WIDTH_16 interface uses the first BD access
            // only to enter the delayed descriptor-write sequence.
            if (addr_bd_rx) begin
                we_m_rx_bd_next = 1'b0;
            end else begin
                we_m_tx_bd_next = 1'b0;
            end
        end else if (bd_state == BD_RX_HIGH) begin
            if (addr_bd_rx) begin
                we_m_rx_bd_next     = 1'b1;
                dat_in_m_rx_bd_next = wb_dat_i[15:0];
            end else begin
                we_m_tx_bd_next     = 1'b1;
                dat_in_m_tx_bd_next = wb_dat_i[15:0];
            end
        end else if (bd_state == BD_TX_HIGH) begin
            if (addr_bd_rx) begin
                we_m_rx_bd_next     = 1'b1;
                dat_in_m_rx_bd_next = wb_dat_i[31:16];
            end else begin
                we_m_tx_bd_next     = 1'b1;
                dat_in_m_tx_bd_next = wb_dat_i[31:16];
            end
        end else begin
            int_ack_next  = 1'b1;
            bd_state_next = BD_IDLE;
            if (addr_bd_rx) begin
                we_m_rx_bd_next = 1'b0;
            end else begin
                we_m_tx_bd_next = 1'b0;
            end
        end
    end

    if (status_reg[0]) begin
        int_busy_next = 1'b0;
    end

    if (wb_access && !wb_ack_o && int_ack_next) begin
        wb_ack_o_next = 1'b1;
    end
end

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

        bd_state                     <= BD_IDLE;
        bd_high_word                 <= 16'h0000;

        wb_dat_o                     <= wb_dat_o_next;
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
        dat_in_m_tx_bd               <= 16'h0000;
        dat_in_m_rx_bd               <= 16'h0000;
    end else begin
        argument_reg                 <= argument_reg_next;
        cmd_setting_reg              <= cmd_setting_reg_next;
        software_reset_reg           <= software_reset_reg_next;
        time_out_reg                 <= time_out_reg_next;
        normal_int_signal_enable_reg <= normal_int_signal_enable_reg_next;
        error_int_signal_enable_reg  <= error_int_signal_enable_reg_next;
        clock_divider                <= clock_divider_next;
        Bd_isr_enable_reg            <= Bd_isr_enable_reg_next;

        bd_state                     <= bd_state_next;
        bd_high_word                 <= bd_high_word_next;

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

endmodule
