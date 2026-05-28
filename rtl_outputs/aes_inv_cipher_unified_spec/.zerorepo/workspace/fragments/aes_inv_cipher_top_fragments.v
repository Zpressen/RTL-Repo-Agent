// STAGE5_SUBTASK_BEGIN B1_decl_state_and_signals: Declare all registers (text_in_r, sa, dcnt, kb, kcnt, ld_r, text_out) and internal combinational wires (state, go, sa_ar
// Registers as per S004
reg [127:0] text_in_r;          // Data Buffer, reset 0
reg [7:0]   sa [0:3][0:3];     // State Matrix, 4x4 bytes, column-major
reg [3:0]   dcnt;              // Round counter, reset 0
reg [127:0] kb [0:10];         // Key buffer, 11 round keys in reverse order
reg [3:0]   kcnt;              // Key buffer counter, reset 0xA (10)
reg         ld_r;              // Load operation flag
reg [127:0] text_out;          // Output buffer, final plaintext

// Internal combinational wires
wire [3:0]  state;             // FSM state (combinational decode)
wire        go;                // Control signal for round processing
wire [127:0] sa_ark;           // State after AddRoundKey
wire [127:0] sa_next;          // Next state value to load into sa
wire [127:0] sbox_out;         // Output of the 16 S-boxes (InvSubBytes)
wire [127:0] mixcol_out;       // Output of InvMixColumns
wire [127:0] output_map;       // Output mapping for final round
wire [127:0] shift_out;        // Output of InvShiftRows
wire [3:0]  round_key_sel;     // Round key select signal
wire        kb_ld;             // Key buffer load strobe
// STAGE5_SUBTASK_END B1_decl_state_and_signals

// STAGE5_SUBTASK_BEGIN B2_inst_submodules: Instantiate one aes_key_expand_128 (u_ke) and sixteen aes_inv_sbox (us00 through us33) with connections as described in 
// Internal wires for key expansion outputs
wire [31:0] wo_0, wo_1, wo_2, wo_3;

// Key Expansion Instance
// Generates all round keys from the input key
aes_key_expand_128 u_ke (
    .clk(clk),
    .kld(kld),
    .key(key),
    .wo_0(wo_0),
    .wo_1(wo_1),
    .wo_2(wo_2),
    .wo_3(wo_3)
);

// 16 Inverse S-box Instances (pure combinational)
// Each instance corresponds to a state matrix position

// Column 0
aes_inv_sbox us00 (.a(sa[0][0]), .b(sbox_out[7:0]));
aes_inv_sbox us01 (.a(sa[0][1]), .b(sbox_out[15:8]));
aes_inv_sbox us02 (.a(sa[0][2]), .b(sbox_out[23:16]));
aes_inv_sbox us03 (.a(sa[0][3]), .b(sbox_out[31:24]));

// Column 1
aes_inv_sbox us10 (.a(sa[1][0]), .b(sbox_out[39:32]));
aes_inv_sbox us11 (.a(sa[1][1]), .b(sbox_out[47:40]));
aes_inv_sbox us12 (.a(sa[1][2]), .b(sbox_out[55:48]));
aes_inv_sbox us13 (.a(sa[1][3]), .b(sbox_out[63:56]));

// Column 2
aes_inv_sbox us20 (.a(sa[2][0]), .b(sbox_out[71:64]));
aes_inv_sbox us21 (.a(sa[2][1]), .b(sbox_out[79:72]));
aes_inv_sbox us22 (.a(sa[2][2]), .b(sbox_out[87:80]));
aes_inv_sbox us23 (.a(sa[2][3]), .b(sbox_out[95:88]));

// Column 3
aes_inv_sbox us30 (.a(sa[3][0]), .b(sbox_out[103:96]));
aes_inv_sbox us31 (.a(sa[3][1]), .b(sbox_out[111:104]));
aes_inv_sbox us32 (.a(sa[3][2]), .b(sbox_out[119:112]));
aes_inv_sbox us33 (.a(sa[3][3]), .b(sbox_out[127:120]));
// STAGE5_SUBTASK_END B2_inst_submodules

