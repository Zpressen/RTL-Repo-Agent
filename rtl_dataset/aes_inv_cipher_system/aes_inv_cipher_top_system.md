# AES-128 Decryption System Design Specification

This specification describes a complete AES-128 decryption system, covering the top-level decryption control, key expansion, S-box, inverse S-box, and round constant generation.

---

**aes_inv_cipher_top Design Specification**

**1. Introduction**

The aes_inv_cipher_top module is the core control module of the AES
decryption system, responsible for coordinating and controlling the
entire decryption process. This module implements all inverse round
transformations of the AES decryption algorithm, including InvSubBytes,
InvShiftRows, InvMixColumns, and AddRoundKey.

**2. Block Diagram**

![](./figures/aes_inv_cipher_topmod.png)


**3. Interface**

| **Signal Name** | **Direction** | **Width** | **Description** |
| --- | --- | --- | --- |
| clk | input | 1 | Clock signal |
| rst | input | 1 | Reset signal |
| kld | input | 1 | Key load enable |
| ld | input | 1 | Load enable |
| done | output | 1 | Decryption complete |
| key | input | 128 | Input key |
| text_in | input | 128 | Input ciphertext |
| text_out | output | 128 | Output plaintext |

**4.Registers**

| **Register Name** | **Width** | **Type** | **Reset Value** | **Description** |
| --- | --- | --- | --- | --- |
| text_in_r | 128 | Data Buffer | 0 | Temporary storage register for input ciphertext during decryption process |
| sa[0:3][0:3] | 8 | State Matrix | 0 | 4×4 state matrix registers for storing and processing intermediate decryption results, arranged in column-major order |
| dcnt | 4 | Control | 0 | Round counter register for tracking decryption progress |
| kb[10:0] | 128 | Key Buffer | 0 | Key schedule buffer storing the round keys in reverse order |
| kcnt | 4 | Control | 0xA | Key buffer counter for key schedule loading |
| ld_r | 1 | Control | 0 | Load operation flag register |
| text_out | 128 | Output Buffer | 0 | Output register storing the final plaintext result |

**6. Operation Principle**

**6.1 Basic Principle**

The AES decryption algorithm is based on the state matrix concept,
performing 10 rounds of inverse transformations on the 128-bit input
ciphertext. Each round includes:

1.  InvShiftRows - Cyclic right shift operation

2.  InvSubBytes - Nonlinear inverse byte substitution

3.  AddRoundKey - XOR with the round key

4.  InvMixColumns - Inverse column mixing operation (except the final
    round)

Key features:

1.  All operations are based on the state matrix

2.  Different round keys are used in each round

3.  The final round does not include the InvMixColumns operation

4.  The order of round key usage is reversed compared to encryption

**6.2 Mathematical Principle**

1\. State Matrix Structure and Data Mapping:

-   State matrix arrangement:

> $$\begin{matrix}
> sa00 & sa01 & sa02 & sa03 \\
> sa10 & sa11 & sa12 & sa13 \\
> sa20 & sa21 & sa22 & sa23 \\
> sa30 & sa31 & sa32 & sa33
> \end{matrix}$$

-   Input data mapping (128-bit in column-major order):

    -   Start from text_in\[127:120\], map to the state matrix from top
        to bottom, left to right.

2\. Inverse Round Transformations

a\) **InvShiftRows**: Cyclic right shift

Row 0: \[a b c d\] → \[a b c d\] // No shift

Row 1: \[a b c d\] → \[d a b c\] // Right shift by 3 bytes

Row 2: \[a b c d\] → \[c d a b\] // Right shift by 2 bytes

Row 3: \[a b c d\] → \[b c d a\] // Right shift by 1 byte

b\) **InvSubBytes**: - Nonlinear transformation using the inverse
S-box - 16 bytes processed in parallel - Involves multiplicative inverse
operations in GF($2^{8}$)

c\) **InvMixColumns**:

