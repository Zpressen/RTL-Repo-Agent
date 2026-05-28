// Verilated -*- C++ -*-
// DESCRIPTION: Verilator output: Design implementation internals
// See Vtb.h for the primary calling header

#include "Vtb__pch.h"

void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__1__KET____DOT__sbox_row__BRA__0__KET____DOT__u_sbox__1(Vtb_aes_sbox* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+            Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__1__KET____DOT__sbox_row__BRA__0__KET____DOT__u_sbox__1\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.a = vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
        [1U][0U];
}

void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__1__KET____DOT__sbox_row__BRA__1__KET____DOT__u_sbox__0(Vtb_aes_sbox* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+            Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__1__KET____DOT__sbox_row__BRA__1__KET____DOT__u_sbox__0\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((0x00000080U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
         [1U][1U])) {
        if ((0x00000040U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [1U][1U])) {
            if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][1U])) {
                if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][1U])) {
                            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [1U][1U])) {
                                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                     [1U][1U])) {
                                    vlSelfRef.b = 0x16U;
                                    ++(vlSymsp->__Vcoverage[458]);
                                } else {
                                    ++(vlSymsp->__Vcoverage[457]);
                                    vlSelfRef.b = 0xbbU;
                                }
                            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                        [1U][1U])) {
                                ++(vlSymsp->__Vcoverage[456]);
                                vlSelfRef.b = 0x54U;
                            } else {
                                ++(vlSymsp->__Vcoverage[455]);
                                vlSelfRef.b = 0xb0U;
                            }
                        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [1U][1U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [1U][1U])) {
                                ++(vlSymsp->__Vcoverage[454]);
                                vlSelfRef.b = 0x0fU;
                            } else {
                                ++(vlSymsp->__Vcoverage[453]);
                                vlSelfRef.b = 0x2dU;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [1U][1U])) {
                            ++(vlSymsp->__Vcoverage[452]);
                            vlSelfRef.b = 0x99U;
                        } else {
                            ++(vlSymsp->__Vcoverage[451]);
                            vlSelfRef.b = 0x41U;
                        }
                    } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][1U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][1U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [1U][1U])) {
                                ++(vlSymsp->__Vcoverage[450]);
                                vlSelfRef.b = 0x68U;
                            } else {
                                ++(vlSymsp->__Vcoverage[449]);
                                vlSelfRef.b = 0x42U;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [1U][1U])) {
                            ++(vlSymsp->__Vcoverage[448]);
                            vlSelfRef.b = 0xe6U;
                        } else {
                            ++(vlSymsp->__Vcoverage[447]);
                            vlSelfRef.b = 0xbfU;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][1U])) {
                            ++(vlSymsp->__Vcoverage[446]);
                            vlSelfRef.b = 0x0dU;
                        } else {
                            ++(vlSymsp->__Vcoverage[445]);
                            vlSelfRef.b = 0x89U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[444]);
                        vlSelfRef.b = 0xa1U;
                    } else {
                        ++(vlSymsp->__Vcoverage[443]);
                        vlSelfRef.b = 0x8cU;
                    }
                } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][1U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [1U][1U])) {
                                ++(vlSymsp->__Vcoverage[442]);
                                vlSelfRef.b = 0xdfU;
                            } else {
                                ++(vlSymsp->__Vcoverage[441]);
                                vlSelfRef.b = 0x28U;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [1U][1U])) {
                            ++(vlSymsp->__Vcoverage[440]);
                            vlSelfRef.b = 0x55U;
                        } else {
                            ++(vlSymsp->__Vcoverage[439]);
                            vlSelfRef.b = 0xceU;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][1U])) {
                            ++(vlSymsp->__Vcoverage[438]);
                            vlSelfRef.b = 0xe9U;
                        } else {
                            ++(vlSymsp->__Vcoverage[437]);
                            vlSelfRef.b = 0x87U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[436]);
                        vlSelfRef.b = 0x1eU;
                    } else {
                        ++(vlSymsp->__Vcoverage[435]);
                        vlSelfRef.b = 0x9bU;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][1U])) {
                            ++(vlSymsp->__Vcoverage[434]);
                            vlSelfRef.b = 0x94U;
                        } else {
                            ++(vlSymsp->__Vcoverage[433]);
                            vlSelfRef.b = 0x8eU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[432]);
                        vlSelfRef.b = 0xd9U;
                    } else {
                        ++(vlSymsp->__Vcoverage[431]);
                        vlSelfRef.b = 0x69U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[430]);
                        vlSelfRef.b = 0x11U;
                    } else {
                        ++(vlSymsp->__Vcoverage[429]);
                        vlSelfRef.b = 0x98U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[428]);
                    vlSelfRef.b = 0xf8U;
                } else {
                    ++(vlSymsp->__Vcoverage[427]);
                    vlSelfRef.b = 0xe1U;
                }
            } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][1U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [1U][1U])) {
                                ++(vlSymsp->__Vcoverage[426]);
                                vlSelfRef.b = 0x9eU;
                            } else {
                                ++(vlSymsp->__Vcoverage[425]);
                                vlSelfRef.b = 0x1dU;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [1U][1U])) {
                            ++(vlSymsp->__Vcoverage[424]);
                            vlSelfRef.b = 0xc1U;
                        } else {
                            ++(vlSymsp->__Vcoverage[423]);
                            vlSelfRef.b = 0x86U;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][1U])) {
                            ++(vlSymsp->__Vcoverage[422]);
                            vlSelfRef.b = 0xb9U;
                        } else {
                            ++(vlSymsp->__Vcoverage[421]);
                            vlSelfRef.b = 0x57U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[420]);
                        vlSelfRef.b = 0x35U;
                    } else {
                        ++(vlSymsp->__Vcoverage[419]);
                        vlSelfRef.b = 0x61U;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][1U])) {
                            ++(vlSymsp->__Vcoverage[418]);
                            vlSelfRef.b = 0x0eU;
                        } else {
                            ++(vlSymsp->__Vcoverage[417]);
                            vlSelfRef.b = 0xf6U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[416]);
                        vlSelfRef.b = 3U;
                    } else {
                        ++(vlSymsp->__Vcoverage[415]);
                        vlSelfRef.b = 0x48U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[414]);
                        vlSelfRef.b = 0x66U;
                    } else {
                        ++(vlSymsp->__Vcoverage[413]);
                        vlSelfRef.b = 0xb5U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[412]);
                    vlSelfRef.b = 0x3eU;
                } else {
                    ++(vlSymsp->__Vcoverage[411]);
                    vlSelfRef.b = 0x70U;
                }
            } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][1U])) {
                            ++(vlSymsp->__Vcoverage[410]);
                            vlSelfRef.b = 0x8aU;
                        } else {
                            ++(vlSymsp->__Vcoverage[409]);
                            vlSelfRef.b = 0x8bU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[408]);
                        vlSelfRef.b = 0xbdU;
                    } else {
                        ++(vlSymsp->__Vcoverage[407]);
                        vlSelfRef.b = 0x4bU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[406]);
                        vlSelfRef.b = 0x1fU;
                    } else {
                        ++(vlSymsp->__Vcoverage[405]);
                        vlSelfRef.b = 0x74U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[404]);
                    vlSelfRef.b = 0xddU;
                } else {
                    ++(vlSymsp->__Vcoverage[403]);
                    vlSelfRef.b = 0xe8U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[402]);
                        vlSelfRef.b = 0xc6U;
                    } else {
                        ++(vlSymsp->__Vcoverage[401]);
                        vlSelfRef.b = 0xb4U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[400]);
                    vlSelfRef.b = 0xa6U;
                } else {
                    ++(vlSymsp->__Vcoverage[399]);
                    vlSelfRef.b = 0x1cU;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[398]);
                    vlSelfRef.b = 0x2eU;
                } else {
                    ++(vlSymsp->__Vcoverage[397]);
                    vlSelfRef.b = 0x25U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                ++(vlSymsp->__Vcoverage[396]);
                vlSelfRef.b = 0x78U;
            } else {
                ++(vlSymsp->__Vcoverage[395]);
                vlSelfRef.b = 0xbaU;
            }
        } else if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][1U])) {
            if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][1U])) {
                if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][1U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [1U][1U])) {
                                ++(vlSymsp->__Vcoverage[394]);
                                vlSelfRef.b = 8U;
                            } else {
                                ++(vlSymsp->__Vcoverage[393]);
                                vlSelfRef.b = 0xaeU;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [1U][1U])) {
                            ++(vlSymsp->__Vcoverage[392]);
                            vlSelfRef.b = 0x7aU;
                        } else {
                            ++(vlSymsp->__Vcoverage[391]);
                            vlSelfRef.b = 0x65U;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][1U])) {
                            ++(vlSymsp->__Vcoverage[390]);
                            vlSelfRef.b = 0xeaU;
                        } else {
                            ++(vlSymsp->__Vcoverage[389]);
                            vlSelfRef.b = 0xf4U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[388]);
                        vlSelfRef.b = 0x56U;
                    } else {
                        ++(vlSymsp->__Vcoverage[387]);
                        vlSelfRef.b = 0x6cU;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][1U])) {
                            ++(vlSymsp->__Vcoverage[386]);
                            vlSelfRef.b = 0xa9U;
                        } else {
                            ++(vlSymsp->__Vcoverage[385]);
                            vlSelfRef.b = 0x4eU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[384]);
                        vlSelfRef.b = 0xd5U;
                    } else {
                        ++(vlSymsp->__Vcoverage[383]);
                        vlSelfRef.b = 0x8dU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[382]);
                        vlSelfRef.b = 0x6dU;
                    } else {
                        ++(vlSymsp->__Vcoverage[381]);
                        vlSelfRef.b = 0x37U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[380]);
                    vlSelfRef.b = 0xc8U;
                } else {
                    ++(vlSymsp->__Vcoverage[379]);
                    vlSelfRef.b = 0xe7U;
                }
            } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][1U])) {
                            ++(vlSymsp->__Vcoverage[378]);
                            vlSelfRef.b = 0x79U;
                        } else {
                            ++(vlSymsp->__Vcoverage[377]);
                            vlSelfRef.b = 0xe4U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[376]);
                        vlSelfRef.b = 0x95U;
                    } else {
                        ++(vlSymsp->__Vcoverage[375]);
                        vlSelfRef.b = 0x91U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[374]);
                        vlSelfRef.b = 0x62U;
                    } else {
                        ++(vlSymsp->__Vcoverage[373]);
                        vlSelfRef.b = 0xacU;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[372]);
                    vlSelfRef.b = 0xd3U;
                } else {
                    ++(vlSymsp->__Vcoverage[371]);
                    vlSelfRef.b = 0xc2U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[370]);
                        vlSelfRef.b = 0x5cU;
                    } else {
                        ++(vlSymsp->__Vcoverage[369]);
                        vlSelfRef.b = 0x24U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[368]);
                    vlSelfRef.b = 6U;
                } else {
                    ++(vlSymsp->__Vcoverage[367]);
                    vlSelfRef.b = 0x49U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[366]);
                    vlSelfRef.b = 0x0aU;
                } else {
                    ++(vlSymsp->__Vcoverage[365]);
                    vlSelfRef.b = 0x3aU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                ++(vlSymsp->__Vcoverage[364]);
                vlSelfRef.b = 0x32U;
            } else {
                ++(vlSymsp->__Vcoverage[363]);
                vlSelfRef.b = 0xe0U;
            }
        } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][1U])) {
            if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][1U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][1U])) {
                            ++(vlSymsp->__Vcoverage[362]);
                            vlSelfRef.b = 0xdbU;
                        } else {
                            ++(vlSymsp->__Vcoverage[361]);
                            vlSelfRef.b = 0x0bU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[360]);
                        vlSelfRef.b = 0x5eU;
                    } else {
                        ++(vlSymsp->__Vcoverage[359]);
                        vlSelfRef.b = 0xdeU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[358]);
                        vlSelfRef.b = 0x14U;
                    } else {
                        ++(vlSymsp->__Vcoverage[357]);
                        vlSelfRef.b = 0xb8U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[356]);
                    vlSelfRef.b = 0xeeU;
                } else {
                    ++(vlSymsp->__Vcoverage[355]);
                    vlSelfRef.b = 0x46U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[354]);
                        vlSelfRef.b = 0x88U;
                    } else {
                        ++(vlSymsp->__Vcoverage[353]);
                        vlSelfRef.b = 0x90U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[352]);
                    vlSelfRef.b = 0x2aU;
                } else {
                    ++(vlSymsp->__Vcoverage[351]);
                    vlSelfRef.b = 0x22U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[350]);
                    vlSelfRef.b = 0xdcU;
                } else {
                    ++(vlSymsp->__Vcoverage[349]);
                    vlSelfRef.b = 0x4fU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                ++(vlSymsp->__Vcoverage[348]);
                vlSelfRef.b = 0x81U;
            } else {
                ++(vlSymsp->__Vcoverage[347]);
                vlSelfRef.b = 0x60U;
            }
        } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][1U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][1U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[346]);
                        vlSelfRef.b = 0x73U;
                    } else {
                        ++(vlSymsp->__Vcoverage[345]);
                        vlSelfRef.b = 0x19U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[344]);
                    vlSelfRef.b = 0x5dU;
                } else {
                    ++(vlSymsp->__Vcoverage[343]);
                    vlSelfRef.b = 0x64U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[342]);
                    vlSelfRef.b = 0x3dU;
                } else {
                    ++(vlSymsp->__Vcoverage[341]);
                    vlSelfRef.b = 0x7eU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                ++(vlSymsp->__Vcoverage[340]);
                vlSelfRef.b = 0xa7U;
            } else {
                ++(vlSymsp->__Vcoverage[339]);
                vlSelfRef.b = 0xc4U;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][1U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[338]);
                    vlSelfRef.b = 0x17U;
                } else {
                    ++(vlSymsp->__Vcoverage[337]);
                    vlSelfRef.b = 0x44U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                ++(vlSymsp->__Vcoverage[336]);
                vlSelfRef.b = 0x97U;
            } else {
                ++(vlSymsp->__Vcoverage[335]);
                vlSelfRef.b = 0x5fU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][1U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][1U])) {
                ++(vlSymsp->__Vcoverage[334]);
                vlSelfRef.b = 0xecU;
            } else {
                ++(vlSymsp->__Vcoverage[333]);
                vlSelfRef.b = 0x13U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][1U])) {
            ++(vlSymsp->__Vcoverage[332]);
            vlSelfRef.b = 0x0cU;
        } else {
            ++(vlSymsp->__Vcoverage[331]);
            vlSelfRef.b = 0xcdU;
        }
    } else if ((0x00000040U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [1U][1U])) {
        if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [1U][1U])) {
            if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][1U])) {
                if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][1U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [1U][1U])) {
                                ++(vlSymsp->__Vcoverage[330]);
                                vlSelfRef.b = 0xd2U;
                            } else {
                                ++(vlSymsp->__Vcoverage[329]);
                                vlSelfRef.b = 0xf3U;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [1U][1U])) {
                            ++(vlSymsp->__Vcoverage[328]);
                            vlSelfRef.b = 0xffU;
                        } else {
                            ++(vlSymsp->__Vcoverage[327]);
                            vlSelfRef.b = 0x10U;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][1U])) {
                            ++(vlSymsp->__Vcoverage[326]);
                            vlSelfRef.b = 0x21U;
                        } else {
                            ++(vlSymsp->__Vcoverage[325]);
                            vlSelfRef.b = 0xdaU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[324]);
                        vlSelfRef.b = 0xb6U;
                    } else {
                        ++(vlSymsp->__Vcoverage[323]);
                        vlSelfRef.b = 0xbcU;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][1U])) {
                            ++(vlSymsp->__Vcoverage[322]);
                            vlSelfRef.b = 0xf5U;
                        } else {
                            ++(vlSymsp->__Vcoverage[321]);
                            vlSelfRef.b = 0x38U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[320]);
                        vlSelfRef.b = 0x9dU;
                    } else {
                        ++(vlSymsp->__Vcoverage[319]);
                        vlSelfRef.b = 0x92U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[318]);
                        vlSelfRef.b = 0x8fU;
                    } else {
                        ++(vlSymsp->__Vcoverage[317]);
                        vlSelfRef.b = 0x40U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[316]);
                    vlSelfRef.b = 0xa3U;
                } else {
                    ++(vlSymsp->__Vcoverage[315]);
                    vlSelfRef.b = 0x51U;
                }
            } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][1U])) {
                            ++(vlSymsp->__Vcoverage[314]);
                            vlSelfRef.b = 0xa8U;
                        } else {
                            ++(vlSymsp->__Vcoverage[313]);
                            vlSelfRef.b = 0x9fU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[312]);
                        vlSelfRef.b = 0x3cU;
                    } else {
                        ++(vlSymsp->__Vcoverage[311]);
                        vlSelfRef.b = 0x50U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[310]);
                        vlSelfRef.b = 0x7fU;
                    } else {
                        ++(vlSymsp->__Vcoverage[309]);
                        vlSelfRef.b = 2U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[308]);
                    vlSelfRef.b = 0xf9U;
                } else {
                    ++(vlSymsp->__Vcoverage[307]);
                    vlSelfRef.b = 0x45U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[306]);
                        vlSelfRef.b = 0x85U;
                    } else {
                        ++(vlSymsp->__Vcoverage[305]);
                        vlSelfRef.b = 0x33U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[304]);
                    vlSelfRef.b = 0x4dU;
                } else {
                    ++(vlSymsp->__Vcoverage[303]);
                    vlSelfRef.b = 0x43U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[302]);
                    vlSelfRef.b = 0xfbU;
                } else {
                    ++(vlSymsp->__Vcoverage[301]);
                    vlSelfRef.b = 0xaaU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                ++(vlSymsp->__Vcoverage[300]);
                vlSelfRef.b = 0xefU;
            } else {
                ++(vlSymsp->__Vcoverage[299]);
                vlSelfRef.b = 0xd0U;
            }
        } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][1U])) {
            if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][1U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][1U])) {
                            ++(vlSymsp->__Vcoverage[298]);
                            vlSelfRef.b = 0xcfU;
                        } else {
                            ++(vlSymsp->__Vcoverage[297]);
                            vlSelfRef.b = 0x58U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[296]);
                        vlSelfRef.b = 0x4cU;
                    } else {
                        ++(vlSymsp->__Vcoverage[295]);
                        vlSelfRef.b = 0x4aU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[294]);
                        vlSelfRef.b = 0x39U;
                    } else {
                        ++(vlSymsp->__Vcoverage[293]);
                        vlSelfRef.b = 0xbeU;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[292]);
                    vlSelfRef.b = 0xcbU;
                } else {
                    ++(vlSymsp->__Vcoverage[291]);
                    vlSelfRef.b = 0x6aU;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[290]);
                        vlSelfRef.b = 0x5bU;
                    } else {
                        ++(vlSymsp->__Vcoverage[289]);
                        vlSelfRef.b = 0xb1U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[288]);
                    vlSelfRef.b = 0xfcU;
                } else {
                    ++(vlSymsp->__Vcoverage[287]);
                    vlSelfRef.b = 0x20U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[286]);
                    vlSelfRef.b = 0xedU;
                } else {
                    ++(vlSymsp->__Vcoverage[285]);
                    vlSelfRef.b = 0U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                ++(vlSymsp->__Vcoverage[284]);
                vlSelfRef.b = 0xd1U;
            } else {
                ++(vlSymsp->__Vcoverage[283]);
                vlSelfRef.b = 0x53U;
            }
        } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][1U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][1U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[282]);
                        vlSelfRef.b = 0x84U;
                    } else {
                        ++(vlSymsp->__Vcoverage[281]);
                        vlSelfRef.b = 0x2fU;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[280]);
                    vlSelfRef.b = 0xe3U;
                } else {
                    ++(vlSymsp->__Vcoverage[279]);
                    vlSelfRef.b = 0x29U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[278]);
                    vlSelfRef.b = 0xb3U;
                } else {
                    ++(vlSymsp->__Vcoverage[277]);
                    vlSelfRef.b = 0xd6U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                ++(vlSymsp->__Vcoverage[276]);
                vlSelfRef.b = 0x3bU;
            } else {
                ++(vlSymsp->__Vcoverage[275]);
                vlSelfRef.b = 0x52U;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][1U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[274]);
                    vlSelfRef.b = 0xa0U;
                } else {
                    ++(vlSymsp->__Vcoverage[273]);
                    vlSelfRef.b = 0x5aU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                ++(vlSymsp->__Vcoverage[272]);
                vlSelfRef.b = 0x6eU;
            } else {
                ++(vlSymsp->__Vcoverage[271]);
                vlSelfRef.b = 0x1bU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][1U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][1U])) {
                ++(vlSymsp->__Vcoverage[270]);
                vlSelfRef.b = 0x1aU;
            } else {
                ++(vlSymsp->__Vcoverage[269]);
                vlSelfRef.b = 0x2cU;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][1U])) {
            ++(vlSymsp->__Vcoverage[268]);
            vlSelfRef.b = 0x83U;
        } else {
            ++(vlSymsp->__Vcoverage[267]);
            vlSelfRef.b = 9U;
        }
    } else if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [1U][1U])) {
        if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [1U][1U])) {
            if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][1U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][1U])) {
                            ++(vlSymsp->__Vcoverage[266]);
                            vlSelfRef.b = 0x75U;
                        } else {
                            ++(vlSymsp->__Vcoverage[265]);
                            vlSelfRef.b = 0xb2U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[264]);
                        vlSelfRef.b = 0x27U;
                    } else {
                        ++(vlSymsp->__Vcoverage[263]);
                        vlSelfRef.b = 0xebU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[262]);
                        vlSelfRef.b = 0xe2U;
                    } else {
                        ++(vlSymsp->__Vcoverage[261]);
                        vlSelfRef.b = 0x80U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[260]);
                    vlSelfRef.b = 0x12U;
                } else {
                    ++(vlSymsp->__Vcoverage[259]);
                    vlSelfRef.b = 7U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[258]);
                        vlSelfRef.b = 0x9aU;
                    } else {
                        ++(vlSymsp->__Vcoverage[257]);
                        vlSelfRef.b = 5U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[256]);
                    vlSelfRef.b = 0x96U;
                } else {
                    ++(vlSymsp->__Vcoverage[255]);
                    vlSelfRef.b = 0x18U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[254]);
                    vlSelfRef.b = 0xc3U;
                } else {
                    ++(vlSymsp->__Vcoverage[253]);
                    vlSelfRef.b = 0x23U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                ++(vlSymsp->__Vcoverage[252]);
                vlSelfRef.b = 0xc7U;
            } else {
                ++(vlSymsp->__Vcoverage[251]);
                vlSelfRef.b = 4U;
            }
        } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][1U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][1U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[250]);
                        vlSelfRef.b = 0x15U;
                    } else {
                        ++(vlSymsp->__Vcoverage[249]);
                        vlSelfRef.b = 0x31U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[248]);
                    vlSelfRef.b = 0xd8U;
                } else {
                    ++(vlSymsp->__Vcoverage[247]);
                    vlSelfRef.b = 0x71U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[246]);
                    vlSelfRef.b = 0xf1U;
                } else {
                    ++(vlSymsp->__Vcoverage[245]);
                    vlSelfRef.b = 0xe5U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                ++(vlSymsp->__Vcoverage[244]);
                vlSelfRef.b = 0xa5U;
            } else {
                ++(vlSymsp->__Vcoverage[243]);
                vlSelfRef.b = 0x34U;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][1U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[242]);
                    vlSelfRef.b = 0xccU;
                } else {
                    ++(vlSymsp->__Vcoverage[241]);
                    vlSelfRef.b = 0xf7U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                ++(vlSymsp->__Vcoverage[240]);
                vlSelfRef.b = 0x3fU;
            } else {
                ++(vlSymsp->__Vcoverage[239]);
                vlSelfRef.b = 0x36U;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][1U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][1U])) {
                ++(vlSymsp->__Vcoverage[238]);
                vlSelfRef.b = 0x26U;
            } else {
                ++(vlSymsp->__Vcoverage[237]);
                vlSelfRef.b = 0x93U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][1U])) {
            ++(vlSymsp->__Vcoverage[236]);
            vlSelfRef.b = 0xfdU;
        } else {
            ++(vlSymsp->__Vcoverage[235]);
            vlSelfRef.b = 0xb7U;
        }
    } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [1U][1U])) {
        if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [1U][1U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][1U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][1U])) {
                        ++(vlSymsp->__Vcoverage[234]);
                        vlSelfRef.b = 0xc0U;
                    } else {
                        ++(vlSymsp->__Vcoverage[233]);
                        vlSelfRef.b = 0x72U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[232]);
                    vlSelfRef.b = 0xa4U;
                } else {
                    ++(vlSymsp->__Vcoverage[231]);
                    vlSelfRef.b = 0x9cU;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[230]);
                    vlSelfRef.b = 0xafU;
                } else {
                    ++(vlSymsp->__Vcoverage[229]);
                    vlSelfRef.b = 0xa2U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                ++(vlSymsp->__Vcoverage[228]);
                vlSelfRef.b = 0xd4U;
            } else {
                ++(vlSymsp->__Vcoverage[227]);
                vlSelfRef.b = 0xadU;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][1U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[226]);
                    vlSelfRef.b = 0xf0U;
                } else {
                    ++(vlSymsp->__Vcoverage[225]);
                    vlSelfRef.b = 0x47U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                ++(vlSymsp->__Vcoverage[224]);
                vlSelfRef.b = 0x59U;
            } else {
                ++(vlSymsp->__Vcoverage[223]);
                vlSelfRef.b = 0xfaU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][1U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][1U])) {
                ++(vlSymsp->__Vcoverage[222]);
                vlSelfRef.b = 0x7dU;
            } else {
                ++(vlSymsp->__Vcoverage[221]);
                vlSelfRef.b = 0xc9U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][1U])) {
            ++(vlSymsp->__Vcoverage[220]);
            vlSelfRef.b = 0x82U;
        } else {
            ++(vlSymsp->__Vcoverage[219]);
            vlSelfRef.b = 0xcaU;
        }
    } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [1U][1U])) {
        if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [1U][1U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][1U])) {
                    ++(vlSymsp->__Vcoverage[218]);
                    vlSelfRef.b = 0x76U;
                } else {
                    ++(vlSymsp->__Vcoverage[217]);
                    vlSelfRef.b = 0xabU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][1U])) {
                ++(vlSymsp->__Vcoverage[216]);
                vlSelfRef.b = 0xd7U;
            } else {
                ++(vlSymsp->__Vcoverage[215]);
                vlSelfRef.b = 0xfeU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][1U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][1U])) {
                ++(vlSymsp->__Vcoverage[214]);
                vlSelfRef.b = 0x2bU;
            } else {
                ++(vlSymsp->__Vcoverage[213]);
                vlSelfRef.b = 0x67U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][1U])) {
            ++(vlSymsp->__Vcoverage[212]);
            vlSelfRef.b = 1U;
        } else {
            ++(vlSymsp->__Vcoverage[211]);
            vlSelfRef.b = 0x30U;
        }
    } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [1U][1U])) {
        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [1U][1U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][1U])) {
                ++(vlSymsp->__Vcoverage[210]);
                vlSelfRef.b = 0xc5U;
            } else {
                ++(vlSymsp->__Vcoverage[209]);
                vlSelfRef.b = 0x6fU;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][1U])) {
            ++(vlSymsp->__Vcoverage[208]);
            vlSelfRef.b = 0x6bU;
        } else {
            ++(vlSymsp->__Vcoverage[207]);
            vlSelfRef.b = 0xf2U;
        }
    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [1U][1U])) {
        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [1U][1U])) {
            ++(vlSymsp->__Vcoverage[206]);
            vlSelfRef.b = 0x7bU;
        } else {
            ++(vlSymsp->__Vcoverage[205]);
            vlSelfRef.b = 0x77U;
        }
    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [1U][1U])) {
        ++(vlSymsp->__Vcoverage[204]);
        vlSelfRef.b = 0x7cU;
    } else {
        ++(vlSymsp->__Vcoverage[203]);
        vlSelfRef.b = 0x63U;
    }
    ++(vlSymsp->__Vcoverage[459]);
}

