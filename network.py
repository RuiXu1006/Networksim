#
# netsim.py - basic mesh simulator for performance analysis
#
# cramey 11/14/14
#
#

import random
import numpy
import network_throt_ctrl
import network_monitor

PRT_NORTH = 0
PRT_SOUTH = 1
PRT_EAST  = 2
PRT_WEST  = 3
PRT_CORE  = 4

ROUTE_DOR = 0
ROUTE_OE = 1 # cramey 12/19/14 - I don't think this "OddEven" router is quite right yet, but close. Needs some debug.

ROUTE_X_FIRST = 0
ROUTE_Y_FIRST = 1

# 0 represents routers, 1 represetns network pipeline
TYPE_ROUTER  = 0
TYPE_NETPIPE = 1

DIST_UNIFORM = 0
DIST_POISSON = 1
DIST_NORMAL  = 2

RANDOM = 0

INJECTOR_FIFO_DEPTH = 50000

# provide complete route history on every packet (used for debugging mostly)
debug_full_hist = True

# provide stats on blocking/fifo-empty
detailed_ib_stats = True

# provide stats on how often we can route to an alternate port
track_amr_stats = False

allow_adaptive_route = False

class Network(object):
    def __init__(self, dim_x=5, dim_y=5, network_pipe_stage=3, credit=1,fifo_depth=10,route_method=ROUTE_X_FIRST, 
                 network_priority_arb=True, use_timewheel=True,                 
                 toroid=False, strict_priority_straight_through=False,
                 unidir_toroid=False):
        global current_time
        
        self.size = (dim_x, dim_y)

        self.network_pipe_stage = network_pipe_stage
        self.fifo_depth = fifo_depth
        self.flits_sent = 0
        self.flits_received = 0
        self.total_latency = 0
        self.max_latency = 0
        self.injectors = []
        self.routers  = []
        self.netpipes = []
        self.targets = []
        self.inj_source_ports = []
        current_time = 0
        self.sample_start_time = 1
        self.track_history = True
        self.use_timewheel = use_timewheel
        self.time_wheel = {}
        self.npa = network_priority_arb
        self.spa_straight = strict_priority_straight_through
        self.route_method = route_method
        self.route_alg = ROUTE_DOR
        self.clip_inport_latency = 15
        self.toroid = toroid
        self.unidir_toroid = unidir_toroid
        self.clock_cycles = 0
        self.monitor = network_monitor.Network_monitor(self)
        self.monitor_period = 1000

        # for single row/col, don't wrap (cleans up appearence of ring and lets us add injectors)
        toroid_x = toroid and dim_x > 1
        toroid_y = toroid and dim_y > 1

        for x in range(dim_x):
            col = []
            for y in range(dim_y):
                col.append(Router([x,y], self, credit))
            self.routers.append(col)

        # generate network pipes for each router
        for x in range(dim_x):
            col = []
            for y in range(dim_y):
                grp = [];
                grp.append(NetPipe([x,y], 0, network_pipe_stage, self));
                grp.append(NetPipe([x,y], 1, network_pipe_stage, self));
                grp.append(NetPipe([x,y], 2, network_pipe_stage, self));
                grp.append(NetPipe([x,y], 3, network_pipe_stage, self));
                grp.append(NetPipe([x,y], 4, network_pipe_stage, self));
                col.append(grp) 
            self.netpipes.append(col)

        # assign output ports to their target input ports (or final target "stub")
        # assign input  ports to their source output ports
        # assign output ports and input ports to corresponding nettwork pipes
        for y in range(dim_y):
            for x in range(dim_x):
                if y > 0:
                    s = self.routers[x][y-1].input_ports[PRT_SOUTH]
                else:
                    if toroid_y:
                        s = self.routers[x][dim_y-1].input_ports[PRT_SOUTH]
                    else:
                        s = StubInputPort(name = "(%d,%d).S" % (x, y-1), coord = [x, y-1], port=PRT_SOUTH, network=self)
                        self.targets.append(s)

                p = self.netpipes[x][y][PRT_NORTH]
                p.assign_target_input_port(s)
                s.assign_target_output_port(self.routers[x][y].output_ports[PRT_NORTH])
                self.routers[x][y].output_ports[PRT_NORTH].assign_target_input_port(s)
                self.routers[x][y].output_ports[PRT_NORTH].assign_target_network_pipe(p)

                if y < (dim_y-1):
                    s = self.routers[x][y+1].input_ports[PRT_NORTH]
                else:
                    if toroid_y:
                        s = self.routers[x][0].input_ports[PRT_NORTH]
                    else:
                        s = StubInputPort(name = "(%d,%d).N" % (x, y+1), coord = [x, y+1], port=PRT_NORTH, network=self)
                        self.targets.append(s)

                p = self.netpipes[x][y][PRT_SOUTH]
                p.assign_target_input_port(s)
                s.assign_target_output_port(self.routers[x][y].output_ports[PRT_SOUTH])
                self.routers[x][y].output_ports[PRT_SOUTH].assign_target_input_port(s)
                self.routers[x][y].output_ports[PRT_SOUTH].assign_target_network_pipe(p)

                if x > 0:
                    s = self.routers[x-1][y].input_ports[PRT_EAST]
                else:
                    if toroid_x:
                        s = self.routers[dim_x-1][y].input_ports[PRT_EAST]
                    else:
                        s = StubInputPort(name = "(%d,%d).E" % (x-1, y), coord = [x-1, y], port=PRT_EAST, network=self)
                        self.targets.append(s)

                p = self.netpipes[x][y][PRT_WEST]
                p.assign_target_input_port(s)
                s.assign_target_output_port(self.routers[x][y].output_ports[PRT_WEST])
                self.routers[x][y].output_ports[PRT_WEST].assign_target_input_port(s)
                self.routers[x][y].output_ports[PRT_WEST].assign_target_network_pipe(p)

                if x < (dim_x-1):
                    s = self.routers[x+1][y].input_ports[PRT_WEST]
                else:
                    if toroid_x:
                        s = self.routers[0][y].input_ports[PRT_WEST]
                    else:
                        s = StubInputPort(name = "(%d,%d).W" % (x+1, y), coord = [x+1, y], port=PRT_WEST, network=self)
                        self.targets.append(s)

                p = self.netpipes[x][y][PRT_EAST]
                p.assign_target_input_port(s)
                s.assign_target_output_port(self.routers[x][y].output_ports[PRT_EAST])
                self.routers[x][y].output_ports[PRT_EAST].assign_target_input_port(s)
                self.routers[x][y].output_ports[PRT_EAST].assign_target_network_pipe(p)

                s = StubInputPort(name = "(%d,%d).C" % (x, y), coord = [x, y], port=PRT_CORE, network=self)
                self.targets.append(s)

                p = self.netpipes[x][y][PRT_CORE]
                p.assign_target_input_port(s)
                s.assign_target_output_port(self.routers[x][y].output_ports[PRT_CORE])
                self.routers[x][y].output_ports[PRT_CORE].assign_target_input_port(s)
                self.routers[x][y].output_ports[PRT_CORE].assign_target_network_pipe(p)

    def update_stats(self):
        global current_time
        self.flits_sent = 0
        self.flits_received = 0
        self.total_latency = 0
        self.max_latency = 0
        self.max_nw_latency = 0
        self.total_nw_latency = 0
        self.average_q = 0
        self.worst_q = 100
        actual_sent_tot = 0
        for i in self.injectors:
            self.flits_sent += i.pkt_count

        tot_q = 0
        for s in self.inj_source_ports:
            actual_sent_tot += s.get_sent_count()
            q = self.calc_q(s)
            if q < self.worst_q:
                self.worst_q = q
            tot_q += q

        if len(self.inj_source_ports):
            self.average_q = tot_q / len(self.inj_source_ports)
        else:
            self.average_q = 0

        samp_time = current_time - self.sample_start_time

        for t in self.targets:
            if not t.stats_are_reliable:
                print "\nWARNING: stats are not reliable on this target port (need more warmup w/ history enabled). %s" % t.name

            self.flits_received += t.pkt_count
            self.total_latency += t.total_latency
            self.total_nw_latency += t.total_nw_latency
            if t.max_latency > self.max_latency:
                self.max_latency = t.max_latency
            if t.max_nw_latency > self.max_nw_latency:
                self.max_nw_latency = t.max_nw_latency
        if len(self.inj_source_ports):
            self.actual_inj_rate = float(actual_sent_tot) / len(self.inj_source_ports) / samp_time
        else:
            self.actual_inj_rate = 0


    def calc_q(self, inj_port):
        """Calculate the "quality" metric on a port. This is the percentage
        of achieved bandwidth vs. what was desired"""
        global current_time
        samp_time = current_time - self.sample_start_time
        
        achieved = float(inj_port.get_sent_count()) / samp_time
        q = int(100 * achieved / inj_port.target_inj_rate)
        if q > 100:
            q = 100
        return q

    def dump_all_heads(self):
        """useful for finding deadlocks. Dumps the flit at the head of every FIFO."""
        for y in range(self.size[1]):
            for x in range(self.size[0]):
                for prt in self.routers[x][y].input_ports:
                    print "%s : " % prt.name,
                    e = prt.curr_entry()
                    if e:
                        e.dump()
                    else:
                        print ""

    def resize_input_ports(self, depth):
        for row in self.routers:
            for r in row:
                r.resize_input_ports(depth)

    def clear_stats(self):
        global current_time
        self.flits_sent = 0
        self.flits_received = 0
        self.total_latency = 0
        self.max_latency = 0
        self.total_nw_latency = 0
        self.max_nw_latency = 0
        for i in self.injectors:
            i.clear_stats()
        for t in self.targets:
            t.clear_stats()

        for row in self.routers:
            for r in row:
                r.clear_stats()
        
        self.sample_start_time = current_time

    def dump_stats(self, verbose=True):
        self.update_stats()
        print "sent:%-7d" % self.flits_sent,
        print "flits:%-7d" % self.flits_received,
        if self.flits_received:
                print " MaxLat:%-4d AvgLat:%-3d MaxNwLat:%-3d AvgNwLat:%-2d AvgInjRate:%0.2f AvgQ:%-3d WorstQ:%-3d BDP:%-3d" % \
                    (self.max_latency,
                     self.total_latency/self.flits_received,
                     self.max_nw_latency,
                     self.total_nw_latency/self.flits_received,
                     self.actual_inj_rate,
                     self.average_q,
                     self.worst_q,
                     self.average_q*self.total_latency/self.flits_received)

        if verbose:
            print "          Port : TargetInj : ActualInj : Q"
            print "       ========:===========:===========:====="
            
            samp_time = current_time - self.sample_start_time
            
            for s in self.inj_source_ports:
                achieved = float(s.get_sent_count()) / samp_time
                print "  %12s : %0.2f      : %0.2f      : %3d" % (s.name, s.target_inj_rate, achieved, self.calc_q(s))

    def dump(self, verbose=False):
        print "Injectors:"
        for i in self.injectors:
            i.dump()
        print "Targets:"
        for t in self.targets:
            t.dump()
        if verbose:
            print "Routers:"
            for row in self.routers:
                for r in row:
                    r.dump(verbose)
        self.dump_stats()
                    
    def verify_wheel(self):
        """Make sure no events got lost in the timewheel"""
        for k in self.time_wheel.keys():
            if k < current_time:
                raise AssertionError("Current time is %d but found %d in time wheel" % (current_time, k))        

    def step(self, num_steps=1, drain=False):
        global current_time
        while num_steps:
            if not drain:                
                if self.use_timewheel:
                    #self.verify_wheel()
                    if current_time in self.time_wheel:
                        for i in self.time_wheel.pop(current_time):
                            next_time = i.gen_step()
                            if next_time < 1:
                                raise AssertionError("next-time generated time in past %d" % next_time)       
                            self.add_to_timewheel(i, current_time + next_time)
                else: # can use simple per cycle probability-based generator
                    for i in self.injectors:
                        i.gen_step_simple()
        
            for row in self.netpipes:
                for r in row:
                    for buf in r:
                        buf.netpipe_step()

            for row in self.routers:
                for r in row:
                    r.route_step()

            # also used as 2nd step in adaptive routing
            if track_amr_stats or allow_adaptive_route:
                for row in self.routers:
                    for r in row:
                        r.amr_stat_calc()                

            #print self.netpipes[2][1][1].netbufs[0].fifo_count

            # update states of each router, injector and netpipe
            for row in self.routers:
                for r in row:
                    r.update_input_state()

            for row in self.routers:
                for r in row:
                    r.update_output_state()

            for inject in self.injectors:
                inject.update_state()
                
            for row in self.netpipes:
                for r in row:
                    for buf in r:
                        buf.update_state()
            
            for i in self.injectors:
                i.adjust_util()

            # monitor network behavior
            self.monitor.monitor_lat(self.monitor_period)
            self.monitor.monitor_starv_rate(self.monitor_period)

            num_steps -= 1
            current_time += 1
            self.clock_cycles += 1
            #print(self.clock_cycles, drain)

    def nw_empty(self):
        for row in self.routers:
            for r in row:
                for i in r.input_ports:
                    if i.fifo_count:
                        return False
        return True

    def drain(self):
        """Keep processing until all flits from the system have flushed out"""
        global current_time

       
        done = self.nw_empty()
        while not done:
            self.step(drain=True)
            done = self.nw_empty()
    
    def add_to_timewheel(self, obj, time):
        if time in self.time_wheel:
            self.time_wheel[time].append(obj)
        else:
            self.time_wheel[time] = [obj]
  

    def add_injector(self,name, src_x, src_y, src_prt, utilization, target_coord="TILES", flits=1, throt_ctrl=False):
        global current_time
        """Add a traffic source. Source is attached to x,y,prt at a target injection rate. The target
        can be TILES, ALL, or a list of [x,y] pairs"""
        if utilization == 0.0:
            return

        # Random Mode
        if target_coord == "TILES":
            target_coord = []
            for x in range(self.size[0]):
                for y in range(self.size[1]):
                    if (x != src_x) or (y != src_y) or (src_prt != PRT_CORE):
                        target_coord.append([x,y])
        elif target_coord == "ALL":
            target_coord = []
            for x in range(-1,self.size[0]+1):
                for y in range(-1,self.size[1]+1):
                    if (x != src_x) or (y != src_y) or (src_prt != PRT_CORE) or \
                            (x == -1) or (x == self.size[0]) or (y == -1) or (y == self.size[1]):
                        target_coord.append([x,y])

        # Neighbor traffic pattern, router(x, y) -> router((x+1)%dim_x,(y+1)%dim_y)
        elif target_coord == "NEIGHBOR":
                target_coord = []
                dst_x = (src_x + 1) % self.size[0]
                dst_y = (src_y + 1) % self.size[1]
                target_coord.append([dst_x, dst_y])

        # Transpose traffic pattern, router(x,y) -> router(y,x)
        elif target_coord == "TRANSPOSE":
                target_coord = []
                dst_x = src_y
                dst_y = src_x
                target_coord.append([dst_x, dst_y])

        # Tornado traffic pattern, router(x,y) -> router((x+dim_x/2)%dim_x,(y+dim_y/2)%dim_y)
        elif target_coord == "TORNADO":
                target_coord = []
                dst_x = (src_x + (int)(self.size[0]/2)) % self.size[0]
                dst_y = (src_y + (int)(self.size[1]/2)) % self.size[1]
                target_coord.append([dst_x, dst_y])
        else:
            dst_x = int(target_coord[0])
            dst_y = int(target_coord[1])
            target_coord = [];
            target_coord.append([dst_x,dst_y])

        source_port_obj = self.routers[src_x][src_y].input_ports[src_prt]
        source_port_obj.target_inj_rate += utilization
        injector = Injector(name, source_port_obj, target_coord, utilization, flits)
        # if throt_ctrl parameter is true, add throttle control module
        if throt_ctrl:
            inj_throt_ctrl = network_throt_ctrl.Network_throt_ctrl(utilization,injector)
            injector.throt_ctrl = inj_throt_ctrl
        source_port_obj.assign_target_output_port(injector);
        self.injectors.append(injector)

        inj_time = injector.get_next_req_time()
        self.add_to_timewheel(injector, current_time + inj_time)

        if not source_port_obj in self.inj_source_ports:
            self.inj_source_ports.append(source_port_obj)
            source_port_obj.resize(INJECTOR_FIFO_DEPTH) # aid in latency plotting - make input buffer at injector large to show latency
            source_port_obj.is_inject_point = True

    def enable_injectors(self, src_coord=None, dst_coord=None, disable=False):
        """Enable injectors from source to dest. None means 'all'."""

        if src_coord is not None:
            if src_coord[0] == -1:
                src_coord[0] = 0
                src_port = PRT_WEST
            elif src_coord[0] == self.size[0]:
                src_coord[0] = self.size[0] - 1
                src_port = PRT_EAST
            elif src_coord[1] == -1:
                src_coord[1] = 0
                src_port = PRT_NORTH
            elif src_coord[1] == self.size[1]:
                src_coord[1] = self.size[1] - 1
                src_port = PRT_SOUTH
            else:
                src_port = PRT_CORE

        for i in self.injectors:
            src_match = (src_coord is None) or ((i.source_port.coord == src_coord) and (i.source_port.port == src_port))
            dst_match = (dst_coord is None) or (dst_coord in i.target_ports)
            if src_match and dst_match:
                if disable:
                    i.disable()    
                else:
                    i.enable()

    def get_inport(self, x, y, port, core_target=False):
        """Returns the associated input port. core_target used to get the input port to the core (final network egress at core)"""
        if core_target:
            return self.routers[x][y].output_ports[PRT_CORE].tgt_input_port
        elif x == -1:
            return self.routers[0][y].output_ports[PRT_WEST].tgt_input_port
        elif x == self.size[0]:
            return self.routers[self.size[0]-1][y].output_ports[PRT_EAST].tgt_input_port
        elif y == -1:
            return self.routers[x][0].output_ports[PRT_NORTH].tgt_input_port
        elif y == self.size[1]:
            return self.routers[x][self.size[1]-1].output_ports[PRT_SOUTH].tgt_input_port

        return self.routers[x][y].input_ports[port]

    def get_inport_util(self, x, y, port, core_target=False):
        global current_time
        p = self.get_inport(x, y, port, core_target)
        samp_time = current_time - self.sample_start_time
        return float(p.sent_count)/samp_time
    def get_inport_lat(self, x, y, port, core_target=False):
        p = self.get_inport(x, y, port, core_target)
        if p.sent_count:
            lat = float(p.total_buf_lat) / p.sent_count
        else:
            lat = 0

        if lat > self.clip_inport_latency:
            lat = self.clip_inport_latency

        return lat

    def get_inport_amr_pct(self, x, y, port, core_target=False):
        p = self.get_inport(x, y, port, core_target)
        v = float(p.amr_could_go_count) / (current_time - self.sample_start_time)
        return v

    def get_amr_str(self, x, y, port, core_target=False):
        return "%0.2f " % self.get_inport_amr_pct(x, y, port, core_target)

    def get_pkt_count_str(self, x, y, port, core_target=False):
        return "%4d " % self.get_inport(x, y, port, core_target).pkt_count
    def get_sent_count_str(self, x, y, port, core_target=False):
        return "%4d " % self.get_inport(x, y, port, core_target).sent_count
    def get_blocked_pct_str(self, x, y, port, core_target=False):
        p = self.get_inport(x, y, port, core_target)
        v = float(p.blocked_count) / (current_time - self.sample_start_time)
        return "%0.2f " % v
    def get_ib_lat_str(self, x, y, port, core_target=False):
        lat = self.get_inport_lat(x, y, port, core_target)
        if lat < 10:
            return "%0.2f " % lat
        else:
            return "%4d " % lat

    def get_req_prt_str(self, x, y, port, core_target=False):
        p = self.get_inport(x, y, port, core_target)
        e = p.curr_entry()
        if e is None:
            req_str = " "
        else:
            rp = self.routers[x][y].dor_route_request(e)
            if rp == PRT_NORTH:
                req_str = "N"
            elif rp == PRT_SOUTH:
                req_str = "S"
            elif rp == PRT_EAST:
                req_str = "E"
            elif rp == PRT_WEST:
                req_str = "W"
            else:
                req_str = "C"
        return "%s    " % req_str
            
        
    def get_inport_util_str(self, x, y, port, core_target=False):
        return "%0.2f " % self.get_inport_util(x, y, port, core_target)

    def print_nw_util_map(self,metric="UTIL"):
        if metric == "SENT":
            self.pretty_print(self.get_sent_count_str)
        elif metric == "RECEIVED":
            self.pretty_print(self.get_pkt_count_str)
        else:
            self.pretty_print(self.get_inport_util_str)
 
    def pretty_print(self, get_stat_fn):
        """Pretty-print some stat in the network. get_stat_fn is called with (x,y,port,core_target) 
        and must return a 6-character string"""
        
        space = 6 * " "

        [dim_x,dim_y] = self.size

        str = ""
        for y in range(dim_y):
            str += space + " "
            for x in range(dim_x):
                str += get_stat_fn(x,y,PRT_NORTH)
                str += get_stat_fn(x,y-1,PRT_SOUTH)
                str += " " + space
            str += "\n"
            str += space + dim_x * ("+-v-----^-+" + space) + "\n"
            str += space
            for x in range(dim_x):
                str += "+  >%s +" % get_stat_fn(x,y,PRT_CORE,core_target=True) # to core
                str += space 
            str += "\n "
            for x in range(dim_x):
                str += get_stat_fn(x,y,PRT_WEST) + ">         > "
            str += get_stat_fn(dim_x,y,PRT_WEST)
            str += "\n" + space
            for x in range(dim_x):
                nm = self.routers[x][y].name
                if len(nm) < 8:
                    prep = (9 - len(nm)) / 2
                    post = 9 - len(nm) - prep
                    str += "+%s%s%s+" % (prep * " ", nm, post * " ") + space
                else:
                    str += "+%9s+" % nm[:8] + space 
            str += "\n " + get_stat_fn(-1,y,PRT_EAST)
            for x in range(dim_x):
                str += "<         < " + get_stat_fn(x,y,PRT_EAST)
            str += "\n"
            str += space
            for x in range(dim_x):
                str += "+  <%s +" % get_stat_fn(x,y,PRT_CORE) # from core
                str += space 
            str += "\n" + space + dim_x * ("+-v-----^-+" + space) + "\n"

        str += space + " "
        for x in range(dim_x):   
            str += get_stat_fn(x,dim_y,PRT_NORTH)
            str += get_stat_fn(x,dim_y-1,PRT_SOUTH)
            str += " " + space
        str += "\n"
        
        print str

    def gen_heatmap(self,measurement="Util",output_ext="png"):

        import numpy as np
        import matplotlib.pyplot as plt
        import os
        from matplotlib.patches import Rectangle

        [dim_x,dim_y] = self.size        

        if measurement == "Latency":
            fn = self.get_inport_lat
        elif measurement == "AMR":
            fn = self.get_inport_amr_pct
        else:
            fn = self.get_inport_util

        interpolation='hermite'
        # Methods must be one of:
    #methods = [None, 'none', 'nearest', 'bilinear', 'bicubic', 'spline16',
    #           'spline36', 'hanning', 'hamming', 'hermite', 'kaiser', 'quadric',
    #           'catrom', 'gaussian', 'bessel', 'mitchell', 'sinc', 'lanczos']
    #
    # hermite seems to do a good job. Oddly, 'nearest' seems to produce non-interpolated data and 'none' seems to be bilinear
    #

        data = []
        blank_val = 0
        tile_size = 4 
        for y in range(dim_y):

            row = []
            for x in range(dim_x):
                row += [blank_val,fn(x,y,PRT_NORTH),blank_val,fn(x,y-1,PRT_SOUTH)]
            row += [blank_val]
            data.append(row)

            row = []
            for x in range(dim_x):
                core_val = fn(x,y,PRT_CORE)
                row += [fn(x,y,PRT_WEST),core_val, core_val, core_val  ]
            row += [fn(dim_x,y,PRT_WEST)]
            data.append(row)

            row = []
            for x in range(dim_x):
                core_val = fn(x,y,PRT_CORE)
                row += [blank_val, core_val, core_val, core_val ]
            row += [blank_val]
            data.append(row)

            row = []
            for x in range(dim_x):
                core_val = fn(x,y,PRT_CORE)
                row += [fn(x-1,y,PRT_EAST), core_val, core_val, core_val ]
            row += [fn(dim_x-1,y,PRT_EAST)]
            data.append(row)


        row = []
        for x in range(dim_x):
            row += [blank_val,fn(x,dim_y,PRT_NORTH),blank_val,fn(x,dim_y-1,PRT_SOUTH)]
        row += [blank_val]
        data.append(row)

        data_a = np.array(data)

        plt.clf()

        ax = plt.gca()
        fig = plt.gcf()

        cax = ax.imshow(data_a, interpolation=interpolation)

        plt.title(measurement)


        for x in range(dim_x):
            for y in range(dim_y):
                ax.annotate(self.routers[x][y].name, xy=(x*tile_size+2,y*tile_size+2), textcoords='offset points', xytext=(-10,-5), fontsize=12, color='white')

        # Add arrow annotations - built in matplotlib arrows are too finicky (divide-by-zero errors when drawing short/straight lines)
        for y in range(dim_y):
            ax.annotate(">", xy=(0,y*tile_size+1),               textcoords='offset points', xytext=(-3,-4), color='white')
            ax.annotate(">", xy=(dim_x*tile_size,y*tile_size+1), textcoords='offset points', xytext=(-3,-4), color='white')
            ax.annotate("<", xy=(0,y*tile_size+3),               textcoords='offset points', xytext=(-3,-4), color='white')
            ax.annotate("<", xy=(dim_x*tile_size,y*tile_size+3), textcoords='offset points', xytext=(-3,-4), color='white')
        for x in range(dim_x):
            ax.annotate("V", xy=(x*tile_size+1,0),               textcoords='offset points', xytext=(-3,-3), color='white')
            ax.annotate("V", xy=(x*tile_size+1,dim_y*tile_size), textcoords='offset points', xytext=(-3,-3), color='white')
            ax.annotate("^", xy=(x*tile_size+3,0),               textcoords='offset points', xytext=(-6,-1), color='white', fontsize=18)
            ax.annotate("^", xy=(x*tile_size+3,dim_y*tile_size), textcoords='offset points', xytext=(-6,-1), color='white', fontsize=18)

        # fill in background between tiles with white boxes

        def add_background(x,y):
            ax.add_patch(Rectangle((x-.5,y-.5), 1, 1, facecolor="white", edgecolor="white"))

        for y in range(dim_y):
            for x in range(dim_x):
                add_background(x*tile_size+0,y*tile_size+0)
                add_background(x*tile_size+2,y*tile_size+0)
                add_background(x*tile_size+0,y*tile_size+2)
            add_background(dim_x*tile_size+0,y*tile_size+0)
            add_background(dim_x*tile_size+0,y*tile_size+2)
        for x in range(dim_x):
            add_background(x*tile_size+0,dim_y*tile_size+0)
            add_background(x*tile_size+2,dim_y*tile_size+0)
        add_background(dim_x*tile_size+0,dim_y*tile_size+0)
        

        #    ax.invert_yaxis()

        cb = fig.colorbar(cax)
        ax.set_axis_off()

        fig.set_size_inches(4 + dim_x*.8, 3 + dim_y*.8)

        filename = measurement + "." + output_ext
        if os.path.isfile(filename):
            os.remove(filename)
        plt.savefig(filename)

