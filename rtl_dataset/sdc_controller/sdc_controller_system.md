# SD/MMC Controller System Design Specification

This specification describes a complete SD/MMC controller system, including host register access, SD command handling, descriptor-driven data transfers, DMA, clock-domain buffering, command and data serialization, CRC checking, clock generation, reset, status, and interrupts.

Internal design partitioning is intentionally unspecified. The functional sections below are behavioral views of one system. They do not define RTL module boundaries, internal module names, submodule interfaces, instance relationships, instance counts, or ownership of responsibilities. Repeated state-machine, synchronization, buffering, and CRC descriptions specify required behavior only. The implementation shall infer its own skeleton and allocate those behaviors to design units as it sees fit.

Only the top-level design-unit name `sdc_controller` and the top-level port interface are fixed. Internal signal names retained in detailed behavioral descriptions are symbolic names used to state sequencing and data dependencies; they are not required internal ports and do not prescribe a boundary.

---

## 1. System Context, Top-Level Interface, and End-to-End Operation

### Introduction

The controller is the interface between the SD/MMC card and the system bus. Two WISHBONE interfaces, one slave and one master, are used. Internal registers and buffer descriptors (BDs) are accessed through the WISHBONE slave interface. The WISHBONE master interface is used by DMA transactions to fetch data from or store data to external memory. The controller contains the user-accessible configuration and status registers and the logic required to operate them.

### Interface

#### Wishbone

##### IO Ports

| Direction | Width | Name        | Description                          |
| --------- | ----- | ----------- | ------------------------------------ |
| Input     | 1     | wb_clk_i    | Slave WISHBONE Clock Input           |
| Input     | 1     | wb_rst_i    | Slave WISHBONE Reset Input           |
| Input     | 4     | wb_sel_i    | Slave WISHBONE Select Inputs         |
| Input     | 32    | wb_dat_i    | Slave WISHBONE Data Inputs           |
| Output    | 32    | wb_dat_o    | Slave WISHBONE Data Output           |
| Input     | 8     | wb_adr_i    | Slave WISHBONE Address Input         |
| Input     | 1     | wb_we_i     | Slave WISHBONE Write Enable          |
| Input     | 1     | wb_cyc_i    | Slave WISHBONE Cycle                 |
| Input     | 1     | wb_stb_i    | Slave WISHBONE Strobe                |
| Output    | 1     | wb_ack_o    | Slave WISHBONE Acknowledgment        |
| Output    | 32    | m_wb_adr_o  | Master WISHBONE Address Output       |
| Output    | 4     | m_wb_sel_o  | Master WISHBONE Select               |
| Output    | 1     | m_wb_we_o   | Master WISHBONE Write Enable         |
| Output    | 32    | m_wb_dat_o  | Master WISHBONE Data Output          |
| Input     | 32    | m_wb_dat_i  | Master WISHBONE Data Input           |
| Output    | 1     | m_wb_cyc_o  | Master WISHBONE Cycle                |
| Output    | 1     | m_wb_stb_o  | Master WISHBONE Strobe               |
| Input     | 1     | m_wb_ack_i  | Master WISHBONE Acknowledgment Input |
| Output    | 3     | m_wb_cti_o  | Master WISHBONE Cti                  |
| Output    | 2     | m_wb_bte_o  | Master WISHBONE Bte                  |
| Input     | 1     | card_detect | Card detect                          |

#### SDC IO

##### IO Ports

| Direction | Width | Name         | Description                |
| --------- | ----- | ------------ | -------------------------- |
| Input     | 1     | sd_cmd_dat_i | SDC/MMC CMD Input          |
| Output    | 1     | sd_cmd_out_o | SDC/MMC CMD Output         |
| Output    | 1     | sd_cmd_oe_o  | SDC/MMC CMD Output enable  |
| Input     | 4     | sd_dat_dat_i | SDC/MMC Data Input         |
| Output    | 4     | sd_dat_out_o | SDC/MMC Data Output        |
| Output    | 1     | sd_dat_oe_o  | SDC/MMC Data Output enable |
| Output    | 1     | sd_clk_o_pad | SDC/MMC CLK Output         |

#### Optional IO

##### IO Ports

| Direction | Width | Name           | Condition        | Description |
| --------- | ----: | -------------- | ---------------- | ----------- |
| Input     | 1     | `sd_clk_i_pad` | `SDC_CLK_SEP`    | Alternative SD clock source |
| Output    | 1     | `int_a`        | `SDC_IRQ_ENABLE` | Enabled normal-status interrupt |
| Output    | 1     | `int_b`        | `SDC_IRQ_ENABLE` | Enabled command-error interrupt |
| Output    | 1     | `int_c`        | `SDC_IRQ_ENABLE` | Enabled data-transfer interrupt |

### Operation

#### Function Description

The host interface connects the IP core to the rest of the system, including a processor and memory, through WISHBONE. The slave interface provides configuration-register access, while the master interface accesses memory. Block data is transferred to and from memory only through DMA.

##### Resetting the core

`wb_rst_i` resets the complete controller. Operational logic can also be reset by setting the `SRST` bit in the Software Reset Register to `1`.

##### Setting up the core

1. Reset the core.
2. Program the Timeout Register and any required interrupt enables.
3. Clear `SRST` before issuing a command or queuing a descriptor. Software may pulse `SRST` when it needs to restart operational state without applying an external reset.

##### Sending command

Sending a command to the SD/MMC card is performed in two steps.

1. First, the command index and transmission settings are written to the Command Setting Register.
2. Next, the command argument is written to the Argument Register; this write initiates the transfer.
3. When the command completes, bit 0 of the Normal Interrupt Status Register is set and response data is available in the Response Register. Any enabled CRC, index, or timeout failure is reported in the Error Interrupt Status Register.

##### Buffer descriptors

Transmission and reception are descriptor based. Transmit descriptors are used for card writes, while receive descriptors are used for card reads. Each descriptor is 64 bits and is submitted as two ordered 32-bit words: first the system-memory buffer address, then the card block address. Descriptor capacity is configuration dependent. With the default `BD_SIZE=32` and 16-bit descriptor storage, each Tx and Rx queue holds eight complete descriptors; other supported configurations may provide a larger capacity.

##### Data block transmission

To transmit a block, software first ensures that the card is initialized, ready for data, configured for a 512-byte block, and operating with all four data bits enabled. If interrupts are used, software may disable command-line interrupts generated by the automatically issued data command and enable the data-transfer interrupts instead.

Software then checks the BD Buffer Status Register for a free Tx descriptor. If space is available, software stores the block in memory and writes the memory start address followed by the destination card block address to the Tx descriptor port.

The controller continuously checks the head of each descriptor queue. For a Tx descriptor, it reads the associated memory pointer and begins filling clock-domain buffering through DMA. At the end of the transfer, status is written to the Data Interrupt Status Register and an interrupt may be generated when enabled. If more descriptors are queued, the next one is then processed.

### Clocks

| Name         | Source             | Remarks | Description                                                  |
| ------------ | ------------------ | ------- | ------------------------------------------------------------ |
| sd_clk_i_pad | Input Pad          |         | Connected to `sd_clk_i` when `SDC_CLK_SEP` is defined        |
| wb_clk_i     | PLL                |         | System clock. Connected to `sd_clk_i` when `SDC_CLK_BUS_CLK` is defined |
| sd_clk_i     |                    |         | clock provided to the system. Used as input clock of SD clock-generation logic when `SDC_CLK_DYNAMIC` is defined. |
| sd_clk_o     | Internal generated |         | clock used in the system. Connected to `sd_clk_i` when `SDC_CLK_BUS_CLK` is defined. Connect to the output SD_CLK of SD clock-generation logic when `SDC_CLK_DYNAMIC` is defined. |
| sd_clk_o_pad | Internal generated |         | An alias for `sd_clk_o`                                      |

---

## 2. Host Programming and Register Behavior

The host register-access behavior provides the WISHBONE slave interface and manages reading and writing of the configuration registers.

### Introduction

WISHBONE is a simple, open-source hardware bus architecture used in digital circuits. It connects different components like processors and memory, allowing them to communicate. This interface should adhere to wishbone specification, detailed in WISHBONE SoC Architecture Specification, Revision B.3.

The host uses this controller logic to assign values to configuration registers to configure the SD card and reads some register values to obtain the SD card's operational status.

#### Required Behavior

The host register-access logic performs two main tasks:

- Assign values to the configuration registers according to the host's settings.
- Return the value of the configuration register specified by the host.

### Register

| Name               | Address | Width | Access | Description                 |
| ------------------ | ------- | ----- | ------ | --------------------------- |
| Argument           | 0x00    | 32    | RW     | Command Argument Reg        |
| Command Setting    | 0x04    | 16    | RW     | Command Setting Reg         |
| Card Status        | 0x08    | 16    | R      | Card Status Reg             |
| Response           | 0x0c    | 32    | R      | Command Response            |
| Controller Setting | 0x1c    | 16    | R      | Controller Setting          |
| Block Size         | 0x20    | 16    | R      | Block Size Reg              |
| Power Control      | 0x24    | 8     | R      | Power Control Reg           |
| Software reset     | 0x28    | 8     | RW     | Software reset Reg          |
| Timeout            | 0x2c    | 16    | RW     | Timeout Reg                 |
| Normal Int Status  | 0x30    | 16    | RW     | Normal Interrupt Status Reg |
| Error Int Status   | 0x34    | 16    | RW     | Error Interrupt Status Reg  |
| Normal Int Enable  | 0x38    | 16    | RW     | Normal Interrupt Enable     |
| Error Int Enable   | 0x3c    | 16    | RW     | Error Interrupt Enable Reg  |
| Capability         | 0x48    | 16    | R      | Capability Reg              |
| Clock Divider      | 0x4c    | 8     | RW     | Clock Divider Reg           |
| BD buffer Status   | 0x50    | 16    | R      | BD Status Reg               |
| Dat Int Status     | 0x54    | 8     | RW     | Data Interrupt Status Reg   |
| Dat Int Enable     | 0x58    | 8     | RW     | Data Interrupt Enable Reg   |
| BD RX              | 0x60    | 32    | W      | Receive descriptor input    |
| BD TX              | 0x80    | 32    | W      | Transmit descriptor input   |

**Argument Register**

| Bit # | Access | Description                     |
| ----- | ------ | ------------------------------- |
| [31:0] | RW      | CMDA - Command Argument Command Data, when writing to this register the transmission starts |

Reset Value: 0000h

**Command setting Register**

| Bit # | Access | Description                     |
| ----- | ------ | ------------------------------- |
| [15:14] | RW | Autonomous receive selector: `00` single-block read (CMD17), `01` SD-status read (ACMD13), `10` or `11` SCR read (ACMD51) |
| [13:8] | RW     | CMDI - Command Index Index of the next command |
| [7:6] | RW     | CMDW – Command Word Select Word to read when response is > 48 Bit |
| 5 | Reserved |  |
| 4 | RW     | CICE - Command index check 0 : Do not perform index check on response CMD 1 : Perform index check on response CMD |
| 3 | RW     | CIRC - Command CRC check 0 : Do not perform CRC check on response CMD 1 : Perform CRC check on response CMD |
| 2 | Reserved |  |
| [1:0] | RW     | RTS – Response type 0: No response 01: Response length 136 10: Response length 48 11: Response length 48 |

Reset Value: 0000h

**Status Register**

| Bit # | Access | Description                     |
| ----- | ------ | ------------------------------- |
| [15:12] | R      | CST – CMD Host Serial Status 0 : Reset 1 : Write Only state 2: Write to Read State 3: Delay after write to read 4: Delay after write only state 5: Read CMD |
| [11:2] | Reserved |  |
| 1 | R | CIDAT – Data-command inhibit/status indication |
| 0 | R      | CICMD – Command Inhibit 1 : Busy 0 : Ready |

Reset Value: 0002h in the default four-bit-bus configuration.

**Response Register**

| Bit # | Access | Description                     |
| ----- | ------ | ------------------------------- |
| [31:0] | R      | CRSP – Command Response Response of last command |

Reset Value:0000h

**Controller settings**

| Bit # | Access | Description                     |
| ----- | ------ | ------------------------------- |
| [15:0] | Not in use |  |

Reset Value: 0000h

**Block Size**

| Bit # | Access | Description                     |
| ----- | ------ | ------------------------------- |
| [15:12] | Reserved |  |
| [11:0] | R      | BS - Block Size Currently Hard coded to 512. Value has no effect on the operation. |

Reset Value: 0200h

**Power control**

| Bit # | Access | Description                     |
| ----- | ------ | ------------------------------- |
| [7:4] | Reserved |  |
| [3:0] | R      | SDBP – SD Bus power Voltage provided to bus 1111 : 3.3 V 1101 : 3 V 1011 : 1.8 V.  We choose 3.3V. |

Reset Value: 000fh

**Software Reset**

| Bit # | Access | Description                     |
| ----- | ------ | ------------------------------- |
| [7:1] | Reserved |  |
| 0 | RW      | SRST – Software reset 0: 1: Reset the hardware |

Reset Value: 0000h

**Timeout Register**

| Bit # | Access | Description                     |
| ----- | ------ | ------------------------------- |
| [15:0] | RW     | CTO – Command timeout Time before a timeout signal is generated when sending, counted with the system clock. |

Reset Value: 0000h

**Normal Interrupt Status Reg**

Writing any value to this register resets it 0000h

| Bit # | Access | Description                     |
| ----- | ------ | ------------------------------- |
| 15 | RW     | EI – Error interrupt; set when any implemented command-error status bit is set |
| [14:3] | Reserved |  |
| 2 | RW | Card removal status after card-detect qualification |
| 1 | RW | Card insertion status after card-detect qualification |
| 0 | RW     | CC – Command Complete This bit is set when get the end bit of the command response. |

**Error Interrupt Status Reg**

Writing any value to this register resets it 0000h

