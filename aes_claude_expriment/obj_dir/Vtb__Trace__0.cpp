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
    if (VL_UNLIKELY(((vlSelfRef.__Vm_traceActivity[3U] 
                      | vlSelfRef.__Vm_traceActivity
                      [5U])))) {
        bufp->chgCData(oldp+55,(vlSelfRef.tb__DOT__top_module1__DOT__init_ark
                                [0U][0U]),8);
        bufp->chgCData(oldp+56,(vlSelfRef.tb__DOT__top_module1__DOT__init_ark
                                [0U][1U]),8);
        bufp->chgCData(oldp+57,(vlSelfRef.tb__DOT__top_module1__DOT__init_ark
                                [0U][2U]),8);
        bufp->chgCData(oldp+58,(vlSelfRef.tb__DOT__top_module1__DOT__init_ark
                                [0U][3U]),8);
        bufp->chgCData(oldp+59,(vlSelfRef.tb__DOT__top_module1__DOT__init_ark
                                [1U][0U]),8);
        bufp->chgCData(oldp+60,(vlSelfRef.tb__DOT__top_module1__DOT__init_ark
                                [1U][1U]),8);
        bufp->chgCData(oldp+61,(vlSelfRef.tb__DOT__top_module1__DOT__init_ark
                                [1U][2U]),8);
        bufp->chgCData(oldp+62,(vlSelfRef.tb__DOT__top_module1__DOT__init_ark
                                [1U][3U]),8);
        bufp->chgCData(oldp+63,(vlSelfRef.tb__DOT__top_module1__DOT__init_ark
                                [2U][0U]),8);
        bufp->chgCData(oldp+64,(vlSelfRef.tb__DOT__top_module1__DOT__init_ark
                                [2U][1U]),8);
        bufp->chgCData(oldp+65,(vlSelfRef.tb__DOT__top_module1__DOT__init_ark
                                [2U][2U]),8);
        bufp->chgCData(oldp+66,(vlSelfRef.tb__DOT__top_module1__DOT__init_ark
                                [2U][3U]),8);
        bufp->chgCData(oldp+67,(vlSelfRef.tb__DOT__top_module1__DOT__init_ark
                                [3U][0U]),8);
        bufp->chgCData(oldp+68,(vlSelfRef.tb__DOT__top_module1__DOT__init_ark
                                [3U][1U]),8);
        bufp->chgCData(oldp+69,(vlSelfRef.tb__DOT__top_module1__DOT__init_ark
                                [3U][2U]),8);
        bufp->chgCData(oldp+70,(vlSelfRef.tb__DOT__top_module1__DOT__init_ark
                                [3U][3U]),8);
    }
    if (VL_UNLIKELY((vlSelfRef.__Vm_traceActivity[4U]))) {
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
        bufp->chgWData(oldp+71,(__Vtemp_5),224);
        bufp->chgBit(oldp+78,(vlSelfRef.tb__DOT__done_ref));
        bufp->chgBit(oldp+79,(vlSelfRef.tb__DOT__top_module1__DOT__done_r));
        bufp->chgWData(oldp+80,(vlSelfRef.tb__DOT__text_out_ref),128);
        bufp->chgWData(oldp+84,(vlSelfRef.tb__DOT__top_module1__DOT__text_out_r),128);
        bufp->chgBit(oldp+88,(vlSelfRef.tb__DOT__tb_match_text));
        bufp->chgBit(oldp+89,(vlSelfRef.tb__DOT__tb_match_done));
        bufp->chgBit(oldp+90,(((IData)(vlSelfRef.tb__DOT__tb_match_text) 
                               & (IData)(vlSelfRef.tb__DOT__tb_match_done))));
        bufp->chgCData(oldp+91,(vlSelfRef.tb__DOT__good1__DOT__dcnt),4);
        bufp->chgIData(oldp+92,(vlSelfRef.tb__DOT__good1__DOT__u0__DOT__rcon),32);
        bufp->chgCData(oldp+93,(vlSelfRef.tb__DOT__good1__DOT__u0__DOT__r0__DOT__rcnt),4);
        bufp->chgCData(oldp+94,((0x0000000fU & ((IData)(1U) 
                                                + (IData)(vlSelfRef.tb__DOT__good1__DOT__u0__DOT__r0__DOT__rcnt)))),4);
        bufp->chgCData(oldp+95,(vlSelfRef.tb__DOT__top_module1__DOT__state),3);
        bufp->chgCData(oldp+96,(vlSelfRef.tb__DOT__top_module1__DOT__dcnt),4);
        bufp->chgBit(oldp+97,(vlSelfRef.tb__DOT__top_module1__DOT__kld));
        bufp->chgIData(oldp+98,(vlSelfRef.tb__DOT__top_module1__DOT__i),32);
        bufp->chgIData(oldp+99,(vlSelfRef.tb__DOT__top_module1__DOT__j),32);
        bufp->chgIData(oldp+100,(vlSelfRef.tb__DOT__top_module1__DOT__key_expand__DOT__rcon),32);
        bufp->chgCData(oldp+101,(vlSelfRef.tb__DOT__top_module1__DOT__key_expand__DOT__r0__DOT__rcnt),4);
        bufp->chgCData(oldp+102,((0x0000000fU & ((IData)(1U) 
                                                 + (IData)(vlSelfRef.tb__DOT__top_module1__DOT__key_expand__DOT__r0__DOT__rcnt)))),4);
    }
    if (VL_UNLIKELY((vlSelfRef.__Vm_traceActivity[6U]))) {
        bufp->chgIData(oldp+103,(vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                 [0U]),32);
        bufp->chgIData(oldp+104,(vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                 [1U]),32);
        bufp->chgIData(oldp+105,(vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                 [2U]),32);
        bufp->chgIData(oldp+106,(vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                 [3U]),32);
        bufp->chgWData(oldp+107,(vlSelfRef.tb__DOT__good1__DOT__text_in_r),128);
        bufp->chgCData(oldp+111,(vlSelfRef.tb__DOT__good1__DOT__sa00),8);
        bufp->chgCData(oldp+112,(vlSelfRef.tb__DOT__good1__DOT__sa01),8);
        bufp->chgCData(oldp+113,(vlSelfRef.tb__DOT__good1__DOT__sa02),8);
        bufp->chgCData(oldp+114,(vlSelfRef.tb__DOT__good1__DOT__sa03),8);
        bufp->chgCData(oldp+115,(vlSelfRef.tb__DOT__good1__DOT__sa10),8);
        bufp->chgCData(oldp+116,(vlSelfRef.tb__DOT__good1__DOT__sa11),8);
        bufp->chgCData(oldp+117,(vlSelfRef.tb__DOT__good1__DOT__sa12),8);
        bufp->chgCData(oldp+118,(vlSelfRef.tb__DOT__good1__DOT__sa13),8);
        bufp->chgCData(oldp+119,(vlSelfRef.tb__DOT__good1__DOT__sa20),8);
        bufp->chgCData(oldp+120,(vlSelfRef.tb__DOT__good1__DOT__sa21),8);
        bufp->chgCData(oldp+121,(vlSelfRef.tb__DOT__good1__DOT__sa22),8);
        bufp->chgCData(oldp+122,(vlSelfRef.tb__DOT__good1__DOT__sa23),8);
        bufp->chgCData(oldp+123,(vlSelfRef.tb__DOT__good1__DOT__sa30),8);
        bufp->chgCData(oldp+124,(vlSelfRef.tb__DOT__good1__DOT__sa31),8);
        bufp->chgCData(oldp+125,(vlSelfRef.tb__DOT__good1__DOT__sa32),8);
        bufp->chgCData(oldp+126,(vlSelfRef.tb__DOT__good1__DOT__sa33),8);
        bufp->chgBit(oldp+127,(vlSelfRef.tb__DOT__good1__DOT__ld_r));
        bufp->chgIData(oldp+128,(vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w[0]),32);
        bufp->chgIData(oldp+129,(vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w[1]),32);
        bufp->chgIData(oldp+130,(vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w[2]),32);
        bufp->chgIData(oldp+131,(vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w[3]),32);
        bufp->chgCData(oldp+132,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [0U][0U]),8);
        bufp->chgCData(oldp+133,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [0U][1U]),8);
        bufp->chgCData(oldp+134,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [0U][2U]),8);
        bufp->chgCData(oldp+135,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [0U][3U]),8);
        bufp->chgCData(oldp+136,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [1U][0U]),8);
        bufp->chgCData(oldp+137,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [1U][1U]),8);
        bufp->chgCData(oldp+138,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [1U][2U]),8);
        bufp->chgCData(oldp+139,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [1U][3U]),8);
        bufp->chgCData(oldp+140,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [2U][0U]),8);
        bufp->chgCData(oldp+141,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [2U][1U]),8);
        bufp->chgCData(oldp+142,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [2U][2U]),8);
        bufp->chgCData(oldp+143,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [2U][3U]),8);
        bufp->chgCData(oldp+144,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [3U][0U]),8);
        bufp->chgCData(oldp+145,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [3U][1U]),8);
        bufp->chgCData(oldp+146,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [3U][2U]),8);
        bufp->chgCData(oldp+147,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [3U][3U]),8);
        bufp->chgIData(oldp+148,(vlSelfRef.tb__DOT__top_module1__DOT__key_expand__DOT__w
                                 [0U]),32);
        bufp->chgIData(oldp+149,(vlSelfRef.tb__DOT__top_module1__DOT__key_expand__DOT__w
                                 [1U]),32);
        bufp->chgIData(oldp+150,(vlSelfRef.tb__DOT__top_module1__DOT__key_expand__DOT__w
                                 [2U]),32);
        bufp->chgIData(oldp+151,(vlSelfRef.tb__DOT__top_module1__DOT__key_expand__DOT__w
                                 [3U]),32);
        bufp->chgIData(oldp+152,(vlSelfRef.tb__DOT__top_module1__DOT__key_expand__DOT__w[0]),32);
        bufp->chgIData(oldp+153,(vlSelfRef.tb__DOT__top_module1__DOT__key_expand__DOT__w[1]),32);
        bufp->chgIData(oldp+154,(vlSelfRef.tb__DOT__top_module1__DOT__key_expand__DOT__w[2]),32);
        bufp->chgIData(oldp+155,(vlSelfRef.tb__DOT__top_module1__DOT__key_expand__DOT__w[3]),32);
        bufp->chgCData(oldp+156,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                                 [3U] 
                                                 >> 0x00000010U))),8);
        bufp->chgCData(oldp+157,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                                 [3U] 
                                                 >> 8U))),8);
        bufp->chgCData(oldp+158,((0x000000ffU & vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                  [3U])),8);
        bufp->chgCData(oldp+159,((vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                  [3U] >> 0x00000018U)),8);
        bufp->chgCData(oldp+160,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [0U][0U]),8);
        bufp->chgCData(oldp+161,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [0U][1U]),8);
        bufp->chgCData(oldp+162,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [0U][2U]),8);
        bufp->chgCData(oldp+163,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [0U][3U]),8);
        bufp->chgCData(oldp+164,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [1U][0U]),8);
        bufp->chgCData(oldp+165,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [1U][1U]),8);
        bufp->chgCData(oldp+166,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [1U][2U]),8);
        bufp->chgCData(oldp+167,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [1U][3U]),8);
        bufp->chgCData(oldp+168,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [2U][0U]),8);
        bufp->chgCData(oldp+169,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [2U][1U]),8);
        bufp->chgCData(oldp+170,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [2U][2U]),8);
        bufp->chgCData(oldp+171,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [2U][3U]),8);
        bufp->chgCData(oldp+172,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [3U][0U]),8);
        bufp->chgCData(oldp+173,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [3U][1U]),8);
        bufp->chgCData(oldp+174,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [3U][2U]),8);
        bufp->chgCData(oldp+175,(vlSelfRef.tb__DOT__top_module1__DOT__sa
                                 [3U][3U]),8);
        bufp->chgCData(oldp+176,((0x000000ffU & (vlSelfRef.tb__DOT__top_module1__DOT__key_expand__DOT__w
                                                 [3U] 
                                                 >> 0x00000010U))),8);
        bufp->chgCData(oldp+177,((0x000000ffU & (vlSelfRef.tb__DOT__top_module1__DOT__key_expand__DOT__w
                                                 [3U] 
                                                 >> 8U))),8);
        bufp->chgCData(oldp+178,((0x000000ffU & vlSelfRef.tb__DOT__top_module1__DOT__key_expand__DOT__w
                                  [3U])),8);
        bufp->chgCData(oldp+179,((vlSelfRef.tb__DOT__top_module1__DOT__key_expand__DOT__w
                                  [3U] >> 0x00000018U)),8);
    }
    if (VL_UNLIKELY((vlSelfRef.__Vm_traceActivity[7U]))) {
        bufp->chgCData(oldp+180,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [0U][0U]),8);
        bufp->chgCData(oldp+181,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [0U][1U]),8);
        bufp->chgCData(oldp+182,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [0U][2U]),8);
        bufp->chgCData(oldp+183,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [0U][3U]),8);
        bufp->chgCData(oldp+184,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [1U][0U]),8);
        bufp->chgCData(oldp+185,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [1U][1U]),8);
        bufp->chgCData(oldp+186,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [1U][2U]),8);
        bufp->chgCData(oldp+187,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [1U][3U]),8);
        bufp->chgCData(oldp+188,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [2U][0U]),8);
        bufp->chgCData(oldp+189,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [2U][1U]),8);
        bufp->chgCData(oldp+190,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [2U][2U]),8);
        bufp->chgCData(oldp+191,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [2U][3U]),8);
        bufp->chgCData(oldp+192,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [3U][0U]),8);
        bufp->chgCData(oldp+193,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [3U][1U]),8);
        bufp->chgCData(oldp+194,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [3U][2U]),8);
        bufp->chgCData(oldp+195,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [3U][3U]),8);
        bufp->chgCData(oldp+196,(vlSelfRef.tb__DOT__top_module1__DOT__mc
                                 [0U][0U]),8);
        bufp->chgCData(oldp+197,(vlSelfRef.tb__DOT__top_module1__DOT__mc
                                 [0U][1U]),8);
        bufp->chgCData(oldp+198,(vlSelfRef.tb__DOT__top_module1__DOT__mc
                                 [0U][2U]),8);
        bufp->chgCData(oldp+199,(vlSelfRef.tb__DOT__top_module1__DOT__mc
                                 [0U][3U]),8);
        bufp->chgCData(oldp+200,(vlSelfRef.tb__DOT__top_module1__DOT__mc
                                 [1U][0U]),8);
        bufp->chgCData(oldp+201,(vlSelfRef.tb__DOT__top_module1__DOT__mc
                                 [1U][1U]),8);
        bufp->chgCData(oldp+202,(vlSelfRef.tb__DOT__top_module1__DOT__mc
                                 [1U][2U]),8);
        bufp->chgCData(oldp+203,(vlSelfRef.tb__DOT__top_module1__DOT__mc
                                 [1U][3U]),8);
        bufp->chgCData(oldp+204,(vlSelfRef.tb__DOT__top_module1__DOT__mc
                                 [2U][0U]),8);
        bufp->chgCData(oldp+205,(vlSelfRef.tb__DOT__top_module1__DOT__mc
                                 [2U][1U]),8);
        bufp->chgCData(oldp+206,(vlSelfRef.tb__DOT__top_module1__DOT__mc
                                 [2U][2U]),8);
        bufp->chgCData(oldp+207,(vlSelfRef.tb__DOT__top_module1__DOT__mc
                                 [2U][3U]),8);
        bufp->chgCData(oldp+208,(vlSelfRef.tb__DOT__top_module1__DOT__mc
                                 [3U][0U]),8);
        bufp->chgCData(oldp+209,(vlSelfRef.tb__DOT__top_module1__DOT__mc
                                 [3U][1U]),8);
        bufp->chgCData(oldp+210,(vlSelfRef.tb__DOT__top_module1__DOT__mc
                                 [3U][2U]),8);
        bufp->chgCData(oldp+211,(vlSelfRef.tb__DOT__top_module1__DOT__mc
                                 [3U][3U]),8);
        bufp->chgCData(oldp+212,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [0U][0U]),8);
        bufp->chgCData(oldp+213,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [0U][1U]),8);
        bufp->chgCData(oldp+214,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [0U][2U]),8);
        bufp->chgCData(oldp+215,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [0U][3U]),8);
        bufp->chgCData(oldp+216,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [1U][0U]),8);
        bufp->chgCData(oldp+217,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [1U][1U]),8);
        bufp->chgCData(oldp+218,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [1U][2U]),8);
        bufp->chgCData(oldp+219,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [1U][3U]),8);
        bufp->chgCData(oldp+220,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [2U][0U]),8);
        bufp->chgCData(oldp+221,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [2U][1U]),8);
        bufp->chgCData(oldp+222,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [2U][2U]),8);
        bufp->chgCData(oldp+223,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [2U][3U]),8);
        bufp->chgCData(oldp+224,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [3U][0U]),8);
        bufp->chgCData(oldp+225,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [3U][1U]),8);
        bufp->chgCData(oldp+226,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [3U][2U]),8);
        bufp->chgCData(oldp+227,(vlSelfRef.tb__DOT__top_module1__DOT__sr
                                 [3U][3U]),8);
    }
    if (VL_UNLIKELY((vlSelfRef.__Vm_traceActivity[8U]))) {
        bufp->chgCData(oldp+228,((vlSelfRef.tb__DOT__good1__DOT__mix_col_out0 
                                  >> 0x00000018U)),8);
        bufp->chgCData(oldp+229,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__mix_col_out0 
                                                 >> 0x00000010U))),8);
        bufp->chgCData(oldp+230,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__mix_col_out0 
                                                 >> 8U))),8);
        bufp->chgCData(oldp+231,((0x000000ffU & vlSelfRef.tb__DOT__good1__DOT__mix_col_out0)),8);
        bufp->chgIData(oldp+232,(vlSelfRef.tb__DOT__good1__DOT__mix_col_out0),32);
    }
    if (VL_UNLIKELY((vlSelfRef.__Vm_traceActivity[9U]))) {
        bufp->chgCData(oldp+233,((vlSelfRef.tb__DOT__good1__DOT__mix_col_out1 
                                  >> 0x00000018U)),8);
        bufp->chgCData(oldp+234,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__mix_col_out1 
                                                 >> 0x00000010U))),8);
        bufp->chgCData(oldp+235,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__mix_col_out1 
                                                 >> 8U))),8);
        bufp->chgCData(oldp+236,((0x000000ffU & vlSelfRef.tb__DOT__good1__DOT__mix_col_out1)),8);
        bufp->chgIData(oldp+237,(vlSelfRef.tb__DOT__good1__DOT__mix_col_out1),32);
    }
    if (VL_UNLIKELY((vlSelfRef.__Vm_traceActivity[0x0000000aU]))) {
        bufp->chgCData(oldp+238,((vlSelfRef.tb__DOT__good1__DOT__mix_col_out2 
                                  >> 0x00000018U)),8);
        bufp->chgCData(oldp+239,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__mix_col_out2 
                                                 >> 0x00000010U))),8);
        bufp->chgCData(oldp+240,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__mix_col_out2 
                                                 >> 8U))),8);
        bufp->chgCData(oldp+241,((0x000000ffU & vlSelfRef.tb__DOT__good1__DOT__mix_col_out2)),8);
        bufp->chgIData(oldp+242,(vlSelfRef.tb__DOT__good1__DOT__mix_col_out2),32);
    }
    if (VL_UNLIKELY((vlSelfRef.__Vm_traceActivity[0x0000000bU]))) {
        bufp->chgCData(oldp+243,((vlSelfRef.tb__DOT__good1__DOT__mix_col_out3 
                                  >> 0x00000018U)),8);
        bufp->chgCData(oldp+244,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__mix_col_out3 
                                                 >> 0x00000010U))),8);
        bufp->chgCData(oldp+245,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__mix_col_out3 
                                                 >> 8U))),8);
        bufp->chgCData(oldp+246,((0x000000ffU & vlSelfRef.tb__DOT__good1__DOT__mix_col_out3)),8);
        bufp->chgIData(oldp+247,(vlSelfRef.tb__DOT__good1__DOT__mix_col_out3),32);
    }
    if (VL_UNLIKELY((vlSelfRef.__Vm_traceActivity[0x0000000cU]))) {
        bufp->chgCData(oldp+248,(vlSelfRef.tb__DOT__top_module1__DOT__ark
                                 [0U][0U]),8);
        bufp->chgCData(oldp+249,(vlSelfRef.tb__DOT__top_module1__DOT__ark
                                 [0U][1U]),8);
        bufp->chgCData(oldp+250,(vlSelfRef.tb__DOT__top_module1__DOT__ark
                                 [0U][2U]),8);
        bufp->chgCData(oldp+251,(vlSelfRef.tb__DOT__top_module1__DOT__ark
                                 [0U][3U]),8);
        bufp->chgCData(oldp+252,(vlSelfRef.tb__DOT__top_module1__DOT__ark
                                 [1U][0U]),8);
        bufp->chgCData(oldp+253,(vlSelfRef.tb__DOT__top_module1__DOT__ark
                                 [1U][1U]),8);
        bufp->chgCData(oldp+254,(vlSelfRef.tb__DOT__top_module1__DOT__ark
                                 [1U][2U]),8);
        bufp->chgCData(oldp+255,(vlSelfRef.tb__DOT__top_module1__DOT__ark
                                 [1U][3U]),8);
        bufp->chgCData(oldp+256,(vlSelfRef.tb__DOT__top_module1__DOT__ark
                                 [2U][0U]),8);
        bufp->chgCData(oldp+257,(vlSelfRef.tb__DOT__top_module1__DOT__ark
                                 [2U][1U]),8);
        bufp->chgCData(oldp+258,(vlSelfRef.tb__DOT__top_module1__DOT__ark
                                 [2U][2U]),8);
        bufp->chgCData(oldp+259,(vlSelfRef.tb__DOT__top_module1__DOT__ark
                                 [2U][3U]),8);
        bufp->chgCData(oldp+260,(vlSelfRef.tb__DOT__top_module1__DOT__ark
                                 [3U][0U]),8);
        bufp->chgCData(oldp+261,(vlSelfRef.tb__DOT__top_module1__DOT__ark
                                 [3U][1U]),8);
        bufp->chgCData(oldp+262,(vlSelfRef.tb__DOT__top_module1__DOT__ark
                                 [3U][2U]),8);
        bufp->chgCData(oldp+263,(vlSelfRef.tb__DOT__top_module1__DOT__ark
                                 [3U][3U]),8);
        bufp->chgCData(oldp+264,(vlSelfRef.tb__DOT__top_module1__DOT__ark_final
                                 [0U][0U]),8);
        bufp->chgCData(oldp+265,(vlSelfRef.tb__DOT__top_module1__DOT__ark_final
                                 [0U][1U]),8);
        bufp->chgCData(oldp+266,(vlSelfRef.tb__DOT__top_module1__DOT__ark_final
                                 [0U][2U]),8);
        bufp->chgCData(oldp+267,(vlSelfRef.tb__DOT__top_module1__DOT__ark_final
                                 [0U][3U]),8);
        bufp->chgCData(oldp+268,(vlSelfRef.tb__DOT__top_module1__DOT__ark_final
                                 [1U][0U]),8);
        bufp->chgCData(oldp+269,(vlSelfRef.tb__DOT__top_module1__DOT__ark_final
                                 [1U][1U]),8);
        bufp->chgCData(oldp+270,(vlSelfRef.tb__DOT__top_module1__DOT__ark_final
                                 [1U][2U]),8);
        bufp->chgCData(oldp+271,(vlSelfRef.tb__DOT__top_module1__DOT__ark_final
                                 [1U][3U]),8);
        bufp->chgCData(oldp+272,(vlSelfRef.tb__DOT__top_module1__DOT__ark_final
                                 [2U][0U]),8);
        bufp->chgCData(oldp+273,(vlSelfRef.tb__DOT__top_module1__DOT__ark_final
                                 [2U][1U]),8);
        bufp->chgCData(oldp+274,(vlSelfRef.tb__DOT__top_module1__DOT__ark_final
                                 [2U][2U]),8);
        bufp->chgCData(oldp+275,(vlSelfRef.tb__DOT__top_module1__DOT__ark_final
                                 [2U][3U]),8);
        bufp->chgCData(oldp+276,(vlSelfRef.tb__DOT__top_module1__DOT__ark_final
                                 [3U][0U]),8);
        bufp->chgCData(oldp+277,(vlSelfRef.tb__DOT__top_module1__DOT__ark_final
                                 [3U][1U]),8);
        bufp->chgCData(oldp+278,(vlSelfRef.tb__DOT__top_module1__DOT__ark_final
                                 [3U][2U]),8);
        bufp->chgCData(oldp+279,(vlSelfRef.tb__DOT__top_module1__DOT__ark_final
                                 [3U][3U]),8);
    }
    bufp->chgBit(oldp+280,(vlSelfRef.tb__DOT__clk));
    bufp->chgCData(oldp+281,(((vlSelfRef.tb__DOT__good1__DOT__mix_col_out0 
                               ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                               [0U]) >> 0x00000018U)),8);
    bufp->chgCData(oldp+282,(((vlSelfRef.tb__DOT__good1__DOT__mix_col_out1 
                               ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                               [1U]) >> 0x00000018U)),8);
    bufp->chgCData(oldp+283,(((vlSelfRef.tb__DOT__good1__DOT__mix_col_out2 
                               ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                               [2U]) >> 0x00000018U)),8);
    bufp->chgCData(oldp+284,(((vlSelfRef.tb__DOT__good1__DOT__mix_col_out3 
                               ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                               [3U]) >> 0x00000018U)),8);
    bufp->chgCData(oldp+285,((0x000000ffU & ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out0 
                                              ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                              [0U]) 
                                             >> 0x00000010U))),8);
    bufp->chgCData(oldp+286,((0x000000ffU & ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out1 
                                              ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                              [1U]) 
                                             >> 0x00000010U))),8);
    bufp->chgCData(oldp+287,((0x000000ffU & ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out2 
                                              ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                              [2U]) 
                                             >> 0x00000010U))),8);
    bufp->chgCData(oldp+288,((0x000000ffU & ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out3 
                                              ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                              [3U]) 
                                             >> 0x00000010U))),8);
    bufp->chgCData(oldp+289,((0x000000ffU & ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out0 
                                              ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                              [0U]) 
                                             >> 8U))),8);
    bufp->chgCData(oldp+290,((0x000000ffU & ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out1 
                                              ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                              [1U]) 
                                             >> 8U))),8);
    bufp->chgCData(oldp+291,((0x000000ffU & ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out2 
                                              ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                              [2U]) 
                                             >> 8U))),8);
    bufp->chgCData(oldp+292,((0x000000ffU & ((vlSelfRef.tb__DOT__good1__DOT__mix_col_out3 
                                              ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                              [3U]) 
                                             >> 8U))),8);
    bufp->chgCData(oldp+293,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__mix_col_out0 
                                             ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                             [0U]))),8);
    bufp->chgCData(oldp+294,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__mix_col_out1 
                                             ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                             [1U]))),8);
    bufp->chgCData(oldp+295,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__mix_col_out2 
                                             ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                             [2U]))),8);
    bufp->chgCData(oldp+296,((0x000000ffU & (vlSelfRef.tb__DOT__good1__DOT__mix_col_out3 
                                             ^ vlSelfRef.tb__DOT__good1__DOT__u0__DOT__w
                                             [3U]))),8);
    bufp->chgCData(oldp+297,(vlSymsp->TOP__tb__DOT__good1__DOT__us00.b),8);
    bufp->chgCData(oldp+298,(vlSymsp->TOP__tb__DOT__good1__DOT__us01.b),8);
    bufp->chgCData(oldp+299,(vlSymsp->TOP__tb__DOT__good1__DOT__us02.b),8);
    bufp->chgCData(oldp+300,(vlSymsp->TOP__tb__DOT__good1__DOT__us03.b),8);
    bufp->chgCData(oldp+301,(vlSymsp->TOP__tb__DOT__good1__DOT__us10.b),8);
    bufp->chgCData(oldp+302,(vlSymsp->TOP__tb__DOT__good1__DOT__us11.b),8);
    bufp->chgCData(oldp+303,(vlSymsp->TOP__tb__DOT__good1__DOT__us12.b),8);
    bufp->chgCData(oldp+304,(vlSymsp->TOP__tb__DOT__good1__DOT__us13.b),8);
    bufp->chgCData(oldp+305,(vlSymsp->TOP__tb__DOT__good1__DOT__us20.b),8);
    bufp->chgCData(oldp+306,(vlSymsp->TOP__tb__DOT__good1__DOT__us21.b),8);
    bufp->chgCData(oldp+307,(vlSymsp->TOP__tb__DOT__good1__DOT__us22.b),8);
    bufp->chgCData(oldp+308,(vlSymsp->TOP__tb__DOT__good1__DOT__us23.b),8);
    bufp->chgCData(oldp+309,(vlSymsp->TOP__tb__DOT__good1__DOT__us30.b),8);
    bufp->chgCData(oldp+310,(vlSymsp->TOP__tb__DOT__good1__DOT__us31.b),8);
    bufp->chgCData(oldp+311,(vlSymsp->TOP__tb__DOT__good1__DOT__us32.b),8);
    bufp->chgCData(oldp+312,(vlSymsp->TOP__tb__DOT__good1__DOT__us33.b),8);
    bufp->chgIData(oldp+313,(vlSelfRef.tb__DOT__good1__DOT__u0__DOT__subword),32);
    bufp->chgCData(oldp+314,(vlSelfRef.tb__DOT__top_module1__DOT__sb
                             [0U][0U]),8);
    bufp->chgCData(oldp+315,(vlSelfRef.tb__DOT__top_module1__DOT__sb
                             [0U][1U]),8);
    bufp->chgCData(oldp+316,(vlSelfRef.tb__DOT__top_module1__DOT__sb
                             [0U][2U]),8);
    bufp->chgCData(oldp+317,(vlSelfRef.tb__DOT__top_module1__DOT__sb
                             [0U][3U]),8);
    bufp->chgCData(oldp+318,(vlSelfRef.tb__DOT__top_module1__DOT__sb
                             [1U][0U]),8);
    bufp->chgCData(oldp+319,(vlSelfRef.tb__DOT__top_module1__DOT__sb
                             [1U][1U]),8);
    bufp->chgCData(oldp+320,(vlSelfRef.tb__DOT__top_module1__DOT__sb
                             [1U][2U]),8);
    bufp->chgCData(oldp+321,(vlSelfRef.tb__DOT__top_module1__DOT__sb
                             [1U][3U]),8);
    bufp->chgCData(oldp+322,(vlSelfRef.tb__DOT__top_module1__DOT__sb
                             [2U][0U]),8);
    bufp->chgCData(oldp+323,(vlSelfRef.tb__DOT__top_module1__DOT__sb
                             [2U][1U]),8);
    bufp->chgCData(oldp+324,(vlSelfRef.tb__DOT__top_module1__DOT__sb
                             [2U][2U]),8);
    bufp->chgCData(oldp+325,(vlSelfRef.tb__DOT__top_module1__DOT__sb
                             [2U][3U]),8);
    bufp->chgCData(oldp+326,(vlSelfRef.tb__DOT__top_module1__DOT__sb
                             [3U][0U]),8);
    bufp->chgCData(oldp+327,(vlSelfRef.tb__DOT__top_module1__DOT__sb
                             [3U][1U]),8);
    bufp->chgCData(oldp+328,(vlSelfRef.tb__DOT__top_module1__DOT__sb
                             [3U][2U]),8);
    bufp->chgCData(oldp+329,(vlSelfRef.tb__DOT__top_module1__DOT__sb
                             [3U][3U]),8);
    bufp->chgIData(oldp+330,(vlSelfRef.tb__DOT__top_module1__DOT__key_expand__DOT__subword),32);
    bufp->chgCData(oldp+331,(vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u0.b),8);
    bufp->chgCData(oldp+332,(vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u1.b),8);
    bufp->chgCData(oldp+333,(vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u2.b),8);
    bufp->chgCData(oldp+334,(vlSymsp->TOP__tb__DOT__good1__DOT__u0__DOT__u3.b),8);
    bufp->chgCData(oldp+335,(vlSymsp->TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__0__KET____DOT__sbox_row__BRA__0__KET____DOT__u_sbox.b),8);
    bufp->chgCData(oldp+336,(vlSymsp->TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__0__KET____DOT__sbox_row__BRA__1__KET____DOT__u_sbox.b),8);
    bufp->chgCData(oldp+337,(vlSymsp->TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__0__KET____DOT__sbox_row__BRA__2__KET____DOT__u_sbox.b),8);
    bufp->chgCData(oldp+338,(vlSymsp->TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__0__KET____DOT__sbox_row__BRA__3__KET____DOT__u_sbox.b),8);
    bufp->chgCData(oldp+339,(vlSymsp->TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__1__KET____DOT__sbox_row__BRA__0__KET____DOT__u_sbox.b),8);
    bufp->chgCData(oldp+340,(vlSymsp->TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__1__KET____DOT__sbox_row__BRA__1__KET____DOT__u_sbox.b),8);
    bufp->chgCData(oldp+341,(vlSymsp->TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__1__KET____DOT__sbox_row__BRA__2__KET____DOT__u_sbox.b),8);
    bufp->chgCData(oldp+342,(vlSymsp->TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__1__KET____DOT__sbox_row__BRA__3__KET____DOT__u_sbox.b),8);
    bufp->chgCData(oldp+343,(vlSymsp->TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__2__KET____DOT__sbox_row__BRA__0__KET____DOT__u_sbox.b),8);
    bufp->chgCData(oldp+344,(vlSymsp->TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__2__KET____DOT__sbox_row__BRA__1__KET____DOT__u_sbox.b),8);
    bufp->chgCData(oldp+345,(vlSymsp->TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__2__KET____DOT__sbox_row__BRA__2__KET____DOT__u_sbox.b),8);
    bufp->chgCData(oldp+346,(vlSymsp->TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__2__KET____DOT__sbox_row__BRA__3__KET____DOT__u_sbox.b),8);
    bufp->chgCData(oldp+347,(vlSymsp->TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__3__KET____DOT__sbox_row__BRA__0__KET____DOT__u_sbox.b),8);
    bufp->chgCData(oldp+348,(vlSymsp->TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__3__KET____DOT__sbox_row__BRA__1__KET____DOT__u_sbox.b),8);
    bufp->chgCData(oldp+349,(vlSymsp->TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__3__KET____DOT__sbox_row__BRA__2__KET____DOT__u_sbox.b),8);
    bufp->chgCData(oldp+350,(vlSymsp->TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__3__KET____DOT__sbox_row__BRA__3__KET____DOT__u_sbox.b),8);
    bufp->chgCData(oldp+351,(vlSymsp->TOP__tb__DOT__top_module1__DOT__key_expand__DOT__u0.b),8);
    bufp->chgCData(oldp+352,(vlSymsp->TOP__tb__DOT__top_module1__DOT__key_expand__DOT__u1.b),8);
    bufp->chgCData(oldp+353,(vlSymsp->TOP__tb__DOT__top_module1__DOT__key_expand__DOT__u2.b),8);
    bufp->chgCData(oldp+354,(vlSymsp->TOP__tb__DOT__top_module1__DOT__key_expand__DOT__u3.b),8);
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
}
