// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb.h for the primary calling header

#include "Vtb__pch.h"

VL_ATTR_COLD void Vtb___024root___eval_initial__TOP(Vtb___024root* vlSelf);
VlCoroutine Vtb___024root___eval_initial__TOP__Vtiming__0(Vtb___024root* vlSelf);
VlCoroutine Vtb___024root___eval_initial__TOP__Vtiming__1(Vtb___024root* vlSelf);
VlCoroutine Vtb___024root___eval_initial__TOP__Vtiming__2(Vtb___024root* vlSelf);

void Vtb___024root___eval_initial(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___eval_initial\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    Vtb___024root___eval_initial__TOP(vlSelf);
    vlSelfRef.__Vm_traceActivity[1U] = 1U;
    Vtb___024root___eval_initial__TOP__Vtiming__0(vlSelf);
    Vtb___024root___eval_initial__TOP__Vtiming__1(vlSelf);
    Vtb___024root___eval_initial__TOP__Vtiming__2(vlSelf);
}

VlCoroutine Vtb___024root___eval_initial__TOP__Vtiming__0(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___eval_initial__TOP__Vtiming__0\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    while (true) {
        co_await vlSelfRef.__VdlySched.delay(5ULL, 
                                             nullptr, 
                                             "aes_cipher_top_testbench.sv", 
                                             19);
        vlSelfRef.tb__DOT__clk = (1U & (~ (IData)(vlSelfRef.tb__DOT__clk)));
        ++(vlSymsp->__Vcoverage[1]);
    }
    ++(vlSymsp->__Vcoverage[2]);
    co_return;}

VlCoroutine Vtb___024root___eval_initial__TOP__Vtiming__1(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___eval_initial__TOP__Vtiming__1\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    co_await vlSelfRef.__VdlySched.delay(0x00000000000f4240ULL, 
                                         nullptr, "aes_cipher_top_testbench.sv", 
                                         115);
    VL_WRITEF_NX("TIMEOUT\n",0);
    VL_FINISH_MT("aes_cipher_top_testbench.sv", 117, "");
    ++(vlSymsp->__Vcoverage[22]);
    co_return;}

extern const VlWide<16>/*511:0*/ Vtb__ConstPool__CONST_h93e1b771_0;
extern const VlWide<16>/*511:0*/ Vtb__ConstPool__CONST_hae2e70c9_0;