| Bit # | Access | Description                     |
| ----- | ------ | ------------------------------- |
| [15:4] | Reserved |  |
| 3 | RW     | CIE – Command index error This bit is set if a Command Index error occurs in the command response. |
| 2 | Reserved |  |
| 1 | RW     | CCRC – Command CRC error This bit is set when a command CRC check fail |
| 0 | RW     | CTE – Command Timeout This bit is set when a command sequence timeout occur |

**Normal Interrupt Enable Reg**

| Bit # | Access | Description                     |
| ----- | ------ | ------------------------------- |
| 15 | RW     | EEI – Enable Error interrupt 1 : Enable interrupt generation on EI 0 : Disable interrupt generation on EI |
| [14:1] | Reserved |  |
| 0 | RW     | ECC – Enable Command Complete 1 : Enable interrupt generation on ECC 0 : Disable interrupt generation on ECC |

**Error Interrupt Enable Reg**

| Bit # | Access | Description                     |
| ----- | ------ | ------------------------------- |
| [15:4] | Reserved |  |
| 3 | RW     | ECIE – Command index error 1 : Enable interrupt generation on CIE 0 : Disable interrupt generation on CIE |
| 2 | Reserved |  |
| 1 | RW     | ECCRC – Command CRC error 1 : Enable interrupt generation on CCRC 0 : Disable interrupt generation on CCRC |
| 0 | RW     | ECTE – Command Timeout 1 : Enable interrupt generation on CTE 0 : Disable interrupt generation on CTE |

**Capability register**

| Bit # | Access | Description                     |
| ----- | ------ | ------------------------------- |
| [15:0] | Reserved |  |

Reset Value: 0000h

**Clock Divider Register**

| Bit # | Access | Description                     |
| ----- | ------ | ------------------------------- |
| [7:0] | CLKD – Clock Divider | Divide the SD input clock: `0` divides by 2, `1` divides by 4, `2` divides by 6, and so on. |

Reset Value: 0000h

**BD Buffer Status Register**

| Bit # | Access | Description                     |
| ----- | ------ | ------------------------------- |
| [15:8] | R      | FBRX – Free RX Buffer Descriptors NO free receiving buffer Descriptors |
| [7:0] | R      | FBTX – Free TX Buffer Descriptors NO free transmission buffer Descriptors |

Reset Value: `0808h` for the default 16-bit descriptor-storage configuration. The value is capacity dependent in other configurations.

**Data Interrupt Status Register**

| Bit # | Access | Description                     |
| ----- | ------ | ------------------------------- |
| [7:6] | Reserved |  |
| 5 | RW     | TRE – Transmission Error 1 : CRC check failed during transmission 0 : No error |
| 4 | RW     | CMDE – Command error 1 : Error in the command response 0 : No error |
| 2 | RW     | FIFOE - FIFO error 1 : FIFO underflow/overflow 0 : No error |
| 1 | RW     | MRC – Max Retry Attempts reached 1 : Unable to send after N attempts 0 : Not reached |
| 0 | RW     | TRS – Transmission successful 1 : One data block has been sent/received 0 : Not successful |

Reset Value: 0000h

**Data Interrupt Enable Register**

| Bit # | Access | Description                     |
| ----- | ------ | ------------------------------- |
| [7:6] | Reserved |  |
| 5 | RW     | ETRE – Transmission Error 1 : Enable interrupt generation on TRE 0 : Disable interrupt generation on TRE |
| 4 | RW     | ECMDE – Command error 1 : Enable interrupt generation on CMDE 0 : Disable interrupt generation on CMDE |
| 2 | RW     | EFIFOE - FIFO error 1 : Enable interrupt generation on FIFOE 0 : Disable interrupt generation on FIFOE |
| 1 | RW     | EMRC – Max Retry Attempts reached 1 : Enable interrupt generation on MRC 0 : Disable interrupt generation on MRC |
| 0 | RW     | ETRS – Transmission successful 1 : Enable interrupt generation on TRS 0 : Disable interrupt generation on TRS |

Reset Value: 0000h

**BD RX**

Two acknowledged 32-bit writes form one receive descriptor. The first write is the memory location where received data shall be stored; the second is the card block address to read. A partial descriptor is not eligible for processing.

**BD TX**

Two acknowledged 32-bit writes form one transmit descriptor. The first write is the memory location from which data shall be read; the second is the card block address to write. A partial descriptor is not eligible for processing.

### Operation

#### Reset  and Clock

Host-side state is updated on the rising edge of `wb_clk_i` and uses an active-high asynchronous external reset.

When `wb_rst_i` is asserted, this controller logic immediately resets all variables to their reset value.  There are two types of situations:

- Configuration registers return to the default values described in the Register section.
- Transaction state is cleared, while the internal condition that permits an ordinary WISHBONE acknowledgment starts in the ready state.

#### Functional Description

##### Register Write

The controller provides register writes through the WISHBONE slave interface.

- Condition: `wb_stb_i` is high,  indicating that this slave logic is selected, `wb_cyc_i` is high, indicating that a valid bus cycle is in progress **and** `wb_we_i` is asserted.
- Action: The address on `wb_adr_i` selects the destination register and `wb_dat_i` supplies its new value. A write to the Argument Register initiates a command, while writes to clear-on-write status addresses request the corresponding status clear.
  - A write to `BD TX` or `BD RX` may be a multi-cycle slave transaction. With 16-bit descriptor storage, the lower and upper halves of the 32-bit bus word are committed in order. `wb_ack_o` is withheld until that complete 32-bit descriptor word has been accepted. Two such bus writes are required to form one 64-bit descriptor.

##### Register Read

The controller provides register reads through the WISHBONE slave interface.

- Condition: If `wb_stb_i` is high,  indicating that this slave logic is selected **and** `wb_cyc_i` is high, indicating that a valid bus cycle is in progress.
- Action: Select the corresponding register based on `wb_adr_i`, and assign the value of this register to `wb_dat_o`. The addresses of the registers are specified in the Register section.
- Purpose: When the controller logic is in operation, return the value of the corresponding register based on the address.

---

## 3. Command Lifecycle and CMD-Line Behavior

This section describes command construction, command-line ownership, response handling, status updates, timeout handling, and the required crossings between the system and SD clock domains. These are behavioral requirements rather than ownership assignments.

### Introduction

**Function Description**

The command transaction behavior synchronizes communication between the host interface and the physical interface. It performs three main tasks:

- Read the user-accessible command registers and compose the 40 protected command-content bits.
- Receive response bits from the CMD line and forward the selected response word to the user-accessible Response Register.
- Track command-line status and report completion, CRC failure, index mismatch, or timeout.

**Design Overview**

The command transaction logic operates as a finite state machine (FSM) with three primary states: `IDLE`, `SETUP`, and `EXECUTE`. It interfaces with various registers such as `ARG_REG`, `CMD_SET_REG`, and `TIMEOUT_REG` to configure and execute commands. The controller logic also handles interrupt generation and status updates based on command execution results.

**Required Behavioral Topics**

The command transaction logic requires several coordinated behaviors that work cohesively to manage SD card commands:

1. **Debounce Logic**: Ensures stable detection of the SD card presence by filtering rapid fluctuations in the `card_detect` signal.
2. **Synchronization**: Synchronizes asynchronous input signals (`req_in` and `ack_in`) to the controller logic's clock domain to prevent metastability.
3. **Finite State Machine (FSM)**: Manages the states of command processing, transitioning between IDLE, SETUP, and EXECUTE states based on inputs and internal conditions.
4. **FSM State operation**: Maintains and updates status registers  based on operational outcomes and error conditions.

#### Register Definitions

**CMD_SET_REG**

| Bits   | Name          | Description          |
| ------ | ------------- | -------------------- |
| [13:8] | `CMDI`        | Command Index        |
| [7:6]  | `WORD_SELECT` | Word Select          |
| [4]    | `CICE`        | Index Check Enable   |
| [3]    | `CRCE`        | CRC Check Enable     |
| [1:0]  | `RTS`         | Response Type Select |

**STATUS_REG**

| Bits | Name    | Description             |
| ---- | ------- | ----------------------- |
| [0]  | `CICMD` | Reserved for future use |

**ERR_INT_REG**

| Bits | Name    | Description           |
| ---- | ------- | --------------------- |
| [3]  | `CIE`   | Command Index Error   |
| [1]  | `CCRCE` | CRC Error             |
| [0]  | `CTE`   | Command Timeout Error |

**NORMAL_INT_REG**

| Bits | Name | Description      |
| ---- | ---- | ---------------- |
| [15] | `EI` | Error Interrupt  |
| [0]  | `CC` | Command Complete |

**State Definitions**

| Behavioral phase | Description |
| ---------------- | ----------- |
| `IDLE` | Waiting for a new command |
| `SETUP` | Preparing command content and response settings |
| `EXECUTE` | Executing the command and waiting for completion or failure |

The phase names describe required sequencing only. Their state encoding and allocation to RTL design units are implementation choices.

**Other Defines**

| Bits        | Name      | Description    |
| ----------- | --------- | -------------- |
| `status[6]` | dat_ava   | Data Available |
| `status[5]` | crc_valid | CRC Validity   |

##### Detailed Functional Behavior

###### Card-Detect Qualification

The **Debounce Logic** ensures stable detection of the SD card’s presence by filtering out transient fluctuations or noise in the `card_detect` signal. Mechanical card insertion/removal can cause rapid, unintended toggling of the `card_detect` signal. The debounce mechanism counteracts this by requiring the `card_detect` signal to remain stable for a specific number of consecutive clock cycles before acknowledging a state change.

This behavior is sampled using `wb_clk_i` and cleared by the active-high command reset.

1. **Reset condition:**

- **Action:** Initialize `debounce` counter and `card_present` flag to `0`.
- **Purpose:** Ensure the system starts in a known, stable state.

2. **Normal operation:**

- **Card Detection (`!card_detect`):**
  - **Condition:** If `card_detect` is low (`!card_detect`), indicating the card is present.
  - **Action**: If `debounce` is not yet at its maximum (`4'b1111`), increment `debounce` by `1`. This step verifies that the card detection signal remains low consistently over multiple clock cycles.
  - **Purpose:** Gradually confirm the card's presence to avoid false triggers due to signal noise.
- **Card Not Detected (`card_detect` High):**
  - **Action:** Reset `debounce` counter to `0`.
  - **Purpose:** Immediate dismissal of the card presence if the detection signal is not persistently low.
- **Card Presence Flag (`card_present`):**
  - **Condition:** If `debounce` reaches its maximum value (`4'b1111`), set `card_present` to `1`. Else: Set `card_present` to `0`.
  - **Purpose:** Only assert `card_present` after the debounce counter confirms stability, ensuring reliable card detection.

###### Request and Acknowledge Synchronization

Request and acknowledgment events that cross between the system and SD clock domains must be synchronized to prevent metastability.

Acknowledgment synchronization mitigates metastability and ensures that an asynchronous acknowledgment is reliable before system-clocked command control uses it.

1. **Reset condition:**

- **Action:** Initialize synchronization registers `ack_q` and `ack_in_int` to `0`.

- **Purpose:** Ensure the acknowledge signal starts in a known, stable state.

2. **Normal operation:**

- **First stage (`ack_q`):** Capture the incoming `ack_in` signal on the rising edge of `wb_clk_i`.

- **Second Stage (`ack_in_int`):** Transfer the synchronized `ack_q` signal to `ack_in_int` on the next rising edge.

- **Purpose:** Two-stage synchronization reduces the probability of metastability by allowing the signal to stabilize before being used internally.

The request signal is synchronized in the same manner so that asynchronous `req_in` transitions are captured reliably in the system-clock domain.

1. **Reset condition:**
- **Action:** Initialize synchronization registers `req_q` and `req_in_int` to `0`.
- **Purpose:** Guarantee that the request signal starts in a known, stable state.
2. **Normal operation:**
- **First stage (`req_q`):** Capture the incoming `req_in` signal on the rising edge of `wb_clk_i`.
- **Second Stage (`req_in_int`):** Transfer the synchronized `req_q` signal to `req_in_int` on the next rising edge.
- **Purpose:** Two-stage synchronization ensures the `req_in` signal is free from metastability before being used internally.

#### Finite State Machine (FSM)

Combinational logic to determine the next state of the FSM based on current state and inputs.

#####  FSM State transitions

**State Transition Table**

The following table outlines the possible state transitions based on current state and input conditions.

| **Current State** | **Input Conditions**                | **Next State** | **Description**                                              |
| ----------------- | ----------------------------------- | -------------- | ------------------------------------------------------------ |
| IDLE              | `New_CMD` asserted                  | SETUP          | A new command is received; transition to SETUP state.        |
| IDLE              | `New_CMD` not asserted              | IDLE           | Remain in IDLE; no new command to process.                   |
| SETUP             | `ack_in_int` asserted               | EXECUTE        | Acknowledge received; move to EXECUTE state.                 |
| SETUP             | `ack_in_int` not asserted           | SETUP          | Remain in SETUP; wait for acknowledgment.                    |
| EXECUTE           | `complete` asserted                 | IDLE           | Command execution completed; return to IDLE state.           |
| EXECUTE           | `complete` not asserted             | EXECUTE        | Continue in EXECUTE; await completion or handle errors.      |
| Default           | Any condition not explicitly listed | IDLE           | Default to IDLE to ensure safe recovery from undefined states. |

**State Diagram**

##### **State Register Update**

The current command phase is updated on each rising edge of `wb_clk_i`; active-high reset returns it to `IDLE`.

1.**Reset Condition**:

- Sets `state` to `IDLE`.

2.**Normal Operation**:

- Transitions to `next_state` as determined by the combinational logic.

#### FSM State operation

The FSM controls various outputs based on the current state and input conditions. The following sections detail the behavior and output assignments in each state.

1. **Reset condition:** command reset is asserted.

