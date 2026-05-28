// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Symbol table implementation internals

#include "Vtb__pch.h"

Vtb__Syms::Vtb__Syms(VerilatedContext* contextp, const char* namep, Vtb* modelp)
    : VerilatedSyms{contextp}
    // Setup internal state of the Syms class
    , __Vm_modelp{modelp}
    // Setup top module instance
    , TOP{this, namep}
{
    // Check resources
    Verilated::stackCheck(575);
    // Setup sub module instances
    TOP__tb__DOT__good1__DOT__u0__DOT__u0.ctor(this, "tb.good1.u0.u0");
    TOP__tb__DOT__good1__DOT__u0__DOT__u1.ctor(this, "tb.good1.u0.u1");
    TOP__tb__DOT__good1__DOT__u0__DOT__u2.ctor(this, "tb.good1.u0.u2");
    TOP__tb__DOT__good1__DOT__u0__DOT__u3.ctor(this, "tb.good1.u0.u3");
    TOP__tb__DOT__good1__DOT__us00.ctor(this, "tb.good1.us00");
    TOP__tb__DOT__good1__DOT__us01.ctor(this, "tb.good1.us01");
    TOP__tb__DOT__good1__DOT__us02.ctor(this, "tb.good1.us02");
    TOP__tb__DOT__good1__DOT__us03.ctor(this, "tb.good1.us03");
    TOP__tb__DOT__good1__DOT__us10.ctor(this, "tb.good1.us10");
    TOP__tb__DOT__good1__DOT__us11.ctor(this, "tb.good1.us11");
    TOP__tb__DOT__good1__DOT__us12.ctor(this, "tb.good1.us12");
    TOP__tb__DOT__good1__DOT__us13.ctor(this, "tb.good1.us13");
    TOP__tb__DOT__good1__DOT__us20.ctor(this, "tb.good1.us20");
    TOP__tb__DOT__good1__DOT__us21.ctor(this, "tb.good1.us21");
    TOP__tb__DOT__good1__DOT__us22.ctor(this, "tb.good1.us22");
    TOP__tb__DOT__good1__DOT__us23.ctor(this, "tb.good1.us23");
    TOP__tb__DOT__good1__DOT__us30.ctor(this, "tb.good1.us30");
    TOP__tb__DOT__good1__DOT__us31.ctor(this, "tb.good1.us31");
    TOP__tb__DOT__good1__DOT__us32.ctor(this, "tb.good1.us32");
    TOP__tb__DOT__good1__DOT__us33.ctor(this, "tb.good1.us33");
    TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u0.ctor(this, "tb.top_module1.u_key_expand.u0");
    TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u1.ctor(this, "tb.top_module1.u_key_expand.u1");
    TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u2.ctor(this, "tb.top_module1.u_key_expand.u2");
    TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u3.ctor(this, "tb.top_module1.u_key_expand.u3");
    TOP__tb__DOT__top_module1__DOT__u_sbox_00.ctor(this, "tb.top_module1.u_sbox_00");
    TOP__tb__DOT__top_module1__DOT__u_sbox_01.ctor(this, "tb.top_module1.u_sbox_01");
    TOP__tb__DOT__top_module1__DOT__u_sbox_02.ctor(this, "tb.top_module1.u_sbox_02");
    TOP__tb__DOT__top_module1__DOT__u_sbox_03.ctor(this, "tb.top_module1.u_sbox_03");
    TOP__tb__DOT__top_module1__DOT__u_sbox_10.ctor(this, "tb.top_module1.u_sbox_10");
    TOP__tb__DOT__top_module1__DOT__u_sbox_11.ctor(this, "tb.top_module1.u_sbox_11");
    TOP__tb__DOT__top_module1__DOT__u_sbox_12.ctor(this, "tb.top_module1.u_sbox_12");
    TOP__tb__DOT__top_module1__DOT__u_sbox_13.ctor(this, "tb.top_module1.u_sbox_13");
    TOP__tb__DOT__top_module1__DOT__u_sbox_20.ctor(this, "tb.top_module1.u_sbox_20");
    TOP__tb__DOT__top_module1__DOT__u_sbox_21.ctor(this, "tb.top_module1.u_sbox_21");
    TOP__tb__DOT__top_module1__DOT__u_sbox_22.ctor(this, "tb.top_module1.u_sbox_22");
    TOP__tb__DOT__top_module1__DOT__u_sbox_23.ctor(this, "tb.top_module1.u_sbox_23");
    TOP__tb__DOT__top_module1__DOT__u_sbox_30.ctor(this, "tb.top_module1.u_sbox_30");
    TOP__tb__DOT__top_module1__DOT__u_sbox_31.ctor(this, "tb.top_module1.u_sbox_31");
    TOP__tb__DOT__top_module1__DOT__u_sbox_32.ctor(this, "tb.top_module1.u_sbox_32");
    TOP__tb__DOT__top_module1__DOT__u_sbox_33.ctor(this, "tb.top_module1.u_sbox_33");
    // Configure time unit / time precision
    _vm_contextp__->timeunit(-12);
    _vm_contextp__->timeprecision(-12);
    // Setup each module's pointers to their submodules
    TOP.__PVT__tb__DOT__good1__DOT__u0__DOT__u0 = &TOP__tb__DOT__good1__DOT__u0__DOT__u0;
    TOP.__PVT__tb__DOT__good1__DOT__u0__DOT__u1 = &TOP__tb__DOT__good1__DOT__u0__DOT__u1;
    TOP.__PVT__tb__DOT__good1__DOT__u0__DOT__u2 = &TOP__tb__DOT__good1__DOT__u0__DOT__u2;
    TOP.__PVT__tb__DOT__good1__DOT__u0__DOT__u3 = &TOP__tb__DOT__good1__DOT__u0__DOT__u3;
    TOP.__PVT__tb__DOT__good1__DOT__us00 = &TOP__tb__DOT__good1__DOT__us00;
    TOP.__PVT__tb__DOT__good1__DOT__us01 = &TOP__tb__DOT__good1__DOT__us01;
    TOP.__PVT__tb__DOT__good1__DOT__us02 = &TOP__tb__DOT__good1__DOT__us02;
    TOP.__PVT__tb__DOT__good1__DOT__us03 = &TOP__tb__DOT__good1__DOT__us03;
    TOP.__PVT__tb__DOT__good1__DOT__us10 = &TOP__tb__DOT__good1__DOT__us10;
    TOP.__PVT__tb__DOT__good1__DOT__us11 = &TOP__tb__DOT__good1__DOT__us11;
    TOP.__PVT__tb__DOT__good1__DOT__us12 = &TOP__tb__DOT__good1__DOT__us12;
    TOP.__PVT__tb__DOT__good1__DOT__us13 = &TOP__tb__DOT__good1__DOT__us13;
    TOP.__PVT__tb__DOT__good1__DOT__us20 = &TOP__tb__DOT__good1__DOT__us20;
    TOP.__PVT__tb__DOT__good1__DOT__us21 = &TOP__tb__DOT__good1__DOT__us21;
    TOP.__PVT__tb__DOT__good1__DOT__us22 = &TOP__tb__DOT__good1__DOT__us22;
    TOP.__PVT__tb__DOT__good1__DOT__us23 = &TOP__tb__DOT__good1__DOT__us23;
    TOP.__PVT__tb__DOT__good1__DOT__us30 = &TOP__tb__DOT__good1__DOT__us30;
    TOP.__PVT__tb__DOT__good1__DOT__us31 = &TOP__tb__DOT__good1__DOT__us31;
    TOP.__PVT__tb__DOT__good1__DOT__us32 = &TOP__tb__DOT__good1__DOT__us32;
    TOP.__PVT__tb__DOT__good1__DOT__us33 = &TOP__tb__DOT__good1__DOT__us33;
    TOP.__PVT__tb__DOT__top_module1__DOT__u_key_expand__DOT__u0 = &TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u0;
    TOP.__PVT__tb__DOT__top_module1__DOT__u_key_expand__DOT__u1 = &TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u1;
    TOP.__PVT__tb__DOT__top_module1__DOT__u_key_expand__DOT__u2 = &TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u2;
    TOP.__PVT__tb__DOT__top_module1__DOT__u_key_expand__DOT__u3 = &TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u3;
    TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_00 = &TOP__tb__DOT__top_module1__DOT__u_sbox_00;
    TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_01 = &TOP__tb__DOT__top_module1__DOT__u_sbox_01;
    TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_02 = &TOP__tb__DOT__top_module1__DOT__u_sbox_02;
    TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_03 = &TOP__tb__DOT__top_module1__DOT__u_sbox_03;
    TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_10 = &TOP__tb__DOT__top_module1__DOT__u_sbox_10;
    TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_11 = &TOP__tb__DOT__top_module1__DOT__u_sbox_11;
    TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_12 = &TOP__tb__DOT__top_module1__DOT__u_sbox_12;
    TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_13 = &TOP__tb__DOT__top_module1__DOT__u_sbox_13;
    TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_20 = &TOP__tb__DOT__top_module1__DOT__u_sbox_20;
    TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_21 = &TOP__tb__DOT__top_module1__DOT__u_sbox_21;
    TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_22 = &TOP__tb__DOT__top_module1__DOT__u_sbox_22;
    TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_23 = &TOP__tb__DOT__top_module1__DOT__u_sbox_23;
    TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_30 = &TOP__tb__DOT__top_module1__DOT__u_sbox_30;
    TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_31 = &TOP__tb__DOT__top_module1__DOT__u_sbox_31;
    TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_32 = &TOP__tb__DOT__top_module1__DOT__u_sbox_32;
    TOP.__PVT__tb__DOT__top_module1__DOT__u_sbox_33 = &TOP__tb__DOT__top_module1__DOT__u_sbox_33;
    // Setup each module's pointer back to symbol table (for public functions)
    TOP.__Vconfigure(true);
    TOP__tb__DOT__good1__DOT__u0__DOT__u0.__Vconfigure(true);
    TOP__tb__DOT__good1__DOT__u0__DOT__u1.__Vconfigure(false);
    TOP__tb__DOT__good1__DOT__u0__DOT__u2.__Vconfigure(false);
    TOP__tb__DOT__good1__DOT__u0__DOT__u3.__Vconfigure(false);
    TOP__tb__DOT__good1__DOT__us00.__Vconfigure(false);
    TOP__tb__DOT__good1__DOT__us01.__Vconfigure(false);
    TOP__tb__DOT__good1__DOT__us02.__Vconfigure(false);
    TOP__tb__DOT__good1__DOT__us03.__Vconfigure(false);
    TOP__tb__DOT__good1__DOT__us10.__Vconfigure(false);
    TOP__tb__DOT__good1__DOT__us11.__Vconfigure(false);
    TOP__tb__DOT__good1__DOT__us12.__Vconfigure(false);
    TOP__tb__DOT__good1__DOT__us13.__Vconfigure(false);
    TOP__tb__DOT__good1__DOT__us20.__Vconfigure(false);
    TOP__tb__DOT__good1__DOT__us21.__Vconfigure(false);
    TOP__tb__DOT__good1__DOT__us22.__Vconfigure(false);
    TOP__tb__DOT__good1__DOT__us23.__Vconfigure(false);
    TOP__tb__DOT__good1__DOT__us30.__Vconfigure(false);
    TOP__tb__DOT__good1__DOT__us31.__Vconfigure(false);
    TOP__tb__DOT__good1__DOT__us32.__Vconfigure(false);
    TOP__tb__DOT__good1__DOT__us33.__Vconfigure(false);
    TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u0.__Vconfigure(false);
    TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u1.__Vconfigure(false);
    TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u2.__Vconfigure(false);
    TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u3.__Vconfigure(false);
    TOP__tb__DOT__top_module1__DOT__u_sbox_00.__Vconfigure(false);
    TOP__tb__DOT__top_module1__DOT__u_sbox_01.__Vconfigure(false);
    TOP__tb__DOT__top_module1__DOT__u_sbox_02.__Vconfigure(false);
    TOP__tb__DOT__top_module1__DOT__u_sbox_03.__Vconfigure(false);
    TOP__tb__DOT__top_module1__DOT__u_sbox_10.__Vconfigure(false);
    TOP__tb__DOT__top_module1__DOT__u_sbox_11.__Vconfigure(false);
    TOP__tb__DOT__top_module1__DOT__u_sbox_12.__Vconfigure(false);
    TOP__tb__DOT__top_module1__DOT__u_sbox_13.__Vconfigure(false);
    TOP__tb__DOT__top_module1__DOT__u_sbox_20.__Vconfigure(false);
    TOP__tb__DOT__top_module1__DOT__u_sbox_21.__Vconfigure(false);
    TOP__tb__DOT__top_module1__DOT__u_sbox_22.__Vconfigure(false);
    TOP__tb__DOT__top_module1__DOT__u_sbox_23.__Vconfigure(false);
    TOP__tb__DOT__top_module1__DOT__u_sbox_30.__Vconfigure(false);
    TOP__tb__DOT__top_module1__DOT__u_sbox_31.__Vconfigure(false);
    TOP__tb__DOT__top_module1__DOT__u_sbox_32.__Vconfigure(false);
    TOP__tb__DOT__top_module1__DOT__u_sbox_33.__Vconfigure(false);
    // Setup scopes
}