// STAGE5_SUBTASK_BEGIN B3_round_transform_comb: Implement purely combinational inverse round transformations: InvShiftRows (cyclic right shifts per row), AddRoundKey (X
// GF(2^8) multiplication helper function
function [7:0] xtime;
  input [7:0] b;
  begin
    xtime = {b[6:0], 1'b0} ^ (b[7] ? 8'h1b : 8'h00);
  end
endfunction

function [7:0] pmul_e;
  input [7:0] b;
  reg [7:0] t1, t2, t3;
  begin
    t1 = xtime(b);
    t2 = xtime(t1);
    t3 = xtime(t2);
    pmul_e = t1 ^ t2 ^ t3;
  end
endfunction

function [7:0] pmul_b;
  input [7:0] b;
  reg [7:0] t1, t2, t3;
  begin
    t1 = xtime(b);
    t2 = xtime(t1);
    t3 = xtime(t2);
    pmul_b = b ^ t1 ^ t3;
  end
endfunction

function [7:0] pmul_d;
  input [7:0] b;
  reg [7:0] t1, t2, t3;
  begin
    t1 = xtime(b);
    t2 = xtime(t1);
    t3 = xtime(t2);
    pmul_d = b ^ t2 ^ t3;
  end
endfunction

function [7:0] pmul_9;
  input [7:0] b;
  reg [7:0] t1, t2, t3;
  begin
    t1 = xtime(b);
    t2 = xtime(t1);
    t3 = xtime(t2);
    pmul_9 = b ^ t3;
  end
endfunction

// Round key selection (combinational)
wire [127:0] round_key = kb[dcnt];

// InvShiftRows: apply row shuffling on sbox_out (InvSubBytes already applied)
// The sbox_out layout is column-major, same as expected for shift_out.
assign shift_out = {
  // Row0 unchanged
  sbox_out[7:0],
  sbox_out[111:104],
  sbox_out[87:80],
  sbox_out[63:56],
  // Row1 right shift 3
  sbox_out[15:8],
  sbox_out[119:112],
  sbox_out[23:16],
  sbox_out[55:48],
  // Row2 right shift 2
  sbox_out[23:16],
  sbox_out[95:88],
  sbox_out[47:40],
  sbox_out[127:120],
  // Row3 right shift 1
  sbox_out[31:24],
  sbox_out[79:72],
  sbox_out[55:48],
  sbox_out[127:120]
};

// AddRoundKey: XOR with round key
assign sa_ark = shift_out ^ round_key;

// InvMixColumns per column (combinational, bypassed when final_round = 1)
// Decompose sa_ark into bytes per column (column-major)
wire [7:0] col0_s0 = sa_ark[7:0];
wire [7:0] col0_s1 = sa_ark[15:8];
wire [7:0] col0_s2 = sa_ark[23:16];
wire [7:0] col0_s3 = sa_ark[31:24];

wire [7:0] col1_s0 = sa_ark[39:32];
wire [7:0] col1_s1 = sa_ark[47:40];
wire [7:0] col1_s2 = sa_ark[55:48];
wire [7:0] col1_s3 = sa_ark[63:56];

wire [7:0] col2_s0 = sa_ark[71:64];
wire [7:0] col2_s1 = sa_ark[79:72];
wire [7:0] col2_s2 = sa_ark[87:80];
wire [7:0] col2_s3 = sa_ark[95:88];

wire [7:0] col3_s0 = sa_ark[103:96];
wire [7:0] col3_s1 = sa_ark[111:104];
wire [7:0] col3_s2 = sa_ark[119:112];
wire [7:0] col3_s3 = sa_ark[127:120];

// Compute InvMixColumns outputs for each column
wire [31:0] mix_col0 = {
  pmul_e(col0_s0) ^ pmul_b(col0_s1) ^ pmul_d(col0_s2) ^ pmul_9(col0_s3),
  pmul_9(col0_s0) ^ pmul_e(col0_s1) ^ pmul_b(col0_s2) ^ pmul_d(col0_s3),
  pmul_d(col0_s0) ^ pmul_9(col0_s1) ^ pmul_e(col0_s2) ^ pmul_b(col0_s3),
  pmul_b(col0_s0) ^ pmul_d(col0_s1) ^ pmul_9(col0_s2) ^ pmul_e(col0_s3)
};

wire [31:0] mix_col1 = {
  pmul_e(col1_s0) ^ pmul_b(col1_s1) ^ pmul_d(col1_s2) ^ pmul_9(col1_s3),
  pmul_9(col1_s0) ^ pmul_e(col1_s1) ^ pmul_b(col1_s2) ^ pmul_d(col1_s3),
  pmul_d(col1_s0) ^ pmul_9(col1_s1) ^ pmul_e(col1_s2) ^ pmul_b(col1_s3),
  pmul_b(col1_s0) ^ pmul_d(col1_s1) ^ pmul_9(col1_s2) ^ pmul_e(col1_s3)
};

wire [31:0] mix_col2 = {
  pmul_e(col2_s0) ^ pmul_b(col2_s1) ^ pmul_d(col2_s2) ^ pmul_9(col2_s3),
  pmul_9(col2_s0) ^ pmul_e(col2_s1) ^ pmul_b(col2_s2) ^ pmul_d(col2_s3),
  pmul_d(col2_s0) ^ pmul_9(col2_s1) ^ pmul_e(col2_s2) ^ pmul_b(col2_s3),
  pmul_b(col2_s0) ^ pmul_d(col2_s1) ^ pmul_9(col2_s2) ^ pmul_e(col2_s3)
};

wire [31:0] mix_col3 = {
  pmul_e(col3_s0) ^ pmul_b(col3_s1) ^ pmul_d(col3_s2) ^ pmul_9(col3_s3),
  pmul_9(col3_s0) ^ pmul_e(col3_s1) ^ pmul_b(col3_s2) ^ pmul_d(col3_s3),
  pmul_d(col3_s0) ^ pmul_9(col3_s1) ^ pmul_e(col3_s2) ^ pmul_b(col3_s3),
  pmul_b(col3_s0) ^ pmul_d(col3_s1) ^ pmul_9(col3_s2) ^ pmul_e(col3_s3)
};

// Combine mixed columns into a single 128-bit wire (column-major order)
wire [127:0] mixed = {mix_col3[31:24], mix_col3[23:16], mix_col3[15:8], mix_col3[7:0],
                     mix_col2[31:24], mix_col2[23:16], mix_col2[15:8], mix_col2[7:0],
                     mix_col1[31:24], mix_col1[23:16], mix_col1[15:8], mix_col1[7:0],
                     mix_col0[31:24], mix_col0[23:16], mix_col0[15:8], mix_col0[7:0]};

// Final bypass multiplexer
assign mixcol_out = final_round ? sa_ark : mixed;

// Next state signal (input to SA register)
assign sa_next = mixcol_out;

// Final output mapping (column-major, identical to sa_ark)
assign output_map = sa_ark;
// STAGE5_SUBTASK_END B3_round_transform_comb

// STAGE5_SUBTASK_BEGIN B4_seq_control_fsm: Implement the explicit FSM with states IDLE, KeyLoad, KeyExpansion, KeyStored, InitialRound, StandardRound, FinalRound, 
// FSM state encoding
localparam [3:0] 
    IDLE       = 4'd0,
    KeyLoad    = 4'd1,
    KeyExpansion = 4'd2,
    KeyStored  = 4'd3,
    InitialRound = 4'd4,
    StandardRound = 4'd5,
    FinalRound = 4'd6,
    Done       = 4'd7;

// Current state register and next state combinational
reg [3:0] state_reg, next_state;
assign state = state_reg;

// Output control signals
assign go = (state != IDLE) && (state != Done);
assign final_round = (state == FinalRound);
assign kb_ld = (state == KeyExpansion);
assign round_key_sel = 10 - dcnt;   // reverse mapping to key buffer
assign done = (state == Done);

// Combinational next state computation
always @(*) begin
    next_state = state_reg;
    case (state_reg)
        IDLE: begin
            if (kld)
                next_state = KeyLoad;
            else if (ld)
                next_state = KeyLoad;  // key must be loaded first
        end
        KeyLoad:
            next_state = KeyExpansion;
        KeyExpansion: begin
            if (kcnt == 4'd0)
                next_state = KeyStored;
            // else stay in KeyExpansion
        end
        KeyStored: begin
            if (ld)
                next_state = InitialRound;
        end
        InitialRound:
            next_state = StandardRound;
        StandardRound: begin
            // after 9 standard rounds (dcnt becomes 9 -> 10) go to final
            if (dcnt == 4'd9)
                next_state = FinalRound;
            // else stay
        end
        FinalRound:
            next_state = Done;
        Done: begin
            if (kld || ld)
                next_state = KeyLoad;  // start new operation, done deasserts
        end
        default: next_state = IDLE;
    endcase
end

// Sequential block for all registers (synchronous reset)
always @(posedge clk) begin
    if (rst) begin
        state_reg <= IDLE;
        dcnt <= 4'd0;
        kcnt <= 4'd10;
        ld_r <= 1'b0;
        text_in_r <= 128'd0;
        text_out <= 128'd0;
        // reset key buffer array
        integer i;
        for (i = 0; i <= 10; i = i + 1) kb[i] <= 128'd0;
    end else begin
        state_reg <= next_state;

        // Capture input data when leaving KeyStored for InitialRound
        if (state_reg == KeyStored && ld)
            text_in_r <= text_in;

        // ld_r flag: 1 only during InitialRound
        ld_r <= (state_reg == InitialRound) ? 1'b1 : 1'b0;

        // Round counter increment control
        case (state_reg)
            InitialRound:    dcnt <= 4'd1;   // set to 1 after initial load
            StandardRound:   dcnt <= dcnt + 4'd1;
            FinalRound:      dcnt <= dcnt + 4'd1;
            // Done: hold value
        endcase

        // Key buffer loading during expansion, with kcnt decrement
        if (state_reg == KeyExpansion) begin
            kb[kcnt] <= {wo_3, wo_2, wo_1, wo_0};
            kcnt <= kcnt - 4'd1;
        end

        // Output capture: in Done state load final result, else hold
        if (state_reg == Done)
            text_out <= output_map;

        // sa register: load initial XORed data, else use round transformation result
        // (integration note: sa_next from round_transform_comb, text_in_r ^ kb[10] gives initial AddRoundKey)
        if (ld_r)
            // unpack 128-bit state matrix from text_in_r XOR kb[10] (column-major)
            {sa[0][3], sa[0][2], sa[0][1], sa[0][0],
             sa[1][3], sa[1][2], sa[1][1], sa[1][0],
             sa[2][3], sa[2][2], sa[2][1], sa[2][0],
             sa[3][3], sa[3][2], sa[3][1], sa[3][0]} <= text_in_r ^ kb[10];
        else
            // Use the next state from round transformation combinational logic
            {sa[0][3], sa[0][2], sa[0][1], sa[0][0],
             sa[1][3], sa[1][2], sa[1][1], sa[1][0],
             sa[2][3], sa[2][2], sa[2][1], sa[2][0],
             sa[3][3], sa[3][2], sa[3][1], sa[3][0]} <= sa_next;
    end
end
// STAGE5_SUBTASK_END B4_seq_control_fsm