- Sets `CRC_check_enable`,`complete`,`RESP_1_REG`,`ERR_INT_REG`,`NORMAL_INT_REG`,`STATUS_REG`,`status`,`cmd_out`,`settings`,`response_size`,`req_out`,`index_check_enable`,`ack_out`,`Watchdog_Cnt`,`CCRCE`,`EI`,`CC`,`go_idle_o` to 0.

2.**Normal Operation**: based on the state.

Normal Interrupt Status bit 1 reflects qualified card presence and bit 2 reflects qualified card absence. The transient command-complete condition defaults low until completion is detected.

- **IDLE State**

  - **Purpose**:

    Check for serial command-status updates and return request, acknowledgment, and forced-idle controls to their inactive values.

  - **Actions**

    - `go_idle_o`: Set to `0`.
    - `req_out`: Set to `0`.
    - `ack_out`: Set to `0`.
    - `CICMD`: Set to `0`.

    - If `req_in_int` is 1 (indicating a status change from an consuming control logic):
      - Update `status` with `serial_status`.
      - Assert `ack_out` to acknowledge the status change.

- **SETUP State**

  - **Purpose**:

    1. Compose the 40-bit command content from the Command Setting and Argument Registers.
    2. Prepare response, delay, CRC-check, and data-transfer settings.
    3. Clear stale command status before starting the new transaction.

  - **Actions**

    - `NORMAL_INT_REG` and `ERR_INT_REG`: Cleared to `0`.
    - `index_check_enable`: Set based on `CICE` (`CMD_SET_REG[4]`).
    - `CRC_check_enable`: Set based on `CRCE` (`CMD_SET_REG[3]`).
    - Configure `cmd_out` with:
      - Bits `[39:38]`: `2'b01`.
      - Bits `[37:32]`: `CMDI` (`CMD_SET_REG[13:8]`).
      - Bits `[31:0]`: `ARG_REG`.
    - Determine `response_size` based on the `RTS` field:
      - `2'b10` or `2'b11`: Set to `small_rsp` (`7'b0101000`).
      - `2'b01`: Set to `big_rsp` (`7'b1111111`).
      - Otherwise: Set to `0`.
    - Configure the symbolic `settings` value with:
      - Bits `[14:13]`: `WORD_SELECT` (`CMD_SET_REG[7:6]`).
      - Bit `12`: `data_read`.
      - Bit `11`: `data_write`.
      - Bits `[10:8]`: `3'b111` (Delay).
      - Bit `7`: `CRCE` (`CMD_SET_REG[3]`).
      - Bits `[6:0]`: `response_size`.
    - `Watchdog_Cnt`: Reset to `0`.
- **EXECUTE State**
  - **Purpose**:

    1. Increment the watchdog and test `Watchdog_Cnt > TIMEOUT_REG`.
    2. On timeout, set `EI` and `CTE`, abort the bit-level transaction, and return to idle.
    3. Start service only after the synchronized ready acknowledgment is observed.
    4. Accept synchronized serial-status updates.
    5. Treat status bit 6 as response-data availability and command completion.
    6. Perform the enabled CRC and command-index checks.
    7. Store `cmd_in[31:0]` in the Response Register when a response is expected.

  - **Actions**

    - Watchdog Mechanism
      - Increment `Watchdog_Cnt` each cycle.
      - If `Watchdog_Cnt > TIMEOUT_REG`
        - Assert `CTE` (Command Timeout Error) and `EI` (Error Interrupt).
        - If `ack_in` is `1`, set `complete` to `1`.
        - Assert `go_idle_o` to transition back to IDLE.
    - Request and Acknowledge Handling
      - If `ack_in_int` is 1: Start sending when serial logic is ready
        - Assert `req_out` to start sending the command.
      - Else if `req_in_int` is 1: Incoming New Status
        - Update `status` with `serial_status`.
        - Assert `ack_out`.
        - If `dat_ava` is 1
          - Set `complete` to `1` and deassert `EI`.
          - If `CRC_check_enable` is 1 and `crc_valid` is 0: Assert `CCRCE` and `EI`.
          - If `index_check_enable` is 1 and command index mismatch: Assert `CIE` and `EI`.
          - Set `CC` (Command Complete) to `1`.
          - If `response_size` is not `0`, capture response data in `RESP_1_REG`.

##### Command-Phase Data Flow

The next command phase is selected from the current phase and synchronized events, captured on `wb_clk_i`, and used to produce the phase-specific actions below. This sequencing requirement does not mandate separate next-state, state-register, or output-logic design units.

**IDLE State Output Flow**

```
[IDLE State]
     |
     |-- Reset Outputs:
           |--> go_idle_o = 0
           |--> req_out = 0
           |--> ack_out = 0
           |--> CICMD = 0
     |
     |-- Check req_in_int:
           |--> If 1:
                 |--> status = serial_status
                 |--> ack_out = 1
           |--> Else:
                 |--> No action
```

**SETUP State Output Flow**

```
[SETUP State]
     |
     |-- Clear Interrupt Registers:
           |--> NORMAL_INT_REG = 0
           |--> ERR_INT_REG = 0
     |
     |-- Enable Checks:
           |--> index_check_enable = CICE
           |--> CRC_check_enable = CRCE
     |
     |-- Determine response_size:
           |--> If RTS == 2'b10 or 2'b11:
                 |--> response_size = small_rsp
           |--> Else if RTS == 2'b01:
                 |--> response_size = big_rsp
           |--> Else:
                 |--> response_size = 0
     |
     |-- Assemble cmd_out and settings:
           |--> cmd_out[39:38] = 2'b01
           |--> cmd_out[37:32] = CMDI
           |--> cmd_out[31:0] = ARG_REG
           |--> settings[14:13] = WORD_SELECT
           |--> settings[12] = data_read
           |--> settings[11] = data_write
           |--> settings[10:8] = 3'b111
           |--> settings[7] = CRCE
           |--> settings[6:0] = response_size
     |
     |-- Reset Watchdog:
           |--> Watchdog_Cnt = 0
     |
     |-- Assert CICMD:
           |--> CICMD = 1
```

**EXECUTE State Output Flow**

```
[EXECUTE State]
     |
     |-- Increment Watchdog:
           |--> Watchdog_Cnt += 1
     |
     |-- Check Watchdog Timeout:
           |--> If Watchdog_Cnt > TIMEOUT_REG:
                 |--> CTE = 1
                 |--> EI = 1
                 |--> If ack_in == 1:
                       |--> complete = 1
                 |--> go_idle_o = 1
     |
     |-- Control req_out and ack_out:
           |--> If ack_in_int == 1:
                 |--> req_out = 1
           |--> Else if req_in_int == 1:
                 |--> status = serial_status
                 |--> ack_out = 1
                 |--> If dat_ava == 1:
                       |--> complete = 1
                       |--> EI = 0
                       |--> If CRC_check_enable && ~crc_valid:
                             |--> CCRCE = 1
                             |--> EI = 1
                       |--> If index_check_enable && (cmd_out[37:32] != cmd_in[37:32]):
                             |--> CIE = 1
                             |--> EI = 1
                       |--> CC = 1
                       |--> If response_size != 0:
                             |--> RESP_1_REG = cmd_in[31:0]
```

### Clock and Reset

**Clock**

- **Clock signal**: `wb_clk_i` drives command construction, watchdog, status, and the system-clock side of the command handshake.

**Reset**

- **Asynchronous reset**: `wb_rst_i`, combined where required with Software Reset bit 0, returns command-control state to its defaults.

### Corner Cases

**Error Handling**

- **Timeouts**: If a command exceeds the configured `TIMEOUT_REG` value, the controller logic asserts error flags (`CTE`, `EI`) and triggers a transition to the `IDLE` state via `go_idle_o`.
- **CRC Errors**: If CRC checks are enabled and a CRC mismatch is detected, the controller logic sets the `CCRCE` flag and asserts the `EI` interrupt.
- **Index Mismatch**: If an index check is enabled and the received command index does not match the sent index, the controller logic sets the `CIE` flag and asserts the `EI` interrupt.
- **Card Detection Debounce Failure**: Rapid toggling of the `card_detect` signal is handled by the debounce logic to prevent false card presence detection.

**Special Conditions**

- **Simultaneous Interrupt Resets**: Both `ERR_INT_RST` and `NORMAL_INT_RST` can be asserted simultaneously to reset their respective interrupt registers without affecting each other.
- **Status Change During Execution**: The controller logic handles asynchronous status changes from the serial interface by prioritizing ACK signals and updating statuses accordingly.

### Constraints

**Signal Interactions**

- **Mutually Exclusive Signals**: Certain signals are designed to be mutually exclusive to prevent conflicting operations. For example:
  - `data_write` and `data_read` should not be asserted simultaneously as they represent different command types (write vs. read).

**Timing Constraints**

- **Debounce Counter**: The debounce counter (`debounce`) must reach its maximum value (`4'b1111`) to confirm card presence. Any fluctuation below this threshold keeps the `card_present` flag inactive.
- **Watchdog Timer**: The watchdog counter (`Watchdog_Cnt`) must not overflow beyond `TIMEOUT_REG` to prevent unintended resets.

**Operational Constraints**

- **CRC and Index Checks**: CRC and index checks are performed only if their respective enable flags (`CRCE`, `CICE`) are set. These checks are essential for ensuring data integrity and command validity.
- **Response Size Determination**: The response size (`response_size`) is determined based on the `RTS` field in `CMD_SET_REG`. Incorrect configuration of `RTS` may lead to unexpected response handling.

**Specific Constraints Based on 2.2.5 Description**

- **Idle State Constraints**:
  - `go_idle_o`, `req_out`, and `ack_out` are deasserted in the `IDLE` state to ensure no unintended command transmissions.

- **Setup State Constraints**:
  - `settings` are configured based on the `CMD_SET_REG` inputs, ensuring that only valid commands with proper settings are sent.

- **Execute State Constraints**:
  - The controller logic must monitor `complete` and `ack_in_int` to determine when to transition back to `IDLE`.
  - Commands shall not start until the SD-clocked CMD behavior reports that it is ready (`ack_in_int` asserted).

- **Interrupt Constraints**:
  - Error and normal interrupts should be reset appropriately using `ERR_INT_RST` and `NORMAL_INT_RST` to avoid stale interrupt statuses.

By adhering to these constraints, the command transaction logic ensures reliable and predictable interactions with the SD/MMC card, maintaining data integrity and system stability.

---

### Introduction

**Design Overview**

CMD-line serial behavior drives and samples the external bidirectional CMD signal using the generated SD clock. The top-level `sd_cmd_out_o`, `sd_cmd_dat_i`, and `sd_cmd_oe_o` signals are combined by the SoC pad wrapper to implement the bidirectional pin.

**Required Behavioral Topics**

The required CMD-line behavior includes next-state calculation, request and acknowledgment synchronization, command decoding, sequential state updates, and per-state output generation.

The required behavior includes combinational phase selection, sequential phase updates, two-flop synchronization of request and acknowledgment events, decoding of command settings, CRC processing, CMD output control, and response sampling. These behaviors may be implemented together or distributed across any internal hierarchy.

### Internal Constants and Parameters

The controller logic utilizes several internal constants and parameters to manage state transitions and operational settings:

**internal constants**

| **Name**                                                     | **Value**                                               | **Description**                                              |
| ------------------------------------------------------------ | ------------------------------------------------------- | ------------------------------------------------------------ |
| `INIT_DELAY`                                                 | `2` (SIM) / `64` (Other)                                | Number of cycles to keep the CMD line high during initialization. |
| `NCR`                                                        | `2`                                                     | Number of cycles required for write delay.                   |
| `SEND_SIZE`                                                  | `48`                                                    | Total number of bits to send for a complete command transmission, including CRC and stop bit. |
| `CONTENT_SIZE`                                               | `40`                                                    | Size of the internal command buffer (`In_Buff` and `Out_Buff`). |
| `Read_Delay`                                                 | `7`                                                     | Number of cycles to delay before processing read response.   |
| `EIGHT_PAD`                                                  | `8`                                                     | Number of padding bits used in response handling.            |
| `INIT`, `IDLE`, `WRITE_WR`, `DLY_WR`, `READ_WR`, `DLY_READ`, `ACK_WR`, `WRITE_WO`, `DLY_WO`, `ACK_WO` | Symbolic phase names | Required CMD-line sequencing phases; binary encodings are implementation-defined. |

**Internal Signals**

The controller logic maintains several internal signals to manage command processing, CRC operations, and state transitions:

| **Name**              | **Width** | **Type** | **Description**                                              |
| --------------------- | --------- | -------- | ------------------------------------------------------------ |
| `Response_Size`       | 7         | Reg      | Stores the size of the expected response from the SD/MMC card. |
| `Delay_Cycler`        | 3         | Reg      | Counter for managing delay cycles during state transitions.  |
| `In_Buff`             | 40        | Reg      | Internal buffer holding the incoming command data (`CMD_IN`). |
| `Out_Buff`            | 40        | Reg      | Internal buffer for storing the outgoing command response data. |
| `Write_Read`          | 1         | Reg      | Flag indicating a write operation expecting a read response. |
| `Write_Only`          | 1         | Reg      | Flag indicating a write-only operation without expecting a read response. |
| `word_select_counter` | 5         | Reg      | Counter for managing word selection during CRC operations.   |
| `CRC_RST`             | 1         | Reg      | Symbolic reset control for CRC calculation.                  |
| `CRC_IN`              | 7         | Reg      | Input data for CRC computation.                              |
| `CRC_VAL`             | 7         | Wire     | CRC7 value calculated from the command bit stream.           |
| `CRC_Enable`          | 1         | Reg      | Enable condition for CRC calculation.                        |
| `CRC_OUT`             | 1         | Reg      | Current bit supplied to the CRC calculation.                 |
| `CRC_Check_On`        | 1         | Reg      | Flag indicating whether CRC checking is enabled for the current command. |
| `Crc_Buffering`       | 1         | Reg      | Flag indicating if CRC data is being buffered.               |
| `CRC_Valid`           | 1         | Reg      | Flag indicating the validity of the received CRC.            |
| `Cmd_Cnt`             | 8         | Reg      | Counter for tracking the number of command bits sent or received. |
| `Delay_Cnt`           | 3         | Reg      | Counter for managing delay states and transitions.           |
| `state`               | Implementation-defined | Reg | Current symbolic CMD-line phase.                        |
| `next_state`          | Implementation-defined | Reg | Next symbolic CMD-line phase selected from current conditions. |
| `block_write`         | 1         | Reg      | Flag indicating a block write operation.                     |
| `block_read`          | 1         | Reg      | Flag indicating a block read operation.                      |
| `word_select`         | 2         | Reg      | Signals for selecting specific words during data transfer.   |
| `FSM_ACK`             | 1         | Reg      | Acknowledgment flag for FSM operations.                      |
| `DECODER_ACK`         | 1         | Reg      | Acknowledgment flag for the command decoder completion.      |
| `q`                   | 1         | Reg      | Intermediate flip-flop for synchronizing `REQ_IN`.           |
| `Req_internal_in`     | 1         | Reg      | Synchronized internal request signal after crossing clock domains. |
| `q1`                  | 1         | Reg      | Intermediate flip-flop for synchronizing `ACK_IN`.           |
| `Ack_internal_in`     | 1         | Reg      | Synchronized internal acknowledgment signal after crossing clock domains. |