class PacketFlit(object):
    def __init__(self, name, dst_coord, eop=True):
        global current_time
        self.name = name
        self.eop = eop
        self.dst_coord = dst_coord
        self.timestamp = current_time
        self.route_hist = []

    def dump(self):
        print "         %s : [%d,%d] (EOP:%d)" % \
            (self.name, self.dst_coord[0], self.dst_coord[1], self.eop),
        if debug_full_hist:
            print "Hist:",
            print self.route_hist
        else:
            print ""

class InputPort(object):
    def __init__(self, name, coord, port, network):
        self.name = name
        self.type = 0
        self.tgt_output_port = None
        self.depth = network.fifo_depth
        self.fifo_count = 0
        self.fifo_entry = self.depth * [None]
        self.fifo_rptr = 0
        self.fifo_wptr = 0
        self.push_count = 0
        self.pop_count = 0
        self.target_inj_rate = 0
        self.coord = coord
        self.port = port
        self.locked = False
        self.can_push_curr = True
        self.can_push_prev = True
        self.network = network
        self.is_inject_point = False
        self.credit_regs = 0;
        self.starv_cnt = 0
        self.global_depth = network.fifo_depth
        self.clear_stats()

    def clear_stats(self):
        self.pkt_count = 0
        self.max_fifo_count = 0
        self.blocked_count = 0
        self.empty_count = 0
        self.sent_count = 0
        self.stats_are_reliable = True
        self.total_buf_lat = 0
        self.amr_could_go_count = 0

    def resize(self, new_size):
        if self.fifo_count != 0:
            raise AssertionError("resizing a non-empty FIFO seems like a bad idea %s" % self.name)
        self.depth = new_size
        self.fifo_entry = self.depth * [None]

    def dump(self, verbose=False):
        print "      %s  (%d flits received) :" % (self.name, self.pkt_count)
        print "      %s  (%d flits sent) :" % (self.name, self.sent_count)
        if verbose:
            ptr = self.fifo_rptr
            cnt = self.fifo_count        
            while cnt:
                self.fifo_entry[ptr].dump()
                ptr += 1
                ptr %= self.depth
                cnt -= 1
    
    def assign_target_output_port(self, output_port):
        self.tgt_output_port = output_port

    def curr_entry(self):
        if self.fifo_count == 0:
            return None
        
        return self.fifo_entry[self.fifo_rptr]

    def pop_entry(self):
        if self.fifo_count == 0:
           raise AssertionError("Tried to pop empty input port %s" % self.name)

        ent = self.fifo_entry[self.fifo_rptr]
        self.fifo_rptr = (self.fifo_rptr + 1) % self.depth
        self.fifo_count -= 1
        self.sent_count += 1
        self.pop_count = 1
        self.locked = not ent.eop
        self.credit_regs = self.credit_regs + 1;

        if self.network.track_history:
            rh = ent.route_hist[len(ent.route_hist)-1]
            if debug_full_hist:
                self.total_buf_lat += current_time - rh[2]
            else:
                self.total_buf_lat += current_time - rh

        return ent

    def push_entry(self, flit):
        global current_time
        if self.fifo_count == self.depth:
           print (self.tgt_output_port.credits,self.tgt_output_port.name)
           print (self.tgt_output_port.tgt_input_port.name,self.tgt_output_port.tgt_input_port.type)
           print self.fifo_count
           raise AssertionError("Tried to push full input port %s" % self.name)
        if self.network.track_history:
            if debug_full_hist:
                flit.route_hist.append(tuple(self.coord + [0] + [current_time]))
            else:
                flit.route_hist.append(current_time)                
        self.fifo_entry[self.fifo_wptr] = flit
        self.fifo_wptr = (self.fifo_wptr + 1) % self.depth
        self.push_count += 1
        self.pkt_count += 1 
        
    def update_state(self):
        if detailed_ib_stats:
            if self.fifo_count == 0:
                self.empty_count += 1
            elif self.pop_count == 0:
                self.blocked_count += 1
                if (self.is_inject_point and self.fifo_count > self.global_depth):
                    self.starv_cnt += 1
                if (self.is_inject_point == False and self.fifo_count == self.global_depth):
                    self.starv_cnt += 1
            if self.fifo_count > self.max_fifo_count:
                self.max_fifo_count = self.fifo_count

        self.fifo_count += self.push_count

        self.push_count = 0
        self.pop_count = 0
        self.can_push_prev = self.can_push_curr
        self.can_push_curr = self.fifo_count < self.depth

        # shift credit register to simulate delay in returning credits
        last_digit = self.credit_regs & 1;
        if last_digit == 1:
            if self.network.network_pipe_stage == 0:
                upper = 1 << (self.network.network_pipe_stage+1);
            else:
                upper = 1 << (self.network.network_pipe_stage);
            self.credit_regs = self.credit_regs >> 1;
            self.credit_regs = self.credit_regs | upper;
        else:
            self.credit_regs = self.credit_regs >> 1;

    def get_sent_count(self):
        return self.sent_count

    def can_push(self):
        # model extra cycle of credit return
        return self.can_push_prev and self.can_push_curr

