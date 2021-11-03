# This file is Copyright (c) 2021 Marcus Comstedt <marcus@mc.pp.se>
# License: BSD

from migen import *

from litex.soc.interconnect import stream


# LiteHyperRAMWishbone2Native --------------------------------------------------------------------------

class LiteHyperRAMWishbone2Native(Module):
    def __init__(self, wishbone, port, base_address=0x00000000):
        wishbone_data_width = len(wishbone.dat_w)
        port_data_width     = len(port.wdata.data)
        assert wishbone_data_width >= port_data_width

        adr_offset = base_address >> log2_int(port.data_width//8)

        # Write Datapath ---------------------------------------------------------------------------
        wdata_converter = stream.StrideConverter(
            [("data", wishbone_data_width), ("we", wishbone_data_width//8)],
            [("data", port_data_width),     ("we", port_data_width//8)],
        )
        self.submodules += wdata_converter
        self.comb += [
            wdata_converter.sink.valid.eq(wishbone.cyc & wishbone.stb & wishbone.we),
            wdata_converter.sink.data.eq(wishbone.dat_w),
            wdata_converter.sink.we.eq(wishbone.sel),
            wdata_converter.sink.last.eq(1),
            wdata_converter.source.connect(port.wdata)
        ]

        # Read Datapath ----------------------------------------------------------------------------
        rdata_converter = stream.StrideConverter(
            [("data", port_data_width)],
            [("data", wishbone_data_width)],
        )
        self.submodules += rdata_converter
        self.comb += [
            port.rdata.connect(rdata_converter.sink),
            rdata_converter.source.ready.eq(1),
            wishbone.dat_r.eq(rdata_converter.source.data),
        ]

        # Control ----------------------------------------------------------------------------------
        ratio = wishbone_data_width//port_data_width
        count = Signal(max=max(ratio, 2))
        self.comb += [
            port.cmd.we.eq(wishbone.we),
            port.cmd.aspace.eq(0),
            port.cmd.burst_type.eq(1),
            port.cmd.addr.eq(wishbone.adr*ratio - adr_offset)
        ]
        self.submodules.fsm = fsm = FSM(reset_state="CMD")
        fsm.act("CMD",
            port.cmd.valid.eq(wishbone.cyc & wishbone.stb),
            If(port.cmd.valid & port.cmd.ready,
               If(wishbone.we,
                  NextState("WAIT-WRITE")
               ).Else(
                  NextValue(count, 0),
                  NextState("WAIT-READ")
               )
            )
        )
        fsm.act("WAIT-WRITE",
            If(wdata_converter.sink.ready,
                wishbone.ack.eq(1),
                NextState("CMD")
            )
        )
        fsm.act("WAIT-READ",
            port.rdata.last.eq(count == (ratio - 1)),
            If(port.rdata.valid, NextValue(count, count + 1)),
            If(rdata_converter.source.valid,
               wishbone.ack.eq(1),
               NextState("CMD")
            )
        )
