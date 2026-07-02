# RTL Agent Memory Index

## Debug Repair Outcomes

- [debug_sd_bd_dat_out_s_improved_1](cases/debug_sd_bd_dat_out_s_improved_1.md)
  - sd_bd: dat_out_s improved; Patch improved mismatch count or first fail time; continue from this direction.
- [debug_sd_bd_dat_out_s_improved_3](cases/debug_sd_bd_dat_out_s_improved_3.md)
  - sd_bd: dat_out_s improved; Patch improved mismatch count or first fail time; continue from this direction.
- [debug_sd_bd_free_bd_improved_4](cases/debug_sd_bd_free_bd_improved_4.md)
  - sd_bd: free_bd improved; Patch improved mismatch count or first fail time; continue from this direction.
- [debug_sd_bd_free_bd_pass_5](cases/debug_sd_bd_free_bd_pass_5.md)
  - sd_bd: free_bd passed; Patch fixed all observed mismatches.
- [debug_sd_cmd_master_ERR_INT_REG_improved_3](cases/debug_sd_cmd_master_ERR_INT_REG_improved_3.md)
  - sd_cmd_master: ERR_INT_REG improved; Patch improved mismatch count or first fail time; continue from this direction.
- [debug_sd_cmd_master_ERR_INT_REG_improved_4](cases/debug_sd_cmd_master_ERR_INT_REG_improved_4.md)
  - sd_cmd_master: ERR_INT_REG improved; Patch improved mismatch count or first fail time; continue from this direction.
- [debug_sd_cmd_master_NORMAL_INT_REG_improved_5](cases/debug_sd_cmd_master_NORMAL_INT_REG_improved_5.md)
  - sd_cmd_master: NORMAL_INT_REG improved; Patch improved mismatch count or first fail time; continue from this direction.
- [debug_sd_cmd_master_NORMAL_INT_REG_improved_6](cases/debug_sd_cmd_master_NORMAL_INT_REG_improved_6.md)
  - sd_cmd_master: NORMAL_INT_REG improved; Patch improved mismatch count or first fail time; continue from this direction.
- [debug_sd_cmd_master_req_out_improved_2](cases/debug_sd_cmd_master_req_out_improved_2.md)
  - sd_cmd_master: req_out improved; Patch improved mismatch count or first fail time; continue from this direction.
- [debug_sd_controller_wb_argument_reg_improved_1](cases/debug_sd_controller_wb_argument_reg_improved_1.md)
  - sd_controller_wb: argument_reg improved; Patch improved mismatch count or first fail time; continue from this direction.
- [debug_sd_controller_wb_dat_in_m_rx_bd_improved_4](cases/debug_sd_controller_wb_dat_in_m_rx_bd_improved_4.md)
  - sd_controller_wb: dat_in_m_rx_bd improved; Patch improved mismatch count or first fail time; continue from this direction.
- [debug_sd_controller_wb_dat_in_m_tx_bd_improved_11](cases/debug_sd_controller_wb_dat_in_m_tx_bd_improved_11.md)
  - sd_controller_wb: dat_in_m_tx_bd improved; Patch was kept by acceptance judge: Patch fixed the primary target: first standalone TX BD write now correctly captures 
- [debug_sd_controller_wb_dat_in_m_tx_bd_improved_8](cases/debug_sd_controller_wb_dat_in_m_tx_bd_improved_8.md)
  - sd_controller_wb: dat_in_m_tx_bd improved; Patch improved mismatch count or first fail time; continue from this direction.
- [debug_sd_controller_wb_int_busy_improved_14](cases/debug_sd_controller_wb_int_busy_improved_14.md)
  - sd_controller_wb: int_busy improved; Patch improved mismatch count or first fail time; continue from this direction.
- [debug_sd_controller_wb_new_cmd_improved_13](cases/debug_sd_controller_wb_new_cmd_improved_13.md)
  - sd_controller_wb: new_cmd improved; Patch improved mismatch count or first fail time; continue from this direction.
- [debug_sd_controller_wb_wb_dat_o_improved_12](cases/debug_sd_controller_wb_wb_dat_o_improved_12.md)
  - sd_controller_wb: wb_dat_o improved; Patch was kept by acceptance judge: Patch successfully fixes the original first failure: dat_in_m_tx_bd no longer clears
- [debug_sd_controller_wb_wb_dat_o_improved_3](cases/debug_sd_controller_wb_wb_dat_o_improved_3.md)
  - sd_controller_wb: wb_dat_o improved; Patch improved mismatch count or first fail time; continue from this direction.

## Negative Directions

- [avoid_sd_bd_dat_out_s_regressed_2](patterns/avoid_sd_bd_dat_out_s_regressed_2.md)
  - sd_bd: dat_out_s regressed; Patch worsened mismatch count or first fail time and was rolled back.
