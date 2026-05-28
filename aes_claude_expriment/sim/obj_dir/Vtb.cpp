// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Model implementation (design independent parts)

#include "Vtb__pch.h"
#include "verilated_vcd_c.h"

//============================================================
// Constructors

Vtb::Vtb(VerilatedContext* _vcontextp__, const char* _vcname__)
    : VerilatedModel{*_vcontextp__}
    , vlSymsp{new Vtb__Syms(contextp(), _vcname__, this)}
    , __PVT__tb__DOT__good1__DOT__us00{vlSymsp->TOP.__PVT__tb__DOT__good1__DOT__us00}
    , __PVT__tb__DOT__good1__DOT__us01{vlSymsp->TOP.__PVT__tb__DOT__good1__DOT__us01}
    , __PVT__tb__DOT__good1__DOT__us02{vlSymsp->TOP.__PVT__tb__DOT__good1__DOT__us02}
    , __PVT__tb__DOT__good1__DOT__us03{vlSymsp->TOP.__PVT__tb__DOT__good1__DOT__us03}
    , __PVT__tb__DOT__good1__DOT__us10{vlSymsp->TOP.__PVT__tb__DOT__good1__DOT__us10}
    , __PVT__tb__DOT__good1__DOT__us11{vlSymsp->TOP.__PVT__tb__DOT__good1__DOT__us11}
    , __PVT__tb__DOT__good1__DOT__us12{vlSymsp->TOP.__PVT__tb__DOT__good1__DOT__us12}
    , __PVT__tb__DOT__good1__DOT__us13{vlSymsp->TOP.__PVT__tb__DOT__good1__DOT__us13}
    , __PVT__tb__DOT__good1__DOT__us20{vlSymsp->TOP.__PVT__tb__DOT__good1__DOT__us20}
    , __PVT__tb__DOT__good1__DOT__us21{vlSymsp->TOP.__PVT__tb__DOT__good1__DOT__us21}
    , __PVT__tb__DOT__good1__DOT__us22{vlSymsp->TOP.__PVT__tb__DOT__good1__DOT__us22}
    , __PVT__tb__DOT__good1__DOT__us23{vlSymsp->TOP.__PVT__tb__DOT__good1__DOT__us23}
    , __PVT__tb__DOT__good1__DOT__us30{vlSymsp->TOP.__PVT__tb__DOT__good1__DOT__us30}
    , __PVT__tb__DOT__good1__DOT__us31{vlSymsp->TOP.__PVT__tb__DOT__good1__DOT__us31}
    , __PVT__tb__DOT__good1__DOT__us32{vlSymsp->TOP.__PVT__tb__DOT__good1__DOT__us32}
    , __PVT__tb__DOT__good1__DOT__us33{vlSymsp->TOP.__PVT__tb__DOT__good1__DOT__us33}
    , __PVT__tb__DOT__good1__DOT__u0__DOT__u0{vlSymsp->TOP.__PVT__tb__DOT__good1__DOT__u0__DOT__u0}
    , __PVT__tb__DOT__good1__DOT__u0__DOT__u1{vlSymsp->TOP.__PVT__tb__DOT__good1__DOT__u0__DOT__u1}
    , __PVT__tb__DOT__good1__DOT__u0__DOT__u2{vlSymsp->TOP.__PVT__tb__DOT__good1__DOT__u0__DOT__u2}
    , __PVT__tb__DOT__good1__DOT__u0__DOT__u3{vlSymsp->TOP.__PVT__tb__DOT__good1__DOT__u0__DOT__u3}
    , __PVT__tb__DOT__top_module1__DOT__u_sbox_00{vlSymsp->TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_00}
    , __PVT__tb__DOT__top_module1__DOT__u_sbox_10{vlSymsp->TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_10}
    , __PVT__tb__DOT__top_module1__DOT__u_sbox_20{vlSymsp->TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_20}
    , __PVT__tb__DOT__top_module1__DOT__u_sbox_30{vlSymsp->TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_30}
    , __PVT__tb__DOT__top_module1__DOT__u_sbox_01{vlSymsp->TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_01}
    , __PVT__tb__DOT__top_module1__DOT__u_sbox_11{vlSymsp->TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_11}
    , __PVT__tb__DOT__top_module1__DOT__u_sbox_21{vlSymsp->TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_21}
    , __PVT__tb__DOT__top_module1__DOT__u_sbox_31{vlSymsp->TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_31}
    , __PVT__tb__DOT__top_module1__DOT__u_sbox_02{vlSymsp->TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_02}
    , __PVT__tb__DOT__top_module1__DOT__u_sbox_12{vlSymsp->TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_12}
    , __PVT__tb__DOT__top_module1__DOT__u_sbox_22{vlSymsp->TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_22}
    , __PVT__tb__DOT__top_module1__DOT__u_sbox_32{vlSymsp->TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_32}
    , __PVT__tb__DOT__top_module1__DOT__u_sbox_03{vlSymsp->TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_03}
    , __PVT__tb__DOT__top_module1__DOT__u_sbox_13{vlSymsp->TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_13}
    , __PVT__tb__DOT__top_module1__DOT__u_sbox_23{vlSymsp->TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_23}
    , __PVT__tb__DOT__top_module1__DOT__u_sbox_33{vlSymsp->TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_33}
    , __PVT__tb__DOT__top_module1__DOT__u_key_expand__DOT__u0{vlSymsp->TOP.__PVT__tb__DOT__top_module1__DOT__u_key_expand__DOT__u0}
    , __PVT__tb__DOT__top_module1__DOT__u_key_expand__DOT__u1{vlSymsp->TOP.__PVT__tb__DOT__top_module1__DOT__u_key_expand__DOT__u1}
    , __PVT__tb__DOT__top_module1__DOT__u_key_expand__DOT__u2{vlSymsp->TOP.__PVT__tb__DOT__top_module1__DOT__u_key_expand__DOT__u2}
    , __PVT__tb__DOT__top_module1__DOT__u_key_expand__DOT__u3{vlSymsp->TOP.__PVT__tb__DOT__top_module1__DOT__u_key_expand__DOT__u3}
    , rootp{&(vlSymsp->TOP)}
{
    // Register model with the context
    contextp()->addModel(this);
    contextp()->traceBaseModelCbAdd(
        [this](VerilatedTraceBaseC* tfp, int levels, int options) { traceBaseModel(tfp, levels, options); });
}