Matrix representation:

$$\begin{bmatrix}
0E & 0B & 0D & 09 \\
09 & 0E & 0B & 0D \\
0D & 09 & 0E & 0B \\
0B & 0D & 09 & 0E
\end{bmatrix} \times \begin{bmatrix}
s0 \\
s1 \\
s2 \\
s3
\end{bmatrix} = \begin{bmatrix}
out0 \\
out1 \\
out2 \\
out3
\end{bmatrix}$$

Multiplication coefficients:

\- 0E: 14

\- 0B: 11

\- 0D: 13

\- 09: 9

All operations are performed in the GF($2^{8}$) domain, using
pre-computed polynomial multiplications.

d\) **AddRoundKey**:

\- Byte-wise XOR with the round key

\- Round keys are applied in reverse order

\- Each byte is XOR\'ed with the corresponding round key byte

**7. Implementation Details**

**7.1 State Transition Diagram**

![](./figures/aes_inv_cipher_topstate.png)


a)  IDLE: This is the initial reset state, waiting for the key load
    signal (kld) or data load signal (ld) to start the decryption
    process.

b)  KeyLoad State: Enters the key loading state, preparing to execute
    the key expansion operation.

c)  KeyExpansion State: Enters the key expansion state, executing the
    expansion algorithm to generate the required round keys.When the key
    expansion is complete (kcnt==0), it transitions to the KeyStored
    state.

d)  KeyStored State: The key expansion is complete, and the round keys
    are ready.Upon receiving the data load signal (ld), it transitions
    to the InitialRound state to start the decryption.

e)  InitialRound State: Performs the initial round\'s inverse round key
    addition operation. The round counter (dcnt) is incremented, and it
    transitions to the StandardRound state.

f)  StandardRound State: Executes the standard round\'s inverse
    transformations, including InvShiftRows, InvSubBytes, AddRoundKey,
    and InvMixColumns. The round counter continues to increment.

g)  FinalRound State: Performs the final round\'s inverse operation,
    excluding the InvMixColumns transformation.When the round counter
    reaches 11, it transitions to the Done state.

h)  Done State: The decryption operation is complete, and the final
    plaintext result is output.

It transitions back to the Idle state, waiting for the next decryption
operation.

**7.2 Round Counter and Control Logic**

1.  Round Counter State Transition:

-   Reset state: Counter reset to 0

-   Load state: Counter set to 1

-   Run state: Increment each cycle

-   Finish state: Count reaches 11 and not in load state

2.  Completion Signal Control:

-   Set when count reaches 11 and not in load state

-   Cleared on reset or new data load

-   Indicates the decryption operation is complete

3.  Run Control (go signal):

-   Cleared on reset

-   Set on data load

-   Cleared on completion

-   Controls the start and stop of the decryption process

**7.3 Initial Data Loading**

1.  Input Data Mapping Process:

-   Buffered in the text_in_r register

-   Mapped to the state matrix in column-major order

-   From sa33 to sa03, then shift left

-   Each data byte XOR\'ed with the corresponding round key byte

2.  State Selection Logic:

-   Load state (ld_r=1): Perform data load and initial round key
    addition

-   Run state (ld_r=0): Use the results of the round transformations

**7.4 Round Transformation Implementation**

1.  InvShiftRows Operation:

-   Row 0: Unchanged

-   Row 1: Cyclic right shift by 3 bytes, sa13-\>sa10, sa10-\>sa11,
    sa11-\>sa12, sa12-\>sa13

-   Row 2: Cyclic right shift by 2 bytes, sa22-\>sa20, sa20-\>sa21,
    sa21-\>sa22, sa23-\>sa21

-   Row 3: Cyclic right shift by 1 byte, sa31-\>sa30, sa32-\>sa31,
    sa33-\>sa32, sa30-\>sa33

2.  InvSubBytes:



-   The replacement results are used for the subsequent round key
    addition