class StubInputPort(InputPort):
    """Stub input port used as final destination for flits. It gathers the latency info and discards the flits"""
    def __init__(self, name, coord, port, network):
        super(StubInputPort,self).__init__(name, coord, port, network)
        self.type = 1 
        self.clear_stats()

    def clear_stats(self):
        super(StubInputPort,self).clear_stats()
        self.total_latency = 0
        self.min_latency = 1000
        self.max_latency = 0
        self.total_nw_latency = 0
        self.min_nw_latency = 1000
        self.max_nw_latency = 0
        self.max_nw_lat_flit = None
        self.tot_buf_lat = 0

    def push_entry(self,flit):
        global current_time
        self.sent_count += 1
        self.pkt_count += 1

        self.tgt_output_port.credits = self.tgt_output_port.credits + 1;

        latency = current_time - flit.timestamp
        self.total_latency += latency
        if latency > self.max_latency:
            self.max_latency = latency
        if latency < self.min_latency:
            self.min_latency = latency        

        #self.network.network_latency_hist[latency] += 1

        if self.network.track_history:
            if debug_full_hist:
                flit.route_hist.append(self.coord + [current_time])
            else:
                flit.route_hist.append(current_time)

            if len(flit.route_hist) < 2:
                # received packet w/o hist. Stats won't be right
                self.stats_are_reliable = False
            else:

                # measure latency from NW injection (ignore time spent at input buffer)
                if debug_full_hist:
                    nw_latency = current_time - flit.route_hist[1][2]
                else:
                    nw_latency = current_time - flit.route_hist[1]
                self.total_nw_latency += nw_latency
                if nw_latency > self.max_nw_latency:
                    self.max_nw_latency = nw_latency
                    self.max_nw_lat_flit = flit
                if nw_latency < self.min_nw_latency:
                    self.min_nw_latency = nw_latency        

    def pop_entry(self):
        raise AssertionError("Tried to pop from stub input port" % self.name)
    def can_push(self):
        return True
    def dump(self, verbose=False):        
        print "      %s (%d flits received)." % (self.name, self.pkt_count),
        if self.pkt_count:
            print "Latency MIN:%d MAX:%d AVG:%0.2f " % \
                (self.min_latency,
                 self.max_latency,
                 float(self.total_latency)/self.pkt_count)
        else:
            print ""

