// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Symbol table internal header
//
// Internal details; most calling programs do not need this header,
// unless using verilator public meta comments.

#ifndef VERILATED_VTB__SYMS_H_
#define VERILATED_VTB__SYMS_H_  // guard

#include "verilated.h"
#include "verilated_vcd_c.h"

// INCLUDE MODEL CLASS

#include "Vtb.h"

// INCLUDE MODULE CLASSES
#include "Vtb___024root.h"
#include "Vtb_aes_sbox.h"

// SYMS CLASS (contains all model state)
class alignas(VL_CACHE_LINE_BYTES) Vtb__Syms final : public VerilatedSyms {
  public:
    // INTERNAL STATE
    Vtb* const __Vm_modelp;
    bool __Vm_dumping = false;  // Dumping is active
    VerilatedMutex __Vm_dumperMutex;  // Protect __Vm_dumperp
    VerilatedVcdC* __Vm_dumperp VL_GUARDED_BY(__Vm_dumperMutex) = nullptr;  /// Trace class for $dump*
    bool __Vm_activity = false;  ///< Used by trace routines to determine change occurred
    uint32_t __Vm_baseCode = 0;  ///< Used by trace routines when tracing multiple models
    VlDeleter __Vm_deleter;
    bool __Vm_didInit = false;

    // MODULE INSTANCE STATE
    Vtb___024root                  TOP;
    Vtb_aes_sbox                   TOP__tb__DOT__good1__DOT__u0__DOT__u0;
    Vtb_aes_sbox                   TOP__tb__DOT__good1__DOT__u0__DOT__u1;
    Vtb_aes_sbox                   TOP__tb__DOT__good1__DOT__u0__DOT__u2;
    Vtb_aes_sbox                   TOP__tb__DOT__good1__DOT__u0__DOT__u3;
    Vtb_aes_sbox                   TOP__tb__DOT__good1__DOT__us00;
    Vtb_aes_sbox                   TOP__tb__DOT__good1__DOT__us01;
    Vtb_aes_sbox                   TOP__tb__DOT__good1__DOT__us02;
    Vtb_aes_sbox                   TOP__tb__DOT__good1__DOT__us03;
    Vtb_aes_sbox                   TOP__tb__DOT__good1__DOT__us10;
    Vtb_aes_sbox                   TOP__tb__DOT__good1__DOT__us11;
    Vtb_aes_sbox                   TOP__tb__DOT__good1__DOT__us12;
    Vtb_aes_sbox                   TOP__tb__DOT__good1__DOT__us13;
    Vtb_aes_sbox                   TOP__tb__DOT__good1__DOT__us20;
    Vtb_aes_sbox                   TOP__tb__DOT__good1__DOT__us21;
    Vtb_aes_sbox                   TOP__tb__DOT__good1__DOT__us22;
    Vtb_aes_sbox                   TOP__tb__DOT__good1__DOT__us23;
    Vtb_aes_sbox                   TOP__tb__DOT__good1__DOT__us30;
    Vtb_aes_sbox                   TOP__tb__DOT__good1__DOT__us31;
    Vtb_aes_sbox                   TOP__tb__DOT__good1__DOT__us32;
    Vtb_aes_sbox                   TOP__tb__DOT__good1__DOT__us33;
    Vtb_aes_sbox                   TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u0;
    Vtb_aes_sbox                   TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u1;
    Vtb_aes_sbox                   TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u2;
    Vtb_aes_sbox                   TOP__tb__DOT__top_module1__DOT__u_key_expand__DOT__u3;
    Vtb_aes_sbox                   TOP__tb__DOT__top_module1__DOT__u_sbox_00;
    Vtb_aes_sbox                   TOP__tb__DOT__top_module1__DOT__u_sbox_01;
    Vtb_aes_sbox                   TOP__tb__DOT__top_module1__DOT__u_sbox_02;
    Vtb_aes_sbox                   TOP__tb__DOT__top_module1__DOT__u_sbox_03;
    Vtb_aes_sbox                   TOP__tb__DOT__top_module1__DOT__u_sbox_10;
    Vtb_aes_sbox                   TOP__tb__DOT__top_module1__DOT__u_sbox_11;
    Vtb_aes_sbox                   TOP__tb__DOT__top_module1__DOT__u_sbox_12;
    Vtb_aes_sbox                   TOP__tb__DOT__top_module1__DOT__u_sbox_13;
    Vtb_aes_sbox                   TOP__tb__DOT__top_module1__DOT__u_sbox_20;
    Vtb_aes_sbox                   TOP__tb__DOT__top_module1__DOT__u_sbox_21;
    Vtb_aes_sbox                   TOP__tb__DOT__top_module1__DOT__u_sbox_22;
    Vtb_aes_sbox                   TOP__tb__DOT__top_module1__DOT__u_sbox_23;
    Vtb_aes_sbox                   TOP__tb__DOT__top_module1__DOT__u_sbox_30;
    Vtb_aes_sbox                   TOP__tb__DOT__top_module1__DOT__u_sbox_31;
    Vtb_aes_sbox                   TOP__tb__DOT__top_module1__DOT__u_sbox_32;
    Vtb_aes_sbox                   TOP__tb__DOT__top_module1__DOT__u_sbox_33;

    // COVERAGE
    uint32_t __Vcoverage[468];

    // CONSTRUCTORS
    Vtb__Syms(VerilatedContext* contextp, const char* namep, Vtb* modelp);
    ~Vtb__Syms();

    // METHODS
    const char* name() const { return TOP.vlNamep; }
    void _traceDump();
    void _traceDumpOpen();
    void _traceDumpClose();
};

#endif  // guard
