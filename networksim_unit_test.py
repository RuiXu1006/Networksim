import networksim
import network

class scoreboard(object):
    def __init__(self, network):
        self.injectors  = []
        self.network = network
        self.board = dict()
        for tar in network.targets:
            self.board[tar.name] = 0

    def reset(self):
        for key in self.board.keys():
            self.board[key] = 0

    def target_check(self):
        for stub in self.network.targets:
            if stub.pkt_count != self.board[stub.name]:
                print "Test Failed: There are missing flits in %s, %d" % (stub.name,stub.pkt_count)
        print "Test Passed!"

    def sys_check(self):
        self.network.update_stats()
        if ns.network.flits_sent != ns.network.flits_received:
            print "Test Failed: Sent flits:%d, Received flits:%d" % (ns.network.flits_sent,ns.network.flits_received)
        else:
            print "Test Passed!"
        self.network.clear_stats()


ns = networksim.NetWorkSim(dim_x=5,dim_y=5)
test_case = 1
test_fail = 0

# one flit test case, push a flit into each input queues and send to core stub inputs
print "Test Case %d: one flit(only core stubinputs)" % test_case
ns.init_network()
checker = scoreboard(ns.network)
ns.config("run_step", 20);
# push one lift in each direction port of each router
for prt in range(0,5):
    for src_x in range(ns.network.size[0]):
        for src_y in range(ns.network.size[1]):
            flit = None 
            for dst_x in range(ns.network.size[0]):
                for dst_y in range(ns.network.size[1]):
                    flit = network.PacketFlit("Flit(%d,%d,%d)" % (src_x,src_y,prt), [dst_x,dst_y])
                    dst_name = "(%d,%d).C" % (dst_x,dst_y)
                    checker.board[dst_name] += 1
                    ns.network.routers[src_x][src_y].input_ports[prt].push_entry(flit)
                    ns.sim()
checker.target_check()
test_case += 1

# one flit test case, push a flit into each input queues and send to perimeter stub inputs
print "Test Case %d: one flit(only perimeter stubinputs)" % test_case
ns.init_network()
checker = scoreboard(ns.network)
ns.config("run_step", 20);
# send flits to west side perimeter stubinputs
for prt in range(0,5):
    for src_x in range(ns.network.size[0]):
        for src_y in range(ns.network.size[1]):
            # send to north and south side perimeter stub inputs
            for dst_y in [-1, ns.network.size[1]]:
                for dst_x in range(ns.network.size[0]):
                    flit = network.PacketFlit("Flit(%d,%d,%d)" % (src_x,src_y,prt), [dst_x,dst_y])
                    if dst_y == -1:
                        dst_name = "(%d,%d).S" % (dst_x,dst_y)
                    else:
                        dst_name = "(%d,%d).N" % (dst_x,dst_y)
                    checker.board[dst_name] += 1
                    ns.network.routers[src_x][src_y].input_ports[prt].push_entry(flit)
                    ns.sim()
            # send to west and east side perimeter stub inputs
            for dst_x in [-1, ns.network.size[0]]:
                for dst_y in range(ns.network.size[1]):
                    flit = network.PacketFlit("Flit(%d,%d,%d)" % (src_x,src_y,prt), [dst_x,dst_y])
                    if dst_x == -1:
                        dst_name = "(%d,%d).E" % (dst_x,dst_y)
                    else:
                        dst_name = "(%d,%d).W" % (dst_x,dst_y)
                    checker.board[dst_name] += 1
                    ns.network.routers[src_x][src_y].input_ports[prt].push_entry(flit)
                    ns.sim()
checker.target_check()
test_case += 1

# Add core injectors for one flit random test
print "Test Case %d: one flit(random tests with core injectors)" % test_case
ns.init_network()
checker = scoreboard(ns.network)
ns.config("run_step", 10000)
ns.add_core_injectors()
ns.sim()
ns.network.drain()
checker.sys_check()
test_case += 1

# Add perimeter injectors for one flit random test
print "Test Case %d: one flit(random tests with perimeter injectors)" % test_case
ns.init_network()
checker = scoreboard(ns.network)
ns.add_perimeter_injectors()
ns.sim()
ns.network.drain()
checker.sys_check()
test_case += 1

# Add both core and perimeter injectors for one flit random test
print "Test Case %d: one flit(random tests with core and perimeter injectors)" % test_case
ns.init_network()
checker = scoreboard(ns.network)
ns.add_core_injectors()
ns.add_perimeter_injectors()
ns.sim()
ns.network.drain()
checker.sys_check()
test_case += 1

# Continuous flits mode test
print "Test Case %d: multiple flits mode"  % test_case
ns.init_network()
checker = scoreboard(ns.network)
ns.config("flits", 4)
ns.add_core_injectors()
ns.add_perimeter_injectors()
ns.sim()
ns.network.drain()
checker.sys_check()
test_case += 1

# Test the functionality correctness under variouse pipe delay
print "Test Case %d: various netwok delay" % test_case
for delay in range(1, 6):
    ns.config("credit", delay)
    ns.config("depth", delay)
    ns.init_network()
    checker = scoreboard(ns.network)
    ns.add_core_injectors()
    ns.add_perimeter_injectors()
    ns.sim()
    ns.network.drain()
    checker.sys_check()
test_case += 1

# "ALL" traffic pattern test
print "Test Case %d: \"ALL\" traffic pattern" % test_case
ns.init_network()
checker = scoreboard(ns.network)
ns.add_core_injectors(target_coord="ALL")
ns.add_perimeter_injectors(target_coord="ALL")
ns.sim()
ns.network.drain()
checker.sys_check()
test_case += 1

# "Neighbor" traffic pattern test
print "Test Case %d: \"NEIGHBOR\" traffic pattern" % test_case
ns.init_network()
checker = scoreboard(ns.network)
ns.add_core_injectors(target_coord="NEIGHBOR")
ns.add_perimeter_injectors(target_coord="NEIGHBOR")
ns.sim()
ns.network.drain()
checker.sys_check()
test_case += 1

# "Transpose" traffic pattern test
print "Test Case %d: \"TRANSPOSE\" traffic pattern" % test_case
ns.init_network()
checker = scoreboard(ns.network)
ns.add_core_injectors(target_coord="TRANSPOSE")
ns.add_perimeter_injectors(target_coord="TRANSPOSE")
ns.sim()
ns.network.drain()
checker.sys_check()
test_case += 1

# "Tornado" traffic pattern test
print "Test Case %d: \"TORNADO\" traffic pattern" % test_case
ns.init_network()
checker = scoreboard(ns.network)
ns.add_core_injectors(target_coord="TORNADO")
ns.add_perimeter_injectors(target_coord="TORNADO")
ns.sim()
ns.network.drain()
checker.sys_check()
test_case += 1

# Hot spot stress test
print "Test Case %d: hot spot stress test" % test_case
ns.init_network()
checker = scoreboard(ns.network)
for x in range(0, ns.network.size[0]):
    for y in range(0, ns.network.size[1]):
        ns.add_core_injector(x, y, "00")
ns.sim()
ns.network.drain()
ns.network.gen_heatmap()
checker.sys_check()
test_case += 1