class OutputPort(object):
    def __init__(self, name, port, network, straight_through_pnum, credit):
        self.name = name
        self.port = port
        self.tgt_input_port = None
        self.tgt_network_pipe = None
        self.last_route_choice = PRT_CORE
        self.mop = False
        self.network = network
        self.straight_through_pnum = straight_through_pnum
        self.full_credit = credit
        self.credits = credit
        self.fails = 0

    def clear_stats(self):
        return

    def update_state(self):
        # check destination input ports to get return credits
        if (self.tgt_input_port.credit_regs & 1):
            self.credits = self.credits + 1;
            self.tgt_input_port.credit_regs -= 1;

    def assign_target_input_port(self, input_port):
        self.tgt_input_port = input_port

    def assign_target_network_pipe(self, network_pipe):
        self.tgt_network_pipe = network_pipe

    def dump(self):
        print (self.name, self.tgt_input_port.name, "failed: %d" % self.fails)

    def route_choice(self, requests):               

        if not self.credits > 0:
            self.fails += 1
            return -1

        if self.mop:
            if (requests >> self.last_route_choice) & 1:
                return self.last_route_choice
            else :
                return -1            

        if self.network.spa_straight and ((requests >> self.straight_through_pnum) & 1):
            self.last_route_choice = self.straight_through_pnum
            return self.straight_through_pnum        

        core_npa_req = (requests >> PRT_CORE) & 1
        if self.network.npa:
            requests &= ~(1 << PRT_CORE)

        count = 5
        src_prt = self.last_route_choice
        while count:
            src_prt = (src_prt  + 1) % 5
            if (requests >> src_prt) & 1:
                self.last_route_choice = src_prt
                return src_prt
            count -= 1

        if core_npa_req:
            self.last_route_choice = PRT_CORE
            return PRT_CORE

        return -1

    def send_packet_flit(self, flit):
        self.mop = not flit.eop
        self.tgt_input_port.push_entry(flit)
        # if the flit is go to stubinput, no need to decrease credits
        if self.tgt_input_port.type == 0:
            self.credits = self.credits - 1;

