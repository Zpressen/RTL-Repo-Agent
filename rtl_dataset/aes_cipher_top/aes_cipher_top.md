**AES-128 Encryption System Design Specification**

---

**1. System Overview**

This document specifies a hardware implementation of the AES-128
encryption algorithm. The system accepts a 128-bit plaintext and a
128-bit cipher key, and after 10 rounds of transformation produces the
128-bit ciphertext. All operations are synchronous to a single clock
domain.

**1.1 Top-Level Interface**

| **Signal Name** | **Direction** | **Width** | **Description** |
| --- | --- | --- | --- |
| clk | input | 1 | System clock |
| rst | input | 1 | Asynchronous reset (active low) |
| ld | input | 1 | Load signal — initiates encryption of new input data |
| done | output | 1 | Encryption complete — asserted when ciphertext is valid |
| key | input | 128 | Cipher key |
| text_in | input | 128 | Input plaintext |
| text_out | output | 128 | Output ciphertext |

**1.2 Operational Overview**

Upon assertion of `ld`, the system loads the input plaintext and cipher
key, performs the initial AddRoundKey transformation, then proceeds
through 10 encryption rounds. The `done` signal is asserted when the
final ciphertext is available at `text_out`. Each round (including the
initial round) consumes one clock cycle; total latency from `ld` to
`done` is 11 clock cycles.

---

**2. AES-128 Algorithm Description**

**2.1 State Matrix**

All internal data is organized as a 4×4 matrix of bytes, called the
*state matrix*:

$$\begin{bmatrix}
s_{00} & s_{01} & s_{02} & s_{03} \\
s_{10} & s_{11} & s_{12} & s_{13} \\
s_{20} & s_{21} & s_{22} & s_{23} \\
s_{30} & s_{31} & s_{32} & s_{33}
\end{bmatrix}$$

- Each element is an 8-bit byte.
- The 128-bit input is mapped to the state matrix in **column-major**
  order: bytes are filled column by column, MSB first within each
  column. That is, `text_in[127:120]` maps to $s_{00}$,
  `text_in[119:112]` maps to $s_{10}$, `text_in[111:104]` maps to
  $s_{20}$, `text_in[103:096]` maps to $s_{30}$, then
  `text_in[095:088]` maps to $s_{01}$, and so on.
- The same column-major ordering applies when the final state matrix is
  read out to `text_out`.

**2.2 Round Transformations**

Each encryption round consists of four transformations applied to the
state matrix:

**2.2.1 SubBytes — Byte Substitution**

Each of the 16 bytes in the state matrix is independently transformed
through a non-linear substitution function (the AES S-box). This is a
byte-in, byte-out mapping:

$$s_{ij} \leftarrow \text{Sbox}(s_{ij}) \quad \text{for } i,j \in \{0,1,2,3\}$$

The S-box transformation is defined mathematically as:
1. Compute the multiplicative inverse of the input byte in GF($2^8$)
   with irreducible polynomial $x^8 + x^4 + x^3 + x + 1$. The inverse
   of 0x00 is defined as 0x00.
2. Apply an affine transformation over GF(2):

$$b_i = a_i \oplus a_{i+4} \oplus a_{i+5} \oplus a_{i+6} \oplus a_{i+7} \oplus c_i$$

where $c$ = 0x63 = {0,1,1,0,0,0,1,1}, and all index arithmetic is
modulo 8.

In hardware, this is typically implemented as a 256×8-bit lookup table
(ROM or LUT-based). The standard AES S-box values are well-known;
refer to FIPS-197 for the complete table.

All 16 bytes are substituted in parallel. The substitution is a pure
combinational function of the input byte — it has no internal state and
requires no clock.

**2.2.2 ShiftRows — Row Shifting**

Each row of the state matrix is cyclically shifted left by a
row-dependent offset:

- Row 0: no shift — $[a, b, c, d] \rightarrow [a, b, c, d]$
- Row 1: left shift by 1 — $[a, b, c, d] \rightarrow [b, c, d, a]$
- Row 2: left shift by 2 — $[a, b, c, d] \rightarrow [c, d, a, b]$
- Row 3: left shift by 3 — $[a, b, c, d] \rightarrow [d, a, b, c]$