Vtb::Vtb(const char* _vcname__)
    : Vtb(Verilated::threadContextp(), _vcname__)
{
}

//============================================================
// Destructor

Vtb::~Vtb() {
    delete vlSymsp;
}

//============================================================
// Evaluation function

#ifdef VL_DEBUG
void Vtb___024root___eval_debug_assertions(Vtb___024root* vlSelf);
#endif  // VL_DEBUG
void Vtb___024root___eval_static(Vtb___024root* vlSelf);
void Vtb___024root___eval_initial(Vtb___024root* vlSelf);
void Vtb___024root___eval_settle(Vtb___024root* vlSelf);
void Vtb___024root___eval(Vtb___024root* vlSelf);

void Vtb::eval_step() {
    VL_DEBUG_IF(VL_DBG_MSGF("+++++TOP Evaluate Vtb::eval_step\n"); );
#ifdef VL_DEBUG
    // Debug assertions
    Vtb___024root___eval_debug_assertions(&(vlSymsp->TOP));
#endif  // VL_DEBUG
    vlSymsp->__Vm_activity = true;
    vlSymsp->__Vm_deleter.deleteAll();
    if (VL_UNLIKELY(!vlSymsp->__Vm_didInit)) {
        vlSymsp->__Vm_didInit = true;
        VL_DEBUG_IF(VL_DBG_MSGF("+ Initial\n"););
        Vtb___024root___eval_static(&(vlSymsp->TOP));
        Vtb___024root___eval_initial(&(vlSymsp->TOP));
        Vtb___024root___eval_settle(&(vlSymsp->TOP));
    }
    VL_DEBUG_IF(VL_DBG_MSGF("+ Eval\n"););
    Vtb___024root___eval(&(vlSymsp->TOP));
    // Evaluate cleanup
    Verilated::endOfEval(vlSymsp->__Vm_evalMsgQp);
}