class Injector(object):
    def __init__(self, name, source_port, target_ports, utilization, flits=1, dist_type=DIST_POISSON):
        self.name = name
        self.util = utilization
        self.target_ports = tuple(target_ports)
        self.source_port = source_port
        self.flits = flits
        self.send_flit_desired_count = 0
        self.tgt_inj = self.util / self.flits
        self.dist_type = dist_type
        self.pkt_count = 0
        self.enabled = True
        self.credits = INJECTOR_FIFO_DEPTH;
        self.get_next_req_time()
        self.throt_ctrl = None
        self.util_seq = []

    def clear_stats(self):
        self.pkt_count = 0

    def update_state(self):
        # get credits from input ports
        if (self.source_port.credit_regs & 1):
            self.credits += 1
            self.source_port.credit_regs -= 1

    def disable(self):
        self.enabled = False
    def enable(self):
        self.enabled = True

    def dump(self):
        print "%s sent %d flits" % (self.name,self.pkt_count)

    def get_next_req_time(self):
        m = 1.0/self.tgt_inj

        if self.dist_type == DIST_UNIFORM:
            nt = int(random.uniform(1,2.0*m))
        elif self.dist_type == DIST_POISSON:           
            m -= 1 # center around m-1 then add 1 since poisson can return 0. Re-normalize by adding 1 on return
            nt = numpy.random.poisson(lam=m) + 1
        else: # default to normal distribution
            while True:
                rs = random.normalvariate(m,m*.25) # normal distribution centerred around mean with 25% of mean as std-dev
                if (rs > 1) and (rs < (2*m - 1)): # resample to fold tails of the distribution in if needed
                    break
            nt = int(round(rs))

        self.next_req_time = nt
        return nt 

    def inject_packet(self):
        if not self.enabled:
            return

        if len(self.target_ports) > 1:
            target_sel = random.randrange(len(self.target_ports))
        else:
            target_sel = 0

        flits_rem = self.flits
        while flits_rem:
            eop = flits_rem == 1       
            p = PacketFlit(self.name, self.target_ports[target_sel], eop)
            if self.credits > 0:
                self.source_port.push_entry(p)
                self.pkt_count += 1
                self.credits = self.credits - 1
            else:
                raise AssertionError("Can't push at injector %s. Input buffer too small?" % self.name)
            flits_rem -= 1

    def gen_step(self):
        if current_time >= self.next_req_time: # don't really need to check this if timewheel being used, but doesn't cost much
            self.inject_packet()
            self.get_next_req_time()

        return self.next_req_time

    def gen_step_simple(self):        
        if self.util > random.random():
            self.send_flit_desired_count += 1
        
        if (self.send_flit_desired_count > 0):
            self.inject_packet()
            self.send_flit_desired_count -= self.flits
        
        return 1

    def adjust_util(self):
        if (current_time % 500 == 0 and self.throt_ctrl):
            self.throt_ctrl.adjust_util()
        self.util_seq.append(self.util)

