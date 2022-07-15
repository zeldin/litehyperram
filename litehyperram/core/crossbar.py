# This file is Copyright (c) 2022 Marcus Comstedt <marcus@mc.pp.se>
# License: BSD

from migen import *

class LiteHyperRAMCrossbar(Module):
    def __init__(self, controller_port, data_port, reg_port):

        self.lockout = Signal()
        reg_select = Signal(reset = 1)

        self.sync += [
            If(~self.lockout & controller_port.cmd.ready & ~reg_port.cmd.valid,
               reg_select.eq(0)),
            If(controller_port.cmd.ready & reg_port.cmd.valid & ~data_port.cmd.valid,
               reg_select.eq(1))
        ]

        self.comb += [
            If(reg_select,
               reg_port.cmd.connect(controller_port.cmd),
               reg_port.wdata.connect(controller_port.wdata),
               controller_port.rdata.connect(reg_port.rdata, omit=["last"]),
               controller_port.rdata.last.eq(reg_port.rdata.last),
               data_port.cmd.ready.eq(0),
               data_port.wdata.ready.eq(0),
               data_port.rdata.valid.eq(0)
            ).Else(
               data_port.cmd.connect(controller_port.cmd),
               data_port.wdata.connect(controller_port.wdata),
               controller_port.rdata.connect(data_port.rdata, omit=["last"]),
               controller_port.rdata.last.eq(data_port.rdata.last),
               reg_port.cmd.ready.eq(0),
               reg_port.wdata.ready.eq(0),
               reg_port.rdata.valid.eq(0))
        ]
