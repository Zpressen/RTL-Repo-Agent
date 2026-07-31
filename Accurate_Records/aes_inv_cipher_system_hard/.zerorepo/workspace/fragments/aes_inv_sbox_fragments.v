// STAGE5_SUBTASK_BEGIN B1_decl_lookup_table: Declare the 256-entry AES inverse S-box lookup table as a constant read-only resource. The table must hold the 8-bit out
localparam [2047:0] INV_SBOX_TABLE = {
    128'h7d0c2155631469e126d677ba7e042b17,
    128'h619953833cbbebc8b0f52aae4d3be0a0,
    128'hef9cc9939f7ae52d0d4ab519a97f5160,
    128'h5fec8027591012b131c7078833a8dd1f,
    128'hf45acd78fec0db9a2079d2c64b3e56fc,
    128'h1bbe18aa0e62b76f89c5291d711af147,
    128'h6edf751ce837f9e28535ade72274ac96,
    128'h73e6b4f0cecff297eadc674f4111913a,
    128'h6b8a130103bdafc1020f3fca8f1e2cd0,
    128'h0645b3b80558e4f70ad3bc8c00abd890,
    128'h849d8da75746155edab9edfd5048706c,
    128'h92b6655dcc5ca4d41698688664f6f872,
    128'h25d18b6d49a25b76b224d92866a12e08,
    128'h4ec3fa420b954cee3d23c2a632947b54,
    128'hcbe9dec444438e3487ff2f9b8239e37c,
    128'hfbd7f3819ea340bf38a53630d56a0952
};
// STAGE5_SUBTASK_END B1_decl_lookup_table

// STAGE5_SUBTASK_BEGIN B2_comb_table_lookup: Read byte_in and drive byte_out by indexing into the constant inverse S-box table declared in B1. This is a purely combi
assign byte_out = INV_SBOX_TABLE[{byte_in, 3'b000} +: 8];
// STAGE5_SUBTASK_END B2_comb_table_lookup