3.  AddRoundKey Operation:

-   XOR each state matrix byte with the corresponding round key byte

-   The result is assigned to the sa_ark signal

-   The XOR result is used for the InvMixColumns operation

4.  InvMixColumns:

-   Processed independently for each column

-   Uses pre-computed GF(2\^8) multiplication functions (pmul_e/b/d/9)

-   Generates the sa_next signal as the input for the next round

**7.5 Key Expansion Buffer**

1.  Buffer Control Logic:

-   Uses the kcnt (4-bit counter) to track the storage progress

-   Initial value is set to 10, reaches 0 when the storage is complete

-   The kb_ld signal controls the storage process

2.  Key Storage Process:

-   kb\[10\] stores the initial round key

-   kb\[9\] to kb\[1\] store the intermediate round keys

-   kb\[0\] stores the last round key


3.  Key Retrieval Mechanism:

-   Selects the current round key based on the dcnt (round counter)

-   Outputs to w3, w2, w1, w0 for the round transformations

-   Updated every clock cycle

**7.6 Final Output Generation**

1.  Output Mapping Process:

-   Maps the round key addition result (sa_ark) of the last round to
    text_out

-   In column-major order, opposite to the input mapping

-   From sa00 to sa30, then shift right

2.  Output Timing Control:

-   Synchronized with the clock rising edge

-   Completion signal indicates the valid output

-   Holds the output until the next load

3.  Output Data Organization:

-   The highest byte (text_out\[127:120\]) comes from sa00

-   The lowest byte (text_out\[7:0\]) comes from sa33

-   Bytes are arranged in column-major order


**9. Corner Cases**

1.  Timing Related:

-   Key schedule loading completion

-   Round operation synchronization

-   Final round detection

2.  Key Schedule:

-   Key buffer loading sequence

-   Key availability timing

-   Buffer overflow prevention

3.  Data Flow:

-   State matrix initialization

-   Round transformation sequencing

-   Output generation timing

**10. Constraints**

> 1\. Timing Constraints:

-   Key schedule must be loaded before data processing

-   Register updates on clock rising edge

-   Critical path includes inverse S-box and inverse column mixing

> 2\. Resource Constraints:


-   11 x 128-bit key buffer registers

-   4×4 state matrix register array

-   Complex multiplication functions in GF(2⁸)

> 3\. Control Constraints:

-   Proper key schedule loading sequence

-   Accurate round counting

-   Correct transformation ordering

---

**aes_key_expand_128 Design Specification**

**1. Introduction**

The aes_key_expand_128 module is a crucial component
in the AES encryption algorithm, responsible for expanding a 128-bit
initial key into round keys for multiple encryption rounds. This
document describes the design principles, implementation methods, and
interface specifications of this module.

**2. Block Diagram**

![](./figures/aes_key_expand_128mod.jpg)


**3. Interface**

|**Signal** |     **Direction**   | **Width**  | **Description Name**    |                                  
|---|---|---|---|
|clk  |          input    |        1      |     Clock signal|
|kld  |          input    |        1      |     Key load enable|
|key  |          input    |        128    |     Input initial key|
|wo_0  |         output   |        32     |     Output round key word 0|
|wo_1 |          output   |        32     |     Output round key word 1|
|wo_2  |         output   |        32     |     Output round key word 2|
|wo_3  |         output   |        32     |     Output round key word 3|
  

**4. Operation Principle**

**4.1 Basic Principle**

AES-128 key expansion transforms a 128-bit initial key into 11 sets of
128-bit round keys (including the initial round key). Each round key
consists of four 32-bit words. The expansion process is iterative,
generating one new round key at a time.

**4.2 Mathematical Derivation**

**The key expansion process involves the following operations:**

1.  Word Rotation (RotWord)

-   Performs a cyclic left shift on input word

-   \[a0,a1,a2,a3\] → \[a1,a2,a3,a0\]