VlCoroutine Vtb___024root___eval_initial__TOP__Vtiming__2(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___eval_initial__TOP__Vtiming__2\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    IData/*31:0*/ tb__DOT__stim1__DOT__unnamedblk1_2__DOT____Vrepeat1;
    tb__DOT__stim1__DOT__unnamedblk1_2__DOT____Vrepeat1 = 0;
    IData/*31:0*/ tb__DOT__stim1__DOT__unnamedblk1_3__DOT____Vrepeat2;
    tb__DOT__stim1__DOT__unnamedblk1_3__DOT____Vrepeat2 = 0;
    IData/*31:0*/ tb__DOT__stim1__DOT__unnamedblk1_4__DOT____Vrepeat3;
    tb__DOT__stim1__DOT__unnamedblk1_4__DOT____Vrepeat3 = 0;
    IData/*31:0*/ tb__DOT__stim1__DOT__unnamedblk1__DOT__unnamedblk1_5__DOT____Vrepeat4;
    tb__DOT__stim1__DOT__unnamedblk1__DOT__unnamedblk1_5__DOT____Vrepeat4 = 0;
    IData/*31:0*/ tb__DOT__stim1__DOT__unnamedblk1__DOT__unnamedblk1_6__DOT____Vrepeat5;
    tb__DOT__stim1__DOT__unnamedblk1__DOT__unnamedblk1_6__DOT____Vrepeat5 = 0;
    IData/*31:0*/ tb__DOT__stim1__DOT__unnamedblk1_7__DOT____Vrepeat6;
    tb__DOT__stim1__DOT__unnamedblk1_7__DOT____Vrepeat6 = 0;
    IData/*31:0*/ tb__DOT__stim1__DOT__unnamedblk1_7__DOT__unnamedblk1_8__DOT____Vrepeat7;
    tb__DOT__stim1__DOT__unnamedblk1_7__DOT__unnamedblk1_8__DOT____Vrepeat7 = 0;
    IData/*31:0*/ tb__DOT__stim1__DOT__unnamedblk1_9__DOT____Vrepeat8;
    tb__DOT__stim1__DOT__unnamedblk1_9__DOT____Vrepeat8 = 0;
    CData/*0:0*/ __Vtask_tb__DOT__stim1__DOT__reset_test__0__async;
    __Vtask_tb__DOT__stim1__DOT__reset_test__0__async = 0;
    IData/*31:0*/ __Vtask_tb__DOT__stim1__DOT__reset_test__0__tb__DOT__stim1__DOT__unnamedblk1_1__DOT____Vrepeat0;
    __Vtask_tb__DOT__stim1__DOT__reset_test__0__tb__DOT__stim1__DOT__unnamedblk1_1__DOT____Vrepeat0 = 0;
    CData/*0:0*/ __Vtask_tb__DOT__stim1__DOT__reset_test__1__async;
    __Vtask_tb__DOT__stim1__DOT__reset_test__1__async = 0;
    IData/*31:0*/ __Vtask_tb__DOT__stim1__DOT__reset_test__1__tb__DOT__stim1__DOT__unnamedblk1_1__DOT____Vrepeat0;
    __Vtask_tb__DOT__stim1__DOT__reset_test__1__tb__DOT__stim1__DOT__unnamedblk1_1__DOT____Vrepeat0 = 0;
    VlWide<16>/*511:0*/ __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title;
    VL_ZERO_W(512, __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title);
    CData/*0:0*/ __Vtask_tb__DOT__stim1__DOT__reset_test__4__async;
    __Vtask_tb__DOT__stim1__DOT__reset_test__4__async = 0;
    IData/*31:0*/ __Vtask_tb__DOT__stim1__DOT__reset_test__4__tb__DOT__stim1__DOT__unnamedblk1_1__DOT____Vrepeat0;
    __Vtask_tb__DOT__stim1__DOT__reset_test__4__tb__DOT__stim1__DOT__unnamedblk1_1__DOT____Vrepeat0 = 0;
    VlWide<3>/*95:0*/ __Vtemp_3;
    VlWide<3>/*95:0*/ __Vtemp_6;
    VlWide<3>/*95:0*/ __Vtemp_17;
    // Body
    vlSelfRef.tb__DOT__rst = 0U;
    vlSelfRef.tb__DOT__ld = 0U;
    vlSelfRef.tb__DOT__key[0U] = 0U;
    vlSelfRef.tb__DOT__key[1U] = 0U;
    vlSelfRef.tb__DOT__key[2U] = 0U;
    vlSelfRef.tb__DOT__key[3U] = 0U;
    vlSelfRef.tb__DOT__text_in[0U] = 0U;
    vlSelfRef.tb__DOT__text_in[1U] = 0U;
    vlSelfRef.tb__DOT__text_in[2U] = 0U;
    vlSelfRef.tb__DOT__text_in[3U] = 0U;
    vlSelfRef.tb__DOT__wavedrom_enable = 0U;
    vlSelfRef.tb__DOT__wavedrom_title[0U] = Vtb__ConstPool__CONST_h93e1b771_0[0U];
    vlSelfRef.tb__DOT__wavedrom_title[1U] = Vtb__ConstPool__CONST_h93e1b771_0[1U];
    vlSelfRef.tb__DOT__wavedrom_title[2U] = Vtb__ConstPool__CONST_h93e1b771_0[2U];
    vlSelfRef.tb__DOT__wavedrom_title[3U] = Vtb__ConstPool__CONST_h93e1b771_0[3U];
    vlSelfRef.tb__DOT__wavedrom_title[4U] = Vtb__ConstPool__CONST_h93e1b771_0[4U];
    vlSelfRef.tb__DOT__wavedrom_title[5U] = Vtb__ConstPool__CONST_h93e1b771_0[5U];
    vlSelfRef.tb__DOT__wavedrom_title[6U] = Vtb__ConstPool__CONST_h93e1b771_0[6U];
    vlSelfRef.tb__DOT__wavedrom_title[7U] = Vtb__ConstPool__CONST_h93e1b771_0[7U];
    vlSelfRef.tb__DOT__wavedrom_title[8U] = Vtb__ConstPool__CONST_h93e1b771_0[8U];
    vlSelfRef.tb__DOT__wavedrom_title[9U] = Vtb__ConstPool__CONST_h93e1b771_0[9U];
    vlSelfRef.tb__DOT__wavedrom_title[0x0000000aU] 
        = Vtb__ConstPool__CONST_h93e1b771_0[0x0000000aU];
    vlSelfRef.tb__DOT__wavedrom_title[0x0000000bU] 
        = Vtb__ConstPool__CONST_h93e1b771_0[0x0000000bU];
    vlSelfRef.tb__DOT__wavedrom_title[0x0000000cU] 
        = Vtb__ConstPool__CONST_h93e1b771_0[0x0000000cU];
    vlSelfRef.tb__DOT__wavedrom_title[0x0000000dU] 
        = Vtb__ConstPool__CONST_h93e1b771_0[0x0000000dU];
    vlSelfRef.tb__DOT__wavedrom_title[0x0000000eU] 
        = Vtb__ConstPool__CONST_h93e1b771_0[0x0000000eU];
    vlSelfRef.tb__DOT__wavedrom_title[0x0000000fU] 
        = Vtb__ConstPool__CONST_h93e1b771_0[0x0000000fU];
    __Vtask_tb__DOT__stim1__DOT__reset_test__0__async = 0U;
    __Vtask_tb__DOT__stim1__DOT__reset_test__0__tb__DOT__stim1__DOT__unnamedblk1_1__DOT____Vrepeat0 = 0;
    co_await vlSelfRef.__VtrigSched_h32009f5a__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb.clk)", 
                                                         "aes_cipher_top_stimulus_gen.sv", 
                                                         33);
    vlSelfRef.__Vm_traceActivity[2U] = 1U;
    co_await vlSelfRef.__VtrigSched_h32009f5a__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb.clk)", 
                                                         "aes_cipher_top_stimulus_gen.sv", 
                                                         34);
    vlSelfRef.__Vm_traceActivity[2U] = 1U;
    vlSelfRef.tb__DOT__rst = 0U;
    __Vtask_tb__DOT__stim1__DOT__reset_test__0__tb__DOT__stim1__DOT__unnamedblk1_1__DOT____Vrepeat0 = 3U;
    while (VL_LTS_III(32, 0U, __Vtask_tb__DOT__stim1__DOT__reset_test__0__tb__DOT__stim1__DOT__unnamedblk1_1__DOT____Vrepeat0)) {
        co_await vlSelfRef.__VtrigSched_h32009f5a__0.trigger(0U, 
                                                             nullptr, 
                                                             "@(posedge tb.clk)", 
                                                             "aes_cipher_top_stimulus_gen.sv", 
                                                             35);
        vlSelfRef.__Vm_traceActivity[2U] = 1U;
        __Vtask_tb__DOT__stim1__DOT__reset_test__0__tb__DOT__stim1__DOT__unnamedblk1_1__DOT____Vrepeat0 
            = (__Vtask_tb__DOT__stim1__DOT__reset_test__0__tb__DOT__stim1__DOT__unnamedblk1_1__DOT____Vrepeat0 
               - (IData)(1U));
        ++(vlSymsp->__Vcoverage[26]);
    }
    co_await vlSelfRef.__VtrigSched_h32009f1b__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb.clk)", 
                                                         "aes_cipher_top_stimulus_gen.sv", 
                                                         37);
    vlSelfRef.__Vm_traceActivity[2U] = 1U;
    vlSelfRef.tb__DOT__stim1__DOT__reset_test__Vstatic__datafail 
        = (1U & (~ ((IData)(vlSelfRef.tb__DOT__tb_match_text) 
                    & (IData)(vlSelfRef.tb__DOT__tb_match_done))));
    vlSelfRef.tb__DOT__rst = 1U;
    co_await vlSelfRef.__VtrigSched_h32009f5a__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb.clk)", 
                                                         "aes_cipher_top_stimulus_gen.sv", 
                                                         38);
    vlSelfRef.__Vm_traceActivity[2U] = 1U;
    vlSelfRef.tb__DOT__stim1__DOT__reset_test__Vstatic__arfail 
        = (1U & (~ ((IData)(vlSelfRef.tb__DOT__tb_match_text) 
                    & (IData)(vlSelfRef.tb__DOT__tb_match_done))));
    co_await vlSelfRef.__VtrigSched_h32009f5a__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb.clk)", 
                                                         "aes_cipher_top_stimulus_gen.sv", 
                                                         39);
    vlSelfRef.__Vm_traceActivity[2U] = 1U;
    vlSelfRef.tb__DOT__stim1__DOT__reset_test__Vstatic__srfail 
        = (1U & (~ ((IData)(vlSelfRef.tb__DOT__tb_match_text) 
                    & (IData)(vlSelfRef.tb__DOT__tb_match_done))));
    vlSelfRef.tb__DOT__rst = 0U;
    if (VL_UNLIKELY((vlSelfRef.tb__DOT__stim1__DOT__reset_test__Vstatic__srfail))) {
        VL_WRITEF_NX("Hint: Your reset doesn't seem to be working.\n",0);
        ++(vlSymsp->__Vcoverage[29]);
    } else if (VL_UNLIKELY((((IData)(vlSelfRef.tb__DOT__stim1__DOT__reset_test__Vstatic__arfail) 
                             & ((IData)(__Vtask_tb__DOT__stim1__DOT__reset_test__0__async) 
                                | (~ (IData)(vlSelfRef.tb__DOT__stim1__DOT__reset_test__Vstatic__datafail))))))) {
        __Vtemp_3[0U] = 0x6e6f7573U;
        __Vtemp_3[1U] = 0x6368726fU;
        __Vtemp_3[2U] = ((IData)(__Vtask_tb__DOT__stim1__DOT__reset_test__0__async)
                          ? 0x6173796eU : 0x0073796eU);
        VL_WRITEF_NX("Hint: Your reset should be %0s, but doesn't appear to be.\n",0,
                     96,__Vtemp_3.data());
        ++(vlSymsp->__Vcoverage[27]);
    } else {
        ++(vlSymsp->__Vcoverage[28]);
    }
    ++(vlSymsp->__Vcoverage[30]);
    tb__DOT__stim1__DOT__unnamedblk1_2__DOT____Vrepeat1 = 2U;
    while (VL_LTS_III(32, 0U, tb__DOT__stim1__DOT__unnamedblk1_2__DOT____Vrepeat1)) {
        co_await vlSelfRef.__VtrigSched_h32009f5a__0.trigger(0U, 
                                                             nullptr, 
                                                             "@(posedge tb.clk)", 
                                                             "aes_cipher_top_stimulus_gen.sv", 
                                                             57);
        vlSelfRef.__Vm_traceActivity[2U] = 1U;
        tb__DOT__stim1__DOT__unnamedblk1_2__DOT____Vrepeat1 
            = (tb__DOT__stim1__DOT__unnamedblk1_2__DOT____Vrepeat1 
               - (IData)(1U));
        ++(vlSymsp->__Vcoverage[31]);
    }
    __Vtask_tb__DOT__stim1__DOT__reset_test__1__async = 0U;
    __Vtask_tb__DOT__stim1__DOT__reset_test__1__tb__DOT__stim1__DOT__unnamedblk1_1__DOT____Vrepeat0 = 0;
    co_await vlSelfRef.__VtrigSched_h32009f5a__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb.clk)", 
                                                         "aes_cipher_top_stimulus_gen.sv", 
                                                         33);
    vlSelfRef.__Vm_traceActivity[2U] = 1U;
    co_await vlSelfRef.__VtrigSched_h32009f5a__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb.clk)", 
                                                         "aes_cipher_top_stimulus_gen.sv", 
                                                         34);
    vlSelfRef.__Vm_traceActivity[2U] = 1U;
    vlSelfRef.tb__DOT__rst = 0U;
    __Vtask_tb__DOT__stim1__DOT__reset_test__1__tb__DOT__stim1__DOT__unnamedblk1_1__DOT____Vrepeat0 = 3U;
    while (VL_LTS_III(32, 0U, __Vtask_tb__DOT__stim1__DOT__reset_test__1__tb__DOT__stim1__DOT__unnamedblk1_1__DOT____Vrepeat0)) {
        co_await vlSelfRef.__VtrigSched_h32009f5a__0.trigger(0U, 
                                                             nullptr, 
                                                             "@(posedge tb.clk)", 
                                                             "aes_cipher_top_stimulus_gen.sv", 
                                                             35);
        vlSelfRef.__Vm_traceActivity[2U] = 1U;
        __Vtask_tb__DOT__stim1__DOT__reset_test__1__tb__DOT__stim1__DOT__unnamedblk1_1__DOT____Vrepeat0 
            = (__Vtask_tb__DOT__stim1__DOT__reset_test__1__tb__DOT__stim1__DOT__unnamedblk1_1__DOT____Vrepeat0 
               - (IData)(1U));
        ++(vlSymsp->__Vcoverage[26]);
    }
    co_await vlSelfRef.__VtrigSched_h32009f1b__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb.clk)", 
                                                         "aes_cipher_top_stimulus_gen.sv", 
                                                         37);
    vlSelfRef.__Vm_traceActivity[2U] = 1U;
    vlSelfRef.tb__DOT__stim1__DOT__reset_test__Vstatic__datafail 
        = (1U & (~ ((IData)(vlSelfRef.tb__DOT__tb_match_text) 
                    & (IData)(vlSelfRef.tb__DOT__tb_match_done))));
    vlSelfRef.tb__DOT__rst = 1U;
    co_await vlSelfRef.__VtrigSched_h32009f5a__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb.clk)", 
                                                         "aes_cipher_top_stimulus_gen.sv", 
                                                         38);
    vlSelfRef.__Vm_traceActivity[2U] = 1U;
    vlSelfRef.tb__DOT__stim1__DOT__reset_test__Vstatic__arfail 
        = (1U & (~ ((IData)(vlSelfRef.tb__DOT__tb_match_text) 
                    & (IData)(vlSelfRef.tb__DOT__tb_match_done))));
    co_await vlSelfRef.__VtrigSched_h32009f5a__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb.clk)", 
                                                         "aes_cipher_top_stimulus_gen.sv", 
                                                         39);
    vlSelfRef.__Vm_traceActivity[2U] = 1U;
    vlSelfRef.tb__DOT__stim1__DOT__reset_test__Vstatic__srfail 
        = (1U & (~ ((IData)(vlSelfRef.tb__DOT__tb_match_text) 
                    & (IData)(vlSelfRef.tb__DOT__tb_match_done))));
    vlSelfRef.tb__DOT__rst = 0U;
    if (VL_UNLIKELY((vlSelfRef.tb__DOT__stim1__DOT__reset_test__Vstatic__srfail))) {
        VL_WRITEF_NX("Hint: Your reset doesn't seem to be working.\n",0);
        ++(vlSymsp->__Vcoverage[29]);
    } else if (VL_UNLIKELY((((IData)(vlSelfRef.tb__DOT__stim1__DOT__reset_test__Vstatic__arfail) 
                             & ((IData)(__Vtask_tb__DOT__stim1__DOT__reset_test__1__async) 
                                | (~ (IData)(vlSelfRef.tb__DOT__stim1__DOT__reset_test__Vstatic__datafail))))))) {
        __Vtemp_6[0U] = 0x6e6f7573U;
        __Vtemp_6[1U] = 0x6368726fU;
        __Vtemp_6[2U] = ((IData)(__Vtask_tb__DOT__stim1__DOT__reset_test__1__async)
                          ? 0x6173796eU : 0x0073796eU);
        VL_WRITEF_NX("Hint: Your reset should be %0s, but doesn't appear to be.\n",0,
                     96,__Vtemp_6.data());
        ++(vlSymsp->__Vcoverage[27]);
    } else {
        ++(vlSymsp->__Vcoverage[28]);
    }
    ++(vlSymsp->__Vcoverage[30]);
    tb__DOT__stim1__DOT__unnamedblk1_3__DOT____Vrepeat2 = 2U;
    while (VL_LTS_III(32, 0U, tb__DOT__stim1__DOT__unnamedblk1_3__DOT____Vrepeat2)) {
        co_await vlSelfRef.__VtrigSched_h32009f5a__0.trigger(0U, 
                                                             nullptr, 
                                                             "@(posedge tb.clk)", 
                                                             "aes_cipher_top_stimulus_gen.sv", 
                                                             59);
        vlSelfRef.__Vm_traceActivity[2U] = 1U;
        tb__DOT__stim1__DOT__unnamedblk1_3__DOT____Vrepeat2 
            = (tb__DOT__stim1__DOT__unnamedblk1_3__DOT____Vrepeat2 
               - (IData)(1U));
        ++(vlSymsp->__Vcoverage[32]);
    }
    __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[0U] 
        = Vtb__ConstPool__CONST_hae2e70c9_0[0U];
    __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[1U] 
        = Vtb__ConstPool__CONST_hae2e70c9_0[1U];
    __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[2U] 
        = Vtb__ConstPool__CONST_hae2e70c9_0[2U];
    __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[3U] 
        = Vtb__ConstPool__CONST_hae2e70c9_0[3U];
    __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[4U] 
        = Vtb__ConstPool__CONST_hae2e70c9_0[4U];
    __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[5U] 
        = Vtb__ConstPool__CONST_hae2e70c9_0[5U];
    __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[6U] 
        = Vtb__ConstPool__CONST_hae2e70c9_0[6U];
    __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[7U] 
        = Vtb__ConstPool__CONST_hae2e70c9_0[7U];
    __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[8U] 
        = Vtb__ConstPool__CONST_hae2e70c9_0[8U];
    __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[9U] 
        = Vtb__ConstPool__CONST_hae2e70c9_0[9U];
    __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[0x0000000aU] 
        = Vtb__ConstPool__CONST_hae2e70c9_0[0x0000000aU];
    __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[0x0000000bU] 
        = Vtb__ConstPool__CONST_hae2e70c9_0[0x0000000bU];
    __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[0x0000000cU] 
        = Vtb__ConstPool__CONST_hae2e70c9_0[0x0000000cU];
    __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[0x0000000dU] 
        = Vtb__ConstPool__CONST_hae2e70c9_0[0x0000000dU];
    __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[0x0000000eU] 
        = Vtb__ConstPool__CONST_hae2e70c9_0[0x0000000eU];
    __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[0x0000000fU] 
        = Vtb__ConstPool__CONST_hae2e70c9_0[0x0000000fU];
    vlSelfRef.tb__DOT__wavedrom_title[0U] = __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[0U];
    vlSelfRef.tb__DOT__wavedrom_title[1U] = __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[1U];
    vlSelfRef.tb__DOT__wavedrom_title[2U] = __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[2U];
    vlSelfRef.tb__DOT__wavedrom_title[3U] = __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[3U];
    vlSelfRef.tb__DOT__wavedrom_title[4U] = __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[4U];
    vlSelfRef.tb__DOT__wavedrom_title[5U] = __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[5U];
    vlSelfRef.tb__DOT__wavedrom_title[6U] = __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[6U];
    vlSelfRef.tb__DOT__wavedrom_title[7U] = __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[7U];
    vlSelfRef.tb__DOT__wavedrom_title[8U] = __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[8U];
    vlSelfRef.tb__DOT__wavedrom_title[9U] = __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[9U];
    vlSelfRef.tb__DOT__wavedrom_title[0x0000000aU] 
        = __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[0x0000000aU];
    vlSelfRef.tb__DOT__wavedrom_title[0x0000000bU] 
        = __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[0x0000000bU];
    vlSelfRef.tb__DOT__wavedrom_title[0x0000000cU] 
        = __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[0x0000000cU];
    vlSelfRef.tb__DOT__wavedrom_title[0x0000000dU] 
        = __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[0x0000000dU];
    vlSelfRef.tb__DOT__wavedrom_title[0x0000000eU] 
        = __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[0x0000000eU];
    vlSelfRef.tb__DOT__wavedrom_title[0x0000000fU] 
        = __Vtask_tb__DOT__stim1__DOT__wavedrom_start__2__title[0x0000000fU];
    vlSelfRef.tb__DOT__wavedrom_enable = 1U;
    ++(vlSymsp->__Vcoverage[24]);
    co_await vlSelfRef.__VtrigSched_h32009f1b__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb.clk)", 
                                                         "aes_cipher_top_stimulus_gen.sv", 
                                                         63);
    vlSelfRef.__Vm_traceActivity[2U] = 1U;
    vlSelfRef.tb__DOT__key[0U] = vlSelfRef.tb__DOT__stim1__DOT__TEST_KEYS
        [0U][0U];
    vlSelfRef.tb__DOT__key[1U] = vlSelfRef.tb__DOT__stim1__DOT__TEST_KEYS
        [0U][1U];
    vlSelfRef.tb__DOT__key[2U] = vlSelfRef.tb__DOT__stim1__DOT__TEST_KEYS
        [0U][2U];
    vlSelfRef.tb__DOT__key[3U] = vlSelfRef.tb__DOT__stim1__DOT__TEST_KEYS
        [0U][3U];
    vlSelfRef.tb__DOT__text_in[0U] = vlSelfRef.tb__DOT__stim1__DOT__TEST_KEYS
        [1U][0U];
    vlSelfRef.tb__DOT__text_in[1U] = vlSelfRef.tb__DOT__stim1__DOT__TEST_KEYS
        [1U][1U];
    vlSelfRef.tb__DOT__text_in[2U] = vlSelfRef.tb__DOT__stim1__DOT__TEST_KEYS
        [1U][2U];
    vlSelfRef.tb__DOT__text_in[3U] = vlSelfRef.tb__DOT__stim1__DOT__TEST_KEYS
        [1U][3U];
    vlSelfRef.tb__DOT__rst = 1U;
    vlSelfRef.tb__DOT__ld = 1U;
    co_await vlSelfRef.__VtrigSched_h32009f5a__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb.clk)", 
                                                         "aes_cipher_top_stimulus_gen.sv", 
                                                         67);
    vlSelfRef.__Vm_traceActivity[2U] = 1U;
    vlSelfRef.tb__DOT__ld = 0U;
    tb__DOT__stim1__DOT__unnamedblk1_4__DOT____Vrepeat3 = 0x0000000fU;
    while (VL_LTS_III(32, 0U, tb__DOT__stim1__DOT__unnamedblk1_4__DOT____Vrepeat3)) {
        co_await vlSelfRef.__VtrigSched_h32009f5a__0.trigger(0U, 
                                                             nullptr, 
                                                             "@(posedge tb.clk)", 
                                                             "aes_cipher_top_stimulus_gen.sv", 
                                                             69);
        vlSelfRef.__Vm_traceActivity[2U] = 1U;
        tb__DOT__stim1__DOT__unnamedblk1_4__DOT____Vrepeat3 
            = (tb__DOT__stim1__DOT__unnamedblk1_4__DOT____Vrepeat3 
               - (IData)(1U));
        ++(vlSymsp->__Vcoverage[33]);
    }
    vlSelfRef.tb__DOT__wavedrom_enable = 0U;
    ++(vlSymsp->__Vcoverage[25]);
    vlSelfRef.tb__DOT__stim1__DOT__unnamedblk1__DOT__i = 0U;
    while (VL_GTS_III(32, 6U, vlSelfRef.tb__DOT__stim1__DOT__unnamedblk1__DOT__i)) {
        co_await vlSelfRef.__VtrigSched_h32009f1b__0.trigger(0U, 
                                                             nullptr, 
                                                             "@(negedge tb.clk)", 
                                                             "aes_cipher_top_stimulus_gen.sv", 
                                                             74);
        vlSelfRef.__Vm_traceActivity[2U] = 1U;
        if ((5U >= (7U & vlSelfRef.tb__DOT__stim1__DOT__unnamedblk1__DOT__i))) {
            vlSelfRef.tb__DOT__key[0U] = vlSelfRef.tb__DOT__stim1__DOT__TEST_KEYS
                [(7U & vlSelfRef.tb__DOT__stim1__DOT__unnamedblk1__DOT__i)][0U];
            vlSelfRef.tb__DOT__key[1U] = vlSelfRef.tb__DOT__stim1__DOT__TEST_KEYS
                [(7U & vlSelfRef.tb__DOT__stim1__DOT__unnamedblk1__DOT__i)][1U];
            vlSelfRef.tb__DOT__key[2U] = vlSelfRef.tb__DOT__stim1__DOT__TEST_KEYS
                [(7U & vlSelfRef.tb__DOT__stim1__DOT__unnamedblk1__DOT__i)][2U];
            vlSelfRef.tb__DOT__key[3U] = vlSelfRef.tb__DOT__stim1__DOT__TEST_KEYS
                [(7U & vlSelfRef.tb__DOT__stim1__DOT__unnamedblk1__DOT__i)][3U];
        } else {
            vlSelfRef.tb__DOT__key[0U] = 0U;
            vlSelfRef.tb__DOT__key[1U] = 0U;
            vlSelfRef.tb__DOT__key[2U] = 0U;
            vlSelfRef.tb__DOT__key[3U] = 0U;
        }
        if ((5U >= (7U & VL_MODDIVS_III(32, ((IData)(1U) 
                                             + vlSelfRef.tb__DOT__stim1__DOT__unnamedblk1__DOT__i), (IData)(6U))))) {
            vlSelfRef.tb__DOT__text_in[0U] = vlSelfRef.tb__DOT__stim1__DOT__TEST_KEYS
                [(7U & VL_MODDIVS_III(32, ((IData)(1U) 
                                           + vlSelfRef.tb__DOT__stim1__DOT__unnamedblk1__DOT__i), (IData)(6U)))][0U];
            vlSelfRef.tb__DOT__text_in[1U] = vlSelfRef.tb__DOT__stim1__DOT__TEST_KEYS
                [(7U & VL_MODDIVS_III(32, ((IData)(1U) 
                                           + vlSelfRef.tb__DOT__stim1__DOT__unnamedblk1__DOT__i), (IData)(6U)))][1U];
            vlSelfRef.tb__DOT__text_in[2U] = vlSelfRef.tb__DOT__stim1__DOT__TEST_KEYS
                [(7U & VL_MODDIVS_III(32, ((IData)(1U) 
                                           + vlSelfRef.tb__DOT__stim1__DOT__unnamedblk1__DOT__i), (IData)(6U)))][2U];
            vlSelfRef.tb__DOT__text_in[3U] = vlSelfRef.tb__DOT__stim1__DOT__TEST_KEYS
                [(7U & VL_MODDIVS_III(32, ((IData)(1U) 
                                           + vlSelfRef.tb__DOT__stim1__DOT__unnamedblk1__DOT__i), (IData)(6U)))][3U];
        } else {
            vlSelfRef.tb__DOT__text_in[0U] = 0U;
            vlSelfRef.tb__DOT__text_in[1U] = 0U;
            vlSelfRef.tb__DOT__text_in[2U] = 0U;
            vlSelfRef.tb__DOT__text_in[3U] = 0U;
        }
        vlSelfRef.tb__DOT__rst = 1U;
        vlSelfRef.tb__DOT__ld = 1U;
        co_await vlSelfRef.__VtrigSched_h32009f5a__0.trigger(0U, 
                                                             nullptr, 
                                                             "@(posedge tb.clk)", 
                                                             "aes_cipher_top_stimulus_gen.sv", 
                                                             79);
        vlSelfRef.__Vm_traceActivity[2U] = 1U;
        vlSelfRef.tb__DOT__ld = 0U;
        if ((1U & vlSelfRef.tb__DOT__stim1__DOT__unnamedblk1__DOT__i)) {
            tb__DOT__stim1__DOT__unnamedblk1__DOT__unnamedblk1_5__DOT____Vrepeat4 = 5U;
            while (VL_LTS_III(32, 0U, tb__DOT__stim1__DOT__unnamedblk1__DOT__unnamedblk1_5__DOT____Vrepeat4)) {
                co_await vlSelfRef.__VtrigSched_h32009f5a__0.trigger(0U, 
                                                                     nullptr, 
                                                                     "@(posedge tb.clk)", 
                                                                     "aes_cipher_top_stimulus_gen.sv", 
                                                                     83);
                vlSelfRef.__Vm_traceActivity[2U] = 1U;
                tb__DOT__stim1__DOT__unnamedblk1__DOT__unnamedblk1_5__DOT____Vrepeat4 
                    = (tb__DOT__stim1__DOT__unnamedblk1__DOT__unnamedblk1_5__DOT____Vrepeat4 
                       - (IData)(1U));
                ++(vlSymsp->__Vcoverage[34]);
            }
            vlSelfRef.tb__DOT__rst = 0U;
            co_await vlSelfRef.__VtrigSched_h32009f5a__0.trigger(0U, 
                                                                 nullptr, 
                                                                 "@(posedge tb.clk)", 
                                                                 "aes_cipher_top_stimulus_gen.sv", 
                                                                 85);
            vlSelfRef.__Vm_traceActivity[2U] = 1U;
            vlSelfRef.tb__DOT__rst = 1U;
            ++(vlSymsp->__Vcoverage[35]);
        } else {
            ++(vlSymsp->__Vcoverage[36]);
        }
        tb__DOT__stim1__DOT__unnamedblk1__DOT__unnamedblk1_6__DOT____Vrepeat5 = 0x0000000fU;
        while (VL_LTS_III(32, 0U, tb__DOT__stim1__DOT__unnamedblk1__DOT__unnamedblk1_6__DOT____Vrepeat5)) {
            co_await vlSelfRef.__VtrigSched_h32009f5a__0.trigger(0U, 
                                                                 nullptr, 
                                                                 "@(posedge tb.clk)", 
                                                                 "aes_cipher_top_stimulus_gen.sv", 
                                                                 88);
            vlSelfRef.__Vm_traceActivity[2U] = 1U;
            tb__DOT__stim1__DOT__unnamedblk1__DOT__unnamedblk1_6__DOT____Vrepeat5 
                = (tb__DOT__stim1__DOT__unnamedblk1__DOT__unnamedblk1_6__DOT____Vrepeat5 
                   - (IData)(1U));
            ++(vlSymsp->__Vcoverage[37]);
        }
        vlSelfRef.tb__DOT__stim1__DOT__unnamedblk1__DOT__i 
            = ((IData)(1U) + vlSelfRef.tb__DOT__stim1__DOT__unnamedblk1__DOT__i);
        ++(vlSymsp->__Vcoverage[38]);
    }
    tb__DOT__stim1__DOT__unnamedblk1_7__DOT____Vrepeat6 = 8U;
    while (VL_LTS_III(32, 0U, tb__DOT__stim1__DOT__unnamedblk1_7__DOT____Vrepeat6)) {
        co_await vlSelfRef.__VtrigSched_h32009f1b__0.trigger(0U, 
                                                             nullptr, 
                                                             "@(negedge tb.clk)", 
                                                             "aes_cipher_top_stimulus_gen.sv", 
                                                             93);
        vlSelfRef.__Vm_traceActivity[2U] = 1U;
        VL_EXTENDS_WI(128,32, vlSelfRef.tb__DOT__key, 
                      VL_RANDOM_I());
        vlSelfRef.tb__DOT__text_in[0U] = (((~ vlSelfRef.tb__DOT__key[0U]) 
                                           << 1U) | 
                                          (vlSelfRef.tb__DOT__key[3U] 
                                           >> 0x0000001fU));
        vlSelfRef.tb__DOT__text_in[1U] = (((~ vlSelfRef.tb__DOT__key[0U]) 
                                           >> 0x0000001fU) 
                                          | ((~ vlSelfRef.tb__DOT__key[1U]) 
                                             << 1U));
        vlSelfRef.tb__DOT__text_in[2U] = (((~ vlSelfRef.tb__DOT__key[1U]) 
                                           >> 0x0000001fU) 
                                          | ((~ vlSelfRef.tb__DOT__key[2U]) 
                                             << 1U));
        vlSelfRef.tb__DOT__text_in[3U] = (((~ vlSelfRef.tb__DOT__key[2U]) 
                                           >> 0x0000001fU) 
                                          | ((~ vlSelfRef.tb__DOT__key[3U]) 
                                             << 1U));
        vlSelfRef.tb__DOT__rst = 1U;
        vlSelfRef.tb__DOT__ld = 1U;
        co_await vlSelfRef.__VtrigSched_h32009f5a__0.trigger(0U, 
                                                             nullptr, 
                                                             "@(posedge tb.clk)", 
                                                             "aes_cipher_top_stimulus_gen.sv", 
                                                             98);
        vlSelfRef.__Vm_traceActivity[2U] = 1U;
        vlSelfRef.tb__DOT__ld = 0U;
        tb__DOT__stim1__DOT__unnamedblk1_7__DOT__unnamedblk1_8__DOT____Vrepeat7 = 0x0000000fU;
        while (VL_LTS_III(32, 0U, tb__DOT__stim1__DOT__unnamedblk1_7__DOT__unnamedblk1_8__DOT____Vrepeat7)) {
            co_await vlSelfRef.__VtrigSched_h32009f5a__0.trigger(0U, 
                                                                 nullptr, 
                                                                 "@(posedge tb.clk)", 
                                                                 "aes_cipher_top_stimulus_gen.sv", 
                                                                 100);
            vlSelfRef.__Vm_traceActivity[2U] = 1U;
            tb__DOT__stim1__DOT__unnamedblk1_7__DOT__unnamedblk1_8__DOT____Vrepeat7 
                = (tb__DOT__stim1__DOT__unnamedblk1_7__DOT__unnamedblk1_8__DOT____Vrepeat7 
                   - (IData)(1U));
            ++(vlSymsp->__Vcoverage[39]);
        }
        tb__DOT__stim1__DOT__unnamedblk1_7__DOT____Vrepeat6 
            = (tb__DOT__stim1__DOT__unnamedblk1_7__DOT____Vrepeat6 
               - (IData)(1U));
        ++(vlSymsp->__Vcoverage[40]);
    }
    __Vtask_tb__DOT__stim1__DOT__reset_test__4__async = 0U;
    __Vtask_tb__DOT__stim1__DOT__reset_test__4__tb__DOT__stim1__DOT__unnamedblk1_1__DOT____Vrepeat0 = 0;
    co_await vlSelfRef.__VtrigSched_h32009f5a__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb.clk)", 
                                                         "aes_cipher_top_stimulus_gen.sv", 
                                                         33);
    vlSelfRef.__Vm_traceActivity[2U] = 1U;
    co_await vlSelfRef.__VtrigSched_h32009f5a__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb.clk)", 
                                                         "aes_cipher_top_stimulus_gen.sv", 
                                                         34);
    vlSelfRef.__Vm_traceActivity[2U] = 1U;
    vlSelfRef.tb__DOT__rst = 0U;
    __Vtask_tb__DOT__stim1__DOT__reset_test__4__tb__DOT__stim1__DOT__unnamedblk1_1__DOT____Vrepeat0 = 3U;
    while (VL_LTS_III(32, 0U, __Vtask_tb__DOT__stim1__DOT__reset_test__4__tb__DOT__stim1__DOT__unnamedblk1_1__DOT____Vrepeat0)) {
        co_await vlSelfRef.__VtrigSched_h32009f5a__0.trigger(0U, 
                                                             nullptr, 
                                                             "@(posedge tb.clk)", 
                                                             "aes_cipher_top_stimulus_gen.sv", 
                                                             35);
        vlSelfRef.__Vm_traceActivity[2U] = 1U;
        __Vtask_tb__DOT__stim1__DOT__reset_test__4__tb__DOT__stim1__DOT__unnamedblk1_1__DOT____Vrepeat0 
            = (__Vtask_tb__DOT__stim1__DOT__reset_test__4__tb__DOT__stim1__DOT__unnamedblk1_1__DOT____Vrepeat0 
               - (IData)(1U));
        ++(vlSymsp->__Vcoverage[26]);
    }
    co_await vlSelfRef.__VtrigSched_h32009f1b__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(negedge tb.clk)", 
                                                         "aes_cipher_top_stimulus_gen.sv", 
                                                         37);
    vlSelfRef.__Vm_traceActivity[2U] = 1U;
    vlSelfRef.tb__DOT__stim1__DOT__reset_test__Vstatic__datafail 
        = (1U & (~ ((IData)(vlSelfRef.tb__DOT__tb_match_text) 
                    & (IData)(vlSelfRef.tb__DOT__tb_match_done))));
    vlSelfRef.tb__DOT__rst = 1U;
    co_await vlSelfRef.__VtrigSched_h32009f5a__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb.clk)", 
                                                         "aes_cipher_top_stimulus_gen.sv", 
                                                         38);
    vlSelfRef.__Vm_traceActivity[2U] = 1U;
    vlSelfRef.tb__DOT__stim1__DOT__reset_test__Vstatic__arfail 
        = (1U & (~ ((IData)(vlSelfRef.tb__DOT__tb_match_text) 
                    & (IData)(vlSelfRef.tb__DOT__tb_match_done))));
    co_await vlSelfRef.__VtrigSched_h32009f5a__0.trigger(0U, 
                                                         nullptr, 
                                                         "@(posedge tb.clk)", 
                                                         "aes_cipher_top_stimulus_gen.sv", 
                                                         39);
    vlSelfRef.__Vm_traceActivity[2U] = 1U;
    vlSelfRef.tb__DOT__stim1__DOT__reset_test__Vstatic__srfail 
        = (1U & (~ ((IData)(vlSelfRef.tb__DOT__tb_match_text) 
                    & (IData)(vlSelfRef.tb__DOT__tb_match_done))));
    vlSelfRef.tb__DOT__rst = 0U;
    if (VL_UNLIKELY((vlSelfRef.tb__DOT__stim1__DOT__reset_test__Vstatic__srfail))) {
        VL_WRITEF_NX("Hint: Your reset doesn't seem to be working.\n",0);
        ++(vlSymsp->__Vcoverage[29]);
    } else if (VL_UNLIKELY((((IData)(vlSelfRef.tb__DOT__stim1__DOT__reset_test__Vstatic__arfail) 
                             & ((IData)(__Vtask_tb__DOT__stim1__DOT__reset_test__4__async) 
                                | (~ (IData)(vlSelfRef.tb__DOT__stim1__DOT__reset_test__Vstatic__datafail))))))) {
        __Vtemp_17[0U] = 0x6e6f7573U;
        __Vtemp_17[1U] = 0x6368726fU;
        __Vtemp_17[2U] = ((IData)(__Vtask_tb__DOT__stim1__DOT__reset_test__4__async)
                           ? 0x6173796eU : 0x0073796eU);
        VL_WRITEF_NX("Hint: Your reset should be %0s, but doesn't appear to be.\n",0,
                     96,__Vtemp_17.data());
        ++(vlSymsp->__Vcoverage[27]);
    } else {
        ++(vlSymsp->__Vcoverage[28]);
    }
    ++(vlSymsp->__Vcoverage[30]);
    tb__DOT__stim1__DOT__unnamedblk1_9__DOT____Vrepeat8 = 5U;
    while (VL_LTS_III(32, 0U, tb__DOT__stim1__DOT__unnamedblk1_9__DOT____Vrepeat8)) {
        co_await vlSelfRef.__VtrigSched_h32009f5a__0.trigger(0U, 
                                                             nullptr, 
                                                             "@(posedge tb.clk)", 
                                                             "aes_cipher_top_stimulus_gen.sv", 
                                                             105);
        vlSelfRef.__Vm_traceActivity[2U] = 1U;
        tb__DOT__stim1__DOT__unnamedblk1_9__DOT____Vrepeat8 
            = (tb__DOT__stim1__DOT__unnamedblk1_9__DOT____Vrepeat8 
               - (IData)(1U));
        ++(vlSymsp->__Vcoverage[41]);
    }
    VL_FINISH_MT("aes_cipher_top_stimulus_gen.sv", 106, "");
    ++(vlSymsp->__Vcoverage[42]);
    vlSelfRef.__Vm_traceActivity[2U] = 1U;
    co_return;}

#ifdef VL_DEBUG
VL_ATTR_COLD void Vtb___024root___dump_triggers__act(const VlUnpacked<QData/*63:0*/, 1> &triggers, const std::string &tag);
#endif  // VL_DEBUG