##### Detailed Functional Behavior

###### State Transition Logic

**State Transition Table**

The following table outlines the possible state transitions based on current state and input conditions.

| **Current State** | **Input Conditions**                     | **Next State** | **Description**                                         |
| ----------------- | ---------------------------------------- | -------------- | ------------------------------------------------------- |
| INIT              | `Cmd_Cnt >= INIT_DELAY`                  | IDLE           | Transition to IDLE after initialization delay.          |
| INIT              | Otherwise                                | INIT           | Remain in INIT state.                                   |
| IDLE              | `Write_Read` asserted                    | WRITE_WR       | Start write with read response.                         |
| IDLE              | `Write_Only` asserted                    | WRITE_WO       | Start write without read response.                      |
| IDLE              | Otherwise                                | IDLE           | Remain in IDLE state.                                   |
| WRITE_WR          | `Cmd_Cnt >= SEND_SIZE - 1`               | DLY_WR         | Transition to write delay after sending.                |
| WRITE_WR          | Otherwise                                | WRITE_WR       | Continue writing.                                       |
| WRITE_WO          | `Cmd_Cnt >= SEND_SIZE - 1`               | DLY_WO         | Transition to write-only delay.                         |
| WRITE_WO          | Otherwise                                | WRITE_WO       | Continue write-only operation.                          |
| DLY_WR            | `Delay_Cnt >= NCR` and `!cmd_dat_i`      | READ_WR        | Transition to read write response delay.                |
| DLY_WR            | Otherwise                                | DLY_WR         | Continue in write delay state.                          |
| DLY_WO            | `Delay_Cnt >= Delay_Cycler`              | ACK_WO         | Transition to acknowledge write-only.                   |
| DLY_WO            | Otherwise                                | DLY_WO         | Continue in write-only delay state.                     |
| READ_WR           | `Cmd_Cnt >= (Response_Size + EIGHT_PAD)` | DLY_READ       | Transition to read delay after receiving response.      |
| READ_WR           | Otherwise                                | READ_WR        | Continue reading response.                              |
| DLY_READ          | `Ack_internal_in` asserted               | ACK_WR         | Transition to acknowledge read response.                |
| DLY_READ          | Otherwise                                | DLY_READ       | Continue in read delay state.                           |
| ACK_WO            | Any                                      | IDLE           | Transition back to IDLE after acknowledging write-only. |
| ACK_WR            | Any                                      | IDLE           | Transition back to IDLE after acknowledging read.       |
| Default           | Any condition not listed                 | INIT           | Default to INIT to ensure safe state.                   |

###### State Register Update

**Reset Condition (`RST_IN` High)**:

- The FSM state is set to `INIT`, regardless of the current state.
- Ensures the FSM starts in a known, stable state upon reset.

**Normal Operation (`RST_IN` Low)**:

- On each rising edge of `SD_CLK_IN`, the current state `state` transitions to `next_state`.
- The next phase is selected from the transition table above.

###### Request Synchronization

Synchronization is updated on the rising edge of `SD_CLK_IN`; asynchronous active-high `RST_IN` takes precedence.
1. **Reset Condition**: `RST_IN` High
- **Action:** Initialize synchronization registers `Req_internal_in` and `q` to `0`.
**Purpose**: Ensures that the controller logic starts in a known, stable state.

2. **Normal Operation**:On each rising edge of `SD_CLK_IN`
- The intermediate flip-flop `q` captures the current value of `REQ_IN`.
- Subsequently, `Req_internal_in` captures the value of `q`.
- **Purpose**: Transitions `REQ_IN` through two flip-flops to safely synchronize it to the local clock domain, mitigating the risk of metastability.

###### Acknowledgment Synchronization

1. ** Reset Condition**:`RST_IN` High
- **Action:** both `q1` and `Ack_internal_in` are reset to `0`.
- **Purpose**: Ensures that the controller logic starts in a known, stable state.

2. **Normal Operation**: On each rising edge of  `SD_CLK_IN`
- The intermediate flip-flop `q1` captures the current value of `ACK_IN`.
- Subsequently, `Ack_internal_in` captures the value of `q1`.
- **Purpose**: Transitions `ACK_IN` through two flip-flops to safely synchronize it to the local clock domain, mitigating the risk of metastability.

###### Command Decode Behavior

**Reset Condition (`RST_IN` High)**:
- Resets all internal registers and flags: `Delay_Cycler`, `Response_Size`, `DECODER_ACK`, `Write_Read`, `Write_Only`, `CRC_Check_On`, `In_Buff`, `block_write`, `block_read`, `word_select` are all set to `0`.
- **Purpose**: Initializes the controller logic to a known state, ensuring no residual data or flags affect subsequent operations.

**Command Decoding**: `Req_internal_in` is asserted (`1`), indicating a synchronized request for command processing.
  - Decode `SETTING_IN`:
    - `Response_Size` <= `SETTING_IN[6:0]`
    - `CRC_Check_On` <= `SETTING_IN[7]`
    - `Delay_Cycler` <= `SETTING_IN[10:8]`
    - `block_write` <= `SETTING_IN[11]`
    - `block_read` <= `SETTING_IN[12]`
    - `word_select` <= `SETTING_IN[14:13]`
  - Load Command Data:
    - `In_Buff` <= `CMD_IN`
  - Set Operation Flags:
    - If `SETTING_IN[6:0] > 0`:
      - `Write_Read` <= `1`
      - `Write_Only` <= `0`
    - Else:
      - `Write_Read` <= `0`
      - `Write_Only` <= `1`
  - Manage Acknowledgment:
    - `DECODER_ACK` <= `0` (indicating decoding in progress)
- **Purpose**: Prepares internal settings and buffers based on the incoming command configuration for accurate command transmission.

**Decoding Completion**: `Req_internal_in` is  Low, indicating no ongoing decoding request.
- Actions:
  - `Write_Read` <= `0`
  - `Write_Only` <= `0`
  - `DECODER_ACK` <= `1` (indicating decoding is complete)
- **Purpose**: Resets operation flags and acknowledges the completion of the decoding process, allowing the FSM to proceed with command transmission.

###### Per-State Output Behavior

The following per-phase behavior manages counters, CRC operation, CMD ownership, status, and response data.

**Reset Condition (`RST_IN` High)**

When a reset is asserted, all internal registers and control signals are initialized to their default states to ensure the controller logic starts in a known and stable condition.

| **Signal**            | **Initial Value** | **Description**                                         |
| --------------------- | ----------------- | ------------------------------------------------------- |
| `CRC_Enable`          | `0`               | Disables CRC calculation.                              |
| `word_select_counter` | `0`               | Resets the word selection counter.                      |
| `Delay_Cnt`           | `0`               | Resets the delay counter.                               |
| `cmd_oe_o`            | `1`               | Enables the CMD line output (high-impedance state off). |
| `cmd_out_o`           | `1`               | Asserts the CMD output high to maintain idle state.     |
| `Out_Buff`            | `0`               | Clears the outgoing command buffer.                     |
| `FSM_ACK`             | `1`               | Asserts FSM acknowledgment.                             |
| `REQ_OUT`             | `0`               | Deasserts the request output signal.                    |
| `CRC_RST`             | `1`               | Resets the CRC calculation state.                      |
| `CRC_OUT`             | `0`               | Clears the CRC output signal.                           |
| `CRC_IN`              | `0`               | Clears the CRC input register.                          |
| `CMD_OUT`             | `0`               | Clears the CMD output data.                             |
| `Crc_Buffering`       | `0`               | Disables CRC buffering.                                 |
| `STATUS`              | `0`               | Resets the status register.                             |
| `CRC_Valid`           | `0`               | Disables CRC validation.                                |
| `Cmd_Cnt`             | `0`               | Resets the command counter.                             |
| `st_dat_t`            | `0`               | Resets the start data transfer type signal.             |

**Detailed Operations by State**

**INIT State**: Initialize the controller logic by keeping the CMD line active for a predefined number of cycles.

- Increment `Cmd_Cnt` by 1 on each clock cycle.
- Keep `cmd_oe_o` and `cmd_out_o` asserted (`1`) to maintain the CMD line in an active state.

**IDLE State**: Await new command requests.

- Deassert `cmd_oe_o` to place the CMD line in a high-impedance state (`0`).
- Reset counters: `Delay_Cnt` and `Cmd_Cnt` to `0`.
- Reset CRC-related signals: `CRC_RST = 1`, `CRC_Enable = 0`, `CMD_OUT = 0`.
- Clear `st_dat_t` and `word_select_counter`.

**WRITE_WR State**: Send a write command expecting a read response.

- Deassert `FSM_ACK` (`0`) to indicate the FSM is processing the write operation.
- Disable CRC reset and enable CRC computation (`CRC_RST = 0`, `CRC_Enable = 1`).
- Command Transmission:
  - If `Cmd_Cnt == 0`: Set `STATUS` to `16'b0000_0000_0000_0001`, indicating a write operation. Assert `REQ_OUT` (`1`) to initiate the command transmission.
  - Else if `Ack_internal_in` is asserted: Deassert `REQ_OUT` (`0`) to stop requesting the service.
  - CRC Buffering and Bit Transmission:

    If `Crc_Buffering == 1`:

    - Assert `cmd_oe_o` (`1`) to enable CMD output.
    - If `Bit_Nr > 8`: Transmit command bits and if `Bit_Nr > 9`, manage CRC output.
    - Else if `Bit_Nr <= 8 && Bit_Nr >= 2`: Transmit CRC bits and update `st_dat_t` based on operation type.
    - Else: Maintain CMD line high (`cmd_out_o = 1`).
    - Increment `Cmd_Cnt` by 1.

    Else:
    - Pre-load CRC by setting `Crc_Buffering = 1`.
    - Assign `CRC_OUT` from `In_Buff` based on `Vector_Index`.

**WRITE_WO State**: Send a write-only command without expecting a read response.

- Similar to `WRITE_WR` state with adjustments for write-only operations. Deassert `FSM_ACK` (`0`) to indicate the FSM is processing the write operation. Disable CRC reset and enable CRC computation (`CRC_RST = 0`, `CRC_Enable = 1`).

- If `Cmd_Cnt == 0`: Set `STATUS[3:0]` to `4'b0010`, indicating a write-only operation. Assert `REQ_OUT` (`1`) to initiate the command transmission. Else if `Ack_internal_in` is asserted: Deassert `REQ_OUT` (`0`) to stop requesting the service.
- CRC Buffering and Bit Transmission:

  If `Crc_Buffering == 1`:
  - Assert `cmd_oe_o` (`1`) to enable CMD output.
  - Transmit command bits and manage CRC output similarly to `WRITE_WR`.
  - Set `st_dat_t` based on `block_read` flag.
  - Increment `Cmd_Cnt` by 1.

  Else:
  - Pre-load CRC by setting `Crc_Buffering = 1`.
  - Assign `CRC_OUT` from `In_Buff` based on `Vector_Index`.

**DLY_WR State**: Introduce a delay after sending a write command.

- If `Delay_Cnt == 0`:
  - Set `STATUS[3:0]` to `4'b0011`, indicating a delay after write.
  - Assert `REQ_OUT` (`1`) to initiate the next operation.
- Else if `Ack_internal_in` is asserted:
  - Deassert `REQ_OUT` (`0`) to stop requesting the service.
- Disable CRC computation and reset (`CRC_Enable = 0`, `CRC_RST = 1`).
- Set `Cmd_Cnt` to `1`.
- Deassert `cmd_oe_o` (`0`) to place CMD line in high-impedance state.
- If `Delay_Cnt < 3'b111`: Increment `Delay_Cnt` by 1.
- Disable CRC buffering (`Crc_Buffering = 0`).

**DLY_WO State**: Introduce a delay after sending a write-only command.

- If `Delay_Cnt == 0`:
  - Set `STATUS[3:0]` to `4'b0100`, indicating a delay after write-only.
  - Clear `STATUS[5]` and set `STATUS[6]` to `1`.
  - Assert `REQ_OUT` (`1`) to initiate the next operation.
- Else if `Ack_internal_in` is asserted:
  - Deassert `REQ_OUT` (`0`) to stop requesting the service.
- Disable CRC computation and reset (`CRC_Enable = 0`, `CRC_RST = 1`).
- Set `Cmd_Cnt` to `0`.
- Deassert `cmd_oe_o` (`0`) to place CMD line in high-impedance state.
- Increment `Delay_Cnt` by 1.
- Disable CRC buffering (`Crc_Buffering = 0`).

