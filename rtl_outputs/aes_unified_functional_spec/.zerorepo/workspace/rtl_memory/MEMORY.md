# RTL Agent Memory Index

## Debug Repair Outcomes

- [debug_aes_cipher_top_text_out_improved_1](cases/debug_aes_cipher_top_text_out_improved_1.md)
  - aes_cipher_top: text_out improved; Patch improved mismatch count or first fail time; continue from this direction.
- [debug_aes_cipher_top_text_out_improved_4](cases/debug_aes_cipher_top_text_out_improved_4.md)
  - aes_cipher_top: text_out improved; Patch improved mismatch count or first fail time; continue from this direction.
- [debug_aes_cipher_top_text_out_pass_5](cases/debug_aes_cipher_top_text_out_pass_5.md)
  - aes_cipher_top: text_out passed; Patch fixed all observed mismatches.

## Negative Directions

- [avoid_aes_cipher_top_text_out_regressed_3](patterns/avoid_aes_cipher_top_text_out_regressed_3.md)
  - aes_cipher_top: text_out regressed; Patch worsened mismatch count or first fail time and was rolled back.
