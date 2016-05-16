import networksim
import matplotlib.pyplot as plt

ns = networksim.NetWorkSim(dim_x=4,dim_y=2)
ns.config("stage", 3)
base_lat = []
throt_lat = []
starve_rate = []
io_starve_rate = []
inj_starve_rate = []
all_starve_rate =[]

# Run simulation
for i in range(0, 2):
    u = 0.01
    util = []
    throt_ctrl = False
    if (i % 2 == 1):
        throt_ctrl = True
    while u < 1:
        print "Utilization: %f. Test Begins" % u
        # set up network
        ns.config("credit",4)
        ns.config("depth",4)
        ns.config("util",u)
        ns.init_network()
        ns.add_core_injectors(util=0.2*u)
        #ns.add_perimeter_injectors()
        ns.add_perimeter_injector(1, 0, util=u, throt_ctrl=throt_ctrl)
        ns.add_perimeter_injector(2, 0, util=u, throt_ctrl=throt_ctrl)
        ns.add_perimeter_injector(2, 1, util=u, throt_ctrl=False)
    
        # re-assign target injector to corresponding bandwidth throttling control
        target_inj = None
        for port in ns.network.inj_source_ports:
            if 'S' in port.name:
                target_inj = port.tgt_output_port
        
        if throt_ctrl:
            for port in ns.network.inj_source_ports:
                if 'N' in port.name:
                    port.tgt_output_port.throt_ctrl.assign_target_injector(target_inj)

        # warm up phase
        ns.config("run_step",1000)
        ns.sim()
        ns.network.clear_stats()
        # real execution phase
        ns.config("run_step", 10000)
        ns.sim()
        ns.network.drain()
        ns.network.update_stats()
        
        #ns.network.gen_heatmap()
        # collect data
        util.append(u)
        if throt_ctrl:
            throt_lat.append(ns.network.total_latency/ns.network.flits_received)
        else:
            base_lat.append(ns.network.total_latency/ns.network.flits_received)
        # calculate starvation rate
        total_starv_count = 0
        total_io_starv_count = 0
        total_inj_starv_count = 0
        total_all_starv_count = 0
        total_inj = 0
        for port in ns.network.inj_source_ports:
            total_inj_starv_count += port.starv_cnt 
            if "S" in port.name:
                #print (port.name, port.blocked_count)
                total_starv_count += port.starv_cnt
                total_inj += 1
            if "N" in port.name or "S" in port.name:
                total_io_starv_count += port.starv_cnt
        s = (float)(total_starv_count) / (float)(10000);
        starve_rate.append(s)
        io_starve_rate.append(total_io_starv_count) 

        for row in ns.network.routers:
            for r in row:
                for i in r.input_ports:
                    total_all_starv_count += i.starv_cnt
        all_starve_rate.append(total_all_starv_count)

        print "Utilization: %f. Test Finishes" % u
        u += 0.01

color_sequence = ['#1f77b4', '#aec7e8', '#ff7f0e', '#ffbb78', '#2ca02c',
                  '#98df8a', '#d62728', '#ff9896', '#9467bd', '#c5b0d5',
                  '#8c564b', '#c49c94', '#e377c2', '#f7b6d2', '#7f7f7f']

fig = plt.figure()

for i in range(0, 1):
    ax1 = fig.add_subplot(1, 1, i+1)
    ax1.set_xlabel('Utilization')
    ax1.set_ylabel('Average Latency')
    ax1.plot(util, base_lat, lw=2.5, color = color_sequence[0], label = "Based Average Latency")
    ax1.plot(util, throt_lat, lw=2.5, color = color_sequence[3], label = "Throt Average Latency")
    ax1.legend()
    '''
    ax2 = ax1.twinx()
    if (i == 0):
        ax1.set_title('Target Starvation rate')
        ax2.set_ylabel('Target Starvation Rate')
        fig2 = ax2.plot(util, starve_rate, lw=2.5, color = color_sequence[3], label = "Target Starvation Rate")
    elif (i == 1):
        ax1.set_title('IO Starvation rate')
        ax2.set_ylabel('IO Starvation Rate')
        fig2 = ax2.plot(util, io_starve_rate, lw=2.5, color = color_sequence[3], label = "IO Starvation Rate")
    elif (i == 2):
        ax1.set_title('All injectors Starvation rate')
        ax2.set_ylabel('All injectors Starvation Rate')
        fig2 = ax2.plot(util, io_starve_rate, lw=2.5, color = color_sequence[3], label = "All Injectors Starvation Rate")
    else:
        ax1.set_title('All Input Buffers Starvation rate')
        ax2.set_ylabel('All Input Buffers Starvation Rate')
        fig2 = ax2.plot(util, io_starve_rate, lw=2.5, color = color_sequence[3], label = "All Input Buffers Starvation Rate")
    
    lns = fig1+fig2
    labs = [l.get_label() for l in lns]
    ax1.legend(lns, labs, loc=0)
 '''
plt.savefig("lat_comparison.png")
