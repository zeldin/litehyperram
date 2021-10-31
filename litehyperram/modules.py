class HyperRAMModule:
    def __init__(self):
        pass

    def min_initial_latency(self, clk_freq):
        return (3 if clk_freq <= 83000000 else
                4 if clk_freq <= 100000000 else
                5 if clk_freq <= 133000000 else
                6)

class S70KL0641(HyperRAMModule):
    maxclock = 100000000
    nbanks = 1
    nrows = 8192
    ncols = 512

class S70KL1281(HyperRAMModule):
    maxclock = 100000000
    nbanks = 2
    nrows = 8192
    ncols = 512

class S70KS0641(HyperRAMModule):
    maxclock = 166000000
    nbanks = 1
    nrows = 8192
    ncols = 512

class S70KS1281(HyperRAMModule):
    maxclock = 166000000
    nbanks = 2
    nrows = 8192
    ncols = 512
