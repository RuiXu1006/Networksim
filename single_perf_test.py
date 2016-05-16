import networksim
import matplotlib.pyplot as plt

ns = networksim.NetWorkSim(dim_x=4,dim_y=2)
ns.config("stage", 3)

util = 0.95
d = 4
throt_ctrl = True;

ns.config("credit", d)
ns.config("depth", d)
ns.config("util", util)

ns.init_network()
ns.add_core_injectors(util=0.2*util)
#ns.add_perimeter_injectors()
ns.add_perimeter_injector(1, 0, util=util, throt_ctrl=throt_ctrl)
ns.add_perimeter_injector(2, 0, util=util, throt_ctrl=throt_ctrl)
ns.add_perimeter_injector(2, 1, util=0.7, throt_ctrl=False)


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
ns.config("run_step", 50000)
ns.sim()
ns.network.drain()
ns.network.update_stats()

#ns.network.gen_heatmap()
ns.network.dump_stats()

fig = plt.figure()
time = []

for i in range(0, len(ns.network.monitor.lat_seq)):
    time.append(i*1000)
ax1 = fig.add_subplot(4, 1, 1)
ax1.plot(time, ns.network.monitor.lat_seq, lw = 2.5)
ax2 = ax1.twinx()
ax2.plot(time, ns.network.monitor.starv_rate, lw=2.5, color = 'r')


avglat = ns.network.total_latency / ns.network.flits_received
print "Average Latency is %2f" % avglat
print "Total received %d flits" % ns.network.flits_received
print "Simualation time %d clock cycles" % ns.network.clock_cycles
inj_port_id = 1

for port in ns.network.inj_source_ports:
    print(port.name, port.starv_cnt, port.pkt_count) 
    if not ('C' in port.name):
        if port.tgt_output_port.throt_ctrl == None:
            continue
        time = []
        for i in range(0, len(port.tgt_output_port.throt_ctrl.util_seq)):
            time.append(i*1000)
        ax1 = fig.add_subplot(4, 1, inj_port_id+1)
        ax1.plot(time, port.tgt_output_port.throt_ctrl.util_seq, lw=2.5, label = ("%s" % port.name))
        ax1.set_xlabel("time")
        ax1.set_ylabel("util")
        #ax1.set_ylim([0, 1.0])
        ax1.legend()
        inj_port_id += 1

        ax2 = ax1.twinx()
        ax2.plot(time, port.tgt_output_port.throt_ctrl.starv_cnt, lw=2.5, color='r')

plt.show()