void Vtb___024root___eval_triggers__act(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___eval_triggers__act\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.__VactTriggered[0U] = (((QData)((IData)(
                                                      (((((vlSelfRef.__VdlySched.awaitingCurrentTime() 
                                                           << 3U) 
                                                          | (((IData)(vlSelfRef.tb__DOT__clk) 
                                                              ^ (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__clk__0)) 
                                                             << 2U)) 
                                                         | ((((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u3.a) 
                                                              != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u3__a__0)) 
                                                             << 1U) 
                                                            | ((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u2.a) 
                                                               != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u2__a__0)))) 
                                                        << 8U) 
                                                       | (((((((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u1.a) 
                                                               != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u1__a__0)) 
                                                              << 3U) 
                                                             | (((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u0.a) 
                                                                 != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u0__a__0)) 
                                                                << 2U)) 
                                                            | ((((IData)(vlSelfRef.tb__DOT__top_module1__DOT__sa_33) 
                                                                 != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_33__0)) 
                                                                << 1U) 
                                                               | ((IData)(vlSelfRef.tb__DOT__top_module1__DOT__sa_23) 
                                                                  != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_23__0)))) 
                                                           << 4U) 
                                                          | (((((IData)(vlSelfRef.tb__DOT__top_module1__DOT__sa_13) 
                                                                != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_13__0)) 
                                                               << 3U) 
                                                              | (((IData)(vlSelfRef.tb__DOT__top_module1__DOT__sa_03) 
                                                                  != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_03__0)) 
                                                                 << 2U)) 
                                                             | ((((IData)(vlSelfRef.tb__DOT__top_module1__DOT__sa_32) 
                                                                  != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_32__0)) 
                                                                 << 1U) 
                                                                | ((IData)(vlSelfRef.tb__DOT__top_module1__DOT__sa_22) 
                                                                   != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_22__0)))))))) 
                                      << 0x00000020U) 
                                     | (QData)((IData)(
                                                       ((((((((((IData)(vlSelfRef.tb__DOT__top_module1__DOT__sa_12) 
                                                                != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_12__0)) 
                                                               << 3U) 
                                                              | (((IData)(vlSelfRef.tb__DOT__top_module1__DOT__sa_02) 
                                                                  != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_02__0)) 
                                                                 << 2U)) 
                                                             | ((((IData)(vlSelfRef.tb__DOT__top_module1__DOT__sa_31) 
                                                                  != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_31__0)) 
                                                                 << 1U) 
                                                                | ((IData)(vlSelfRef.tb__DOT__top_module1__DOT__sa_21) 
                                                                   != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_21__0)))) 
                                                            << 0x0000000cU) 
                                                           | ((((((IData)(vlSelfRef.tb__DOT__top_module1__DOT__sa_11) 
                                                                  != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_11__0)) 
                                                                 << 3U) 
                                                                | (((IData)(vlSelfRef.tb__DOT__top_module1__DOT__sa_01) 
                                                                    != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_01__0)) 
                                                                   << 2U)) 
                                                               | ((((IData)(vlSelfRef.tb__DOT__top_module1__DOT__sa_30) 
                                                                    != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_30__0)) 
                                                                   << 1U) 
                                                                  | ((IData)(vlSelfRef.tb__DOT__top_module1__DOT__sa_20) 
                                                                     != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_20__0)))) 
                                                              << 8U)) 
                                                          | (((((((IData)(vlSelfRef.tb__DOT__top_module1__DOT__sa_10) 
                                                                  != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_10__0)) 
                                                                 << 3U) 
                                                                | (((IData)(vlSelfRef.tb__DOT__top_module1__DOT__sa_00) 
                                                                    != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_00__0)) 
                                                                   << 2U)) 
                                                               | ((((IData)(vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u3.a) 
                                                                    != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__u0__DOT__u3__a__0)) 
                                                                   << 1U) 
                                                                  | ((IData)(vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u2.a) 
                                                                     != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__u0__DOT__u2__a__0)))) 
                                                              << 4U) 
                                                             | (((((IData)(vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u1.a) 
                                                                   != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__u0__DOT__u1__a__0)) 
                                                                  << 3U) 
                                                                 | (((IData)(vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u0.a) 
                                                                     != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__u0__DOT__u0__a__0)) 
                                                                    << 2U)) 
                                                                | ((((IData)(vlSelfRef.tb__DOT__good1__DOT__sa33) 
                                                                     != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa33__0)) 
                                                                    << 1U) 
                                                                   | ((IData)(vlSelfRef.tb__DOT__good1__DOT__sa32) 
                                                                      != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa32__0)))))) 
                                                         << 0x00000010U) 
                                                        | ((((((((IData)(vlSelfRef.tb__DOT__good1__DOT__sa31) 
                                                                 != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa31__0)) 
                                                                << 3U) 
                                                               | (((IData)(vlSelfRef.tb__DOT__good1__DOT__sa30) 
                                                                   != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa30__0)) 
                                                                  << 2U)) 
                                                              | ((((IData)(vlSelfRef.tb__DOT__good1__DOT__sa23) 
                                                                   != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa23__0)) 
                                                                  << 1U) 
                                                                 | ((IData)(vlSelfRef.tb__DOT__good1__DOT__sa22) 
                                                                    != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa22__0)))) 
                                                             << 0x0000000cU) 
                                                            | ((((((IData)(vlSelfRef.tb__DOT__good1__DOT__sa21) 
                                                                   != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa21__0)) 
                                                                  << 3U) 
                                                                 | (((IData)(vlSelfRef.tb__DOT__good1__DOT__sa20) 
                                                                     != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa20__0)) 
                                                                    << 2U)) 
                                                                | ((((IData)(vlSelfRef.tb__DOT__good1__DOT__sa13) 
                                                                     != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa13__0)) 
                                                                    << 1U) 
                                                                   | ((IData)(vlSelfRef.tb__DOT__good1__DOT__sa12) 
                                                                      != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa12__0)))) 
                                                               << 8U)) 
                                                           | (((((((IData)(vlSelfRef.tb__DOT__good1__DOT__sa11) 
                                                                   != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa11__0)) 
                                                                  << 3U) 
                                                                 | (((IData)(vlSelfRef.tb__DOT__good1__DOT__sa10) 
                                                                     != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa10__0)) 
                                                                    << 2U)) 
                                                                | ((((IData)(vlSelfRef.tb__DOT__good1__DOT__sa03) 
                                                                     != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa03__0)) 
                                                                    << 1U) 
                                                                   | ((IData)(vlSelfRef.tb__DOT__good1__DOT__sa02) 
                                                                      != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa02__0)))) 
                                                               << 4U) 
                                                              | (((((IData)(vlSelfRef.tb__DOT__good1__DOT__sa01) 
                                                                    != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa01__0)) 
                                                                   << 3U) 
                                                                  | (((IData)(vlSelfRef.tb__DOT__good1__DOT__sa00) 
                                                                      != (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa00__0)) 
                                                                     << 2U)) 
                                                                 | ((((~ (IData)(vlSelfRef.tb__DOT__clk)) 
                                                                      & (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__clk__0)) 
                                                                     << 1U) 
                                                                    | ((IData)(vlSelfRef.tb__DOT__clk) 
                                                                       & (~ (IData)(vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__clk__0)))))))))));
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__clk__0 
        = vlSelfRef.tb__DOT__clk;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa00__0 
        = vlSelfRef.tb__DOT__good1__DOT__sa00;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa01__0 
        = vlSelfRef.tb__DOT__good1__DOT__sa01;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa02__0 
        = vlSelfRef.tb__DOT__good1__DOT__sa02;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa03__0 
        = vlSelfRef.tb__DOT__good1__DOT__sa03;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa10__0 
        = vlSelfRef.tb__DOT__good1__DOT__sa10;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa11__0 
        = vlSelfRef.tb__DOT__good1__DOT__sa11;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa12__0 
        = vlSelfRef.tb__DOT__good1__DOT__sa12;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa13__0 
        = vlSelfRef.tb__DOT__good1__DOT__sa13;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa20__0 
        = vlSelfRef.tb__DOT__good1__DOT__sa20;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa21__0 
        = vlSelfRef.tb__DOT__good1__DOT__sa21;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa22__0 
        = vlSelfRef.tb__DOT__good1__DOT__sa22;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa23__0 
        = vlSelfRef.tb__DOT__good1__DOT__sa23;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa30__0 
        = vlSelfRef.tb__DOT__good1__DOT__sa30;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa31__0 
        = vlSelfRef.tb__DOT__good1__DOT__sa31;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa32__0 
        = vlSelfRef.tb__DOT__good1__DOT__sa32;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__sa33__0 
        = vlSelfRef.tb__DOT__good1__DOT__sa33;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__u0__DOT__u0__a__0 
        = vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u0.a;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__u0__DOT__u1__a__0 
        = vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u1.a;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__u0__DOT__u2__a__0 
        = vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u2.a;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__good1__DOT__u0__DOT__u3__a__0 
        = vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u3.a;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_00__0 
        = vlSelfRef.tb__DOT__top_module1__DOT__sa_00;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_10__0 
        = vlSelfRef.tb__DOT__top_module1__DOT__sa_10;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_20__0 
        = vlSelfRef.tb__DOT__top_module1__DOT__sa_20;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_30__0 
        = vlSelfRef.tb__DOT__top_module1__DOT__sa_30;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_01__0 
        = vlSelfRef.tb__DOT__top_module1__DOT__sa_01;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_11__0 
        = vlSelfRef.tb__DOT__top_module1__DOT__sa_11;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_21__0 
        = vlSelfRef.tb__DOT__top_module1__DOT__sa_21;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_31__0 
        = vlSelfRef.tb__DOT__top_module1__DOT__sa_31;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_02__0 
        = vlSelfRef.tb__DOT__top_module1__DOT__sa_02;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_12__0 
        = vlSelfRef.tb__DOT__top_module1__DOT__sa_12;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_22__0 
        = vlSelfRef.tb__DOT__top_module1__DOT__sa_22;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_32__0 
        = vlSelfRef.tb__DOT__top_module1__DOT__sa_32;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_03__0 
        = vlSelfRef.tb__DOT__top_module1__DOT__sa_03;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_13__0 
        = vlSelfRef.tb__DOT__top_module1__DOT__sa_13;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_23__0 
        = vlSelfRef.tb__DOT__top_module1__DOT__sa_23;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__sa_33__0 
        = vlSelfRef.tb__DOT__top_module1__DOT__sa_33;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u0__a__0 
        = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u0.a;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u1__a__0 
        = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u1.a;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u2__a__0 
        = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u2.a;
    vlSelfRef.__Vtrigprevexpr___TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u3__a__0 
        = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u3.a;
    if (VL_UNLIKELY(((1U & (~ (IData)(vlSelfRef.__VactDidInit)))))) {
        vlSelfRef.__VactDidInit = 1U;
        vlSelfRef.__VactTriggered[0U] = (4ULL | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (8ULL | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000000000010ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000000000020ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000000000040ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000000000080ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000000000100ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000000000200ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000000000400ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000000000800ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000000001000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000000002000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000000004000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000000008000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000000010000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000000020000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000000040000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000000080000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000000100000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000000200000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000000400000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000000800000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000001000000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000002000000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000004000000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000008000000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000010000000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000020000000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000040000000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000080000000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000100000000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000200000000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000400000000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000000800000000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000001000000000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000002000000000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000004000000000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000008000000000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000010000000000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
        vlSelfRef.__VactTriggered[0U] = (0x0000020000000000ULL 
                                         | vlSelfRef.__VactTriggered
                                         [0U]);
    }
#ifdef VL_DEBUG
    if (VL_UNLIKELY(vlSymsp->_vm_contextp__->debug())) {
        Vtb___024root___dump_triggers__act(vlSelfRef.__VactTriggered, "act"s);
    }
#endif
}

bool Vtb___024root___trigger_anySet__act(const VlUnpacked<QData/*63:0*/, 1> &in) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___trigger_anySet__act\n"); );
    // Locals
    IData/*31:0*/ n;
    // Body
    n = 0U;
    do {
        if (in[n]) {
            return (1U);
        }
        n = ((IData)(1U) + n);
    } while ((1U > n));
    return (0U);
}