**READ_WR State**: Receive and process the read response from the SD/MMC card.

- Reset `Delay_Cnt` to `0`.
- Disable CRC reset and enable CRC computation (`CRC_RST = 0`, `CRC_Enable = 1`).
- Deassert `cmd_oe_o` (`0`) to place CMD line in high-impedance state.
- If `Cmd_Cnt == 1`:
  - Set `STATUS[3:0]` to `4'b0101`, indicating a read operation.
  - Assert `REQ_OUT` (`1`) to initiate the read response reception.
  - Set `Out_Buff[39] = 0` to mark the start bit.
- Else if `Ack_internal_in` is asserted:
  - Deassert `REQ_OUT` (`0`) to stop requesting the service.
- Response Reception:
  - If `Cmd_Cnt < Response_Size`:
    - Capture incoming data bits (`cmd_dat_i`) into `Out_Buff` based on `Cmd_Cnt` and `word_select`.
    - Assign `CRC_OUT` from `cmd_dat_i` for CRC computation.
  - Else if `(Cmd_Cnt - Response_Size) <= 6`:
    - Assign `CRC_IN` from `cmd_dat_i` based on the reduced count.
    - Disable CRC computation (`CRC_Enable = 0`).
  - Else:
    - Validate CRC:
      - If `(CRC_IN != CRC_VAL)` and `CRC_Check_On == 1`:
        - Set `CRC_Valid = 0`.
        - Disable CRC (`CRC_Enable = 0`).
      - Else:
        - Set `CRC_Valid = 1`.
        - Disable CRC (`CRC_Enable = 0`).
    - Update `st_dat_t` based on `block_read` and `block_write` flags:
      - If both `block_read` and `block_write` are asserted:
        - Set `st_dat_t = 2'b11`.
      - Else if `block_write` is asserted:
        - Set `st_dat_t = 2'b01`.
    - Increment `Cmd_Cnt` by 1.

**DLY_READ State**: Finalize the read response processing.

- If `Delay_Cnt == 0`:
  - Set `STATUS[3:0]` to `4'b0110`, indicating completion of read delay.
  - Set `STATUS[5]` to `CRC_Valid` and `STATUS[6]` to `1`.
  - Assert `REQ_OUT` (`1`) to signal completion.
- Else if `Ack_internal_in` is asserted:
  - Deassert `REQ_OUT` (`0`) to stop requesting the service.
- Disable CRC computation and reset (`CRC_Enable = 0`, `CRC_RST = 1`).
- Clear `Cmd_Cnt` and deassert `cmd_oe_o` (`0`).
- Assign `CMD_OUT` with the contents of `Out_Buff`.
- Increment `Delay_Cnt` by 1.

**ACK_WO State**: Acknowledge the completion of a write-only operation.

- Assert `FSM_ACK` (`1`).

**ACK_WR State**: Acknowledge the completion of a read operation.

- Assert `FSM_ACK` (`1`).
- Deassert `REQ_OUT` (`0`).

### Clock and Reset

#### Clock

- **Signal**: `SD_CLK_IN`
- **Description**: The main clock signal for the CMD-line serial logic, driving all synchronous operations including state transitions, signal synchronization, and CRC computations.

#### Reset

- **Signal**: symbolic `RST_IN`, driven by the active-high command reset.
- **Description**: Reset is asynchronous for the SD-clocked command state and initializes counters, status, output controls, and phase state.

#### Operation

- **Clock Conditions**: All synchronous operations are triggered on the rising edge of `SD_CLK_IN`.
- **Reset conditions**: When reset is asserted, command serial state and outputs return immediately to their defaults.

### Corner Cases

#### Metastability in Signal Synchronization

- **Issue**: Asynchronous `REQ_IN` and `ACK_IN` signals may cause metastability when transitioning between clock domains.
- **Handling**: Two-stage flip-flop synchronization safely transfers these control events into the local `SD_CLK_IN` domain, minimizing the risk of metastability.

#### CRC Validation Failures

- **Issue**: Received CRC does not match the computed CRC, indicating data corruption.
- **Handling**: In the `READ_WR` state, if `CRC_IN` does not match `CRC_VAL` and CRC checking is enabled (`CRC_Check_On`), the controller logic deasserts `CRC_Valid` and manages error flags accordingly.

#### Command Timeout

- **Issue**: A card may fail to return the expected response.
- **Handling**: The bit-level CMD behavior implements frame and response-delay counts, while the system-clock command watchdog compares elapsed time with the Timeout Register. A watchdog timeout aborts the serial operation and reports `CTE`; `INIT_DELAY` is only the post-reset CMD initialization delay.

#### Simultaneous Read and Write Operations

- **Issue**: Attempting to perform a read and write operation simultaneously may cause signal conflicts.
- **Handling**: The controller logic uses mutually exclusive flags (`Write_Read` and `Write_Only`) to ensure that only one type of operation occurs at a time, preventing conflicts.

#### High-Impedance CMD Line

- **Issue**: Improper release of the CMD line can lead to bus contention or undefined states.
- **Handling**: The FSM ensures that `cmd_oe_o` is correctly deasserted in the `IDLE` state, placing the CMD line in a high-impedance state (`Z`) when not actively transmitting commands.

---

### CRC7 Calculation Behavior

CMD transmission and response checking require a 7-bit cyclic redundancy check over serial input bits. Each accepted bit updates the previous CRC value as specified below. This behavior may be shared or inlined and does not require a distinct RTL unit.

### Clock and Reset

**Clock :`CLK`**

- Type: Synchronous
- Edge: Positive (rising edge)
- Function: Drives the CRC update mechanism. On each rising edge, if `Enable` is high, the CRC value is updated based on the current input.

**Reset:`RST`**

- Type: Asynchronous
- Active Level: High (`1`)
- Function: Immediately resets the CRC register to `0` regardless of the clock. Ensures CRC computation starts from a known state.

### Dataflow

CRC7 operates according to the following dataflow:

1. Inverse Calculation:

- `inv = BITVAL ^ CRC[6]`

- Determines whether to invert the incoming bit based on the highest bit of the current CRC value.

2. CRC Update:

- On the rising edge of `CLK` or when `RST` is asserted:

- If `RST` is high, `CRC` is reset to `0`.

- Else, if `Enable` is high:

  | Signal | Updated with |
  | ------ | ------------ |
  | `CRC[6]` | `CRC[5]` |
  | `CRC[5]` | `CRC[4]` |
  | `CRC[4]` | `CRC[3]` |
  | `CRC[3]` | `CRC[2] ^ inv` |
  | `CRC[2]` | `CRC[1]` |
  | `CRC[1]` | `CRC[0]` |
  | `CRC[0]` | `inv` |

This is the serial LFSR realization of the CRC7 polynomial `x^7 + x^3 + 1`.

### Corner Cases

**Enable Signal Deassertion:**

- When `Enable` is low (`0`), the CRC value remains unchanged even if `BITVAL` changes. This prevents unintended updates when CRC computation should be paused.

**Simultaneous Reset and Enable:**

- If `RST` is high and `Enable` is high simultaneously, the reset operation takes precedence, and the CRC is set to `0`.

---

## 4. Descriptor-Driven Transfer Lifecycle

The controller checks whether any new BD needs to be processed. If so, it generates a command by setting up the command and argument register, then sets up DMA to read or write the correct address. If the command line is free, the controller sends the command and waits for a response. If the response is valid, the controller starts DMA; otherwise, the command is sent again.

During transmission, the controller tracks FIFO buffer underflow or overflow. When transmission is complete, it checks for a valid CRC. If anything goes wrong, a stop command is sent and the controller retries recovery up to `RESEND_MAX_CNT` times before giving up; the default limit is three.

### Introduction

#### Required Behavior

The descriptor-driven transfer logic manages data transfer between the SD card and the host system. It performs three primary functions:

1. **Transmit and Receive Data**: It coordinates the transfer of data to and from the SD card by interfacing with the Tx (transmit) and Rx (receive) buffers. It retrieves buffer descriptors for both transmission and reception, managing the flow of data through FIFOs.

2. **Execute SD Commands**: The controller logic sends various SD card commands (e.g., CMD17, CMD24, CMD12) for reading, writing, and stopping data transfers. It manages the command sequence, handling responses from the SD card and ensuring proper command execution through retries in case of errors.

3. **Track Transfer Status**: It monitors the status of the data transmission and reception, including error detection (e.g., CRC errors), buffer fullness, and command completion. The controller logic sets status flags to inform the host system of successful transfers or failures, ensuring reliable communication with the SD card.

#### Design Overview

Descriptor-driven transfer behavior uses the phases `IDLE`, `GET_TX_BD`, `GET_RX_BD`, `SEND_CMD`, `RECEIVE_CMD`, and `DATA_TRANSFER`. These phases describe the progression of data transfers and command execution without prescribing a particular state encoding or RTL boundary.

1. **FSM Control**: The controller logic transitions between states based on the availability of data in Tx and Rx buffers, command completion, and error conditions. It handles data transfers in `DATA_TRANSFER` state and executes commands in `SEND_CMD` state.

2. **Retry and Error Handling**: The controller logic includes a retry mechanism (`resend_try_cnt`) to handle failed transfers. It tracks command execution through flags like `cmd_busy` and error indicators such as `crc_ok`. Errors trigger transitions to recovery states `STOP_SEND`.

3. **Status Updates**: The controller logic continuously monitors the status of the SD card's data lines, transfer completion, and FIFO buffers. It updates the `Dat_Int_Status` register to notify the host system of the current state, errors, or transfer completions.

#### Parameters

| Name   | Type   | Width | Value  | Description                                          |
|------------|------------|-----------|------------|----------------------------------------------------------|
| `CMD24`    | Parameter  | 16 bits   | 16'h181A   | Command to write a single block to the SD card.           |
| `CMD17`    | Parameter  | 16 bits   | 16'h111A   | Command to read a single block from the SD card.          |
| `CMD12`    | Parameter  | 16 bits   | 16'hC1A    | Command to stop a transmission on the SD card.            |
| `ACMD13`   | Parameter  | 16 bits   | 16'hD1A    | Command to retrieve SD card status.                       |
| `ACMD51`   | Parameter  | 16 bits   | 16'h331A   | Command to read the SCR register from the SD card.        |
| `RESEND_MAX_CNT` | Parameter | 3 bits | 3          | Defines the maximum number of retries for command sending. |
| `READ_CYCLE` | Parameter | -        | 2 or 4     | Defines the number of read cycles based on memory width.  |
| `BD_EMPTY`  | Parameter | -        | Derived from BD_SIZE | Indicates an empty buffer descriptor (Tx or Rx).       |

The named phases used below express the required sequence. State-register width and encoding are intentionally unspecified.

#### External Signals

| Name                  | Width                                  | Description                                                                                     |
|-----------------------|----------------------------------------|-------------------------------------------------------------------------------------------------|
| `RAM_MEM_WIDTH`        | Defined in external file               | Defines the width of RAM memory, can be 16 bits or 32 bits, affects read cycle and buffer descriptor behavior. |
| `BD_WIDTH`             | Defined in external file               | Defines the width of the buffer descriptor.                                                      |
| `BD_SIZE`              | Defined in external file               | Defines the size of the buffer descriptor.                                                       |

##### Definitions Related to External Variables
- **`RESEND_MAX_CNT`** is defined as 3, which indicates the maximum number of retries for sending a command.
- The `READ_CYCLE` value depends on the RAM memory width:
  - If the RAM memory width is 32 bits (`RAM_MEM_WIDTH_32` is defined), then `READ_CYCLE` is set to 2, and a 2-bit register `bd_cnt` is declared.
  - If the RAM memory width is 16 bits (`RAM_MEM_WIDTH_16` is defined), then `READ_CYCLE` is set to 4, and a 3-bit register `bd_cnt` is declared.
- The value of **`BD_EMPTY`** is also determined by the memory width:
  - For 32-bit RAM, `BD_EMPTY` is set to half of `BD_SIZE` (i.e., `BD_SIZE / 2`).
  - For 16-bit RAM, `BD_EMPTY` is set to one-quarter of `BD_SIZE` (i.e., `BD_SIZE / 4`).
### Finite State Machine(FSM)

#### State Transition Table
| Current State      | Input Conditions                                                                                  | Next State         | Description                                                                                          |
|--------------------|--------------------------------------------------------------------------------------------------|--------------------|------------------------------------------------------------------------------------------------------|
| `IDLE`             | `free_tx_bd != BD_EMPTY`                                              | `GET_TX_BD` | Checks if there are available buffer descriptors (Tx BD) to start transmission.        |
| `IDLE`             | `free_rx_bd != BD_EMPTY`                                              | `GET_RX_BD` | Checks if there are available buffer descriptors (Rx BD) to start reception.        |
| `IDLE`             | otherwise                                                                                         | `IDLE`             | Remains in `IDLE` state when no buffer descriptors are available.                                     |
| `GET_TX_BD`        | `bd_cnt > READ_CYCLE - 1` and `tx_full == 1`                                                      | `SEND_CMD`         | Successfully retrieves the transmit buffer descriptor (Tx BD) and prepares for sending a command.      |
| `GET_TX_BD`        | otherwise                                                     | `GET_TX_BD`        | Continues fetching Tx BD if conditions are not met (buffer descriptor count is low or Tx buffer not full). |
| `GET_RX_BD`        | `bd_cnt >= READ_CYCLE - 1`                                                                        | `SEND_CMD`         | Successfully retrieves the receive buffer descriptor (Rx BD) and prepares for sending a command.       |
| `GET_RX_BD`        | otherwise                                                                       | `GET_RX_BD`        | Continues fetching Rx BD if the buffer descriptor count is insufficient.                              |
| `SEND_CMD`         | `send_done == 1`                                                                                  | `RECEIVE_CMD`       | Sends the command successfully and transitions to receive command state.                              |
| `SEND_CMD`         | otherwise                                                                                         | `SEND_CMD`         | Continues sending the command if not complete.                                                        |
| `RECEIVE_CMD`       | `rec_done == 1`                                                                                   | `DATA_TRANSFER`    | Successfully receives the command and moves to data transfer state.                                   |
| `RECEIVE_CMD`       | `rec_failed == 1`                                                                                 | `SEND_CMD`         | If command reception fails, retries by sending the command again.                                     |
| `RECEIVE_CMD`       | otherwise                                                                                         | `RECEIVE_CMD`       | Continues receiving the command until success or failure.                                             |
| `DATA_TRANSFER`    | `trans_done == 1`                                                                                 | `IDLE`             | Successfully completes data transfer and returns to `IDLE`.                                           |
| `DATA_TRANSFER`    | `trans_failed == 1`                                                                               | `STOP`             | If data transfer fails, transitions to `STOP` state to terminate the process.                         |
| `DATA_TRANSFER`    | otherwise                                                                                         | `DATA_TRANSFER`    | Continues the data transfer if it's not yet completed or failed.                                      |
| `STOP`             | N/A                                                                                               | `STOP_SEND`        | Prepares to send a stop command to halt data transmission.                                            |
| `STOP_SEND`        | `send_done == 1`                                                                                  | `IDLE`             | Successfully sends the stop command and transitions back to `IDLE`.                                   |
| `STOP_SEND`        | otherwise                                                                                         | `STOP_SEND`        | Continues sending the stop command until successful.                                                  |

