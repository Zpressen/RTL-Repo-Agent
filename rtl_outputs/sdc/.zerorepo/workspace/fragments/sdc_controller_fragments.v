// STAGE5_SUBTASK_BEGIN B1_declarations_and_interconnects: Declare the internal wires and buses required to connect all child modules, master Wishbone mux paths, status assembly s
wire core_rst;
wire sd_clk;
wire sd_clk_divider_out;
wire sd_clk_selected;

wire we_m_tx_bd;
wire we_m_rx_bd;
wire new_cmd;
wire we_ack;
wire int_ack;
wire cmd_int_busy;
wire int_busy;
wire write_req_s;

wire [`RAM_MEM_WIDTH-1:0] dat_in_m_tx_bd;
wire [`RAM_MEM_WIDTH-1:0] dat_in_m_rx_bd;
wire [`RAM_MEM_WIDTH-1:0] dat_out_s_tx_bd;
wire [`RAM_MEM_WIDTH-1:0] dat_out_s_rx_bd;
wire [`BD_WIDTH-1:0] free_tx_bd;
wire [`BD_WIDTH-1:0] free_rx_bd;
wire ack_i_s_tx;
wire ack_i_s_rx;
wire re_s_tx;
wire re_s_rx;
wire a_cmp_tx;
wire a_cmp_rx;

wire [31:0] argument_reg;
wire [15:0] cmd_setting_reg;
wire [7:0] software_reset_reg;
wire [15:0] time_out_reg;
wire [7:0] clock_divider;
wire [15:0] status_reg;
wire [15:0] cmd_status_reg;
wire [31:0] cmd_resp_1;
wire [15:0] normal_int_status_reg;
wire [15:0] error_int_status_reg;
wire [15:0] normal_int_signal_enable_reg;
wire [15:0] error_int_signal_enable_reg;
wire [15:0] Bd_Status_reg;
wire [7:0] Bd_isr_reg;
wire [7:0] Bd_isr_enable_reg;
wire bd_isr_reset;
wire normal_isr_reset;
wire error_isr_reset;
wire cidat_w;

wire [4:0] cmd_error_int_reg;
wire [15:0] cmd_normal_int_reg;
wire [15:0] cmd_settings;
wire cmd_go_idle;
wire [39:0] cmd_to_serial;
wire cmd_req_to_serial;
wire cmd_ack_to_serial;
wire [39:0] serial_to_cmd;
wire serial_req_to_cmd;
wire serial_ack_to_cmd;
wire [7:0] serial_status;
wire [1:0] st_dat_t;

wire d_write;
wire d_read;
wire [31:0] cmd_arg_s;
wire [15:0] cmd_set_s;
wire start_tx_fifo;
wire start_rx_fifo;
wire [31:0] sys_adr;
wire ack_transfer;
wire [7:0] Dat_Int_Status;
wire [1:0] transfer_type;

wire tx_fifo_rd;
wire [31:0] tx_fifo_dat_o;
wire tx_fifo_empty;
wire tx_fifo_full;
wire rx_fifo_wr;
wire [`SD_BUS_W-1:0] rx_fifo_dat_i;
wire rx_fifo_full;

wire data_serial_rd;
wire data_serial_we;
wire [`SD_BUS_W-1:0] data_serial_dat_o;
wire busy_n;
wire transm_complete;
wire crc_ok;

wire [31:0] tx_m_wb_adr_o;
wire tx_m_wb_we_o;
wire tx_m_wb_cyc_o;
wire tx_m_wb_stb_o;
wire [2:0] tx_m_wb_cti_o;
wire [1:0] tx_m_wb_bte_o;

wire [31:0] rx_m_wb_adr_o;
wire rx_m_wb_we_o;
wire [31:0] rx_m_wb_dat_o;
wire rx_m_wb_cyc_o;
wire rx_m_wb_stb_o;
wire [2:0] rx_m_wb_cti_o;
wire [1:0] rx_m_wb_bte_o;

wire master_select_tx;
wire master_select_rx;
wire [31:0] master_wb_adr_mux;
wire master_wb_we_mux;
wire [31:0] master_wb_dat_mux;
wire master_wb_cyc_mux;
wire master_wb_stb_mux;
wire [2:0] master_wb_cti_mux;
wire [1:0] master_wb_bte_mux;