void Vtb___024root___nba_sequent__TOP__0(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___nba_sequent__TOP__0\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    IData/*31:0*/ __Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__Vfuncout;
    __Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__Vfuncout = 0;
    CData/*3:0*/ __Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__i;
    __Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__i = 0;
    IData/*31:0*/ __Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__Vfuncout;
    __Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__Vfuncout = 0;
    CData/*3:0*/ __Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__i;
    __Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__i = 0;
    CData/*3:0*/ __Vdly__tb__DOT__good1__DOT__dcnt;
    __Vdly__tb__DOT__good1__DOT__dcnt = 0;
    // Body
    ++(vlSymsp->__Vcoverage[48]);
    ++(vlSymsp->__Vcoverage[52]);
    ++(vlSymsp->__Vcoverage[101]);
    ++(vlSymsp->__Vcoverage[102]);
    ++(vlSymsp->__Vcoverage[103]);
    ++(vlSymsp->__Vcoverage[104]);
    ++(vlSymsp->__Vcoverage[105]);
    ++(vlSymsp->__Vcoverage[106]);
    ++(vlSymsp->__Vcoverage[107]);
    ++(vlSymsp->__Vcoverage[108]);
    ++(vlSymsp->__Vcoverage[109]);
    ++(vlSymsp->__Vcoverage[110]);
    ++(vlSymsp->__Vcoverage[111]);
    ++(vlSymsp->__Vcoverage[112]);
    ++(vlSymsp->__Vcoverage[113]);
    ++(vlSymsp->__Vcoverage[114]);
    ++(vlSymsp->__Vcoverage[115]);
    ++(vlSymsp->__Vcoverage[116]);
    __Vdly__tb__DOT__good1__DOT__dcnt = vlSelfRef.tb__DOT__good1__DOT__dcnt;
    vlSelfRef.__Vdly__tb__DOT__top_module1__DOT__kld 
        = vlSelfRef.tb__DOT__top_module1__DOT__kld;
    vlSelfRef.__Vdly__tb__DOT__top_module1__DOT__dcnt 
        = vlSelfRef.tb__DOT__top_module1__DOT__dcnt;
    vlSelfRef.tb__DOT__stats1__BRA__31__03a0__KET__ 
        = ((IData)(1U) + vlSelfRef.tb__DOT__stats1__BRA__31__03a0__KET__);
    if (((IData)(vlSelfRef.tb__DOT__tb_match_text) 
         & (IData)(vlSelfRef.tb__DOT__tb_match_done))) {
        ++(vlSymsp->__Vcoverage[7]);
    } else {
        if ((0U == vlSelfRef.tb__DOT__stats1__BRA__223__03a192__KET__)) {
            ++(vlSymsp->__Vcoverage[4]);
            vlSelfRef.tb__DOT__stats1__BRA__191__03a160__KET__ 
                = (IData)(VL_TIME_UNITED_Q(1));
        } else {
            ++(vlSymsp->__Vcoverage[5]);
        }
        vlSelfRef.tb__DOT__stats1__BRA__223__03a192__KET__ 
            = ((IData)(1U) + vlSelfRef.tb__DOT__stats1__BRA__223__03a192__KET__);
        ++(vlSymsp->__Vcoverage[6]);
    }
    if (vlSelfRef.tb__DOT__tb_match_text) {
        ++(vlSymsp->__Vcoverage[11]);
    } else {
        if ((0U == vlSelfRef.tb__DOT__stats1__BRA__159__03a128__KET__)) {
            ++(vlSymsp->__Vcoverage[8]);
            vlSelfRef.tb__DOT__stats1__BRA__127__03a96__KET__ 
                = (IData)(VL_TIME_UNITED_Q(1));
        } else {
            ++(vlSymsp->__Vcoverage[9]);
        }
        vlSelfRef.tb__DOT__stats1__BRA__159__03a128__KET__ 
            = ((IData)(1U) + vlSelfRef.tb__DOT__stats1__BRA__159__03a128__KET__);
        ++(vlSymsp->__Vcoverage[10]);
    }
    if (vlSelfRef.tb__DOT__tb_match_done) {
        ++(vlSymsp->__Vcoverage[15]);
    } else {
        if ((0U == vlSelfRef.tb__DOT__stats1__BRA__95__03a64__KET__)) {
            ++(vlSymsp->__Vcoverage[12]);
            vlSelfRef.tb__DOT__stats1__BRA__63__03a32__KET__ 
                = (IData)(VL_TIME_UNITED_Q(1));
        } else {
            ++(vlSymsp->__Vcoverage[13]);
        }
        vlSelfRef.tb__DOT__stats1__BRA__95__03a64__KET__ 
            = ((IData)(1U) + vlSelfRef.tb__DOT__stats1__BRA__95__03a64__KET__);
        ++(vlSymsp->__Vcoverage[14]);
    }
    ++(vlSymsp->__Vcoverage[16]);
    if (vlSelfRef.tb__DOT__rst) {
        if (vlSelfRef.tb__DOT__ld) {
            ++(vlSymsp->__Vcoverage[45]);
            __Vdly__tb__DOT__good1__DOT__dcnt = 0x0bU;
        } else if ((0U != (IData)(vlSelfRef.tb__DOT__good1__DOT__dcnt))) {
            __Vdly__tb__DOT__good1__DOT__dcnt = (0x0000000fU 
                                                 & ((IData)(vlSelfRef.tb__DOT__good1__DOT__dcnt) 
                                                    - (IData)(1U)));
            ++(vlSymsp->__Vcoverage[43]);
        } else {
            ++(vlSymsp->__Vcoverage[44]);
        }
    } else {
        ++(vlSymsp->__Vcoverage[46]);
        __Vdly__tb__DOT__good1__DOT__dcnt = 0U;
    }
    ++(vlSymsp->__Vcoverage[47]);
    vlSelfRef.__VdlyVal__tb__DOT__top_module1__DOT__u_key_expand__DOT__w__v0 
        = ((IData)(vlSelfRef.tb__DOT__top_module1__DOT__kld)
            ? ([&]() {
                ++(vlSymsp->__Vcoverage[181]);
            }(), vlSelfRef.tb__DOT__key[3U]) : ([&]() {
                ++(vlSymsp->__Vcoverage[182]);
            }(), ((vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                   [0U] ^ vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__subword) 
                  ^ vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__rcon)));
    vlSelfRef.__VdlySet__tb__DOT__top_module1__DOT__u_key_expand__DOT__w__v0 = 1U;
    ++(vlSymsp->__Vcoverage[183]);
    vlSelfRef.__VdlyVal__tb__DOT__top_module1__DOT__u_key_expand__DOT__w__v1 
        = ((IData)(vlSelfRef.tb__DOT__top_module1__DOT__kld)
            ? ([&]() {
                ++(vlSymsp->__Vcoverage[184]);
            }(), vlSelfRef.tb__DOT__key[2U]) : ([&]() {
                ++(vlSymsp->__Vcoverage[185]);
            }(), (((vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                    [0U] ^ vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                    [1U]) ^ vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__subword) 
                  ^ vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__rcon)));
    vlSelfRef.__VdlySet__tb__DOT__top_module1__DOT__u_key_expand__DOT__w__v1 = 1U;
    ++(vlSymsp->__Vcoverage[186]);
    vlSelfRef.__VdlyVal__tb__DOT__top_module1__DOT__u_key_expand__DOT__w__v2 
        = ((IData)(vlSelfRef.tb__DOT__top_module1__DOT__kld)
            ? ([&]() {
                ++(vlSymsp->__Vcoverage[187]);
            }(), vlSelfRef.tb__DOT__key[1U]) : ([&]() {
                ++(vlSymsp->__Vcoverage[188]);
            }(), ((((vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                     [0U] ^ vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                     [2U]) ^ vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                    [1U]) ^ vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__subword) 
                  ^ vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__rcon)));
    vlSelfRef.__VdlySet__tb__DOT__top_module1__DOT__u_key_expand__DOT__w__v2 = 1U;
    ++(vlSymsp->__Vcoverage[189]);
    vlSelfRef.__VdlyVal__tb__DOT__top_module1__DOT__u_key_expand__DOT__w__v3 
        = ((IData)(vlSelfRef.tb__DOT__top_module1__DOT__kld)
            ? ([&]() {
                ++(vlSymsp->__Vcoverage[190]);
            }(), vlSelfRef.tb__DOT__key[0U]) : ([&]() {
                ++(vlSymsp->__Vcoverage[191]);
            }(), (((((vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                      [0U] ^ vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                      [3U]) ^ vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                     [2U]) ^ vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                    [1U]) ^ vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__subword) 
                  ^ vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__rcon)));
    vlSelfRef.__VdlySet__tb__DOT__top_module1__DOT__u_key_expand__DOT__w__v3 = 1U;
    ++(vlSymsp->__Vcoverage[192]);
    vlSelfRef.__VdlyVal__tb__DOT__good1__DOT__u0__DOT__w__v0 
        = ((IData)(vlSelfRef.tb__DOT__ld) ? ([&]() {
                ++(vlSymsp->__Vcoverage[119]);
            }(), vlSelfRef.tb__DOT__key[3U]) : ([&]() {
                ++(vlSymsp->__Vcoverage[120]);
            }(), ((vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                   [0U] ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__subword) 
                  ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__rcon)));
    vlSelfRef.__VdlySet__tb__DOT__good1__DOT__u0__DOT__w__v0 = 1U;
    ++(vlSymsp->__Vcoverage[121]);
    vlSelfRef.__VdlyVal__tb__DOT__good1__DOT__u0__DOT__w__v1 
        = ((IData)(vlSelfRef.tb__DOT__ld) ? ([&]() {
                ++(vlSymsp->__Vcoverage[122]);
            }(), vlSelfRef.tb__DOT__key[2U]) : ([&]() {
                ++(vlSymsp->__Vcoverage[123]);
            }(), (((vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                    [0U] ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                    [1U]) ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__subword) 
                  ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__rcon)));
    vlSelfRef.__VdlySet__tb__DOT__good1__DOT__u0__DOT__w__v1 = 1U;
    ++(vlSymsp->__Vcoverage[124]);
    vlSelfRef.__VdlyVal__tb__DOT__good1__DOT__u0__DOT__w__v2 
        = ((IData)(vlSelfRef.tb__DOT__ld) ? ([&]() {
                ++(vlSymsp->__Vcoverage[125]);
            }(), vlSelfRef.tb__DOT__key[1U]) : ([&]() {
                ++(vlSymsp->__Vcoverage[126]);
            }(), ((((vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                     [0U] ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                     [2U]) ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                    [1U]) ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__subword) 
                  ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__rcon)));
    vlSelfRef.__VdlySet__tb__DOT__good1__DOT__u0__DOT__w__v2 = 1U;
    ++(vlSymsp->__Vcoverage[127]);
    vlSelfRef.__VdlyVal__tb__DOT__good1__DOT__u0__DOT__w__v3 
        = ((IData)(vlSelfRef.tb__DOT__ld) ? ([&]() {
                ++(vlSymsp->__Vcoverage[128]);
            }(), vlSelfRef.tb__DOT__key[0U]) : ([&]() {
                ++(vlSymsp->__Vcoverage[129]);
            }(), (((((vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                      [0U] ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                      [3U]) ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                     [2U]) ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                    [1U]) ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__subword) 
                  ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__rcon)));
    vlSelfRef.__VdlySet__tb__DOT__good1__DOT__u0__DOT__w__v3 = 1U;
    ++(vlSymsp->__Vcoverage[130]);
    vlSelfRef.tb__DOT__done_ref = (1U & (((~ (0U != 
                                              (7U & 
                                               ((IData)(vlSelfRef.tb__DOT__good1__DOT__dcnt) 
                                                >> 1U)))) 
                                          & (IData)(vlSelfRef.tb__DOT__good1__DOT__dcnt)) 
                                         & (~ (IData)(vlSelfRef.tb__DOT__ld))));
    vlSelfRef.tb__DOT__text_out_ref[3U] = ((0x00ffffffU 
                                            & vlSelfRef.tb__DOT__text_out_ref[3U]) 
                                           | (0xff000000U 
                                              & (((IData)(vlSymsp->TOP__tb__DOT__good1__DOT__us00.b) 
                                                  << 0x00000018U) 
                                                 ^ 
                                                 (0xff000000U 
                                                  & vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                                  [0U]))));
    vlSelfRef.tb__DOT__text_out_ref[2U] = ((0x00ffffffU 
                                            & vlSelfRef.tb__DOT__text_out_ref[2U]) 
                                           | (0xff000000U 
                                              & (((IData)(vlSymsp->TOP__tb__DOT__good1__DOT__us01.b) 
                                                  << 0x00000018U) 
                                                 ^ 
                                                 (0xff000000U 
                                                  & vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                                  [1U]))));
    vlSelfRef.tb__DOT__text_out_ref[1U] = ((0x00ffffffU 
                                            & vlSelfRef.tb__DOT__text_out_ref[1U]) 
                                           | (0xff000000U 
                                              & (((IData)(vlSymsp->TOP__tb__DOT__good1__DOT__us02.b) 
                                                  << 0x00000018U) 
                                                 ^ 
                                                 (0xff000000U 
                                                  & vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                                  [2U]))));
    vlSelfRef.tb__DOT__text_out_ref[0U] = ((0x00ffffffU 
                                            & vlSelfRef.tb__DOT__text_out_ref[0U]) 
                                           | (0xff000000U 
                                              & (((IData)(vlSymsp->TOP__tb__DOT__good1__DOT__us03.b) 
                                                  << 0x00000018U) 
                                                 ^ 
                                                 (0xff000000U 
                                                  & vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                                  [3U]))));
    vlSelfRef.tb__DOT__text_out_ref[3U] = ((0xff00ffffU 
                                            & vlSelfRef.tb__DOT__text_out_ref[3U]) 
                                           | (0x00ff0000U 
                                              & (((IData)(vlSymsp->TOP__tb__DOT__good1__DOT__us11.b) 
                                                  << 0x00000010U) 
                                                 ^ 
                                                 (0xffff0000U 
                                                  & vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                                  [0U]))));
    vlSelfRef.tb__DOT__text_out_ref[2U] = ((0xff00ffffU 
                                            & vlSelfRef.tb__DOT__text_out_ref[2U]) 
                                           | (0x00ff0000U 
                                              & (((IData)(vlSymsp->TOP__tb__DOT__good1__DOT__us12.b) 
                                                  << 0x00000010U) 
                                                 ^ 
                                                 (0xffff0000U 
                                                  & vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                                  [1U]))));
    vlSelfRef.tb__DOT__text_out_ref[1U] = ((0xff00ffffU 
                                            & vlSelfRef.tb__DOT__text_out_ref[1U]) 
                                           | (0x00ff0000U 
                                              & (((IData)(vlSymsp->TOP__tb__DOT__good1__DOT__us13.b) 
                                                  << 0x00000010U) 
                                                 ^ 
                                                 (0xffff0000U 
                                                  & vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                                  [2U]))));
    vlSelfRef.tb__DOT__text_out_ref[0U] = ((0xff00ffffU 
                                            & vlSelfRef.tb__DOT__text_out_ref[0U]) 
                                           | (0x00ff0000U 
                                              & (((IData)(vlSymsp->TOP__tb__DOT__good1__DOT__us10.b) 
                                                  << 0x00000010U) 
                                                 ^ 
                                                 (0xffff0000U 
                                                  & vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                                  [3U]))));
    vlSelfRef.tb__DOT__text_out_ref[3U] = ((0xffff00ffU 
                                            & vlSelfRef.tb__DOT__text_out_ref[3U]) 
                                           | (0x0000ff00U 
                                              & (((IData)(vlSymsp->TOP__tb__DOT__good1__DOT__us22.b) 
                                                  << 8U) 
                                                 ^ 
                                                 (0xffffff00U 
                                                  & vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                                  [0U]))));
    vlSelfRef.tb__DOT__text_out_ref[2U] = ((0xffff00ffU 
                                            & vlSelfRef.tb__DOT__text_out_ref[2U]) 
                                           | (0x0000ff00U 
                                              & (((IData)(vlSymsp->TOP__tb__DOT__good1__DOT__us23.b) 
                                                  << 8U) 
                                                 ^ 
                                                 (0xffffff00U 
                                                  & vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                                  [1U]))));
    vlSelfRef.tb__DOT__text_out_ref[1U] = ((0xffff00ffU 
                                            & vlSelfRef.tb__DOT__text_out_ref[1U]) 
                                           | (0x0000ff00U 
                                              & (((IData)(vlSymsp->TOP__tb__DOT__good1__DOT__us20.b) 
                                                  << 8U) 
                                                 ^ 
                                                 (0xffffff00U 
                                                  & vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                                  [2U]))));
    vlSelfRef.tb__DOT__text_out_ref[0U] = ((0xffff00ffU 
                                            & vlSelfRef.tb__DOT__text_out_ref[0U]) 
                                           | (0x0000ff00U 
                                              & (((IData)(vlSymsp->TOP__tb__DOT__good1__DOT__us21.b) 
                                                  << 8U) 
                                                 ^ 
                                                 (0xffffff00U 
                                                  & vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                                  [3U]))));
    vlSelfRef.tb__DOT__text_out_ref[3U] = ((0xffffff00U 
                                            & vlSelfRef.tb__DOT__text_out_ref[3U]) 
                                           | (0x000000ffU 
                                              & ((IData)(vlSymsp->TOP__tb__DOT__good1__DOT__us33.b) 
                                                 ^ 
                                                 vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                                 [0U])));
    vlSelfRef.tb__DOT__text_out_ref[2U] = ((0xffffff00U 
                                            & vlSelfRef.tb__DOT__text_out_ref[2U]) 
                                           | (0x000000ffU 
                                              & ((IData)(vlSymsp->TOP__tb__DOT__good1__DOT__us30.b) 
                                                 ^ 
                                                 vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                                 [1U])));
    vlSelfRef.tb__DOT__text_out_ref[1U] = ((0xffffff00U 
                                            & vlSelfRef.tb__DOT__text_out_ref[1U]) 
                                           | (0x000000ffU 
                                              & ((IData)(vlSymsp->TOP__tb__DOT__good1__DOT__us31.b) 
                                                 ^ 
                                                 vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                                 [2U])));
    vlSelfRef.tb__DOT__text_out_ref[0U] = ((0xffffff00U 
                                            & vlSelfRef.tb__DOT__text_out_ref[0U]) 
                                           | (0x000000ffU 
                                              & ((IData)(vlSymsp->TOP__tb__DOT__good1__DOT__us32.b) 
                                                 ^ 
                                                 vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                                 [3U])));
    vlSelfRef.tb__DOT__good1__DOT__dcnt = __Vdly__tb__DOT__good1__DOT__dcnt;
    if (vlSelfRef.tb__DOT__top_module1__DOT__kld) {
        ++(vlSymsp->__Vcoverage[193]);
        vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__rcon = 0x01000000U;
    } else {
        __Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__i 
            = (0x0000000fU & ((IData)(1U) + (IData)(vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__rcnt)));
        if ((8U & (IData)(__Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__i))) {
            if ((4U & (IData)(__Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__i))) {
                ++(vlSymsp->__Vcoverage[209]);
                __Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__Vfuncout = 0U;
            } else if ((2U & (IData)(__Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__i))) {
                ++(vlSymsp->__Vcoverage[209]);
                __Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__Vfuncout = 0U;
            } else if ((1U & (IData)(__Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__i))) {
                ++(vlSymsp->__Vcoverage[208]);
                __Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__Vfuncout = 0x36000000U;
            } else {
                ++(vlSymsp->__Vcoverage[207]);
                __Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__Vfuncout = 0x1b000000U;
            }
        } else if ((4U & (IData)(__Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__i))) {
            if ((2U & (IData)(__Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__i))) {
                if ((1U & (IData)(__Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__i))) {
                    ++(vlSymsp->__Vcoverage[206]);
                    __Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__Vfuncout = 0x80000000U;
                } else {
                    ++(vlSymsp->__Vcoverage[205]);
                    __Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__Vfuncout = 0x40000000U;
                }
            } else if ((1U & (IData)(__Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__i))) {
                ++(vlSymsp->__Vcoverage[204]);
                __Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__Vfuncout = 0x20000000U;
            } else {
                ++(vlSymsp->__Vcoverage[203]);
                __Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__Vfuncout = 0x10000000U;
            }
        } else if ((2U & (IData)(__Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__i))) {
            if ((1U & (IData)(__Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__i))) {
                ++(vlSymsp->__Vcoverage[202]);
                __Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__Vfuncout = 0x08000000U;
            } else {
                ++(vlSymsp->__Vcoverage[201]);
                __Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__Vfuncout = 0x04000000U;
            }
        } else if ((1U & (IData)(__Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__i))) {
            ++(vlSymsp->__Vcoverage[200]);
            __Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__Vfuncout = 0x02000000U;
        } else {
            ++(vlSymsp->__Vcoverage[199]);
            __Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__Vfuncout = 0x01000000U;
        }
        ++(vlSymsp->__Vcoverage[210]);
        vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__rcon 
            = __Vfunc_tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__frcon__74__Vfuncout;
        ++(vlSymsp->__Vcoverage[194]);
    }
    ++(vlSymsp->__Vcoverage[195]);
    if (vlSelfRef.tb__DOT__ld) {
        ++(vlSymsp->__Vcoverage[131]);
        vlSelfRef.tb__DOT__good1__DOT__u0__DOT__rcon = 0x01000000U;
    } else {
        __Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__i 
            = (0x0000000fU & ((IData)(1U) + (IData)(vlSelfRef.tb__DOT__good1__DOT__u0__DOT__r0__DOT__rcnt)));
        if ((8U & (IData)(__Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__i))) {
            if ((4U & (IData)(__Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__i))) {
                ++(vlSymsp->__Vcoverage[147]);
                __Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__Vfuncout = 0U;
            } else if ((2U & (IData)(__Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__i))) {
                ++(vlSymsp->__Vcoverage[147]);
                __Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__Vfuncout = 0U;
            } else if ((1U & (IData)(__Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__i))) {
                ++(vlSymsp->__Vcoverage[146]);
                __Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__Vfuncout = 0x36000000U;
            } else {
                ++(vlSymsp->__Vcoverage[145]);
                __Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__Vfuncout = 0x1b000000U;
            }
        } else if ((4U & (IData)(__Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__i))) {
            if ((2U & (IData)(__Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__i))) {
                if ((1U & (IData)(__Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__i))) {
                    ++(vlSymsp->__Vcoverage[144]);
                    __Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__Vfuncout = 0x80000000U;
                } else {
                    ++(vlSymsp->__Vcoverage[143]);
                    __Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__Vfuncout = 0x40000000U;
                }
            } else if ((1U & (IData)(__Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__i))) {
                ++(vlSymsp->__Vcoverage[142]);
                __Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__Vfuncout = 0x20000000U;
            } else {
                ++(vlSymsp->__Vcoverage[141]);
                __Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__Vfuncout = 0x10000000U;
            }
        } else if ((2U & (IData)(__Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__i))) {
            if ((1U & (IData)(__Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__i))) {
                ++(vlSymsp->__Vcoverage[140]);
                __Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__Vfuncout = 0x08000000U;
            } else {
                ++(vlSymsp->__Vcoverage[139]);
                __Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__Vfuncout = 0x04000000U;
            }
        } else if ((1U & (IData)(__Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__i))) {
            ++(vlSymsp->__Vcoverage[138]);
            __Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__Vfuncout = 0x02000000U;
        } else {
            ++(vlSymsp->__Vcoverage[137]);
            __Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__Vfuncout = 0x01000000U;
        }
        ++(vlSymsp->__Vcoverage[148]);
        vlSelfRef.tb__DOT__good1__DOT__u0__DOT__rcon 
            = __Vfunc_tb__DOT__good1__DOT__u0__DOT__r0__DOT__frcon__41__Vfuncout;
        ++(vlSymsp->__Vcoverage[132]);
    }
    ++(vlSymsp->__Vcoverage[133]);
    if (vlSelfRef.tb__DOT__top_module1__DOT__kld) {
        ++(vlSymsp->__Vcoverage[196]);
        vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__rcnt = 0U;
    } else {
        ++(vlSymsp->__Vcoverage[197]);
        vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__rcnt 
            = vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__rcnt_next;
    }
    ++(vlSymsp->__Vcoverage[198]);
    if (vlSelfRef.tb__DOT__ld) {
        ++(vlSymsp->__Vcoverage[134]);
        vlSelfRef.tb__DOT__good1__DOT__u0__DOT__r0__DOT__rcnt = 0U;
    } else {
        ++(vlSymsp->__Vcoverage[135]);
        vlSelfRef.tb__DOT__good1__DOT__u0__DOT__r0__DOT__rcnt 
            = vlSelfRef.tb__DOT__good1__DOT__u0__DOT__r0__DOT__rcnt_next;
    }
    ++(vlSymsp->__Vcoverage[136]);
    vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__rcnt_next 
        = (0x0000000fU & ((IData)(1U) + (IData)(vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__rcnt)));
    vlSelfRef.tb__DOT__good1__DOT__u0__DOT__r0__DOT__rcnt_next 
        = (0x0000000fU & ((IData)(1U) + (IData)(vlSelfRef.tb__DOT__good1__DOT__u0__DOT__r0__DOT__rcnt)));
}

void Vtb___024root___nba_sequent__TOP__1(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___nba_sequent__TOP__1\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.__Vdly__tb__DOT__top_module1__DOT__ld_cap 
        = vlSelfRef.tb__DOT__top_module1__DOT__ld_cap;
}

void Vtb___024root___nba_sequent__TOP__2(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___nba_sequent__TOP__2\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if (vlSelfRef.tb__DOT__rst) {
        if (vlSelfRef.tb__DOT__ld) {
            ++(vlSymsp->__Vcoverage[149]);
            vlSelfRef.__Vdly__tb__DOT__top_module1__DOT__ld_cap = 1U;
        } else {
            ++(vlSymsp->__Vcoverage[150]);
        }
    } else {
        ++(vlSymsp->__Vcoverage[151]);
        vlSelfRef.__Vdly__tb__DOT__top_module1__DOT__ld_cap = 0U;
    }
    ++(vlSymsp->__Vcoverage[152]);
}

void Vtb___024root___nba_comb__TOP__0(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___nba_comb__TOP__0\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__subword 
        = ((((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u0.b) 
             << 0x00000018U) | ((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u1.b) 
                                << 0x00000010U)) | 
           (((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u2.b) 
             << 8U) | (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u3.b)));
}

void Vtb___024root___nba_comb__TOP__1(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___nba_comb__TOP__1\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb__DOT__good1__DOT__u0__DOT__subword 
        = ((((IData)(vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u0.b) 
             << 0x00000018U) | ((IData)(vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u1.b) 
                                << 0x00000010U)) | 
           (((IData)(vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u2.b) 
             << 8U) | (IData)(vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u3.b)));
}