2.  S-box Substitution (SubWord)

-   Applies S-box transformation to each byte

-   Uses the same S-box as encryption process

3.  Round Constant XOR (Rcon)

-   XOR operation with round constant

-   Different constant value for each round

4.  Key Expansion Algorithm

-   W\[i\] = W\[i-4\]⊕T(W\[i-1\]), when i mod 4 = 0

-   W\[i\] = W\[i-4\]⊕W\[i-1\], otherwise where T(W) =
    SubWord(RotWord(W))⊕Rcon

**5. Implementation Details**

**5.1 State Transition Diagram**

![](./figures/aes_key_expand_128state.png)

**5.2 Key Loading Operation**

1.  When kld signal is active:

-   128-bit input key is divided into four 32-bit words

-   key\[127:96\] loads into first register

-   key\[95:64\] loads into second register

-   key\[63:32\] loads into third register

-   key\[31:0\] loads into fourth register

2.  Loading process:

-   Synchronous loading at clock rising edge

-   All registers update simultaneously

-   Immediately output to wo_0 to wo_3 ports after loading

**5.3 Key Expansion Operation**

1.  When kld signal is inactive, perform expansion:

-   Take the last word (fourth register value)

-   Perform byte reordering and S-box transformation

-   XOR with current round constant

2.  New round key generation sequence:

-   First word: XOR with previous round word and transformation result

-   Second word: XOR with previous round word, current round first word,
    and transformation result

-   Third word: XOR with previous round word, current round first two
    words, and transformation result

-   Fourth word: XOR with previous round word, current round first three
    words, and transformation result

**5.4 S-box Transformation**

1.  S-box transformation process:

-   Perform parallel S-box lookup on reordered bytes

-   First byte transformation result stores in highest 8 bits

-   Second byte transformation result stores in second highest 8 bits

-   Third byte transformation result stores in second lowest 8 bits

-   Fourth byte transformation result stores in lowest 8 bits

**5.5 Round Constant Operation**

1.  Round constant generation:

-   Starts from initial value, updates automatically each round

-   Only highest byte is valid, other bytes are 0

-   XORs with transformation result during each key expansion

2.  Round constant update:

-   Reset during initial key loading

-   Left shift each round, XOR with specific polynomial on overflow

**7. Corner Cases**

1.  Key loading timing:

-   kld signal rising edge must synchronize with clk

-   Ensure initial key remains stable when kld is active

2.  Special value handling:

-   All-zero initial key case

-   All-one initial key case

**8. Constraints**

1\. Timing constraints:

-   All registers update on clk rising edge

-   Combinational logic path must meet timing requirements

2\. Resource constraints:

-   Requires four 32-bit registers



---

**aes_sbox Design Specification**

**1. Introduction**

The aes_sbox module is a crucial component in the AES
encryption algorithm, responsible for performing non-linear byte
substitution operations. This document describes the design principles,
implementation methods, and interface specifications of the S-box.

**2. Block Diagram**

![](./figures/aes_sboxmod.jpg)

**3. Interface**

| **Signal Name** | **Direction** | **Width** | **Description** |
| ---             | ---           | ---       | ---             |
| a | input | 8 | Input byte |
| b | output | 8 | Substituted byte |

**4. Operation Principle**

**4.1 Basic Principle**

The S-box transformation is completed in two steps:

1.  Computing the multiplicative inverse in Galois Field GF($2^{8}$)

2.  Applying an affine transformation

Apart from the mathematical calculations, we can look up in the forward
S-box table in actual realization.

In this design, we uses a lookup table to store all the S-box outputs
values for their corresponding inputs.

**4.2 Mathematical Derivation**

**4.2.1 Multiplicative Inverse in GF(**$\mathbf{2}^{\mathbf{8}}$**)**

1.  GF($2^{8}$) Definition:

-   Irreducible polynomial:$\ x^{8} + x^{4} + x^{3} + x + 1$