- [avoid_sd_cmd_master_NORMAL_INT_REG_regressed_1](patterns/avoid_sd_cmd_master_NORMAL_INT_REG_regressed_1.md)
  - sd_cmd_master: NORMAL_INT_REG regressed; Patch worsened mismatch count or first fail time and was rolled back.
- [avoid_sd_cmd_master_NORMAL_INT_REG_regressed_10](patterns/avoid_sd_cmd_master_NORMAL_INT_REG_regressed_10.md)
  - sd_cmd_master: NORMAL_INT_REG regressed; Patch worsened mismatch count or first fail time and was rolled back.
- [avoid_sd_cmd_master_NORMAL_INT_REG_regressed_3](patterns/avoid_sd_cmd_master_NORMAL_INT_REG_regressed_3.md)
  - sd_cmd_master: NORMAL_INT_REG regressed; Patch worsened mismatch count or first fail time and was rolled back.
- [avoid_sd_cmd_master_NORMAL_INT_REG_regressed_4](patterns/avoid_sd_cmd_master_NORMAL_INT_REG_regressed_4.md)
  - sd_cmd_master: NORMAL_INT_REG regressed; Patch worsened mismatch count or first fail time and was rolled back.
- [avoid_sd_cmd_master_NORMAL_INT_REG_regressed_5](patterns/avoid_sd_cmd_master_NORMAL_INT_REG_regressed_5.md)
  - sd_cmd_master: NORMAL_INT_REG regressed; Patch worsened mismatch count or first fail time and was rolled back.
- [avoid_sd_cmd_master_NORMAL_INT_REG_syntax_failed_1](patterns/avoid_sd_cmd_master_NORMAL_INT_REG_syntax_failed_1.md)
  - sd_cmd_master: NORMAL_INT_REG syntax_failed; Patch failed lint and was rolled back; fix syntax before retrying this idea.
- [avoid_sd_cmd_master_NORMAL_INT_REG_syntax_failed_2](patterns/avoid_sd_cmd_master_NORMAL_INT_REG_syntax_failed_2.md)
  - sd_cmd_master: NORMAL_INT_REG syntax_failed; Patch failed lint and was rolled back; fix syntax before retrying this idea.
- [avoid_sd_cmd_master_NORMAL_INT_REG_syntax_failed_4](patterns/avoid_sd_cmd_master_NORMAL_INT_REG_syntax_failed_4.md)
  - sd_cmd_master: NORMAL_INT_REG syntax_failed; Patch failed lint and was rolled back; fix syntax before retrying this idea.
- [avoid_sd_cmd_master_NORMAL_INT_REG_syntax_failed_8](patterns/avoid_sd_cmd_master_NORMAL_INT_REG_syntax_failed_8.md)
  - sd_cmd_master: NORMAL_INT_REG syntax_failed; Patch failed lint and was rolled back; fix syntax before retrying this idea.
- [avoid_sd_controller_wb_argument_reg_syntax_failed_2](patterns/avoid_sd_controller_wb_argument_reg_syntax_failed_2.md)
  - sd_controller_wb: argument_reg syntax_failed; Patch failed lint and was rolled back; fix syntax before retrying this idea.
- [avoid_sd_controller_wb_dat_in_m_tx_bd_regressed_10](patterns/avoid_sd_controller_wb_dat_in_m_tx_bd_regressed_10.md)
  - sd_controller_wb: dat_in_m_tx_bd regressed; Patch worsened mismatch count or first fail time and was rolled back.
- [avoid_sd_controller_wb_dat_in_m_tx_bd_syntax_failed_9](patterns/avoid_sd_controller_wb_dat_in_m_tx_bd_syntax_failed_9.md)
  - sd_controller_wb: dat_in_m_tx_bd syntax_failed; Patch failed lint and was rolled back; fix syntax before retrying this idea.
- [avoid_sd_controller_wb_int_busy_regressed_15](patterns/avoid_sd_controller_wb_int_busy_regressed_15.md)
  - sd_controller_wb: int_busy regressed; Patch worsened mismatch count or first fail time and was rolled back.

## Planning Corrections

- [correction_sd_cmd_master_wrong_timing](corrections/correction_sd_cmd_master_wrong_timing.md)
  - sd_cmd_master: One unexplored repair direction: perform an exact line-by-line logic comparison between reference A6 and DUT A6, fix any logic differences f

## Stage6 Merge Rules

- [merge_sd_bd_lint_pass](rules/merge_sd_bd_lint_pass.md)
  - sd_bd: Stage6 merge warning; Output block is not visibly driven by parsed always/assign blocks.
- [merge_sd_cmd_master_lint_pass](rules/merge_sd_cmd_master_lint_pass.md)
  - sd_cmd_master: Stage6 merge warning; Stage5 contracts have multiple writers for response_size: ['B4_comb_cmd_settings_assembly', 'B7_seq_fsm_state_operations
