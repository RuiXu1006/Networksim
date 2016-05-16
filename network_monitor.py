#
# network_monitor.py - monitor phase change of variables in the netowrk simulator
#

import network

class Network_monitor(object):
    
    def __init__(self, network):
        self.network = network
        self.lat_cnt = 0
        self.lat_seq = []
        self.flits_received_cnt = 0
        self.starv_cnt = 0
        self.starv_rate = []

    def monitor_lat(self, period):
        if (self.network.clock_cycles % period == 0):
            cur_total_latency = 0
            cur_flits_received = 0
            for s in self.network.targets:
                cur_total_latency  += s.total_latency
                cur_flits_received += s.pkt_count
            if (cur_flits_received - self.flits_received_cnt != 0):
                cur_latency = (float)(cur_total_latency - self.lat_cnt) / (float)(cur_flits_received -self.flits_received_cnt)
                self.lat_seq.append(cur_latency)
            else:
                self.lat_seq.append(0.0)

            self.lat_cnt = cur_total_latency
            self.flits_received_cnt = cur_flits_received

    def monitor_starv_rate(self, period):
        if (self.network.clock_cycles % period == 0):
            for port in self.network.inj_source_ports:
                if 'S' in port.name:
                    cur_starv_cnt = port.starv_cnt - self.starv_cnt
                    self.starv_rate.append(cur_starv_cnt)
                    self.starv_cnt = port.starv_cnt


    