-   Field elements representation:
    $b_{7}x^{7} + b_{6}x^{6} + b_{5}x^{5} + b_{4}x^{4} + b_{3}x^{3} + b_{2}x^{2} + b_{1}x + b_{0}$

2.  Inverse Calculation:

-   For non-zero element a, its inverse $a^{- 1}$ satisfies: a ×
    $a^{- 1}$ ≡ 1 (mod$x^{8} + x^{4} + x^{3} + x + 1$)

-   Special case: inverse of 0x00 is defined as 0x00

**4.2.2 Affine Transformation**

After computing the multiplicative inverse, an affine transformation is
applied:

$$b_{i}\  = \ a_{i} \oplus a_{i + 4} \oplus a_{i + 5} \oplus a_{i + 6} \oplus a_{i + 7} \oplus c_{i}$$

where:

-   $b_{i}\ $is the i-th bit of the result.

-   c = 0x63 is the transformation constant

-   All index additions are performed modulo 8

For example, for i = 0:

$$b_{0}\  = \ a_{0} \oplus a_{4} \oplus a_{5} \oplus a_{6} \oplus a_{7} \oplus c_{0}$$

For i = 7:

$$b_{7}\  = \ a_{7} \oplus a_{3} \oplus a_{4} \oplus a_{5} \oplus a_{6} \oplus c_{7}$$

This can be represented in matrix form as:

![](./figures/sboxmatrix.jpg)

where c = 0x63 =
$\{c_{7},c_{6},c_{5},c_{4},c_{3},c_{2},c_{1},c_{0}\}$=
{0,1,1,0,0,0,1,1}

**5. Corner Cases**

1.  Zero Value Handling:

Input 0x00 must correctly output 0x63.

2.  All-Ones Handling:

Input 0xFF must correctly output 0x16.

**6. Constraints**

1.  Timing Constraints:

-   Combinational logic implementation, no clock required.

-   Output updates immediately after input changes.

2.  Resource Constraints:

-   ROM implementation: requires 256×8 bits storage.

-   Implementation method can be selected based on target device
    characteristics (ROM/LUT).

3.  Usage Guidelines:

-   Pure combinational logic module, consider setup and hold times.

-   Pipeline registers can be added externally if needed.

---

**aes_rcon Design Specification**

**1. Introduction**

The aes_rcon module generates constant values used in the
AES key expansion process. For each round of key expansion, a different
constant value is needed. This module generates these round constants
through a counter-based lookup mechanism.

**2. Block Diagram**

![](./figures/aes_rconmod.jpg)

**3. Interface**

|**Signal Name**|      **Direction**|    **Width**|   **Description**|                                      
| --- | --- | --- | --- |
|clk    |        input      |      1       |    System clock|
|kld  |          iutput   |        1     |      Key load signal (active high)|
|out       |     output    |       32   |       Round constant value|

**4.Register**

rcnt: Round counter for key expansion process. Counts from 0 to 9,
increments each clock cycle when kld is deasserted, resets to 0 when kld
is asserted. Controls round constant generation sequence.

**5. Operation Principle**

**5.1 Algebraic Structure of Round Constants**

Round constants are calculated in the finite field GF($2^{8}$).
According to the paper, this field is defined by the irreducible
polynomial m(x) = $x^{8} + x^{4} + x^{3} + x + 1$. In this field:

-   Each element can be represented as an 8-bit binary number

-   Addition operation is bitwise XOR

-   Multiplication must be performed under modulo m(x)

**5.2 Round Constant Generation Principle**

Round constants RC\[i\] are generated using the following recursive
formula:

1.  RC\[1\] = 01 (initial value)

2.  RC\[i\] = x·RC\[i-1\], i\>1

where x represents 02 in GF($2^{8}$). Therefore, each round constant is
the result of multiplying the previous round constant by 02 in
GF($2^{8}$).

**5.3 Round Constant Sequence Derivation**