void Vtb::eval_end_step() {
    VL_DEBUG_IF(VL_DBG_MSGF("+eval_end_step Vtb::eval_end_step\n"); );
#ifdef VM_TRACE
    // Tracing
    if (VL_UNLIKELY(vlSymsp->__Vm_dumping)) vlSymsp->_traceDump();
#endif  // VM_TRACE
}

//============================================================
// Events and timing
bool Vtb::eventsPending() { return !vlSymsp->TOP.__VdlySched.empty(); }

uint64_t Vtb::nextTimeSlot() { return vlSymsp->TOP.__VdlySched.nextTimeSlot(); }

//============================================================
// Utilities

const char* Vtb::name() const {
    return vlSymsp->name();
}

//============================================================
// Invoke final blocks

void Vtb___024root___eval_final(Vtb___024root* vlSelf);

VL_ATTR_COLD void Vtb::final() {
    Vtb___024root___eval_final(&(vlSymsp->TOP));
}

//============================================================
// Implementations of abstract methods from VerilatedModel

const char* Vtb::hierName() const { return vlSymsp->name(); }
const char* Vtb::modelName() const { return "Vtb"; }
unsigned Vtb::threads() const { return 1; }
void Vtb::prepareClone() const { contextp()->prepareClone(); }
void Vtb::atClone() const {
    contextp()->threadPoolpOnClone();
}
std::unique_ptr<VerilatedTraceConfig> Vtb::traceConfig() const {
    return std::unique_ptr<VerilatedTraceConfig>{new VerilatedTraceConfig{false, false, false}};
};

//============================================================
// Trace configuration

void Vtb___024root__trace_decl_types(VerilatedVcd* tracep);

void Vtb___024root__trace_init_top(Vtb___024root* vlSelf, VerilatedVcd* tracep);

VL_ATTR_COLD static void trace_init(void* voidSelf, VerilatedVcd* tracep, uint32_t code) {
    // Callback from tracep->open()
    Vtb___024root* const __restrict vlSelf VL_ATTR_UNUSED = static_cast<Vtb___024root*>(voidSelf);
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    if (!vlSymsp->_vm_contextp__->calcUnusedSigs()) {
        VL_FATAL_MT(__FILE__, __LINE__, __FILE__,
            "Turning on wave traces requires Verilated::traceEverOn(true) call before time 0.");
    }
    vlSymsp->__Vm_baseCode = code;
    tracep->pushPrefix(vlSymsp->name(), VerilatedTracePrefixType::SCOPE_MODULE);
    Vtb___024root__trace_decl_types(tracep);
    Vtb___024root__trace_init_top(vlSelf, tracep);
    tracep->popPrefix();
}

VL_ATTR_COLD void Vtb___024root__trace_register(Vtb___024root* vlSelf, VerilatedVcd* tracep);

VL_ATTR_COLD void Vtb::traceBaseModel(VerilatedTraceBaseC* tfp, int levels, int options) {
    (void)levels; (void)options;
    VerilatedVcdC* const stfp = dynamic_cast<VerilatedVcdC*>(tfp);
    if (VL_UNLIKELY(!stfp)) {
        vl_fatal(__FILE__, __LINE__, __FILE__,"'Vtb::trace()' called on non-VerilatedVcdC object;"
            " use --trace-fst with VerilatedFst object, and --trace-vcd with VerilatedVcd object");
    }
    stfp->spTrace()->addModel(this);
    stfp->spTrace()->addInitCb(&trace_init, &(vlSymsp->TOP));
    Vtb___024root__trace_register(&(vlSymsp->TOP), stfp->spTrace());
}