Vtb__Syms::~Vtb__Syms() {
    if (__Vm_dumping) _traceDumpClose();
    // Tear down scopes
    // Tear down sub module instances
    TOP__tb__DOT__top_module1__DOT__u_sbox_33.dtor();
    TOP__tb__DOT__top_module1__DOT__u_sbox_32.dtor();
    TOP__tb__DOT__top_module1__DOT__u_sbox_31.dtor();
    TOP__tb__DOT__top_module1__DOT__u_sbox_30.dtor();
    TOP__tb__DOT__top_module1__DOT__u_sbox_23.dtor();
    TOP__tb__DOT__top_module1__DOT__u_sbox_22.dtor();
    TOP__tb__DOT__top_module1__DOT__u_sbox_21.dtor();
    TOP__tb__DOT__top_module1__DOT__u_sbox_20.dtor();
    TOP__tb__DOT__top_module1__DOT__u_sbox_13.dtor();
    TOP__tb__DOT__top_module1__DOT__u_sbox_12.dtor();
    TOP__tb__DOT__top_module1__DOT__u_sbox_11.dtor();
    TOP__tb__DOT__top_module1__DOT__u_sbox_10.dtor();
    TOP__tb__DOT__top_module1__DOT__u_sbox_03.dtor();
    TOP__tb__DOT__top_module1__DOT__u_sbox_02.dtor();
    TOP__tb__DOT__top_module1__DOT__u_sbox_01.dtor();
    TOP__tb__DOT__top_module1__DOT__u_sbox_00.dtor();
    TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u3.dtor();
    TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u2.dtor();
    TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u1.dtor();
    TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u0.dtor();
    TOP__tb__DOT__good1__DOT__us33.dtor();
    TOP__tb__DOT__good1__DOT__us32.dtor();
    TOP__tb__DOT__good1__DOT__us31.dtor();
    TOP__tb__DOT__good1__DOT__us30.dtor();
    TOP__tb__DOT__good1__DOT__us23.dtor();
    TOP__tb__DOT__good1__DOT__us22.dtor();
    TOP__tb__DOT__good1__DOT__us21.dtor();
    TOP__tb__DOT__good1__DOT__us20.dtor();
    TOP__tb__DOT__good1__DOT__us13.dtor();
    TOP__tb__DOT__good1__DOT__us12.dtor();
    TOP__tb__DOT__good1__DOT__us11.dtor();
    TOP__tb__DOT__good1__DOT__us10.dtor();
    TOP__tb__DOT__good1__DOT__us03.dtor();
    TOP__tb__DOT__good1__DOT__us02.dtor();
    TOP__tb__DOT__good1__DOT__us01.dtor();
    TOP__tb__DOT__good1__DOT__us00.dtor();
    TOP__tb__DOT__good1__DOT__u0__DOT__u3.dtor();
    TOP__tb__DOT__good1__DOT__u0__DOT__u2.dtor();
    TOP__tb__DOT__good1__DOT__u0__DOT__u1.dtor();
    TOP__tb__DOT__good1__DOT__u0__DOT__u0.dtor();
}

void Vtb__Syms::_traceDump() {
    const VerilatedLockGuard lock{__Vm_dumperMutex};
    __Vm_dumperp->dump(VL_TIME_Q());
}

void Vtb__Syms::_traceDumpOpen() {
    const VerilatedLockGuard lock{__Vm_dumperMutex};
    if (VL_UNLIKELY(!__Vm_dumperp)) {
        __Vm_dumperp = new VerilatedVcdC();
        __Vm_modelp->trace(__Vm_dumperp, 0, 0);
        const std::string dumpfile = _vm_contextp__->dumpfileCheck();
        __Vm_dumperp->open(dumpfile.c_str());
        __Vm_dumping = true;
    }
}

void Vtb__Syms::_traceDumpClose() {
    const VerilatedLockGuard lock{__Vm_dumperMutex};
    __Vm_dumping = false;
    VL_DO_CLEAR(delete __Vm_dumperp, __Vm_dumperp = nullptr);
}