**5.3.1 Basic Derivation Process**

The derivation process of round constants:

1.  RC\[1\] = 01

2.  RC\[2\] = 02 × 01 = 02

3.  RC\[3\] = 02 × 02 = 04

4.  RC\[4\] = 02 × 04 = 08

5.  RC\[5\] = 02 × 08 = 10

6.  RC\[6\] = 02 × 10 = 20

7.  RC\[7\] = 02 × 40 = 40

8.  RC\[8\] = 02 × 40 = 80

9.  RC\[9\] = 02 × 80 = 1B (requires reduction in GF($2^{8}$))

10. RC\[10\] = 02 × 1B = 36 (requires reduction in GF($2^{8}$))

**5.3.2 Special Value Processing**

When products exceed 8 bits (as in RC\[9\] and RC\[10\]), reduction in
GF($2^{8}$) is required:

-   100 = 1B (mod m(x))

-   1B × 02 = 36 (mod m(x))

**6.Operation**

**6.1 State Transition Diagram**

![](./figures/aes_rconstate.jpg)


**6.2 Normal Operation**

1.  Upon Reset:

-   One time unit after the clock's rising edge, rcnt is cleared to zero

-   One time unit after the clock's rising edge, out outputs initial round constant (32\'h01_00_00_00)

2.  Counting Operation:

-   One time unit after the clock's rising edge, rcnt increments every clock cycle

-   One time unit after the clock's rising edge, out generates corresponding round constant based on rcnt value

**6.3 Round Constant Sequence**

-   RC\[0\] = 32\'h01_00_00_00

-   RC\[1\] = 32\'h02_00_00_00

-   RC\[2\] = 32\'h04_00_00_00

-   \...continues through RC\[9\]

**7. Corner Cases**

**7.1 Key load**

-   When kld=1, output must be 0x01000000

-   Counter must reset to 0

**7.2 Maximum Count**

-   When rcnt\>9, output should be 0x00000000

-   Counter continues to increment but output remains 0

**8. Constraints**

1.  Counter Size:

-   rcnt is 4 bits wide

-   Valid RCON values for rcnt range 0-9

2.  Output Format:

-   Only MSB changes

-   Lower 24 bits must always be 0x000000

-   Output is registered, changes on clock edge

---

**aes_inv_sbox Design Specification**

**1. Introduction**

The aes_inv_sbox module is a key component in
the AES decryption algorithm, responsible for performing the inverse
non-linear byte substitution operation. This document describes the
design principles, implementation methods, and interface specifications
of the Inverse S-box.

**2. Block Diagram**

![](./figures/aes_inv_sboxmod.jpg)


**3. Interface**

| **Signal  Name**| **Direction**  |  **Width** |  **Description**   |                                  
| --- | --- | --- | --- |
|a |input| 8      |     Input byte|
|b  |output|8      |     Substituted byte|

**4. Operation Principle**

**4.1 Basic Principle**

The Inverse S-box transformation implements the inverse operation of the
S-box transformation in AES encryption. According to AES algorithm
theory, the inverse S-box values can be obtained through two
mathematical methods:

1.  Through mathematical calculations in GF($2^{8}$) field, including
    multiplicative inverse and inverse affine transformation.

2.  Directly through the Inverse S-box table.

This design uses a lookup table approach to directly implement the
inverse S-box functionality, where the table stores the inverse S-box
output values for all possible inputs.

**4.2 Mathematical Derivation**

The Inverse S-box transformation process is the reverse order of the
original S-box transformation steps:

4.2.1 Inverse Affine Transformation

-   Input byte b undergoes a linear transformation using an inverse
    matrix

-   The transformation includes two parts:



-   8x8 binary matrix multiplication (matrix is inverse of original
    S-box affine transformation matrix)

-   XOR with constant vector 0x05 (inverse of original S-box constant
    0x63)