void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__1__KET____DOT__sbox_row__BRA__1__KET____DOT__u_sbox__1(Vtb_aes_sbox* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+            Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__1__KET____DOT__sbox_row__BRA__1__KET____DOT__u_sbox__1\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.a = vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
        [1U][1U];
}

void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__1__KET____DOT__sbox_row__BRA__2__KET____DOT__u_sbox__0(Vtb_aes_sbox* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+            Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__1__KET____DOT__sbox_row__BRA__2__KET____DOT__u_sbox__0\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((0x00000080U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
         [1U][2U])) {
        if ((0x00000040U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [1U][2U])) {
            if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][2U])) {
                if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][2U])) {
                            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [1U][2U])) {
                                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                     [1U][2U])) {
                                    vlSelfRef.b = 0x16U;
                                    ++(vlSymsp->__Vcoverage[458]);
                                } else {
                                    ++(vlSymsp->__Vcoverage[457]);
                                    vlSelfRef.b = 0xbbU;
                                }
                            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                        [1U][2U])) {
                                ++(vlSymsp->__Vcoverage[456]);
                                vlSelfRef.b = 0x54U;
                            } else {
                                ++(vlSymsp->__Vcoverage[455]);
                                vlSelfRef.b = 0xb0U;
                            }
                        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [1U][2U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [1U][2U])) {
                                ++(vlSymsp->__Vcoverage[454]);
                                vlSelfRef.b = 0x0fU;
                            } else {
                                ++(vlSymsp->__Vcoverage[453]);
                                vlSelfRef.b = 0x2dU;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [1U][2U])) {
                            ++(vlSymsp->__Vcoverage[452]);
                            vlSelfRef.b = 0x99U;
                        } else {
                            ++(vlSymsp->__Vcoverage[451]);
                            vlSelfRef.b = 0x41U;
                        }
                    } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][2U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][2U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [1U][2U])) {
                                ++(vlSymsp->__Vcoverage[450]);
                                vlSelfRef.b = 0x68U;
                            } else {
                                ++(vlSymsp->__Vcoverage[449]);
                                vlSelfRef.b = 0x42U;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [1U][2U])) {
                            ++(vlSymsp->__Vcoverage[448]);
                            vlSelfRef.b = 0xe6U;
                        } else {
                            ++(vlSymsp->__Vcoverage[447]);
                            vlSelfRef.b = 0xbfU;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][2U])) {
                            ++(vlSymsp->__Vcoverage[446]);
                            vlSelfRef.b = 0x0dU;
                        } else {
                            ++(vlSymsp->__Vcoverage[445]);
                            vlSelfRef.b = 0x89U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[444]);
                        vlSelfRef.b = 0xa1U;
                    } else {
                        ++(vlSymsp->__Vcoverage[443]);
                        vlSelfRef.b = 0x8cU;
                    }
                } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][2U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [1U][2U])) {
                                ++(vlSymsp->__Vcoverage[442]);
                                vlSelfRef.b = 0xdfU;
                            } else {
                                ++(vlSymsp->__Vcoverage[441]);
                                vlSelfRef.b = 0x28U;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [1U][2U])) {
                            ++(vlSymsp->__Vcoverage[440]);
                            vlSelfRef.b = 0x55U;
                        } else {
                            ++(vlSymsp->__Vcoverage[439]);
                            vlSelfRef.b = 0xceU;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][2U])) {
                            ++(vlSymsp->__Vcoverage[438]);
                            vlSelfRef.b = 0xe9U;
                        } else {
                            ++(vlSymsp->__Vcoverage[437]);
                            vlSelfRef.b = 0x87U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[436]);
                        vlSelfRef.b = 0x1eU;
                    } else {
                        ++(vlSymsp->__Vcoverage[435]);
                        vlSelfRef.b = 0x9bU;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][2U])) {
                            ++(vlSymsp->__Vcoverage[434]);
                            vlSelfRef.b = 0x94U;
                        } else {
                            ++(vlSymsp->__Vcoverage[433]);
                            vlSelfRef.b = 0x8eU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[432]);
                        vlSelfRef.b = 0xd9U;
                    } else {
                        ++(vlSymsp->__Vcoverage[431]);
                        vlSelfRef.b = 0x69U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[430]);
                        vlSelfRef.b = 0x11U;
                    } else {
                        ++(vlSymsp->__Vcoverage[429]);
                        vlSelfRef.b = 0x98U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[428]);
                    vlSelfRef.b = 0xf8U;
                } else {
                    ++(vlSymsp->__Vcoverage[427]);
                    vlSelfRef.b = 0xe1U;
                }
            } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][2U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [1U][2U])) {
                                ++(vlSymsp->__Vcoverage[426]);
                                vlSelfRef.b = 0x9eU;
                            } else {
                                ++(vlSymsp->__Vcoverage[425]);
                                vlSelfRef.b = 0x1dU;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [1U][2U])) {
                            ++(vlSymsp->__Vcoverage[424]);
                            vlSelfRef.b = 0xc1U;
                        } else {
                            ++(vlSymsp->__Vcoverage[423]);
                            vlSelfRef.b = 0x86U;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][2U])) {
                            ++(vlSymsp->__Vcoverage[422]);
                            vlSelfRef.b = 0xb9U;
                        } else {
                            ++(vlSymsp->__Vcoverage[421]);
                            vlSelfRef.b = 0x57U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[420]);
                        vlSelfRef.b = 0x35U;
                    } else {
                        ++(vlSymsp->__Vcoverage[419]);
                        vlSelfRef.b = 0x61U;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][2U])) {
                            ++(vlSymsp->__Vcoverage[418]);
                            vlSelfRef.b = 0x0eU;
                        } else {
                            ++(vlSymsp->__Vcoverage[417]);
                            vlSelfRef.b = 0xf6U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[416]);
                        vlSelfRef.b = 3U;
                    } else {
                        ++(vlSymsp->__Vcoverage[415]);
                        vlSelfRef.b = 0x48U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[414]);
                        vlSelfRef.b = 0x66U;
                    } else {
                        ++(vlSymsp->__Vcoverage[413]);
                        vlSelfRef.b = 0xb5U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[412]);
                    vlSelfRef.b = 0x3eU;
                } else {
                    ++(vlSymsp->__Vcoverage[411]);
                    vlSelfRef.b = 0x70U;
                }
            } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][2U])) {
                            ++(vlSymsp->__Vcoverage[410]);
                            vlSelfRef.b = 0x8aU;
                        } else {
                            ++(vlSymsp->__Vcoverage[409]);
                            vlSelfRef.b = 0x8bU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[408]);
                        vlSelfRef.b = 0xbdU;
                    } else {
                        ++(vlSymsp->__Vcoverage[407]);
                        vlSelfRef.b = 0x4bU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[406]);
                        vlSelfRef.b = 0x1fU;
                    } else {
                        ++(vlSymsp->__Vcoverage[405]);
                        vlSelfRef.b = 0x74U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[404]);
                    vlSelfRef.b = 0xddU;
                } else {
                    ++(vlSymsp->__Vcoverage[403]);
                    vlSelfRef.b = 0xe8U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[402]);
                        vlSelfRef.b = 0xc6U;
                    } else {
                        ++(vlSymsp->__Vcoverage[401]);
                        vlSelfRef.b = 0xb4U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[400]);
                    vlSelfRef.b = 0xa6U;
                } else {
                    ++(vlSymsp->__Vcoverage[399]);
                    vlSelfRef.b = 0x1cU;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[398]);
                    vlSelfRef.b = 0x2eU;
                } else {
                    ++(vlSymsp->__Vcoverage[397]);
                    vlSelfRef.b = 0x25U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                ++(vlSymsp->__Vcoverage[396]);
                vlSelfRef.b = 0x78U;
            } else {
                ++(vlSymsp->__Vcoverage[395]);
                vlSelfRef.b = 0xbaU;
            }
        } else if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][2U])) {
            if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][2U])) {
                if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][2U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [1U][2U])) {
                                ++(vlSymsp->__Vcoverage[394]);
                                vlSelfRef.b = 8U;
                            } else {
                                ++(vlSymsp->__Vcoverage[393]);
                                vlSelfRef.b = 0xaeU;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [1U][2U])) {
                            ++(vlSymsp->__Vcoverage[392]);
                            vlSelfRef.b = 0x7aU;
                        } else {
                            ++(vlSymsp->__Vcoverage[391]);
                            vlSelfRef.b = 0x65U;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][2U])) {
                            ++(vlSymsp->__Vcoverage[390]);
                            vlSelfRef.b = 0xeaU;
                        } else {
                            ++(vlSymsp->__Vcoverage[389]);
                            vlSelfRef.b = 0xf4U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[388]);
                        vlSelfRef.b = 0x56U;
                    } else {
                        ++(vlSymsp->__Vcoverage[387]);
                        vlSelfRef.b = 0x6cU;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][2U])) {
                            ++(vlSymsp->__Vcoverage[386]);
                            vlSelfRef.b = 0xa9U;
                        } else {
                            ++(vlSymsp->__Vcoverage[385]);
                            vlSelfRef.b = 0x4eU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[384]);
                        vlSelfRef.b = 0xd5U;
                    } else {
                        ++(vlSymsp->__Vcoverage[383]);
                        vlSelfRef.b = 0x8dU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[382]);
                        vlSelfRef.b = 0x6dU;
                    } else {
                        ++(vlSymsp->__Vcoverage[381]);
                        vlSelfRef.b = 0x37U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[380]);
                    vlSelfRef.b = 0xc8U;
                } else {
                    ++(vlSymsp->__Vcoverage[379]);
                    vlSelfRef.b = 0xe7U;
                }
            } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][2U])) {
                            ++(vlSymsp->__Vcoverage[378]);
                            vlSelfRef.b = 0x79U;
                        } else {
                            ++(vlSymsp->__Vcoverage[377]);
                            vlSelfRef.b = 0xe4U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[376]);
                        vlSelfRef.b = 0x95U;
                    } else {
                        ++(vlSymsp->__Vcoverage[375]);
                        vlSelfRef.b = 0x91U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[374]);
                        vlSelfRef.b = 0x62U;
                    } else {
                        ++(vlSymsp->__Vcoverage[373]);
                        vlSelfRef.b = 0xacU;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[372]);
                    vlSelfRef.b = 0xd3U;
                } else {
                    ++(vlSymsp->__Vcoverage[371]);
                    vlSelfRef.b = 0xc2U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[370]);
                        vlSelfRef.b = 0x5cU;
                    } else {
                        ++(vlSymsp->__Vcoverage[369]);
                        vlSelfRef.b = 0x24U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[368]);
                    vlSelfRef.b = 6U;
                } else {
                    ++(vlSymsp->__Vcoverage[367]);
                    vlSelfRef.b = 0x49U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[366]);
                    vlSelfRef.b = 0x0aU;
                } else {
                    ++(vlSymsp->__Vcoverage[365]);
                    vlSelfRef.b = 0x3aU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                ++(vlSymsp->__Vcoverage[364]);
                vlSelfRef.b = 0x32U;
            } else {
                ++(vlSymsp->__Vcoverage[363]);
                vlSelfRef.b = 0xe0U;
            }
        } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][2U])) {
            if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][2U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][2U])) {
                            ++(vlSymsp->__Vcoverage[362]);
                            vlSelfRef.b = 0xdbU;
                        } else {
                            ++(vlSymsp->__Vcoverage[361]);
                            vlSelfRef.b = 0x0bU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[360]);
                        vlSelfRef.b = 0x5eU;
                    } else {
                        ++(vlSymsp->__Vcoverage[359]);
                        vlSelfRef.b = 0xdeU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[358]);
                        vlSelfRef.b = 0x14U;
                    } else {
                        ++(vlSymsp->__Vcoverage[357]);
                        vlSelfRef.b = 0xb8U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[356]);
                    vlSelfRef.b = 0xeeU;
                } else {
                    ++(vlSymsp->__Vcoverage[355]);
                    vlSelfRef.b = 0x46U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[354]);
                        vlSelfRef.b = 0x88U;
                    } else {
                        ++(vlSymsp->__Vcoverage[353]);
                        vlSelfRef.b = 0x90U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[352]);
                    vlSelfRef.b = 0x2aU;
                } else {
                    ++(vlSymsp->__Vcoverage[351]);
                    vlSelfRef.b = 0x22U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[350]);
                    vlSelfRef.b = 0xdcU;
                } else {
                    ++(vlSymsp->__Vcoverage[349]);
                    vlSelfRef.b = 0x4fU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                ++(vlSymsp->__Vcoverage[348]);
                vlSelfRef.b = 0x81U;
            } else {
                ++(vlSymsp->__Vcoverage[347]);
                vlSelfRef.b = 0x60U;
            }
        } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][2U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][2U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[346]);
                        vlSelfRef.b = 0x73U;
                    } else {
                        ++(vlSymsp->__Vcoverage[345]);
                        vlSelfRef.b = 0x19U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[344]);
                    vlSelfRef.b = 0x5dU;
                } else {
                    ++(vlSymsp->__Vcoverage[343]);
                    vlSelfRef.b = 0x64U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[342]);
                    vlSelfRef.b = 0x3dU;
                } else {
                    ++(vlSymsp->__Vcoverage[341]);
                    vlSelfRef.b = 0x7eU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                ++(vlSymsp->__Vcoverage[340]);
                vlSelfRef.b = 0xa7U;
            } else {
                ++(vlSymsp->__Vcoverage[339]);
                vlSelfRef.b = 0xc4U;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][2U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[338]);
                    vlSelfRef.b = 0x17U;
                } else {
                    ++(vlSymsp->__Vcoverage[337]);
                    vlSelfRef.b = 0x44U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                ++(vlSymsp->__Vcoverage[336]);
                vlSelfRef.b = 0x97U;
            } else {
                ++(vlSymsp->__Vcoverage[335]);
                vlSelfRef.b = 0x5fU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][2U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][2U])) {
                ++(vlSymsp->__Vcoverage[334]);
                vlSelfRef.b = 0xecU;
            } else {
                ++(vlSymsp->__Vcoverage[333]);
                vlSelfRef.b = 0x13U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][2U])) {
            ++(vlSymsp->__Vcoverage[332]);
            vlSelfRef.b = 0x0cU;
        } else {
            ++(vlSymsp->__Vcoverage[331]);
            vlSelfRef.b = 0xcdU;
        }
    } else if ((0x00000040U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [1U][2U])) {
        if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [1U][2U])) {
            if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][2U])) {
                if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][2U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [1U][2U])) {
                                ++(vlSymsp->__Vcoverage[330]);
                                vlSelfRef.b = 0xd2U;
                            } else {
                                ++(vlSymsp->__Vcoverage[329]);
                                vlSelfRef.b = 0xf3U;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [1U][2U])) {
                            ++(vlSymsp->__Vcoverage[328]);
                            vlSelfRef.b = 0xffU;
                        } else {
                            ++(vlSymsp->__Vcoverage[327]);
                            vlSelfRef.b = 0x10U;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][2U])) {
                            ++(vlSymsp->__Vcoverage[326]);
                            vlSelfRef.b = 0x21U;
                        } else {
                            ++(vlSymsp->__Vcoverage[325]);
                            vlSelfRef.b = 0xdaU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[324]);
                        vlSelfRef.b = 0xb6U;
                    } else {
                        ++(vlSymsp->__Vcoverage[323]);
                        vlSelfRef.b = 0xbcU;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][2U])) {
                            ++(vlSymsp->__Vcoverage[322]);
                            vlSelfRef.b = 0xf5U;
                        } else {
                            ++(vlSymsp->__Vcoverage[321]);
                            vlSelfRef.b = 0x38U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[320]);
                        vlSelfRef.b = 0x9dU;
                    } else {
                        ++(vlSymsp->__Vcoverage[319]);
                        vlSelfRef.b = 0x92U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[318]);
                        vlSelfRef.b = 0x8fU;
                    } else {
                        ++(vlSymsp->__Vcoverage[317]);
                        vlSelfRef.b = 0x40U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[316]);
                    vlSelfRef.b = 0xa3U;
                } else {
                    ++(vlSymsp->__Vcoverage[315]);
                    vlSelfRef.b = 0x51U;
                }
            } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][2U])) {
                            ++(vlSymsp->__Vcoverage[314]);
                            vlSelfRef.b = 0xa8U;
                        } else {
                            ++(vlSymsp->__Vcoverage[313]);
                            vlSelfRef.b = 0x9fU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[312]);
                        vlSelfRef.b = 0x3cU;
                    } else {
                        ++(vlSymsp->__Vcoverage[311]);
                        vlSelfRef.b = 0x50U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[310]);
                        vlSelfRef.b = 0x7fU;
                    } else {
                        ++(vlSymsp->__Vcoverage[309]);
                        vlSelfRef.b = 2U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[308]);
                    vlSelfRef.b = 0xf9U;
                } else {
                    ++(vlSymsp->__Vcoverage[307]);
                    vlSelfRef.b = 0x45U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[306]);
                        vlSelfRef.b = 0x85U;
                    } else {
                        ++(vlSymsp->__Vcoverage[305]);
                        vlSelfRef.b = 0x33U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[304]);
                    vlSelfRef.b = 0x4dU;
                } else {
                    ++(vlSymsp->__Vcoverage[303]);
                    vlSelfRef.b = 0x43U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[302]);
                    vlSelfRef.b = 0xfbU;
                } else {
                    ++(vlSymsp->__Vcoverage[301]);
                    vlSelfRef.b = 0xaaU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                ++(vlSymsp->__Vcoverage[300]);
                vlSelfRef.b = 0xefU;
            } else {
                ++(vlSymsp->__Vcoverage[299]);
                vlSelfRef.b = 0xd0U;
            }
        } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][2U])) {
            if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][2U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][2U])) {
                            ++(vlSymsp->__Vcoverage[298]);
                            vlSelfRef.b = 0xcfU;
                        } else {
                            ++(vlSymsp->__Vcoverage[297]);
                            vlSelfRef.b = 0x58U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[296]);
                        vlSelfRef.b = 0x4cU;
                    } else {
                        ++(vlSymsp->__Vcoverage[295]);
                        vlSelfRef.b = 0x4aU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[294]);
                        vlSelfRef.b = 0x39U;
                    } else {
                        ++(vlSymsp->__Vcoverage[293]);
                        vlSelfRef.b = 0xbeU;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[292]);
                    vlSelfRef.b = 0xcbU;
                } else {
                    ++(vlSymsp->__Vcoverage[291]);
                    vlSelfRef.b = 0x6aU;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[290]);
                        vlSelfRef.b = 0x5bU;
                    } else {
                        ++(vlSymsp->__Vcoverage[289]);
                        vlSelfRef.b = 0xb1U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[288]);
                    vlSelfRef.b = 0xfcU;
                } else {
                    ++(vlSymsp->__Vcoverage[287]);
                    vlSelfRef.b = 0x20U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[286]);
                    vlSelfRef.b = 0xedU;
                } else {
                    ++(vlSymsp->__Vcoverage[285]);
                    vlSelfRef.b = 0U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                ++(vlSymsp->__Vcoverage[284]);
                vlSelfRef.b = 0xd1U;
            } else {
                ++(vlSymsp->__Vcoverage[283]);
                vlSelfRef.b = 0x53U;
            }
        } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][2U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][2U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[282]);
                        vlSelfRef.b = 0x84U;
                    } else {
                        ++(vlSymsp->__Vcoverage[281]);
                        vlSelfRef.b = 0x2fU;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[280]);
                    vlSelfRef.b = 0xe3U;
                } else {
                    ++(vlSymsp->__Vcoverage[279]);
                    vlSelfRef.b = 0x29U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[278]);
                    vlSelfRef.b = 0xb3U;
                } else {
                    ++(vlSymsp->__Vcoverage[277]);
                    vlSelfRef.b = 0xd6U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                ++(vlSymsp->__Vcoverage[276]);
                vlSelfRef.b = 0x3bU;
            } else {
                ++(vlSymsp->__Vcoverage[275]);
                vlSelfRef.b = 0x52U;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][2U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[274]);
                    vlSelfRef.b = 0xa0U;
                } else {
                    ++(vlSymsp->__Vcoverage[273]);
                    vlSelfRef.b = 0x5aU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                ++(vlSymsp->__Vcoverage[272]);
                vlSelfRef.b = 0x6eU;
            } else {
                ++(vlSymsp->__Vcoverage[271]);
                vlSelfRef.b = 0x1bU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][2U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][2U])) {
                ++(vlSymsp->__Vcoverage[270]);
                vlSelfRef.b = 0x1aU;
            } else {
                ++(vlSymsp->__Vcoverage[269]);
                vlSelfRef.b = 0x2cU;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][2U])) {
            ++(vlSymsp->__Vcoverage[268]);
            vlSelfRef.b = 0x83U;
        } else {
            ++(vlSymsp->__Vcoverage[267]);
            vlSelfRef.b = 9U;
        }
    } else if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [1U][2U])) {
        if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [1U][2U])) {
            if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][2U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][2U])) {
                            ++(vlSymsp->__Vcoverage[266]);
                            vlSelfRef.b = 0x75U;
                        } else {
                            ++(vlSymsp->__Vcoverage[265]);
                            vlSelfRef.b = 0xb2U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[264]);
                        vlSelfRef.b = 0x27U;
                    } else {
                        ++(vlSymsp->__Vcoverage[263]);
                        vlSelfRef.b = 0xebU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[262]);
                        vlSelfRef.b = 0xe2U;
                    } else {
                        ++(vlSymsp->__Vcoverage[261]);
                        vlSelfRef.b = 0x80U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[260]);
                    vlSelfRef.b = 0x12U;
                } else {
                    ++(vlSymsp->__Vcoverage[259]);
                    vlSelfRef.b = 7U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[258]);
                        vlSelfRef.b = 0x9aU;
                    } else {
                        ++(vlSymsp->__Vcoverage[257]);
                        vlSelfRef.b = 5U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[256]);
                    vlSelfRef.b = 0x96U;
                } else {
                    ++(vlSymsp->__Vcoverage[255]);
                    vlSelfRef.b = 0x18U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[254]);
                    vlSelfRef.b = 0xc3U;
                } else {
                    ++(vlSymsp->__Vcoverage[253]);
                    vlSelfRef.b = 0x23U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                ++(vlSymsp->__Vcoverage[252]);
                vlSelfRef.b = 0xc7U;
            } else {
                ++(vlSymsp->__Vcoverage[251]);
                vlSelfRef.b = 4U;
            }
        } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][2U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][2U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[250]);
                        vlSelfRef.b = 0x15U;
                    } else {
                        ++(vlSymsp->__Vcoverage[249]);
                        vlSelfRef.b = 0x31U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[248]);
                    vlSelfRef.b = 0xd8U;
                } else {
                    ++(vlSymsp->__Vcoverage[247]);
                    vlSelfRef.b = 0x71U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[246]);
                    vlSelfRef.b = 0xf1U;
                } else {
                    ++(vlSymsp->__Vcoverage[245]);
                    vlSelfRef.b = 0xe5U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                ++(vlSymsp->__Vcoverage[244]);
                vlSelfRef.b = 0xa5U;
            } else {
                ++(vlSymsp->__Vcoverage[243]);
                vlSelfRef.b = 0x34U;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][2U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[242]);
                    vlSelfRef.b = 0xccU;
                } else {
                    ++(vlSymsp->__Vcoverage[241]);
                    vlSelfRef.b = 0xf7U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                ++(vlSymsp->__Vcoverage[240]);
                vlSelfRef.b = 0x3fU;
            } else {
                ++(vlSymsp->__Vcoverage[239]);
                vlSelfRef.b = 0x36U;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][2U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][2U])) {
                ++(vlSymsp->__Vcoverage[238]);
                vlSelfRef.b = 0x26U;
            } else {
                ++(vlSymsp->__Vcoverage[237]);
                vlSelfRef.b = 0x93U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][2U])) {
            ++(vlSymsp->__Vcoverage[236]);
            vlSelfRef.b = 0xfdU;
        } else {
            ++(vlSymsp->__Vcoverage[235]);
            vlSelfRef.b = 0xb7U;
        }
    } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [1U][2U])) {
        if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [1U][2U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][2U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][2U])) {
                        ++(vlSymsp->__Vcoverage[234]);
                        vlSelfRef.b = 0xc0U;
                    } else {
                        ++(vlSymsp->__Vcoverage[233]);
                        vlSelfRef.b = 0x72U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[232]);
                    vlSelfRef.b = 0xa4U;
                } else {
                    ++(vlSymsp->__Vcoverage[231]);
                    vlSelfRef.b = 0x9cU;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[230]);
                    vlSelfRef.b = 0xafU;
                } else {
                    ++(vlSymsp->__Vcoverage[229]);
                    vlSelfRef.b = 0xa2U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                ++(vlSymsp->__Vcoverage[228]);
                vlSelfRef.b = 0xd4U;
            } else {
                ++(vlSymsp->__Vcoverage[227]);
                vlSelfRef.b = 0xadU;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][2U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[226]);
                    vlSelfRef.b = 0xf0U;
                } else {
                    ++(vlSymsp->__Vcoverage[225]);
                    vlSelfRef.b = 0x47U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                ++(vlSymsp->__Vcoverage[224]);
                vlSelfRef.b = 0x59U;
            } else {
                ++(vlSymsp->__Vcoverage[223]);
                vlSelfRef.b = 0xfaU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][2U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][2U])) {
                ++(vlSymsp->__Vcoverage[222]);
                vlSelfRef.b = 0x7dU;
            } else {
                ++(vlSymsp->__Vcoverage[221]);
                vlSelfRef.b = 0xc9U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][2U])) {
            ++(vlSymsp->__Vcoverage[220]);
            vlSelfRef.b = 0x82U;
        } else {
            ++(vlSymsp->__Vcoverage[219]);
            vlSelfRef.b = 0xcaU;
        }
    } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [1U][2U])) {
        if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [1U][2U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][2U])) {
                    ++(vlSymsp->__Vcoverage[218]);
                    vlSelfRef.b = 0x76U;
                } else {
                    ++(vlSymsp->__Vcoverage[217]);
                    vlSelfRef.b = 0xabU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][2U])) {
                ++(vlSymsp->__Vcoverage[216]);
                vlSelfRef.b = 0xd7U;
            } else {
                ++(vlSymsp->__Vcoverage[215]);
                vlSelfRef.b = 0xfeU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][2U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][2U])) {
                ++(vlSymsp->__Vcoverage[214]);
                vlSelfRef.b = 0x2bU;
            } else {
                ++(vlSymsp->__Vcoverage[213]);
                vlSelfRef.b = 0x67U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][2U])) {
            ++(vlSymsp->__Vcoverage[212]);
            vlSelfRef.b = 1U;
        } else {
            ++(vlSymsp->__Vcoverage[211]);
            vlSelfRef.b = 0x30U;
        }
    } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [1U][2U])) {
        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [1U][2U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][2U])) {
                ++(vlSymsp->__Vcoverage[210]);
                vlSelfRef.b = 0xc5U;
            } else {
                ++(vlSymsp->__Vcoverage[209]);
                vlSelfRef.b = 0x6fU;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][2U])) {
            ++(vlSymsp->__Vcoverage[208]);
            vlSelfRef.b = 0x6bU;
        } else {
            ++(vlSymsp->__Vcoverage[207]);
            vlSelfRef.b = 0xf2U;
        }
    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [1U][2U])) {
        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [1U][2U])) {
            ++(vlSymsp->__Vcoverage[206]);
            vlSelfRef.b = 0x7bU;
        } else {
            ++(vlSymsp->__Vcoverage[205]);
            vlSelfRef.b = 0x77U;
        }
    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [1U][2U])) {
        ++(vlSymsp->__Vcoverage[204]);
        vlSelfRef.b = 0x7cU;
    } else {
        ++(vlSymsp->__Vcoverage[203]);
        vlSelfRef.b = 0x63U;
    }
    ++(vlSymsp->__Vcoverage[459]);
}