void Vtb___024root___nba_sequent__TOP__3(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___nba_sequent__TOP__3\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb__DOT__good1__DOT__sa00 = (0x000000ffU 
                                           & ((IData)(vlSelfRef.tb__DOT__good1__DOT__ld_r)
                                               ? ([&]() {
                    ++(vlSymsp->__Vcoverage[98]);
                }(), (((vlSelfRef.tb__DOT__good1__DOT__text_in_r[3U] 
                        << 8U) | (vlSelfRef.tb__DOT__good1__DOT__text_in_r[3U] 
                                  >> 0x00000018U)) 
                      ^ (vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                         [0U] >> 0x18U))) : ([&]() {
                    ++(vlSymsp->__Vcoverage[99]);
                }(), ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out0 
                       ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                       [0U]) >> 0x00000018U))));
    ++(vlSymsp->__Vcoverage[100]);
    vlSelfRef.tb__DOT__good1__DOT__sa01 = (0x000000ffU 
                                           & ((IData)(vlSelfRef.tb__DOT__good1__DOT__ld_r)
                                               ? ([&]() {
                    ++(vlSymsp->__Vcoverage[86]);
                }(), (((vlSelfRef.tb__DOT__good1__DOT__text_in_r[2U] 
                        << 8U) | (vlSelfRef.tb__DOT__good1__DOT__text_in_r[2U] 
                                  >> 0x00000018U)) 
                      ^ (vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                         [1U] >> 0x18U))) : ([&]() {
                    ++(vlSymsp->__Vcoverage[87]);
                }(), ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out1 
                       ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                       [1U]) >> 0x00000018U))));
    ++(vlSymsp->__Vcoverage[88]);
    vlSelfRef.tb__DOT__good1__DOT__sa02 = (0x000000ffU 
                                           & ((IData)(vlSelfRef.tb__DOT__good1__DOT__ld_r)
                                               ? ([&]() {
                    ++(vlSymsp->__Vcoverage[74]);
                }(), (((vlSelfRef.tb__DOT__good1__DOT__text_in_r[1U] 
                        << 8U) | (vlSelfRef.tb__DOT__good1__DOT__text_in_r[1U] 
                                  >> 0x00000018U)) 
                      ^ (vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                         [2U] >> 0x18U))) : ([&]() {
                    ++(vlSymsp->__Vcoverage[75]);
                }(), ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out2 
                       ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                       [2U]) >> 0x00000018U))));
    ++(vlSymsp->__Vcoverage[76]);
    vlSelfRef.tb__DOT__good1__DOT__sa03 = (0x000000ffU 
                                           & ((IData)(vlSelfRef.tb__DOT__good1__DOT__ld_r)
                                               ? ([&]() {
                    ++(vlSymsp->__Vcoverage[62]);
                }(), (((vlSelfRef.tb__DOT__good1__DOT__text_in_r[0U] 
                        << 8U) | (vlSelfRef.tb__DOT__good1__DOT__text_in_r[0U] 
                                  >> 0x00000018U)) 
                      ^ (vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                         [3U] >> 0x18U))) : ([&]() {
                    ++(vlSymsp->__Vcoverage[63]);
                }(), ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out3 
                       ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                       [3U]) >> 0x00000018U))));
    ++(vlSymsp->__Vcoverage[64]);
    vlSelfRef.tb__DOT__good1__DOT__sa10 = (0x000000ffU 
                                           & ((IData)(vlSelfRef.tb__DOT__good1__DOT__ld_r)
                                               ? ([&]() {
                    ++(vlSymsp->__Vcoverage[95]);
                }(), (((vlSelfRef.tb__DOT__good1__DOT__text_in_r[3U] 
                        << 0x00000010U) | (vlSelfRef.tb__DOT__good1__DOT__text_in_r[3U] 
                                           >> 0x00000010U)) 
                      ^ (vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                         [0U] >> 0x10U))) : ([&]() {
                    ++(vlSymsp->__Vcoverage[96]);
                }(), ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out0 
                       ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                       [0U]) >> 0x00000010U))));
    ++(vlSymsp->__Vcoverage[97]);
    vlSelfRef.tb__DOT__good1__DOT__sa11 = (0x000000ffU 
                                           & ((IData)(vlSelfRef.tb__DOT__good1__DOT__ld_r)
                                               ? ([&]() {
                    ++(vlSymsp->__Vcoverage[83]);
                }(), (((vlSelfRef.tb__DOT__good1__DOT__text_in_r[2U] 
                        << 0x00000010U) | (vlSelfRef.tb__DOT__good1__DOT__text_in_r[2U] 
                                           >> 0x00000010U)) 
                      ^ (vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                         [1U] >> 0x10U))) : ([&]() {
                    ++(vlSymsp->__Vcoverage[84]);
                }(), ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out1 
                       ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                       [1U]) >> 0x00000010U))));
    ++(vlSymsp->__Vcoverage[85]);
    vlSelfRef.tb__DOT__good1__DOT__sa12 = (0x000000ffU 
                                           & ((IData)(vlSelfRef.tb__DOT__good1__DOT__ld_r)
                                               ? ([&]() {
                    ++(vlSymsp->__Vcoverage[71]);
                }(), (((vlSelfRef.tb__DOT__good1__DOT__text_in_r[1U] 
                        << 0x00000010U) | (vlSelfRef.tb__DOT__good1__DOT__text_in_r[1U] 
                                           >> 0x00000010U)) 
                      ^ (vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                         [2U] >> 0x10U))) : ([&]() {
                    ++(vlSymsp->__Vcoverage[72]);
                }(), ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out2 
                       ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                       [2U]) >> 0x00000010U))));
    ++(vlSymsp->__Vcoverage[73]);
    vlSelfRef.tb__DOT__good1__DOT__sa13 = (0x000000ffU 
                                           & ((IData)(vlSelfRef.tb__DOT__good1__DOT__ld_r)
                                               ? ([&]() {
                    ++(vlSymsp->__Vcoverage[59]);
                }(), (((vlSelfRef.tb__DOT__good1__DOT__text_in_r[0U] 
                        << 0x00000010U) | (vlSelfRef.tb__DOT__good1__DOT__text_in_r[0U] 
                                           >> 0x00000010U)) 
                      ^ (vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                         [3U] >> 0x10U))) : ([&]() {
                    ++(vlSymsp->__Vcoverage[60]);
                }(), ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out3 
                       ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                       [3U]) >> 0x00000010U))));
    ++(vlSymsp->__Vcoverage[61]);
    vlSelfRef.tb__DOT__good1__DOT__sa20 = (0x000000ffU 
                                           & ((IData)(vlSelfRef.tb__DOT__good1__DOT__ld_r)
                                               ? ([&]() {
                    ++(vlSymsp->__Vcoverage[92]);
                }(), (((vlSelfRef.tb__DOT__good1__DOT__text_in_r[3U] 
                        << 0x00000018U) | (vlSelfRef.tb__DOT__good1__DOT__text_in_r[3U] 
                                           >> 8U)) 
                      ^ (vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                         [0U] >> 8U))) : ([&]() {
                    ++(vlSymsp->__Vcoverage[93]);
                }(), ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out0 
                       ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                       [0U]) >> 8U))));
    ++(vlSymsp->__Vcoverage[94]);
    vlSelfRef.tb__DOT__good1__DOT__sa21 = (0x000000ffU 
                                           & ((IData)(vlSelfRef.tb__DOT__good1__DOT__ld_r)
                                               ? ([&]() {
                    ++(vlSymsp->__Vcoverage[80]);
                }(), (((vlSelfRef.tb__DOT__good1__DOT__text_in_r[2U] 
                        << 0x00000018U) | (vlSelfRef.tb__DOT__good1__DOT__text_in_r[2U] 
                                           >> 8U)) 
                      ^ (vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                         [1U] >> 8U))) : ([&]() {
                    ++(vlSymsp->__Vcoverage[81]);
                }(), ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out1 
                       ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                       [1U]) >> 8U))));
    ++(vlSymsp->__Vcoverage[82]);
    vlSelfRef.tb__DOT__good1__DOT__sa22 = (0x000000ffU 
                                           & ((IData)(vlSelfRef.tb__DOT__good1__DOT__ld_r)
                                               ? ([&]() {
                    ++(vlSymsp->__Vcoverage[68]);
                }(), (((vlSelfRef.tb__DOT__good1__DOT__text_in_r[1U] 
                        << 0x00000018U) | (vlSelfRef.tb__DOT__good1__DOT__text_in_r[1U] 
                                           >> 8U)) 
                      ^ (vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                         [2U] >> 8U))) : ([&]() {
                    ++(vlSymsp->__Vcoverage[69]);
                }(), ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out2 
                       ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                       [2U]) >> 8U))));
    ++(vlSymsp->__Vcoverage[70]);
    vlSelfRef.tb__DOT__good1__DOT__sa23 = (0x000000ffU 
                                           & ((IData)(vlSelfRef.tb__DOT__good1__DOT__ld_r)
                                               ? ([&]() {
                    ++(vlSymsp->__Vcoverage[56]);
                }(), (((vlSelfRef.tb__DOT__good1__DOT__text_in_r[0U] 
                        << 0x00000018U) | (vlSelfRef.tb__DOT__good1__DOT__text_in_r[0U] 
                                           >> 8U)) 
                      ^ (vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                         [3U] >> 8U))) : ([&]() {
                    ++(vlSymsp->__Vcoverage[57]);
                }(), ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out3 
                       ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                       [3U]) >> 8U))));
    ++(vlSymsp->__Vcoverage[58]);
    vlSelfRef.tb__DOT__good1__DOT__sa30 = (0x000000ffU 
                                           & ((IData)(vlSelfRef.tb__DOT__good1__DOT__ld_r)
                                               ? ([&]() {
                    ++(vlSymsp->__Vcoverage[89]);
                }(), (vlSelfRef.tb__DOT__good1__DOT__text_in_r[3U] 
                      ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                      [0U])) : ([&]() {
                    ++(vlSymsp->__Vcoverage[90]);
                }(), (vlSelfRef.tb__DOT__good1__DOT__mix_col_out0 
                      ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                      [0U]))));
    ++(vlSymsp->__Vcoverage[91]);
    vlSelfRef.tb__DOT__good1__DOT__sa31 = (0x000000ffU 
                                           & ((IData)(vlSelfRef.tb__DOT__good1__DOT__ld_r)
                                               ? ([&]() {
                    ++(vlSymsp->__Vcoverage[77]);
                }(), (vlSelfRef.tb__DOT__good1__DOT__text_in_r[2U] 
                      ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                      [1U])) : ([&]() {
                    ++(vlSymsp->__Vcoverage[78]);
                }(), (vlSelfRef.tb__DOT__good1__DOT__mix_col_out1 
                      ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                      [1U]))));
    ++(vlSymsp->__Vcoverage[79]);
    vlSelfRef.tb__DOT__good1__DOT__sa32 = (0x000000ffU 
                                           & ((IData)(vlSelfRef.tb__DOT__good1__DOT__ld_r)
                                               ? ([&]() {
                    ++(vlSymsp->__Vcoverage[65]);
                }(), (vlSelfRef.tb__DOT__good1__DOT__text_in_r[1U] 
                      ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                      [2U])) : ([&]() {
                    ++(vlSymsp->__Vcoverage[66]);
                }(), (vlSelfRef.tb__DOT__good1__DOT__mix_col_out2 
                      ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                      [2U]))));
    ++(vlSymsp->__Vcoverage[67]);
    vlSelfRef.tb__DOT__good1__DOT__sa33 = (0x000000ffU 
                                           & ((IData)(vlSelfRef.tb__DOT__good1__DOT__ld_r)
                                               ? ([&]() {
                    ++(vlSymsp->__Vcoverage[53]);
                }(), (vlSelfRef.tb__DOT__good1__DOT__text_in_r[0U] 
                      ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                      [3U])) : ([&]() {
                    ++(vlSymsp->__Vcoverage[54]);
                }(), (vlSelfRef.tb__DOT__good1__DOT__mix_col_out3 
                      ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                      [3U]))));
    ++(vlSymsp->__Vcoverage[55]);
    if (vlSelfRef.tb__DOT__rst) {
        if ((((0U == (IData)(vlSelfRef.tb__DOT__top_module1__DOT__state)) 
              & (IData)(vlSelfRef.tb__DOT__top_module1__DOT__ld_cap)) 
             & (~ (IData)(vlSelfRef.tb__DOT__top_module1__DOT__kld)))) {
            ++(vlSymsp->__Vcoverage[172]);
            vlSelfRef.__Vdly__tb__DOT__top_module1__DOT__kld = 1U;
            vlSelfRef.__Vdly__tb__DOT__top_module1__DOT__ld_cap = 0U;
        } else if ((((4U == (IData)(vlSelfRef.tb__DOT__top_module1__DOT__state)) 
                     & (IData)(vlSelfRef.tb__DOT__top_module1__DOT__ld_cap)) 
                    & (~ (IData)(vlSelfRef.tb__DOT__top_module1__DOT__kld)))) {
            ++(vlSymsp->__Vcoverage[171]);
            vlSelfRef.__Vdly__tb__DOT__top_module1__DOT__kld = 1U;
            vlSelfRef.__Vdly__tb__DOT__top_module1__DOT__ld_cap = 0U;
        } else if (((IData)(vlSelfRef.tb__DOT__top_module1__DOT__kld) 
                    & (1U == (IData)(vlSelfRef.tb__DOT__top_module1__DOT__next_state)))) {
            ++(vlSymsp->__Vcoverage[169]);
            vlSelfRef.__Vdly__tb__DOT__top_module1__DOT__kld = 0U;
        } else {
            ++(vlSymsp->__Vcoverage[170]);
        }
        if ((1U == (IData)(vlSelfRef.tb__DOT__top_module1__DOT__next_state))) {
            ++(vlSymsp->__Vcoverage[175]);
            vlSelfRef.__Vdly__tb__DOT__top_module1__DOT__dcnt = 0x0aU;
            vlSelfRef.tb__DOT__top_module1__DOT__sa_00 
                = (0x000000ffU & (((vlSelfRef.tb__DOT__text_in[3U] 
                                    << 8U) | (vlSelfRef.tb__DOT__text_in[3U] 
                                              >> 0x00000018U)) 
                                  ^ (vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                     [0U] >> 0x18U)));
            vlSelfRef.tb__DOT__top_module1__DOT__sa_10 
                = (0x000000ffU & (((vlSelfRef.tb__DOT__text_in[3U] 
                                    << 0x00000010U) 
                                   | (vlSelfRef.tb__DOT__text_in[3U] 
                                      >> 0x00000010U)) 
                                  ^ (vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                     [0U] >> 0x10U)));
            vlSelfRef.tb__DOT__top_module1__DOT__sa_20 
                = (0x000000ffU & (((vlSelfRef.tb__DOT__text_in[3U] 
                                    << 0x00000018U) 
                                   | (vlSelfRef.tb__DOT__text_in[3U] 
                                      >> 8U)) ^ (vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                                 [0U] 
                                                 >> 8U)));
            vlSelfRef.tb__DOT__top_module1__DOT__sa_30 
                = (0x000000ffU & (vlSelfRef.tb__DOT__text_in[3U] 
                                  ^ vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                  [0U]));
            vlSelfRef.tb__DOT__top_module1__DOT__sa_01 
                = (0x000000ffU & (((vlSelfRef.tb__DOT__text_in[2U] 
                                    << 8U) | (vlSelfRef.tb__DOT__text_in[2U] 
                                              >> 0x00000018U)) 
                                  ^ (vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                     [1U] >> 0x18U)));
            vlSelfRef.tb__DOT__top_module1__DOT__sa_11 
                = (0x000000ffU & (((vlSelfRef.tb__DOT__text_in[2U] 
                                    << 0x00000010U) 
                                   | (vlSelfRef.tb__DOT__text_in[2U] 
                                      >> 0x00000010U)) 
                                  ^ (vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                     [1U] >> 0x10U)));
            vlSelfRef.tb__DOT__top_module1__DOT__sa_21 
                = (0x000000ffU & (((vlSelfRef.tb__DOT__text_in[2U] 
                                    << 0x00000018U) 
                                   | (vlSelfRef.tb__DOT__text_in[2U] 
                                      >> 8U)) ^ (vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                                 [1U] 
                                                 >> 8U)));
            vlSelfRef.tb__DOT__top_module1__DOT__sa_31 
                = (0x000000ffU & (vlSelfRef.tb__DOT__text_in[2U] 
                                  ^ vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                  [1U]));
            vlSelfRef.tb__DOT__top_module1__DOT__sa_02 
                = (0x000000ffU & (((vlSelfRef.tb__DOT__text_in[1U] 
                                    << 8U) | (vlSelfRef.tb__DOT__text_in[1U] 
                                              >> 0x00000018U)) 
                                  ^ (vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                     [2U] >> 0x18U)));
            vlSelfRef.tb__DOT__top_module1__DOT__sa_12 
                = (0x000000ffU & (((vlSelfRef.tb__DOT__text_in[1U] 
                                    << 0x00000010U) 
                                   | (vlSelfRef.tb__DOT__text_in[1U] 
                                      >> 0x00000010U)) 
                                  ^ (vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                     [2U] >> 0x10U)));
            vlSelfRef.tb__DOT__top_module1__DOT__sa_22 
                = (0x000000ffU & (((vlSelfRef.tb__DOT__text_in[1U] 
                                    << 0x00000018U) 
                                   | (vlSelfRef.tb__DOT__text_in[1U] 
                                      >> 8U)) ^ (vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                                 [2U] 
                                                 >> 8U)));
            vlSelfRef.tb__DOT__top_module1__DOT__sa_32 
                = (0x000000ffU & (vlSelfRef.tb__DOT__text_in[1U] 
                                  ^ vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                  [2U]));
            vlSelfRef.tb__DOT__top_module1__DOT__sa_03 
                = (0x000000ffU & (((vlSelfRef.tb__DOT__text_in[0U] 
                                    << 8U) | (vlSelfRef.tb__DOT__text_in[0U] 
                                              >> 0x00000018U)) 
                                  ^ (vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                     [3U] >> 0x18U)));
            vlSelfRef.tb__DOT__top_module1__DOT__sa_13 
                = (0x000000ffU & (((vlSelfRef.tb__DOT__text_in[0U] 
                                    << 0x00000010U) 
                                   | (vlSelfRef.tb__DOT__text_in[0U] 
                                      >> 0x00000010U)) 
                                  ^ (vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                     [3U] >> 0x10U)));
            vlSelfRef.tb__DOT__top_module1__DOT__sa_23 
                = (0x000000ffU & (((vlSelfRef.tb__DOT__text_in[0U] 
                                    << 0x00000018U) 
                                   | (vlSelfRef.tb__DOT__text_in[0U] 
                                      >> 8U)) ^ (vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                                 [3U] 
                                                 >> 8U)));
            vlSelfRef.tb__DOT__top_module1__DOT__sa_33 
                = (0x000000ffU & (vlSelfRef.tb__DOT__text_in[0U] 
                                  ^ vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                  [3U]));
        } else if (((2U == (IData)(vlSelfRef.tb__DOT__top_module1__DOT__next_state)) 
                    | (3U == (IData)(vlSelfRef.tb__DOT__top_module1__DOT__next_state)))) {
            vlSelfRef.__Vdly__tb__DOT__top_module1__DOT__dcnt 
                = (0x0000000fU & ((IData)(vlSelfRef.tb__DOT__top_module1__DOT__dcnt) 
                                  - (IData)(1U)));
            ++(vlSymsp->__Vcoverage[173]);
            vlSelfRef.tb__DOT__top_module1__DOT__sa_00 
                = (vlSelfRef.tb__DOT__top_module1__DOT__add_rkey_out[3U] 
                   >> 0x00000018U);
            vlSelfRef.tb__DOT__top_module1__DOT__sa_10 
                = (0x000000ffU & (vlSelfRef.tb__DOT__top_module1__DOT__add_rkey_out[3U] 
                                  >> 0x00000010U));
            vlSelfRef.tb__DOT__top_module1__DOT__sa_20 
                = (0x000000ffU & (vlSelfRef.tb__DOT__top_module1__DOT__add_rkey_out[3U] 
                                  >> 8U));
            vlSelfRef.tb__DOT__top_module1__DOT__sa_30 
                = (0x000000ffU & vlSelfRef.tb__DOT__top_module1__DOT__add_rkey_out[3U]);
            vlSelfRef.tb__DOT__top_module1__DOT__sa_01 
                = (vlSelfRef.tb__DOT__top_module1__DOT__add_rkey_out[2U] 
                   >> 0x00000018U);
            vlSelfRef.tb__DOT__top_module1__DOT__sa_11 
                = (0x000000ffU & (vlSelfRef.tb__DOT__top_module1__DOT__add_rkey_out[2U] 
                                  >> 0x00000010U));
            vlSelfRef.tb__DOT__top_module1__DOT__sa_21 
                = (0x000000ffU & (vlSelfRef.tb__DOT__top_module1__DOT__add_rkey_out[2U] 
                                  >> 8U));
            vlSelfRef.tb__DOT__top_module1__DOT__sa_31 
                = (0x000000ffU & vlSelfRef.tb__DOT__top_module1__DOT__add_rkey_out[2U]);
            vlSelfRef.tb__DOT__top_module1__DOT__sa_02 
                = (vlSelfRef.tb__DOT__top_module1__DOT__add_rkey_out[1U] 
                   >> 0x00000018U);
            vlSelfRef.tb__DOT__top_module1__DOT__sa_12 
                = (0x000000ffU & (vlSelfRef.tb__DOT__top_module1__DOT__add_rkey_out[1U] 
                                  >> 0x00000010U));
            vlSelfRef.tb__DOT__top_module1__DOT__sa_22 
                = (0x000000ffU & (vlSelfRef.tb__DOT__top_module1__DOT__add_rkey_out[1U] 
                                  >> 8U));
            vlSelfRef.tb__DOT__top_module1__DOT__sa_32 
                = (0x000000ffU & vlSelfRef.tb__DOT__top_module1__DOT__add_rkey_out[1U]);
            vlSelfRef.tb__DOT__top_module1__DOT__sa_03 
                = (vlSelfRef.tb__DOT__top_module1__DOT__add_rkey_out[0U] 
                   >> 0x00000018U);
            vlSelfRef.tb__DOT__top_module1__DOT__sa_13 
                = (0x000000ffU & (vlSelfRef.tb__DOT__top_module1__DOT__add_rkey_out[0U] 
                                  >> 0x00000010U));
            vlSelfRef.tb__DOT__top_module1__DOT__sa_23 
                = (0x000000ffU & (vlSelfRef.tb__DOT__top_module1__DOT__add_rkey_out[0U] 
                                  >> 8U));
            vlSelfRef.tb__DOT__top_module1__DOT__sa_33 
                = (0x000000ffU & vlSelfRef.tb__DOT__top_module1__DOT__add_rkey_out[0U]);
        } else {
            ++(vlSymsp->__Vcoverage[174]);
        }
        vlSelfRef.tb__DOT__top_module1__DOT__state 
            = vlSelfRef.tb__DOT__top_module1__DOT__next_state;
        if ((3U == (IData)(vlSelfRef.tb__DOT__top_module1__DOT__next_state))) {
            ++(vlSymsp->__Vcoverage[176]);
            vlSelfRef.tb__DOT__top_module1__DOT__text_out_r[0U] 
                = vlSelfRef.tb__DOT__top_module1__DOT__add_rkey_out[0U];
            vlSelfRef.tb__DOT__top_module1__DOT__text_out_r[1U] 
                = vlSelfRef.tb__DOT__top_module1__DOT__add_rkey_out[1U];
            vlSelfRef.tb__DOT__top_module1__DOT__text_out_r[2U] 
                = vlSelfRef.tb__DOT__top_module1__DOT__add_rkey_out[2U];
            vlSelfRef.tb__DOT__top_module1__DOT__text_out_r[3U] 
                = vlSelfRef.tb__DOT__top_module1__DOT__add_rkey_out[3U];
        } else {
            ++(vlSymsp->__Vcoverage[177]);
        }
        ++(vlSymsp->__Vcoverage[179]);
    } else {
        ++(vlSymsp->__Vcoverage[178]);
        vlSelfRef.tb__DOT__top_module1__DOT__state = 0U;
        vlSelfRef.__Vdly__tb__DOT__top_module1__DOT__dcnt = 0U;
        vlSelfRef.__Vdly__tb__DOT__top_module1__DOT__kld = 0U;
        vlSelfRef.__Vdly__tb__DOT__top_module1__DOT__ld_cap = 0U;
        vlSelfRef.tb__DOT__top_module1__DOT__text_out_r[0U] = 0U;
        vlSelfRef.tb__DOT__top_module1__DOT__text_out_r[1U] = 0U;
        vlSelfRef.tb__DOT__top_module1__DOT__text_out_r[2U] = 0U;
        vlSelfRef.tb__DOT__top_module1__DOT__text_out_r[3U] = 0U;
        vlSelfRef.tb__DOT__top_module1__DOT__sa_00 = 0U;
        vlSelfRef.tb__DOT__top_module1__DOT__sa_01 = 0U;
        vlSelfRef.tb__DOT__top_module1__DOT__sa_02 = 0U;
        vlSelfRef.tb__DOT__top_module1__DOT__sa_03 = 0U;
        vlSelfRef.tb__DOT__top_module1__DOT__sa_10 = 0U;
        vlSelfRef.tb__DOT__top_module1__DOT__sa_11 = 0U;
        vlSelfRef.tb__DOT__top_module1__DOT__sa_12 = 0U;
        vlSelfRef.tb__DOT__top_module1__DOT__sa_13 = 0U;
        vlSelfRef.tb__DOT__top_module1__DOT__sa_20 = 0U;
        vlSelfRef.tb__DOT__top_module1__DOT__sa_21 = 0U;
        vlSelfRef.tb__DOT__top_module1__DOT__sa_22 = 0U;
        vlSelfRef.tb__DOT__top_module1__DOT__sa_23 = 0U;
        vlSelfRef.tb__DOT__top_module1__DOT__sa_30 = 0U;
        vlSelfRef.tb__DOT__top_module1__DOT__sa_31 = 0U;
        vlSelfRef.tb__DOT__top_module1__DOT__sa_32 = 0U;
        vlSelfRef.tb__DOT__top_module1__DOT__sa_33 = 0U;
    }
    ++(vlSymsp->__Vcoverage[180]);
    if (vlSelfRef.__VdlySet__tb__DOT__good1__DOT__u0__DOT__w__v0) {
        vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w[0U] 
            = vlSelfRef.__VdlyVal__tb__DOT__good1__DOT__u0__DOT__w__v0;
    }
    if (vlSelfRef.__VdlySet__tb__DOT__good1__DOT__u0__DOT__w__v1) {
        vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w[1U] 
            = vlSelfRef.__VdlyVal__tb__DOT__good1__DOT__u0__DOT__w__v1;
    }
    if (vlSelfRef.__VdlySet__tb__DOT__good1__DOT__u0__DOT__w__v2) {
        vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w[2U] 
            = vlSelfRef.__VdlyVal__tb__DOT__good1__DOT__u0__DOT__w__v2;
    }
    if (vlSelfRef.__VdlySet__tb__DOT__good1__DOT__u0__DOT__w__v3) {
        vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w[3U] 
            = vlSelfRef.__VdlyVal__tb__DOT__good1__DOT__u0__DOT__w__v3;
    }
    vlSelfRef.tb__DOT__top_module1__DOT__dcnt = vlSelfRef.__Vdly__tb__DOT__top_module1__DOT__dcnt;
    if (vlSelfRef.__VdlySet__tb__DOT__top_module1__DOT__u_key_expand__DOT__w__v0) {
        vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w[0U] 
            = vlSelfRef.__VdlyVal__tb__DOT__top_module1__DOT__u_key_expand__DOT__w__v0;
    }
    if (vlSelfRef.__VdlySet__tb__DOT__top_module1__DOT__u_key_expand__DOT__w__v1) {
        vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w[1U] 
            = vlSelfRef.__VdlyVal__tb__DOT__top_module1__DOT__u_key_expand__DOT__w__v1;
    }
    if (vlSelfRef.__VdlySet__tb__DOT__top_module1__DOT__u_key_expand__DOT__w__v2) {
        vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w[2U] 
            = vlSelfRef.__VdlyVal__tb__DOT__top_module1__DOT__u_key_expand__DOT__w__v2;
    }
    if (vlSelfRef.__VdlySet__tb__DOT__top_module1__DOT__u_key_expand__DOT__w__v3) {
        vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w[3U] 
            = vlSelfRef.__VdlyVal__tb__DOT__top_module1__DOT__u_key_expand__DOT__w__v3;
    }
    vlSelfRef.tb__DOT__top_module1__DOT__kld = vlSelfRef.__Vdly__tb__DOT__top_module1__DOT__kld;
    vlSelfRef.tb__DOT__good1__DOT__ld_r = vlSelfRef.tb__DOT__ld;
    if (vlSelfRef.tb__DOT__ld) {
        ++(vlSymsp->__Vcoverage[49]);
        vlSelfRef.tb__DOT__good1__DOT__text_in_r[0U] 
            = vlSelfRef.tb__DOT__text_in[0U];
        vlSelfRef.tb__DOT__good1__DOT__text_in_r[1U] 
            = vlSelfRef.tb__DOT__text_in[1U];
        vlSelfRef.tb__DOT__good1__DOT__text_in_r[2U] 
            = vlSelfRef.tb__DOT__text_in[2U];
        vlSelfRef.tb__DOT__good1__DOT__text_in_r[3U] 
            = vlSelfRef.tb__DOT__text_in[3U];
    } else {
        ++(vlSymsp->__Vcoverage[50]);
    }
    ++(vlSymsp->__Vcoverage[51]);
    vlSelfRef.tb__DOT__tb_match_text = (0U == ((((vlSelfRef.tb__DOT__text_out_ref[0U] 
                                                  ^ 
                                                  vlSelfRef.tb__DOT__top_module1__DOT__text_out_r[0U]) 
                                                 | (vlSelfRef.tb__DOT__text_out_ref[1U] 
                                                    ^ 
                                                    vlSelfRef.tb__DOT__top_module1__DOT__text_out_r[1U])) 
                                                | (vlSelfRef.tb__DOT__text_out_ref[2U] 
                                                   ^ 
                                                   vlSelfRef.tb__DOT__top_module1__DOT__text_out_r[2U])) 
                                               | (vlSelfRef.tb__DOT__text_out_ref[3U] 
                                                  ^ 
                                                  vlSelfRef.tb__DOT__top_module1__DOT__text_out_r[3U])));
    vlSelfRef.tb__DOT__tb_match_done = ((4U == (IData)(vlSelfRef.tb__DOT__top_module1__DOT__state)) 
                                        == (IData)(vlSelfRef.tb__DOT__done_ref));
}