#### state descriptions

1. **IDLE**: The idle state, where the system checks if there are available transmit or receive buffer descriptors (Tx/Rx BD).
2. **GET_TX_BD**: Retrieves the transmit buffer descriptor (Tx BD) to prepare for sending a data command.
3. **GET_RX_BD**: Retrieves the receive buffer descriptor (Rx BD) to prepare for receiving a data command.
4. **SEND_CMD**: Sends a command to the physical interface, entering the process of sending data or receiving a command.
5. **RECEIVE_CMD**: Waits for a command response from the physical interface.
6. **DATA_TRANSFER**: Executes the actual data transfer operation.
7. **STOP**: Stops the current transmission process and prepares to send a stop command.
8. **STOP_SEND**: Sends the stop command to ensure the data transfer is correctly terminated.

#### State Self-loop Transitions:
- Each state includes a transition back to itself (e.g., when sending or receiving is incomplete) to ensure the controller logic correctly handles intermediate states and transitions according to input conditions.

###### State Register Update

**Reset Condition (`rst` High)**:

- The FSM state is set to `IDLE`, regardless of the current state.
- Ensures the FSM starts in a known, stable state upon reset.

**Normal Operation (`rst` Low)**:

- On each rising edge of `clk`, the current state state transitions to next_state.
- The next phase is selected according to the transition table and current conditions.

###### Per-State Output Behavior

**Reset Condition (`rst` High)**:

  Reset all control signals

**Normal Operation (`rst` Low)**:

Here is the conversion of the state machine code into the specified format:

1. **IDLE State**

    Reset all control signals

2. **GET_TX_BD State**
   1. Assert `re_s_tx = 1` to read a transmit buffer descriptor
   2. Process data based on memory width:
      - For 32-bit RAM:
        - First read: Store data to `sys_adr`
        - Second read: Store data to `cmd_arg` and start TX FIFO
      - For 16-bit RAM:
        - Four reads to populate `sys_adr` and `cmd_arg` (16 bits at a time)
        - After last read, start TX FIFO
   3. Set `cmd_set = CMD24` (write single block command)
   4. Set `tx_cycle = 1` to indicate transmit mode

3. **GET_RX_BD State**
   1. Assert `re_s_rx = 1` to read a receive buffer descriptor
   2. Process data based on memory width:
      - For 32-bit RAM:
        - First read: Store data to `sys_adr`
        - Second read: Store data to `cmd_arg`
      - For 16-bit RAM:
        - Four reads to populate `sys_adr` and `cmd_arg` (16 bits at a time)
   3. Set command based on `transfer_type`:
      - If 2'b00: Set `cmd_set = CMD17` (read single block)
      - If 2'b01: Set `cmd_set = ACMD13` (SD status)
      - Otherwise: Set `cmd_set = ACMD51` (SCR register)
   4. Set `rx_cycle = 1` to indicate receive mode

4. **SEND_CMD State**
    1. Determine whether the active descriptor is Rx or Tx.
    2. Select the corresponding read or write command behavior.
    3. Wait until the shared CMD resource is free, then request command issue.
    4. Wait for command acceptance before marking the send phase complete.

5. **RECEIVE_CMD State**
    1. Enable card-to-memory buffering for an Rx operation.
    2. Wait for command inhibit to clear, indicating that the response has completed.
    3. Treat an asserted command-transfer error as command failure.
    4. Accept the response only when the ready-for-data bit is set and the card state is one of the permitted transfer states 4, 5, or 6.

6. **DATA_TRANSFER State**
    1. During Tx, detect a clock-crossing-buffer underflow.
    2. During Rx, detect a clock-crossing-buffer overflow.
    3. Wait for data-transfer completion.
    4. Require `crc_ok == 1` and the data line to be released before reporting success.
    5. Release exactly one completed descriptor.

7. **STOP State**
     1. Set `cmd_set` to `CMD12`
     2. Set `rec_done`, `rec_failed`, `send_done`, `trans_failed`, `trans_done` to `0`
     3. Set `d_read`, `d_write` to `1`
     4. Set `start_rx_fifo`, `start_tx_fifo` to `0`

8. **STOP_SEND State**
      1. Increment `resend_try_cnt` by `1`
      2. If `resend_try_cnt` reaches `RESEND_MAX_CNT`, set Data Interrupt Status bit 1.
      3. If CMD is not busy, then request access to CMD registers
      4. When access is granted, mark stop-command issue complete.

9. A host write to the Data Interrupt Status Register clears the recorded data-transfer status.

### Clock and Reset

#### Clock
Clock Signal: `clk` is the primary clock input for the controller logic. All synchronous operations and state transitions are driven by the rising edge of this clock.

#### Reset
Asynchronous Reset: `rst` is an active-high asynchronous reset signal. When asserted, the controller logic resets all internal registers and states to their default values.

### Constraints

#### 1. **Clock and Reset Constraints**
   - The state machine operates on a clock signal (`clk`).
   - The system should respond to a reset signal (`rst`), initializing the state machine and all relevant output variables to their default values.

#### 2. **State Transition Constraints**
   - The state transitions depend on the current state and various input signals.
   - Only one state can be active at any given time.
   - The state machine must ensure that transitions happen only at the rising edge of the clock or during a reset.

#### 3. **Input Acknowledgment Constraints**
   - In states like `GET_RX_BD` and `GET_TX_BD`, the machine must wait for acknowledgment signals (`ack_i_s_rx`, `ack_i_s_tx`) before proceeding with data handling.
   - If the acknowledgment is not received, the state machine may not be able to proceed, preventing data corruption.

#### 4. **Data Handling Constraints**
   - Descriptor data must remain stable until its read acknowledgment is accepted during `GET_RX_BD` and `GET_TX_BD`.
   - SD DAT inputs are sampled only in the SD clock domain during response-token, busy, or receive-data phases.
   - Read/write direction controls must be mutually consistent with the active descriptor.

#### 5. **Block Count Constraints**
   - The symbolic `bd_cnt` value tracks the number of descriptor storage words read, not the number of 512-byte blocks transferred.
   - It must stop after two reads in 32-bit storage mode or four reads in 16-bit storage mode, so that one memory address and one card argument are assembled without consuming the following descriptor.

#### 6. **Command Set Constraints**
   - The command set (`cmd_set`) must be correctly assigned based on the type of data transfer. Commands must adhere to predefined conditions for proper functioning.

#### 7. **Transfer Constraints**
   - Conditions must be checked to ensure that data transfers only occur when the system is ready (e.g., `cmd_busy` must be `0` before sending commands).
   - Constraints related to the status of the card (`card_status`) must be evaluated to determine the success or failure of data transfers.

#### 8. **Failure and Acknowledgment Constraints**
   - The system should properly handle failure conditions (e.g., `trans_failed`, `rec_failed`) and provide corresponding status updates through the `Dat_Int_Status` register.
   - Acknowledgments for commands (`we_ack`) must be monitored to ensure that operations have completed successfully.

#### 9. **Data Integrity Constraints**
   - The data integrity during transfers must be ensured, particularly through checks on the CRC (cyclic redundancy check) status.
   - Any CRC errors or issues must trigger the appropriate status signals to prevent the use of corrupted data.

#### 10. **Resend Mechanism Constraints**
   - The resend mechanism (`resend_try_cnt`) should be limited to a predefined maximum (`RESEND_MAX_CNT`) to avoid endless retries, ensuring that the system can recover gracefully from transmission errors.

These constraints ensure that the state machine operates reliably, handling data correctly, responding to inputs appropriately, and managing transitions between states without errors.

---

**1. Introduction**

The descriptor queue logic is a crucial component in the SD/MMC controller design. It manages the buffer descriptors used for data transmission and reception between the system memory and the SD card. This controller logic implements a circular buffer of descriptors, allowing efficient management of data transfer operations.

**5. Operation Process**

**5.1 Initialization**

1.  The controller logic enters initialization state on system reset.
2.  32-bit mode: The free_bd counter is set to half of the total number of BDs.
3.  16-bit mode: The free_bd counter is set to one quarter of the total number of BDs.
4.  Write pointer m_wr_pnt and read pointer s_rd_pnt are reset to 0.
5.  Write and read counters are reset to 0.

**5.2 Writing Buffer Descriptor**

1.  The host asserts the we_m signal to initiate a BD write.
2.  The controller logic checks if free_bd is greater than 0.
3.  32-bit mode: Two writes complete one BD.
4.  16-bit mode: Four writes complete one BD.
5.  m_wr_pnt increments by 1 after each write.
6.  After completing a BD write, new_bw is set high, and free_bd decrements by 1.

**5.3 Reading Buffer Descriptor**

1.  The SD controller asserts the re_s signal to initiate a BD read.
2.  32-bit mode: Two reads obtain complete BD information.
3.  16-bit mode: Four reads obtain complete BD information.
4.  Each read outputs data from bd_mem[s_rd_pnt] to dat_out_s.
5.  s_rd_pnt increments by 1 after each read.
6.  In 16-bit mode, ack_o_s is set high during each read.

**5.4 Releasing Buffer Descriptor**

1.  The consuming control logic asserts the a_cmp signal to indicate SD card operation completion.
2.  When an a_cmp rising edge is detected, free_bd increments by 1.
3.  16-bit mode uses last_a_cmp to detect the rising edge.

**5.5 Circular Operation**

1.  Write and read operations continue, with pointers wrapping to 0 after reaching BD_SIZE - 1.
2.  The free_bd counter updates dynamically, tracking the number of available BDs.

**6. Constraints and Limitations**

1.  The total number of BDs must be a power of 2 to ensure correct wraparound behavior.
2.  The controller logic assumes read and write operations do not overlap in the buffer.
3.  In 16-bit mode, all four writes or reads must be completed consecutively for a valid BD operation.

---

## 5. DAT-Line Transfer, DMA, and Clock-Domain Buffering

DAT-line behavior drives and samples the four bidirectional SD data pins using the generated SD clock. The top-level `sd_dat_out_o`, `sd_dat_dat_i`, and `sd_dat_oe_o` signals are combined by the SoC pad wrapper.

The controller logic performs the following actions.

- Synchronize transfer control across clock domains.
- Add a CRC16 checksum to transmitted data and check the CRC16 values received with card data.

### Function Description

The required DAT-line behavior includes CRC16 calculation, acknowledgment synchronization, next-phase selection, start-bit detection, sequential phase updates, and per-phase output generation. A symbolic `start_dat` value of `2'b01` starts a card write, `2'b10` starts a card read, and `2'b11` aborts or stops the current data operation. These behaviors do not prescribe internal RTL boundaries.

##### Detailed Sequential and Combinational Behavior

The following requirements retain the original sequencing detail without prescribing separate combinational, sequential, synchronization, CRC, or output-control design units.

###### Acknowledgment Synchronization

**Reset Condition (`rst` High)**:

- Symbolic synchronizer state `ack_transfer_int` and `ack_q` is set to `0`.

**Normal Operation (`rst` Low)**:

- On each rising edge of `sd_clk`, the first stage captures `ack_transfer` and the second stage captures the previous first-stage value.

###### State Transition Logic

The following table defines the required DAT-line phase transitions:

| **Current State** | **Input Conditions**                               | **Next State** | **Description**                                                                 |
| ----------------- | -------------------------------------------------- | -------------- | ------------------------------------------------------------------------------- |
| `IDLE`            | `start_dat == 2'b01`                              | `WRITE_DAT`    | Start writing data to the SD bus.                                               |
| `IDLE`            | `start_dat == 2'b10`                              | `READ_WAIT`    | Enter read wait state to receive data from the SD bus.                          |
| `IDLE`            | Otherwise                                          | `IDLE`         | Remain in idle state.                                                           |
| `WRITE_DAT`       | `transf_cnt >= BIT_BLOCK`                          | `WRITE_CRC`    | The data, CRC, and stop-bit interval is complete.                               |
| `WRITE_DAT`       | `start_dat == 2'b11`                              | `IDLE`         | Abort the active write.                                                         |
| `WRITE_DAT`       | Otherwise                                          | `WRITE_DAT`    | Continue writing data.                                                          |
| `WRITE_CRC`       | `crc_status == 0`                                  | `WRITE_BUSY`   | CRC response-token sampling is complete; wait for card busy release.            |
| `WRITE_CRC`       | Otherwise                                          | `WRITE_CRC`    | Continue CRC generation.                                                        |
| `WRITE_BUSY`      | `busy_int == 1` and synchronized transfer acknowledgment is asserted | `IDLE` | The card released DAT0 and completion was acknowledged. |
| `WRITE_BUSY`      | Otherwise                                          | `WRITE_BUSY`   | Continue waiting for busy signal to deassert.                                   |
| `READ_WAIT`       | Synchronized start-bit indication is low           | `READ_DAT`     | Start bit detected; begin reading data.                                         |
| `READ_WAIT`       | Otherwise                                          | `READ_WAIT`    | Wait for start bit.                                                             |
| `READ_DAT`        | Synchronized transfer acknowledgment asserted      | `IDLE`         | Completed receive was acknowledged.                                             |
| `READ_DAT`        | `start_dat == 2'b11`                              | `IDLE`         | Abort the active read.                                                          |
| `READ_DAT`        | Otherwise                                          | `READ_DAT`     | Continue reading data.                                                          |
| Default           | Any condition not listed                           | `IDLE`         | Default to idle to ensure safe operation.                                       |