This is a pure wiring operation — no logic gates required.

**2.2.3 MixColumns — Column Mixing**

Each column of the state matrix is transformed independently by
multiplying it with a fixed 4×4 matrix over GF($2^8$):

$$\begin{bmatrix}
02 & 03 & 01 & 01 \\
01 & 02 & 03 & 01 \\
01 & 01 & 02 & 03 \\
03 & 01 & 01 & 02
\end{bmatrix} \times
\begin{bmatrix} s_{0j} \\ s_{1j} \\ s_{2j} \\ s_{3j} \end{bmatrix}$$

The multiplication by {02} (denoted `xtime`) is defined as:
$$\text{xtime}(b) = \{b[6:0], 1'b0\} \oplus (8'h1b \cdot b[7])$$

Multiplication by {03} equals xtime(b) ⊕ b. Multiplication by {01} is
the identity.

All four columns are processed in parallel. MixColumns is a pure
combinational function of the column inputs.

**2.2.4 AddRoundKey — Round Key Addition**

Each byte of the state matrix is XORed with the corresponding byte of
the current round key. The round key is also a 128-bit value, mapped to
the state matrix using the same column-major byte ordering. This is a
bitwise XOR operation performed in parallel on all 128 bits.

**2.3 Encryption Sequence**

The complete encryption of one 128-bit block proceeds as follows:

1. **Initial Round Key Addition**: XOR the input plaintext with the
   initial round key (Round Key 0). This is the first use of
   AddRoundKey, performed when `ld` is asserted.

2. **Rounds 1 through 9** (the "full rounds"): Apply all four
   transformations in order — SubBytes → ShiftRows → MixColumns →
   AddRoundKey.

3. **Round 10** (the "final round"): Apply SubBytes → ShiftRows →
   AddRoundKey. **MixColumns is omitted in the final round.**

4. After Round 10, the state matrix contains the ciphertext. It is read
   out in column-major order to the `text_out` port, and `done` is
   asserted.

The system processes one round per clock cycle. Since there are 10
rounds plus the initial round key addition, the total latency is 11
clock cycles from `ld` to `done`.

---

**3. Functional Decomposition**

The system can be understood as a composition of several cooperating
functions. The following sections describe each function's purpose,
algorithm, interface needs, and nature (combinational vs. sequential).

**3.1 Byte Substitution Function (S-box)**

*Nature*: Pure combinational. No clock, no state.

*Purpose*: Maps an 8-bit input byte to an 8-bit output byte according to
the AES S-box transformation (see Section 2.2.1).

*Usage contexts*: This function is required in **two distinct places**
within the system:
- **In the cipher datapath** (SubBytes step): 16 bytes of the state
  matrix must be substituted in parallel during each round.
- **In the key expansion** (SubWord step, see Section 3.2): 4 bytes of a
  key word must be substituted in parallel during each round of key
  generation.

Since the same substitution table is used in both contexts, the S-box
function should be defined once and instantiated wherever a byte
substitution is needed (20 total instances: 16 for the cipher datapath +
4 for key expansion).

*Implementation*: 256×8-bit lookup table (ROM, or combinational
case/LUT). The mathematical computation (GF inverse + affine transform)
may also be used if preferred by the target technology.

*Input/output*: 8-bit input byte → 8-bit output byte. Propagation delay
is combinational.

**3.2 Key Expansion Function**

*Nature*: Sequential. Contains internal state registers and updates on
the clock edge.

*Purpose*: Expands the 128-bit cipher key into a sequence of 11 round
keys (each 128 bits wide). The key expansion runs in lockstep with the
cipher rounds: the initial round key is available immediately upon key
load, and a new round key is produced each subsequent clock cycle.

*Interface needs*:
- A clock signal for synchronous operation.
- A key-load strobe signal that indicates when a new cipher key should
  be loaded.