void Vtb___024root___nba_comb__TOP__2(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___nba_comb__TOP__2\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb__DOT__top_module1__DOT__mc_03 = ((
                                                   (([&]() {
                        vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__66__x 
                            = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_03.b;
                        vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__66__Vfuncout 
                            = (0x000000ffU & (((0x00000080U 
                                                & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__66__x))
                                                ? 0x1bU
                                                : 0U) 
                                              ^ VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__66__x), 1U)));
                        ++(vlSymsp->__Vcoverage[153]);
                    }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__66__Vfuncout)) 
                                                    ^ 
                                                    (([&]() {
                            vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__67__x 
                                = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_10.b;
                            vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__67__Vfuncout 
                                = (0x000000ffU & ((
                                                   (0x00000080U 
                                                    & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__67__x))
                                                    ? 0x1bU
                                                    : 0U) 
                                                  ^ 
                                                  VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__67__x), 1U)));
                            ++(vlSymsp->__Vcoverage[153]);
                        }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__67__Vfuncout)) 
                                                     ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_10.b))) 
                                                   ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_21.b)) 
                                                  ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_32.b));
    vlSelfRef.tb__DOT__top_module1__DOT__mc_13 = ((
                                                   ((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_03.b) 
                                                    ^ 
                                                    ([&]() {
                        vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__68__x 
                            = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_10.b;
                        vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__68__Vfuncout 
                            = (0x000000ffU & (((0x00000080U 
                                                & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__68__x))
                                                ? 0x1bU
                                                : 0U) 
                                              ^ VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__68__x), 1U)));
                        ++(vlSymsp->__Vcoverage[153]);
                    }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__68__Vfuncout))) 
                                                   ^ 
                                                   (([&]() {
                        vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__69__x 
                            = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_21.b;
                        vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__69__Vfuncout 
                            = (0x000000ffU & (((0x00000080U 
                                                & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__69__x))
                                                ? 0x1bU
                                                : 0U) 
                                              ^ VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__69__x), 1U)));
                        ++(vlSymsp->__Vcoverage[153]);
                    }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__69__Vfuncout)) 
                                                    ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_21.b))) 
                                                  ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_32.b));
    vlSelfRef.tb__DOT__top_module1__DOT__mc_23 = ((
                                                   ((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_03.b) 
                                                    ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_10.b)) 
                                                   ^ 
                                                   ([&]() {
                    vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__70__x 
                        = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_21.b;
                    vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__70__Vfuncout 
                        = (0x000000ffU & (((0x00000080U 
                                            & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__70__x))
                                            ? 0x1bU
                                            : 0U) ^ 
                                          VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__70__x), 1U)));
                    ++(vlSymsp->__Vcoverage[153]);
                }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__70__Vfuncout))) 
                                                  ^ 
                                                  (([&]() {
                    vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__71__x 
                        = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_32.b;
                    vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__71__Vfuncout 
                        = (0x000000ffU & (((0x00000080U 
                                            & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__71__x))
                                            ? 0x1bU
                                            : 0U) ^ 
                                          VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__71__x), 1U)));
                    ++(vlSymsp->__Vcoverage[153]);
                }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__71__Vfuncout)) 
                                                   ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_32.b)));
    vlSelfRef.tb__DOT__top_module1__DOT__mc_33 = ((
                                                   ((([&]() {
                            vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__72__x 
                                = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_03.b;
                            vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__72__Vfuncout 
                                = (0x000000ffU & ((
                                                   (0x00000080U 
                                                    & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__72__x))
                                                    ? 0x1bU
                                                    : 0U) 
                                                  ^ 
                                                  VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__72__x), 1U)));
                            ++(vlSymsp->__Vcoverage[153]);
                        }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__72__Vfuncout)) 
                                                     ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_03.b)) 
                                                    ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_10.b)) 
                                                   ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_21.b)) 
                                                  ^ 
                                                  ([&]() {
                vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__73__x 
                    = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_32.b;
                vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__73__Vfuncout 
                    = (0x000000ffU & (((0x00000080U 
                                        & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__73__x))
                                        ? 0x1bU : 0U) 
                                      ^ VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__73__x), 1U)));
                ++(vlSymsp->__Vcoverage[153]);
            }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__73__Vfuncout)));
}

void Vtb___024root___nba_comb__TOP__3(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___nba_comb__TOP__3\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb__DOT__top_module1__DOT__mc_02 = ((
                                                   (([&]() {
                        vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__58__x 
                            = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_02.b;
                        vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__58__Vfuncout 
                            = (0x000000ffU & (((0x00000080U 
                                                & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__58__x))
                                                ? 0x1bU
                                                : 0U) 
                                              ^ VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__58__x), 1U)));
                        ++(vlSymsp->__Vcoverage[153]);
                    }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__58__Vfuncout)) 
                                                    ^ 
                                                    (([&]() {
                            vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__59__x 
                                = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_13.b;
                            vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__59__Vfuncout 
                                = (0x000000ffU & ((
                                                   (0x00000080U 
                                                    & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__59__x))
                                                    ? 0x1bU
                                                    : 0U) 
                                                  ^ 
                                                  VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__59__x), 1U)));
                            ++(vlSymsp->__Vcoverage[153]);
                        }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__59__Vfuncout)) 
                                                     ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_13.b))) 
                                                   ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_20.b)) 
                                                  ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_31.b));
    vlSelfRef.tb__DOT__top_module1__DOT__mc_12 = ((
                                                   ((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_02.b) 
                                                    ^ 
                                                    ([&]() {
                        vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__60__x 
                            = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_13.b;
                        vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__60__Vfuncout 
                            = (0x000000ffU & (((0x00000080U 
                                                & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__60__x))
                                                ? 0x1bU
                                                : 0U) 
                                              ^ VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__60__x), 1U)));
                        ++(vlSymsp->__Vcoverage[153]);
                    }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__60__Vfuncout))) 
                                                   ^ 
                                                   (([&]() {
                        vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__61__x 
                            = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_20.b;
                        vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__61__Vfuncout 
                            = (0x000000ffU & (((0x00000080U 
                                                & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__61__x))
                                                ? 0x1bU
                                                : 0U) 
                                              ^ VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__61__x), 1U)));
                        ++(vlSymsp->__Vcoverage[153]);
                    }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__61__Vfuncout)) 
                                                    ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_20.b))) 
                                                  ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_31.b));
    vlSelfRef.tb__DOT__top_module1__DOT__mc_22 = ((
                                                   ((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_02.b) 
                                                    ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_13.b)) 
                                                   ^ 
                                                   ([&]() {
                    vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__62__x 
                        = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_20.b;
                    vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__62__Vfuncout 
                        = (0x000000ffU & (((0x00000080U 
                                            & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__62__x))
                                            ? 0x1bU
                                            : 0U) ^ 
                                          VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__62__x), 1U)));
                    ++(vlSymsp->__Vcoverage[153]);
                }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__62__Vfuncout))) 
                                                  ^ 
                                                  (([&]() {
                    vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__63__x 
                        = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_31.b;
                    vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__63__Vfuncout 
                        = (0x000000ffU & (((0x00000080U 
                                            & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__63__x))
                                            ? 0x1bU
                                            : 0U) ^ 
                                          VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__63__x), 1U)));
                    ++(vlSymsp->__Vcoverage[153]);
                }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__63__Vfuncout)) 
                                                   ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_31.b)));
    vlSelfRef.tb__DOT__top_module1__DOT__mc_32 = ((
                                                   ((([&]() {
                            vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__64__x 
                                = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_02.b;
                            vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__64__Vfuncout 
                                = (0x000000ffU & ((
                                                   (0x00000080U 
                                                    & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__64__x))
                                                    ? 0x1bU
                                                    : 0U) 
                                                  ^ 
                                                  VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__64__x), 1U)));
                            ++(vlSymsp->__Vcoverage[153]);
                        }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__64__Vfuncout)) 
                                                     ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_02.b)) 
                                                    ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_13.b)) 
                                                   ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_20.b)) 
                                                  ^ 
                                                  ([&]() {
                vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__65__x 
                    = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_31.b;
                vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__65__Vfuncout 
                    = (0x000000ffU & (((0x00000080U 
                                        & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__65__x))
                                        ? 0x1bU : 0U) 
                                      ^ VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__65__x), 1U)));
                ++(vlSymsp->__Vcoverage[153]);
            }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__65__Vfuncout)));
}

void Vtb___024root___nba_comb__TOP__4(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___nba_comb__TOP__4\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb__DOT__top_module1__DOT__mc_01 = ((
                                                   (([&]() {
                        vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__50__x 
                            = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_01.b;
                        vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__50__Vfuncout 
                            = (0x000000ffU & (((0x00000080U 
                                                & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__50__x))
                                                ? 0x1bU
                                                : 0U) 
                                              ^ VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__50__x), 1U)));
                        ++(vlSymsp->__Vcoverage[153]);
                    }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__50__Vfuncout)) 
                                                    ^ 
                                                    (([&]() {
                            vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__51__x 
                                = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_12.b;
                            vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__51__Vfuncout 
                                = (0x000000ffU & ((
                                                   (0x00000080U 
                                                    & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__51__x))
                                                    ? 0x1bU
                                                    : 0U) 
                                                  ^ 
                                                  VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__51__x), 1U)));
                            ++(vlSymsp->__Vcoverage[153]);
                        }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__51__Vfuncout)) 
                                                     ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_12.b))) 
                                                   ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_23.b)) 
                                                  ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_30.b));
    vlSelfRef.tb__DOT__top_module1__DOT__mc_11 = ((
                                                   ((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_01.b) 
                                                    ^ 
                                                    ([&]() {
                        vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__52__x 
                            = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_12.b;
                        vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__52__Vfuncout 
                            = (0x000000ffU & (((0x00000080U 
                                                & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__52__x))
                                                ? 0x1bU
                                                : 0U) 
                                              ^ VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__52__x), 1U)));
                        ++(vlSymsp->__Vcoverage[153]);
                    }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__52__Vfuncout))) 
                                                   ^ 
                                                   (([&]() {
                        vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__53__x 
                            = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_23.b;
                        vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__53__Vfuncout 
                            = (0x000000ffU & (((0x00000080U 
                                                & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__53__x))
                                                ? 0x1bU
                                                : 0U) 
                                              ^ VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__53__x), 1U)));
                        ++(vlSymsp->__Vcoverage[153]);
                    }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__53__Vfuncout)) 
                                                    ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_23.b))) 
                                                  ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_30.b));
    vlSelfRef.tb__DOT__top_module1__DOT__mc_21 = ((
                                                   ((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_01.b) 
                                                    ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_12.b)) 
                                                   ^ 
                                                   ([&]() {
                    vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__54__x 
                        = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_23.b;
                    vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__54__Vfuncout 
                        = (0x000000ffU & (((0x00000080U 
                                            & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__54__x))
                                            ? 0x1bU
                                            : 0U) ^ 
                                          VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__54__x), 1U)));
                    ++(vlSymsp->__Vcoverage[153]);
                }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__54__Vfuncout))) 
                                                  ^ 
                                                  (([&]() {
                    vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__55__x 
                        = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_30.b;
                    vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__55__Vfuncout 
                        = (0x000000ffU & (((0x00000080U 
                                            & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__55__x))
                                            ? 0x1bU
                                            : 0U) ^ 
                                          VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__55__x), 1U)));
                    ++(vlSymsp->__Vcoverage[153]);
                }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__55__Vfuncout)) 
                                                   ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_30.b)));
    vlSelfRef.tb__DOT__top_module1__DOT__mc_31 = ((
                                                   ((([&]() {
                            vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__56__x 
                                = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_01.b;
                            vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__56__Vfuncout 
                                = (0x000000ffU & ((
                                                   (0x00000080U 
                                                    & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__56__x))
                                                    ? 0x1bU
                                                    : 0U) 
                                                  ^ 
                                                  VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__56__x), 1U)));
                            ++(vlSymsp->__Vcoverage[153]);
                        }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__56__Vfuncout)) 
                                                     ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_01.b)) 
                                                    ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_12.b)) 
                                                   ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_23.b)) 
                                                  ^ 
                                                  ([&]() {
                vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__57__x 
                    = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_30.b;
                vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__57__Vfuncout 
                    = (0x000000ffU & (((0x00000080U 
                                        & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__57__x))
                                        ? 0x1bU : 0U) 
                                      ^ VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__57__x), 1U)));
                ++(vlSymsp->__Vcoverage[153]);
            }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__57__Vfuncout)));
}

void Vtb___024root___nba_comb__TOP__5(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___nba_comb__TOP__5\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb__DOT__top_module1__DOT__mc_00 = ((
                                                   (([&]() {
                        vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__42__x 
                            = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_00.b;
                        vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__42__Vfuncout 
                            = (0x000000ffU & (((0x00000080U 
                                                & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__42__x))
                                                ? 0x1bU
                                                : 0U) 
                                              ^ VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__42__x), 1U)));
                        ++(vlSymsp->__Vcoverage[153]);
                    }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__42__Vfuncout)) 
                                                    ^ 
                                                    (([&]() {
                            vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__43__x 
                                = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_11.b;
                            vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__43__Vfuncout 
                                = (0x000000ffU & ((
                                                   (0x00000080U 
                                                    & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__43__x))
                                                    ? 0x1bU
                                                    : 0U) 
                                                  ^ 
                                                  VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__43__x), 1U)));
                            ++(vlSymsp->__Vcoverage[153]);
                        }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__43__Vfuncout)) 
                                                     ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_11.b))) 
                                                   ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_22.b)) 
                                                  ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_33.b));
    vlSelfRef.tb__DOT__top_module1__DOT__mc_10 = ((
                                                   ((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_00.b) 
                                                    ^ 
                                                    ([&]() {
                        vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__44__x 
                            = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_11.b;
                        vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__44__Vfuncout 
                            = (0x000000ffU & (((0x00000080U 
                                                & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__44__x))
                                                ? 0x1bU
                                                : 0U) 
                                              ^ VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__44__x), 1U)));
                        ++(vlSymsp->__Vcoverage[153]);
                    }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__44__Vfuncout))) 
                                                   ^ 
                                                   (([&]() {
                        vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__45__x 
                            = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_22.b;
                        vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__45__Vfuncout 
                            = (0x000000ffU & (((0x00000080U 
                                                & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__45__x))
                                                ? 0x1bU
                                                : 0U) 
                                              ^ VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__45__x), 1U)));
                        ++(vlSymsp->__Vcoverage[153]);
                    }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__45__Vfuncout)) 
                                                    ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_22.b))) 
                                                  ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_33.b));
    vlSelfRef.tb__DOT__top_module1__DOT__mc_20 = ((
                                                   ((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_00.b) 
                                                    ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_11.b)) 
                                                   ^ 
                                                   ([&]() {
                    vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__46__x 
                        = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_22.b;
                    vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__46__Vfuncout 
                        = (0x000000ffU & (((0x00000080U 
                                            & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__46__x))
                                            ? 0x1bU
                                            : 0U) ^ 
                                          VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__46__x), 1U)));
                    ++(vlSymsp->__Vcoverage[153]);
                }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__46__Vfuncout))) 
                                                  ^ 
                                                  (([&]() {
                    vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__47__x 
                        = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_33.b;
                    vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__47__Vfuncout 
                        = (0x000000ffU & (((0x00000080U 
                                            & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__47__x))
                                            ? 0x1bU
                                            : 0U) ^ 
                                          VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__47__x), 1U)));
                    ++(vlSymsp->__Vcoverage[153]);
                }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__47__Vfuncout)) 
                                                   ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_33.b)));
    vlSelfRef.tb__DOT__top_module1__DOT__mc_30 = ((
                                                   ((([&]() {
                            vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__48__x 
                                = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_00.b;
                            vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__48__Vfuncout 
                                = (0x000000ffU & ((
                                                   (0x00000080U 
                                                    & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__48__x))
                                                    ? 0x1bU
                                                    : 0U) 
                                                  ^ 
                                                  VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__48__x), 1U)));
                            ++(vlSymsp->__Vcoverage[153]);
                        }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__48__Vfuncout)) 
                                                     ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_00.b)) 
                                                    ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_11.b)) 
                                                   ^ (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_22.b)) 
                                                  ^ 
                                                  ([&]() {
                vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__49__x 
                    = vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_33.b;
                vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__49__Vfuncout 
                    = (0x000000ffU & (((0x00000080U 
                                        & (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__49__x))
                                        ? 0x1bU : 0U) 
                                      ^ VL_SHIFTL_III(8,8,32, (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__49__x), 1U)));
                ++(vlSymsp->__Vcoverage[153]);
            }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__top_module1__DOT__xtime__49__Vfuncout)));
}