wire normal_irq_active;
wire error_irq_active;
wire data_irq_active;
// STAGE5_SUBTASK_END B1_declarations_and_interconnects

// STAGE5_SUBTASK_BEGIN B2_submodule_instances: Instantiate the required child modules once each, with separate tx_bd and rx_bd sd_bd instances, and wire every port to 
sd_controller_wb u_sd_controller_wb (
    .wb_clk_i(wb_clk_i),
    .wb_rst_i(core_rst),
    .wb_dat_i(wb_dat_i),
    .wb_dat_o(wb_dat_o),
    .wb_adr_i(wb_adr_i),
    .wb_sel_i(wb_sel_i),
    .wb_we_i(wb_we_i),
    .wb_cyc_i(wb_cyc_i),
    .wb_stb_i(wb_stb_i),
    .wb_ack_o(wb_ack_o),
    .we_m_tx_bd(we_m_tx_bd),
    .we_m_rx_bd(we_m_rx_bd),
    .new_cmd(new_cmd),
    .we_ack(we_ack),
    .int_ack(int_ack),
    .cmd_int_busy(cmd_int_busy),
    .int_busy(int_busy),
    .write_req_s(write_req_s),
    .cmd_set_s(cmd_set_s),
    .cmd_arg_s(cmd_arg_s),
    .argument_reg(argument_reg),
    .cmd_setting_reg(cmd_setting_reg),
    .status_reg(status_reg),
    .cmd_resp_1(cmd_resp_1),
    .software_reset_reg(software_reset_reg),
    .time_out_reg(time_out_reg),
    .normal_int_status_reg(normal_int_status_reg),
    .error_int_status_reg(error_int_status_reg),
    .normal_int_signal_enable_reg(normal_int_signal_enable_reg),
    .error_int_signal_enable_reg(error_int_signal_enable_reg),
    .clock_divider(clock_divider),
    .Bd_Status_reg(Bd_Status_reg),
    .Bd_isr_reg(Bd_isr_reg),
    .Bd_isr_enable_reg(Bd_isr_enable_reg),
    .bd_isr_reset(bd_isr_reset),
    .normal_isr_reset(normal_isr_reset),
    .error_isr_reset(error_isr_reset),
    .dat_in_m_tx_bd(dat_in_m_tx_bd),
    .dat_in_m_rx_bd(dat_in_m_rx_bd)
);

sd_clock_divider u_sd_clock_divider (
    .CLK(sd_clk_i),
    .DIVIDER(clock_divider),
    .RST(core_rst),
    .SD_CLK(sd_clk_divider_out)
);

sd_cmd_master u_sd_cmd_master (
    .CLK_PAD_IO(sd_clk),
    .RST_PAD_I(core_rst),
    .New_CMD(new_cmd),
    .data_write(d_write),
    .data_read(d_read),
    .ARG_REG(argument_reg),
    .CMD_SET_REG(cmd_setting_reg[13:0]),
    .TIMEOUT_REG(time_out_reg),
    .STATUS_REG(cmd_status_reg),
    .RESP_1_REG(cmd_resp_1),
    .ERR_INT_REG(cmd_error_int_reg),
    .NORMAL_INT_REG(cmd_normal_int_reg),
    .ERR_INT_RST(error_isr_reset),
    .NORMAL_INT_RST(normal_isr_reset),
    .settings(cmd_settings),
    .go_idle_o(cmd_go_idle),
    .cmd_out(cmd_to_serial),
    .req_out(cmd_req_to_serial),
    .ack_out(cmd_ack_to_serial),
    .req_in(serial_req_to_cmd),
    .ack_in(serial_ack_to_cmd),
    .cmd_in(serial_to_cmd),
    .serial_status(serial_status),
    .card_detect(card_detect)
);