- The 128-bit cipher key input.
- Four 32-bit round key word outputs, which together form the 128-bit
  round key for the current round.

*Internal state*: Four 32-bit registers (`W0`, `W1`, `W2`, `W3`) holding
the current round key words. These are output directly.

*Algorithm* — The AES-128 key expansion algorithm:

The 128-bit cipher key is divided into four 32-bit words:
- W[0] ← key[127:96]
- W[1] ← key[095:64]
- W[2] ← key[063:32]
- W[3] ← key[031:00]

These four words form Round Key 0 (the initial round key).

For subsequent rounds, new words W[4] through W[43] are generated
iteratively. In a hardware implementation, the four registers are
updated in parallel once per clock cycle, each advancing by 4 positions
in the word sequence per cycle.

Let `g(word)` be a transformation function defined as:
$$\text{g}(w) = \text{SubWord}(\text{RotWord}(w)) \oplus \text{Rcon}$$

where:
- **RotWord**: Performs a cyclic left shift of one byte on the 32-bit
  input: $[a_0, a_1, a_2, a_3] \rightarrow [a_1, a_2, a_3, a_0]$.
- **SubWord**: Applies the S-box substitution (Section 3.1) to each of
  the four bytes independently. This requires four parallel S-box
  instantiations.
- **Rcon**: The 32-bit round constant for the current expansion round
  (see Section 3.3). Only the most significant byte is non-zero; the
  lower 24 bits are always zero.

The parallel register update equations for each clock cycle (when not
loading a new key) are:

$$\begin{aligned}
W_0 &\leftarrow W_0 \oplus g(W_3) \\
W_1 &\leftarrow W_1 \oplus W_0 \oplus g(W_3) \\
W_2 &\leftarrow W_2 \oplus W_1 \oplus W_0 \oplus g(W_3) \\
W_3 &\leftarrow W_3 \oplus W_2 \oplus W_1 \oplus W_0 \oplus g(W_3)
\end{aligned}$$

where all $W_i$ on the right-hand side refer to the *current* (old)
register values. These equations produce one full 128-bit round key per
cycle.

*Key loading*: When the key-load strobe is asserted, the four internal
registers are loaded directly from the 128-bit key input (split into
four 32-bit words as described above), overriding the expansion
equations. The round constant generator is also reset.

*Interaction with cipher core*: The four 32-bit word outputs of the key
expansion function are connected to the cipher core's AddRoundKey stage.
Both the initial round key addition and each round's AddRoundKey consume
these outputs. The key expansion advances one round per clock cycle in
synchronization with the cipher round counter.

**3.3 Round Constant Generation**

*Nature*: Sequential. Contains a counter and updates on the clock edge.

*Purpose*: Generates the sequence of 32-bit round constants RC[0]
through RC[9] used in the key expansion's `g` function. Each round
constant has its round-dependent value in the most significant byte;
the lower 24 bits are always zero.

*Interface needs*:
- A clock signal.
- A reset/load signal that restarts the sequence from the beginning.
- A 32-bit round constant output.

*Internal state*: A 4-bit counter (`rcnt`) that tracks which round
constant to produce. It increments every clock cycle (0 → 1 → 2 → … →
9) and is reset to 0 when the key-load signal is asserted.

*Algorithm* — The round constants RC[i] are generated by successive
multiplication by {02} in GF($2^8$), starting from RC[0] = 0x01:

| rcnt | Output (hex) | Derivation |
| --- | --- | --- |
| 0 | `32'h01_00_00_00` | RC[0] = 0x01 |
| 1 | `32'h02_00_00_00` | RC[0] × {02} |
| 2 | `32'h04_00_00_00` | RC[1] × {02} |
| 3 | `32'h08_00_00_00` | RC[2] × {02} |
| 4 | `32'h10_00_00_00` | RC[3] × {02} |
| 5 | `32'h20_00_00_00` | RC[4] × {02} |
| 6 | `32'h40_00_00_00` | RC[5] × {02} |
| 7 | `32'h80_00_00_00` | RC[6] × {02} |
| 8 | `32'h1B_00_00_00` | RC[7] × {02}, reduced mod $m(x)$ |
| 9 | `32'h36_00_00_00` | RC[8] × {02}, reduced mod $m(x)$ |

