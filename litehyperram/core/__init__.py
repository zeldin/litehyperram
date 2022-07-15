from migen import *

from litehyperram.common import LiteHyperRAMNativePort
from litehyperram.core.controller import LiteHyperRAMController
from litehyperram.core.registerspace import LiteHyperRAMRegisterSpace
from litehyperram.core.crossbar import LiteHyperRAMCrossbar
from litex.soc.interconnect.csr import AutoCSR

class LiteHyperRAMCore(Module, AutoCSR):
    def __init__(self, phy, module, clk_freq, **kwargs):
        self.submodules.controller = LiteHyperRAMController(
            phy = phy, module = module, clk_freq = clk_freq, **kwargs)
        data_port = LiteHyperRAMNativePort.like(self.controller.port)
        reg_port = LiteHyperRAMNativePort.like(self.controller.port)
        self.submodules.register_space = LiteHyperRAMRegisterSpace(
            initial_latency = self.controller.initial_latency,
            fixed_latency = self.controller.fixed_latency,
            nbanks = module.nbanks, port = reg_port)
        self.submodules.crossbar = LiteHyperRAMCrossbar(
            self.controller.port, data_port, reg_port)
        self.comb += self.crossbar.lockout.eq(~self.register_space.setup_done)
        if data_port.data_width == 32:
            self.data_port = LiteHyperRAMNativePort(data_port.address_width-1,
                                                    data_port.data_width)
            self.comb += [
               self.data_port.cmd.connect(data_port.cmd, omit=["addr"]),
               data_port.cmd.addr.eq(Cat(C(0, 1), self.data_port.cmd.addr)),
               self.data_port.wdata.connect(data_port.wdata),
               data_port.rdata.connect(self.data_port.rdata, omit=["last"]),
               data_port.rdata.last.eq(self.data_port.rdata.last)
            ]
        else:
            self.data_port = data_port

    def get_port(self):
        return self.data_port
