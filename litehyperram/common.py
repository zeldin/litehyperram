from migen import *

from litex.soc.interconnect import stream

def cmd_description(address_width):
    return [
        ("we",         1),
        ("aspace",     1),
        ("burst_type", 1),
        ("addr",       address_width)
    ]

def wdata_description(data_width):
    return [
        ("data", data_width),
        ("we",   data_width//8)
    ]

def rdata_description(data_width):
    return [("data", data_width)]

class LiteHyperRAMNativePort:
    def __init__(self, address_width, data_width=16):
        self.cmd   = stream.Endpoint(cmd_description(address_width))
        self.wdata = stream.Endpoint(wdata_description(data_width))
        self.rdata = stream.Endpoint(rdata_description(data_width))
        self.address_width = address_width
        self.data_width = data_width