For rcnt > 9, the output should be `32'h00_00_00_00`.

*Design note*: Since the round constant sequence is short (only 10
values), it can be implemented as a simple lookup table indexed by the
counter, or as a linear-feedback shift register performing the xtime
operation. The counter and output register must be reset when a new key
is loaded.

**3.4 MixColumns Computation**

*Nature*: Pure combinational function. No clock, no state.

*Purpose*: Performs the MixColumns matrix multiplication on one column
(four bytes) of the state matrix (see Section 2.2.3).

*Input*: Four 8-bit bytes representing one column of the state matrix
($s_{0j}, s_{1j}, s_{2j}, s_{3j}$).

*Output*: Four 8-bit bytes representing the transformed column.

The computation uses a helper function `xtime` that multiplies a byte by
{02} in GF($2^8$):
```
xtime(b) = {b[6:0], 1'b0} XOR (8'h1B if b[7] else 8'h00)
```

Using xtime, the MixColumns output for column $j$ is:
$$\begin{aligned}
out_0 &= \text{xtime}(s_0) \oplus \text{xtime}(s_1) \oplus s_1 \oplus s_2 \oplus s_3 \\
out_1 &= s_0 \oplus \text{xtime}(s_1) \oplus \text{xtime}(s_2) \oplus s_2 \oplus s_3 \\
out_2 &= s_0 \oplus s_1 \oplus \text{xtime}(s_2) \oplus \text{xtime}(s_3) \oplus s_3 \\
out_3 &= \text{xtime}(s_0) \oplus s_0 \oplus s_1 \oplus s_2 \oplus \text{xtime}(s_3)
\end{aligned}$$

*Usage*: Four instances operate in parallel, one per column, during
rounds 1–9. During the final round (Round 10), MixColumns is bypassed.

Since xtime and MixColumns are used only within the cipher datapath and
are relatively simple combinational expressions, they may be implemented
as local functions or inline combinational logic rather than as
separately instantiated blocks.

**3.5 Cipher Round Control Function**

*Nature*: Sequential. Contains the main control state machine and the
state matrix registers.

*Purpose*: Orchestrates the encryption process by controlling the
sequence of transformations applied to the state matrix and managing
the interaction with the key expansion function.

**3.5.1 State Matrix Registers**

The core internal state consists of 16 byte-wide registers organized as
a 4×4 matrix ($sa_{ij}$ for $i,j \in \{0,1,2,3\}$). These registers
hold the current state matrix and are updated on every clock rising
edge.

Additionally, a 128-bit data buffer register (`text_in_r`) is required to
hold the input plaintext value during the initial round key addition,
ensuring the input remains stable even if `text_in` changes externally
after `ld` is deasserted.

**3.5.2 Control State Machine**

The control logic implements a finite state machine with the following
states:

| State | Description |
| --- | --- |
| IDLE | Reset state. Waits for `ld=1`. State matrix holds previous result or reset value. `done` is deasserted. |
| INIT_ROUND | Loads input plaintext into the buffer register. Performs the initial AddRoundKey (plaintext XOR initial round key) and stores the result in the state matrix registers. Sets the round counter to 11 (0xB). |
| ROUND_OP | Executes one standard encryption round: SubBytes → ShiftRows → MixColumns → AddRoundKey. This state is active for rounds 1 through 9. The round counter decrements each cycle. |
| FINAL_ROUND | Executes the final round: SubBytes → ShiftRows → AddRoundKey (no MixColumns). The result is the ciphertext. |
| DONE | Asserts `done=1`. The ciphertext is presented at `text_out`. The state machine returns to IDLE (or remains in DONE until the next `ld`). |

