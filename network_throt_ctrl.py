#
# network_throt_ctrl.py - control when/how to throttle the bandwidth of IO
#
# rui 05/13/16
#

import network

class Network_throt_ctrl(object):
    def __init__(self, util, injector):
        self.cur_starv  = 0
        self.pre_starv  = 0
        self.pre_cnt = 0
        self.injector = injector
        self.tgt_injector = injector
        self.util_seq = [0]
        self.starv_cnt = [0]
        self.uncongested_cnt = 0
        self.util_limit = injector.util

    def assign_target_injector(self, injector):
        self.tgt_injector = injector
        print self.tgt_injector.name

    def is_congested(self):
        if (self.cur_starv == 0 and self.pre_starv == 0):
            self.pre_starv = self.tgt_injector.source_port.starv_cnt
            self.pre_cnt = self.tgt_injector.source_port.starv_cnt
            return False

        self.cur_starv = self.tgt_injector.source_port.starv_cnt - self.pre_cnt;
        self.pre_cnt = self.tgt_injector.source_port.starv_cnt
        if (self.cur_starv > 20):
            self.pre_starv = self.cur_starv;
            print "congested"
            return True
        else:
            self.pre_starv = self.cur_starv;
            return False

    def adjust_util(self):
        if self.is_congested():
            self.injector.util *= 0.9
            self.util_seq.append(self.injector.util)
            self.starv_cnt.append(self.cur_starv)
            self.injector.tgt_inj = self.injector.util / self.injector.flits
            self.uncongested_cnt = 0
        else:
            self.uncongested_cnt += 1
            if self.uncongested_cnt >= 3:
                if self.injector.util*1.05 < self.util_limit:
                    self.injector.util *= 1.05
                self.injector.tgt_inj = self.injector.util / self.injector.flits
            self.util_seq.append(self.injector.util)
            self.starv_cnt.append(self.cur_starv)
