module aes_inv_cipher_top (
    input  clk,
    input  rst,
    input  kld,
    input  ld,
    output done,
    input  [127:0] key,
    input  [127:0] text_in,
    output reg [127:0] text_out
);
    //------------------------------------------------------------------------
    // State registers
    //------------------------------------------------------------------------
    reg [127:0] text_in_r;                 // Data Buffer
    reg [7:0]   sa [0:3][0:3];             // State Matrix, column-major
    reg [3:0]   dcnt;                       // Round counter
    reg [127:0] kb [0:10];                  // Key buffer (reverse order)
    reg [3:0]   kcnt;                       // Key buffer counter

    //------------------------------------------------------------------------
    // Combinational wires
    //------------------------------------------------------------------------
    wire [3:0]  state;                      // Current FSM state
    wire        final_round;                // True in FinalRound state
    wire [127:0] sbox_out;                  // InvSubBytes output
    wire [127:0] shift_out;                 // InvShiftRows output
    wire [127:0] sa_ark;                    // AddRoundKey output
    wire [127:0] sa_next;                   // Next value for sa register
    wire [127:0] round_key;                 // Chosen round key

    // Internal signals for key expansion
    wire [31:0] wo_0, wo_1, wo_2, wo_3;

    // FSM control
    reg [3:0] state_reg, next_state;
    assign state = state_reg;
    assign done = (state == 4'd7);          // Done state

    // State encodings
    localparam [3:0]
        IDLE         = 4'd0,
        KeyLoad      = 4'd1,
        KeyExpansion = 4'd2,
        KeyStored    = 4'd3,
        InitialRound = 4'd4,
        StandardRound= 4'd5,
        FinalRound   = 4'd6,
        Done         = 4'd7;

    //------------------------------------------------------------------------
    // Submodules
    //------------------------------------------------------------------------
    // Key expansion
    aes_key_expand_128 u_ke (
        .clk  (clk),
        .kld  (kld),
        .key  (key),
        .wo_0 (wo_0),
        .wo_1 (wo_1),
        .wo_2 (wo_2),
        .wo_3 (wo_3)
    );

    // 16 parallel inverse S-boxes
    aes_inv_sbox us00 (.a(sa[0][0]), .b(sbox_out[7:0]));
    aes_inv_sbox us01 (.a(sa[0][1]), .b(sbox_out[15:8]));
    aes_inv_sbox us02 (.a(sa[0][2]), .b(sbox_out[23:16]));
    aes_inv_sbox us03 (.a(sa[0][3]), .b(sbox_out[31:24]));

    aes_inv_sbox us10 (.a(sa[1][0]), .b(sbox_out[39:32]));
    aes_inv_sbox us11 (.a(sa[1][1]), .b(sbox_out[47:40]));
    aes_inv_sbox us12 (.a(sa[1][2]), .b(sbox_out[55:48]));
    aes_inv_sbox us13 (.a(sa[1][3]), .b(sbox_out[63:56]));

    aes_inv_sbox us20 (.a(sa[2][0]), .b(sbox_out[71:64]));
    aes_inv_sbox us21 (.a(sa[2][1]), .b(sbox_out[79:72]));
    aes_inv_sbox us22 (.a(sa[2][2]), .b(sbox_out[87:80]));
    aes_inv_sbox us23 (.a(sa[2][3]), .b(sbox_out[95:88]));

    aes_inv_sbox us30 (.a(sa[3][0]), .b(sbox_out[103:96]));
    aes_inv_sbox us31 (.a(sa[3][1]), .b(sbox_out[111:104]));
    aes_inv_sbox us32 (.a(sa[3][2]), .b(sbox_out[119:112]));
    aes_inv_sbox us33 (.a(sa[3][3]), .b(sbox_out[127:120]));

    //------------------------------------------------------------------------
    // GF(2^8) multiplication helper functions
    //------------------------------------------------------------------------
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

    //------------------------------------------------------------------------
    // Round key selection (reverse index: 10 - dcnt)
    //------------------------------------------------------------------------
    assign round_key = kb[10 - dcnt];

    //------------------------------------------------------------------------
    // InvShiftRows – standard AES inverse row shifting
    // sbox_out is column-major: [col0 rows0:3, col1 rows0:3, ...]
    //------------------------------------------------------------------------
    wire [7:0] sr00, sr01, sr02, sr03;
    wire [7:0] sr10, sr11, sr12, sr13;
    wire [7:0] sr20, sr21, sr22, sr23;
    wire [7:0] sr30, sr31, sr32, sr33;

    assign {sr03, sr02, sr01, sr00} = sbox_out[31:0];
    assign {sr13, sr12, sr11, sr10} = sbox_out[63:32];
    assign {sr23, sr22, sr21, sr20} = sbox_out[95:64];
    assign {sr33, sr32, sr31, sr30} = sbox_out[127:96];

    wire [7:0] isr00, isr01, isr02, isr03, isr10, isr11, isr12, isr13;
    wire [7:0] isr20, isr21, isr22, isr23, isr30, isr31, isr32, isr33;

    // Row0 unchanged
    assign isr00 = sr00;
    assign isr01 = sr01;
    assign isr02 = sr02;
    assign isr03 = sr03;

    // Row1 rotate right by 1
    assign isr10 = sr13;
    assign isr11 = sr10;
    assign isr12 = sr11;
    assign isr13 = sr12;

    // Row2 rotate right by 2
    assign isr20 = sr22;
    assign isr21 = sr23;
    assign isr22 = sr20;
    assign isr23 = sr21;

    // Row3 rotate right by 3 (equiv. rotate left by 1)
    assign isr30 = sr33;
    assign isr31 = sr30;
    assign isr32 = sr31;
    assign isr33 = sr32;

    // Pack into column-major ascending format: {col0 row0..row3, col1 row0..row3, ...}
    assign shift_out = { isr00, isr10, isr20, isr30,
                         isr01, isr11, isr21, isr31,
                         isr02, isr12, isr22, isr32,
                         isr03, isr13, isr23, isr33 };

    //------------------------------------------------------------------------
    // AddRoundKey
    //------------------------------------------------------------------------
    assign sa_ark = shift_out ^ round_key;

    //------------------------------------------------------------------------
    // InvMixColumns (per column)
    //------------------------------------------------------------------------
    wire [7:0] ark00, ark10, ark20, ark30;
    wire [7:0] ark01, ark11, ark21, ark31;
    wire [7:0] ark02, ark12, ark22, ark32;
    wire [7:0] ark03, ark13, ark23, ark33;

    assign {ark00, ark10, ark20, ark30} = sa_ark[127:96];   // column0
    assign {ark01, ark11, ark21, ark31} = sa_ark[95:64];   // column1
    assign {ark02, ark12, ark22, ark32} = sa_ark[63:32];   // column2
    assign {ark03, ark13, ark23, ark33} = sa_ark[31:0];    // column3

    wire [31:0] mix_col0, mix_col1, mix_col2, mix_col3;

    assign mix_col0[31:24] = pmul_e(ark00) ^ pmul_b(ark10) ^ pmul_d(ark20) ^ pmul_9(ark30);
    assign mix_col0[23:16] = pmul_9(ark00) ^ pmul_e(ark10) ^ pmul_b(ark20) ^ pmul_d(ark30);
    assign mix_col0[15:8]  = pmul_d(ark00) ^ pmul_9(ark10) ^ pmul_e(ark20) ^ pmul_b(ark30);
    assign mix_col0[7:0]   = pmul_b(ark00) ^ pmul_d(ark10) ^ pmul_9(ark20) ^ pmul_e(ark30);

    assign mix_col1[31:24] = pmul_e(ark01) ^ pmul_b(ark11) ^ pmul_d(ark21) ^ pmul_9(ark31);
    assign mix_col1[23:16] = pmul_9(ark01) ^ pmul_e(ark11) ^ pmul_b(ark21) ^ pmul_d(ark31);
    assign mix_col1[15:8]  = pmul_d(ark01) ^ pmul_9(ark11) ^ pmul_e(ark21) ^ pmul_b(ark31);
    assign mix_col1[7:0]   = pmul_b(ark01) ^ pmul_d(ark11) ^ pmul_9(ark21) ^ pmul_e(ark31);

    assign mix_col2[31:24] = pmul_e(ark02) ^ pmul_b(ark12) ^ pmul_d(ark22) ^ pmul_9(ark32);
    assign mix_col2[23:16] = pmul_9(ark02) ^ pmul_e(ark12) ^ pmul_b(ark22) ^ pmul_d(ark32);
    assign mix_col2[15:8]  = pmul_d(ark02) ^ pmul_9(ark12) ^ pmul_e(ark22) ^ pmul_b(ark32);
    assign mix_col2[7:0]   = pmul_b(ark02) ^ pmul_d(ark12) ^ pmul_9(ark22) ^ pmul_e(ark32);

    assign mix_col3[31:24] = pmul_e(ark03) ^ pmul_b(ark13) ^ pmul_d(ark23) ^ pmul_9(ark33);
    assign mix_col3[23:16] = pmul_9(ark03) ^ pmul_e(ark13) ^ pmul_b(ark23) ^ pmul_d(ark33);
    assign mix_col3[15:8]  = pmul_d(ark03) ^ pmul_9(ark13) ^ pmul_e(ark23) ^ pmul_b(ark33);
    assign mix_col3[7:0]   = pmul_b(ark03) ^ pmul_d(ark13) ^ pmul_9(ark23) ^ pmul_e(ark33);

    // Mixed columns placed column-major ascending: column0 at top.
    wire [127:0] mixed = {mix_col0, mix_col1, mix_col2, mix_col3};

    // In the final round, skip InvMixColumns.
    assign final_round = (state == FinalRound);
    wire [127:0] mixcol_out = final_round ? sa_ark : mixed;
    assign sa_next = mixcol_out;

    //------------------------------------------------------------------------
    // FSM – next state combinational
    //------------------------------------------------------------------------
    always @(state_reg or kld or ld or kcnt or dcnt) begin
        next_state = state_reg;
        case (state_reg)
            IDLE:
                if (kld || ld)
                    next_state = KeyLoad;
            KeyLoad:
                next_state = KeyExpansion;
            KeyExpansion:
                if (kcnt == 4'd0)
                    next_state = KeyStored;
            KeyStored:
                if (ld)
                    next_state = InitialRound;
            InitialRound:
                next_state = StandardRound;
            StandardRound:
                if (dcnt == 4'd9)
                    next_state = FinalRound;
            FinalRound:
                next_state = Done;
            Done:
                next_state = IDLE;
            default:
                next_state = IDLE;
        endcase
    end

    //------------------------------------------------------------------------
    // Sequential logic
    //------------------------------------------------------------------------
    integer i;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            state_reg <= IDLE;
            dcnt      <= 4'd0;
            kcnt      <= 4'd10;
            text_in_r <= 128'd0;
            text_out  <= 128'd0;
            for (i = 0; i < 4; i = i + 1) begin
                sa[i][0] <= 8'd0;
                sa[i][1] <= 8'd0;
                sa[i][2] <= 8'd0;
                sa[i][3] <= 8'd0;
            end
            for (i = 0; i <= 10; i = i + 1) kb[i] <= 128'd0;
        end else begin
            state_reg <= next_state;

            // Round counter
            if (state_reg == InitialRound)
                dcnt <= 4'd1;
            else if (state_reg == StandardRound || state_reg == FinalRound)
                dcnt <= dcnt + 4'd1;
            else
                dcnt <= dcnt;

            // Key buffer loading during expansion
            if (state_reg == KeyExpansion) begin
                kb[kcnt] <= {wo_0, wo_1, wo_2, wo_3};
                kcnt     <= kcnt - 4'd1;
            end else begin
                kcnt <= kcnt;
            end

            // Capture input text
            if (state_reg == KeyStored && ld)
                text_in_r <= text_in;
            else
                text_in_r <= text_in_r;

            // Output register: latch plaintext at the end of the final round
            if (state_reg == FinalRound)
                text_out <= sa_ark;
            else
                text_out <= text_out;

            // State matrix update
            if (next_state == InitialRound) begin
                // Initial AddRoundKey: use text_in directly (buffered in text_in_r afterwards)
                {sa[0][0], sa[0][1], sa[0][2], sa[0][3],
                 sa[1][0], sa[1][1], sa[1][2], sa[1][3],
                 sa[2][0], sa[2][1], sa[2][2], sa[2][3],
                 sa[3][0], sa[3][1], sa[3][2], sa[3][3]} <= text_in ^ kb[10];
            end else begin
                {sa[0][0], sa[0][1], sa[0][2], sa[0][3],
                 sa[1][0], sa[1][1], sa[1][2], sa[1][3],
                 sa[2][0], sa[2][1], sa[2][2], sa[2][3],
                 sa[3][0], sa[3][1], sa[3][2], sa[3][3]} <= sa_next;
            end
        end
    end

endmodule