*State transitions*:
- IDLE → INIT_ROUND: when `ld=1`
- INIT_ROUND → ROUND_OP: automatically on next clock cycle
- ROUND_OP → ROUND_OP: while round counter > 1 (i.e., rounds 1–8)
- ROUND_OP → FINAL_ROUND: when round counter = 1 (i.e., after round 9 completes)
- FINAL_ROUND → DONE: automatically on next clock cycle
- DONE → IDLE: when `ld=0` (or on next clock cycle)

**3.5.3 Round Counter**

A 4-bit down-counter tracks the encryption progress:
- Reset to 0 when `rst` is deasserted.
- Set to 11 (0xB) when `ld` is asserted (representing: 10 rounds +
  initial round key addition still to be processed).
- Decrements by 1 each clock cycle while non-zero.
- When the counter reaches 0, it stays at 0 (does not wrap).

The `done` output is asserted when the upper 3 bits of the counter are
zero and the LSB is 1 and `ld` is not currently asserted — this
corresponds to the cycle after the final round completes. Specifically:
$$\text{done} = \overline{dcnt[3]} \cdot \overline{dcnt[2]} \cdot \overline{dcnt[1]} \cdot dcnt[0] \cdot \overline{ld}$$

**3.5.4 Round Data Flow**

Within the ROUND_OP state, data flows through the following stages each
clock cycle:

1. **SubBytes**: Each of the 16 state matrix register bytes feeds into
   an S-box instance. The 16 substituted bytes are produced
   combinationally.

2. **ShiftRows**: The substituted bytes are wired with the appropriate
   row-dependent rotation to produce the shifted bytes. This is purely
   wiring.

3. **MixColumns**: Each column of shifted bytes feeds into a MixColumns
   computation block. Four columns produce four 32-bit mixed results.

4. **AddRoundKey**: Each byte of the mixed result is XORed with the
   corresponding byte from the current round key words produced by the
   key expansion function. The byte-to-word mapping follows the
   column-major ordering:
   - Column 0 bytes are XORed with portions of round key word 0
   - Column 1 bytes with word 1
   - Column 2 bytes with word 2
   - Column 3 bytes with word 3

5. The XOR results become the next-state values for the state matrix
   registers, to be captured on the next clock edge.

In the FINAL_ROUND state, the MixColumns stage is bypassed — the
ShiftRows output feeds directly into AddRoundKey.

During the INIT_ROUND state, the state matrix registers are loaded with
the XOR of the buffered input plaintext and the initial round key (the
first set of words from the key expansion function).

**3.5.5 Output Generation**

After the final round completes, the ciphertext is formed by XORing the
ShiftRows output (not the MixColumns output, since MixColumns is
skipped in the final round) with the final round key. The result is
registered and driven onto `text_out` in column-major byte order:

- `text_out[127:120]` ← $sa_{00}$ XOR round_key_word_0[31:24]
- `text_out[119:112]` ← $sa_{10}$ XOR round_key_word_0[23:16]
- `text_out[111:104]` ← $sa_{20}$ XOR round_key_word_0[15:08]
- `text_out[103:096]` ← $sa_{30}$ XOR round_key_word_0[07:00]
- … and similarly for columns 1, 2, 3.

---

**4. System Data Flow Diagram**

The following describes the data flow through the system. Each
indentation level represents a stage in the round pipeline.