> $\begin{bmatrix}
> b'0 \\
> b'1 \\
> b'2 \\
> b'3 \\
> b'4 \\
> b'5 \\
> b'6 \\
> b'7
> \end{bmatrix}$ =$\ \left\lbrack \begin{matrix}
> 0 \\
> 0 \\
> 1 \\
> 0 \\
> 0 \\
> 1 \\
> 0 \\
> 1
> \end{matrix}\ \begin{matrix}
> 1 \\
> 0 \\
> 0 \\
> 1 \\
> 0 \\
> 0 \\
> 1 \\
> 0
> \end{matrix}\ \begin{matrix}
> 0 \\
> 1 \\
> 0 \\
> 0 \\
> 1 \\
> 0 \\
> 0 \\
> 1
> \end{matrix}\ \begin{matrix}
> 1 \\
> 0 \\
> 1 \\
> 0 \\
> 0 \\
> 1 \\
> 0 \\
> 0
> \end{matrix}\ \begin{matrix}
> 0 \\
> 1 \\
> 0 \\
> 1 \\
> 0 \\
> 0 \\
> 1 \\
> 0
> \end{matrix}\ \begin{matrix}
> 0 \\
> 0 \\
> 1 \\
> 0 \\
> 1 \\
> 0 \\
> 0 \\
> 1
> \end{matrix}\ \begin{matrix}
> 1 \\
> 0 \\
> 0 \\
> 1 \\
> 0 \\
> 1 \\
> 0 \\
> 0
> \end{matrix}\ \begin{matrix}
> 0 \\
> 1 \\
> 0 \\
> 0 \\
> 1 \\
> 0 \\
> 1 \\
> 0
> \end{matrix} \right\rbrack\ \begin{bmatrix}
> b0 \\
> b1 \\
> b2 \\
> b3 \\
> b4 \\
> b5 \\
> b6 \\
> b7
> \end{bmatrix} + \begin{bmatrix}
> 1 \\
> 1 \\
> 0 \\
> 0 \\
> 0 \\
> 1 \\
> 1 \\
> 0
> \end{bmatrix}$

4.2.2 Multiplicative Inverse in GF($2^{8}$)

-   Calculate multiplicative inverse in Galois Field GF($2^{8}$)

-   Based on irreducible polynomial: p(x)
    =$x^{8} + x^{4} + x^{3} + x + 1$

-   For any non-zero element a, its inverse $a^{- 1}$ satisfies: a ×
    $a^{- 1}$ ≡ 1 (mod p(x))

-   Special case: inverse of 0x00 is defined as 0x00

**4.3 Implementation Method**

Due to the complexity of mathematical operations, actual implementation
uses a ROM lookup table:

1.  ROM structure uses 256 x 8-bit mapping table

2.  Input byte directly serves as ROM address

3.  ROM output corresponds to pre-calculated inverse transformation
    results

4.  All 256 possible input values have unique output mappings

**4.4 Transformation Example**

Taking input 0x63 as an example:

1.  Input 0x63

2.  Lookup table returns 0x00

3.  This result corresponds to S-box mapping 0x00 to 0x63, verifying the
    inverse relationship

**5. Corner Cases**

**5.1 Special Input Value Handling**

-   Input 0x00 → Output 0x52

-   Input 0x63 → Output 0x00

-   Input 0xFF → Output 0x7D

**5.2 Key Verification Points**

1.  Ensure inverse relationship with S-box module

2.  For any input x, must satisfy:

-   S-box(Inv_S-box(x)) = x

-   Inv_S-box(S-box(x)) = x

**6. Constraints**

1.  Implementation Constraints:

-   Pure combinational logic implementation, no clock or reset required

-   Output responds immediately to input changes

-   Input must remain stable until output is sampled

2.  Resource Constraints:

-   ROM implementation requires 256×8-bit storage

-   Implementation method can be chosen based on target device (ROM/LUT)

-   Lookup table method uses more resources than computational
    implementation
