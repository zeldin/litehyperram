# This file is Copyright (c) 2021 Marcus Comstedt <marcus@mc.pp.se>
# License: BSD

from migen import *

from migen.fhdl.decorators import CEInserter, ResetInserter
from migen.fhdl.tools import rename_clock_domain

from litehyperram.common import LiteHyperRAMNativePort

class LiteHyperRAMController(Module):

    il_code = { 3: 0b1110, 4: 0b1111, 5: 0b0000, 6: 0b0001, 7: 0b0010 }

    def __init__(self, phy, module, clk_freq, initial_latency=None, fixed_latency=None):

        if clk_freq > module.maxclock:
            raise ValueError("Clock exceeds module max")

        reset_delay = clk_freq // 5000000 + 1
        min_initial_latency = module.min_initial_latency(clk_freq)
        if initial_latency is None:
            initial_latency = min_initial_latency
        if initial_latency < 3 or initial_latency > module.max_initial_latency:
            raise ValueError("Invalid initial latency")
        if initial_latency < min_initial_latency:
            raise ValueError("Too low initial latency for this frequency")

        dual_die = module.nbanks > 1
        if fixed_latency is None:
            fixed_latency = dual_die
        if dual_die and not fixed_latency:
            raise ValueError("Must use fixed latency for dual die module")

        if 2 * initial_latency < 1 + 2 + phy.tx_latency:
            raise ValueError("Initial latency too low for this phy")
        if initial_latency < 1 + 2 + phy.tx_latency and not fixed_latency:
            raise ValueError("Must enable fixed latency with this initial latency")

        cr0_value = (0x8f07 | (self.il_code[initial_latency] << 4) |
                     (0x0008 if fixed_latency else 0))

        ram_reset_b = Signal(reset=0)
        self.comb += phy.reset_n.eq(ram_reset_b)

        dlycnt = Signal(max=max(reset_delay, phy.tx_latency + phy.rx_latency,
                                2 * initial_latency),
                        reset=reset_delay, reset_less=True)
        self.sync += If(ResetSignal(),
                        dlycnt.eq(reset_delay)
                     ).Elif(dlycnt != 0,
                        dlycnt.eq(dlycnt-1)
                     ).Elif(~ram_reset_b,
                        dlycnt.eq(reset_delay),
                        If(phy.pll_locked, ram_reset_b.eq(1)))

        ck = Signal(reset=0)
        rwds_out = Signal(2)
        dq_out = Signal(16)
        rwds_oe = Signal(reset=0)
        dq_oe = Signal(reset=0)
        cs_b = Signal(reset=1)
        self.comb += [ phy.clk_enable.eq(ck),
                       phy.rwds_da.eq(rwds_out[1]),
                       phy.rwds_db.eq(rwds_out[0]),
                       phy.dq_da.eq(dq_out[8:16]),
                       phy.dq_db.eq(dq_out[0:8]),
                       phy.rwds_oe.eq(rwds_oe),
                       phy.dq_oe.eq(dq_oe),
                       phy.cs_n.eq(cs_b)
                     ]
        rwds_in = [ phy.rwds_qb, phy.rwds_qa ]
        dq_in = Cat(phy.dq_qb, phy.dq_qa)

        self.port = port = LiteHyperRAMNativePort(log2_int(module.nbanks * module.nrows * module.ncols))
        self.comb += [ port.rdata.data.eq(dq_in) ]

        self.submodules.fsm = fsm = ResetInserter()(CEInserter()(FSM(reset_state="CA_WORD0")))
        fsm.ce = dlycnt == 0
        fsm.reset = ~ram_reset_b

        ca = Signal(48, reset=0x600001000000)
        initial_cr0_write = Signal(reset=1)

        fsm.act("CA_WORD0",
                NextValue(cs_b, 0),
                NextValue(ck, 1),
                NextValue(dq_oe, 1),
                NextValue(dq_out, ca[32:48]),
                NextValue(rwds_out, 0b11),
                NextState("CA_WORD1"))

        fsm.act("CA_WORD1",
                NextValue(dq_out, ca[16:32]),
                NextState("CA_WORD2"))

        fsm.act("CA_WORD2",
                NextValue(dq_out, ca[0:16]),
                NextState("SELECT_OP"))

        fsm.act("SELECT_OP",
                NextValue(dq_out, 0),
                If(ca[47] == 1,
                   # Read operation
                   NextValue(dlycnt, phy.tx_latency + phy.rx_latency),
                   NextState("READ_DELAY")
                ).Elif(ca[46] == 1,
                   # Zero latency write to register
                   NextState("END_WRITE"),
                   If(initial_cr0_write == 1,
                      NextValue(dq_out, cr0_value)
                   ).Else(
                      NextValue(dq_out, port.wdata.data),
                      port.wdata.ready.eq(1),
                      If(port.wdata.last == 0, NextState("WRITE_REG")))
                ).Else(
                   # Normal write, wait for RWDS direction change
                   NextValue(dlycnt, phy.tx_latency),
                   NextState("WRITE_DELAY")
                ))

        fsm.act("WRITE_DELAY",
                NextValue(rwds_oe, 1),
                If(1 if fixed_latency else rwds_in[1],
                   NextValue(dlycnt, 2*initial_latency-1-2-phy.tx_latency)
                ).Else(
                   NextValue(dlycnt, initial_latency-1-2-phy.tx_latency)
                ),
                NextState("WRITE"))

        fsm.act("WRITE",
                NextValue(dq_out, port.wdata.data),
                NextValue(rwds_out, ~port.wdata.we),
                If(dlycnt == 0, port.wdata.ready.eq(1)),
                If(port.wdata.last == 1, NextState("END_WRITE")))

        fsm.act("WRITE_REG",
                NextValue(dq_out, port.wdata.data),
                port.wdata.ready.eq(1),
                If(port.wdata.last == 1, NextState("END_WRITE")))

        fsm.act("END_WRITE",
                NextValue(ck, 0),
                NextValue(rwds_out, 0b11),
                NextValue(dlycnt, phy.tx_latency),
                NextState("END_READ"))

        fsm.act("READ_DELAY",
                NextValue(dq_oe, 0),
                If(1 if fixed_latency else rwds_in[0],
                   NextValue(dlycnt, 2 * initial_latency)
                ).Else(
                   NextValue(dlycnt, initial_latency)
                ),
                NextState("READ"))

        fsm.act("READ",
                If(rwds_in[1],
                   If(dlycnt == 0, port.rdata.valid.eq(1)),
                   If(port.rdata.last == 1,
                      NextValue(ck, 0),
                      NextValue(dlycnt, phy.tx_latency),
                      NextState("END_READ"))))

        fsm.act("END_READ",
                NextValue(rwds_oe, 0),
                NextValue(cs_b, 1),
                NextState("IDLE"))

        fsm.act("IDLE",
                If(((initial_cr0_write == 1) & (ca[35] == 0)) if dual_die else 0,
                   # Repeat config for second die
                   NextValue(ca[35], 1),
                   NextState("CA_WORD0")
                ).Else(
                   NextValue(initial_cr0_write, 0),
                   port.cmd.ready.eq(1),
                   If(port.cmd.valid,
                      NextValue(ca[47], ~port.cmd.we),
                      NextValue(ca[46], port.cmd.aspace),
                      NextValue(ca[45], port.cmd.burst_type),
                      NextValue(ca[16:45], port.cmd.addr[3:32]),
                      NextValue(ca[0:3], port.cmd.addr[0:3]),
                      NextState("CA_WORD0"))))