```
                    ┌──────────────┐
   key ────────────►│              │
                    │ Key Expansion│────► round_key_words[127:0]
   ld  ────────────►│              │
                    └──────────────┘
                            │
   text_in ─────────────────┼──────────────────────────────┐
                            │                              │
                            ▼                              ▼
                    ┌──────────────┐              ┌────────────────┐
                    │    INITIAL   │              │                │
                    │  AddRoundKey │              │   State Matrix │
                    │  (ld cycle)  │──────────────►│   Registers    │
                    └──────────────┘              │  (16 × 8-bit)  │
                                                  │                │
                                                  └───────┬────────┘
                                                          │
                                    ┌─────────────────────┘
                                    ▼
                            ┌──────────────┐
                            │   SubBytes   │◄──── 16 × S-box (combinational)
                            │  (16 bytes)  │
                            └──────┬───────┘
                                   │
                                   ▼
                            ┌──────────────┐
                            │  ShiftRows   │ (wiring)
                            │  (4 rows)    │
                            └──────┬───────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │ (rounds 1-9) │              │ (round 10)
                    ▼              │              ▼
            ┌──────────────┐      │      ┌──────────────┐
            │  MixColumns  │      │      │   (bypass)   │
            │  (4 columns) │      │      └──────┬───────┘
            └──────┬───────┘      │             │
                   │              │             │
                   └──────────────┼─────────────┘
                                  │
                                  ▼
                          ┌──────────────┐
                          │ AddRoundKey  │◄──── round_key_words
                          │ (128-bit XOR)│
                          └──────┬───────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │ State Matrix  │ (feedback for next round,
                         │ Registers     │  or final output to text_out)
                         └───────────────┘
```

**Key data dependencies**:
- The key expansion function receives `ld` and `key` and produces round
  key words. It advances one round per clock, synchronized with the
  cipher round counter.
- The cipher datapath reads round key words during both the INIT_ROUND
  (initial AddRoundKey) and each subsequent round's AddRoundKey.
- The S-box function is used by both the cipher datapath (SubBytes, 16
  parallel instances) and the key expansion (SubWord, 4 parallel
  instances).
- The round constant sequence is generated within the key expansion
  function and is reset when a new key is loaded.

---

**5. Timing and Sequencing**

**5.1 Clock Cycle Allocation**

| Cycle | State | Action |
| --- | --- | --- |
| 0 | IDLE | System idle, waiting for `ld` |
| 1 | INIT_ROUND | `ld=1` detected. Load plaintext buffer, load key, perform initial AddRoundKey. Round counter ← 11. |
| 2–10 | ROUND_OP | Each cycle: SubBytes → ShiftRows → MixColumns → AddRoundKey. Round counter decrements 11→10→…→2. 9 cycles total (rounds 1–9). |
| 11 | FINAL_ROUND | SubBytes → ShiftRows → AddRoundKey (no MixColumns). Round counter = 1 → 0. |
| 12 | DONE | `done=1`, ciphertext valid at `text_out`. |

**5.2 Synchronization Requirements**

- All register updates occur on the rising edge of `clk`.
- The key expansion function and the cipher datapath advance in
  lockstep: both use the same `ld` signal to initiate a new encryption,
  and both consume/produce one round of data per clock cycle.
- The round counter in the cipher control must stay synchronized with
  the round constant counter in the key expansion, as they are both
  reset by `ld` and advance on each clock cycle.

**5.3 Critical Path**

The critical combinational path in each round includes:
1. S-box lookup (ROM/LUT access or GF compute)
2. ShiftRows wiring (negligible delay)
3. MixColumns computation (multiple levels of XOR + xtime)
4. AddRoundKey XOR

If timing closure is challenging, pipeline registers may be inserted
between transformation stages. However, the baseline design processes
one full round per cycle without internal pipelining.

---

**6. Register Summary**

The system requires the following register resources:

| **Register** | **Width** | **Reset Value** | **Purpose** |
| --- | --- | --- | --- |
| State matrix registers ($sa_{ij}$) | 16 × 8 bits | 0 | Holds the current state matrix during encryption |
| Input data buffer | 128 bits | 0 | Captures and holds `text_in` when `ld=1` |
| Round counter (`dcnt`) | 4 bits | 0 | Down-counter tracking encryption progress (11 → 0) |
| Load flag (`ld_r`) | 1 bit | 0 | Delayed copy of `ld` for control timing |
| Done flag | 1 bit | 0 | Output register for the `done` signal |
| Output register (`text_out`) | 128 bits | 0 | Holds the final ciphertext |
| Key expansion word registers | 4 × 32 bits | 0 | Hold the current round key words |
| Round constant counter | 4 bits | 0 | Tracks round constant sequence position |
| Round constant output register | 32 bits | `0x01000000` | Registered output of the round constant value |

---

**7. Corner Cases**

