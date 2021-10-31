# This file is Copyright (c) 2021 Marcus Comstedt <marcus@mc.pp.se>
# License: BSD

# Lattice ECP5 HyperRAM PHY -----------------------------------------------------------------------------

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
        else:
            self.reset_n = Signal()

        rx_q0 = Cat(*self.dq_qa, self.rwds_qa)
        rx_q1 = Cat(*self.dq_qb, self.rwds_qb)
        tx_d0 = Cat(*self.dq_da, self.rwds_da)
        tx_d1 = Cat(*self.dq_db, self.rwds_db)
        oe = Cat(*Replicate(self.dq_oe, 8), self.rwds_oe)

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
            o_Q    = pads.ck_p)

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