void Vtb___024root___nba_comb__TOP__6(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___nba_comb__TOP__6\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    CData/*7:0*/ __Vfunc_tb__DOT__good1__DOT__mix_col__5__s0;
    __Vfunc_tb__DOT__good1__DOT__mix_col__5__s0 = 0;
    CData/*7:0*/ __Vfunc_tb__DOT__good1__DOT__mix_col__5__s1;
    __Vfunc_tb__DOT__good1__DOT__mix_col__5__s1 = 0;
    CData/*7:0*/ __Vfunc_tb__DOT__good1__DOT__mix_col__5__s2;
    __Vfunc_tb__DOT__good1__DOT__mix_col__5__s2 = 0;
    CData/*7:0*/ __Vfunc_tb__DOT__good1__DOT__mix_col__5__s3;
    __Vfunc_tb__DOT__good1__DOT__mix_col__5__s3 = 0;
    // Body
    __Vfunc_tb__DOT__good1__DOT__mix_col__5__s3 = vlSymsp->TOP__tb__DOT__good1__DOT__us33.b;
    __Vfunc_tb__DOT__good1__DOT__mix_col__5__s2 = vlSymsp->TOP__tb__DOT__good1__DOT__us22.b;
    __Vfunc_tb__DOT__good1__DOT__mix_col__5__s1 = vlSymsp->TOP__tb__DOT__good1__DOT__us11.b;
    __Vfunc_tb__DOT__good1__DOT__mix_col__5__s0 = vlSymsp->TOP__tb__DOT__good1__DOT__us00.b;
    VL_ASSIGNSEL_II(32, 8, 0x18U, vlSelfRef.__Vfunc_tb__DOT__good1__DOT__mix_col__5__Vfuncout, 
                    ((((([&]() {
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__6__b 
                                    = __Vfunc_tb__DOT__good1__DOT__mix_col__5__s0;
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__6__Vfuncout 
                                    = ((0x000000feU 
                                        & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__6__b) 
                                           << 1U)) 
                                       ^ (0x1bU & (- (IData)(
                                                             (1U 
                                                              & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__6__b) 
                                                                 >> 7U))))));
                                ++(vlSymsp->__Vcoverage[118]);
                            }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__6__Vfuncout)) 
                        ^ ([&]() {
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__7__b 
                                    = __Vfunc_tb__DOT__good1__DOT__mix_col__5__s1;
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__7__Vfuncout 
                                    = ((0x000000feU 
                                        & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__7__b) 
                                           << 1U)) 
                                       ^ (0x1bU & (- (IData)(
                                                             (1U 
                                                              & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__7__b) 
                                                                 >> 7U))))));
                                ++(vlSymsp->__Vcoverage[118]);
                            }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__7__Vfuncout))) 
                       ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__5__s1)) 
                      ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__5__s2)) 
                     ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__5__s3)));
    VL_ASSIGNSEL_II(32, 8, 0x10U, vlSelfRef.__Vfunc_tb__DOT__good1__DOT__mix_col__5__Vfuncout, 
                    (((((IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__5__s0) 
                        ^ ([&]() {
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__8__b 
                                    = __Vfunc_tb__DOT__good1__DOT__mix_col__5__s1;
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__8__Vfuncout 
                                    = ((0x000000feU 
                                        & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__8__b) 
                                           << 1U)) 
                                       ^ (0x1bU & (- (IData)(
                                                             (1U 
                                                              & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__8__b) 
                                                                 >> 7U))))));
                                ++(vlSymsp->__Vcoverage[118]);
                            }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__8__Vfuncout))) 
                       ^ ([&]() {
                            vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__9__b 
                                = __Vfunc_tb__DOT__good1__DOT__mix_col__5__s2;
                            vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__9__Vfuncout 
                                = ((0x000000feU & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__9__b) 
                                                   << 1U)) 
                                   ^ (0x1bU & (- (IData)(
                                                         (1U 
                                                          & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__9__b) 
                                                             >> 7U))))));
                            ++(vlSymsp->__Vcoverage[118]);
                        }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__9__Vfuncout))) 
                      ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__5__s2)) 
                     ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__5__s3)));
    VL_ASSIGNSEL_II(32, 8, 8U, vlSelfRef.__Vfunc_tb__DOT__good1__DOT__mix_col__5__Vfuncout, 
                    (((((IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__5__s0) 
                        ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__5__s1)) 
                       ^ ([&]() {
                            vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__10__b 
                                = __Vfunc_tb__DOT__good1__DOT__mix_col__5__s2;
                            vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__10__Vfuncout 
                                = ((0x000000feU & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__10__b) 
                                                   << 1U)) 
                                   ^ (0x1bU & (- (IData)(
                                                         (1U 
                                                          & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__10__b) 
                                                             >> 7U))))));
                            ++(vlSymsp->__Vcoverage[118]);
                        }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__10__Vfuncout))) 
                      ^ ([&]() {
                        vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__11__b 
                            = __Vfunc_tb__DOT__good1__DOT__mix_col__5__s3;
                        vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__11__Vfuncout 
                            = ((0x000000feU & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__11__b) 
                                               << 1U)) 
                               ^ (0x1bU & (- (IData)(
                                                     (1U 
                                                      & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__11__b) 
                                                         >> 7U))))));
                        ++(vlSymsp->__Vcoverage[118]);
                    }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__11__Vfuncout))) 
                     ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__5__s3)));
    VL_ASSIGNSEL_II(32, 8, 0U, vlSelfRef.__Vfunc_tb__DOT__good1__DOT__mix_col__5__Vfuncout, 
                    ((((([&]() {
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__12__b 
                                    = __Vfunc_tb__DOT__good1__DOT__mix_col__5__s0;
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__12__Vfuncout 
                                    = ((0x000000feU 
                                        & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__12__b) 
                                           << 1U)) 
                                       ^ (0x1bU & (- (IData)(
                                                             (1U 
                                                              & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__12__b) 
                                                                 >> 7U))))));
                                ++(vlSymsp->__Vcoverage[118]);
                            }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__12__Vfuncout)) 
                        ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__5__s0)) 
                       ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__5__s1)) 
                      ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__5__s2)) 
                     ^ ([&]() {
                    vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__13__b 
                        = __Vfunc_tb__DOT__good1__DOT__mix_col__5__s3;
                    vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__13__Vfuncout 
                        = ((0x000000feU & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__13__b) 
                                           << 1U)) 
                           ^ (0x1bU & (- (IData)((1U 
                                                  & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__13__b) 
                                                     >> 7U))))));
                    ++(vlSymsp->__Vcoverage[118]);
                }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__13__Vfuncout))));
    ++(vlSymsp->__Vcoverage[117]);
    vlSelfRef.tb__DOT__good1__DOT__mix_col_out0 = vlSelfRef.__Vfunc_tb__DOT__good1__DOT__mix_col__5__Vfuncout;
}

void Vtb___024root___nba_comb__TOP__7(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___nba_comb__TOP__7\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    CData/*7:0*/ __Vfunc_tb__DOT__good1__DOT__mix_col__14__s0;
    __Vfunc_tb__DOT__good1__DOT__mix_col__14__s0 = 0;
    CData/*7:0*/ __Vfunc_tb__DOT__good1__DOT__mix_col__14__s1;
    __Vfunc_tb__DOT__good1__DOT__mix_col__14__s1 = 0;
    CData/*7:0*/ __Vfunc_tb__DOT__good1__DOT__mix_col__14__s2;
    __Vfunc_tb__DOT__good1__DOT__mix_col__14__s2 = 0;
    CData/*7:0*/ __Vfunc_tb__DOT__good1__DOT__mix_col__14__s3;
    __Vfunc_tb__DOT__good1__DOT__mix_col__14__s3 = 0;
    // Body
    __Vfunc_tb__DOT__good1__DOT__mix_col__14__s3 = vlSymsp->TOP__tb__DOT__good1__DOT__us30.b;
    __Vfunc_tb__DOT__good1__DOT__mix_col__14__s2 = vlSymsp->TOP__tb__DOT__good1__DOT__us23.b;
    __Vfunc_tb__DOT__good1__DOT__mix_col__14__s1 = vlSymsp->TOP__tb__DOT__good1__DOT__us12.b;
    __Vfunc_tb__DOT__good1__DOT__mix_col__14__s0 = vlSymsp->TOP__tb__DOT__good1__DOT__us01.b;
    VL_ASSIGNSEL_II(32, 8, 0x18U, vlSelfRef.__Vfunc_tb__DOT__good1__DOT__mix_col__14__Vfuncout, 
                    ((((([&]() {
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__15__b 
                                    = __Vfunc_tb__DOT__good1__DOT__mix_col__14__s0;
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__15__Vfuncout 
                                    = ((0x000000feU 
                                        & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__15__b) 
                                           << 1U)) 
                                       ^ (0x1bU & (- (IData)(
                                                             (1U 
                                                              & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__15__b) 
                                                                 >> 7U))))));
                                ++(vlSymsp->__Vcoverage[118]);
                            }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__15__Vfuncout)) 
                        ^ ([&]() {
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__16__b 
                                    = __Vfunc_tb__DOT__good1__DOT__mix_col__14__s1;
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__16__Vfuncout 
                                    = ((0x000000feU 
                                        & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__16__b) 
                                           << 1U)) 
                                       ^ (0x1bU & (- (IData)(
                                                             (1U 
                                                              & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__16__b) 
                                                                 >> 7U))))));
                                ++(vlSymsp->__Vcoverage[118]);
                            }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__16__Vfuncout))) 
                       ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__14__s1)) 
                      ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__14__s2)) 
                     ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__14__s3)));
    VL_ASSIGNSEL_II(32, 8, 0x10U, vlSelfRef.__Vfunc_tb__DOT__good1__DOT__mix_col__14__Vfuncout, 
                    (((((IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__14__s0) 
                        ^ ([&]() {
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__17__b 
                                    = __Vfunc_tb__DOT__good1__DOT__mix_col__14__s1;
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__17__Vfuncout 
                                    = ((0x000000feU 
                                        & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__17__b) 
                                           << 1U)) 
                                       ^ (0x1bU & (- (IData)(
                                                             (1U 
                                                              & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__17__b) 
                                                                 >> 7U))))));
                                ++(vlSymsp->__Vcoverage[118]);
                            }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__17__Vfuncout))) 
                       ^ ([&]() {
                            vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__18__b 
                                = __Vfunc_tb__DOT__good1__DOT__mix_col__14__s2;
                            vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__18__Vfuncout 
                                = ((0x000000feU & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__18__b) 
                                                   << 1U)) 
                                   ^ (0x1bU & (- (IData)(
                                                         (1U 
                                                          & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__18__b) 
                                                             >> 7U))))));
                            ++(vlSymsp->__Vcoverage[118]);
                        }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__18__Vfuncout))) 
                      ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__14__s2)) 
                     ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__14__s3)));
    VL_ASSIGNSEL_II(32, 8, 8U, vlSelfRef.__Vfunc_tb__DOT__good1__DOT__mix_col__14__Vfuncout, 
                    (((((IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__14__s0) 
                        ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__14__s1)) 
                       ^ ([&]() {
                            vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__19__b 
                                = __Vfunc_tb__DOT__good1__DOT__mix_col__14__s2;
                            vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__19__Vfuncout 
                                = ((0x000000feU & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__19__b) 
                                                   << 1U)) 
                                   ^ (0x1bU & (- (IData)(
                                                         (1U 
                                                          & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__19__b) 
                                                             >> 7U))))));
                            ++(vlSymsp->__Vcoverage[118]);
                        }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__19__Vfuncout))) 
                      ^ ([&]() {
                        vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__20__b 
                            = __Vfunc_tb__DOT__good1__DOT__mix_col__14__s3;
                        vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__20__Vfuncout 
                            = ((0x000000feU & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__20__b) 
                                               << 1U)) 
                               ^ (0x1bU & (- (IData)(
                                                     (1U 
                                                      & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__20__b) 
                                                         >> 7U))))));
                        ++(vlSymsp->__Vcoverage[118]);
                    }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__20__Vfuncout))) 
                     ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__14__s3)));
    VL_ASSIGNSEL_II(32, 8, 0U, vlSelfRef.__Vfunc_tb__DOT__good1__DOT__mix_col__14__Vfuncout, 
                    ((((([&]() {
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__21__b 
                                    = __Vfunc_tb__DOT__good1__DOT__mix_col__14__s0;
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__21__Vfuncout 
                                    = ((0x000000feU 
                                        & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__21__b) 
                                           << 1U)) 
                                       ^ (0x1bU & (- (IData)(
                                                             (1U 
                                                              & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__21__b) 
                                                                 >> 7U))))));
                                ++(vlSymsp->__Vcoverage[118]);
                            }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__21__Vfuncout)) 
                        ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__14__s0)) 
                       ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__14__s1)) 
                      ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__14__s2)) 
                     ^ ([&]() {
                    vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__22__b 
                        = __Vfunc_tb__DOT__good1__DOT__mix_col__14__s3;
                    vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__22__Vfuncout 
                        = ((0x000000feU & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__22__b) 
                                           << 1U)) 
                           ^ (0x1bU & (- (IData)((1U 
                                                  & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__22__b) 
                                                     >> 7U))))));
                    ++(vlSymsp->__Vcoverage[118]);
                }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__22__Vfuncout))));
    ++(vlSymsp->__Vcoverage[117]);
    vlSelfRef.tb__DOT__good1__DOT__mix_col_out1 = vlSelfRef.__Vfunc_tb__DOT__good1__DOT__mix_col__14__Vfuncout;
}

void Vtb___024root___nba_comb__TOP__8(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___nba_comb__TOP__8\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    CData/*7:0*/ __Vfunc_tb__DOT__good1__DOT__mix_col__23__s0;
    __Vfunc_tb__DOT__good1__DOT__mix_col__23__s0 = 0;
    CData/*7:0*/ __Vfunc_tb__DOT__good1__DOT__mix_col__23__s1;
    __Vfunc_tb__DOT__good1__DOT__mix_col__23__s1 = 0;
    CData/*7:0*/ __Vfunc_tb__DOT__good1__DOT__mix_col__23__s2;
    __Vfunc_tb__DOT__good1__DOT__mix_col__23__s2 = 0;
    CData/*7:0*/ __Vfunc_tb__DOT__good1__DOT__mix_col__23__s3;
    __Vfunc_tb__DOT__good1__DOT__mix_col__23__s3 = 0;
    // Body
    __Vfunc_tb__DOT__good1__DOT__mix_col__23__s3 = vlSymsp->TOP__tb__DOT__good1__DOT__us31.b;
    __Vfunc_tb__DOT__good1__DOT__mix_col__23__s2 = vlSymsp->TOP__tb__DOT__good1__DOT__us20.b;
    __Vfunc_tb__DOT__good1__DOT__mix_col__23__s1 = vlSymsp->TOP__tb__DOT__good1__DOT__us13.b;
    __Vfunc_tb__DOT__good1__DOT__mix_col__23__s0 = vlSymsp->TOP__tb__DOT__good1__DOT__us02.b;
    VL_ASSIGNSEL_II(32, 8, 0x18U, vlSelfRef.__Vfunc_tb__DOT__good1__DOT__mix_col__23__Vfuncout, 
                    ((((([&]() {
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__24__b 
                                    = __Vfunc_tb__DOT__good1__DOT__mix_col__23__s0;
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__24__Vfuncout 
                                    = ((0x000000feU 
                                        & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__24__b) 
                                           << 1U)) 
                                       ^ (0x1bU & (- (IData)(
                                                             (1U 
                                                              & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__24__b) 
                                                                 >> 7U))))));
                                ++(vlSymsp->__Vcoverage[118]);
                            }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__24__Vfuncout)) 
                        ^ ([&]() {
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__25__b 
                                    = __Vfunc_tb__DOT__good1__DOT__mix_col__23__s1;
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__25__Vfuncout 
                                    = ((0x000000feU 
                                        & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__25__b) 
                                           << 1U)) 
                                       ^ (0x1bU & (- (IData)(
                                                             (1U 
                                                              & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__25__b) 
                                                                 >> 7U))))));
                                ++(vlSymsp->__Vcoverage[118]);
                            }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__25__Vfuncout))) 
                       ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__23__s1)) 
                      ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__23__s2)) 
                     ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__23__s3)));
    VL_ASSIGNSEL_II(32, 8, 0x10U, vlSelfRef.__Vfunc_tb__DOT__good1__DOT__mix_col__23__Vfuncout, 
                    (((((IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__23__s0) 
                        ^ ([&]() {
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__26__b 
                                    = __Vfunc_tb__DOT__good1__DOT__mix_col__23__s1;
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__26__Vfuncout 
                                    = ((0x000000feU 
                                        & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__26__b) 
                                           << 1U)) 
                                       ^ (0x1bU & (- (IData)(
                                                             (1U 
                                                              & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__26__b) 
                                                                 >> 7U))))));
                                ++(vlSymsp->__Vcoverage[118]);
                            }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__26__Vfuncout))) 
                       ^ ([&]() {
                            vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__27__b 
                                = __Vfunc_tb__DOT__good1__DOT__mix_col__23__s2;
                            vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__27__Vfuncout 
                                = ((0x000000feU & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__27__b) 
                                                   << 1U)) 
                                   ^ (0x1bU & (- (IData)(
                                                         (1U 
                                                          & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__27__b) 
                                                             >> 7U))))));
                            ++(vlSymsp->__Vcoverage[118]);
                        }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__27__Vfuncout))) 
                      ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__23__s2)) 
                     ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__23__s3)));
    VL_ASSIGNSEL_II(32, 8, 8U, vlSelfRef.__Vfunc_tb__DOT__good1__DOT__mix_col__23__Vfuncout, 
                    (((((IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__23__s0) 
                        ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__23__s1)) 
                       ^ ([&]() {
                            vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__28__b 
                                = __Vfunc_tb__DOT__good1__DOT__mix_col__23__s2;
                            vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__28__Vfuncout 
                                = ((0x000000feU & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__28__b) 
                                                   << 1U)) 
                                   ^ (0x1bU & (- (IData)(
                                                         (1U 
                                                          & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__28__b) 
                                                             >> 7U))))));
                            ++(vlSymsp->__Vcoverage[118]);
                        }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__28__Vfuncout))) 
                      ^ ([&]() {
                        vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__29__b 
                            = __Vfunc_tb__DOT__good1__DOT__mix_col__23__s3;
                        vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__29__Vfuncout 
                            = ((0x000000feU & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__29__b) 
                                               << 1U)) 
                               ^ (0x1bU & (- (IData)(
                                                     (1U 
                                                      & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__29__b) 
                                                         >> 7U))))));
                        ++(vlSymsp->__Vcoverage[118]);
                    }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__29__Vfuncout))) 
                     ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__23__s3)));
    VL_ASSIGNSEL_II(32, 8, 0U, vlSelfRef.__Vfunc_tb__DOT__good1__DOT__mix_col__23__Vfuncout, 
                    ((((([&]() {
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__30__b 
                                    = __Vfunc_tb__DOT__good1__DOT__mix_col__23__s0;
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__30__Vfuncout 
                                    = ((0x000000feU 
                                        & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__30__b) 
                                           << 1U)) 
                                       ^ (0x1bU & (- (IData)(
                                                             (1U 
                                                              & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__30__b) 
                                                                 >> 7U))))));
                                ++(vlSymsp->__Vcoverage[118]);
                            }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__30__Vfuncout)) 
                        ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__23__s0)) 
                       ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__23__s1)) 
                      ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__23__s2)) 
                     ^ ([&]() {
                    vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__31__b 
                        = __Vfunc_tb__DOT__good1__DOT__mix_col__23__s3;
                    vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__31__Vfuncout 
                        = ((0x000000feU & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__31__b) 
                                           << 1U)) 
                           ^ (0x1bU & (- (IData)((1U 
                                                  & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__31__b) 
                                                     >> 7U))))));
                    ++(vlSymsp->__Vcoverage[118]);
                }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__31__Vfuncout))));
    ++(vlSymsp->__Vcoverage[117]);
    vlSelfRef.tb__DOT__good1__DOT__mix_col_out2 = vlSelfRef.__Vfunc_tb__DOT__good1__DOT__mix_col__23__Vfuncout;
}

void Vtb___024root___nba_comb__TOP__9(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___nba_comb__TOP__9\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    CData/*7:0*/ __Vfunc_tb__DOT__good1__DOT__mix_col__32__s0;
    __Vfunc_tb__DOT__good1__DOT__mix_col__32__s0 = 0;
    CData/*7:0*/ __Vfunc_tb__DOT__good1__DOT__mix_col__32__s1;
    __Vfunc_tb__DOT__good1__DOT__mix_col__32__s1 = 0;
    CData/*7:0*/ __Vfunc_tb__DOT__good1__DOT__mix_col__32__s2;
    __Vfunc_tb__DOT__good1__DOT__mix_col__32__s2 = 0;
    CData/*7:0*/ __Vfunc_tb__DOT__good1__DOT__mix_col__32__s3;
    __Vfunc_tb__DOT__good1__DOT__mix_col__32__s3 = 0;
    // Body
    __Vfunc_tb__DOT__good1__DOT__mix_col__32__s3 = vlSymsp->TOP__tb__DOT__good1__DOT__us32.b;
    __Vfunc_tb__DOT__good1__DOT__mix_col__32__s2 = vlSymsp->TOP__tb__DOT__good1__DOT__us21.b;
    __Vfunc_tb__DOT__good1__DOT__mix_col__32__s1 = vlSymsp->TOP__tb__DOT__good1__DOT__us10.b;
    __Vfunc_tb__DOT__good1__DOT__mix_col__32__s0 = vlSymsp->TOP__tb__DOT__good1__DOT__us03.b;
    VL_ASSIGNSEL_II(32, 8, 0x18U, vlSelfRef.__Vfunc_tb__DOT__good1__DOT__mix_col__32__Vfuncout, 
                    ((((([&]() {
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__33__b 
                                    = __Vfunc_tb__DOT__good1__DOT__mix_col__32__s0;
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__33__Vfuncout 
                                    = ((0x000000feU 
                                        & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__33__b) 
                                           << 1U)) 
                                       ^ (0x1bU & (- (IData)(
                                                             (1U 
                                                              & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__33__b) 
                                                                 >> 7U))))));
                                ++(vlSymsp->__Vcoverage[118]);
                            }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__33__Vfuncout)) 
                        ^ ([&]() {
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__34__b 
                                    = __Vfunc_tb__DOT__good1__DOT__mix_col__32__s1;
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__34__Vfuncout 
                                    = ((0x000000feU 
                                        & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__34__b) 
                                           << 1U)) 
                                       ^ (0x1bU & (- (IData)(
                                                             (1U 
                                                              & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__34__b) 
                                                                 >> 7U))))));
                                ++(vlSymsp->__Vcoverage[118]);
                            }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__34__Vfuncout))) 
                       ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__32__s1)) 
                      ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__32__s2)) 
                     ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__32__s3)));
    VL_ASSIGNSEL_II(32, 8, 0x10U, vlSelfRef.__Vfunc_tb__DOT__good1__DOT__mix_col__32__Vfuncout, 
                    (((((IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__32__s0) 
                        ^ ([&]() {
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__35__b 
                                    = __Vfunc_tb__DOT__good1__DOT__mix_col__32__s1;
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__35__Vfuncout 
                                    = ((0x000000feU 
                                        & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__35__b) 
                                           << 1U)) 
                                       ^ (0x1bU & (- (IData)(
                                                             (1U 
                                                              & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__35__b) 
                                                                 >> 7U))))));
                                ++(vlSymsp->__Vcoverage[118]);
                            }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__35__Vfuncout))) 
                       ^ ([&]() {
                            vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__36__b 
                                = __Vfunc_tb__DOT__good1__DOT__mix_col__32__s2;
                            vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__36__Vfuncout 
                                = ((0x000000feU & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__36__b) 
                                                   << 1U)) 
                                   ^ (0x1bU & (- (IData)(
                                                         (1U 
                                                          & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__36__b) 
                                                             >> 7U))))));
                            ++(vlSymsp->__Vcoverage[118]);
                        }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__36__Vfuncout))) 
                      ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__32__s2)) 
                     ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__32__s3)));
    VL_ASSIGNSEL_II(32, 8, 8U, vlSelfRef.__Vfunc_tb__DOT__good1__DOT__mix_col__32__Vfuncout, 
                    (((((IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__32__s0) 
                        ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__32__s1)) 
                       ^ ([&]() {
                            vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__37__b 
                                = __Vfunc_tb__DOT__good1__DOT__mix_col__32__s2;
                            vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__37__Vfuncout 
                                = ((0x000000feU & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__37__b) 
                                                   << 1U)) 
                                   ^ (0x1bU & (- (IData)(
                                                         (1U 
                                                          & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__37__b) 
                                                             >> 7U))))));
                            ++(vlSymsp->__Vcoverage[118]);
                        }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__37__Vfuncout))) 
                      ^ ([&]() {
                        vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__38__b 
                            = __Vfunc_tb__DOT__good1__DOT__mix_col__32__s3;
                        vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__38__Vfuncout 
                            = ((0x000000feU & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__38__b) 
                                               << 1U)) 
                               ^ (0x1bU & (- (IData)(
                                                     (1U 
                                                      & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__38__b) 
                                                         >> 7U))))));
                        ++(vlSymsp->__Vcoverage[118]);
                    }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__38__Vfuncout))) 
                     ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__32__s3)));
    VL_ASSIGNSEL_II(32, 8, 0U, vlSelfRef.__Vfunc_tb__DOT__good1__DOT__mix_col__32__Vfuncout, 
                    ((((([&]() {
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__39__b 
                                    = __Vfunc_tb__DOT__good1__DOT__mix_col__32__s0;
                                vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__39__Vfuncout 
                                    = ((0x000000feU 
                                        & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__39__b) 
                                           << 1U)) 
                                       ^ (0x1bU & (- (IData)(
                                                             (1U 
                                                              & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__39__b) 
                                                                 >> 7U))))));
                                ++(vlSymsp->__Vcoverage[118]);
                            }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__39__Vfuncout)) 
                        ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__32__s0)) 
                       ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__32__s1)) 
                      ^ (IData)(__Vfunc_tb__DOT__good1__DOT__mix_col__32__s2)) 
                     ^ ([&]() {
                    vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__40__b 
                        = __Vfunc_tb__DOT__good1__DOT__mix_col__32__s3;
                    vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__40__Vfuncout 
                        = ((0x000000feU & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__40__b) 
                                           << 1U)) 
                           ^ (0x1bU & (- (IData)((1U 
                                                  & ((IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__40__b) 
                                                     >> 7U))))));
                    ++(vlSymsp->__Vcoverage[118]);
                }(), (IData)(vlSelfRef.__Vfunc_tb__DOT__good1__DOT__xtime__40__Vfuncout))));
    ++(vlSymsp->__Vcoverage[117]);
    vlSelfRef.tb__DOT__good1__DOT__mix_col_out3 = vlSelfRef.__Vfunc_tb__DOT__good1__DOT__mix_col__32__Vfuncout;
}

