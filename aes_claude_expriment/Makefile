VERILATOR = verilator
VERILATOR_FLAGS += -cc --exe
VERILATOR_FLAGS += --binary
VERILATOR_FLAGS += --trace
VERILATOR_FLAGS += --assert
VERILATOR_FLAGS += --coverage-line -fno-table
VERILATOR_FLAGS += -Wno-CASEOVERLAP -Wno-LATCH -Wno-UNOPTFLAT -Wno-MULTIDRIVEN -Wno-ASCRANGE -Wno-IMPLICIT -Wno-CASEINCOMPLETE -Wno-PINMISSING -Wno-WIDTHTRUNC -Wno-EOFNEWLINE -Wno-DECLFILENAME -Wno-WIDTHEXPAND
VERILATOR_FLAGS += -j 4
VERILATOR_FLAGS += --timing
VERILATOR_FLAGS += -fno-table
VERILATOR_FLAGS += --top tb
VERILATOR_INPUT = aes_cipher_top.v aes_sbox.v aes_key_expand_128.v aes_rcon.v aes_cipher_top_testbench.sv aes_cipher_top_stimulus_gen.sv aes_cipher_top_ref.sv

default: compile run

compile:
	@echo "-- COMPILE ----------------"
	$(VERILATOR) $(VERILATOR_FLAGS) $(VERILATOR_INPUT)

run:
	@echo "-- RUN ---------------------"
	@rm -rf logs
	@mkdir -p logs
	obj_dir/Vtb
	@mv coverage.dat wave.vcd logs/

clean:
	-rm -rf obj_dir logs
