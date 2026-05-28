// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Tracing implementation internals

#include "verilated_vcd_c.h"
#include "Vtb__Syms.h"


void Vtb___024root__trace_chg_0_sub_0(Vtb___024root* vlSelf, VerilatedVcd::Buffer* bufp);

void Vtb___024root__trace_chg_0(void* voidSelf, VerilatedVcd::Buffer* bufp) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root__trace_chg_0\n"); );
    // Body
    Vtb___024root* const __restrict vlSelf VL_ATTR_UNUSED = static_cast<Vtb___024root*>(voidSelf);
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    if (VL_UNLIKELY(!vlSymsp->__Vm_activity)) return;
    Vtb___024root__trace_chg_0_sub_0((&vlSymsp->TOP), bufp);
}

void Vtb___024root__trace_chg_0_sub_0(Vtb___024root* vlSelf, VerilatedVcd::Buffer* bufp) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root__trace_chg_0_sub_0\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Locals
    VlWide<7>/*223:0*/ __Vtemp_5;
    VlWide<4>/*127:0*/ __Vtemp_7;
    VlWide<4>/*127:0*/ __Vtemp_9;
    VlWide<4>/*127:0*/ __Vtemp_11;
    VlWide<4>/*127:0*/ __Vtemp_13;
    // Body
    uint32_t* const oldp VL_ATTR_UNUSED = bufp->oldp(vlSymsp->__Vm_baseCode + 1);
    if (VL_UNLIKELY((vlSelfRef.__Vm_traceActivity[0U]))) {
        bufp->chgWData(oldp+0,(vlSelfRef.tb__DOT__stim1__DOT__TEST_KEYS[0]),128);
        bufp->chgWData(oldp+4,(vlSelfRef.tb__DOT__stim1__DOT__TEST_KEYS[1]),128);
        bufp->chgWData(oldp+8,(vlSelfRef.tb__DOT__stim1__DOT__TEST_KEYS[2]),128);
        bufp->chgWData(oldp+12,(vlSelfRef.tb__DOT__stim1__DOT__TEST_KEYS[3]),128);
        bufp->chgWData(oldp+16,(vlSelfRef.tb__DOT__stim1__DOT__TEST_KEYS[4]),128);
        bufp->chgWData(oldp+20,(vlSelfRef.tb__DOT__stim1__DOT__TEST_KEYS[5]),128);
    }
    if (VL_UNLIKELY(((vlSelfRef.__Vm_traceActivity[1U] 
                      | vlSelfRef.__Vm_traceActivity
                      [2U])))) {
        bufp->chgBit(oldp+24,(vlSelfRef.tb__DOT__rst));
        bufp->chgBit(oldp+25,(vlSelfRef.tb__DOT__ld));
        bufp->chgWData(oldp+26,(vlSelfRef.tb__DOT__key),128);
        bufp->chgWData(oldp+30,(vlSelfRef.tb__DOT__text_in),128);
        bufp->chgWData(oldp+34,(vlSelfRef.tb__DOT__wavedrom_title),512);
        bufp->chgBit(oldp+50,(vlSelfRef.tb__DOT__wavedrom_enable));
        bufp->chgBit(oldp+51,(vlSelfRef.tb__DOT__stim1__DOT__reset_test__Vstatic__arfail));
        bufp->chgBit(oldp+52,(vlSelfRef.tb__DOT__stim1__DOT__reset_test__Vstatic__srfail));
        bufp->chgBit(oldp+53,(vlSelfRef.tb__DOT__stim1__DOT__reset_test__Vstatic__datafail));
        bufp->chgIData(oldp+54,(vlSelfRef.tb__DOT__stim1__DOT__unnamedblk1__DOT__i),32);
    }
    if (VL_UNLIKELY((vlSelfRef.__Vm_traceActivity[3U]))) {
        __Vtemp_5[0U] = vlSelfRef.tb__DOT__stats1__BRA__31__03a0__KET__;
        __Vtemp_5[1U] = vlSelfRef.tb__DOT__stats1__BRA__63__03a32__KET__;
        __Vtemp_5[2U] = vlSelfRef.tb__DOT__stats1__BRA__95__03a64__KET__;
        __Vtemp_5[3U] = vlSelfRef.tb__DOT__stats1__BRA__127__03a96__KET__;
        __Vtemp_5[4U] = vlSelfRef.tb__DOT__stats1__BRA__159__03a128__KET__;
        __Vtemp_5[5U] = (IData)((((QData)((IData)(vlSelfRef.tb__DOT__stats1__BRA__223__03a192__KET__)) 
                                  << 0x00000020U) | (QData)((IData)(vlSelfRef.tb__DOT__stats1__BRA__191__03a160__KET__))));
        __Vtemp_5[6U] = (IData)(((((QData)((IData)(vlSelfRef.tb__DOT__stats1__BRA__223__03a192__KET__)) 
                                   << 0x00000020U) 
                                  | (QData)((IData)(vlSelfRef.tb__DOT__stats1__BRA__191__03a160__KET__))) 
                                 >> 0x00000020U));
        bufp->chgWData(oldp+55,(__Vtemp_5),224);
        bufp->chgBit(oldp+62,(vlSelfRef.tb__DOT__done_ref));
        bufp->chgWData(oldp+63,(vlSelfRef.tb__DOT__text_out_ref),128);
        bufp->chgCData(oldp+67,(vlSelfRef.tb__DOT__good1__DOT__dcnt),4);
        bufp->chgIData(oldp+68,(vlSelfRef.tb__DOT__good1__DOT__u0__DOT__rcon),32);
        bufp->chgCData(oldp+69,(vlSelfRef.tb__DOT__good1__DOT__u0__DOT__r0__DOT__rcnt),4);
        bufp->chgCData(oldp+70,((0x0000000fU & ((IData)(1U) 
                                                + (IData)(vlSelfRef.tb__DOT__good1__DOT__u0__DOT__r0__DOT__rcnt)))),4);
        bufp->chgIData(oldp+71,(vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__rcon),32);
        bufp->chgCData(oldp+72,(vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__rcnt),4);
        bufp->chgCData(oldp+73,((0x0000000fU & ((IData)(1U) 
                                                + (IData)(vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__r0__DOT__rcnt)))),4);
    }
    if (VL_UNLIKELY((vlSelfRef.__Vm_traceActivity[4U]))) {
        bufp->chgBit(oldp+74,((4U == (IData)(vlSelfRef.tb__DOT__top_module1__DOT__state))));
        bufp->chgWData(oldp+75,(vlSelfRef.tb__DOT__top_module1__DOT__text_out_r),128);
        bufp->chgBit(oldp+79,(vlSelfRef.tb__DOT__tb_match_text));
        bufp->chgBit(oldp+80,(vlSelfRef.tb__DOT__tb_match_done));
        bufp->chgBit(oldp+81,(((IData)(vlSelfRef.tb__DOT__tb_match_text) 
                               & (IData)(vlSelfRef.tb__DOT__tb_match_done))));
        bufp->chgIData(oldp+82,(vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                [0U]),32);
        bufp->chgIData(oldp+83,(vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                [1U]),32);
        bufp->chgIData(oldp+84,(vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                [2U]),32);
        bufp->chgIData(oldp+85,(vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                [3U]),32);
        bufp->chgWData(oldp+86,(vlSelfRef.tb__DOT__good1__DOT__text_in_r),128);
        bufp->chgCData(oldp+90,(vlSelfRef.tb__DOT__good1__DOT__sa00),8);
        bufp->chgCData(oldp+91,(vlSelfRef.tb__DOT__good1__DOT__sa01),8);
        bufp->chgCData(oldp+92,(vlSelfRef.tb__DOT__good1__DOT__sa02),8);
        bufp->chgCData(oldp+93,(vlSelfRef.tb__DOT__good1__DOT__sa03),8);
        bufp->chgCData(oldp+94,(vlSelfRef.tb__DOT__good1__DOT__sa10),8);
        bufp->chgCData(oldp+95,(vlSelfRef.tb__DOT__good1__DOT__sa11),8);
        bufp->chgCData(oldp+96,(vlSelfRef.tb__DOT__good1__DOT__sa12),8);
        bufp->chgCData(oldp+97,(vlSelfRef.tb__DOT__good1__DOT__sa13),8);
        bufp->chgCData(oldp+98,(vlSelfRef.tb__DOT__good1__DOT__sa20),8);
        bufp->chgCData(oldp+99,(vlSelfRef.tb__DOT__good1__DOT__sa21),8);
        bufp->chgCData(oldp+100,(vlSelfRef.tb__DOT__good1__DOT__sa22),8);
        bufp->chgCData(oldp+101,(vlSelfRef.tb__DOT__good1__DOT__sa23),8);
        bufp->chgCData(oldp+102,(vlSelfRef.tb__DOT__good1__DOT__sa30),8);
        bufp->chgCData(oldp+103,(vlSelfRef.tb__DOT__good1__DOT__sa31),8);
        bufp->chgCData(oldp+104,(vlSelfRef.tb__DOT__good1__DOT__sa32),8);
        bufp->chgCData(oldp+105,(vlSelfRef.tb__DOT__good1__DOT__sa33),8);
        bufp->chgBit(oldp+106,(vlSelfRef.tb__DOT__good1__DOT__ld_r));
        bufp->chgIData(oldp+107,(vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w[0]),32);
        bufp->chgIData(oldp+108,(vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w[1]),32);
        bufp->chgIData(oldp+109,(vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w[2]),32);
        bufp->chgIData(oldp+110,(vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w[3]),32);
        bufp->chgCData(oldp+111,(vlSelfRef.tb__DOT__top_module1__DOT__state),3);
        bufp->chgCData(oldp+112,(vlSelfRef.tb__DOT__top_module1__DOT__dcnt),4);
        bufp->chgCData(oldp+113,(vlSelfRef.tb__DOT__top_module1__DOT__sa_00),8);
        bufp->chgCData(oldp+114,(vlSelfRef.tb__DOT__top_module1__DOT__sa_01),8);
        bufp->chgCData(oldp+115,(vlSelfRef.tb__DOT__top_module1__DOT__sa_02),8);
        bufp->chgCData(oldp+116,(vlSelfRef.tb__DOT__top_module1__DOT__sa_03),8);
        bufp->chgCData(oldp+117,(vlSelfRef.tb__DOT__top_module1__DOT__sa_10),8);
        bufp->chgCData(oldp+118,(vlSelfRef.tb__DOT__top_module1__DOT__sa_11),8);
        bufp->chgCData(oldp+119,(vlSelfRef.tb__DOT__top_module1__DOT__sa_12),8);
        bufp->chgCData(oldp+120,(vlSelfRef.tb__DOT__top_module1__DOT__sa_13),8);
        bufp->chgCData(oldp+121,(vlSelfRef.tb__DOT__top_module1__DOT__sa_20),8);
        bufp->chgCData(oldp+122,(vlSelfRef.tb__DOT__top_module1__DOT__sa_21),8);
        bufp->chgCData(oldp+123,(vlSelfRef.tb__DOT__top_module1__DOT__sa_22),8);
        bufp->chgCData(oldp+124,(vlSelfRef.tb__DOT__top_module1__DOT__sa_23),8);
        bufp->chgCData(oldp+125,(vlSelfRef.tb__DOT__top_module1__DOT__sa_30),8);
        bufp->chgCData(oldp+126,(vlSelfRef.tb__DOT__top_module1__DOT__sa_31),8);
        bufp->chgCData(oldp+127,(vlSelfRef.tb__DOT__top_module1__DOT__sa_32),8);
        bufp->chgCData(oldp+128,(vlSelfRef.tb__DOT__top_module1__DOT__sa_33),8);
        bufp->chgBit(oldp+129,(vlSelfRef.tb__DOT__top_module1__DOT__kld));
        bufp->chgIData(oldp+130,(vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                 [0U]),32);
        bufp->chgIData(oldp+131,(vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                 [1U]),32);
        bufp->chgIData(oldp+132,(vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                 [2U]),32);
        bufp->chgIData(oldp+133,(vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                 [3U]),32);
        __Vtemp_7[0U] = vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
            [3U];
        __Vtemp_7[1U] = vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
            [2U];
        __Vtemp_7[2U] = (IData)((((QData)((IData)(vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                                  [0U])) 
                                  << 0x00000020U) | (QData)((IData)(
                                                                    vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                                                    [1U]))));
        __Vtemp_7[3U] = (IData)(((((QData)((IData)(
                                                   vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                                   [0U])) 
                                   << 0x00000020U) 
                                  | (QData)((IData)(
                                                    vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                                    [1U]))) 
                                 >> 0x00000020U));
        bufp->chgWData(oldp+134,(__Vtemp_7),128);
        bufp->chgBit(oldp+138,((2U != (IData)(vlSelfRef.tb__DOT__top_module1__DOT__state))));
        bufp->chgIData(oldp+139,(vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w[0]),32);
        bufp->chgIData(oldp+140,(vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w[1]),32);
        bufp->chgIData(oldp+141,(vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w[2]),32);
        bufp->chgIData(oldp+142,(vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w[3]),32);
        bufp->chgCData(oldp+143,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                                 [3U] 
                                                 >> 0x00000010U))),8);
        bufp->chgCData(oldp+144,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                                 [3U] 
                                                 >> 8U))),8);
        bufp->chgCData(oldp+145,((0x000000ffU & vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                  [3U])),8);
        bufp->chgCData(oldp+146,((vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                  [3U] >> 0x00000018U)),8);
        bufp->chgCData(oldp+147,((0x000000ffU & (vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                                 [3U] 
                                                 >> 0x00000010U))),8);
        bufp->chgCData(oldp+148,((0x000000ffU & (vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                                 [3U] 
                                                 >> 8U))),8);
        bufp->chgCData(oldp+149,((0x000000ffU & vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                  [3U])),8);
        bufp->chgCData(oldp+150,((vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__w
                                  [3U] >> 0x00000018U)),8);
    }
    if (VL_UNLIKELY((vlSelfRef.__Vm_traceActivity[5U]))) {
        bufp->chgCData(oldp+151,(vlSelfRef.tb__DOT__top_module1__DOT__mc_03),8);
        bufp->chgCData(oldp+152,(vlSelfRef.tb__DOT__top_module1__DOT__mc_13),8);
        bufp->chgCData(oldp+153,(vlSelfRef.tb__DOT__top_module1__DOT__mc_23),8);
        bufp->chgCData(oldp+154,(vlSelfRef.tb__DOT__top_module1__DOT__mc_33),8);
    }
    if (VL_UNLIKELY((vlSelfRef.__Vm_traceActivity[6U]))) {
        bufp->chgCData(oldp+155,(vlSelfRef.tb__DOT__top_module1__DOT__mc_02),8);
        bufp->chgCData(oldp+156,(vlSelfRef.tb__DOT__top_module1__DOT__mc_12),8);
        bufp->chgCData(oldp+157,(vlSelfRef.tb__DOT__top_module1__DOT__mc_22),8);
        bufp->chgCData(oldp+158,(vlSelfRef.tb__DOT__top_module1__DOT__mc_32),8);
    }
    if (VL_UNLIKELY((vlSelfRef.__Vm_traceActivity[7U]))) {
        bufp->chgCData(oldp+159,(vlSelfRef.tb__DOT__top_module1__DOT__mc_01),8);
        bufp->chgCData(oldp+160,(vlSelfRef.tb__DOT__top_module1__DOT__mc_11),8);
        bufp->chgCData(oldp+161,(vlSelfRef.tb__DOT__top_module1__DOT__mc_21),8);
        bufp->chgCData(oldp+162,(vlSelfRef.tb__DOT__top_module1__DOT__mc_31),8);
    }
    if (VL_UNLIKELY((vlSelfRef.__Vm_traceActivity[8U]))) {
        bufp->chgCData(oldp+163,(vlSelfRef.tb__DOT__top_module1__DOT__mc_00),8);
        bufp->chgCData(oldp+164,(vlSelfRef.tb__DOT__top_module1__DOT__mc_10),8);
        bufp->chgCData(oldp+165,(vlSelfRef.tb__DOT__top_module1__DOT__mc_20),8);
        bufp->chgCData(oldp+166,(vlSelfRef.tb__DOT__top_module1__DOT__mc_30),8);
    }
    if (VL_UNLIKELY((vlSelfRef.__Vm_traceActivity[9U]))) {
        bufp->chgCData(oldp+167,((vlSelfRef.tb__DOT__good1__DOT__mix_col_out0 
                                  >> 0x00000018U)),8);
        bufp->chgCData(oldp+168,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__mix_col_out0 
                                                 >> 0x00000010U))),8);
        bufp->chgCData(oldp+169,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__mix_col_out0 
                                                 >> 8U))),8);
        bufp->chgCData(oldp+170,((0x000000ffU & vlSelfRef.tb__DOT__good1__DOT__mix_col_out0)),8);
        bufp->chgIData(oldp+171,(vlSelfRef.tb__DOT__good1__DOT__mix_col_out0),32);
    }
    if (VL_UNLIKELY((vlSelfRef.__Vm_traceActivity[0x0000000aU]))) {
        bufp->chgCData(oldp+172,((vlSelfRef.tb__DOT__good1__DOT__mix_col_out1 
                                  >> 0x00000018U)),8);
        bufp->chgCData(oldp+173,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__mix_col_out1 
                                                 >> 0x00000010U))),8);
        bufp->chgCData(oldp+174,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__mix_col_out1 
                                                 >> 8U))),8);
        bufp->chgCData(oldp+175,((0x000000ffU & vlSelfRef.tb__DOT__good1__DOT__mix_col_out1)),8);
        bufp->chgIData(oldp+176,(vlSelfRef.tb__DOT__good1__DOT__mix_col_out1),32);
    }
    if (VL_UNLIKELY((vlSelfRef.__Vm_traceActivity[0x0000000bU]))) {
        bufp->chgCData(oldp+177,((vlSelfRef.tb__DOT__good1__DOT__mix_col_out2 
                                  >> 0x00000018U)),8);
        bufp->chgCData(oldp+178,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__mix_col_out2 
                                                 >> 0x00000010U))),8);
        bufp->chgCData(oldp+179,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__mix_col_out2 
                                                 >> 8U))),8);
        bufp->chgCData(oldp+180,((0x000000ffU & vlSelfRef.tb__DOT__good1__DOT__mix_col_out2)),8);
        bufp->chgIData(oldp+181,(vlSelfRef.tb__DOT__good1__DOT__mix_col_out2),32);
    }
    if (VL_UNLIKELY((vlSelfRef.__Vm_traceActivity[0x0000000cU]))) {
        bufp->chgCData(oldp+182,((vlSelfRef.tb__DOT__good1__DOT__mix_col_out3 
                                  >> 0x00000018U)),8);
        bufp->chgCData(oldp+183,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__mix_col_out3 
                                                 >> 0x00000010U))),8);
        bufp->chgCData(oldp+184,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__mix_col_out3 
                                                 >> 8U))),8);
        bufp->chgCData(oldp+185,((0x000000ffU & vlSelfRef.tb__DOT__good1__DOT__mix_col_out3)),8);
        bufp->chgIData(oldp+186,(vlSelfRef.tb__DOT__good1__DOT__mix_col_out3),32);
    }
    if (VL_UNLIKELY((vlSelfRef.__Vm_traceActivity[0x0000000dU]))) {
        bufp->chgWData(oldp+187,(vlSelfRef.tb__DOT__top_module1__DOT__add_rkey_out),128);
        bufp->chgWData(oldp+191,(vlSelfRef.tb__DOT__top_module1__DOT__round_data),128);
    }
    bufp->chgBit(oldp+195,(vlSelfRef.tb__DOT__clk));
    bufp->chgCData(oldp+196,(((vlSelfRef.tb__DOT__good1__DOT__mix_col_out0 
                               ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                               [0U]) >> 0x00000018U)),8);
    bufp->chgCData(oldp+197,(((vlSelfRef.tb__DOT__good1__DOT__mix_col_out1 
                               ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                               [1U]) >> 0x00000018U)),8);
    bufp->chgCData(oldp+198,(((vlSelfRef.tb__DOT__good1__DOT__mix_col_out2 
                               ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                               [2U]) >> 0x00000018U)),8);
    bufp->chgCData(oldp+199,(((vlSelfRef.tb__DOT__good1__DOT__mix_col_out3 
                               ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                               [3U]) >> 0x00000018U)),8);
    bufp->chgCData(oldp+200,((0x000000ffU & ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out0 
                                              ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                              [0U]) 
                                             >> 0x00000010U))),8);
    bufp->chgCData(oldp+201,((0x000000ffU & ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out1 
                                              ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                              [1U]) 
                                             >> 0x00000010U))),8);
    bufp->chgCData(oldp+202,((0x000000ffU & ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out2 
                                              ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                              [2U]) 
                                             >> 0x00000010U))),8);
    bufp->chgCData(oldp+203,((0x000000ffU & ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out3 
                                              ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                              [3U]) 
                                             >> 0x00000010U))),8);
    bufp->chgCData(oldp+204,((0x000000ffU & ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out0 
                                              ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                              [0U]) 
                                             >> 8U))),8);
    bufp->chgCData(oldp+205,((0x000000ffU & ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out1 
                                              ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                              [1U]) 
                                             >> 8U))),8);
    bufp->chgCData(oldp+206,((0x000000ffU & ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out2 
                                              ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                              [2U]) 
                                             >> 8U))),8);
    bufp->chgCData(oldp+207,((0x000000ffU & ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out3 
                                              ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                              [3U]) 
                                             >> 8U))),8);
    bufp->chgCData(oldp+208,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__mix_col_out0 
                                             ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                             [0U]))),8);
    bufp->chgCData(oldp+209,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__mix_col_out1 
                                             ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                             [1U]))),8);
    bufp->chgCData(oldp+210,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__mix_col_out2 
                                             ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                             [2U]))),8);
    bufp->chgCData(oldp+211,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__mix_col_out3 
                                             ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                             [3U]))),8);
    bufp->chgCData(oldp+212,(vlSymsp->TOP__tb__DOT__good1__DOT__us00.b),8);
    bufp->chgCData(oldp+213,(vlSymsp->TOP__tb__DOT__good1__DOT__us01.b),8);
    bufp->chgCData(oldp+214,(vlSymsp->TOP__tb__DOT__good1__DOT__us02.b),8);
    bufp->chgCData(oldp+215,(vlSymsp->TOP__tb__DOT__good1__DOT__us03.b),8);
    bufp->chgCData(oldp+216,(vlSymsp->TOP__tb__DOT__good1__DOT__us10.b),8);
    bufp->chgCData(oldp+217,(vlSymsp->TOP__tb__DOT__good1__DOT__us11.b),8);
    bufp->chgCData(oldp+218,(vlSymsp->TOP__tb__DOT__good1__DOT__us12.b),8);
    bufp->chgCData(oldp+219,(vlSymsp->TOP__tb__DOT__good1__DOT__us13.b),8);
    bufp->chgCData(oldp+220,(vlSymsp->TOP__tb__DOT__good1__DOT__us20.b),8);
    bufp->chgCData(oldp+221,(vlSymsp->TOP__tb__DOT__good1__DOT__us21.b),8);
    bufp->chgCData(oldp+222,(vlSymsp->TOP__tb__DOT__good1__DOT__us22.b),8);
    bufp->chgCData(oldp+223,(vlSymsp->TOP__tb__DOT__good1__DOT__us23.b),8);
    bufp->chgCData(oldp+224,(vlSymsp->TOP__tb__DOT__good1__DOT__us30.b),8);
    bufp->chgCData(oldp+225,(vlSymsp->TOP__tb__DOT__good1__DOT__us31.b),8);
    bufp->chgCData(oldp+226,(vlSymsp->TOP__tb__DOT__good1__DOT__us32.b),8);
    bufp->chgCData(oldp+227,(vlSymsp->TOP__tb__DOT__good1__DOT__us33.b),8);
    bufp->chgIData(oldp+228,(vlSelfRef.tb__DOT__good1__DOT__u0__DOT__subword),32);
    bufp->chgCData(oldp+229,(vlSelfRef.tb__DOT__top_module1__DOT__next_state),3);
    bufp->chgBit(oldp+230,(vlSelfRef.tb__DOT__top_module1__DOT__ld_cap));
    bufp->chgCData(oldp+231,(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_00.b),8);
    bufp->chgCData(oldp+232,(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_01.b),8);
    bufp->chgCData(oldp+233,(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_02.b),8);
    bufp->chgCData(oldp+234,(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_03.b),8);
    bufp->chgCData(oldp+235,(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_10.b),8);
    bufp->chgCData(oldp+236,(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_11.b),8);
    bufp->chgCData(oldp+237,(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_12.b),8);
    bufp->chgCData(oldp+238,(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_13.b),8);
    bufp->chgCData(oldp+239,(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_20.b),8);
    bufp->chgCData(oldp+240,(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_21.b),8);
    bufp->chgCData(oldp+241,(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_22.b),8);
    bufp->chgCData(oldp+242,(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_23.b),8);
    bufp->chgCData(oldp+243,(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_30.b),8);
    bufp->chgCData(oldp+244,(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_31.b),8);
    bufp->chgCData(oldp+245,(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_32.b),8);
    bufp->chgCData(oldp+246,(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_33.b),8);
    __Vtemp_9[0U] = ((((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_00.b) 
                       << 0x00000018U) | ((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_10.b) 
                                          << 0x00000010U)) 
                     | (((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_20.b) 
                         << 8U) | (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_30.b)));
    __Vtemp_9[1U] = ((((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_01.b) 
                       << 0x00000018U) | ((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_11.b) 
                                          << 0x00000010U)) 
                     | (((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_21.b) 
                         << 8U) | (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_31.b)));
    __Vtemp_9[2U] = (IData)((((QData)((IData)(((((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_03.b) 
                                                 << 0x00000018U) 
                                                | ((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_13.b) 
                                                   << 0x00000010U)) 
                                               | (((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_23.b) 
                                                   << 8U) 
                                                  | (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_33.b))))) 
                              << 0x00000020U) | (QData)((IData)(
                                                                ((((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_02.b) 
                                                                   << 0x00000018U) 
                                                                  | ((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_12.b) 
                                                                     << 0x00000010U)) 
                                                                 | (((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_22.b) 
                                                                     << 8U) 
                                                                    | (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_32.b)))))));
    __Vtemp_9[3U] = (IData)(((((QData)((IData)(((((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_03.b) 
                                                  << 0x00000018U) 
                                                 | ((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_13.b) 
                                                    << 0x00000010U)) 
                                                | (((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_23.b) 
                                                    << 8U) 
                                                   | (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_33.b))))) 
                               << 0x00000020U) | (QData)((IData)(
                                                                 ((((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_02.b) 
                                                                    << 0x00000018U) 
                                                                   | ((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_12.b) 
                                                                      << 0x00000010U)) 
                                                                  | (((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_22.b) 
                                                                      << 8U) 
                                                                     | (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_32.b)))))) 
                             >> 0x00000020U));
    bufp->chgWData(oldp+247,(__Vtemp_9),128);
    __Vtemp_11[0U] = ((((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_00.b) 
                        << 0x00000018U) | ((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_11.b) 
                                           << 0x00000010U)) 
                      | (((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_22.b) 
                          << 8U) | (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_33.b)));
    __Vtemp_11[1U] = ((((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_01.b) 
                        << 0x00000018U) | ((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_12.b) 
                                           << 0x00000010U)) 
                      | (((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_23.b) 
                          << 8U) | (IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_30.b)));
    __Vtemp_11[2U] = (IData)((((QData)((IData)(((((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_03.b) 
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
    __Vtemp_11[3U] = (IData)(((((QData)((IData)(((((IData)(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_sbox_03.b) 
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
    bufp->chgWData(oldp+251,(__Vtemp_11),128);
    __Vtemp_13[0U] = ((((IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_00) 
                        << 0x00000018U) | ((IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_10) 
                                           << 0x00000010U)) 
                      | (((IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_20) 
                          << 8U) | (IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_30)));
    __Vtemp_13[1U] = ((((IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_01) 
                        << 0x00000018U) | ((IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_11) 
                                           << 0x00000010U)) 
                      | (((IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_21) 
                          << 8U) | (IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_31)));
    __Vtemp_13[2U] = (IData)((((QData)((IData)(((((IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_03) 
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
    __Vtemp_13[3U] = (IData)(((((QData)((IData)(((((IData)(vlSelfRef.tb__DOT__top_module1__DOT__mc_03) 
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
    bufp->chgWData(oldp+255,(__Vtemp_13),128);
    bufp->chgIData(oldp+259,(vlSelfRef.tb__DOT__top_module1__DOT__u_key_expand__DOT__subword),32);
    bufp->chgCData(oldp+260,(vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u0.b),8);
    bufp->chgCData(oldp+261,(vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u1.b),8);
    bufp->chgCData(oldp+262,(vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u2.b),8);
    bufp->chgCData(oldp+263,(vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u3.b),8);
    bufp->chgCData(oldp+264,(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u0.b),8);
    bufp->chgCData(oldp+265,(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u1.b),8);
    bufp->chgCData(oldp+266,(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u2.b),8);
    bufp->chgCData(oldp+267,(vlSymsp->TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u3.b),8);
}

void Vtb___024root__trace_cleanup(void* voidSelf, VerilatedVcd* /*unused*/) {
    VL_DEBUG_IF(VL_DBG_MSGF("+    Vtb___024root__trace_cleanup\n"); );
    // Body
    Vtb___024root* const __restrict vlSelf VL_ATTR_UNUSED = static_cast<Vtb___024root*>(voidSelf);
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    vlSymsp->__Vm_activity = false;
    vlSymsp->TOP.__Vm_traceActivity[0U] = 0U;
    vlSymsp->TOP.__Vm_traceActivity[1U] = 0U;
    vlSymsp->TOP.__Vm_traceActivity[2U] = 0U;
    vlSymsp->TOP.__Vm_traceActivity[3U] = 0U;
    vlSymsp->TOP.__Vm_traceActivity[4U] = 0U;
    vlSymsp->TOP.__Vm_traceActivity[5U] = 0U;
    vlSymsp->TOP.__Vm_traceActivity[6U] = 0U;
    vlSymsp->TOP.__Vm_traceActivity[7U] = 0U;
    vlSymsp->TOP.__Vm_traceActivity[8U] = 0U;
    vlSymsp->TOP.__Vm_traceActivity[9U] = 0U;
    vlSymsp->TOP.__Vm_traceActivity[0x0000000aU] = 0U;
    vlSymsp->TOP.__Vm_traceActivity[0x0000000bU] = 0U;
    vlSymsp->TOP.__Vm_traceActivity[0x0000000cU] = 0U;
    vlSymsp->TOP.__Vm_traceActivity[0x0000000dU] = 0U;
}