void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__1__KET____DOT__sbox_row__BRA__2__KET____DOT__u_sbox__1(Vtb_aes_sbox* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+            Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__1__KET____DOT__sbox_row__BRA__2__KET____DOT__u_sbox__1\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.a = vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
        [1U][2U];
}

void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__1__KET____DOT__sbox_row__BRA__3__KET____DOT__u_sbox__0(Vtb_aes_sbox* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+            Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__1__KET____DOT__sbox_row__BRA__3__KET____DOT__u_sbox__0\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((0x00000080U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
         [1U][3U])) {
        if ((0x00000040U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [1U][3U])) {
            if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][3U])) {
                if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][3U])) {
                            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [1U][3U])) {
                                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                     [1U][3U])) {
                                    vlSelfRef.b = 0x16U;
                                    ++(vlSymsp->__Vcoverage[458]);
                                } else {
                                    ++(vlSymsp->__Vcoverage[457]);
                                    vlSelfRef.b = 0xbbU;
                                }
                            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                        [1U][3U])) {
                                ++(vlSymsp->__Vcoverage[456]);
                                vlSelfRef.b = 0x54U;
                            } else {
                                ++(vlSymsp->__Vcoverage[455]);
                                vlSelfRef.b = 0xb0U;
                            }
                        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [1U][3U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [1U][3U])) {
                                ++(vlSymsp->__Vcoverage[454]);
                                vlSelfRef.b = 0x0fU;
                            } else {
                                ++(vlSymsp->__Vcoverage[453]);
                                vlSelfRef.b = 0x2dU;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [1U][3U])) {
                            ++(vlSymsp->__Vcoverage[452]);
                            vlSelfRef.b = 0x99U;
                        } else {
                            ++(vlSymsp->__Vcoverage[451]);
                            vlSelfRef.b = 0x41U;
                        }
                    } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][3U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][3U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [1U][3U])) {
                                ++(vlSymsp->__Vcoverage[450]);
                                vlSelfRef.b = 0x68U;
                            } else {
                                ++(vlSymsp->__Vcoverage[449]);
                                vlSelfRef.b = 0x42U;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [1U][3U])) {
                            ++(vlSymsp->__Vcoverage[448]);
                            vlSelfRef.b = 0xe6U;
                        } else {
                            ++(vlSymsp->__Vcoverage[447]);
                            vlSelfRef.b = 0xbfU;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][3U])) {
                            ++(vlSymsp->__Vcoverage[446]);
                            vlSelfRef.b = 0x0dU;
                        } else {
                            ++(vlSymsp->__Vcoverage[445]);
                            vlSelfRef.b = 0x89U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[444]);
                        vlSelfRef.b = 0xa1U;
                    } else {
                        ++(vlSymsp->__Vcoverage[443]);
                        vlSelfRef.b = 0x8cU;
                    }
                } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][3U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [1U][3U])) {
                                ++(vlSymsp->__Vcoverage[442]);
                                vlSelfRef.b = 0xdfU;
                            } else {
                                ++(vlSymsp->__Vcoverage[441]);
                                vlSelfRef.b = 0x28U;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [1U][3U])) {
                            ++(vlSymsp->__Vcoverage[440]);
                            vlSelfRef.b = 0x55U;
                        } else {
                            ++(vlSymsp->__Vcoverage[439]);
                            vlSelfRef.b = 0xceU;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][3U])) {
                            ++(vlSymsp->__Vcoverage[438]);
                            vlSelfRef.b = 0xe9U;
                        } else {
                            ++(vlSymsp->__Vcoverage[437]);
                            vlSelfRef.b = 0x87U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[436]);
                        vlSelfRef.b = 0x1eU;
                    } else {
                        ++(vlSymsp->__Vcoverage[435]);
                        vlSelfRef.b = 0x9bU;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][3U])) {
                            ++(vlSymsp->__Vcoverage[434]);
                            vlSelfRef.b = 0x94U;
                        } else {
                            ++(vlSymsp->__Vcoverage[433]);
                            vlSelfRef.b = 0x8eU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[432]);
                        vlSelfRef.b = 0xd9U;
                    } else {
                        ++(vlSymsp->__Vcoverage[431]);
                        vlSelfRef.b = 0x69U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[430]);
                        vlSelfRef.b = 0x11U;
                    } else {
                        ++(vlSymsp->__Vcoverage[429]);
                        vlSelfRef.b = 0x98U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[428]);
                    vlSelfRef.b = 0xf8U;
                } else {
                    ++(vlSymsp->__Vcoverage[427]);
                    vlSelfRef.b = 0xe1U;
                }
            } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][3U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [1U][3U])) {
                                ++(vlSymsp->__Vcoverage[426]);
                                vlSelfRef.b = 0x9eU;
                            } else {
                                ++(vlSymsp->__Vcoverage[425]);
                                vlSelfRef.b = 0x1dU;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [1U][3U])) {
                            ++(vlSymsp->__Vcoverage[424]);
                            vlSelfRef.b = 0xc1U;
                        } else {
                            ++(vlSymsp->__Vcoverage[423]);
                            vlSelfRef.b = 0x86U;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][3U])) {
                            ++(vlSymsp->__Vcoverage[422]);
                            vlSelfRef.b = 0xb9U;
                        } else {
                            ++(vlSymsp->__Vcoverage[421]);
                            vlSelfRef.b = 0x57U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[420]);
                        vlSelfRef.b = 0x35U;
                    } else {
                        ++(vlSymsp->__Vcoverage[419]);
                        vlSelfRef.b = 0x61U;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][3U])) {
                            ++(vlSymsp->__Vcoverage[418]);
                            vlSelfRef.b = 0x0eU;
                        } else {
                            ++(vlSymsp->__Vcoverage[417]);
                            vlSelfRef.b = 0xf6U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[416]);
                        vlSelfRef.b = 3U;
                    } else {
                        ++(vlSymsp->__Vcoverage[415]);
                        vlSelfRef.b = 0x48U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[414]);
                        vlSelfRef.b = 0x66U;
                    } else {
                        ++(vlSymsp->__Vcoverage[413]);
                        vlSelfRef.b = 0xb5U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[412]);
                    vlSelfRef.b = 0x3eU;
                } else {
                    ++(vlSymsp->__Vcoverage[411]);
                    vlSelfRef.b = 0x70U;
                }
            } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][3U])) {
                            ++(vlSymsp->__Vcoverage[410]);
                            vlSelfRef.b = 0x8aU;
                        } else {
                            ++(vlSymsp->__Vcoverage[409]);
                            vlSelfRef.b = 0x8bU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[408]);
                        vlSelfRef.b = 0xbdU;
                    } else {
                        ++(vlSymsp->__Vcoverage[407]);
                        vlSelfRef.b = 0x4bU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[406]);
                        vlSelfRef.b = 0x1fU;
                    } else {
                        ++(vlSymsp->__Vcoverage[405]);
                        vlSelfRef.b = 0x74U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[404]);
                    vlSelfRef.b = 0xddU;
                } else {
                    ++(vlSymsp->__Vcoverage[403]);
                    vlSelfRef.b = 0xe8U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[402]);
                        vlSelfRef.b = 0xc6U;
                    } else {
                        ++(vlSymsp->__Vcoverage[401]);
                        vlSelfRef.b = 0xb4U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[400]);
                    vlSelfRef.b = 0xa6U;
                } else {
                    ++(vlSymsp->__Vcoverage[399]);
                    vlSelfRef.b = 0x1cU;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[398]);
                    vlSelfRef.b = 0x2eU;
                } else {
                    ++(vlSymsp->__Vcoverage[397]);
                    vlSelfRef.b = 0x25U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                ++(vlSymsp->__Vcoverage[396]);
                vlSelfRef.b = 0x78U;
            } else {
                ++(vlSymsp->__Vcoverage[395]);
                vlSelfRef.b = 0xbaU;
            }
        } else if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][3U])) {
            if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][3U])) {
                if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][3U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [1U][3U])) {
                                ++(vlSymsp->__Vcoverage[394]);
                                vlSelfRef.b = 8U;
                            } else {
                                ++(vlSymsp->__Vcoverage[393]);
                                vlSelfRef.b = 0xaeU;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [1U][3U])) {
                            ++(vlSymsp->__Vcoverage[392]);
                            vlSelfRef.b = 0x7aU;
                        } else {
                            ++(vlSymsp->__Vcoverage[391]);
                            vlSelfRef.b = 0x65U;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][3U])) {
                            ++(vlSymsp->__Vcoverage[390]);
                            vlSelfRef.b = 0xeaU;
                        } else {
                            ++(vlSymsp->__Vcoverage[389]);
                            vlSelfRef.b = 0xf4U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[388]);
                        vlSelfRef.b = 0x56U;
                    } else {
                        ++(vlSymsp->__Vcoverage[387]);
                        vlSelfRef.b = 0x6cU;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][3U])) {
                            ++(vlSymsp->__Vcoverage[386]);
                            vlSelfRef.b = 0xa9U;
                        } else {
                            ++(vlSymsp->__Vcoverage[385]);
                            vlSelfRef.b = 0x4eU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[384]);
                        vlSelfRef.b = 0xd5U;
                    } else {
                        ++(vlSymsp->__Vcoverage[383]);
                        vlSelfRef.b = 0x8dU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[382]);
                        vlSelfRef.b = 0x6dU;
                    } else {
                        ++(vlSymsp->__Vcoverage[381]);
                        vlSelfRef.b = 0x37U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[380]);
                    vlSelfRef.b = 0xc8U;
                } else {
                    ++(vlSymsp->__Vcoverage[379]);
                    vlSelfRef.b = 0xe7U;
                }
            } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][3U])) {
                            ++(vlSymsp->__Vcoverage[378]);
                            vlSelfRef.b = 0x79U;
                        } else {
                            ++(vlSymsp->__Vcoverage[377]);
                            vlSelfRef.b = 0xe4U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[376]);
                        vlSelfRef.b = 0x95U;
                    } else {
                        ++(vlSymsp->__Vcoverage[375]);
                        vlSelfRef.b = 0x91U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[374]);
                        vlSelfRef.b = 0x62U;
                    } else {
                        ++(vlSymsp->__Vcoverage[373]);
                        vlSelfRef.b = 0xacU;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[372]);
                    vlSelfRef.b = 0xd3U;
                } else {
                    ++(vlSymsp->__Vcoverage[371]);
                    vlSelfRef.b = 0xc2U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[370]);
                        vlSelfRef.b = 0x5cU;
                    } else {
                        ++(vlSymsp->__Vcoverage[369]);
                        vlSelfRef.b = 0x24U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[368]);
                    vlSelfRef.b = 6U;
                } else {
                    ++(vlSymsp->__Vcoverage[367]);
                    vlSelfRef.b = 0x49U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[366]);
                    vlSelfRef.b = 0x0aU;
                } else {
                    ++(vlSymsp->__Vcoverage[365]);
                    vlSelfRef.b = 0x3aU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                ++(vlSymsp->__Vcoverage[364]);
                vlSelfRef.b = 0x32U;
            } else {
                ++(vlSymsp->__Vcoverage[363]);
                vlSelfRef.b = 0xe0U;
            }
        } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][3U])) {
            if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][3U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][3U])) {
                            ++(vlSymsp->__Vcoverage[362]);
                            vlSelfRef.b = 0xdbU;
                        } else {
                            ++(vlSymsp->__Vcoverage[361]);
                            vlSelfRef.b = 0x0bU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[360]);
                        vlSelfRef.b = 0x5eU;
                    } else {
                        ++(vlSymsp->__Vcoverage[359]);
                        vlSelfRef.b = 0xdeU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[358]);
                        vlSelfRef.b = 0x14U;
                    } else {
                        ++(vlSymsp->__Vcoverage[357]);
                        vlSelfRef.b = 0xb8U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[356]);
                    vlSelfRef.b = 0xeeU;
                } else {
                    ++(vlSymsp->__Vcoverage[355]);
                    vlSelfRef.b = 0x46U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[354]);
                        vlSelfRef.b = 0x88U;
                    } else {
                        ++(vlSymsp->__Vcoverage[353]);
                        vlSelfRef.b = 0x90U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[352]);
                    vlSelfRef.b = 0x2aU;
                } else {
                    ++(vlSymsp->__Vcoverage[351]);
                    vlSelfRef.b = 0x22U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[350]);
                    vlSelfRef.b = 0xdcU;
                } else {
                    ++(vlSymsp->__Vcoverage[349]);
                    vlSelfRef.b = 0x4fU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                ++(vlSymsp->__Vcoverage[348]);
                vlSelfRef.b = 0x81U;
            } else {
                ++(vlSymsp->__Vcoverage[347]);
                vlSelfRef.b = 0x60U;
            }
        } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][3U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][3U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[346]);
                        vlSelfRef.b = 0x73U;
                    } else {
                        ++(vlSymsp->__Vcoverage[345]);
                        vlSelfRef.b = 0x19U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[344]);
                    vlSelfRef.b = 0x5dU;
                } else {
                    ++(vlSymsp->__Vcoverage[343]);
                    vlSelfRef.b = 0x64U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[342]);
                    vlSelfRef.b = 0x3dU;
                } else {
                    ++(vlSymsp->__Vcoverage[341]);
                    vlSelfRef.b = 0x7eU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                ++(vlSymsp->__Vcoverage[340]);
                vlSelfRef.b = 0xa7U;
            } else {
                ++(vlSymsp->__Vcoverage[339]);
                vlSelfRef.b = 0xc4U;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][3U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[338]);
                    vlSelfRef.b = 0x17U;
                } else {
                    ++(vlSymsp->__Vcoverage[337]);
                    vlSelfRef.b = 0x44U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                ++(vlSymsp->__Vcoverage[336]);
                vlSelfRef.b = 0x97U;
            } else {
                ++(vlSymsp->__Vcoverage[335]);
                vlSelfRef.b = 0x5fU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][3U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][3U])) {
                ++(vlSymsp->__Vcoverage[334]);
                vlSelfRef.b = 0xecU;
            } else {
                ++(vlSymsp->__Vcoverage[333]);
                vlSelfRef.b = 0x13U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][3U])) {
            ++(vlSymsp->__Vcoverage[332]);
            vlSelfRef.b = 0x0cU;
        } else {
            ++(vlSymsp->__Vcoverage[331]);
            vlSelfRef.b = 0xcdU;
        }
    } else if ((0x00000040U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [1U][3U])) {
        if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [1U][3U])) {
            if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][3U])) {
                if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][3U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [1U][3U])) {
                                ++(vlSymsp->__Vcoverage[330]);
                                vlSelfRef.b = 0xd2U;
                            } else {
                                ++(vlSymsp->__Vcoverage[329]);
                                vlSelfRef.b = 0xf3U;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [1U][3U])) {
                            ++(vlSymsp->__Vcoverage[328]);
                            vlSelfRef.b = 0xffU;
                        } else {
                            ++(vlSymsp->__Vcoverage[327]);
                            vlSelfRef.b = 0x10U;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][3U])) {
                            ++(vlSymsp->__Vcoverage[326]);
                            vlSelfRef.b = 0x21U;
                        } else {
                            ++(vlSymsp->__Vcoverage[325]);
                            vlSelfRef.b = 0xdaU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[324]);
                        vlSelfRef.b = 0xb6U;
                    } else {
                        ++(vlSymsp->__Vcoverage[323]);
                        vlSelfRef.b = 0xbcU;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][3U])) {
                            ++(vlSymsp->__Vcoverage[322]);
                            vlSelfRef.b = 0xf5U;
                        } else {
                            ++(vlSymsp->__Vcoverage[321]);
                            vlSelfRef.b = 0x38U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[320]);
                        vlSelfRef.b = 0x9dU;
                    } else {
                        ++(vlSymsp->__Vcoverage[319]);
                        vlSelfRef.b = 0x92U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[318]);
                        vlSelfRef.b = 0x8fU;
                    } else {
                        ++(vlSymsp->__Vcoverage[317]);
                        vlSelfRef.b = 0x40U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[316]);
                    vlSelfRef.b = 0xa3U;
                } else {
                    ++(vlSymsp->__Vcoverage[315]);
                    vlSelfRef.b = 0x51U;
                }
            } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][3U])) {
                            ++(vlSymsp->__Vcoverage[314]);
                            vlSelfRef.b = 0xa8U;
                        } else {
                            ++(vlSymsp->__Vcoverage[313]);
                            vlSelfRef.b = 0x9fU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[312]);
                        vlSelfRef.b = 0x3cU;
                    } else {
                        ++(vlSymsp->__Vcoverage[311]);
                        vlSelfRef.b = 0x50U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[310]);
                        vlSelfRef.b = 0x7fU;
                    } else {
                        ++(vlSymsp->__Vcoverage[309]);
                        vlSelfRef.b = 2U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[308]);
                    vlSelfRef.b = 0xf9U;
                } else {
                    ++(vlSymsp->__Vcoverage[307]);
                    vlSelfRef.b = 0x45U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[306]);
                        vlSelfRef.b = 0x85U;
                    } else {
                        ++(vlSymsp->__Vcoverage[305]);
                        vlSelfRef.b = 0x33U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[304]);
                    vlSelfRef.b = 0x4dU;
                } else {
                    ++(vlSymsp->__Vcoverage[303]);
                    vlSelfRef.b = 0x43U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[302]);
                    vlSelfRef.b = 0xfbU;
                } else {
                    ++(vlSymsp->__Vcoverage[301]);
                    vlSelfRef.b = 0xaaU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                ++(vlSymsp->__Vcoverage[300]);
                vlSelfRef.b = 0xefU;
            } else {
                ++(vlSymsp->__Vcoverage[299]);
                vlSelfRef.b = 0xd0U;
            }
        } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][3U])) {
            if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][3U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][3U])) {
                            ++(vlSymsp->__Vcoverage[298]);
                            vlSelfRef.b = 0xcfU;
                        } else {
                            ++(vlSymsp->__Vcoverage[297]);
                            vlSelfRef.b = 0x58U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[296]);
                        vlSelfRef.b = 0x4cU;
                    } else {
                        ++(vlSymsp->__Vcoverage[295]);
                        vlSelfRef.b = 0x4aU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[294]);
                        vlSelfRef.b = 0x39U;
                    } else {
                        ++(vlSymsp->__Vcoverage[293]);
                        vlSelfRef.b = 0xbeU;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[292]);
                    vlSelfRef.b = 0xcbU;
                } else {
                    ++(vlSymsp->__Vcoverage[291]);
                    vlSelfRef.b = 0x6aU;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[290]);
                        vlSelfRef.b = 0x5bU;
                    } else {
                        ++(vlSymsp->__Vcoverage[289]);
                        vlSelfRef.b = 0xb1U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[288]);
                    vlSelfRef.b = 0xfcU;
                } else {
                    ++(vlSymsp->__Vcoverage[287]);
                    vlSelfRef.b = 0x20U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[286]);
                    vlSelfRef.b = 0xedU;
                } else {
                    ++(vlSymsp->__Vcoverage[285]);
                    vlSelfRef.b = 0U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                ++(vlSymsp->__Vcoverage[284]);
                vlSelfRef.b = 0xd1U;
            } else {
                ++(vlSymsp->__Vcoverage[283]);
                vlSelfRef.b = 0x53U;
            }
        } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][3U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][3U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[282]);
                        vlSelfRef.b = 0x84U;
                    } else {
                        ++(vlSymsp->__Vcoverage[281]);
                        vlSelfRef.b = 0x2fU;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[280]);
                    vlSelfRef.b = 0xe3U;
                } else {
                    ++(vlSymsp->__Vcoverage[279]);
                    vlSelfRef.b = 0x29U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[278]);
                    vlSelfRef.b = 0xb3U;
                } else {
                    ++(vlSymsp->__Vcoverage[277]);
                    vlSelfRef.b = 0xd6U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                ++(vlSymsp->__Vcoverage[276]);
                vlSelfRef.b = 0x3bU;
            } else {
                ++(vlSymsp->__Vcoverage[275]);
                vlSelfRef.b = 0x52U;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][3U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[274]);
                    vlSelfRef.b = 0xa0U;
                } else {
                    ++(vlSymsp->__Vcoverage[273]);
                    vlSelfRef.b = 0x5aU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                ++(vlSymsp->__Vcoverage[272]);
                vlSelfRef.b = 0x6eU;
            } else {
                ++(vlSymsp->__Vcoverage[271]);
                vlSelfRef.b = 0x1bU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][3U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][3U])) {
                ++(vlSymsp->__Vcoverage[270]);
                vlSelfRef.b = 0x1aU;
            } else {
                ++(vlSymsp->__Vcoverage[269]);
                vlSelfRef.b = 0x2cU;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][3U])) {
            ++(vlSymsp->__Vcoverage[268]);
            vlSelfRef.b = 0x83U;
        } else {
            ++(vlSymsp->__Vcoverage[267]);
            vlSelfRef.b = 9U;
        }
    } else if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [1U][3U])) {
        if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [1U][3U])) {
            if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][3U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [1U][3U])) {
                            ++(vlSymsp->__Vcoverage[266]);
                            vlSelfRef.b = 0x75U;
                        } else {
                            ++(vlSymsp->__Vcoverage[265]);
                            vlSelfRef.b = 0xb2U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[264]);
                        vlSelfRef.b = 0x27U;
                    } else {
                        ++(vlSymsp->__Vcoverage[263]);
                        vlSelfRef.b = 0xebU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[262]);
                        vlSelfRef.b = 0xe2U;
                    } else {
                        ++(vlSymsp->__Vcoverage[261]);
                        vlSelfRef.b = 0x80U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[260]);
                    vlSelfRef.b = 0x12U;
                } else {
                    ++(vlSymsp->__Vcoverage[259]);
                    vlSelfRef.b = 7U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[258]);
                        vlSelfRef.b = 0x9aU;
                    } else {
                        ++(vlSymsp->__Vcoverage[257]);
                        vlSelfRef.b = 5U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[256]);
                    vlSelfRef.b = 0x96U;
                } else {
                    ++(vlSymsp->__Vcoverage[255]);
                    vlSelfRef.b = 0x18U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[254]);
                    vlSelfRef.b = 0xc3U;
                } else {
                    ++(vlSymsp->__Vcoverage[253]);
                    vlSelfRef.b = 0x23U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                ++(vlSymsp->__Vcoverage[252]);
                vlSelfRef.b = 0xc7U;
            } else {
                ++(vlSymsp->__Vcoverage[251]);
                vlSelfRef.b = 4U;
            }
        } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][3U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][3U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[250]);
                        vlSelfRef.b = 0x15U;
                    } else {
                        ++(vlSymsp->__Vcoverage[249]);
                        vlSelfRef.b = 0x31U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[248]);
                    vlSelfRef.b = 0xd8U;
                } else {
                    ++(vlSymsp->__Vcoverage[247]);
                    vlSelfRef.b = 0x71U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[246]);
                    vlSelfRef.b = 0xf1U;
                } else {
                    ++(vlSymsp->__Vcoverage[245]);
                    vlSelfRef.b = 0xe5U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                ++(vlSymsp->__Vcoverage[244]);
                vlSelfRef.b = 0xa5U;
            } else {
                ++(vlSymsp->__Vcoverage[243]);
                vlSelfRef.b = 0x34U;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][3U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[242]);
                    vlSelfRef.b = 0xccU;
                } else {
                    ++(vlSymsp->__Vcoverage[241]);
                    vlSelfRef.b = 0xf7U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                ++(vlSymsp->__Vcoverage[240]);
                vlSelfRef.b = 0x3fU;
            } else {
                ++(vlSymsp->__Vcoverage[239]);
                vlSelfRef.b = 0x36U;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][3U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][3U])) {
                ++(vlSymsp->__Vcoverage[238]);
                vlSelfRef.b = 0x26U;
            } else {
                ++(vlSymsp->__Vcoverage[237]);
                vlSelfRef.b = 0x93U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][3U])) {
            ++(vlSymsp->__Vcoverage[236]);
            vlSelfRef.b = 0xfdU;
        } else {
            ++(vlSymsp->__Vcoverage[235]);
            vlSelfRef.b = 0xb7U;
        }
    } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [1U][3U])) {
        if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [1U][3U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][3U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [1U][3U])) {
                        ++(vlSymsp->__Vcoverage[234]);
                        vlSelfRef.b = 0xc0U;
                    } else {
                        ++(vlSymsp->__Vcoverage[233]);
                        vlSelfRef.b = 0x72U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[232]);
                    vlSelfRef.b = 0xa4U;
                } else {
                    ++(vlSymsp->__Vcoverage[231]);
                    vlSelfRef.b = 0x9cU;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[230]);
                    vlSelfRef.b = 0xafU;
                } else {
                    ++(vlSymsp->__Vcoverage[229]);
                    vlSelfRef.b = 0xa2U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                ++(vlSymsp->__Vcoverage[228]);
                vlSelfRef.b = 0xd4U;
            } else {
                ++(vlSymsp->__Vcoverage[227]);
                vlSelfRef.b = 0xadU;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][3U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[226]);
                    vlSelfRef.b = 0xf0U;
                } else {
                    ++(vlSymsp->__Vcoverage[225]);
                    vlSelfRef.b = 0x47U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                ++(vlSymsp->__Vcoverage[224]);
                vlSelfRef.b = 0x59U;
            } else {
                ++(vlSymsp->__Vcoverage[223]);
                vlSelfRef.b = 0xfaU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][3U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][3U])) {
                ++(vlSymsp->__Vcoverage[222]);
                vlSelfRef.b = 0x7dU;
            } else {
                ++(vlSymsp->__Vcoverage[221]);
                vlSelfRef.b = 0xc9U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][3U])) {
            ++(vlSymsp->__Vcoverage[220]);
            vlSelfRef.b = 0x82U;
        } else {
            ++(vlSymsp->__Vcoverage[219]);
            vlSelfRef.b = 0xcaU;
        }
    } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [1U][3U])) {
        if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [1U][3U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [1U][3U])) {
                    ++(vlSymsp->__Vcoverage[218]);
                    vlSelfRef.b = 0x76U;
                } else {
                    ++(vlSymsp->__Vcoverage[217]);
                    vlSelfRef.b = 0xabU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [1U][3U])) {
                ++(vlSymsp->__Vcoverage[216]);
                vlSelfRef.b = 0xd7U;
            } else {
                ++(vlSymsp->__Vcoverage[215]);
                vlSelfRef.b = 0xfeU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][3U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][3U])) {
                ++(vlSymsp->__Vcoverage[214]);
                vlSelfRef.b = 0x2bU;
            } else {
                ++(vlSymsp->__Vcoverage[213]);
                vlSelfRef.b = 0x67U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][3U])) {
            ++(vlSymsp->__Vcoverage[212]);
            vlSelfRef.b = 1U;
        } else {
            ++(vlSymsp->__Vcoverage[211]);
            vlSelfRef.b = 0x30U;
        }
    } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [1U][3U])) {
        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [1U][3U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [1U][3U])) {
                ++(vlSymsp->__Vcoverage[210]);
                vlSelfRef.b = 0xc5U;
            } else {
                ++(vlSymsp->__Vcoverage[209]);
                vlSelfRef.b = 0x6fU;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [1U][3U])) {
            ++(vlSymsp->__Vcoverage[208]);
            vlSelfRef.b = 0x6bU;
        } else {
            ++(vlSymsp->__Vcoverage[207]);
            vlSelfRef.b = 0xf2U;
        }
    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [1U][3U])) {
        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [1U][3U])) {
            ++(vlSymsp->__Vcoverage[206]);
            vlSelfRef.b = 0x7bU;
        } else {
            ++(vlSymsp->__Vcoverage[205]);
            vlSelfRef.b = 0x77U;
        }
    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [1U][3U])) {
        ++(vlSymsp->__Vcoverage[204]);
        vlSelfRef.b = 0x7cU;
    } else {
        ++(vlSymsp->__Vcoverage[203]);
        vlSelfRef.b = 0x63U;
    }
    ++(vlSymsp->__Vcoverage[459]);
}