class Router(object):

    def __init__(self, coord, network, credit):

        my_x = coord[0]
        my_y = coord[1]
        self.coord = tuple(coord)
        self.size = tuple(network.size)
        self.input_ports = ()
        self.output_ports = ()
        self.route_conflicts = 5 * [0]
        self.name = "%d,%d" % (self.coord[0], self.coord[1])
        self.network = network
        prt_num = 0
        for prt in ["N","S","E","W","C"]:
            self.input_ports += (InputPort(name = "(%d,%d).%s" % (my_x, my_y, prt), coord = [my_x, my_y], port=prt_num, network=network),)
            straight_through_pnum = (PRT_SOUTH, PRT_NORTH, PRT_WEST, PRT_EAST, PRT_CORE)[prt_num]
            self.output_ports += (OutputPort(name = "(%d,%d).%s" % (my_x, my_y, prt), port=prt_num, network=network, straight_through_pnum=straight_through_pnum, credit=credit),)
            prt_num += 1
    
    def clear_stats(self):
        self.route_conflicts = 5 * [0]
        for i in self.input_ports:
            i.clear_stats()
        for o in self.output_ports:
            o.clear_stats()

    def resize_input_ports(self, depth):
        for s in self.input_ports:
            if not s.is_inject_point:
                s.resize(depth)

    def legal_route_request(self, src_prt, dst_prt):
        if self.network.route_alg != ROUTE_OE:
            return True

        odd_col = self.coord[0] & 1
        
        if odd_col:
            restricted_turn = (src_prt == PRT_WEST) and (dst_prt != PRT_EAST)
        else:
            restricted_turn = (dst_prt == PRT_WEST) and (src_prt != PRT_EAST)

        return not restricted_turn

    def oe_route_request(self,flit, src_prt, is_injector):
        """Generate route request using odd/even method."""

        [my_x, my_y] = self.coord
        [dst_x,dst_y] = flit.dst_coord
        [tgt_x,tgt_y] = [dst_x,dst_y]

        if (dst_x == self.coord[0]) and (dst_y == self.coord[1]):
            return PRT_CORE

        # target last tile before IO route
        if dst_x < 0: tgt_x = 0
        elif dst_x == self.size[0]: tgt_x = self.size[0]-1
        elif dst_y < 0: tgt_y = 0
        elif dst_y == self.size[1]: tgt_y = self.size[1]-1


        # made it to last tile, now route to IO
        if (tgt_x == self.coord[0]) and (tgt_y == self.coord[1]):
            if dst_x > my_x:
                return PRT_EAST
            elif dst_x < my_x:
                return PRT_WEST
            elif dst_y > my_y:
                return PRT_SOUTH
            else:
                return PRT_NORTH



        odd_col = my_x & 1

        # detect the restricted turns:
        # EN/ES = even
        # NW/SW = odd
        if odd_col:
            restricted_turn = (src_prt == PRT_WEST) and (tgt_y != my_y)
        else:
            restricted_turn = ((src_prt == PRT_NORTH) or (src_prt == PRT_SOUTH)) and (tgt_x < my_x)
            
        # if we're coming from the injector and need to go west and in an even column, need to jog now
        if is_injector and (tgt_x < my_x) and not odd_col:
            return PRT_WEST

        # if heading east and next col is our target col (but not in right row yet), need to turn now
        if (tgt_x == (my_x + 1)) and (not odd_col) and (tgt_y != my_y):
            if tgt_y < my_y:
                return PRT_NORTH
            else:
                return PRT_SOUTH

        if tgt_x < my_x: # never restricted
            return PRT_WEST

        if (tgt_x > my_x) and ((not restricted_turn) or (src_prt == PRT_WEST)):
            return PRT_EAST

        if (tgt_y < my_y) and ((not restricted_turn) or (src_prt == PRT_SOUTH)):
            return PRT_NORTH

        if (tgt_y > my_y) and ((not restricted_turn) or (src_prt == PRT_NORTH)):
            return PRT_SOUTH

        print "ERROR: could not route at %s" % self.name
        flit.dump()
        raise AssertionError("")
        

    def dor_route_request(self, flit):        
        """Generate route request for simple dimensionally-ordered route"""

        [dst_x,dst_y] = flit.dst_coord
        [tgt_x,tgt_y] = [dst_x,dst_y]

        # target last tile before IO route
        if dst_x < 0: tgt_x = 0
        elif dst_x == self.size[0]: tgt_x = self.size[0]-1
        elif dst_y < 0: tgt_y = 0
        elif dst_y == self.size[1]: tgt_y = self.size[1]-1

        # made it to last tile, now route to IO
        if (tgt_x == self.coord[0]) and (tgt_y == self.coord[1]):
            [tgt_x, tgt_y] = [dst_x,dst_y]
            
        if self.network.toroid:
            if self.network.route_method == ROUTE_X_FIRST:

                if self.network.unidir_toroid:
                    if tgt_x != self.coord[0]:
                        return PRT_EAST
                    if tgt_y != self.coord[1]:
                        return PRT_SOUTH
                    return PRT_CORE                    

                if tgt_x > self.coord[0]:
                    xwrap = abs(tgt_x - self.coord[0]) > (self.size[0] >> 1)
                    return (PRT_EAST,PRT_WEST)[xwrap]
                if tgt_x < self.coord[0]:
                    xwrap = abs(tgt_x - self.coord[0]) > (self.size[0] >> 1)
                    return (PRT_WEST,PRT_EAST)[xwrap]
                if tgt_y < self.coord[1]:
                    ywrap = abs(tgt_y - self.coord[1]) > (self.size[1] >> 1)
                    return (PRT_NORTH,PRT_SOUTH)[ywrap]
                if tgt_y > self.coord[1]:
                    ywrap = abs(tgt_y - self.coord[1]) > (self.size[1] >> 1)
                    return (PRT_SOUTH,PRT_NORTH)[ywrap]
                return PRT_CORE
            else:
                if self.network.unidir_toroid:
                    if tgt_y != self.coord[1]:
                        return PRT_SOUTH
                    if tgt_x != self.coord[0]:
                        return PRT_EAST
                    return PRT_CORE                    

                if tgt_y < self.coord[1]:
                    ywrap = abs(tgt_y - self.coord[1]) > (self.size[1] >> 1)
                    return (PRT_NORTH,PRT_SOUTH)[ywrap]
                if tgt_y > self.coord[1]:
                    ywrap = abs(tgt_y - self.coord[1]) > (self.size[1] >> 1)
                    return (PRT_SOUTH,PRT_NORTH)[ywrap]
                if tgt_x > self.coord[0]:
                    xwrap = abs(tgt_x - self.coord[0]) > (self.size[0] >> 1)
                    return (PRT_EAST,PRT_WEST)[xwrap]
                if tgt_x < self.coord[0]:
                    xwrap = abs(tgt_x - self.coord[0]) > (self.size[0] >> 1)
                    return (PRT_WEST,PRT_EAST)[xwrap]
                return PRT_CORE                
        else: # non-toroid routing
            if self.network.route_method == ROUTE_X_FIRST:
                if tgt_x > self.coord[0]:
                    return PRT_EAST
                if tgt_x < self.coord[0]:
                    return PRT_WEST
                if tgt_y < self.coord[1]:
                    return PRT_NORTH
                if tgt_y > self.coord[1]:
                    return PRT_SOUTH
                return PRT_CORE
            else:
                if tgt_y < self.coord[1]:
                    return PRT_NORTH
                if tgt_y > self.coord[1]:
                    return PRT_SOUTH
                if tgt_x > self.coord[0]:
                    return PRT_EAST
                if tgt_x < self.coord[0]:
                    return PRT_WEST
                return PRT_CORE

    def amr_route_request(self, flit):
        """Return request for an alternate minimum route if available"""

        [dst_x,dst_y] = flit.dst_coord
        [tgt_x,tgt_y] = [dst_x,dst_y]

        # target last tile before IO route
        if dst_x < 0: tgt_x = 0
        elif dst_x == self.size[0]: tgt_x = self.size[0]-1
        elif dst_y < 0: tgt_y = 0
        elif dst_y == self.size[1]: tgt_y = self.size[1]-1

        # already done in mesh, no AMR
        if [tgt_x, tgt_y] == self.coord:
            return None

        if self.network.route_method == ROUTE_X_FIRST:
            if tgt_x == self.coord[0]: # in last dimension, no AMR
                return None
            elif tgt_y == self.coord[1]: # in correct row, no AMR
                return None
            elif tgt_y < self.coord[1]:
                return PRT_NORTH
            else:
                return PRT_SOUTH                            
        else:
            if tgt_y == self.coord[1]: # in last dimension, no AMR
                return None
            elif tgt_x == self.coord[0]: # in correct col, no AMR
                return None
            elif tgt_x > self.coord[0]:
                return PRT_EAST
            else:
                return PRT_WEST

    def amr_stat_calc(self):
        prt = 0
        for src in self.input_ports:
            # something in the FIFO and it was not routed this cycle            
            if src.fifo_count and (src.pop_count == 0) and not src.locked:
                op_req_amr = self.amr_route_request(src.fifo_entry[src.fifo_rptr])
                if op_req_amr is not None:
                    # see if AMR could go
                    tgt_op = self.output_ports[op_req_amr]
                    tgt_inp = tgt_op.tgt_input_port
                    # nothing pushed this output port and there's credit available
                    if (tgt_inp.push_count == 0) and tgt_inp.can_push() and (not tgt_op.mop) and self.legal_route_request(prt,op_req_amr):
                        src.amr_could_go_count += 1   
                        if allow_adaptive_route:
                            self.output_ports[op_req_amr].send_packet_flit(src.pop_entry())
            prt += 1

    def route_step(self):

        requests = [0, 0, 0, 0, 0]

        # go through the source ports and mark output requests vector 'True' at my source location
        # if I have something to send there.
        src_prt = 0
        for src in self.input_ports:
