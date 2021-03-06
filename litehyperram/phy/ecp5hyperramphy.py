# This file is Copyright (c) 2021 Marcus Comstedt <marcus@mc.pp.se>
# License: BSD

# Lattice ECP5 HyperRAM PHY -----------------------------------------------------------------------------

# The following DDR PHY has built-in latencies.  The time from dq_d being
# sampled to it appearing on dq is 2 clocks for A data and 2.5 clocks for
# B data.  The same applies to rwds.  The following wavedrom diagram shows
# the exact timing:
#
# {signal: [
#  {name: 'clk', wave: 'P......', period: 2},
#  {name: 'dq_da', wave: 'x35x...', period: 2, data: ["D0A", "D1A"], node:'..A'},
#  {name: 'dq_db', wave: 'x47x...', period: 2, data: ["D0B", "D1B"]},
#  {name: 'clk_enable', wave: '01.0...', period: 2},
#  {},
#  {name: 'dq', wave: 'x.......3457x.', data: ["D0A", "D0B", "D1A", "D1B"], node:'........BC'},
#  {name: 'ck', wave: '0........HLHL.', phase: 0.5},
#  {node: '....D...E'},
#  {node: '....F....G'}],
#  edge: ['A-F', 'B-E', 'C-G', 'D<-|->E 2 Tclk', 'F<-|->G 2.5 Tclk']}
#
# For input, the corresponding latencies is 1.5 clocks for A data and
# 1 clock for B data, as shown in the following diagram:
# 
# {signal: [
#  {name: 'clk', wave: 'P....', period: 2},
#  {name: 'clk_enable', wave: '10...', period: 2},
#  {},
#  {name: 'ck', wave: 'lHLHLHLHL.', phase: 0.5},
#  {name: 'dq', wave: 'x3457x....', phase: 0.5, data: ["D0A", "D0B", "D1A", "D1B"]},
#  {node: '.AB.C'},
#  {name: 'dq_qa', wave: 'x.35x', period: 2, data: ["D0A", "D1A"]},
#  {name: 'dq_qb', wave: 'x.47x', period: 2, data: ["D0B", "D1B"]},
#  {node: '..D.E'},
#  {node: '.F..G'}],
#  edge: ['A-F', 'B-D', 'C-G', 'D<-|->E 1 Tclk', 'F<-|->G 1.5 Tclk']}

from migen import *
from migen.fhdl.specials import Tristate