void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__1__KET____DOT__sbox_row__BRA__3__KET____DOT__u_sbox__1(Vtb_aes_sbox* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+            Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__1__KET____DOT__sbox_row__BRA__3__KET____DOT__u_sbox__1\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.a = vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
        [1U][3U];
}

void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__2__KET____DOT__sbox_row__BRA__0__KET____DOT__u_sbox__0(Vtb_aes_sbox* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+            Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__2__KET____DOT__sbox_row__BRA__0__KET____DOT__u_sbox__0\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((0x00000080U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
         [2U][0U])) {
        if ((0x00000040U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][0U])) {
            if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][0U])) {
                if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][0U])) {
                            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][0U])) {
                                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                     [2U][0U])) {
                                    vlSelfRef.b = 0x16U;
                                    ++(vlSymsp->__Vcoverage[458]);
                                } else {
                                    ++(vlSymsp->__Vcoverage[457]);
                                    vlSelfRef.b = 0xbbU;
                                }
                            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                        [2U][0U])) {
                                ++(vlSymsp->__Vcoverage[456]);
                                vlSelfRef.b = 0x54U;
                            } else {
                                ++(vlSymsp->__Vcoverage[455]);
                                vlSelfRef.b = 0xb0U;
                            }
                        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][0U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][0U])) {
                                ++(vlSymsp->__Vcoverage[454]);
                                vlSelfRef.b = 0x0fU;
                            } else {
                                ++(vlSymsp->__Vcoverage[453]);
                                vlSelfRef.b = 0x2dU;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][0U])) {
                            ++(vlSymsp->__Vcoverage[452]);
                            vlSelfRef.b = 0x99U;
                        } else {
                            ++(vlSymsp->__Vcoverage[451]);
                            vlSelfRef.b = 0x41U;
                        }
                    } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][0U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][0U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][0U])) {
                                ++(vlSymsp->__Vcoverage[450]);
                                vlSelfRef.b = 0x68U;
                            } else {
                                ++(vlSymsp->__Vcoverage[449]);
                                vlSelfRef.b = 0x42U;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][0U])) {
                            ++(vlSymsp->__Vcoverage[448]);
                            vlSelfRef.b = 0xe6U;
                        } else {
                            ++(vlSymsp->__Vcoverage[447]);
                            vlSelfRef.b = 0xbfU;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][0U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][0U])) {
                            ++(vlSymsp->__Vcoverage[446]);
                            vlSelfRef.b = 0x0dU;
                        } else {
                            ++(vlSymsp->__Vcoverage[445]);
                            vlSelfRef.b = 0x89U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[444]);
                        vlSelfRef.b = 0xa1U;
                    } else {
                        ++(vlSymsp->__Vcoverage[443]);
                        vlSelfRef.b = 0x8cU;
                    }
                } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][0U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][0U])) {
                                ++(vlSymsp->__Vcoverage[442]);
                                vlSelfRef.b = 0xdfU;
                            } else {
                                ++(vlSymsp->__Vcoverage[441]);
                                vlSelfRef.b = 0x28U;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][0U])) {
                            ++(vlSymsp->__Vcoverage[440]);
                            vlSelfRef.b = 0x55U;
                        } else {
                            ++(vlSymsp->__Vcoverage[439]);
                            vlSelfRef.b = 0xceU;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][0U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][0U])) {
                            ++(vlSymsp->__Vcoverage[438]);
                            vlSelfRef.b = 0xe9U;
                        } else {
                            ++(vlSymsp->__Vcoverage[437]);
                            vlSelfRef.b = 0x87U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[436]);
                        vlSelfRef.b = 0x1eU;
                    } else {
                        ++(vlSymsp->__Vcoverage[435]);
                        vlSelfRef.b = 0x9bU;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][0U])) {
                            ++(vlSymsp->__Vcoverage[434]);
                            vlSelfRef.b = 0x94U;
                        } else {
                            ++(vlSymsp->__Vcoverage[433]);
                            vlSelfRef.b = 0x8eU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[432]);
                        vlSelfRef.b = 0xd9U;
                    } else {
                        ++(vlSymsp->__Vcoverage[431]);
                        vlSelfRef.b = 0x69U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[430]);
                        vlSelfRef.b = 0x11U;
                    } else {
                        ++(vlSymsp->__Vcoverage[429]);
                        vlSelfRef.b = 0x98U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[428]);
                    vlSelfRef.b = 0xf8U;
                } else {
                    ++(vlSymsp->__Vcoverage[427]);
                    vlSelfRef.b = 0xe1U;
                }
            } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][0U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][0U])) {
                                ++(vlSymsp->__Vcoverage[426]);
                                vlSelfRef.b = 0x9eU;
                            } else {
                                ++(vlSymsp->__Vcoverage[425]);
                                vlSelfRef.b = 0x1dU;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][0U])) {
                            ++(vlSymsp->__Vcoverage[424]);
                            vlSelfRef.b = 0xc1U;
                        } else {
                            ++(vlSymsp->__Vcoverage[423]);
                            vlSelfRef.b = 0x86U;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][0U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][0U])) {
                            ++(vlSymsp->__Vcoverage[422]);
                            vlSelfRef.b = 0xb9U;
                        } else {
                            ++(vlSymsp->__Vcoverage[421]);
                            vlSelfRef.b = 0x57U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[420]);
                        vlSelfRef.b = 0x35U;
                    } else {
                        ++(vlSymsp->__Vcoverage[419]);
                        vlSelfRef.b = 0x61U;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][0U])) {
                            ++(vlSymsp->__Vcoverage[418]);
                            vlSelfRef.b = 0x0eU;
                        } else {
                            ++(vlSymsp->__Vcoverage[417]);
                            vlSelfRef.b = 0xf6U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[416]);
                        vlSelfRef.b = 3U;
                    } else {
                        ++(vlSymsp->__Vcoverage[415]);
                        vlSelfRef.b = 0x48U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[414]);
                        vlSelfRef.b = 0x66U;
                    } else {
                        ++(vlSymsp->__Vcoverage[413]);
                        vlSelfRef.b = 0xb5U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[412]);
                    vlSelfRef.b = 0x3eU;
                } else {
                    ++(vlSymsp->__Vcoverage[411]);
                    vlSelfRef.b = 0x70U;
                }
            } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][0U])) {
                            ++(vlSymsp->__Vcoverage[410]);
                            vlSelfRef.b = 0x8aU;
                        } else {
                            ++(vlSymsp->__Vcoverage[409]);
                            vlSelfRef.b = 0x8bU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[408]);
                        vlSelfRef.b = 0xbdU;
                    } else {
                        ++(vlSymsp->__Vcoverage[407]);
                        vlSelfRef.b = 0x4bU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[406]);
                        vlSelfRef.b = 0x1fU;
                    } else {
                        ++(vlSymsp->__Vcoverage[405]);
                        vlSelfRef.b = 0x74U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[404]);
                    vlSelfRef.b = 0xddU;
                } else {
                    ++(vlSymsp->__Vcoverage[403]);
                    vlSelfRef.b = 0xe8U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[402]);
                        vlSelfRef.b = 0xc6U;
                    } else {
                        ++(vlSymsp->__Vcoverage[401]);
                        vlSelfRef.b = 0xb4U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[400]);
                    vlSelfRef.b = 0xa6U;
                } else {
                    ++(vlSymsp->__Vcoverage[399]);
                    vlSelfRef.b = 0x1cU;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[398]);
                    vlSelfRef.b = 0x2eU;
                } else {
                    ++(vlSymsp->__Vcoverage[397]);
                    vlSelfRef.b = 0x25U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                ++(vlSymsp->__Vcoverage[396]);
                vlSelfRef.b = 0x78U;
            } else {
                ++(vlSymsp->__Vcoverage[395]);
                vlSelfRef.b = 0xbaU;
            }
        } else if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][0U])) {
            if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][0U])) {
                if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][0U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][0U])) {
                                ++(vlSymsp->__Vcoverage[394]);
                                vlSelfRef.b = 8U;
                            } else {
                                ++(vlSymsp->__Vcoverage[393]);
                                vlSelfRef.b = 0xaeU;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][0U])) {
                            ++(vlSymsp->__Vcoverage[392]);
                            vlSelfRef.b = 0x7aU;
                        } else {
                            ++(vlSymsp->__Vcoverage[391]);
                            vlSelfRef.b = 0x65U;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][0U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][0U])) {
                            ++(vlSymsp->__Vcoverage[390]);
                            vlSelfRef.b = 0xeaU;
                        } else {
                            ++(vlSymsp->__Vcoverage[389]);
                            vlSelfRef.b = 0xf4U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[388]);
                        vlSelfRef.b = 0x56U;
                    } else {
                        ++(vlSymsp->__Vcoverage[387]);
                        vlSelfRef.b = 0x6cU;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][0U])) {
                            ++(vlSymsp->__Vcoverage[386]);
                            vlSelfRef.b = 0xa9U;
                        } else {
                            ++(vlSymsp->__Vcoverage[385]);
                            vlSelfRef.b = 0x4eU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[384]);
                        vlSelfRef.b = 0xd5U;
                    } else {
                        ++(vlSymsp->__Vcoverage[383]);
                        vlSelfRef.b = 0x8dU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[382]);
                        vlSelfRef.b = 0x6dU;
                    } else {
                        ++(vlSymsp->__Vcoverage[381]);
                        vlSelfRef.b = 0x37U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[380]);
                    vlSelfRef.b = 0xc8U;
                } else {
                    ++(vlSymsp->__Vcoverage[379]);
                    vlSelfRef.b = 0xe7U;
                }
            } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][0U])) {
                            ++(vlSymsp->__Vcoverage[378]);
                            vlSelfRef.b = 0x79U;
                        } else {
                            ++(vlSymsp->__Vcoverage[377]);
                            vlSelfRef.b = 0xe4U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[376]);
                        vlSelfRef.b = 0x95U;
                    } else {
                        ++(vlSymsp->__Vcoverage[375]);
                        vlSelfRef.b = 0x91U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[374]);
                        vlSelfRef.b = 0x62U;
                    } else {
                        ++(vlSymsp->__Vcoverage[373]);
                        vlSelfRef.b = 0xacU;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[372]);
                    vlSelfRef.b = 0xd3U;
                } else {
                    ++(vlSymsp->__Vcoverage[371]);
                    vlSelfRef.b = 0xc2U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[370]);
                        vlSelfRef.b = 0x5cU;
                    } else {
                        ++(vlSymsp->__Vcoverage[369]);
                        vlSelfRef.b = 0x24U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[368]);
                    vlSelfRef.b = 6U;
                } else {
                    ++(vlSymsp->__Vcoverage[367]);
                    vlSelfRef.b = 0x49U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[366]);
                    vlSelfRef.b = 0x0aU;
                } else {
                    ++(vlSymsp->__Vcoverage[365]);
                    vlSelfRef.b = 0x3aU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                ++(vlSymsp->__Vcoverage[364]);
                vlSelfRef.b = 0x32U;
            } else {
                ++(vlSymsp->__Vcoverage[363]);
                vlSelfRef.b = 0xe0U;
            }
        } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][0U])) {
            if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][0U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][0U])) {
                            ++(vlSymsp->__Vcoverage[362]);
                            vlSelfRef.b = 0xdbU;
                        } else {
                            ++(vlSymsp->__Vcoverage[361]);
                            vlSelfRef.b = 0x0bU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[360]);
                        vlSelfRef.b = 0x5eU;
                    } else {
                        ++(vlSymsp->__Vcoverage[359]);
                        vlSelfRef.b = 0xdeU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[358]);
                        vlSelfRef.b = 0x14U;
                    } else {
                        ++(vlSymsp->__Vcoverage[357]);
                        vlSelfRef.b = 0xb8U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[356]);
                    vlSelfRef.b = 0xeeU;
                } else {
                    ++(vlSymsp->__Vcoverage[355]);
                    vlSelfRef.b = 0x46U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[354]);
                        vlSelfRef.b = 0x88U;
                    } else {
                        ++(vlSymsp->__Vcoverage[353]);
                        vlSelfRef.b = 0x90U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[352]);
                    vlSelfRef.b = 0x2aU;
                } else {
                    ++(vlSymsp->__Vcoverage[351]);
                    vlSelfRef.b = 0x22U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[350]);
                    vlSelfRef.b = 0xdcU;
                } else {
                    ++(vlSymsp->__Vcoverage[349]);
                    vlSelfRef.b = 0x4fU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                ++(vlSymsp->__Vcoverage[348]);
                vlSelfRef.b = 0x81U;
            } else {
                ++(vlSymsp->__Vcoverage[347]);
                vlSelfRef.b = 0x60U;
            }
        } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][0U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][0U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[346]);
                        vlSelfRef.b = 0x73U;
                    } else {
                        ++(vlSymsp->__Vcoverage[345]);
                        vlSelfRef.b = 0x19U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[344]);
                    vlSelfRef.b = 0x5dU;
                } else {
                    ++(vlSymsp->__Vcoverage[343]);
                    vlSelfRef.b = 0x64U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[342]);
                    vlSelfRef.b = 0x3dU;
                } else {
                    ++(vlSymsp->__Vcoverage[341]);
                    vlSelfRef.b = 0x7eU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                ++(vlSymsp->__Vcoverage[340]);
                vlSelfRef.b = 0xa7U;
            } else {
                ++(vlSymsp->__Vcoverage[339]);
                vlSelfRef.b = 0xc4U;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][0U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][0U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[338]);
                    vlSelfRef.b = 0x17U;
                } else {
                    ++(vlSymsp->__Vcoverage[337]);
                    vlSelfRef.b = 0x44U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                ++(vlSymsp->__Vcoverage[336]);
                vlSelfRef.b = 0x97U;
            } else {
                ++(vlSymsp->__Vcoverage[335]);
                vlSelfRef.b = 0x5fU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][0U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][0U])) {
                ++(vlSymsp->__Vcoverage[334]);
                vlSelfRef.b = 0xecU;
            } else {
                ++(vlSymsp->__Vcoverage[333]);
                vlSelfRef.b = 0x13U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][0U])) {
            ++(vlSymsp->__Vcoverage[332]);
            vlSelfRef.b = 0x0cU;
        } else {
            ++(vlSymsp->__Vcoverage[331]);
            vlSelfRef.b = 0xcdU;
        }
    } else if ((0x00000040U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][0U])) {
        if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][0U])) {
            if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][0U])) {
                if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][0U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][0U])) {
                                ++(vlSymsp->__Vcoverage[330]);
                                vlSelfRef.b = 0xd2U;
                            } else {
                                ++(vlSymsp->__Vcoverage[329]);
                                vlSelfRef.b = 0xf3U;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][0U])) {
                            ++(vlSymsp->__Vcoverage[328]);
                            vlSelfRef.b = 0xffU;
                        } else {
                            ++(vlSymsp->__Vcoverage[327]);
                            vlSelfRef.b = 0x10U;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][0U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][0U])) {
                            ++(vlSymsp->__Vcoverage[326]);
                            vlSelfRef.b = 0x21U;
                        } else {
                            ++(vlSymsp->__Vcoverage[325]);
                            vlSelfRef.b = 0xdaU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[324]);
                        vlSelfRef.b = 0xb6U;
                    } else {
                        ++(vlSymsp->__Vcoverage[323]);
                        vlSelfRef.b = 0xbcU;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][0U])) {
                            ++(vlSymsp->__Vcoverage[322]);
                            vlSelfRef.b = 0xf5U;
                        } else {
                            ++(vlSymsp->__Vcoverage[321]);
                            vlSelfRef.b = 0x38U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[320]);
                        vlSelfRef.b = 0x9dU;
                    } else {
                        ++(vlSymsp->__Vcoverage[319]);
                        vlSelfRef.b = 0x92U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[318]);
                        vlSelfRef.b = 0x8fU;
                    } else {
                        ++(vlSymsp->__Vcoverage[317]);
                        vlSelfRef.b = 0x40U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[316]);
                    vlSelfRef.b = 0xa3U;
                } else {
                    ++(vlSymsp->__Vcoverage[315]);
                    vlSelfRef.b = 0x51U;
                }
            } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][0U])) {
                            ++(vlSymsp->__Vcoverage[314]);
                            vlSelfRef.b = 0xa8U;
                        } else {
                            ++(vlSymsp->__Vcoverage[313]);
                            vlSelfRef.b = 0x9fU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[312]);
                        vlSelfRef.b = 0x3cU;
                    } else {
                        ++(vlSymsp->__Vcoverage[311]);
                        vlSelfRef.b = 0x50U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[310]);
                        vlSelfRef.b = 0x7fU;
                    } else {
                        ++(vlSymsp->__Vcoverage[309]);
                        vlSelfRef.b = 2U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[308]);
                    vlSelfRef.b = 0xf9U;
                } else {
                    ++(vlSymsp->__Vcoverage[307]);
                    vlSelfRef.b = 0x45U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[306]);
                        vlSelfRef.b = 0x85U;
                    } else {
                        ++(vlSymsp->__Vcoverage[305]);
                        vlSelfRef.b = 0x33U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[304]);
                    vlSelfRef.b = 0x4dU;
                } else {
                    ++(vlSymsp->__Vcoverage[303]);
                    vlSelfRef.b = 0x43U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[302]);
                    vlSelfRef.b = 0xfbU;
                } else {
                    ++(vlSymsp->__Vcoverage[301]);
                    vlSelfRef.b = 0xaaU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                ++(vlSymsp->__Vcoverage[300]);
                vlSelfRef.b = 0xefU;
            } else {
                ++(vlSymsp->__Vcoverage[299]);
                vlSelfRef.b = 0xd0U;
            }
        } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][0U])) {
            if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][0U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][0U])) {
                            ++(vlSymsp->__Vcoverage[298]);
                            vlSelfRef.b = 0xcfU;
                        } else {
                            ++(vlSymsp->__Vcoverage[297]);
                            vlSelfRef.b = 0x58U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[296]);
                        vlSelfRef.b = 0x4cU;
                    } else {
                        ++(vlSymsp->__Vcoverage[295]);
                        vlSelfRef.b = 0x4aU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[294]);
                        vlSelfRef.b = 0x39U;
                    } else {
                        ++(vlSymsp->__Vcoverage[293]);
                        vlSelfRef.b = 0xbeU;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[292]);
                    vlSelfRef.b = 0xcbU;
                } else {
                    ++(vlSymsp->__Vcoverage[291]);
                    vlSelfRef.b = 0x6aU;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[290]);
                        vlSelfRef.b = 0x5bU;
                    } else {
                        ++(vlSymsp->__Vcoverage[289]);
                        vlSelfRef.b = 0xb1U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[288]);
                    vlSelfRef.b = 0xfcU;
                } else {
                    ++(vlSymsp->__Vcoverage[287]);
                    vlSelfRef.b = 0x20U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[286]);
                    vlSelfRef.b = 0xedU;
                } else {
                    ++(vlSymsp->__Vcoverage[285]);
                    vlSelfRef.b = 0U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                ++(vlSymsp->__Vcoverage[284]);
                vlSelfRef.b = 0xd1U;
            } else {
                ++(vlSymsp->__Vcoverage[283]);
                vlSelfRef.b = 0x53U;
            }
        } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][0U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][0U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[282]);
                        vlSelfRef.b = 0x84U;
                    } else {
                        ++(vlSymsp->__Vcoverage[281]);
                        vlSelfRef.b = 0x2fU;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[280]);
                    vlSelfRef.b = 0xe3U;
                } else {
                    ++(vlSymsp->__Vcoverage[279]);
                    vlSelfRef.b = 0x29U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[278]);
                    vlSelfRef.b = 0xb3U;
                } else {
                    ++(vlSymsp->__Vcoverage[277]);
                    vlSelfRef.b = 0xd6U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                ++(vlSymsp->__Vcoverage[276]);
                vlSelfRef.b = 0x3bU;
            } else {
                ++(vlSymsp->__Vcoverage[275]);
                vlSelfRef.b = 0x52U;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][0U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][0U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[274]);
                    vlSelfRef.b = 0xa0U;
                } else {
                    ++(vlSymsp->__Vcoverage[273]);
                    vlSelfRef.b = 0x5aU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                ++(vlSymsp->__Vcoverage[272]);
                vlSelfRef.b = 0x6eU;
            } else {
                ++(vlSymsp->__Vcoverage[271]);
                vlSelfRef.b = 0x1bU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][0U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][0U])) {
                ++(vlSymsp->__Vcoverage[270]);
                vlSelfRef.b = 0x1aU;
            } else {
                ++(vlSymsp->__Vcoverage[269]);
                vlSelfRef.b = 0x2cU;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][0U])) {
            ++(vlSymsp->__Vcoverage[268]);
            vlSelfRef.b = 0x83U;
        } else {
            ++(vlSymsp->__Vcoverage[267]);
            vlSelfRef.b = 9U;
        }
    } else if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][0U])) {
        if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][0U])) {
            if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][0U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][0U])) {
                            ++(vlSymsp->__Vcoverage[266]);
                            vlSelfRef.b = 0x75U;
                        } else {
                            ++(vlSymsp->__Vcoverage[265]);
                            vlSelfRef.b = 0xb2U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[264]);
                        vlSelfRef.b = 0x27U;
                    } else {
                        ++(vlSymsp->__Vcoverage[263]);
                        vlSelfRef.b = 0xebU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[262]);
                        vlSelfRef.b = 0xe2U;
                    } else {
                        ++(vlSymsp->__Vcoverage[261]);
                        vlSelfRef.b = 0x80U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[260]);
                    vlSelfRef.b = 0x12U;
                } else {
                    ++(vlSymsp->__Vcoverage[259]);
                    vlSelfRef.b = 7U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[258]);
                        vlSelfRef.b = 0x9aU;
                    } else {
                        ++(vlSymsp->__Vcoverage[257]);
                        vlSelfRef.b = 5U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[256]);
                    vlSelfRef.b = 0x96U;
                } else {
                    ++(vlSymsp->__Vcoverage[255]);
                    vlSelfRef.b = 0x18U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[254]);
                    vlSelfRef.b = 0xc3U;
                } else {
                    ++(vlSymsp->__Vcoverage[253]);
                    vlSelfRef.b = 0x23U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                ++(vlSymsp->__Vcoverage[252]);
                vlSelfRef.b = 0xc7U;
            } else {
                ++(vlSymsp->__Vcoverage[251]);
                vlSelfRef.b = 4U;
            }
        } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][0U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][0U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[250]);
                        vlSelfRef.b = 0x15U;
                    } else {
                        ++(vlSymsp->__Vcoverage[249]);
                        vlSelfRef.b = 0x31U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[248]);
                    vlSelfRef.b = 0xd8U;
                } else {
                    ++(vlSymsp->__Vcoverage[247]);
                    vlSelfRef.b = 0x71U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[246]);
                    vlSelfRef.b = 0xf1U;
                } else {
                    ++(vlSymsp->__Vcoverage[245]);
                    vlSelfRef.b = 0xe5U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                ++(vlSymsp->__Vcoverage[244]);
                vlSelfRef.b = 0xa5U;
            } else {
                ++(vlSymsp->__Vcoverage[243]);
                vlSelfRef.b = 0x34U;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][0U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][0U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[242]);
                    vlSelfRef.b = 0xccU;
                } else {
                    ++(vlSymsp->__Vcoverage[241]);
                    vlSelfRef.b = 0xf7U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                ++(vlSymsp->__Vcoverage[240]);
                vlSelfRef.b = 0x3fU;
            } else {
                ++(vlSymsp->__Vcoverage[239]);
                vlSelfRef.b = 0x36U;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][0U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][0U])) {
                ++(vlSymsp->__Vcoverage[238]);
                vlSelfRef.b = 0x26U;
            } else {
                ++(vlSymsp->__Vcoverage[237]);
                vlSelfRef.b = 0x93U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][0U])) {
            ++(vlSymsp->__Vcoverage[236]);
            vlSelfRef.b = 0xfdU;
        } else {
            ++(vlSymsp->__Vcoverage[235]);
            vlSelfRef.b = 0xb7U;
        }
    } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][0U])) {
        if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][0U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][0U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][0U])) {
                        ++(vlSymsp->__Vcoverage[234]);
                        vlSelfRef.b = 0xc0U;
                    } else {
                        ++(vlSymsp->__Vcoverage[233]);
                        vlSelfRef.b = 0x72U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[232]);
                    vlSelfRef.b = 0xa4U;
                } else {
                    ++(vlSymsp->__Vcoverage[231]);
                    vlSelfRef.b = 0x9cU;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[230]);
                    vlSelfRef.b = 0xafU;
                } else {
                    ++(vlSymsp->__Vcoverage[229]);
                    vlSelfRef.b = 0xa2U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                ++(vlSymsp->__Vcoverage[228]);
                vlSelfRef.b = 0xd4U;
            } else {
                ++(vlSymsp->__Vcoverage[227]);
                vlSelfRef.b = 0xadU;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][0U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][0U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[226]);
                    vlSelfRef.b = 0xf0U;
                } else {
                    ++(vlSymsp->__Vcoverage[225]);
                    vlSelfRef.b = 0x47U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                ++(vlSymsp->__Vcoverage[224]);
                vlSelfRef.b = 0x59U;
            } else {
                ++(vlSymsp->__Vcoverage[223]);
                vlSelfRef.b = 0xfaU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][0U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][0U])) {
                ++(vlSymsp->__Vcoverage[222]);
                vlSelfRef.b = 0x7dU;
            } else {
                ++(vlSymsp->__Vcoverage[221]);
                vlSelfRef.b = 0xc9U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][0U])) {
            ++(vlSymsp->__Vcoverage[220]);
            vlSelfRef.b = 0x82U;
        } else {
            ++(vlSymsp->__Vcoverage[219]);
            vlSelfRef.b = 0xcaU;
        }
    } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][0U])) {
        if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][0U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][0U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][0U])) {
                    ++(vlSymsp->__Vcoverage[218]);
                    vlSelfRef.b = 0x76U;
                } else {
                    ++(vlSymsp->__Vcoverage[217]);
                    vlSelfRef.b = 0xabU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][0U])) {
                ++(vlSymsp->__Vcoverage[216]);
                vlSelfRef.b = 0xd7U;
            } else {
                ++(vlSymsp->__Vcoverage[215]);
                vlSelfRef.b = 0xfeU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][0U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][0U])) {
                ++(vlSymsp->__Vcoverage[214]);
                vlSelfRef.b = 0x2bU;
            } else {
                ++(vlSymsp->__Vcoverage[213]);
                vlSelfRef.b = 0x67U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][0U])) {
            ++(vlSymsp->__Vcoverage[212]);
            vlSelfRef.b = 1U;
        } else {
            ++(vlSymsp->__Vcoverage[211]);
            vlSelfRef.b = 0x30U;
        }
    } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][0U])) {
        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][0U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][0U])) {
                ++(vlSymsp->__Vcoverage[210]);
                vlSelfRef.b = 0xc5U;
            } else {
                ++(vlSymsp->__Vcoverage[209]);
                vlSelfRef.b = 0x6fU;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][0U])) {
            ++(vlSymsp->__Vcoverage[208]);
            vlSelfRef.b = 0x6bU;
        } else {
            ++(vlSymsp->__Vcoverage[207]);
            vlSelfRef.b = 0xf2U;
        }
    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][0U])) {
        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][0U])) {
            ++(vlSymsp->__Vcoverage[206]);
            vlSelfRef.b = 0x7bU;
        } else {
            ++(vlSymsp->__Vcoverage[205]);
            vlSelfRef.b = 0x77U;
        }
    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][0U])) {
        ++(vlSymsp->__Vcoverage[204]);
        vlSelfRef.b = 0x7cU;
    } else {
        ++(vlSymsp->__Vcoverage[203]);
        vlSelfRef.b = 0x63U;
    }
    ++(vlSymsp->__Vcoverage[459]);
}