sd_cmd_serial_host u_sd_cmd_serial_host (
    .SD_CLK_IN(sd_clk),
    .RST_IN(core_rst),
    .SETTING_IN(cmd_settings),
    .CMD_IN(cmd_to_serial),
    .REQ_IN(cmd_req_to_serial),
    .ACK_IN(cmd_ack_to_serial),
    .cmd_dat_i(cmd_dat_i),
    .CMD_OUT(serial_to_cmd),
    .ACK_OUT(serial_ack_to_cmd),
    .REQ_OUT(serial_req_to_cmd),
    .STATUS(serial_status),
    .cmd_oe_o(cmd_oe_o),
    .cmd_out_o(cmd_out_o),
    .st_dat_t(st_dat_t)
);

sd_data_master u_sd_data_master (
    .clk(wb_clk_i),
    .rst(core_rst),
    .dat_in_tx(dat_out_s_tx_bd),
    .free_tx_bd(free_tx_bd),
    .ack_i_s_tx(ack_i_s_tx),
    .dat_in_rx(dat_out_s_rx_bd),
    .free_rx_bd(free_rx_bd),
    .ack_i_s_rx(ack_i_s_rx),
    .cmd_busy(cmd_int_busy),
    .we_ack(we_ack),
    .cmd_tsf_err(cmd_error_int_reg[0]),
    .card_status(cmd_status_reg[4:0]),
    .tx_empt(tx_fifo_empty),
    .tx_full(tx_fifo_full),
    .rx_full(rx_fifo_full),
    .busy_n(busy_n),
    .transm_complete(transm_complete),
    .crc_ok(crc_ok),
    .Dat_Int_Status_rst(bd_isr_reset),
    .transfer_type(st_dat_t),
    .re_s_tx(re_s_tx),
    .a_cmp_tx(a_cmp_tx),
    .re_s_rx(re_s_rx),
    .a_cmp_rx(a_cmp_rx),
    .we_req(write_req_s),
    .d_write(d_write),
    .d_read(d_read),
    .cmd_arg(cmd_arg_s),
    .cmd_set(cmd_set_s),
    .start_tx_fifo(start_tx_fifo),
    .start_rx_fifo(start_rx_fifo),
    .sys_adr(sys_adr),
    .ack_transfer(ack_transfer),
    .Dat_Int_Status(Dat_Int_Status),
    .CIDAT(cidat_w)
);

sd_data_serial_host u_sd_data_serial_host (
    .sd_clk(sd_clk),
    .rst(core_rst),
    .data_in(tx_fifo_dat_o),
    .start_dat(st_dat_t),
    .ack_transfer(ack_transfer),
    .DAT_dat_i(DAT_dat_i),
    .rd(tx_fifo_rd),
    .data_out(rx_fifo_dat_i),
    .we(rx_fifo_wr),
    .DAT_oe_o(DAT_oe_o),
    .DAT_dat_o(DAT_dat_o),
    .busy_n(busy_n),
    .transm_complete(transm_complete),
    .crc_ok(crc_ok)
);

sd_bd u_tx_bd (
    .clk(wb_clk_i),
    .rst(core_rst),
    .we_m(we_m_tx_bd),
    .dat_in_m(dat_in_m_tx_bd),
    .free_bd(free_tx_bd),
    .re_s(re_s_tx),
    .ack_o_s(ack_i_s_tx),
    .a_cmp(a_cmp_tx),
    .dat_out_s(dat_out_s_tx_bd)
);

sd_bd u_rx_bd (
    .clk(wb_clk_i),
    .rst(core_rst),
    .we_m(we_m_rx_bd),
    .dat_in_m(dat_in_m_rx_bd),
    .free_bd(free_rx_bd),
    .re_s(re_s_rx),
    .ack_o_s(ack_i_s_rx),
    .a_cmp(a_cmp_rx),
    .dat_out_s(dat_out_s_rx_bd)
);

sd_fifo_tx_filler u_sd_fifo_tx_filler (
    .clk(wb_clk_i),
    .rst(core_rst),
    .m_wb_adr_o(tx_m_wb_adr_o),
    .m_wb_we_o(tx_m_wb_we_o),
    .m_wb_dat_i(m_wb_dat_i),
    .m_wb_cyc_o(tx_m_wb_cyc_o),
    .m_wb_stb_o(tx_m_wb_stb_o),
    .m_wb_ack_i(m_wb_ack_i),
    .m_wb_cti_o(tx_m_wb_cti_o),
    .m_wb_bte_o(tx_m_wb_bte_o),
    .en(start_tx_fifo),
    .adr(sys_adr),
    .sd_clk(sd_clk),
    .dat_o(tx_fifo_dat_o),
    .rd(tx_fifo_rd),
    .empty(tx_fifo_empty),
    .fe(tx_fifo_full)
);