#            src = self.input_ports[src_prt]
#            e=src.curr_entry()
#            if e is not None:
            if src.fifo_count:

                if self.network.route_alg == ROUTE_OE:
                    target_req = self.oe_route_request(src.fifo_entry[src.fifo_rptr], src_prt, src.is_inject_point)
                else:
                    target_req = self.dor_route_request(src.fifo_entry[src.fifo_rptr])

#                if target_req == src_prt:
#                    raise AssertionError("Tried to loop back to same port on %s" % self.name)
                requests[target_req] |= 1 << src_prt
            src_prt += 1

        # go through dst_ports and handle any requests
        dst_prt = 0
        for dst in self.output_ports:
            d_requests = requests[dst_prt]
            if d_requests:
                src_sel = dst.route_choice(d_requests)

                if src_sel >= 0:
                    f= self.input_ports[src_sel].pop_entry()
                    dst.send_packet_flit(f)
                    if (1 << src_sel) != d_requests:
                        self.route_conflicts[dst_prt] += 1
            dst_prt += 1

    def update_input_state(self):
        for p in self.input_ports:
            p.update_state()

    def update_output_state(self):
        for p in self.output_ports:
            p.update_state()
            
    def dump(self, verbose=False):
        print "   Router %s" % self.name
        
        for p in self.input_ports:
            p.dump(verbose)
        for p in self.output_ports:
            p.dump()