void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__2__KET____DOT__sbox_row__BRA__0__KET____DOT__u_sbox__1(Vtb_aes_sbox* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+            Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__2__KET____DOT__sbox_row__BRA__0__KET____DOT__u_sbox__1\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.a = vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
        [2U][0U];
}

void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__2__KET____DOT__sbox_row__BRA__1__KET____DOT__u_sbox__0(Vtb_aes_sbox* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+            Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__2__KET____DOT__sbox_row__BRA__1__KET____DOT__u_sbox__0\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((0x00000080U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
         [2U][1U])) {
        if ((0x00000040U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][1U])) {
            if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][1U])) {
                if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][1U])) {
                            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][1U])) {
                                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                     [2U][1U])) {
                                    vlSelfRef.b = 0x16U;
                                    ++(vlSymsp->__Vcoverage[458]);
                                } else {
                                    ++(vlSymsp->__Vcoverage[457]);
                                    vlSelfRef.b = 0xbbU;
                                }
                            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                        [2U][1U])) {
                                ++(vlSymsp->__Vcoverage[456]);
                                vlSelfRef.b = 0x54U;
                            } else {
                                ++(vlSymsp->__Vcoverage[455]);
                                vlSelfRef.b = 0xb0U;
                            }
                        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][1U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][1U])) {
                                ++(vlSymsp->__Vcoverage[454]);
                                vlSelfRef.b = 0x0fU;
                            } else {
                                ++(vlSymsp->__Vcoverage[453]);
                                vlSelfRef.b = 0x2dU;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][1U])) {
                            ++(vlSymsp->__Vcoverage[452]);
                            vlSelfRef.b = 0x99U;
                        } else {
                            ++(vlSymsp->__Vcoverage[451]);
                            vlSelfRef.b = 0x41U;
                        }
                    } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][1U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][1U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][1U])) {
                                ++(vlSymsp->__Vcoverage[450]);
                                vlSelfRef.b = 0x68U;
                            } else {
                                ++(vlSymsp->__Vcoverage[449]);
                                vlSelfRef.b = 0x42U;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][1U])) {
                            ++(vlSymsp->__Vcoverage[448]);
                            vlSelfRef.b = 0xe6U;
                        } else {
                            ++(vlSymsp->__Vcoverage[447]);
                            vlSelfRef.b = 0xbfU;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][1U])) {
                            ++(vlSymsp->__Vcoverage[446]);
                            vlSelfRef.b = 0x0dU;
                        } else {
                            ++(vlSymsp->__Vcoverage[445]);
                            vlSelfRef.b = 0x89U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[444]);
                        vlSelfRef.b = 0xa1U;
                    } else {
                        ++(vlSymsp->__Vcoverage[443]);
                        vlSelfRef.b = 0x8cU;
                    }
                } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][1U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][1U])) {
                                ++(vlSymsp->__Vcoverage[442]);
                                vlSelfRef.b = 0xdfU;
                            } else {
                                ++(vlSymsp->__Vcoverage[441]);
                                vlSelfRef.b = 0x28U;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][1U])) {
                            ++(vlSymsp->__Vcoverage[440]);
                            vlSelfRef.b = 0x55U;
                        } else {
                            ++(vlSymsp->__Vcoverage[439]);
                            vlSelfRef.b = 0xceU;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][1U])) {
                            ++(vlSymsp->__Vcoverage[438]);
                            vlSelfRef.b = 0xe9U;
                        } else {
                            ++(vlSymsp->__Vcoverage[437]);
                            vlSelfRef.b = 0x87U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[436]);
                        vlSelfRef.b = 0x1eU;
                    } else {
                        ++(vlSymsp->__Vcoverage[435]);
                        vlSelfRef.b = 0x9bU;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][1U])) {
                            ++(vlSymsp->__Vcoverage[434]);
                            vlSelfRef.b = 0x94U;
                        } else {
                            ++(vlSymsp->__Vcoverage[433]);
                            vlSelfRef.b = 0x8eU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[432]);
                        vlSelfRef.b = 0xd9U;
                    } else {
                        ++(vlSymsp->__Vcoverage[431]);
                        vlSelfRef.b = 0x69U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[430]);
                        vlSelfRef.b = 0x11U;
                    } else {
                        ++(vlSymsp->__Vcoverage[429]);
                        vlSelfRef.b = 0x98U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[428]);
                    vlSelfRef.b = 0xf8U;
                } else {
                    ++(vlSymsp->__Vcoverage[427]);
                    vlSelfRef.b = 0xe1U;
                }
            } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][1U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][1U])) {
                                ++(vlSymsp->__Vcoverage[426]);
                                vlSelfRef.b = 0x9eU;
                            } else {
                                ++(vlSymsp->__Vcoverage[425]);
                                vlSelfRef.b = 0x1dU;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][1U])) {
                            ++(vlSymsp->__Vcoverage[424]);
                            vlSelfRef.b = 0xc1U;
                        } else {
                            ++(vlSymsp->__Vcoverage[423]);
                            vlSelfRef.b = 0x86U;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][1U])) {
                            ++(vlSymsp->__Vcoverage[422]);
                            vlSelfRef.b = 0xb9U;
                        } else {
                            ++(vlSymsp->__Vcoverage[421]);
                            vlSelfRef.b = 0x57U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[420]);
                        vlSelfRef.b = 0x35U;
                    } else {
                        ++(vlSymsp->__Vcoverage[419]);
                        vlSelfRef.b = 0x61U;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][1U])) {
                            ++(vlSymsp->__Vcoverage[418]);
                            vlSelfRef.b = 0x0eU;
                        } else {
                            ++(vlSymsp->__Vcoverage[417]);
                            vlSelfRef.b = 0xf6U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[416]);
                        vlSelfRef.b = 3U;
                    } else {
                        ++(vlSymsp->__Vcoverage[415]);
                        vlSelfRef.b = 0x48U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[414]);
                        vlSelfRef.b = 0x66U;
                    } else {
                        ++(vlSymsp->__Vcoverage[413]);
                        vlSelfRef.b = 0xb5U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[412]);
                    vlSelfRef.b = 0x3eU;
                } else {
                    ++(vlSymsp->__Vcoverage[411]);
                    vlSelfRef.b = 0x70U;
                }
            } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][1U])) {
                            ++(vlSymsp->__Vcoverage[410]);
                            vlSelfRef.b = 0x8aU;
                        } else {
                            ++(vlSymsp->__Vcoverage[409]);
                            vlSelfRef.b = 0x8bU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[408]);
                        vlSelfRef.b = 0xbdU;
                    } else {
                        ++(vlSymsp->__Vcoverage[407]);
                        vlSelfRef.b = 0x4bU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[406]);
                        vlSelfRef.b = 0x1fU;
                    } else {
                        ++(vlSymsp->__Vcoverage[405]);
                        vlSelfRef.b = 0x74U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[404]);
                    vlSelfRef.b = 0xddU;
                } else {
                    ++(vlSymsp->__Vcoverage[403]);
                    vlSelfRef.b = 0xe8U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[402]);
                        vlSelfRef.b = 0xc6U;
                    } else {
                        ++(vlSymsp->__Vcoverage[401]);
                        vlSelfRef.b = 0xb4U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[400]);
                    vlSelfRef.b = 0xa6U;
                } else {
                    ++(vlSymsp->__Vcoverage[399]);
                    vlSelfRef.b = 0x1cU;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[398]);
                    vlSelfRef.b = 0x2eU;
                } else {
                    ++(vlSymsp->__Vcoverage[397]);
                    vlSelfRef.b = 0x25U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                ++(vlSymsp->__Vcoverage[396]);
                vlSelfRef.b = 0x78U;
            } else {
                ++(vlSymsp->__Vcoverage[395]);
                vlSelfRef.b = 0xbaU;
            }
        } else if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][1U])) {
            if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][1U])) {
                if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][1U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][1U])) {
                                ++(vlSymsp->__Vcoverage[394]);
                                vlSelfRef.b = 8U;
                            } else {
                                ++(vlSymsp->__Vcoverage[393]);
                                vlSelfRef.b = 0xaeU;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][1U])) {
                            ++(vlSymsp->__Vcoverage[392]);
                            vlSelfRef.b = 0x7aU;
                        } else {
                            ++(vlSymsp->__Vcoverage[391]);
                            vlSelfRef.b = 0x65U;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][1U])) {
                            ++(vlSymsp->__Vcoverage[390]);
                            vlSelfRef.b = 0xeaU;
                        } else {
                            ++(vlSymsp->__Vcoverage[389]);
                            vlSelfRef.b = 0xf4U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[388]);
                        vlSelfRef.b = 0x56U;
                    } else {
                        ++(vlSymsp->__Vcoverage[387]);
                        vlSelfRef.b = 0x6cU;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][1U])) {
                            ++(vlSymsp->__Vcoverage[386]);
                            vlSelfRef.b = 0xa9U;
                        } else {
                            ++(vlSymsp->__Vcoverage[385]);
                            vlSelfRef.b = 0x4eU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[384]);
                        vlSelfRef.b = 0xd5U;
                    } else {
                        ++(vlSymsp->__Vcoverage[383]);
                        vlSelfRef.b = 0x8dU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[382]);
                        vlSelfRef.b = 0x6dU;
                    } else {
                        ++(vlSymsp->__Vcoverage[381]);
                        vlSelfRef.b = 0x37U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[380]);
                    vlSelfRef.b = 0xc8U;
                } else {
                    ++(vlSymsp->__Vcoverage[379]);
                    vlSelfRef.b = 0xe7U;
                }
            } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][1U])) {
                            ++(vlSymsp->__Vcoverage[378]);
                            vlSelfRef.b = 0x79U;
                        } else {
                            ++(vlSymsp->__Vcoverage[377]);
                            vlSelfRef.b = 0xe4U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[376]);
                        vlSelfRef.b = 0x95U;
                    } else {
                        ++(vlSymsp->__Vcoverage[375]);
                        vlSelfRef.b = 0x91U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[374]);
                        vlSelfRef.b = 0x62U;
                    } else {
                        ++(vlSymsp->__Vcoverage[373]);
                        vlSelfRef.b = 0xacU;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[372]);
                    vlSelfRef.b = 0xd3U;
                } else {
                    ++(vlSymsp->__Vcoverage[371]);
                    vlSelfRef.b = 0xc2U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[370]);
                        vlSelfRef.b = 0x5cU;
                    } else {
                        ++(vlSymsp->__Vcoverage[369]);
                        vlSelfRef.b = 0x24U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[368]);
                    vlSelfRef.b = 6U;
                } else {
                    ++(vlSymsp->__Vcoverage[367]);
                    vlSelfRef.b = 0x49U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[366]);
                    vlSelfRef.b = 0x0aU;
                } else {
                    ++(vlSymsp->__Vcoverage[365]);
                    vlSelfRef.b = 0x3aU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                ++(vlSymsp->__Vcoverage[364]);
                vlSelfRef.b = 0x32U;
            } else {
                ++(vlSymsp->__Vcoverage[363]);
                vlSelfRef.b = 0xe0U;
            }
        } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][1U])) {
            if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][1U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][1U])) {
                            ++(vlSymsp->__Vcoverage[362]);
                            vlSelfRef.b = 0xdbU;
                        } else {
                            ++(vlSymsp->__Vcoverage[361]);
                            vlSelfRef.b = 0x0bU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[360]);
                        vlSelfRef.b = 0x5eU;
                    } else {
                        ++(vlSymsp->__Vcoverage[359]);
                        vlSelfRef.b = 0xdeU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[358]);
                        vlSelfRef.b = 0x14U;
                    } else {
                        ++(vlSymsp->__Vcoverage[357]);
                        vlSelfRef.b = 0xb8U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[356]);
                    vlSelfRef.b = 0xeeU;
                } else {
                    ++(vlSymsp->__Vcoverage[355]);
                    vlSelfRef.b = 0x46U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[354]);
                        vlSelfRef.b = 0x88U;
                    } else {
                        ++(vlSymsp->__Vcoverage[353]);
                        vlSelfRef.b = 0x90U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[352]);
                    vlSelfRef.b = 0x2aU;
                } else {
                    ++(vlSymsp->__Vcoverage[351]);
                    vlSelfRef.b = 0x22U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[350]);
                    vlSelfRef.b = 0xdcU;
                } else {
                    ++(vlSymsp->__Vcoverage[349]);
                    vlSelfRef.b = 0x4fU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                ++(vlSymsp->__Vcoverage[348]);
                vlSelfRef.b = 0x81U;
            } else {
                ++(vlSymsp->__Vcoverage[347]);
                vlSelfRef.b = 0x60U;
            }
        } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][1U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][1U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[346]);
                        vlSelfRef.b = 0x73U;
                    } else {
                        ++(vlSymsp->__Vcoverage[345]);
                        vlSelfRef.b = 0x19U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[344]);
                    vlSelfRef.b = 0x5dU;
                } else {
                    ++(vlSymsp->__Vcoverage[343]);
                    vlSelfRef.b = 0x64U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[342]);
                    vlSelfRef.b = 0x3dU;
                } else {
                    ++(vlSymsp->__Vcoverage[341]);
                    vlSelfRef.b = 0x7eU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                ++(vlSymsp->__Vcoverage[340]);
                vlSelfRef.b = 0xa7U;
            } else {
                ++(vlSymsp->__Vcoverage[339]);
                vlSelfRef.b = 0xc4U;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][1U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[338]);
                    vlSelfRef.b = 0x17U;
                } else {
                    ++(vlSymsp->__Vcoverage[337]);
                    vlSelfRef.b = 0x44U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                ++(vlSymsp->__Vcoverage[336]);
                vlSelfRef.b = 0x97U;
            } else {
                ++(vlSymsp->__Vcoverage[335]);
                vlSelfRef.b = 0x5fU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][1U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][1U])) {
                ++(vlSymsp->__Vcoverage[334]);
                vlSelfRef.b = 0xecU;
            } else {
                ++(vlSymsp->__Vcoverage[333]);
                vlSelfRef.b = 0x13U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][1U])) {
            ++(vlSymsp->__Vcoverage[332]);
            vlSelfRef.b = 0x0cU;
        } else {
            ++(vlSymsp->__Vcoverage[331]);
            vlSelfRef.b = 0xcdU;
        }
    } else if ((0x00000040U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][1U])) {
        if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][1U])) {
            if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][1U])) {
                if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][1U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][1U])) {
                                ++(vlSymsp->__Vcoverage[330]);
                                vlSelfRef.b = 0xd2U;
                            } else {
                                ++(vlSymsp->__Vcoverage[329]);
                                vlSelfRef.b = 0xf3U;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][1U])) {
                            ++(vlSymsp->__Vcoverage[328]);
                            vlSelfRef.b = 0xffU;
                        } else {
                            ++(vlSymsp->__Vcoverage[327]);
                            vlSelfRef.b = 0x10U;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][1U])) {
                            ++(vlSymsp->__Vcoverage[326]);
                            vlSelfRef.b = 0x21U;
                        } else {
                            ++(vlSymsp->__Vcoverage[325]);
                            vlSelfRef.b = 0xdaU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[324]);
                        vlSelfRef.b = 0xb6U;
                    } else {
                        ++(vlSymsp->__Vcoverage[323]);
                        vlSelfRef.b = 0xbcU;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][1U])) {
                            ++(vlSymsp->__Vcoverage[322]);
                            vlSelfRef.b = 0xf5U;
                        } else {
                            ++(vlSymsp->__Vcoverage[321]);
                            vlSelfRef.b = 0x38U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[320]);
                        vlSelfRef.b = 0x9dU;
                    } else {
                        ++(vlSymsp->__Vcoverage[319]);
                        vlSelfRef.b = 0x92U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[318]);
                        vlSelfRef.b = 0x8fU;
                    } else {
                        ++(vlSymsp->__Vcoverage[317]);
                        vlSelfRef.b = 0x40U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[316]);
                    vlSelfRef.b = 0xa3U;
                } else {
                    ++(vlSymsp->__Vcoverage[315]);
                    vlSelfRef.b = 0x51U;
                }
            } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][1U])) {
                            ++(vlSymsp->__Vcoverage[314]);
                            vlSelfRef.b = 0xa8U;
                        } else {
                            ++(vlSymsp->__Vcoverage[313]);
                            vlSelfRef.b = 0x9fU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[312]);
                        vlSelfRef.b = 0x3cU;
                    } else {
                        ++(vlSymsp->__Vcoverage[311]);
                        vlSelfRef.b = 0x50U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[310]);
                        vlSelfRef.b = 0x7fU;
                    } else {
                        ++(vlSymsp->__Vcoverage[309]);
                        vlSelfRef.b = 2U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[308]);
                    vlSelfRef.b = 0xf9U;
                } else {
                    ++(vlSymsp->__Vcoverage[307]);
                    vlSelfRef.b = 0x45U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[306]);
                        vlSelfRef.b = 0x85U;
                    } else {
                        ++(vlSymsp->__Vcoverage[305]);
                        vlSelfRef.b = 0x33U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[304]);
                    vlSelfRef.b = 0x4dU;
                } else {
                    ++(vlSymsp->__Vcoverage[303]);
                    vlSelfRef.b = 0x43U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[302]);
                    vlSelfRef.b = 0xfbU;
                } else {
                    ++(vlSymsp->__Vcoverage[301]);
                    vlSelfRef.b = 0xaaU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                ++(vlSymsp->__Vcoverage[300]);
                vlSelfRef.b = 0xefU;
            } else {
                ++(vlSymsp->__Vcoverage[299]);
                vlSelfRef.b = 0xd0U;
            }
        } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][1U])) {
            if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][1U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][1U])) {
                            ++(vlSymsp->__Vcoverage[298]);
                            vlSelfRef.b = 0xcfU;
                        } else {
                            ++(vlSymsp->__Vcoverage[297]);
                            vlSelfRef.b = 0x58U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[296]);
                        vlSelfRef.b = 0x4cU;
                    } else {
                        ++(vlSymsp->__Vcoverage[295]);
                        vlSelfRef.b = 0x4aU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[294]);
                        vlSelfRef.b = 0x39U;
                    } else {
                        ++(vlSymsp->__Vcoverage[293]);
                        vlSelfRef.b = 0xbeU;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[292]);
                    vlSelfRef.b = 0xcbU;
                } else {
                    ++(vlSymsp->__Vcoverage[291]);
                    vlSelfRef.b = 0x6aU;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[290]);
                        vlSelfRef.b = 0x5bU;
                    } else {
                        ++(vlSymsp->__Vcoverage[289]);
                        vlSelfRef.b = 0xb1U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[288]);
                    vlSelfRef.b = 0xfcU;
                } else {
                    ++(vlSymsp->__Vcoverage[287]);
                    vlSelfRef.b = 0x20U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[286]);
                    vlSelfRef.b = 0xedU;
                } else {
                    ++(vlSymsp->__Vcoverage[285]);
                    vlSelfRef.b = 0U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                ++(vlSymsp->__Vcoverage[284]);
                vlSelfRef.b = 0xd1U;
            } else {
                ++(vlSymsp->__Vcoverage[283]);
                vlSelfRef.b = 0x53U;
            }
        } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][1U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][1U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[282]);
                        vlSelfRef.b = 0x84U;
                    } else {
                        ++(vlSymsp->__Vcoverage[281]);
                        vlSelfRef.b = 0x2fU;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[280]);
                    vlSelfRef.b = 0xe3U;
                } else {
                    ++(vlSymsp->__Vcoverage[279]);
                    vlSelfRef.b = 0x29U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[278]);
                    vlSelfRef.b = 0xb3U;
                } else {
                    ++(vlSymsp->__Vcoverage[277]);
                    vlSelfRef.b = 0xd6U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                ++(vlSymsp->__Vcoverage[276]);
                vlSelfRef.b = 0x3bU;
            } else {
                ++(vlSymsp->__Vcoverage[275]);
                vlSelfRef.b = 0x52U;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][1U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[274]);
                    vlSelfRef.b = 0xa0U;
                } else {
                    ++(vlSymsp->__Vcoverage[273]);
                    vlSelfRef.b = 0x5aU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                ++(vlSymsp->__Vcoverage[272]);
                vlSelfRef.b = 0x6eU;
            } else {
                ++(vlSymsp->__Vcoverage[271]);
                vlSelfRef.b = 0x1bU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][1U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][1U])) {
                ++(vlSymsp->__Vcoverage[270]);
                vlSelfRef.b = 0x1aU;
            } else {
                ++(vlSymsp->__Vcoverage[269]);
                vlSelfRef.b = 0x2cU;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][1U])) {
            ++(vlSymsp->__Vcoverage[268]);
            vlSelfRef.b = 0x83U;
        } else {
            ++(vlSymsp->__Vcoverage[267]);
            vlSelfRef.b = 9U;
        }
    } else if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][1U])) {
        if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][1U])) {
            if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][1U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][1U])) {
                            ++(vlSymsp->__Vcoverage[266]);
                            vlSelfRef.b = 0x75U;
                        } else {
                            ++(vlSymsp->__Vcoverage[265]);
                            vlSelfRef.b = 0xb2U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[264]);
                        vlSelfRef.b = 0x27U;
                    } else {
                        ++(vlSymsp->__Vcoverage[263]);
                        vlSelfRef.b = 0xebU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[262]);
                        vlSelfRef.b = 0xe2U;
                    } else {
                        ++(vlSymsp->__Vcoverage[261]);
                        vlSelfRef.b = 0x80U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[260]);
                    vlSelfRef.b = 0x12U;
                } else {
                    ++(vlSymsp->__Vcoverage[259]);
                    vlSelfRef.b = 7U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[258]);
                        vlSelfRef.b = 0x9aU;
                    } else {
                        ++(vlSymsp->__Vcoverage[257]);
                        vlSelfRef.b = 5U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[256]);
                    vlSelfRef.b = 0x96U;
                } else {
                    ++(vlSymsp->__Vcoverage[255]);
                    vlSelfRef.b = 0x18U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[254]);
                    vlSelfRef.b = 0xc3U;
                } else {
                    ++(vlSymsp->__Vcoverage[253]);
                    vlSelfRef.b = 0x23U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                ++(vlSymsp->__Vcoverage[252]);
                vlSelfRef.b = 0xc7U;
            } else {
                ++(vlSymsp->__Vcoverage[251]);
                vlSelfRef.b = 4U;
            }
        } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][1U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][1U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[250]);
                        vlSelfRef.b = 0x15U;
                    } else {
                        ++(vlSymsp->__Vcoverage[249]);
                        vlSelfRef.b = 0x31U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[248]);
                    vlSelfRef.b = 0xd8U;
                } else {
                    ++(vlSymsp->__Vcoverage[247]);
                    vlSelfRef.b = 0x71U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[246]);
                    vlSelfRef.b = 0xf1U;
                } else {
                    ++(vlSymsp->__Vcoverage[245]);
                    vlSelfRef.b = 0xe5U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                ++(vlSymsp->__Vcoverage[244]);
                vlSelfRef.b = 0xa5U;
            } else {
                ++(vlSymsp->__Vcoverage[243]);
                vlSelfRef.b = 0x34U;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][1U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[242]);
                    vlSelfRef.b = 0xccU;
                } else {
                    ++(vlSymsp->__Vcoverage[241]);
                    vlSelfRef.b = 0xf7U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                ++(vlSymsp->__Vcoverage[240]);
                vlSelfRef.b = 0x3fU;
            } else {
                ++(vlSymsp->__Vcoverage[239]);
                vlSelfRef.b = 0x36U;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][1U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][1U])) {
                ++(vlSymsp->__Vcoverage[238]);
                vlSelfRef.b = 0x26U;
            } else {
                ++(vlSymsp->__Vcoverage[237]);
                vlSelfRef.b = 0x93U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][1U])) {
            ++(vlSymsp->__Vcoverage[236]);
            vlSelfRef.b = 0xfdU;
        } else {
            ++(vlSymsp->__Vcoverage[235]);
            vlSelfRef.b = 0xb7U;
        }
    } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][1U])) {
        if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][1U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][1U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][1U])) {
                        ++(vlSymsp->__Vcoverage[234]);
                        vlSelfRef.b = 0xc0U;
                    } else {
                        ++(vlSymsp->__Vcoverage[233]);
                        vlSelfRef.b = 0x72U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[232]);
                    vlSelfRef.b = 0xa4U;
                } else {
                    ++(vlSymsp->__Vcoverage[231]);
                    vlSelfRef.b = 0x9cU;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[230]);
                    vlSelfRef.b = 0xafU;
                } else {
                    ++(vlSymsp->__Vcoverage[229]);
                    vlSelfRef.b = 0xa2U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                ++(vlSymsp->__Vcoverage[228]);
                vlSelfRef.b = 0xd4U;
            } else {
                ++(vlSymsp->__Vcoverage[227]);
                vlSelfRef.b = 0xadU;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][1U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[226]);
                    vlSelfRef.b = 0xf0U;
                } else {
                    ++(vlSymsp->__Vcoverage[225]);
                    vlSelfRef.b = 0x47U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                ++(vlSymsp->__Vcoverage[224]);
                vlSelfRef.b = 0x59U;
            } else {
                ++(vlSymsp->__Vcoverage[223]);
                vlSelfRef.b = 0xfaU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][1U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][1U])) {
                ++(vlSymsp->__Vcoverage[222]);
                vlSelfRef.b = 0x7dU;
            } else {
                ++(vlSymsp->__Vcoverage[221]);
                vlSelfRef.b = 0xc9U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][1U])) {
            ++(vlSymsp->__Vcoverage[220]);
            vlSelfRef.b = 0x82U;
        } else {
            ++(vlSymsp->__Vcoverage[219]);
            vlSelfRef.b = 0xcaU;
        }
    } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][1U])) {
        if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][1U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][1U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][1U])) {
                    ++(vlSymsp->__Vcoverage[218]);
                    vlSelfRef.b = 0x76U;
                } else {
                    ++(vlSymsp->__Vcoverage[217]);
                    vlSelfRef.b = 0xabU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][1U])) {
                ++(vlSymsp->__Vcoverage[216]);
                vlSelfRef.b = 0xd7U;
            } else {
                ++(vlSymsp->__Vcoverage[215]);
                vlSelfRef.b = 0xfeU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][1U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][1U])) {
                ++(vlSymsp->__Vcoverage[214]);
                vlSelfRef.b = 0x2bU;
            } else {
                ++(vlSymsp->__Vcoverage[213]);
                vlSelfRef.b = 0x67U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][1U])) {
            ++(vlSymsp->__Vcoverage[212]);
            vlSelfRef.b = 1U;
        } else {
            ++(vlSymsp->__Vcoverage[211]);
            vlSelfRef.b = 0x30U;
        }
    } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][1U])) {
        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][1U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][1U])) {
                ++(vlSymsp->__Vcoverage[210]);
                vlSelfRef.b = 0xc5U;
            } else {
                ++(vlSymsp->__Vcoverage[209]);
                vlSelfRef.b = 0x6fU;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][1U])) {
            ++(vlSymsp->__Vcoverage[208]);
            vlSelfRef.b = 0x6bU;
        } else {
            ++(vlSymsp->__Vcoverage[207]);
            vlSelfRef.b = 0xf2U;
        }
    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][1U])) {
        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][1U])) {
            ++(vlSymsp->__Vcoverage[206]);
            vlSelfRef.b = 0x7bU;
        } else {
            ++(vlSymsp->__Vcoverage[205]);
            vlSelfRef.b = 0x77U;
        }
    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][1U])) {
        ++(vlSymsp->__Vcoverage[204]);
        vlSelfRef.b = 0x7cU;
    } else {
        ++(vlSymsp->__Vcoverage[203]);
        vlSelfRef.b = 0x63U;
    }
    ++(vlSymsp->__Vcoverage[459]);
}

