// STAGE5_SUBTASK_BEGIN B1_sbox_lut_decl: Declare the complete forward S-box constant lookup table as a 256-entry byte array; must contain the standard AES S-box 
wire [2047:0] sbox_table;

assign sbox_table[ 127:   0] = 128'h76abd7fe2b670130c56f6bf27b777c63;
assign sbox_table[ 255: 128] = 128'hc072a49cafa2d4adf04759fa7dc982ca;
assign sbox_table[ 383: 256] = 128'h1531d871f1e5a534ccf73f362693fdb7;
assign sbox_table[ 511: 384] = 128'h75b227ebe28012079a059618c323c704;
assign sbox_table[ 639: 512] = 128'h842fe329b3d63b52a05a6e1b1a2c8309;
assign sbox_table[ 767: 640] = 128'hcf584c4a39becb6a5bb1fc20ed00d153;
assign sbox_table[ 895: 768] = 128'ha89f3c507f02f94585334d43fbaaefd0;
assign sbox_table[1023: 896] = 128'hd2f3ff1021dab6bcf5389d928f40a351;
assign sbox_table[1151:1024] = 128'h73195d643d7ea7c41744975fec130ccd;
assign sbox_table[1279:1152] = 128'hdb0b5ede14b8ee4688902a22dc4f8160;
assign sbox_table[1407:1280] = 128'h79e4959162acd3c25c2406490a3a32e0;
assign sbox_table[1535:1408] = 128'h08ae7a65eaf4566ca94ed58d6d37c8e7;
assign sbox_table[1663:1536] = 128'h8a8bbd4b1f74dde8c6b4a61c2e2578ba;
assign sbox_table[1791:1664] = 128'h9e1dc186b95735610ef6034866b53e70;
assign sbox_table[1919:1792] = 128'hdf2855cee9871e9b948ed9691198f8e1;
assign sbox_table[2047:1920] = 128'h16bb54b00f2d99416842e6bf0d89a18c;
// STAGE5_SUBTASK_END B1_sbox_lut_decl

// STAGE5_SUBTASK_BEGIN B2_sbox_output_comb: Map the input byte sbox_byte_request to the output byte sbox_byte_response using the lookup table from B1, with purely c
reg [127:0] sbox_selected_row;
reg [7:0] sbox_selected_byte;

always @(sbox_byte_request or sbox_table) begin
    case (sbox_byte_request[7:4])
        4'h0: sbox_selected_row = sbox_table[127:0];
        4'h1: sbox_selected_row = sbox_table[255:128];
        4'h2: sbox_selected_row = sbox_table[383:256];
        4'h3: sbox_selected_row = sbox_table[511:384];
        4'h4: sbox_selected_row = sbox_table[639:512];
        4'h5: sbox_selected_row = sbox_table[767:640];
        4'h6: sbox_selected_row = sbox_table[895:768];
        4'h7: sbox_selected_row = sbox_table[1023:896];
        4'h8: sbox_selected_row = sbox_table[1151:1024];
        4'h9: sbox_selected_row = sbox_table[1279:1152];
        4'ha: sbox_selected_row = sbox_table[1407:1280];
        4'hb: sbox_selected_row = sbox_table[1535:1408];
        4'hc: sbox_selected_row = sbox_table[1663:1536];
        4'hd: sbox_selected_row = sbox_table[1791:1664];
        4'he: sbox_selected_row = sbox_table[1919:1792];
        4'hf: sbox_selected_row = sbox_table[2047:1920];
        default: sbox_selected_row = 128'b0;
    endcase
end

always @(sbox_byte_request or sbox_selected_row) begin
    case (sbox_byte_request[3:0])
        4'h0: sbox_selected_byte = sbox_selected_row[7:0];
        4'h1: sbox_selected_byte = sbox_selected_row[15:8];
        4'h2: sbox_selected_byte = sbox_selected_row[23:16];
        4'h3: sbox_selected_byte = sbox_selected_row[31:24];
        4'h4: sbox_selected_byte = sbox_selected_row[39:32];
        4'h5: sbox_selected_byte = sbox_selected_row[47:40];
        4'h6: sbox_selected_byte = sbox_selected_row[55:48];
        4'h7: sbox_selected_byte = sbox_selected_row[63:56];
        4'h8: sbox_selected_byte = sbox_selected_row[71:64];
        4'h9: sbox_selected_byte = sbox_selected_row[79:72];
        4'ha: sbox_selected_byte = sbox_selected_row[87:80];
        4'hb: sbox_selected_byte = sbox_selected_row[95:88];
        4'hc: sbox_selected_byte = sbox_selected_row[103:96];
        4'hd: sbox_selected_byte = sbox_selected_row[111:104];
        4'he: sbox_selected_byte = sbox_selected_row[119:112];
        4'hf: sbox_selected_byte = sbox_selected_row[127:120];
        default: sbox_selected_byte = 8'b0;
    endcase
end

assign sbox_byte_response = sbox_selected_byte;
// STAGE5_SUBTASK_END B2_sbox_output_comb