sd_fifo_rx_filler u_sd_fifo_rx_filler (
    .clk(wb_clk_i),
    .rst(core_rst),
    .m_wb_adr_o(rx_m_wb_adr_o),
    .m_wb_we_o(rx_m_wb_we_o),
    .m_wb_dat_o(rx_m_wb_dat_o),
    .m_wb_cyc_o(rx_m_wb_cyc_o),
    .m_wb_stb_o(rx_m_wb_stb_o),
    .m_wb_ack_i(m_wb_ack_i),
    .m_wb_cti_o(rx_m_wb_cti_o),
    .m_wb_bte_o(rx_m_wb_bte_o),
    .en(start_rx_fifo),
    .adr(sys_adr),
    .sd_clk(sd_clk),
    .dat_i(rx_fifo_dat_i),
    .wr(rx_fifo_wr),
    .full(rx_fifo_full)
);
// STAGE5_SUBTASK_END B2_submodule_instances

// STAGE5_SUBTASK_BEGIN B3_master_wb_mux: Generate combinational mux assignments that route master Wishbone outputs from the TX filler when start_tx_fifo is asser
assign master_select_tx = start_tx_fifo;
assign master_select_rx = (~start_tx_fifo) & start_rx_fifo;

assign master_wb_adr_mux = master_select_tx ? tx_m_wb_adr_o :
                           (master_select_rx ? rx_m_wb_adr_o : 32'b0);
assign master_wb_we_mux  = master_select_tx ? tx_m_wb_we_o :
                           (master_select_rx ? rx_m_wb_we_o : 1'b0);
assign master_wb_dat_mux = master_select_tx ? 32'b0 :
                           (master_select_rx ? rx_m_wb_dat_o : 32'b0);
assign master_wb_cyc_mux = master_select_tx ? tx_m_wb_cyc_o :
                           (master_select_rx ? rx_m_wb_cyc_o : 1'b0);
assign master_wb_stb_mux = master_select_tx ? tx_m_wb_stb_o :
                           (master_select_rx ? rx_m_wb_stb_o : 1'b0);
assign master_wb_cti_mux = master_select_tx ? tx_m_wb_cti_o :
                           (master_select_rx ? rx_m_wb_cti_o : 3'b000);
assign master_wb_bte_mux = master_select_tx ? tx_m_wb_bte_o :
                           (master_select_rx ? rx_m_wb_bte_o : 2'b00);

assign m_wb_adr_o = master_wb_adr_mux;
assign m_wb_we_o  = master_wb_we_mux;
assign m_wb_dat_o = master_wb_dat_mux;
assign m_wb_cyc_o = master_wb_cyc_mux;
assign m_wb_stb_o = master_wb_stb_mux;
assign m_wb_cti_o = master_wb_cti_mux;
assign m_wb_bte_o = master_wb_bte_mux;
assign m_wb_sel_o = 4'b1111;
// STAGE5_SUBTASK_END B3_master_wb_mux

// STAGE5_SUBTASK_BEGIN B4_register_status_assembly_and_interrupts: Generate combinational assignments for Bd_status_reg, status_reg fields, normal/error interrupt status registers, Bd_isr
assign Bd_Status_reg[15:8] = free_rx_bd;
assign Bd_Status_reg[7:0]  = free_tx_bd;

assign status_reg[0]    = cmd_int_busy ? 1'b1 : cmd_status_reg[0];
assign status_reg[1]    = cidat_w;
assign status_reg[15:2] = cmd_status_reg[15:2];

assign normal_int_status_reg = cmd_normal_int_reg;
assign error_int_status_reg  = {11'b00000000000, cmd_error_int_reg};
assign Bd_isr_reg           = Dat_Int_Status;

assign normal_irq_active = |(normal_int_status_reg & normal_int_signal_enable_reg);
assign error_irq_active  = |(error_int_status_reg & error_int_signal_enable_reg);
assign data_irq_active   = |(Bd_isr_reg & Bd_isr_enable_reg);

assign int_a = normal_irq_active;
assign int_b = error_irq_active;
assign int_c = data_irq_active;
// STAGE5_SUBTASK_END B4_register_status_assembly_and_interrupts

// STAGE5_SUBTASK_BEGIN B5_clock_and_reset_wiring: Generate combinational clock selection for sd_clk_o/sd_clk_o_pad according to the compile-time clock source definitions.
assign core_rst = wb_rst_i | software_reset_reg[0];
assign cmd_serial_rst = core_rst | cmd_go_idle;

`ifdef SD_CLK_BUS_CLK
assign sd_clk = wb_clk_i;
assign sd_clk_selected = wb_clk_i;
assign sd_clk_o = wb_clk_i;
assign sd_clk_o_pad = wb_clk_i;
`endif

`ifdef SD_CLK_SEP
assign sd_clk = sd_clk_i_pad;
assign sd_clk_selected = sd_clk_i_pad;
assign sd_clk_o = sd_clk_i_pad;
assign sd_clk_o_pad = sd_clk_i_pad;
`endif

`ifdef SD_CLK_DYNAMIC
assign sd_clk = sd_clk_divider_out;
assign sd_clk_selected = sd_clk_divider_out;
assign sd_clk_o = sd_clk_divider_out;
assign sd_clk_o_pad = sd_clk_divider_out;
`endif

`ifdef SD_CLK_STATIC
assign sd_clk = sd_clk_i;
assign sd_clk_selected = sd_clk_i;
assign sd_clk_o = sd_clk_i;
assign sd_clk_o_pad = sd_clk_i;
`endif
// STAGE5_SUBTASK_END B5_clock_and_reset_wiring

// STAGE5_SUBTASK_BEGIN B1_decl_glue_signals: Declare all internal wires and regs needed to interconnect sub-modules, carry status/control signals, and hold muxed mas
wire core_rst;
wire cmd_serial_rst;
wire sd_clk;
wire sd_clk_divider_out;
wire sd_clk_selected;

wire we_m_tx_bd;
wire we_m_rx_bd;
wire new_cmd;
wire we_ack;
wire int_ack;
wire cmd_int_busy;
wire int_busy;
wire write_req_s;

wire [`RAM_MEM_WIDTH-1:0] dat_in_m_tx_bd;
wire [`RAM_MEM_WIDTH-1:0] dat_in_m_rx_bd;
wire [`RAM_MEM_WIDTH-1:0] dat_out_s_tx_bd;
wire [`RAM_MEM_WIDTH-1:0] dat_out_s_rx_bd;
wire [`BD_WIDTH-1:0] free_tx_bd;
wire [`BD_WIDTH-1:0] free_rx_bd;
wire ack_i_s_tx;
wire ack_i_s_rx;
wire re_s_tx;
wire re_s_rx;
wire a_cmp_tx;
wire a_cmp_rx;

wire [31:0] argument_reg;
wire [15:0] cmd_setting_reg;
wire [7:0] software_reset_reg;
wire [15:0] time_out_reg;
wire [7:0] clock_divider;
wire [15:0] status_reg;
wire [15:0] cmd_status_reg;
wire [31:0] cmd_resp_1;
wire [15:0] normal_int_status_reg;
wire [15:0] error_int_status_reg;
wire [15:0] normal_int_signal_enable_reg;
wire [15:0] error_int_signal_enable_reg;
wire [15:0] Bd_Status_reg;
wire [7:0] Bd_isr_reg;
wire [7:0] Bd_isr_enable_reg;
wire bd_isr_reset;
wire normal_isr_reset;
wire error_isr_reset;
wire cidat_w;

wire [4:0] cmd_error_int_reg;
wire [15:0] cmd_normal_int_reg;
wire [15:0] cmd_settings;
wire cmd_go_idle;
wire [39:0] cmd_to_serial;
wire cmd_req_to_serial;
wire cmd_ack_to_serial;
wire [39:0] serial_to_cmd;
wire serial_req_to_cmd;
wire serial_ack_to_cmd;
wire [7:0] serial_status;
wire [1:0] st_dat_t;

wire d_write;
wire d_read;
wire [31:0] cmd_arg_s;
wire [15:0] cmd_set_s;
wire start_tx_fifo;
wire start_rx_fifo;
wire [31:0] sys_adr;
wire ack_transfer;
wire [7:0] Dat_Int_Status;
wire [1:0] transfer_type;

wire tx_fifo_rd;
wire [31:0] tx_fifo_dat_o;
wire tx_fifo_empty;
wire tx_fifo_full;
wire rx_fifo_wr;
wire [`SD_BUS_W-1:0] rx_fifo_dat_i;
wire rx_fifo_full;

wire data_serial_rd;
wire data_serial_we;
wire [`SD_BUS_W-1:0] data_serial_dat_o;
wire busy_n;
wire transm_complete;
wire crc_ok;

wire [31:0] tx_m_wb_adr_o;
wire tx_m_wb_we_o;
wire tx_m_wb_cyc_o;
wire tx_m_wb_stb_o;
wire [2:0] tx_m_wb_cti_o;
wire [1:0] tx_m_wb_bte_o;

wire [31:0] rx_m_wb_adr_o;
wire rx_m_wb_we_o;
wire [31:0] rx_m_wb_dat_o;
wire rx_m_wb_cyc_o;
wire rx_m_wb_stb_o;
wire [2:0] rx_m_wb_cti_o;
wire [1:0] rx_m_wb_bte_o;

wire master_select_tx;
wire master_select_rx;
wire [31:0] master_wb_adr_mux;
wire master_wb_we_mux;
wire [31:0] master_wb_dat_mux;
wire master_wb_cyc_mux;
wire master_wb_stb_mux;
wire [2:0] master_wb_cti_mux;
wire [1:0] master_wb_bte_mux;

wire normal_irq_active;
wire error_irq_active;
wire data_irq_active;
// STAGE5_SUBTASK_END B1_decl_glue_signals

// STAGE5_SUBTASK_BEGIN B2_inst_submodules: Instantiate all child modules (sd_controller_wb, sd_clock_divider, sd_cmd_master, sd_cmd_serial_host, sd_data_master, sd
sd_controller_wb u_sd_controller_wb (
    .wb_clk_i(wb_clk_i),
    .wb_rst_i(core_rst),
    .wb_dat_i(wb_dat_i),
    .wb_dat_o(wb_dat_o),
    .wb_adr_i(wb_adr_i),
    .wb_sel_i(wb_sel_i),
    .wb_we_i(wb_we_i),
    .wb_cyc_i(wb_cyc_i),
    .wb_stb_i(wb_stb_i),
    .wb_ack_o(wb_ack_o),
    .we_m_tx_bd(we_m_tx_bd),
    .we_m_rx_bd(we_m_rx_bd),
    .new_cmd(new_cmd),
    .we_ack(we_ack),
    .int_ack(int_ack),
    .cmd_int_busy(cmd_int_busy),
    .int_busy(int_busy),
    .write_req_s(write_req_s),
    .cmd_set_s(cmd_set_s),
    .cmd_arg_s(cmd_arg_s),
    .argument_reg(argument_reg),
    .cmd_setting_reg(cmd_setting_reg),
    .status_reg(status_reg),
    .cmd_resp_1(cmd_resp_1),
    .software_reset_reg(software_reset_reg),
    .time_out_reg(time_out_reg),
    .normal_int_status_reg(normal_int_status_reg),
    .error_int_status_reg(error_int_status_reg),
    .normal_int_signal_enable_reg(normal_int_signal_enable_reg),
    .error_int_signal_enable_reg(error_int_signal_enable_reg),
    .clock_divider(clock_divider),
    .Bd_Status_reg(Bd_Status_reg),
    .Bd_isr_reg(Bd_isr_reg),
    .Bd_isr_enable_reg(Bd_isr_enable_reg),
    .bd_isr_reset(bd_isr_reset),
    .normal_isr_reset(normal_isr_reset),
    .error_isr_reset(error_isr_reset),
    .dat_in_m_tx_bd(dat_in_m_tx_bd),
    .dat_in_m_rx_bd(dat_in_m_rx_bd)
);

sd_clock_divider u_sd_clock_divider (
    .CLK(wb_clk_i),
    .DIVIDER(clock_divider),
    .RST(core_rst),
    .SD_CLK(sd_clk_divider_out)
);

sd_cmd_master u_sd_cmd_master (
    .CLK_PAD_IO(sd_clk),
    .RST_PAD_I(core_rst),
    .New_CMD(new_cmd),
    .data_write(d_write),
    .data_read(d_read),
    .ARG_REG(argument_reg),
    .CMD_SET_REG(cmd_setting_reg[13:0]),
    .TIMEOUT_REG(time_out_reg),
    .STATUS_REG(cmd_status_reg),
    .RESP_1_REG(cmd_resp_1),
    .ERR_INT_REG(cmd_error_int_reg),
    .NORMAL_INT_REG(cmd_normal_int_reg),
    .ERR_INT_RST(error_isr_reset),
    .NORMAL_INT_RST(normal_isr_reset),
    .settings(cmd_settings),
    .go_idle_o(cmd_go_idle),
    .cmd_out(cmd_to_serial),
    .req_out(cmd_req_to_serial),
    .ack_out(cmd_ack_to_serial),
    .req_in(serial_req_to_cmd),
    .ack_in(serial_ack_to_cmd),
    .cmd_in(serial_to_cmd),
    .serial_status(serial_status),
    .card_detect(card_detect)
);

sd_cmd_serial_host u_sd_cmd_serial_host (
    .SD_CLK_IN(sd_clk),
    .RST_IN(cmd_serial_rst),
    .SETTING_IN(cmd_settings),
    .CMD_IN(cmd_to_serial),
    .REQ_IN(cmd_req_to_serial),
    .ACK_IN(cmd_ack_to_serial),
    .cmd_dat_i(sd_cmd_dat_i),
    .CMD_OUT(serial_to_cmd),
    .ACK_OUT(serial_ack_to_cmd),
    .REQ_OUT(serial_req_to_cmd),
    .STATUS(serial_status),
    .cmd_oe_o(sd_cmd_oe_o),
    .cmd_out_o(sd_cmd_out_o),
    .st_dat_t(st_dat_t)
);

sd_data_master u_sd_data_master (
    .clk(wb_clk_i),
    .rst(core_rst),
    .dat_in_tx(dat_out_s_tx_bd),
    .free_tx_bd(free_tx_bd),
    .ack_i_s_tx(ack_i_s_tx),
    .dat_in_rx(dat_out_s_rx_bd),
    .free_rx_bd(free_rx_bd),
    .ack_i_s_rx(ack_i_s_rx),
    .cmd_busy(cmd_int_busy),
    .we_ack(we_ack),
    .cmd_tsf_err(cmd_error_int_reg[0]),
    .card_status(cmd_status_reg[4:0]),
    .tx_empt(tx_fifo_empty),
    .tx_full(tx_fifo_full),
    .rx_full(rx_fifo_full),
    .busy_n(busy_n),
    .transm_complete(transm_complete),
    .crc_ok(crc_ok),
    .Dat_Int_Status_rst(bd_isr_reset),
    .transfer_type(st_dat_t),
    .re_s_tx(re_s_tx),
    .a_cmp_tx(a_cmp_tx),
    .re_s_rx(re_s_rx),
    .a_cmp_rx(a_cmp_rx),
    .we_req(write_req_s),
    .d_write(d_write),
    .d_read(d_read),
    .cmd_arg(cmd_arg_s),
    .cmd_set(cmd_set_s),
    .start_tx_fifo(start_tx_fifo),
    .start_rx_fifo(start_rx_fifo),
    .sys_adr(sys_adr),
    .ack_transfer(ack_transfer),
    .Dat_Int_Status(Dat_Int_Status),
    .CIDAT(cidat_w)
);

sd_data_serial_host u_sd_data_serial_host (
    .sd_clk(sd_clk),
    .rst(core_rst),
    .data_in(tx_fifo_dat_o),
    .start_dat(st_dat_t),
    .ack_transfer(ack_transfer),
    .DAT_dat_i(sd_dat_dat_i),
    .rd(tx_fifo_rd),
    .data_out(rx_fifo_dat_i),
    .we(rx_fifo_wr),
    .DAT_oe_o(sd_dat_oe_o),
    .DAT_dat_o(sd_dat_out_o),
    .busy_n(busy_n),
    .transm_complete(transm_complete),
    .crc_ok(crc_ok)
);

sd_bd u_tx_bd (
    .clk(wb_clk_i),
    .rst(core_rst),
    .we_m(we_m_tx_bd),
    .dat_in_m(dat_in_m_tx_bd),
    .free_bd(free_tx_bd),
    .re_s(re_s_tx),
    .ack_o_s(ack_i_s_tx),
    .a_cmp(a_cmp_tx),
    .dat_out_s(dat_out_s_tx_bd)
);

sd_bd u_rx_bd (
    .clk(wb_clk_i),
    .rst(core_rst),
    .we_m(we_m_rx_bd),
    .dat_in_m(dat_in_m_rx_bd),
    .free_bd(free_rx_bd),
    .re_s(re_s_rx),
    .ack_o_s(ack_i_s_rx),
    .a_cmp(a_cmp_rx),
    .dat_out_s(dat_out_s_rx_bd)
);

sd_fifo_tx_filler u_sd_fifo_tx_filler (
    .clk(wb_clk_i),
    .rst(core_rst),
    .m_wb_adr_o(tx_m_wb_adr_o),
    .m_wb_we_o(tx_m_wb_we_o),
    .m_wb_dat_i(m_wb_dat_i),
    .m_wb_cyc_o(tx_m_wb_cyc_o),
    .m_wb_stb_o(tx_m_wb_stb_o),
    .m_wb_ack_i(m_wb_ack_i),
    .m_wb_cti_o(tx_m_wb_cti_o),
    .m_wb_bte_o(tx_m_wb_bte_o),
    .en(start_tx_fifo),
    .adr(sys_adr),
    .sd_clk(sd_clk),
    .dat_o(tx_fifo_dat_o),
    .rd(tx_fifo_rd),
    .empty(tx_fifo_empty),
    .fe(tx_fifo_full)
);

sd_fifo_rx_filler u_sd_fifo_rx_filler (
    .clk(wb_clk_i),
    .rst(core_rst),
    .m_wb_adr_o(rx_m_wb_adr_o),
    .m_wb_we_o(rx_m_wb_we_o),
    .m_wb_dat_o(rx_m_wb_dat_o),
    .m_wb_cyc_o(rx_m_wb_cyc_o),
    .m_wb_stb_o(rx_m_wb_stb_o),
    .m_wb_ack_i(m_wb_ack_i),
    .m_wb_cti_o(rx_m_wb_cti_o),
    .m_wb_bte_o(rx_m_wb_bte_o),
    .en(start_rx_fifo),
    .adr(sys_adr),
    .sd_clk(sd_clk),
    .dat_i(rx_fifo_dat_i),
    .wr(rx_fifo_wr),
    .full(rx_fifo_full)
);
// STAGE5_SUBTASK_END B2_inst_submodules

// STAGE5_SUBTASK_BEGIN B3_comb_status_reg_assembly: Assemble internal status registers (Bd_status_reg, status_reg bits, normal_int_status_reg, error_int_status_reg, Bd_isr_
assign Bd_Status_reg[15:8] = free_rx_bd;
assign Bd_Status_reg[7:0]  = free_tx_bd;

assign status_reg[0]    = cmd_int_busy ? 1'b1 : cmd_status_reg[0];
assign status_reg[1]    = cidat_w;
assign status_reg[15:2] = cmd_status_reg[15:2];

assign normal_int_status_reg = cmd_normal_int_reg;
assign error_int_status_reg  = {11'b00000000000, cmd_error_int_reg};
assign Bd_isr_reg            = Dat_Int_Status;
// STAGE5_SUBTASK_END B3_comb_status_reg_assembly