void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__2__KET____DOT__sbox_row__BRA__1__KET____DOT__u_sbox__1(Vtb_aes_sbox* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+            Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__2__KET____DOT__sbox_row__BRA__1__KET____DOT__u_sbox__1\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.a = vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
        [2U][1U];
}

void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__2__KET____DOT__sbox_row__BRA__2__KET____DOT__u_sbox__0(Vtb_aes_sbox* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+            Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__2__KET____DOT__sbox_row__BRA__2__KET____DOT__u_sbox__0\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((0x00000080U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
         [2U][2U])) {
        if ((0x00000040U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][2U])) {
            if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][2U])) {
                if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][2U])) {
                            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][2U])) {
                                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                     [2U][2U])) {
                                    vlSelfRef.b = 0x16U;
                                    ++(vlSymsp->__Vcoverage[458]);
                                } else {
                                    ++(vlSymsp->__Vcoverage[457]);
                                    vlSelfRef.b = 0xbbU;
                                }
                            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                        [2U][2U])) {
                                ++(vlSymsp->__Vcoverage[456]);
                                vlSelfRef.b = 0x54U;
                            } else {
                                ++(vlSymsp->__Vcoverage[455]);
                                vlSelfRef.b = 0xb0U;
                            }
                        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][2U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][2U])) {
                                ++(vlSymsp->__Vcoverage[454]);
                                vlSelfRef.b = 0x0fU;
                            } else {
                                ++(vlSymsp->__Vcoverage[453]);
                                vlSelfRef.b = 0x2dU;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][2U])) {
                            ++(vlSymsp->__Vcoverage[452]);
                            vlSelfRef.b = 0x99U;
                        } else {
                            ++(vlSymsp->__Vcoverage[451]);
                            vlSelfRef.b = 0x41U;
                        }
                    } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][2U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][2U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][2U])) {
                                ++(vlSymsp->__Vcoverage[450]);
                                vlSelfRef.b = 0x68U;
                            } else {
                                ++(vlSymsp->__Vcoverage[449]);
                                vlSelfRef.b = 0x42U;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][2U])) {
                            ++(vlSymsp->__Vcoverage[448]);
                            vlSelfRef.b = 0xe6U;
                        } else {
                            ++(vlSymsp->__Vcoverage[447]);
                            vlSelfRef.b = 0xbfU;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][2U])) {
                            ++(vlSymsp->__Vcoverage[446]);
                            vlSelfRef.b = 0x0dU;
                        } else {
                            ++(vlSymsp->__Vcoverage[445]);
                            vlSelfRef.b = 0x89U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[444]);
                        vlSelfRef.b = 0xa1U;
                    } else {
                        ++(vlSymsp->__Vcoverage[443]);
                        vlSelfRef.b = 0x8cU;
                    }
                } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][2U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][2U])) {
                                ++(vlSymsp->__Vcoverage[442]);
                                vlSelfRef.b = 0xdfU;
                            } else {
                                ++(vlSymsp->__Vcoverage[441]);
                                vlSelfRef.b = 0x28U;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][2U])) {
                            ++(vlSymsp->__Vcoverage[440]);
                            vlSelfRef.b = 0x55U;
                        } else {
                            ++(vlSymsp->__Vcoverage[439]);
                            vlSelfRef.b = 0xceU;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][2U])) {
                            ++(vlSymsp->__Vcoverage[438]);
                            vlSelfRef.b = 0xe9U;
                        } else {
                            ++(vlSymsp->__Vcoverage[437]);
                            vlSelfRef.b = 0x87U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[436]);
                        vlSelfRef.b = 0x1eU;
                    } else {
                        ++(vlSymsp->__Vcoverage[435]);
                        vlSelfRef.b = 0x9bU;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][2U])) {
                            ++(vlSymsp->__Vcoverage[434]);
                            vlSelfRef.b = 0x94U;
                        } else {
                            ++(vlSymsp->__Vcoverage[433]);
                            vlSelfRef.b = 0x8eU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[432]);
                        vlSelfRef.b = 0xd9U;
                    } else {
                        ++(vlSymsp->__Vcoverage[431]);
                        vlSelfRef.b = 0x69U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[430]);
                        vlSelfRef.b = 0x11U;
                    } else {
                        ++(vlSymsp->__Vcoverage[429]);
                        vlSelfRef.b = 0x98U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[428]);
                    vlSelfRef.b = 0xf8U;
                } else {
                    ++(vlSymsp->__Vcoverage[427]);
                    vlSelfRef.b = 0xe1U;
                }
            } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][2U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][2U])) {
                                ++(vlSymsp->__Vcoverage[426]);
                                vlSelfRef.b = 0x9eU;
                            } else {
                                ++(vlSymsp->__Vcoverage[425]);
                                vlSelfRef.b = 0x1dU;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][2U])) {
                            ++(vlSymsp->__Vcoverage[424]);
                            vlSelfRef.b = 0xc1U;
                        } else {
                            ++(vlSymsp->__Vcoverage[423]);
                            vlSelfRef.b = 0x86U;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][2U])) {
                            ++(vlSymsp->__Vcoverage[422]);
                            vlSelfRef.b = 0xb9U;
                        } else {
                            ++(vlSymsp->__Vcoverage[421]);
                            vlSelfRef.b = 0x57U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[420]);
                        vlSelfRef.b = 0x35U;
                    } else {
                        ++(vlSymsp->__Vcoverage[419]);
                        vlSelfRef.b = 0x61U;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][2U])) {
                            ++(vlSymsp->__Vcoverage[418]);
                            vlSelfRef.b = 0x0eU;
                        } else {
                            ++(vlSymsp->__Vcoverage[417]);
                            vlSelfRef.b = 0xf6U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[416]);
                        vlSelfRef.b = 3U;
                    } else {
                        ++(vlSymsp->__Vcoverage[415]);
                        vlSelfRef.b = 0x48U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[414]);
                        vlSelfRef.b = 0x66U;
                    } else {
                        ++(vlSymsp->__Vcoverage[413]);
                        vlSelfRef.b = 0xb5U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[412]);
                    vlSelfRef.b = 0x3eU;
                } else {
                    ++(vlSymsp->__Vcoverage[411]);
                    vlSelfRef.b = 0x70U;
                }
            } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][2U])) {
                            ++(vlSymsp->__Vcoverage[410]);
                            vlSelfRef.b = 0x8aU;
                        } else {
                            ++(vlSymsp->__Vcoverage[409]);
                            vlSelfRef.b = 0x8bU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[408]);
                        vlSelfRef.b = 0xbdU;
                    } else {
                        ++(vlSymsp->__Vcoverage[407]);
                        vlSelfRef.b = 0x4bU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[406]);
                        vlSelfRef.b = 0x1fU;
                    } else {
                        ++(vlSymsp->__Vcoverage[405]);
                        vlSelfRef.b = 0x74U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[404]);
                    vlSelfRef.b = 0xddU;
                } else {
                    ++(vlSymsp->__Vcoverage[403]);
                    vlSelfRef.b = 0xe8U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[402]);
                        vlSelfRef.b = 0xc6U;
                    } else {
                        ++(vlSymsp->__Vcoverage[401]);
                        vlSelfRef.b = 0xb4U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[400]);
                    vlSelfRef.b = 0xa6U;
                } else {
                    ++(vlSymsp->__Vcoverage[399]);
                    vlSelfRef.b = 0x1cU;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[398]);
                    vlSelfRef.b = 0x2eU;
                } else {
                    ++(vlSymsp->__Vcoverage[397]);
                    vlSelfRef.b = 0x25U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                ++(vlSymsp->__Vcoverage[396]);
                vlSelfRef.b = 0x78U;
            } else {
                ++(vlSymsp->__Vcoverage[395]);
                vlSelfRef.b = 0xbaU;
            }
        } else if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][2U])) {
            if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][2U])) {
                if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][2U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][2U])) {
                                ++(vlSymsp->__Vcoverage[394]);
                                vlSelfRef.b = 8U;
                            } else {
                                ++(vlSymsp->__Vcoverage[393]);
                                vlSelfRef.b = 0xaeU;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][2U])) {
                            ++(vlSymsp->__Vcoverage[392]);
                            vlSelfRef.b = 0x7aU;
                        } else {
                            ++(vlSymsp->__Vcoverage[391]);
                            vlSelfRef.b = 0x65U;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][2U])) {
                            ++(vlSymsp->__Vcoverage[390]);
                            vlSelfRef.b = 0xeaU;
                        } else {
                            ++(vlSymsp->__Vcoverage[389]);
                            vlSelfRef.b = 0xf4U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[388]);
                        vlSelfRef.b = 0x56U;
                    } else {
                        ++(vlSymsp->__Vcoverage[387]);
                        vlSelfRef.b = 0x6cU;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][2U])) {
                            ++(vlSymsp->__Vcoverage[386]);
                            vlSelfRef.b = 0xa9U;
                        } else {
                            ++(vlSymsp->__Vcoverage[385]);
                            vlSelfRef.b = 0x4eU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[384]);
                        vlSelfRef.b = 0xd5U;
                    } else {
                        ++(vlSymsp->__Vcoverage[383]);
                        vlSelfRef.b = 0x8dU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[382]);
                        vlSelfRef.b = 0x6dU;
                    } else {
                        ++(vlSymsp->__Vcoverage[381]);
                        vlSelfRef.b = 0x37U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[380]);
                    vlSelfRef.b = 0xc8U;
                } else {
                    ++(vlSymsp->__Vcoverage[379]);
                    vlSelfRef.b = 0xe7U;
                }
            } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][2U])) {
                            ++(vlSymsp->__Vcoverage[378]);
                            vlSelfRef.b = 0x79U;
                        } else {
                            ++(vlSymsp->__Vcoverage[377]);
                            vlSelfRef.b = 0xe4U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[376]);
                        vlSelfRef.b = 0x95U;
                    } else {
                        ++(vlSymsp->__Vcoverage[375]);
                        vlSelfRef.b = 0x91U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[374]);
                        vlSelfRef.b = 0x62U;
                    } else {
                        ++(vlSymsp->__Vcoverage[373]);
                        vlSelfRef.b = 0xacU;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[372]);
                    vlSelfRef.b = 0xd3U;
                } else {
                    ++(vlSymsp->__Vcoverage[371]);
                    vlSelfRef.b = 0xc2U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[370]);
                        vlSelfRef.b = 0x5cU;
                    } else {
                        ++(vlSymsp->__Vcoverage[369]);
                        vlSelfRef.b = 0x24U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[368]);
                    vlSelfRef.b = 6U;
                } else {
                    ++(vlSymsp->__Vcoverage[367]);
                    vlSelfRef.b = 0x49U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[366]);
                    vlSelfRef.b = 0x0aU;
                } else {
                    ++(vlSymsp->__Vcoverage[365]);
                    vlSelfRef.b = 0x3aU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                ++(vlSymsp->__Vcoverage[364]);
                vlSelfRef.b = 0x32U;
            } else {
                ++(vlSymsp->__Vcoverage[363]);
                vlSelfRef.b = 0xe0U;
            }
        } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][2U])) {
            if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][2U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][2U])) {
                            ++(vlSymsp->__Vcoverage[362]);
                            vlSelfRef.b = 0xdbU;
                        } else {
                            ++(vlSymsp->__Vcoverage[361]);
                            vlSelfRef.b = 0x0bU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[360]);
                        vlSelfRef.b = 0x5eU;
                    } else {
                        ++(vlSymsp->__Vcoverage[359]);
                        vlSelfRef.b = 0xdeU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[358]);
                        vlSelfRef.b = 0x14U;
                    } else {
                        ++(vlSymsp->__Vcoverage[357]);
                        vlSelfRef.b = 0xb8U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[356]);
                    vlSelfRef.b = 0xeeU;
                } else {
                    ++(vlSymsp->__Vcoverage[355]);
                    vlSelfRef.b = 0x46U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[354]);
                        vlSelfRef.b = 0x88U;
                    } else {
                        ++(vlSymsp->__Vcoverage[353]);
                        vlSelfRef.b = 0x90U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[352]);
                    vlSelfRef.b = 0x2aU;
                } else {
                    ++(vlSymsp->__Vcoverage[351]);
                    vlSelfRef.b = 0x22U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[350]);
                    vlSelfRef.b = 0xdcU;
                } else {
                    ++(vlSymsp->__Vcoverage[349]);
                    vlSelfRef.b = 0x4fU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                ++(vlSymsp->__Vcoverage[348]);
                vlSelfRef.b = 0x81U;
            } else {
                ++(vlSymsp->__Vcoverage[347]);
                vlSelfRef.b = 0x60U;
            }
        } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][2U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][2U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[346]);
                        vlSelfRef.b = 0x73U;
                    } else {
                        ++(vlSymsp->__Vcoverage[345]);
                        vlSelfRef.b = 0x19U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[344]);
                    vlSelfRef.b = 0x5dU;
                } else {
                    ++(vlSymsp->__Vcoverage[343]);
                    vlSelfRef.b = 0x64U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[342]);
                    vlSelfRef.b = 0x3dU;
                } else {
                    ++(vlSymsp->__Vcoverage[341]);
                    vlSelfRef.b = 0x7eU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                ++(vlSymsp->__Vcoverage[340]);
                vlSelfRef.b = 0xa7U;
            } else {
                ++(vlSymsp->__Vcoverage[339]);
                vlSelfRef.b = 0xc4U;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][2U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[338]);
                    vlSelfRef.b = 0x17U;
                } else {
                    ++(vlSymsp->__Vcoverage[337]);
                    vlSelfRef.b = 0x44U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                ++(vlSymsp->__Vcoverage[336]);
                vlSelfRef.b = 0x97U;
            } else {
                ++(vlSymsp->__Vcoverage[335]);
                vlSelfRef.b = 0x5fU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][2U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][2U])) {
                ++(vlSymsp->__Vcoverage[334]);
                vlSelfRef.b = 0xecU;
            } else {
                ++(vlSymsp->__Vcoverage[333]);
                vlSelfRef.b = 0x13U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][2U])) {
            ++(vlSymsp->__Vcoverage[332]);
            vlSelfRef.b = 0x0cU;
        } else {
            ++(vlSymsp->__Vcoverage[331]);
            vlSelfRef.b = 0xcdU;
        }
    } else if ((0x00000040U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][2U])) {
        if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][2U])) {
            if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][2U])) {
                if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][2U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][2U])) {
                                ++(vlSymsp->__Vcoverage[330]);
                                vlSelfRef.b = 0xd2U;
                            } else {
                                ++(vlSymsp->__Vcoverage[329]);
                                vlSelfRef.b = 0xf3U;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][2U])) {
                            ++(vlSymsp->__Vcoverage[328]);
                            vlSelfRef.b = 0xffU;
                        } else {
                            ++(vlSymsp->__Vcoverage[327]);
                            vlSelfRef.b = 0x10U;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][2U])) {
                            ++(vlSymsp->__Vcoverage[326]);
                            vlSelfRef.b = 0x21U;
                        } else {
                            ++(vlSymsp->__Vcoverage[325]);
                            vlSelfRef.b = 0xdaU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[324]);
                        vlSelfRef.b = 0xb6U;
                    } else {
                        ++(vlSymsp->__Vcoverage[323]);
                        vlSelfRef.b = 0xbcU;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][2U])) {
                            ++(vlSymsp->__Vcoverage[322]);
                            vlSelfRef.b = 0xf5U;
                        } else {
                            ++(vlSymsp->__Vcoverage[321]);
                            vlSelfRef.b = 0x38U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[320]);
                        vlSelfRef.b = 0x9dU;
                    } else {
                        ++(vlSymsp->__Vcoverage[319]);
                        vlSelfRef.b = 0x92U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[318]);
                        vlSelfRef.b = 0x8fU;
                    } else {
                        ++(vlSymsp->__Vcoverage[317]);
                        vlSelfRef.b = 0x40U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[316]);
                    vlSelfRef.b = 0xa3U;
                } else {
                    ++(vlSymsp->__Vcoverage[315]);
                    vlSelfRef.b = 0x51U;
                }
            } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][2U])) {
                            ++(vlSymsp->__Vcoverage[314]);
                            vlSelfRef.b = 0xa8U;
                        } else {
                            ++(vlSymsp->__Vcoverage[313]);
                            vlSelfRef.b = 0x9fU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[312]);
                        vlSelfRef.b = 0x3cU;
                    } else {
                        ++(vlSymsp->__Vcoverage[311]);
                        vlSelfRef.b = 0x50U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[310]);
                        vlSelfRef.b = 0x7fU;
                    } else {
                        ++(vlSymsp->__Vcoverage[309]);
                        vlSelfRef.b = 2U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[308]);
                    vlSelfRef.b = 0xf9U;
                } else {
                    ++(vlSymsp->__Vcoverage[307]);
                    vlSelfRef.b = 0x45U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[306]);
                        vlSelfRef.b = 0x85U;
                    } else {
                        ++(vlSymsp->__Vcoverage[305]);
                        vlSelfRef.b = 0x33U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[304]);
                    vlSelfRef.b = 0x4dU;
                } else {
                    ++(vlSymsp->__Vcoverage[303]);
                    vlSelfRef.b = 0x43U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[302]);
                    vlSelfRef.b = 0xfbU;
                } else {
                    ++(vlSymsp->__Vcoverage[301]);
                    vlSelfRef.b = 0xaaU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                ++(vlSymsp->__Vcoverage[300]);
                vlSelfRef.b = 0xefU;
            } else {
                ++(vlSymsp->__Vcoverage[299]);
                vlSelfRef.b = 0xd0U;
            }
        } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][2U])) {
            if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][2U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][2U])) {
                            ++(vlSymsp->__Vcoverage[298]);
                            vlSelfRef.b = 0xcfU;
                        } else {
                            ++(vlSymsp->__Vcoverage[297]);
                            vlSelfRef.b = 0x58U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[296]);
                        vlSelfRef.b = 0x4cU;
                    } else {
                        ++(vlSymsp->__Vcoverage[295]);
                        vlSelfRef.b = 0x4aU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[294]);
                        vlSelfRef.b = 0x39U;
                    } else {
                        ++(vlSymsp->__Vcoverage[293]);
                        vlSelfRef.b = 0xbeU;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[292]);
                    vlSelfRef.b = 0xcbU;
                } else {
                    ++(vlSymsp->__Vcoverage[291]);
                    vlSelfRef.b = 0x6aU;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[290]);
                        vlSelfRef.b = 0x5bU;
                    } else {
                        ++(vlSymsp->__Vcoverage[289]);
                        vlSelfRef.b = 0xb1U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[288]);
                    vlSelfRef.b = 0xfcU;
                } else {
                    ++(vlSymsp->__Vcoverage[287]);
                    vlSelfRef.b = 0x20U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[286]);
                    vlSelfRef.b = 0xedU;
                } else {
                    ++(vlSymsp->__Vcoverage[285]);
                    vlSelfRef.b = 0U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                ++(vlSymsp->__Vcoverage[284]);
                vlSelfRef.b = 0xd1U;
            } else {
                ++(vlSymsp->__Vcoverage[283]);
                vlSelfRef.b = 0x53U;
            }
        } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][2U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][2U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[282]);
                        vlSelfRef.b = 0x84U;
                    } else {
                        ++(vlSymsp->__Vcoverage[281]);
                        vlSelfRef.b = 0x2fU;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[280]);
                    vlSelfRef.b = 0xe3U;
                } else {
                    ++(vlSymsp->__Vcoverage[279]);
                    vlSelfRef.b = 0x29U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[278]);
                    vlSelfRef.b = 0xb3U;
                } else {
                    ++(vlSymsp->__Vcoverage[277]);
                    vlSelfRef.b = 0xd6U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                ++(vlSymsp->__Vcoverage[276]);
                vlSelfRef.b = 0x3bU;
            } else {
                ++(vlSymsp->__Vcoverage[275]);
                vlSelfRef.b = 0x52U;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][2U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[274]);
                    vlSelfRef.b = 0xa0U;
                } else {
                    ++(vlSymsp->__Vcoverage[273]);
                    vlSelfRef.b = 0x5aU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                ++(vlSymsp->__Vcoverage[272]);
                vlSelfRef.b = 0x6eU;
            } else {
                ++(vlSymsp->__Vcoverage[271]);
                vlSelfRef.b = 0x1bU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][2U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][2U])) {
                ++(vlSymsp->__Vcoverage[270]);
                vlSelfRef.b = 0x1aU;
            } else {
                ++(vlSymsp->__Vcoverage[269]);
                vlSelfRef.b = 0x2cU;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][2U])) {
            ++(vlSymsp->__Vcoverage[268]);
            vlSelfRef.b = 0x83U;
        } else {
            ++(vlSymsp->__Vcoverage[267]);
            vlSelfRef.b = 9U;
        }
    } else if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][2U])) {
        if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][2U])) {
            if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][2U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][2U])) {
                            ++(vlSymsp->__Vcoverage[266]);
                            vlSelfRef.b = 0x75U;
                        } else {
                            ++(vlSymsp->__Vcoverage[265]);
                            vlSelfRef.b = 0xb2U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[264]);
                        vlSelfRef.b = 0x27U;
                    } else {
                        ++(vlSymsp->__Vcoverage[263]);
                        vlSelfRef.b = 0xebU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[262]);
                        vlSelfRef.b = 0xe2U;
                    } else {
                        ++(vlSymsp->__Vcoverage[261]);
                        vlSelfRef.b = 0x80U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[260]);
                    vlSelfRef.b = 0x12U;
                } else {
                    ++(vlSymsp->__Vcoverage[259]);
                    vlSelfRef.b = 7U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[258]);
                        vlSelfRef.b = 0x9aU;
                    } else {
                        ++(vlSymsp->__Vcoverage[257]);
                        vlSelfRef.b = 5U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[256]);
                    vlSelfRef.b = 0x96U;
                } else {
                    ++(vlSymsp->__Vcoverage[255]);
                    vlSelfRef.b = 0x18U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[254]);
                    vlSelfRef.b = 0xc3U;
                } else {
                    ++(vlSymsp->__Vcoverage[253]);
                    vlSelfRef.b = 0x23U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                ++(vlSymsp->__Vcoverage[252]);
                vlSelfRef.b = 0xc7U;
            } else {
                ++(vlSymsp->__Vcoverage[251]);
                vlSelfRef.b = 4U;
            }
        } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][2U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][2U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[250]);
                        vlSelfRef.b = 0x15U;
                    } else {
                        ++(vlSymsp->__Vcoverage[249]);
                        vlSelfRef.b = 0x31U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[248]);
                    vlSelfRef.b = 0xd8U;
                } else {
                    ++(vlSymsp->__Vcoverage[247]);
                    vlSelfRef.b = 0x71U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[246]);
                    vlSelfRef.b = 0xf1U;
                } else {
                    ++(vlSymsp->__Vcoverage[245]);
                    vlSelfRef.b = 0xe5U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                ++(vlSymsp->__Vcoverage[244]);
                vlSelfRef.b = 0xa5U;
            } else {
                ++(vlSymsp->__Vcoverage[243]);
                vlSelfRef.b = 0x34U;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][2U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[242]);
                    vlSelfRef.b = 0xccU;
                } else {
                    ++(vlSymsp->__Vcoverage[241]);
                    vlSelfRef.b = 0xf7U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                ++(vlSymsp->__Vcoverage[240]);
                vlSelfRef.b = 0x3fU;
            } else {
                ++(vlSymsp->__Vcoverage[239]);
                vlSelfRef.b = 0x36U;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][2U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][2U])) {
                ++(vlSymsp->__Vcoverage[238]);
                vlSelfRef.b = 0x26U;
            } else {
                ++(vlSymsp->__Vcoverage[237]);
                vlSelfRef.b = 0x93U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][2U])) {
            ++(vlSymsp->__Vcoverage[236]);
            vlSelfRef.b = 0xfdU;
        } else {
            ++(vlSymsp->__Vcoverage[235]);
            vlSelfRef.b = 0xb7U;
        }
    } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][2U])) {
        if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][2U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][2U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][2U])) {
                        ++(vlSymsp->__Vcoverage[234]);
                        vlSelfRef.b = 0xc0U;
                    } else {
                        ++(vlSymsp->__Vcoverage[233]);
                        vlSelfRef.b = 0x72U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[232]);
                    vlSelfRef.b = 0xa4U;
                } else {
                    ++(vlSymsp->__Vcoverage[231]);
                    vlSelfRef.b = 0x9cU;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[230]);
                    vlSelfRef.b = 0xafU;
                } else {
                    ++(vlSymsp->__Vcoverage[229]);
                    vlSelfRef.b = 0xa2U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                ++(vlSymsp->__Vcoverage[228]);
                vlSelfRef.b = 0xd4U;
            } else {
                ++(vlSymsp->__Vcoverage[227]);
                vlSelfRef.b = 0xadU;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][2U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[226]);
                    vlSelfRef.b = 0xf0U;
                } else {
                    ++(vlSymsp->__Vcoverage[225]);
                    vlSelfRef.b = 0x47U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                ++(vlSymsp->__Vcoverage[224]);
                vlSelfRef.b = 0x59U;
            } else {
                ++(vlSymsp->__Vcoverage[223]);
                vlSelfRef.b = 0xfaU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][2U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][2U])) {
                ++(vlSymsp->__Vcoverage[222]);
                vlSelfRef.b = 0x7dU;
            } else {
                ++(vlSymsp->__Vcoverage[221]);
                vlSelfRef.b = 0xc9U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][2U])) {
            ++(vlSymsp->__Vcoverage[220]);
            vlSelfRef.b = 0x82U;
        } else {
            ++(vlSymsp->__Vcoverage[219]);
            vlSelfRef.b = 0xcaU;
        }
    } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][2U])) {
        if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][2U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][2U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][2U])) {
                    ++(vlSymsp->__Vcoverage[218]);
                    vlSelfRef.b = 0x76U;
                } else {
                    ++(vlSymsp->__Vcoverage[217]);
                    vlSelfRef.b = 0xabU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][2U])) {
                ++(vlSymsp->__Vcoverage[216]);
                vlSelfRef.b = 0xd7U;
            } else {
                ++(vlSymsp->__Vcoverage[215]);
                vlSelfRef.b = 0xfeU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][2U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][2U])) {
                ++(vlSymsp->__Vcoverage[214]);
                vlSelfRef.b = 0x2bU;
            } else {
                ++(vlSymsp->__Vcoverage[213]);
                vlSelfRef.b = 0x67U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][2U])) {
            ++(vlSymsp->__Vcoverage[212]);
            vlSelfRef.b = 1U;
        } else {
            ++(vlSymsp->__Vcoverage[211]);
            vlSelfRef.b = 0x30U;
        }
    } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][2U])) {
        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][2U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][2U])) {
                ++(vlSymsp->__Vcoverage[210]);
                vlSelfRef.b = 0xc5U;
            } else {
                ++(vlSymsp->__Vcoverage[209]);
                vlSelfRef.b = 0x6fU;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][2U])) {
            ++(vlSymsp->__Vcoverage[208]);
            vlSelfRef.b = 0x6bU;
        } else {
            ++(vlSymsp->__Vcoverage[207]);
            vlSelfRef.b = 0xf2U;
        }
    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][2U])) {
        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][2U])) {
            ++(vlSymsp->__Vcoverage[206]);
            vlSelfRef.b = 0x7bU;
        } else {
            ++(vlSymsp->__Vcoverage[205]);
            vlSelfRef.b = 0x77U;
        }
    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][2U])) {
        ++(vlSymsp->__Vcoverage[204]);
        vlSelfRef.b = 0x7cU;
    } else {
        ++(vlSymsp->__Vcoverage[203]);
        vlSelfRef.b = 0x63U;
    }
    ++(vlSymsp->__Vcoverage[459]);
}

