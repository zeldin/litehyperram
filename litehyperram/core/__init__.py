from migen import *

from litehyperram.core.controller import LiteHyperRAMController

class LiteHyperRAMCore(Module):
    def __init__(self, phy, module, clk_freq, **kwargs):
        self.submodules.controller = LiteHyperRAMController(
            phy = phy, module = module, clk_freq = clk_freq, **kwargs)

    def get_port(self):
        return self.controller.port