class ECP5HYPERRAMPHY(Module):
    def __init__(self, pads, sys_clk_freq=100e6):

        self.tx_latency = 2
        self.rx_latency = 1

        self.clk_enable = Signal()
        self.pll_locked = Signal()

        self.rwds_da = Signal()
        self.rwds_db = Signal()
        self.rwds_qa = Signal()
        self.rwds_qb = Signal()
        self.dq_da = Signal(8)
        self.dq_db = Signal(8)
        self.dq_qa = Signal(8)
        self.dq_qb = Signal(8)
        self.rwds_oe = Signal()
        self.dq_oe = Signal()
        self.cs_n = pads.cs_n
        if hasattr(pads, "reset_n"):
            self.reset_n = pads.reset_n
        elif hasattr(pads, "rst_n"):
            self.reset_n = pads.rst_n
        else:
            self.reset_n = Signal()

        rx_q0 = [self.dq_qa[i] for i in range(8)] + [self.rwds_qa]
        rx_q1 = [self.dq_qb[i] for i in range(8)] + [self.rwds_qb]
        tx_d0 = [self.dq_da[i] for i in range(8)] + [self.rwds_da]
        tx_d1 = [self.dq_db[i] for i in range(8)] + [self.rwds_db]
        oe = [self.dq_oe] * 8 + [self.rwds_oe]

        # Clock output is delayed 90 degrees to convert TX aligned and RX
        # centered into TX centered and RX aligned from the perspective of
        # the external slave
        self.clock_domains.phi90 = ClockDomain()
        div = 550000000 // sys_clk_freq;
        if div > 128:
            raise ValueError("Clock too slow, can't generate EHXPLLL")
        op_phase_x8 = div * 4 # 180 degrees
        os_phase_x8 = div * 6 # 270 degrees
        self.specials += Instance("EHXPLLL",
            i_RST   = ResetSignal(),
            i_STDBY = 0,
            i_CLKI  = ClockSignal(),
            o_CLKOS = self.phi90.clk,
            o_LOCK  = self.pll_locked,
            p_CLKOP_ENABLE = "DISABLED",
            p_CLKOS_ENABLE = "ENABLED",
	    p_CLKOP_DIV    = div,
            p_CLKOP_CPHASE = op_phase_x8 >> 3,
	    p_CLKOP_FPHASE = op_phase_x8 & 7,
	    p_CLKOS_DIV    = div,
            p_CLKOS_CPHASE = os_phase_x8 >> 3,
	    p_CLKOS_FPHASE = os_phase_x8 & 7,
            p_FEEDBK_PATH  = "INT_OP",
            p_CLKFB_DIV    = 1,
            p_CLKI_DIV     = 1)
        clk_enable_dly = Signal()
        self.sync.phi90 += clk_enable_dly.eq(self.clk_enable)
        self.specials += Instance("ODDRX1F",
            i_SCLK = self.phi90.clk,
            i_RST  = ResetSignal(),
            i_D0   = clk_enable_dly,
            i_D1   = 0,
            o_Q    = pads.ck_p if hasattr(pads, "ck_p") else pads.clk)

        for i in range(9):
            d = Signal()
            q = Signal()
            self.specials += [
                Tristate(pads.dq[i] if i < 8 else pads.rwds, q, oe[i], d),
                Instance("IDDRX1F",
                    i_SCLK = ClockSignal(),
                    i_RST  = ResetSignal(),
                    i_D    = d,
                    o_Q0   = rx_q0[i],
                    o_Q1   = rx_q1[i]),
                Instance("ODDRX1F",
                    i_SCLK = ClockSignal(),
                    i_RST  = ResetSignal(),
                    i_D0   = tx_d0[i],
                    i_D1   = tx_d1[i],
                    o_Q    = q)
            ]

        # Assume PSC is not needed (non DCARS part)
        if hasattr(pads, "psc_p"):
            self.comb += pads.psc_p.eq(0)