void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__2__KET____DOT__sbox_row__BRA__2__KET____DOT__u_sbox__1(Vtb_aes_sbox* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+            Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__2__KET____DOT__sbox_row__BRA__2__KET____DOT__u_sbox__1\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    vlSelfRef.a = vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
        [2U][2U];
}

void Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__2__KET____DOT__sbox_row__BRA__3__KET____DOT__u_sbox__0(Vtb_aes_sbox* vlSelf) {
    VL_DEBUG_IF(VL_DBG_MSGF("+            Vtb_aes_sbox___nba_sequent__TOP__tb__DOT__top_module1__DOT__sbox_col__BRA__2__KET____DOT__sbox_row__BRA__3__KET____DOT__u_sbox__0\n"); );
    Vtb__Syms* const __restrict vlSymsp VL_ATTR_UNUSED = vlSelf->vlSymsp;
    auto& vlSelfRef = std::ref(*vlSelf).get();
    // Body
    if ((0x00000080U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
         [2U][3U])) {
        if ((0x00000040U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][3U])) {
            if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][3U])) {
                if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][3U])) {
                            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][3U])) {
                                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                     [2U][3U])) {
                                    vlSelfRef.b = 0x16U;
                                    ++(vlSymsp->__Vcoverage[458]);
                                } else {
                                    ++(vlSymsp->__Vcoverage[457]);
                                    vlSelfRef.b = 0xbbU;
                                }
                            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                        [2U][3U])) {
                                ++(vlSymsp->__Vcoverage[456]);
                                vlSelfRef.b = 0x54U;
                            } else {
                                ++(vlSymsp->__Vcoverage[455]);
                                vlSelfRef.b = 0xb0U;
                            }
                        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][3U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][3U])) {
                                ++(vlSymsp->__Vcoverage[454]);
                                vlSelfRef.b = 0x0fU;
                            } else {
                                ++(vlSymsp->__Vcoverage[453]);
                                vlSelfRef.b = 0x2dU;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][3U])) {
                            ++(vlSymsp->__Vcoverage[452]);
                            vlSelfRef.b = 0x99U;
                        } else {
                            ++(vlSymsp->__Vcoverage[451]);
                            vlSelfRef.b = 0x41U;
                        }
                    } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][3U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][3U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][3U])) {
                                ++(vlSymsp->__Vcoverage[450]);
                                vlSelfRef.b = 0x68U;
                            } else {
                                ++(vlSymsp->__Vcoverage[449]);
                                vlSelfRef.b = 0x42U;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][3U])) {
                            ++(vlSymsp->__Vcoverage[448]);
                            vlSelfRef.b = 0xe6U;
                        } else {
                            ++(vlSymsp->__Vcoverage[447]);
                            vlSelfRef.b = 0xbfU;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][3U])) {
                            ++(vlSymsp->__Vcoverage[446]);
                            vlSelfRef.b = 0x0dU;
                        } else {
                            ++(vlSymsp->__Vcoverage[445]);
                            vlSelfRef.b = 0x89U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[444]);
                        vlSelfRef.b = 0xa1U;
                    } else {
                        ++(vlSymsp->__Vcoverage[443]);
                        vlSelfRef.b = 0x8cU;
                    }
                } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][3U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][3U])) {
                                ++(vlSymsp->__Vcoverage[442]);
                                vlSelfRef.b = 0xdfU;
                            } else {
                                ++(vlSymsp->__Vcoverage[441]);
                                vlSelfRef.b = 0x28U;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][3U])) {
                            ++(vlSymsp->__Vcoverage[440]);
                            vlSelfRef.b = 0x55U;
                        } else {
                            ++(vlSymsp->__Vcoverage[439]);
                            vlSelfRef.b = 0xceU;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][3U])) {
                            ++(vlSymsp->__Vcoverage[438]);
                            vlSelfRef.b = 0xe9U;
                        } else {
                            ++(vlSymsp->__Vcoverage[437]);
                            vlSelfRef.b = 0x87U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[436]);
                        vlSelfRef.b = 0x1eU;
                    } else {
                        ++(vlSymsp->__Vcoverage[435]);
                        vlSelfRef.b = 0x9bU;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][3U])) {
                            ++(vlSymsp->__Vcoverage[434]);
                            vlSelfRef.b = 0x94U;
                        } else {
                            ++(vlSymsp->__Vcoverage[433]);
                            vlSelfRef.b = 0x8eU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[432]);
                        vlSelfRef.b = 0xd9U;
                    } else {
                        ++(vlSymsp->__Vcoverage[431]);
                        vlSelfRef.b = 0x69U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[430]);
                        vlSelfRef.b = 0x11U;
                    } else {
                        ++(vlSymsp->__Vcoverage[429]);
                        vlSelfRef.b = 0x98U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[428]);
                    vlSelfRef.b = 0xf8U;
                } else {
                    ++(vlSymsp->__Vcoverage[427]);
                    vlSelfRef.b = 0xe1U;
                }
            } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][3U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][3U])) {
                                ++(vlSymsp->__Vcoverage[426]);
                                vlSelfRef.b = 0x9eU;
                            } else {
                                ++(vlSymsp->__Vcoverage[425]);
                                vlSelfRef.b = 0x1dU;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][3U])) {
                            ++(vlSymsp->__Vcoverage[424]);
                            vlSelfRef.b = 0xc1U;
                        } else {
                            ++(vlSymsp->__Vcoverage[423]);
                            vlSelfRef.b = 0x86U;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][3U])) {
                            ++(vlSymsp->__Vcoverage[422]);
                            vlSelfRef.b = 0xb9U;
                        } else {
                            ++(vlSymsp->__Vcoverage[421]);
                            vlSelfRef.b = 0x57U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[420]);
                        vlSelfRef.b = 0x35U;
                    } else {
                        ++(vlSymsp->__Vcoverage[419]);
                        vlSelfRef.b = 0x61U;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][3U])) {
                            ++(vlSymsp->__Vcoverage[418]);
                            vlSelfRef.b = 0x0eU;
                        } else {
                            ++(vlSymsp->__Vcoverage[417]);
                            vlSelfRef.b = 0xf6U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[416]);
                        vlSelfRef.b = 3U;
                    } else {
                        ++(vlSymsp->__Vcoverage[415]);
                        vlSelfRef.b = 0x48U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[414]);
                        vlSelfRef.b = 0x66U;
                    } else {
                        ++(vlSymsp->__Vcoverage[413]);
                        vlSelfRef.b = 0xb5U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[412]);
                    vlSelfRef.b = 0x3eU;
                } else {
                    ++(vlSymsp->__Vcoverage[411]);
                    vlSelfRef.b = 0x70U;
                }
            } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][3U])) {
                            ++(vlSymsp->__Vcoverage[410]);
                            vlSelfRef.b = 0x8aU;
                        } else {
                            ++(vlSymsp->__Vcoverage[409]);
                            vlSelfRef.b = 0x8bU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[408]);
                        vlSelfRef.b = 0xbdU;
                    } else {
                        ++(vlSymsp->__Vcoverage[407]);
                        vlSelfRef.b = 0x4bU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[406]);
                        vlSelfRef.b = 0x1fU;
                    } else {
                        ++(vlSymsp->__Vcoverage[405]);
                        vlSelfRef.b = 0x74U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[404]);
                    vlSelfRef.b = 0xddU;
                } else {
                    ++(vlSymsp->__Vcoverage[403]);
                    vlSelfRef.b = 0xe8U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[402]);
                        vlSelfRef.b = 0xc6U;
                    } else {
                        ++(vlSymsp->__Vcoverage[401]);
                        vlSelfRef.b = 0xb4U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[400]);
                    vlSelfRef.b = 0xa6U;
                } else {
                    ++(vlSymsp->__Vcoverage[399]);
                    vlSelfRef.b = 0x1cU;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[398]);
                    vlSelfRef.b = 0x2eU;
                } else {
                    ++(vlSymsp->__Vcoverage[397]);
                    vlSelfRef.b = 0x25U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                ++(vlSymsp->__Vcoverage[396]);
                vlSelfRef.b = 0x78U;
            } else {
                ++(vlSymsp->__Vcoverage[395]);
                vlSelfRef.b = 0xbaU;
            }
        } else if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][3U])) {
            if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][3U])) {
                if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][3U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][3U])) {
                                ++(vlSymsp->__Vcoverage[394]);
                                vlSelfRef.b = 8U;
                            } else {
                                ++(vlSymsp->__Vcoverage[393]);
                                vlSelfRef.b = 0xaeU;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][3U])) {
                            ++(vlSymsp->__Vcoverage[392]);
                            vlSelfRef.b = 0x7aU;
                        } else {
                            ++(vlSymsp->__Vcoverage[391]);
                            vlSelfRef.b = 0x65U;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][3U])) {
                            ++(vlSymsp->__Vcoverage[390]);
                            vlSelfRef.b = 0xeaU;
                        } else {
                            ++(vlSymsp->__Vcoverage[389]);
                            vlSelfRef.b = 0xf4U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[388]);
                        vlSelfRef.b = 0x56U;
                    } else {
                        ++(vlSymsp->__Vcoverage[387]);
                        vlSelfRef.b = 0x6cU;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][3U])) {
                            ++(vlSymsp->__Vcoverage[386]);
                            vlSelfRef.b = 0xa9U;
                        } else {
                            ++(vlSymsp->__Vcoverage[385]);
                            vlSelfRef.b = 0x4eU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[384]);
                        vlSelfRef.b = 0xd5U;
                    } else {
                        ++(vlSymsp->__Vcoverage[383]);
                        vlSelfRef.b = 0x8dU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[382]);
                        vlSelfRef.b = 0x6dU;
                    } else {
                        ++(vlSymsp->__Vcoverage[381]);
                        vlSelfRef.b = 0x37U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[380]);
                    vlSelfRef.b = 0xc8U;
                } else {
                    ++(vlSymsp->__Vcoverage[379]);
                    vlSelfRef.b = 0xe7U;
                }
            } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][3U])) {
                            ++(vlSymsp->__Vcoverage[378]);
                            vlSelfRef.b = 0x79U;
                        } else {
                            ++(vlSymsp->__Vcoverage[377]);
                            vlSelfRef.b = 0xe4U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[376]);
                        vlSelfRef.b = 0x95U;
                    } else {
                        ++(vlSymsp->__Vcoverage[375]);
                        vlSelfRef.b = 0x91U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[374]);
                        vlSelfRef.b = 0x62U;
                    } else {
                        ++(vlSymsp->__Vcoverage[373]);
                        vlSelfRef.b = 0xacU;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[372]);
                    vlSelfRef.b = 0xd3U;
                } else {
                    ++(vlSymsp->__Vcoverage[371]);
                    vlSelfRef.b = 0xc2U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[370]);
                        vlSelfRef.b = 0x5cU;
                    } else {
                        ++(vlSymsp->__Vcoverage[369]);
                        vlSelfRef.b = 0x24U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[368]);
                    vlSelfRef.b = 6U;
                } else {
                    ++(vlSymsp->__Vcoverage[367]);
                    vlSelfRef.b = 0x49U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[366]);
                    vlSelfRef.b = 0x0aU;
                } else {
                    ++(vlSymsp->__Vcoverage[365]);
                    vlSelfRef.b = 0x3aU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                ++(vlSymsp->__Vcoverage[364]);
                vlSelfRef.b = 0x32U;
            } else {
                ++(vlSymsp->__Vcoverage[363]);
                vlSelfRef.b = 0xe0U;
            }
        } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][3U])) {
            if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][3U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][3U])) {
                            ++(vlSymsp->__Vcoverage[362]);
                            vlSelfRef.b = 0xdbU;
                        } else {
                            ++(vlSymsp->__Vcoverage[361]);
                            vlSelfRef.b = 0x0bU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[360]);
                        vlSelfRef.b = 0x5eU;
                    } else {
                        ++(vlSymsp->__Vcoverage[359]);
                        vlSelfRef.b = 0xdeU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[358]);
                        vlSelfRef.b = 0x14U;
                    } else {
                        ++(vlSymsp->__Vcoverage[357]);
                        vlSelfRef.b = 0xb8U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[356]);
                    vlSelfRef.b = 0xeeU;
                } else {
                    ++(vlSymsp->__Vcoverage[355]);
                    vlSelfRef.b = 0x46U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[354]);
                        vlSelfRef.b = 0x88U;
                    } else {
                        ++(vlSymsp->__Vcoverage[353]);
                        vlSelfRef.b = 0x90U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[352]);
                    vlSelfRef.b = 0x2aU;
                } else {
                    ++(vlSymsp->__Vcoverage[351]);
                    vlSelfRef.b = 0x22U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[350]);
                    vlSelfRef.b = 0xdcU;
                } else {
                    ++(vlSymsp->__Vcoverage[349]);
                    vlSelfRef.b = 0x4fU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                ++(vlSymsp->__Vcoverage[348]);
                vlSelfRef.b = 0x81U;
            } else {
                ++(vlSymsp->__Vcoverage[347]);
                vlSelfRef.b = 0x60U;
            }
        } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][3U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][3U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[346]);
                        vlSelfRef.b = 0x73U;
                    } else {
                        ++(vlSymsp->__Vcoverage[345]);
                        vlSelfRef.b = 0x19U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[344]);
                    vlSelfRef.b = 0x5dU;
                } else {
                    ++(vlSymsp->__Vcoverage[343]);
                    vlSelfRef.b = 0x64U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[342]);
                    vlSelfRef.b = 0x3dU;
                } else {
                    ++(vlSymsp->__Vcoverage[341]);
                    vlSelfRef.b = 0x7eU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                ++(vlSymsp->__Vcoverage[340]);
                vlSelfRef.b = 0xa7U;
            } else {
                ++(vlSymsp->__Vcoverage[339]);
                vlSelfRef.b = 0xc4U;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][3U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[338]);
                    vlSelfRef.b = 0x17U;
                } else {
                    ++(vlSymsp->__Vcoverage[337]);
                    vlSelfRef.b = 0x44U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                ++(vlSymsp->__Vcoverage[336]);
                vlSelfRef.b = 0x97U;
            } else {
                ++(vlSymsp->__Vcoverage[335]);
                vlSelfRef.b = 0x5fU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][3U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][3U])) {
                ++(vlSymsp->__Vcoverage[334]);
                vlSelfRef.b = 0xecU;
            } else {
                ++(vlSymsp->__Vcoverage[333]);
                vlSelfRef.b = 0x13U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][3U])) {
            ++(vlSymsp->__Vcoverage[332]);
            vlSelfRef.b = 0x0cU;
        } else {
            ++(vlSymsp->__Vcoverage[331]);
            vlSelfRef.b = 0xcdU;
        }
    } else if ((0x00000040U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][3U])) {
        if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][3U])) {
            if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][3U])) {
                if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][3U])) {
                            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                 [2U][3U])) {
                                ++(vlSymsp->__Vcoverage[330]);
                                vlSelfRef.b = 0xd2U;
                            } else {
                                ++(vlSymsp->__Vcoverage[329]);
                                vlSelfRef.b = 0xf3U;
                            }
                        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                    [2U][3U])) {
                            ++(vlSymsp->__Vcoverage[328]);
                            vlSelfRef.b = 0xffU;
                        } else {
                            ++(vlSymsp->__Vcoverage[327]);
                            vlSelfRef.b = 0x10U;
                        }
                    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][3U])) {
                            ++(vlSymsp->__Vcoverage[326]);
                            vlSelfRef.b = 0x21U;
                        } else {
                            ++(vlSymsp->__Vcoverage[325]);
                            vlSelfRef.b = 0xdaU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[324]);
                        vlSelfRef.b = 0xb6U;
                    } else {
                        ++(vlSymsp->__Vcoverage[323]);
                        vlSelfRef.b = 0xbcU;
                    }
                } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][3U])) {
                            ++(vlSymsp->__Vcoverage[322]);
                            vlSelfRef.b = 0xf5U;
                        } else {
                            ++(vlSymsp->__Vcoverage[321]);
                            vlSelfRef.b = 0x38U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[320]);
                        vlSelfRef.b = 0x9dU;
                    } else {
                        ++(vlSymsp->__Vcoverage[319]);
                        vlSelfRef.b = 0x92U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[318]);
                        vlSelfRef.b = 0x8fU;
                    } else {
                        ++(vlSymsp->__Vcoverage[317]);
                        vlSelfRef.b = 0x40U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[316]);
                    vlSelfRef.b = 0xa3U;
                } else {
                    ++(vlSymsp->__Vcoverage[315]);
                    vlSelfRef.b = 0x51U;
                }
            } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][3U])) {
                            ++(vlSymsp->__Vcoverage[314]);
                            vlSelfRef.b = 0xa8U;
                        } else {
                            ++(vlSymsp->__Vcoverage[313]);
                            vlSelfRef.b = 0x9fU;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[312]);
                        vlSelfRef.b = 0x3cU;
                    } else {
                        ++(vlSymsp->__Vcoverage[311]);
                        vlSelfRef.b = 0x50U;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[310]);
                        vlSelfRef.b = 0x7fU;
                    } else {
                        ++(vlSymsp->__Vcoverage[309]);
                        vlSelfRef.b = 2U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[308]);
                    vlSelfRef.b = 0xf9U;
                } else {
                    ++(vlSymsp->__Vcoverage[307]);
                    vlSelfRef.b = 0x45U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[306]);
                        vlSelfRef.b = 0x85U;
                    } else {
                        ++(vlSymsp->__Vcoverage[305]);
                        vlSelfRef.b = 0x33U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[304]);
                    vlSelfRef.b = 0x4dU;
                } else {
                    ++(vlSymsp->__Vcoverage[303]);
                    vlSelfRef.b = 0x43U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[302]);
                    vlSelfRef.b = 0xfbU;
                } else {
                    ++(vlSymsp->__Vcoverage[301]);
                    vlSelfRef.b = 0xaaU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                ++(vlSymsp->__Vcoverage[300]);
                vlSelfRef.b = 0xefU;
            } else {
                ++(vlSymsp->__Vcoverage[299]);
                vlSelfRef.b = 0xd0U;
            }
        } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][3U])) {
            if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][3U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][3U])) {
                            ++(vlSymsp->__Vcoverage[298]);
                            vlSelfRef.b = 0xcfU;
                        } else {
                            ++(vlSymsp->__Vcoverage[297]);
                            vlSelfRef.b = 0x58U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[296]);
                        vlSelfRef.b = 0x4cU;
                    } else {
                        ++(vlSymsp->__Vcoverage[295]);
                        vlSelfRef.b = 0x4aU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[294]);
                        vlSelfRef.b = 0x39U;
                    } else {
                        ++(vlSymsp->__Vcoverage[293]);
                        vlSelfRef.b = 0xbeU;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[292]);
                    vlSelfRef.b = 0xcbU;
                } else {
                    ++(vlSymsp->__Vcoverage[291]);
                    vlSelfRef.b = 0x6aU;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[290]);
                        vlSelfRef.b = 0x5bU;
                    } else {
                        ++(vlSymsp->__Vcoverage[289]);
                        vlSelfRef.b = 0xb1U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[288]);
                    vlSelfRef.b = 0xfcU;
                } else {
                    ++(vlSymsp->__Vcoverage[287]);
                    vlSelfRef.b = 0x20U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[286]);
                    vlSelfRef.b = 0xedU;
                } else {
                    ++(vlSymsp->__Vcoverage[285]);
                    vlSelfRef.b = 0U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                ++(vlSymsp->__Vcoverage[284]);
                vlSelfRef.b = 0xd1U;
            } else {
                ++(vlSymsp->__Vcoverage[283]);
                vlSelfRef.b = 0x53U;
            }
        } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][3U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][3U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[282]);
                        vlSelfRef.b = 0x84U;
                    } else {
                        ++(vlSymsp->__Vcoverage[281]);
                        vlSelfRef.b = 0x2fU;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[280]);
                    vlSelfRef.b = 0xe3U;
                } else {
                    ++(vlSymsp->__Vcoverage[279]);
                    vlSelfRef.b = 0x29U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[278]);
                    vlSelfRef.b = 0xb3U;
                } else {
                    ++(vlSymsp->__Vcoverage[277]);
                    vlSelfRef.b = 0xd6U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                ++(vlSymsp->__Vcoverage[276]);
                vlSelfRef.b = 0x3bU;
            } else {
                ++(vlSymsp->__Vcoverage[275]);
                vlSelfRef.b = 0x52U;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][3U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[274]);
                    vlSelfRef.b = 0xa0U;
                } else {
                    ++(vlSymsp->__Vcoverage[273]);
                    vlSelfRef.b = 0x5aU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                ++(vlSymsp->__Vcoverage[272]);
                vlSelfRef.b = 0x6eU;
            } else {
                ++(vlSymsp->__Vcoverage[271]);
                vlSelfRef.b = 0x1bU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][3U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][3U])) {
                ++(vlSymsp->__Vcoverage[270]);
                vlSelfRef.b = 0x1aU;
            } else {
                ++(vlSymsp->__Vcoverage[269]);
                vlSelfRef.b = 0x2cU;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][3U])) {
            ++(vlSymsp->__Vcoverage[268]);
            vlSelfRef.b = 0x83U;
        } else {
            ++(vlSymsp->__Vcoverage[267]);
            vlSelfRef.b = 9U;
        }
    } else if ((0x00000020U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][3U])) {
        if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][3U])) {
            if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][3U])) {
                if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                             [2U][3U])) {
                            ++(vlSymsp->__Vcoverage[266]);
                            vlSelfRef.b = 0x75U;
                        } else {
                            ++(vlSymsp->__Vcoverage[265]);
                            vlSelfRef.b = 0xb2U;
                        }
                    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                                [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[264]);
                        vlSelfRef.b = 0x27U;
                    } else {
                        ++(vlSymsp->__Vcoverage[263]);
                        vlSelfRef.b = 0xebU;
                    }
                } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[262]);
                        vlSelfRef.b = 0xe2U;
                    } else {
                        ++(vlSymsp->__Vcoverage[261]);
                        vlSelfRef.b = 0x80U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[260]);
                    vlSelfRef.b = 0x12U;
                } else {
                    ++(vlSymsp->__Vcoverage[259]);
                    vlSelfRef.b = 7U;
                }
            } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[258]);
                        vlSelfRef.b = 0x9aU;
                    } else {
                        ++(vlSymsp->__Vcoverage[257]);
                        vlSelfRef.b = 5U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[256]);
                    vlSelfRef.b = 0x96U;
                } else {
                    ++(vlSymsp->__Vcoverage[255]);
                    vlSelfRef.b = 0x18U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[254]);
                    vlSelfRef.b = 0xc3U;
                } else {
                    ++(vlSymsp->__Vcoverage[253]);
                    vlSelfRef.b = 0x23U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                ++(vlSymsp->__Vcoverage[252]);
                vlSelfRef.b = 0xc7U;
            } else {
                ++(vlSymsp->__Vcoverage[251]);
                vlSelfRef.b = 4U;
            }
        } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][3U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][3U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[250]);
                        vlSelfRef.b = 0x15U;
                    } else {
                        ++(vlSymsp->__Vcoverage[249]);
                        vlSelfRef.b = 0x31U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[248]);
                    vlSelfRef.b = 0xd8U;
                } else {
                    ++(vlSymsp->__Vcoverage[247]);
                    vlSelfRef.b = 0x71U;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[246]);
                    vlSelfRef.b = 0xf1U;
                } else {
                    ++(vlSymsp->__Vcoverage[245]);
                    vlSelfRef.b = 0xe5U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                ++(vlSymsp->__Vcoverage[244]);
                vlSelfRef.b = 0xa5U;
            } else {
                ++(vlSymsp->__Vcoverage[243]);
                vlSelfRef.b = 0x34U;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][3U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[242]);
                    vlSelfRef.b = 0xccU;
                } else {
                    ++(vlSymsp->__Vcoverage[241]);
                    vlSelfRef.b = 0xf7U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                ++(vlSymsp->__Vcoverage[240]);
                vlSelfRef.b = 0x3fU;
            } else {
                ++(vlSymsp->__Vcoverage[239]);
                vlSelfRef.b = 0x36U;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][3U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][3U])) {
                ++(vlSymsp->__Vcoverage[238]);
                vlSelfRef.b = 0x26U;
            } else {
                ++(vlSymsp->__Vcoverage[237]);
                vlSelfRef.b = 0x93U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][3U])) {
            ++(vlSymsp->__Vcoverage[236]);
            vlSelfRef.b = 0xfdU;
        } else {
            ++(vlSymsp->__Vcoverage[235]);
            vlSelfRef.b = 0xb7U;
        }
    } else if ((0x00000010U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][3U])) {
        if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][3U])) {
            if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][3U])) {
                if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                         [2U][3U])) {
                        ++(vlSymsp->__Vcoverage[234]);
                        vlSelfRef.b = 0xc0U;
                    } else {
                        ++(vlSymsp->__Vcoverage[233]);
                        vlSelfRef.b = 0x72U;
                    }
                } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                            [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[232]);
                    vlSelfRef.b = 0xa4U;
                } else {
                    ++(vlSymsp->__Vcoverage[231]);
                    vlSelfRef.b = 0x9cU;
                }
            } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[230]);
                    vlSelfRef.b = 0xafU;
                } else {
                    ++(vlSymsp->__Vcoverage[229]);
                    vlSelfRef.b = 0xa2U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                ++(vlSymsp->__Vcoverage[228]);
                vlSelfRef.b = 0xd4U;
            } else {
                ++(vlSymsp->__Vcoverage[227]);
                vlSelfRef.b = 0xadU;
            }
        } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][3U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[226]);
                    vlSelfRef.b = 0xf0U;
                } else {
                    ++(vlSymsp->__Vcoverage[225]);
                    vlSelfRef.b = 0x47U;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                ++(vlSymsp->__Vcoverage[224]);
                vlSelfRef.b = 0x59U;
            } else {
                ++(vlSymsp->__Vcoverage[223]);
                vlSelfRef.b = 0xfaU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][3U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][3U])) {
                ++(vlSymsp->__Vcoverage[222]);
                vlSelfRef.b = 0x7dU;
            } else {
                ++(vlSymsp->__Vcoverage[221]);
                vlSelfRef.b = 0xc9U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][3U])) {
            ++(vlSymsp->__Vcoverage[220]);
            vlSelfRef.b = 0x82U;
        } else {
            ++(vlSymsp->__Vcoverage[219]);
            vlSelfRef.b = 0xcaU;
        }
    } else if ((8U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][3U])) {
        if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][3U])) {
            if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][3U])) {
                if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                     [2U][3U])) {
                    ++(vlSymsp->__Vcoverage[218]);
                    vlSelfRef.b = 0x76U;
                } else {
                    ++(vlSymsp->__Vcoverage[217]);
                    vlSelfRef.b = 0xabU;
                }
            } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                        [2U][3U])) {
                ++(vlSymsp->__Vcoverage[216]);
                vlSelfRef.b = 0xd7U;
            } else {
                ++(vlSymsp->__Vcoverage[215]);
                vlSelfRef.b = 0xfeU;
            }
        } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][3U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][3U])) {
                ++(vlSymsp->__Vcoverage[214]);
                vlSelfRef.b = 0x2bU;
            } else {
                ++(vlSymsp->__Vcoverage[213]);
                vlSelfRef.b = 0x67U;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][3U])) {
            ++(vlSymsp->__Vcoverage[212]);
            vlSelfRef.b = 1U;
        } else {
            ++(vlSymsp->__Vcoverage[211]);
            vlSelfRef.b = 0x30U;
        }
    } else if ((4U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][3U])) {
        if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][3U])) {
            if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                 [2U][3U])) {
                ++(vlSymsp->__Vcoverage[210]);
                vlSelfRef.b = 0xc5U;
            } else {
                ++(vlSymsp->__Vcoverage[209]);
                vlSelfRef.b = 0x6fU;
            }
        } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                    [2U][3U])) {
            ++(vlSymsp->__Vcoverage[208]);
            vlSelfRef.b = 0x6bU;
        } else {
            ++(vlSymsp->__Vcoverage[207]);
            vlSelfRef.b = 0xf2U;
        }
    } else if ((2U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][3U])) {
        if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
             [2U][3U])) {
            ++(vlSymsp->__Vcoverage[206]);
            vlSelfRef.b = 0x7bU;
        } else {
            ++(vlSymsp->__Vcoverage[205]);
            vlSelfRef.b = 0x77U;
        }
    } else if ((1U & vlSymsp->TOP.tb__DOT__top_module1__DOT__sa
                [2U][3U])) {
        ++(vlSymsp->__Vcoverage[204]);
        vlSelfRef.b = 0x7cU;
    } else {
        ++(vlSymsp->__Vcoverage[203]);
        vlSelfRef.b = 0x63U;
    }
    ++(vlSymsp->__Vcoverage[459]);
}
