import network

npa = False

class NetWorkSim(object):
        def __init__(self, dim_x=5, dim_y=5, stage=0, credit=3, fifo_depth=3, util=0.2):
            self.dim_x = dim_x
            self.dim_y = dim_y
            self.pipe_stage = stage
            self.output_credit = credit
            self.input_fifo_depth = fifo_depth 
            self.util = util
            self.debug_mode = False
            self.warm_steps = 1000
            self.run_steps = 10000
            self.flits = 1
            self.network = None

        def config(self, parameter, v):
            if parameter == "dim_x":
                self.dim_x = v
            elif parameter == "dim_y":
                self.dim_y = v
            elif parameter == "stage":
                self.pipe_stage = v
            elif parameter == "credit":
                self.output_credit = v
            elif parameter == "depth":
                self.input_fifo_depth = v
            elif parameter == "debug":
                self.debug_mode = v
            elif parameter == "util":
                self.util = v
            elif parameter == "flits":
                self.flits = v
            elif parameter == "run_step":
                self.run_steps = v
            else:
                raise AssertionError("Unrecognized parameters!")

        def dump_config(self):
            print "Network dimension:(%d, %d)" % (self.dim_x, self.dim_y)
            print "pipe stage:%d output credit:%d fifo depth:%d util:%f flits:%d run_steps:%d" %(self.pipe_stage,self.output_credit,self.input_fifo_depth,self.util,self.flits,self.run_steps)

        # remove original network
        def reset(self):
            self.network = None
        
        def init_network(self):
            self.network = network.Network(self.dim_x, self.dim_y, self.pipe_stage, self.output_credit, self.input_fifo_depth, route_method=network.ROUTE_X_FIRST, network_priority_arb=False)

        def add_core_injector(self, x, y, util, target_coord="TILES"):
            if self.network == None:
                raise AssertionError("You should initialize Nework firstly!")
            self.network.add_injector("CORE(%d,%d)" % (x,y), x, y, network.PRT_CORE, util, target_coord, self.flits)
       
        def add_core_injectors(self, util, target_coord="TILES"):
            for x in range(self.dim_x):
                for y in range(self.dim_y):
                    self.add_core_injector(x, y, util, target_coord)

        def add_perimeter_injector(self, x, y, util=0.3, target_coord="TILES", throt_ctrl=False):
            if (x != 0 and x != self.dim_x-1) and (y != 0 and y != self.dim_y-1):
                raise AssertionError("This is not a perimeter injector!")
            if y == 0:
                self.network.add_injector("PERIM(%d,%d)" % (x,y), x, y, network.PRT_NORTH, util, target_coord, self.flits, throt_ctrl)
            elif y == self.dim_y-1:
                self.network.add_injector("PERIM(%d,%d)" % (x,y), x, y, network.PRT_SOUTH, util, target_coord, self.flits, throt_ctrl)

            if x == 0:
                self.network.add_injector("PERIM(%d,%d)" % (x,y), x, y, network.PRT_WEST, util, target_coord, self.flits, throt_ctrl)
            elif x == self.dim_x-1:
                self.network.add_injector("PERIM(%d,%d)" % (x,y), x, y, network.PRT_EAST, util, target_coord, self.flits, throt_ctrl)

        def add_perimeter_injectors(self, target_coord="TILES"):
            for x in range(self.dim_x):
                self.add_perimeter_injector(x, 0, target_coord)
                self.add_perimeter_injector(x, self.dim_y-1, target_coord)
            for y in range(1, self.dim_y-1):
                self.add_perimeter_injector(0, y, target_coord)
                self.add_perimeter_injector(self.dim_x-1, y, target_coord)

        def sim(self):
            if self.network == None:
                self.init_network()

            self.network.step(self.run_steps)

        def dump_system_stats(self):
            if self.network == None:
                raise AssertionError("You should firstly initialize networl and run simulation!")
            self.network.dump_stats(verbose=self.debug_mode)

        def dump_input_stats(self, x, y, prt):
            self.network.routers[x][y].input_ports[prt].dump()

        def dump_stub_stats(self, x, y, prt):
            self.network.routers[x][y].output_ports[prt].tgt_input_port.dump()

        def dump_output_stats(self, x, y, prt):
            self.network.routers[x][y].output_ports[prt].dump()

        def dump_router_stats(self, x, y):
            self.network.routers[x][y].dump(verbose=self.debug_mode)

#s = NetWorkSim()
#s.config("debug", True)
#s.dump_config()
#s.init_network()
#s.add_core_injectors()
#s.add_perimeter_injectors()
#s.sim()
#s.dump_system_stats()