###### Start-Bit Synchronization

**Reset Condition (`rst` High)**:

- The symbolic start-bit indication is set to `1`.

**Normal Operation (`rst` Low)**:

- On each rising edge of `sd_clk`, set the symbolic start-bit indication low when `sd_dat_dat_i[0]` is low during `READ_WAIT`; otherwise set it high.

###### State Register Update

**Reset Condition (`rst` High)**:

- The FSM state is set to IDLE, regardless of the current state.
- Ensures the FSM starts in a known, stable state upon reset.

**Normal Operation (`rst` Low)**:

- On each rising edge of `sd_clk`, the current phase advances to the selected next phase.

###### Per-State Output Behavior

**Reset Condition (`rst` High)**:
The variables listed below will be assigned values as shown in the table.

| **Signal**            | **Value** |
|-----------------------|-----------|
| `write_buf_0`         | `0`       |
| `write_buf_1`         | `0`       |
| `DAT_oe_o`            | `0`       |
| `crc_en`              | `0`       |
| `crc_rst`             | `1`       |
| `transf_cnt`          | `0`       |
| `rd`                  | `0`       |
| `last_din`            | `0`       |
| `crc_c`               | `0`       |
| `crc_in`              | `0`       |
| `DAT_dat_o`           | `0`       |
| `crc_status`          | `7`       |
| `crc_s`               | `0`       |
| `transm_complete`     | `0`       |
| `busy_n`              | `1`       |
| `we`                  | `0`       |
| `data_out`            | `0`       |
| `crc_ok`              | `0`       |
| `busy_int`            | `0`       |
| `data_send_index`     | `0`       |
| `out_buff_ptr`        | `0`       |
| `in_buff_ptr`         | `0`       |

**Normal Operation (`rst` Low)**:

1. IDLE State

    Reset and pause the CRC calculation, clear transfer counters, and return the DAT outputs to their inactive values.

2. WRITE_DAT State
     1. Prefetch FIFO words into two alternating 32-bit holding buffers so that a new word can be accepted while the other is serialized.
     2. Select the holding buffer indicated by the output-buffer pointer as the current transmit word.
     3. Drive a start bit of `0` on the active data lines.
     4. In 4-bit mode, serialize one nibble per SD clock in the original word ordering; feed the same nibble into the four CRC16 calculations.
     5. Pipeline the driven nibble by one SD-clock step relative to the CRC input, as required by the original timing.
     6. After all eight nibbles of a 32-bit word have been sent, switch the output-buffer pointer and load the next complete FIFO word without losing or repeating data.
     7. Repeat until the complete 512-byte block has been sent.
     8. Append one 16-bit CRC value on each active data line.
     9. End the transfer with a stop bit of `1`, then release the data lines.

3. WRITE_CRC State

    Sample the seven-cycle CRC response token on DAT0. Account for the two-cycle input delay and the token start bit, then capture the three response-status bits. The accepted status is `3'b010`; other status values indicate a write failure.

    Read bit nr 7 the stopbit.

4. WRITE_BUSY State
     1. Mark the serial block transmission complete after the response token has been captured.
     2. Set the CRC-result indication according to the captured response-status bits.
     3. Poll `sd_dat_dat_i[0]`: low means that the card remains busy and high means that the card has released DAT0. The overall write operation succeeds only after an acceptable response token and busy release have both occurred.

5. READ_WAIT State

    Prepare for data reception, enable the CRC calculations, release the DAT output enables, and wait for the synchronized low start bit on DAT0.

6. READ_DAT State
     1. Sample the active DAT inputs, pass the data nibble to the receive buffering path, and feed each active line into its CRC16 calculation.
     2. Increment the transfer counter once per sampled SD-clock data beat.
     3. Repeat until 512 data bytes have been received.
     4. During the following 16 cycles, compare the received CRC bit on each active line with its calculated CRC value. Four-bit mode checks all four lines independently; one-bit mode checks DAT0 only.
     5. Latch a failed CRC result if any required comparison mismatches. The historical simulation configuration may bypass this comparison, but a synthesizable implementation shall support the check.
     6. Assert serial-transfer completion after all 16 CRC bits have been consumed and preserve the result until it is acknowledged.
     7. Do not report the received block as successful unless the complete payload and CRC interval were accepted without overflow or abort.

---

### Memory-to-Card Buffering Behavior

For a card-write operation, the controller reads 32-bit words from system memory through the Wishbone master interface and buffers them across the system-clock/SD-clock boundary before serial transmission. The following symbolic register names describe the original sequencing; they do not prescribe a separate RTL unit or its ports.

#### Clock and Reset

-   System Clock (clk): Main clock for the control logic and Wishbone
    interface.

-   SD Clock (sd_clk): Clock for the SD card interface, used for reading
    from the TX FIFO.

-   Reset (rst): Asynchronous reset, active high. Resets all registers
    and the TX FIFO.

#### Symbolic State

| **Register**  | **Width** | **Description**                          |
|---------------|-----------|------------------------------------------|
| offset        | 9         | Address offset for Wishbone transactions |
| we            | 9         | Write enable counter                     |
| din           | 32        | Data to be written to FIFO               |
| wr_tx         | 1         | Write control for FIFO                   |
| reset_tx_fifo | 1         | TX FIFO reset control                    |
| first         | 1         | First operation flag                     |
| ackd          | 1         | Acknowledge delay flag                   |
| delay         | 1         | Delay flag for synchronization           |

#### Operation

##### Initialization

On reset:

-   Reset all control signals and counters

-   Reset the FIFO buffer

-   Set Wishbone master signals to inactive state

-   Initialize address offset to 0

##### Data Transfer Process

When enabled (en = 1):

1.  Start a Wishbone read transaction when:

    -   FIFO is not full (fe = 0)

    -   No Wishbone master transaction is already active

    -   The previous transfer's internal completion delay has elapsed (`ackd = 1` in the symbolic sequencing)

2.  When Wishbone acknowledges (m_wb_ack_i = 1):

    -   Write data to FIFO (wr_tx = 1, din = m_wb_dat_i)

    -   Deassert Wishbone cycle and strobe after accepting the returned word

    -   Set delay flag for timing purposes

3.  On the next clock cycle (delay = 1):

    -   Increment memory address offset.(offset += MEM_OFFSET)

    -   Rearm the request sequencing for the next word

    -   Stop writing to FIFO (wr_tx = 0)

##### Disabled State Handling

When disabled (en = 0):

-   Reset TX FIFO (reset_tx_fifo = 1)

-   Reset address offset to 0

-   Set Wishbone control signals to inactive state (m_wb_cyc_o = 0,
    m_wb_stb_o = 0, m_wb_we_o = 0)

##### Constraints and Limitations

-   The controller logic assumes a 32-bit Wishbone data bus.

-   The default transmit-buffer depth is eight 32-bit words and may be configured consistently with the pointer width.

-   `m_wb_adr_o`, cycle, strobe, write-enable, byte select, burst type, and write data shall remain stable for an outstanding transaction until `m_wb_ack_i` is observed. Card-write memory fetches use `m_wb_we_o = 0`, `m_wb_sel_o = 4'b1111`, classic-cycle control (`m_wb_cti_o = 3'b000`, `m_wb_bte_o = 2'b00`), and successive word addresses separated by `MEM_OFFSET`, whose default is four bytes.

---

### Memory-to-Card Clock-Domain Buffering

The memory-to-card stream crosses from the Wishbone clock domain to the SD clock domain through an ordered dual-clock buffer. This section specifies the required buffering behavior without requiring a particular FIFO implementation or hierarchy.

#### Clock and Reset

-   Write Clock (wclk): Used for write operations and write pointer management
-   Read Clock (rclk): Used for read operations and read pointer management
-   Reset (rst): Asynchronous active-high reset

#### Symbolic Storage State

| **Register** | **Width**                | **Description**    |
|--------------|--------------------------|--------------------|
| ram          | 32bit\*FIFO_TX_MEM_DEPTH | FIFO storage array |
| adr_i        | FIFO_TX_MEM_ADR_SIZE      | Write address plus wrap information |
| adr_o        | FIFO_TX_MEM_ADR_SIZE      | Read address plus wrap information  |

#### Operation Process

The FIFO operation process can be divided into the following main parts:

##### Write Operation

1.  Write Enable Check:
    -   The system checks the write enable signal and the FIFO's full status.
    -   Write operation is allowed only when the FIFO is not full and the write enable is active.
2.  Data Writing:
    -   When write conditions are met, data is written to the RAM location pointed to by the current write pointer.

##### Write Address Management

1.  Write Address Increment:
    -   After each successful write, the write address pointer is automatically incremented.
2.  Write Address Wrap-around:
    -   When the write address pointer reaches the maximum value of the FIFO depth, it wraps around to the starting position.
    -   This process is handled by specific logic to ensure correct circular writing.

##### Read Operation

1.  Read Enable Check:
    -   The system checks the read enable signal and the FIFO's empty status.
    -   Read operation is allowed only when the FIFO is not empty and the read enable is active.
2.  Data Reading:
    -   When read conditions are met, data is read from the RAM location pointed to by the current read pointer.
3.  Read Address Management:
    -   The read address pointer increment and wrap-around logic is similar to the write address, but operates independently in the read clock domain.

##### Status Update

1.  FIFO Full Status Update:
    -   The FIFO full status is determined by comparing the positions of read and write pointers.
    -   Specific logic is used to accurately determine the full status, considering pointer wrap-around situations.
2.  FIFO Empty Status Update:
    -   The FIFO is considered empty when the read and write pointers are equal.
3.  FIFO Occupancy Update:
    -   The FIFO occupancy(mem_empt) is determined by the relative positions of the write and read pointers(adr_i - adr_o).
    -   The system continuously calculates and updates this value to reflect the current usage status of the FIFO.
4.  Clock Domain Crossing Considerations:
    -   Write operations and write address management occur in the write clock domain.
    -   Read operations and read address management occur in the read clock domain.
    -   Full and empty indications shall be generated using safe clock-domain-crossing synchronization. An implementation may use Gray-coded pointers or an equivalent proven scheme; it shall not directly consume an unsynchronized multi-bit pointer in the opposite clock domain.

#### Corner Cases

##### Reset

-   Verify that both read pointer (adr_o) and write pointer (adr_i) are reset to 0.
-   Ensure that the FIFO is empty (empty signal is high) after reset.
-   Check that the full signal is low after reset.
-   Verify that the mem_empt signal correctly indicates an empty FIFO.

##### FIFO Full

-   Continue writing until the FIFO is full, verify that the full signal is correctly asserted.
-   When the FIFO is full, attempt to write more data:
    -   Ensure that new write requests do not result in any writes to the RAM.
    -   Verify that existing data in the FIFO is not overwritten.
    -   Confirm that new data is effectively discarded.
-   Check that adr_i does not continue to increment when the FIFO is full.
-   Verify that the mem_empt signal correctly indicates a full FIFO.

##### FIFO Empty

-   When the FIFO is empty, attempt to read data:
    -   Ensure that the read operation does not change the FIFO's state (empty signal should remain high).
    -   Verify that the read address (adr_o) is not updated.
    -   Check that the output q returns the data from the RAM location corresponding to the last read address (adr_o).
-   Ensure that the empty signal is correctly maintained when the FIFO is empty.
-   Verify that the mem_empt signal correctly indicates an empty FIFO.

##### Pointer Wrap-around

-   For the write pointer (adr_i):
    -   Fill the FIFO, then read out some data.
    -   Continue writing until adr_i reaches the end of memory (FIFO_TX_MEM_DEPTH-1).
    -   Verify that on the next write, adr_i correctly wraps around to 0 and the high bit flips.
-   For the read pointer (adr_o):
    -   Fill the FIFO, then read data until adr_o reaches the end of memory.
    -   Verify that on the next read, adr_o correctly wraps around to 0 and the high bit flips.
-   Ensure that the FIFO's full/empty state determination remains correct after pointer wrap-around.
-   Verify that the mem_empt signal correctly reflects the FIFO occupancy during and after pointer wrap-around.

#### Constraints

1.  The write clock (wclk) and read clock (rclk) can be asynchronous to each other.
2.  The reset signal (rst) is asynchronous and active-high.

---

### Card-to-Memory Buffering Behavior

For a card-read operation, the controller assembles the SD data stream into 32-bit words, carries the words into the system-clock domain, and writes them to system memory through the Wishbone master interface. The following symbolic state names preserve the original operation detail but do not prescribe a separate RTL unit or interface.

#### Clock and Reset

-   System Clock (clk): Main clock for the control logic and Wishbone
    interface.

-   SD Clock (sd_clk): Clock for the SD card interface, used for writing
    to the RX FIFO.

-   Reset (rst): Asynchronous reset, active high. Resets all registers
    and the RX FIFO.

#### Symbolic State

| **Register**  | **Width** | **Description**                          |
|---------------|-----------|------------------------------------------|
| offset        | 9         | Address offset for Wishbone transactions |
| wb_free       | 1         | Wishbone bus availability flag           |
| reset_rx_fifo | 1         | RX FIFO reset control                    |
| rd            | 1         | Read enable for RX FIFO                  |

