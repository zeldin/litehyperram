# This file is Copyright (c) 2021 Marcus Comstedt <marcus@mc.pp.se>
# License: BSD

class HyperRAMModule:
    max_initial_latency = 6

    def __init__(self):
        pass

    def min_initial_latency(self, clk_freq):
        return (3 if clk_freq <= 83000000 else
                4 if clk_freq <= 100000000 else
                5 if clk_freq <= 133000000 else
                6 if clk_freq <= 166000000 else
		7)

class S27KL0641DA(HyperRAMModule):
    maxclock = 100000000
    nbanks = 1
    nrows = 8192
    ncols = 512

class S27KL0641(S27KL0641DA):
    pass

class S70KL1281DA(HyperRAMModule):
    maxclock = 100000000
    nbanks = 2
    nrows = 8192
    ncols = 512

class S70KL1281(S70KL1281DA):
    pass

class S27KS0641DP(HyperRAMModule):
    maxclock = 166000000
    nbanks = 1
    nrows = 8192
    ncols = 512

class S27KS0641(S27KS0641DP):
    pass

class S70KS1281DP(HyperRAMModule):
    maxclock = 166000000
    nbanks = 2
    nrows = 8192
    ncols = 512

class S70KS1281(S70KS1281DP):
    pass

class S27KS0641DA(HyperRAMModule):
    maxclock = 100000000
    nbanks = 1
    nrows = 8192
    ncols = 512

class S70KS1281DA(HyperRAMModule):
    maxclock = 100000000
    nbanks = 2
    nrows = 8192
    ncols = 512

class S27KS0641DG(HyperRAMModule):
    maxclock = 133000000
    nbanks = 1
    nrows = 8192
    ncols = 512

class S70KS1281DG(HyperRAMModule):
    maxclock = 133000000
    nbanks = 2
    nrows = 8192
    ncols = 512

class S70KL1282DP(HyperRAMModule):
    maxclock = 166000000
    max_initial_latency = 7
    nbanks = 2
    nrows = 8192
    ncols = 512

class S70KL1282GA(HyperRAMModule):
    maxclock = 200000000
    max_initial_latency = 7
    nbanks = 2
    nrows = 8192
    ncols = 512
    
class S70KS1282GA(HyperRAMModule):
    maxclock = 200000000
    max_initial_latency = 7
    nbanks = 2
    nrows = 8192
    ncols = 512

class S70KS1282(S70KS1282GA):
    pass
