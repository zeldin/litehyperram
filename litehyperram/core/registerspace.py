# This file is Copyright (c) 2022 Marcus Comstedt <marcus@mc.pp.se>
# License: BSD

from litex.soc.interconnect.csr import AutoCSR, CSR, CSRAccess, CSRField
from litex.soc.interconnect.csr import CSRFieldAggregate, CSRStatus
from migen import *

class LiteHyperRAMRegisterSpace(Module, AutoCSR):

    il_code = { 3: 0b1110, 4: 0b1111, 5: 0b0000, 6: 0b0001, 7: 0b0010 }

    def __init__(self, initial_latency, fixed_latency, nbanks, port):

        cr0_value = (0x8f07 | (self.il_code[initial_latency] << 4) |
                     (0x0008 if fixed_latency else 0))

        self.setup_done = Signal(reset = 0)

        idle = Signal()
        decrement_die_nr = Signal()

        self.access = access = CSR(32)
        access.description= "Register space access control. " + \
            "Can only be written when no operation is in progress."
        access.fields = CSRFieldAggregate([
            CSRField("reg_value", 16, reset = cr0_value,
                description="Value to write to register, or result of read."),
            CSRField("reg_nr", 3, values=[
                ("``0b0``", "Register number 0."),
                ("``0b1``", "Register number 1."),
            ]),
            CSRField("reg_type", 8, reset = 1, values=[
                ("``0b0``", "Identification Register."),
                ("``0b1``", "Configuration Register.")
            ]),
            CSRField("die_nr", 2, reset = nbanks-1,
                description="Number of the die to access."),
            CSRField("we", offset = 29, reset = 1, values=[
                ("``0b0``", "Read operation."),
                ("``0b1``", "Write operation.")
            ]),
            CSRField("strobe", offset = 30, pulse = True,
                description="Write ``1`` to perform read/write."),
            CSRField("busy", offset = 31, access = CSRAccess.ReadOnly,
                description="Operation in progress (when read as ``1``).")
        ], CSRAccess.ReadWrite)

        self.comb += [
            port.cmd.we.eq(access.fields.we),
            port.cmd.aspace.eq(1),
            port.cmd.burst_type.eq(1),
            port.cmd.addr.eq(Cat(access.fields.reg_nr, C(0, 8),
                                 access.fields.reg_type, C(0, 3),
                                 access.fields.die_nr)),
            port.wdata.data.eq(access.fields.reg_value),
            port.wdata.last.eq(1),
            port.rdata.last.eq(1),
            access.fields.busy.eq(~idle),
            [access.w[field.offset:field.offset+field.size].eq(field)
             for field in access.fields.fields]
        ]

        self.sync += [
            If(access.re & idle,
               [field.eq(access.r[field.offset:field.offset+field.size])
                for field in access.fields.fields
                if field.access != CSRAccess.ReadOnly]
            ).Else(
               access.fields.strobe.eq(0),
               If(port.rdata.valid,
                  access.fields.reg_value.eq(port.rdata.data[-16:])),
               If(decrement_die_nr,
                  access.fields.die_nr.eq(access.fields.die_nr - 1))
            )
        ]

        self.submodules.fsm = fsm = FSM(reset_state="START")

        fsm.act("START",
                idle.eq(self.setup_done),
                If(~self.setup_done | access.fields.strobe,
                   NextState("WAIT_CMD")))

        fsm.act("WAIT_CMD",
                port.cmd.valid.eq(1),
                If(port.cmd.ready,
                   If(access.fields.we,
                      NextState("WAIT_WRITE")
                   ).Else(NextState("WAIT_READ"))))

        fsm.act("WAIT_WRITE",
                port.wdata.valid.eq(1),
                If(port.wdata.ready,
                   If(~self.setup_done,
                      If(access.fields.die_nr == 0,
                         NextValue(self.setup_done, 1)
                      ).Else(
                         decrement_die_nr.eq(1))),
                   NextState("START")))

        fsm.act("WAIT_READ",
                port.rdata.ready.eq(1),
                If(port.rdata.valid, NextState("START")))