#### Operation

##### Initialization

On reset:

-   Reset all control signals and counters

-   Reset the RX FIFO buffer

-   Set Wishbone master signals to inactive state

-   Initialize address offset to 0

##### Data Reception and Transfer Process

When enabled (`en = 1`):

1.  FIFO Read Preparation:

    -   Stop any previous read operation (rd = 0)

    -   Release FIFO from reset state (reset_rx_fifo = 0)

2.  Read from FIFO and initiate Wishbone write transaction when:

    -   The receive buffer is not empty (`empty = 0`)

    -   Wishbone bus is free (wb_free = 1)

    Actions include:

    -   Start reading from FIFO (rd = 1)

    -   Prepare Wishbone data output (m_wb_dat_o = dat_o)

    -   Set Wishbone write enable and control signals

    -   Mark Wishbone bus as busy (wb_free = 0)

3.  Wishbone Write Transaction Completion: When the Wishbone bus is busy and
    acknowledgment is received (m_wb_ack_i = 1):

    -   Reset Wishbone control signals

    -   Update address offset (offset += MEM_OFFSET)

    -   Mark Wishbone bus as free (wb_free = 1)

##### Disabled State Handling

When disabled (`en = 0`):

-   Reset RX FIFO

-   Stop FIFO read operation

-   Reset address offset

-   Reset all Wishbone control signals

-   Mark Wishbone bus as free

##### Constraints

1.  The controller assumes that the Wishbone slave will eventually acknowledge each transaction. The external master interface has no error input and no independent DMA timeout; therefore an unresponsive slave stalls the operation.

2.  The address increment `MEM_OFFSET` is configurable and defaults to four bytes, matching the 32-bit data width and word-aligned addresses.

3.  The controller logic doesn\'t implement error handling for Wishbone bus
    errors. Additional logic may be needed if error responses need to be
    handled.

4.  The receive-buffer depth defaults to eight 32-bit words. Backpressure or overflow prevention shall guarantee that a full buffer never silently overwrites uncommitted data.

5.  Card-read memory stores use `m_wb_we_o = 1`, `m_wb_sel_o = 4'b1111`, classic-cycle control (`m_wb_cti_o = 3'b000`, `m_wb_bte_o = 2'b00`), and successive addresses separated by `MEM_OFFSET`. Address, data, cycle, strobe, write-enable, byte select, and burst controls remain stable until acknowledgment.

---

### Card-to-Memory Clock-Domain Buffering

The incoming DAT stream is accumulated into words in the SD clock domain and transferred in order to the Wishbone clock domain. This behavior may share storage or control with other functions as long as the observable ordering and protection rules below are maintained.

#### Clock and Reset

-   Write Clock (wclk): Used for write operations and write pointer management
-   Read Clock (rclk): Used for read operations and read pointer management
-   Reset (rst): Asynchronous active-high reset

#### Symbolic Storage State

| **Register** | **Width**                | **Description**                                                                 |
|--------------|--------------------------|---------------------------------------------------------------------------------|
| ram          | 32bit\*FIFO_RX_MEM_DEPTH | FIFO storage array                                                              |
| adr_i        | FIFO_RX_MEM_ADR_SIZE     | Write address                                                                   |
| adr_o        | FIFO_RX_MEM_ADR_SIZE     | Read address                                                                    |
| we           | 8                        | Byte-wise write enable. Used to indicate which bytes can be written to the RAM. |
| tmp          | 32                       | Temporary storage                                                               |
| ft           | 1                        | Data written flag                                                               |

#### Operation

##### Write Operation

1.  4-bit data is written when wr is high on the rising edge of wclk.
2.  Data is accumulated in the tmp register.
3.  After eight accepted nibbles form a complete 32-bit word, that word is written atomically into the buffer if space is available.
4.  The write address (adr_i) is incremented.

##### Read Operation

1.  32-bit data is read from the RAM when rd is high and the FIFO is not empty.
2.  Data is presented on the q output.
3.  The read address (adr_o) is incremented.

##### Full and Empty Flags

-   Full Flag: Asserted when the next accepted word would cause the write position to catch the unread read position, accounting for pointer wraparound.
-   Empty Flag: Asserted when the synchronized read and write positions are equal.
-   Status that crosses between the SD and Wishbone clocks shall use safe CDC synchronization; unsynchronized multi-bit pointers shall not be used directly in the opposite domain.

#### Corner Cases

##### Reset

-   Verify that both read pointer (adr_o) and write pointer (adr_i) are reset to 0.
-   Ensure that the FIFO is empty (empty signal is high) after reset.
-   Check that the full signal is low after reset.
-   Verify that the we register is correctly initialized to 8'h1.
-   Confirm that the tmp register is cleared to zero and the ft flag is set to 0.

##### FIFO Full

-   Continue writing until the FIFO is full, verify that the full signal is correctly asserted.
-   If the buffer becomes full, do not advance its write pointer or overwrite unread words. Prevent further serial acceptance when possible; otherwise terminate the active block as an overflow/error rather than reporting success.

##### FIFO Empty

-   When the FIFO is empty, attempt to read data:
    -   Ensure that the read operation does not change the FIFO's state (empty signal should remain high).
    -   Verify that the read address (adr_o) is not updated.
    -   Check that the output q returns the data from the RAM location corresponding to the last read address (adr_o).
-   Ensure that the empty signal is correctly maintained when the FIFO is empty.

##### Pointer Wrap-around

-   For the write pointer (adr_i):
    -   Fill the FIFO, then read out some data.
    -   Continue writing until adr_i reaches the end of memory (FIFO_RX_MEM_DEPTH-1).
    -   Verify that on the next write, adr_i correctly wraps around to 0 and the high bit flips.
-   For the read pointer (adr_o):
    -   Fill the FIFO, then read data until adr_o reaches the end of memory.
    -   Verify that on the next read, adr_o correctly wraps around to 0 and the high bit flips.
-   Ensure that the FIFO's full/empty state determination remains correct after pointer wrap-around.

#### Constraints

The controller normally relies on the Wishbone side draining data fast enough to avoid overflow, but correctness may not depend on silent overwrite. Overflow must remain detectable and must prevent a false successful completion.

---

### CRC16 Calculation Behavior

DAT transmission and reception require a 16-bit CRC calculation for each active data line. The behavior is equivalent to a serial linear-feedback shift register using the polynomial `x^16 + x^12 + x^5 + 1`; this equivalence does not require a distinct CRC RTL unit.

#### Clock and Reset

**Clock :`CLK`**

- Type: Synchronous
- Edge: Positive (rising edge)

**Reset:`RST`**

- Type: Asynchronous
- Active Level: High (`1`)

#### Function and Logic

##### Combinational Logic

- **`inv` Calculation**: `inv` is computed as the XOR of the current input bit (`BITVAL`) and the most significant bit, `CRC[15]`.

##### Sequential Logic

On each rising edge of the clock or when the reset signal is high, the controller logic performs the following operations:

1. **Reset Handling**: If the reset signal (RST) is high, the CRC value is immediately set to zero.
2. **CRC Update**: If `Enable` is high, update all bits as follows. If `Enable` is low, retain the current CRC value.

| Destination | Next value | Destination | Next value |
|-------------|------------|-------------|------------|
| `CRC[15]` | `CRC[14]` | `CRC[7]` | `CRC[6]` |
| `CRC[14]` | `CRC[13]` | `CRC[6]` | `CRC[5]` |
| `CRC[13]` | `CRC[12]` | `CRC[5]` | `CRC[4] ^ inv` |
| `CRC[12]` | `CRC[11] ^ inv` | `CRC[4]` | `CRC[3]` |
| `CRC[11]` | `CRC[10]` | `CRC[3]` | `CRC[2]` |
| `CRC[10]` | `CRC[9]` | `CRC[2]` | `CRC[1]` |
| `CRC[9]` | `CRC[8]` | `CRC[1]` | `CRC[0]` |
| `CRC[8]` | `CRC[7]` | `CRC[0]` | `inv` |

---

## 6. Configuration and SD Clock Behavior

The original design exposes compile-time options that affect endianness, memory organization, clocking, retry limits, block size, bus width, and buffering depth. The defaults below define the required benchmark configuration; equivalent parameters or constants may be used and need not retain these macro names.

| Name                 | Valid Values                 | Description                              |
|----------------------|------------------------------|------------------------------------------|
| BIG_ENDIAN           | Enabled by default | Assemble and serialize words in big-endian ordering |
| LITTLE_ENDIAN        | Disabled by default | Alternative little-endian ordering |
| SIM                  | Enabled in the supplied benchmark configuration | Simulation-specific clock routing and optional CRC-check bypass in the historical source |
| SYN                  | Disabled in the supplied simulation configuration | Select synthesis behavior when building hardware |
| SDC_IRQ_ENABLE       | Enabled by default | Provide the three optional interrupt outputs |
| ACTEL                | Enabled by default | Select the supplied predefined memory/backend settings |
| BD_WIDTH             | Default 5; no greater than 8 | Descriptor-storage pointer width |
| BD_SIZE              | Default 32; no greater than 255 | Number of 16-bit descriptor storage entries; two entries form one complete 32-bit descriptor word |
| RAM_MEM_WIDTH_16     | Enabled by default | Use 16-bit descriptor storage |
| RAM_MEM_WIDTH        | Default 16; valid 16 or 32 | Descriptor-storage word width |
| RESEND_MAX_CNT       | Default 3; less than 255 | Maximum automatic data-command retries |
| MEM_OFFSET           | Default 4 bytes | Memory address increment between consecutive 32-bit words |
| RESET_CLK_DIV        | Default 0; less than 255 | Clock-divider reset value |
| SD_CLK_BUS_CLK       | Enabled by default | Use `wb_clk_i` as the divider input clock |
| SD_CLK_SEP           | Disabled by default | Optionally use `sd_clk_i_pad` as the divider input clock |
| SD_CLK_STATIC        | Disabled by default | Bypass dynamic division |
| SD_CLK_DYNAMIC       | Enabled by default | Generate the SD clock using the programmable divider |
| BLOCK_SIZE           | 512 bytes | Transferred data-block size |
| SD_BUS_WIDTH_4       | Enabled by default | Use four-bit DAT transfers |
| SD_BUS_W             | 4 | Number of active DAT lines |
| FIFO_RX_MEM_DEPTH    | Default 8 words | Receive-buffer storage depth |
| FIFO_RX_MEM_ADR_SIZE | Default 4 | Receive pointer width, including wrap information |
| FIFO_TX_MEM_DEPTH    | Default 8 words | Transmit-buffer storage depth |
| FIFO_TX_MEM_ADR_SIZE | Default 4 | Transmit pointer width, including wrap information |

Table 1: Core define options

---

### SD Clock Generation

The SD clock-generation logic is a converter between the system clock and the clock required by the SD card-related logic sections.

The controller divides the selected input clock according to the programmed divider and drives the resulting clock on `sd_clk_o_pad`.

### Operation

#### Function Description

The divider toggles the output after `DIVIDER + 1` input-clock cycles. Therefore the complete output-clock frequency is `f_in / (2 * (DIVIDER + 1))`: a register value of 0 divides by 2, 1 divides by 4, and 2 divides by 6.

##### Clock and Reset

**Clock :`CLK`**

- Type: Synchronous
- Edge: Positive (rising edge)

**Reset:`RST`**

- Type: Asynchronous
- Active Level: High (`1`)
- Function: Immediately resets the SD_CLK to `0` regardless of the clock.

### Additional Constraints

| Name  | Description                                  | Effect                                                       |
| ----- | -------------------------------------------- | ------------------------------------------------------------ |
| SYN   | defined during synthesis                     |                                                              |
| SIM   | defined during simulation                    | Directly connect SD_CLK_O and SD_CLK                         |
| ACTEL | a specific backend version used in synthesis | Use SD_CLK_O as the output and SD_CLK as the input for CLKINT |

---

## 7. Architecture Inference Requirement

### System-Wide Coordination Invariants

The detailed behaviors above interact through shared external resources. Any inferred hierarchy shall preserve these system-wide rules:

1. At most one CMD transaction is active on the card interface. A host-initiated command and an automatically generated descriptor command shall be serialized; neither may overwrite the other's command, response, watchdog, or interrupt state.
2. At most one Wishbone master transaction is outstanding. Card-write memory reads and card-read memory writes are mutually exclusive owners of `m_wb_*`; the selected owner retains control until acknowledgment.
3. Only one descriptor-driven data direction is active at a time. If both Tx and Rx queues are nonempty when idle, the original arbitration gives the Tx queue priority; after the current descriptor is released, arbitration is performed again.
4. A descriptor becomes visible to transfer control only after both ordered 32-bit words have been accepted. Its queue entry remains owned until success or terminal failure, and it is released exactly once.
5. Data words remain ordered across clock domains. Empty buffering cannot be read, full buffering cannot be overwritten, and reset or abort cannot expose a partial receive word as valid data.
6. Command and data completion events crossing clock domains must be acknowledged or otherwise transferred without loss or double counting. Multi-bit payloads shall be stable for the complete associated handshake.
7. External reset and software reset leave CMD and DAT outputs in non-contentious inactive states, cancel outstanding internal work, clear partial descriptor/data assembly, and prevent stale completion events after reset release.

### Partitioning Freedom

The preceding sections intentionally overlap in places because they preserve the detailed functional descriptions of the original system-level source specifications. Such overlap does not imply duplicate hardware or a required one-to-one implementation. The implementation shall analyze clock domains, persistent state, handshakes, shared resources, data dependencies, repeated computations, protocol timing, and recovery paths to determine an appropriate RTL hierarchy.

No behavioral subsection above shall be interpreted as a required RTL module. The implementation may merge, split, or reuse logic and may choose all internal module names, ports, state encodings, and instance relationships. Only the externally observable behavior and the fixed top-level `sdc_controller` interface are mandatory.