# Network pipeline is composed of network entry
class NetPipe(object):
    def __init__(self, coord, prt_num, stage, network):
        self.coord = coord
        self.stage = stage
        self.prt_num = prt_num
        self.network = network
        self.entries = []
        self.tgt_input_port = None
        self.sent_count = 0
    
        for i in range(self.stage):
            self.entries.append(NetPipe_Entry(self.coord, self.prt_num, i, self.network))

        self.clear_stats()

    def clear_stats(self):
        for i in range(self.stage):
            self.entries[i].clear_stats()

    def update_state(self):
        for i in range(self.stage):
            self.entries[i].update_state();

    def assign_target_input_port(self, input_port):
        self.tgt_input_port = input_port

    def push_entry(self, flit):
        # Based on whether in the bypass mode to determine to use which module's
        # push_entry() function call
        if self.stage > 0:
            self.entries[0].push_entry(flit)
        else:
            self.tgt_input_port.push_entry(flit)

    def send_packet_flit(self, flit):
        self.tgt_input_port.push_entry(flit)

    def netpipe_step(self):
        if self.stage > 0 and self.entries[self.stage-1].full == True:
            flit = self.entries[self.stage-1].pop_entry()
            self.send_packet_flit(flit)

        for i in range(self.stage-1, 0, -1):
            if self.entries[i-1].full == True:
                flit = self.entries[i-1].pop_entry()
                self.entries[i].push_entry(flit)

class NetPipe_Entry(object):
    def __init__(self, coord, prt_num, index, network):
        self.coord = coord
        self.prt_num = prt_num
        self.index = index
        self.network = network
        self.full = False
        self.content = None

    def clear_stats(self):
        return;

    def update_state(self):
        return;

    def push_entry(self, flit):
        global current_time
        if self.network.track_history:
            if debug_full_hist:
                flit.route_hist.append(tuple(self.coord + [1] + [current_time]))
            else:
                flit.route_hist.append(current_time)
        self.full = True
        self.content = flit 

    def pop_entry(self):
        flit = self.content
        self.full = False
        self.content = None
        return flit
        