void Vtb___024root___nba_sequent__TOP__4(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___nba_sequent__TOP__4\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.tb__DOT__top_module1__DOT__ld_cap = vlSelfRef.__Vdly__tb__DOT__top_module1__DOT__ld_cap;
}

void Vtb___024root___nba_comb__TOP__10(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___nba_comb__TOP__10\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    VlWide<4>/*127:0*/ __Vtemp_2;
    VlWide<4>/*127:0*/ __Vtemp_4;
    // Body
    __Vtemp_2[0U] = ((((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_00.b) 
                       << 0x00000018U) | ((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_11.b) 
                                          << 0x00000010U)) 
                     | (((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_22.b) 
                         << 8U) | (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_33.b)));
    __Vtemp_2[1U] = ((((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_01.b) 
                       << 0x00000018U) | ((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_12.b) 
                                          << 0x00000010U)) 
                     | (((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_23.b) 
                         << 8U) | (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_30.b)));
    __Vtemp_2[2U] = (IData)((((QData)((IData)(((((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_03.b) 
                                                 << 0x00000018U) 
                                                | ((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_10.b) 
                                                   << 0x00000010U)) 
                                               | (((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_21.b) 
                                                   << 8U) 
                                                  | (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_32.b))))) 
                              << 0x00000020U) | (QData)((IData)(
                                                                ((((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_02.b) 
                                                                   << 0x00000018U) 
                                                                  | ((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_13.b) 
                                                                     << 0x00000010U)) 
                                                                 | (((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_20.b) 
                                                                     << 8U) 
                                                                    | (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_31.b)))))));
    __Vtemp_2[3U] = (IData)(((((QData)((IData)(((((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_03.b) 
                                                  << 0x00000018U) 
                                                 | ((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_10.b) 
                                                    << 0x00000010U)) 
                                                | (((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_21.b) 
                                                    << 8U) 
                                                   | (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_32.b))))) 
                               << 0x00000020U) | (QData)((IData)(
                                                                 ((((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_02.b) 
                                                                    << 0x00000018U) 
                                                                   | ((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_13.b) 
                                                                      << 0x00000010U)) 
                                                                  | (((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_20.b) 
                                                                      << 8U) 
                                                                     | (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_31.b)))))) 
                             >> 0x00000020U));
    __Vtemp_4[0U] = ((((IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_00) 
                       << 0x00000018U) | ((IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_10) 
                                          << 0x00000010U)) 
                     | (((IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_20) 
                         << 8U) | (IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_30)));
    __Vtemp_4[1U] = ((((IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_01) 
                       << 0x00000018U) | ((IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_11) 
                                          << 0x00000010U)) 
                     | (((IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_21) 
                         << 8U) | (IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_31)));
    __Vtemp_4[2U] = (IData)((((QData)((IData)(((((IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_03) 
                                                 << 0x00000018U) 
                                                | ((IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_13) 
                                                   << 0x00000010U)) 
                                               | (((IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_23) 
                                                   << 8U) 
                                                  | (IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_33))))) 
                              << 0x00000020U) | (QData)((IData)(
                                                                ((((IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_02) 
                                                                   << 0x00000018U) 
                                                                  | ((IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_12) 
                                                                     << 0x00000010U)) 
                                                                 | (((IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_22) 
                                                                     << 8U) 
                                                                    | (IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_32)))))));
    __Vtemp_4[3U] = (IData)(((((QData)((IData)(((((IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_03) 
                                                  << 0x00000018U) 
                                                 | ((IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_13) 
                                                    << 0x00000010U)) 
                                                | (((IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_23) 
                                                    << 8U) 
                                                   | (IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_33))))) 
                               << 0x00000020U) | (QData)((IData)(
                                                                 ((((IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_02) 
                                                                    << 0x00000018U) 
                                                                   | ((IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_12) 
                                                                      << 0x00000010U)) 
                                                                  | (((IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_22) 
                                                                      << 8U) 
                                                                     | (IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_32)))))) 
                             >> 0x00000020U));
    VL_COND_WIWW(128, vlSelfRef.tb__DOT__top_module1__DOT__round_data, 
                 (2U != (IData)(vlSelfRef.tb__DOT__top_module1__DOT__state)), 
                 ([&]() {
                ++(vlSymsp->__Vcoverage[154]);
            }(), __Vtemp_2), ([&]() {
                ++(vlSymsp->__Vcoverage[155]);
            }(), __Vtemp_4));
    vlSelfRef.tb__DOT__top_module1__DOT__add_rkey_out[0U] 
        = (vlSelfRef.tb__DOT__top_module1__DOT__round_data[0U] 
           ^ vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
           [3U]);
    vlSelfRef.tb__DOT__top_module1__DOT__add_rkey_out[1U] 
        = (vlSelfRef.tb__DOT__top_module1__DOT__round_data[1U] 
           ^ vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
           [2U]);
    vlSelfRef.tb__DOT__top_module1__DOT__add_rkey_out[2U] 
        = (vlSelfRef.tb__DOT__top_module1__DOT__round_data[2U] 
           ^ (IData)((((QData)((IData)(vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                       [0U])) << 0x00000020U) 
                      | (QData)((IData)(vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                        [1U])))));
    vlSelfRef.tb__DOT__top_module1__DOT__add_rkey_out[3U] 
        = (vlSelfRef.tb__DOT__top_module1__DOT__round_data[3U] 
           ^ (IData)(((((QData)((IData)(vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                        [0U])) << 0x00000020U) 
                       | (QData)((IData)(vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                         [1U]))) >> 0x00000020U)));
}

void Vtb___024root___nba_comb__TOP__11(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___nba_comb__TOP__11\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((4U & (IData)(vlSelfRef.tb__DOT__top_module1__DOT__state))) {
        if ((2U & (IData)(vlSelfRef.tb__DOT__top_module1__DOT__state))) {
            vlSelfRef.tb__DOT__top_module1__DOT__next_state = 0U;
            ++(vlSymsp->__Vcoverage[167]);
        } else if ((1U & (IData)(vlSelfRef.tb__DOT__top_module1__DOT__state))) {
            ++(vlSymsp->__Vcoverage[167]);
            vlSelfRef.tb__DOT__top_module1__DOT__next_state = 0U;
        } else {
            vlSelfRef.tb__DOT__top_module1__DOT__next_state 
                = (((IData)(vlSelfRef.tb__DOT__top_module1__DOT__ld_cap) 
                    | (IData)(vlSelfRef.tb__DOT__top_module1__DOT__kld))
                    ? ([&]() {
                        ++(vlSymsp->__Vcoverage[164]);
                    }(), 1U) : ([&]() {
                        ++(vlSymsp->__Vcoverage[165]);
                    }(), 4U));
            ++(vlSymsp->__Vcoverage[166]);
        }
    } else if ((2U & (IData)(vlSelfRef.tb__DOT__top_module1__DOT__state))) {
        if ((1U & (IData)(vlSelfRef.tb__DOT__top_module1__DOT__state))) {
            ++(vlSymsp->__Vcoverage[163]);
            vlSelfRef.tb__DOT__top_module1__DOT__next_state = 4U;
        } else {
            vlSelfRef.tb__DOT__top_module1__DOT__next_state 
                = ((1U == (IData)(vlSelfRef.tb__DOT__top_module1__DOT__dcnt))
                    ? ([&]() {
                        ++(vlSymsp->__Vcoverage[160]);
                    }(), 3U) : ([&]() {
                        ++(vlSymsp->__Vcoverage[161]);
                    }(), 2U));
            ++(vlSymsp->__Vcoverage[162]);
        }
    } else if ((1U & (IData)(vlSelfRef.tb__DOT__top_module1__DOT__state))) {
        ++(vlSymsp->__Vcoverage[159]);
        vlSelfRef.tb__DOT__top_module1__DOT__next_state = 2U;
    } else {
        vlSelfRef.tb__DOT__top_module1__DOT__next_state 
            = (((IData)(vlSelfRef.tb__DOT__top_module1__DOT__ld_cap) 
                | (IData)(vlSelfRef.tb__DOT__top_module1__DOT__kld))
                ? ([&]() {
                    ++(vlSymsp->__Vcoverage[156]);
                }(), 1U) : ([&]() {
                    ++(vlSymsp->__Vcoverage[157]);
                }(), 0U));
        ++(vlSymsp->__Vcoverage[158]);
    }
    ++(vlSymsp->__Vcoverage[168]);
}

void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u0__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u1__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u2__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u3__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__u0__DOT__u0__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__u0__DOT__u1__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__u0__DOT__u2__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__u0__DOT__u3__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us00__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us01__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us02__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us03__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us10__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us11__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us12__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us13__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us20__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us21__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us22__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us23__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us30__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us31__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us32__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us33__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_00__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_10__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_20__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_30__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_01__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_11__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_21__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_31__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_02__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_12__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_22__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_32__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_03__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_13__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_23__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_33__0(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__u0__DOT__u0__1(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__u0__DOT__u1__1(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__u0__DOT__u2__1(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__u0__DOT__u3__1(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u0__1(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u1__1(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u2__1(Vtb_aes_sbox* vlSelf);
void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u3__1(Vtb_aes_sbox* vlSelf);

void Vtb___024root___eval_nba(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___eval_nba\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((1ULL & vlSelfRef.__VnbaTriggered[0U])) {
        Vtb___024root___nba_sequent__TOP__0(vlSelf);
        vlSelfRef.__Vm_traceActivity[3U] = 1U;
    }
    if ((0x0000040000000002ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb___024root___nba_sequent__TOP__1(vlSelf);
    }
    if ((0x0000004000000000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u0__0((&vlSymsp->TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u0));
    }
    if ((0x0000008000000000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u1__0((&vlSymsp->TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u1));
    }
    if ((0x0000010000000000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u2__0((&vlSymsp->TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u2));
    }
    if ((0x0000020000000000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u3__0((&vlSymsp->TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u3));
    }
    if ((0x0000000000040000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__u0__DOT__u0__0((&vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u0));
    }
    if ((0x0000000000080000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__u0__DOT__u1__0((&vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u1));
    }
    if ((0x0000000000100000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__u0__DOT__u2__0((&vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u2));
    }
    if ((0x0000000000200000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__u0__DOT__u3__0((&vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u3));
    }
    if ((4ULL & vlSelfRef.__VnbaTriggered[0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us00__0((&vlSymsp->TOP__tb__DOT__good1__DOT__us00));
    }
    if ((8ULL & vlSelfRef.__VnbaTriggered[0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us01__0((&vlSymsp->TOP__tb__DOT__good1__DOT__us01));
    }
    if ((0x0000000000000010ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us02__0((&vlSymsp->TOP__tb__DOT__good1__DOT__us02));
    }
    if ((0x0000000000000020ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us03__0((&vlSymsp->TOP__tb__DOT__good1__DOT__us03));
    }
    if ((0x0000000000000040ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us10__0((&vlSymsp->TOP__tb__DOT__good1__DOT__us10));
    }
    if ((0x0000000000000080ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us11__0((&vlSymsp->TOP__tb__DOT__good1__DOT__us11));
    }
    if ((0x0000000000000100ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us12__0((&vlSymsp->TOP__tb__DOT__good1__DOT__us12));
    }
    if ((0x0000000000000200ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us13__0((&vlSymsp->TOP__tb__DOT__good1__DOT__us13));
    }
    if ((0x0000000000000400ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us20__0((&vlSymsp->TOP__tb__DOT__good1__DOT__us20));
    }
    if ((0x0000000000000800ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us21__0((&vlSymsp->TOP__tb__DOT__good1__DOT__us21));
    }
    if ((0x0000000000001000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us22__0((&vlSymsp->TOP__tb__DOT__good1__DOT__us22));
    }
    if ((0x0000000000002000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us23__0((&vlSymsp->TOP__tb__DOT__good1__DOT__us23));
    }
    if ((0x0000000000004000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us30__0((&vlSymsp->TOP__tb__DOT__good1__DOT__us30));
    }
    if ((0x0000000000008000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us31__0((&vlSymsp->TOP__tb__DOT__good1__DOT__us31));
    }
    if ((0x0000000000010000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us32__0((&vlSymsp->TOP__tb__DOT__good1__DOT__us32));
    }
    if ((0x0000000000020000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__us33__0((&vlSymsp->TOP__tb__DOT__good1__DOT__us33));
    }
    if ((0x0000000000400000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_00__0((&vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_00));
    }
    if ((0x0000000000800000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_10__0((&vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_10));
    }
    if ((0x0000000001000000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_20__0((&vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_20));
    }
    if ((0x0000000002000000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_30__0((&vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_30));
    }
    if ((0x0000000004000000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_01__0((&vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_01));
    }
    if ((0x0000000008000000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_11__0((&vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_11));
    }
    if ((0x0000000010000000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_21__0((&vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_21));
    }
    if ((0x0000000020000000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_31__0((&vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_31));
    }
    if ((0x0000000040000000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_02__0((&vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_02));
    }
    if ((0x0000000080000000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_12__0((&vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_12));
    }
    if ((0x0000000100000000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_22__0((&vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_22));
    }
    if ((0x0000000200000000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_32__0((&vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_32));
    }
    if ((0x0000000400000000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_03__0((&vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_03));
    }
    if ((0x0000000800000000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_13__0((&vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_13));
    }
    if ((0x0000001000000000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_23__0((&vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_23));
    }
    if ((0x0000002000000000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_sbox_33__0((&vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_33));
    }
    if ((2ULL & vlSelfRef.__VnbaTriggered[0U])) {
        Vtb___024root___nba_sequent__TOP__2(vlSelf);
    }
    if ((0x000003c000000000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb___024root___nba_comb__TOP__0(vlSelf);
    }
    if ((0x00000000003c0000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb___024root___nba_comb__TOP__1(vlSelf);
    }
    if ((1ULL & vlSelfRef.__VnbaTriggered[0U])) {
        Vtb___024root___nba_sequent__TOP__3(vlSelf);
        vlSelfRef.__Vm_traceActivity[4U] = 1U;
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__u0__DOT__u0__1((&vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u0));
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__u0__DOT__u1__1((&vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u1));
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__u0__DOT__u2__1((&vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u2));
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__good1__DOT__u0__DOT__u3__1((&vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u3));
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u0__1((&vlSymsp->TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u0));
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u1__1((&vlSymsp->TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u1));
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u2__1((&vlSymsp->TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u2));
        Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u3__1((&vlSymsp->TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u3));
    }
    if ((0x0000000610800000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb___024root___nba_comb__TOP__2(vlSelf);
        vlSelfRef.__Vm_traceActivity[5U] = 1U;
    }
    if ((0x0000000861000000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb___024root___nba_comb__TOP__3(vlSelf);
        vlSelfRef.__Vm_traceActivity[6U] = 1U;
    }
    if ((0x0000001086000000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb___024root___nba_comb__TOP__4(vlSelf);
        vlSelfRef.__Vm_traceActivity[7U] = 1U;
    }
    if ((0x0000002108400000ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb___024root___nba_comb__TOP__5(vlSelf);
        vlSelfRef.__Vm_traceActivity[8U] = 1U;
    }
    if ((0x0000000000021084ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb___024root___nba_comb__TOP__6(vlSelf);
        vlSelfRef.__Vm_traceActivity[9U] = 1U;
    }
    if ((0x0000000000006108ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb___024root___nba_comb__TOP__7(vlSelf);
        vlSelfRef.__Vm_traceActivity[0x0000000aU] = 1U;
    }
    if ((0x0000000000008610ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb___024root___nba_comb__TOP__8(vlSelf);
        vlSelfRef.__Vm_traceActivity[0x0000000bU] = 1U;
    }
    if ((0x0000000000010860ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb___024root___nba_comb__TOP__9(vlSelf);
        vlSelfRef.__Vm_traceActivity[0x0000000cU] = 1U;
    }
    if ((0x0000040000000002ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb___024root___nba_sequent__TOP__4(vlSelf);
    }
    if ((0x0000003fffc00001ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb___024root___nba_comb__TOP__10(vlSelf);
        vlSelfRef.__Vm_traceActivity[0x0000000dU] = 1U;
    }
    if ((0x0000040000000003ULL & vlSelfRef.__VnbaTriggered
         [0U])) {
        Vtb___024root___nba_comb__TOP__11(vlSelf);
    }
}

void Vtb___024root___timing_commit(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___timing_commit\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((! (1ULL & vlSelfRef.__VactTriggered[0U]))) {
        vlSelfRef.__VtrigSched_h32009f5a__0.commit(
                                                   "@(posedge tb.clk)");
    }
    if ((! (2ULL & vlSelfRef.__VactTriggered[0U]))) {
        vlSelfRef.__VtrigSched_h32009f1b__0.commit(
                                                   "@(negedge tb.clk)");
    }
}

void Vtb___024root___timing_resume(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___timing_resume\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((1ULL & vlSelfRef.__VactTriggered[0U])) {
        vlSelfRef.__VtrigSched_h32009f5a__0.resume(
                                                   "@(posedge tb.clk)");
    }
    if ((2ULL & vlSelfRef.__VactTriggered[0U])) {
        vlSelfRef.__VtrigSched_h32009f1b__0.resume(
                                                   "@(negedge tb.clk)");
    }
    if ((0x0000080000000000ULL & vlSelfRef.__VactTriggered
         [0U])) {
        vlSelfRef.__VdlySched.resume();
    }
}

void Vtb___024root___trigger_orInto__act(VlUnpacked<QData/*63:0*/, 1> &out, const VlUnpacked<QData/*63:0*/, 1> &in) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___trigger_orInto__act\n"); );
    // Locals
    IData/*31:0*/ n;
    // Body
    n = 0U;
    do {
        out[n] = (out[n] | in[n]);
        n = ((IData)(1U) + n);
    } while ((1U > n));
}

bool Vtb___024root___eval_phase__act(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___eval_phase__act\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    CData/*0:0*/ __VactExecute;
    // Body
    Vtb___024root___eval_triggers__act(vlSelf);
    Vtb___024root___timing_commit(vlSelf);
    Vtb___024root___trigger_orInto__act(vlSelfRef.__VnbaTriggered, vlSelfRef.__VactTriggered);
    __VactExecute = Vtb___024root___trigger_anySet__act(vlSelfRef.__VactTriggered);
    if (__VactExecute) {
        Vtb___024root___timing_resume(vlSelf);
    }
    return (__VactExecute);
}

void Vtb___024root___trigger_clear__act(VlUnpacked<QData/*63:0*/, 1> &out) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___trigger_clear__act\n"); );
    // Locals
    IData/*31:0*/ n;
    // Body
    n = 0U;
    do {
        out[n] = 0ULL;
        n = ((IData)(1U) + n);
    } while ((1U > n));
}

bool Vtb___024root___eval_phase__nba(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___eval_phase__nba\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    CData/*0:0*/ __VnbaExecute;
    // Body
    __VnbaExecute = Vtb___024root___trigger_anySet__act(vlSelfRef.__VnbaTriggered);
    if (__VnbaExecute) {
        Vtb___024root___eval_nba(vlSelf);
        Vtb___024root___trigger_clear__act(vlSelfRef.__VnbaTriggered);
    }
    return (__VnbaExecute);
}

void Vtb___024root___eval(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___eval\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    IData/*31:0*/ __VnbaIterCount;
    // Body
    __VnbaIterCount = 0U;
    do {
        if (VL_UNLIKELY(((0x00000064U < __VnbaIterCount)))) {
#ifdef VL_DEBUG
            Vtb___024root___dump_triggers__act(vlSelfRef.__VnbaTriggered, "nba"s);
#endif
            VL_FATAL_MT("aes_cipher_top_testbench.sv", 3, "", "NBA region did not converge after 100 tries");
        }
        __VnbaIterCount = ((IData)(1U) + __VnbaIterCount);
        vlSelfRef.__VactIterCount = 0U;
        do {
            if (VL_UNLIKELY(((0x00000064U < vlSelfRef.__VactIterCount)))) {
#ifdef VL_DEBUG
                Vtb___024root___dump_triggers__act(vlSelfRef.__VactTriggered, "act"s);
#endif
                VL_FATAL_MT("aes_cipher_top_testbench.sv", 3, "", "Active region did not converge after 100 tries");
            }
            vlSelfRef.__VactIterCount = ((IData)(1U) 
                                         + vlSelfRef.__VactIterCount);
        } while (Vtb___024root___eval_phase__act(vlSelf));
    } while (Vtb___024root___eval_phase__nba(vlSelf));
}

#ifdef VL_DEBUG
void Vtb___024root___eval_debug_assertions(Vtb___024root* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root___eval_debug_assertions\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
}
#endif  // VL_DEBUG