**7.1 Reset Behavior**
- After `rst` is asserted (low), all registers must return to their
  reset values. The state machine enters the IDLE state.
- `done` must be deasserted (0).
- The key expansion registers must be cleared.

**7.2 Back-to-Back Encryption**
- When a new `ld` is asserted while the system is in or after the DONE
  state, a new encryption begins immediately on the next cycle.
- The key expansion is reloaded, the round counter is reset to 11, and
  the new plaintext is captured.
- Ensure that `key` and `text_in` are stable when `ld` is asserted.

**7.3 Load During Active Encryption**
- If `ld` is asserted while an encryption is in progress, the current
  encryption is aborted and a new one begins. The round counter is reset
  to 11, and the key expansion is reloaded.

**7.4 Done Signal Timing**
- `done` is asserted exactly one cycle after the final round completes
  and remains asserted until the next `ld` or until the state machine
  returns to IDLE.
- The ciphertext at `text_out` is valid during the cycle when `done=1`
  and remains valid until overwritten by the next encryption.

**7.5 Edge Case Input Values**
- All-zero plaintext with all-zero key: the system must produce the
  correct AES-128 ciphertext.
- All-ones plaintext with all-ones key: same requirement.
- The S-box must correctly handle input 0x00 → 0x63 and input 0xFF →
  0x16.

---

**8. Constraints**

**8.1 Timing Constraints**
- Single-clock-domain synchronous design. All registers update on the
  rising edge of `clk`.
- One round of encryption (including SubBytes, ShiftRows, MixColumns,
  AddRoundKey, and register setup) must complete within one clock
  period.
- Key expansion and round constant generation must also complete within
  the same clock period.

**8.2 Resource Constraints**
- 20 instances of the S-box function are required: 16 for the cipher
  datapath SubBytes, plus 4 for the key expansion SubWord.
- The S-box implementation requires 256×8 bits of storage (if ROM-based)
  or equivalent LUT resources.
- 16 × 8-bit state matrix registers.
- 4 × 32-bit key expansion registers.
- 4-bit round counter and associated control logic.
- 4-bit round constant counter and 32-bit output register.

**8.3 Design Partitioning Guidance**

When implementing this specification, consider the following natural
boundaries between functional blocks:

- Functions that are **purely combinational** and **used in multiple
  contexts** (like the S-box) are natural candidates for separate,
  reusable implementation units.
- Functions that maintain **their own internal state** and operate
  **synchronously with the clock** (like key expansion and cipher
  control) are natural candidates for separate sequential blocks.
- Functions that are **simple combinational expressions used in a single
  context** (like xtime and MixColumns) may be implemented as local
  functions within the block that uses them.
- The **interface between the cipher datapath and key expansion**
  consists of: the shared `ld` (key load / encryption start) signal, and
  the four 32-bit round key words flowing from key expansion to the
  AddRoundKey stage.
- The **interface between the cipher datapath and the S-box function**
  is: 16 parallel 8-bit input bytes (the current state matrix) and 16
  parallel 8-bit output bytes (the substituted values).
- The **interface between key expansion and the S-box function** is: 4
  parallel 8-bit input bytes (the bytes of the rotated word) and 4
  parallel 8-bit output bytes (the substituted word bytes).

---

**9. Verification Considerations**

- Verify against known AES-128 test vectors from FIPS-197.
- Key test: the all-zero key and all-zero plaintext case.
- Key test: verify SubBytes, ShiftRows, MixColumns, and AddRoundKey
  independently before full integration.
- Verify the `done` signal timing: must be asserted exactly once per
  encryption, at the correct cycle.
- Verify back-to-back encryption: start a new encryption immediately
  after `done`.
- Verify that reset correctly clears all state and returns to IDLE.

---

**10. References**

- FIPS PUB 197: Advanced Encryption Standard (AES), November 2001.
- AES key expansion algorithm as defined in FIPS-197, Section 5.2.
- The irreducible polynomial for GF($2^8$) is $x^8 + x^4 + x^3 + x + 1$
  (0x11B).