class ECP5HYPERRAMPHY2x(Module):
    def __init__(self, pads):

        self.tx_latency = 3
        self.rx_latency = 2

        self.clk_enable = Signal()
        self.pll_locked = Signal(reset=1)

        self.rwds_da = Signal()
        self.rwds_db = Signal()
        self.rwds_dc = Signal()
        self.rwds_dd = Signal()
        self.rwds_qa = Signal()
        self.rwds_qb = Signal()
        self.rwds_qc = Signal()
        self.rwds_qd = Signal()
        self.rwds_qa_wa = Signal()
        self.rwds_qb_wa = Signal()
        self.rwds_qc_wa = Signal()
        self.rwds_qd_wa = Signal()
        self.dq_da = Signal(8)
        self.dq_db = Signal(8)
        self.dq_dc = Signal(8)
        self.dq_dd = Signal(8)
        self.dq_qa = Signal(8)
        self.dq_qb = Signal(8)
        self.dq_qc = Signal(8)
        self.dq_qd = Signal(8)
        self.dq_qa_wa = Signal(8)
        self.dq_qb_wa = Signal(8)
        self.dq_qc_wa = Signal(8)
        self.dq_qd_wa = Signal(8)
        self.rwds_oe = Signal()
        self.dq_oe = Signal()
        self.cs_n = pads.cs_n
        if hasattr(pads, "reset_n"):
            self.reset_n = pads.reset_n
        elif hasattr(pads, "rst_n"):
            self.reset_n = pads.rst_n
        else:
            self.reset_n = Signal()

        rx_q0 = [self.dq_qa_wa[i] for i in range(8)] + [self.rwds_qa_wa]
        rx_q1 = [self.dq_qb_wa[i] for i in range(8)] + [self.rwds_qb_wa]
        rx_q2 = [self.dq_qc_wa[i] for i in range(8)] + [self.rwds_qc_wa]
        rx_q3 = [self.dq_qd_wa[i] for i in range(8)] + [self.rwds_qd_wa]
        tx_d0 = [self.dq_da[i] for i in range(8)] + [self.rwds_da]
        tx_d1 = [self.dq_db[i] for i in range(8)] + [self.rwds_db]
        tx_d2 = [self.dq_dc[i] for i in range(8)] + [self.rwds_dc]
        tx_d3 = [self.dq_dd[i] for i in range(8)] + [self.rwds_dd]
        oe = [self.dq_oe] * 8 + [self.rwds_oe]

	# Align read data so that the first word with RWDS set on
	# the negative edge of CK becomes the high word
        word_align = Signal()
        rwds_qc_save = Signal(8)
        rwds_qd_save = Signal(8)
        dq_qc_save = Signal(8)
        dq_qd_save = Signal(8)
        self.comb += \
            If(word_align,
                self.dq_qa.eq(dq_qc_save),
                self.dq_qb.eq(dq_qd_save),
                self.dq_qc.eq(self.dq_qa_wa),
                self.dq_qd.eq(self.dq_qb_wa),
                self.rwds_qa.eq(rwds_qc_save),
                self.rwds_qb.eq(rwds_qd_save),
                self.rwds_qc.eq(self.rwds_qa_wa),
                self.rwds_qd.eq(self.rwds_qb_wa),
            ).Elif(self.rwds_qc_wa & ~self.rwds_qa_wa,
                self.dq_qa.eq(0),
                self.dq_qb.eq(0),
                self.dq_qc.eq(0),
                self.dq_qd.eq(0),
                self.rwds_qa.eq(0),
                self.rwds_qb.eq(0),
                self.rwds_qc.eq(0),
                self.rwds_qd.eq(0)
            ).Else(
                self.dq_qa.eq(self.dq_qa_wa),
                self.dq_qb.eq(self.dq_qb_wa),
                self.dq_qc.eq(self.dq_qc_wa),
                self.dq_qd.eq(self.dq_qd_wa),
                self.rwds_qa.eq(self.rwds_qa_wa),
                self.rwds_qb.eq(self.rwds_qb_wa),
                self.rwds_qc.eq(self.rwds_qc_wa),
                self.rwds_qd.eq(self.rwds_qd_wa)
            )
        self.sync += [
            If(word_align,
               If(~self.rwds_qc_wa, word_align.eq(0))
            ).Elif(self.rwds_qc_wa & ~self.rwds_qa_wa,
               word_align.eq(1)
            ),
            dq_qc_save.eq(self.dq_qc_wa),
            dq_qd_save.eq(self.dq_qd_wa),
            rwds_qc_save.eq(self.rwds_qc_wa),
            rwds_qd_save.eq(self.rwds_qd_wa)
        ]

        clk = Signal()
        self.specials += [
            Instance("ODDRX2F",
                i_SCLK = ClockSignal("sys"),
                i_ECLK = ClockSignal("sys2x_90"),
                i_RST  = ResetSignal("sys"),
                i_D0   = 0,
                i_D1   = self.clk_enable,
                i_D2   = 0,
                i_D3   = self.clk_enable,
                o_Q    = clk
            ),
            Instance("DELAYF",
                p_DEL_MODE  = "ECLK_ALIGNED",
                i_A         = clk,
                o_Z         = pads.ck_p if hasattr(pads, "ck_p") else pads.clk
            )
        ]
        for i in range(9):
            d = Signal()
            q = Signal()
            d_delayed = Signal()
            self.specials += [
                Tristate(pads.dq[i] if i < 8 else pads.rwds, q, oe[i], d),
                Instance("DELAYF",
                    p_DEL_MODE  = "ECLK_CENTERED",
                    i_A         = d,
                    o_Z         = d_delayed
                ),
                Instance("IDDRX2F",
                    i_SCLK = ClockSignal("sys"),
                    i_ECLK = ClockSignal("sys2x"),
                    i_RST  = ResetSignal("sys"),
                    i_D    = d_delayed,
                    o_Q0   = rx_q0[i],
                    o_Q1   = rx_q1[i],
                    o_Q2   = rx_q2[i],
                    o_Q3   = rx_q3[i]
                ),
                Instance("ODDRX2F",
                    i_SCLK = ClockSignal("sys"),
                    i_ECLK = ClockSignal("sys2x"),
                    i_RST  = ResetSignal("sys"),
                    i_D0   = tx_d0[i],
                    i_D1   = tx_d1[i],
                    i_D2   = tx_d2[i],
                    i_D3   = tx_d3[i],
                    o_Q    = q
                )
            ]

        # Assume PSC is not needed (non DCARS part)
        if hasattr(pads, "psc_p"):
            self.comb += pads.psc_p.eq(0)
