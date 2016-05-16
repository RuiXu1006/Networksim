import networksim
import matplotlib.pyplot as plt

ns = networksim.NetWorkSim(dim_x=5,dim_y=5)
ns.config("stage",2)
util = []
lat  = []
rec_flits = []
AvgQ = []
Maxlat = []

# Set how many groups 
u = 0.01
while u < 0.7:
    util.append(u)
    u += 0.05

# Run simulation
#for d in range(1, 2*ns.pipe_stage+7):
for d in range(1,2):
    print "depth:%d" % d
    lat_each = []
    rec_flits_each = []
    AvgQ_each = []
    Maxlat_each = []
    for u in util:
        print "util: %f" % u
        ns.config("credit",d)
        ns.config("depth",d)
        ns.config("util",u)
        ns.init_network()
        ns.add_core_injectors()
        ns.add_perimeter_injectors()
        # warm up phase
        ns.config("run_step",1000)
        ns.sim()
        ns.network.clear_stats()
        # real execution phase
        ns.config("run_step",10000)
        ns.sim()
        ns.network.drain()
        ns.network.update_stats()
        rec_flits_each.append(ns.network.flits_received)
        lat_each.append(ns.network.total_latency/ns.network.flits_received)
        AvgQ_each.append(ns.network.average_q) 
        Maxlat_each.append(ns.network.max_latency)
    lat.append(lat_each)
    rec_flits.append(rec_flits_each)
    AvgQ.append(AvgQ_each)
    Maxlat.append(Maxlat_each)

# plot simulation results
color_sequence = ['#1f77b4', '#aec7e8', '#ff7f0e', '#ffbb78', '#2ca02c',
                  '#98df8a', '#d62728', '#ff9896', '#9467bd', '#c5b0d5',
                  '#8c564b', '#c49c94', '#e377c2', '#f7b6d2', '#7f7f7f']

fig = plt.figure()

ax1 = fig.add_subplot(111)
ax1.set_title('Avergae Latency vs Utilization')
ax1.set_xlabel('Utilization')
ax1.set_ylabel('Avergae Latency')
for i in range(0, len(lat)):
    ax1.plot(util, lat[i], lw=2.5, color=color_sequence[i], label = "%d entries" % (i+1))
#box = ax1.get_position()
#ax1.set_position([box.x0, box.y0,box.width*0.8,box.height])
ax1.legend(loc='center left',bbox_to_anchor=(1,0.5))
ax1.set_xlim([0,0.4])
ax1.set_ylim([0,500])
'''
ax2 = fig.add_subplot(224)
ax2.set_title('Received Flits vs Utilization')
ax2.set_xlabel('Utilization')
ax2.set_ylabel('Received Flits')
for i in range(0, len(lat)):
    ax2.plot(util, rec_flits[i], lw=2.5, color=color_sequence[i], label = "%d entries" % (i+1))
box = ax2.get_position()
ax2.set_position([box.x0+box.width*0.05, box.y0,box.width*0.85,box.height])
ax2.legend(loc='center left',bbox_to_anchor=(1,0.5))

ax3 = fig.add_subplot(222)
ax3.set_title('Max Latency vs Utilization')
ax3.set_xlabel('Utilization')
ax3.set_ylabel('Max Latency')
for i in range(0, len(lat)):
    ax3.plot(util, Maxlat[i], lw=2.5, color=color_sequence[i], label = "%d entries" % (i+1))
box = ax3.get_position()
ax3.set_position([box.x0+box.width*0.05, box.y0,box.width*0.85,box.height])
ax3.legend(loc='center left',bbox_to_anchor=(1,0.5))

ax4 = fig.add_subplot(223)
ax4.set_title('AvgQ vs Utilization')
ax4.set_xlabel('Utilization')
ax4.set_ylabel('AvgQ')
for i in range(0, len(lat)):
    ax4.plot(util, AvgQ[i], lw=2.5, color=color_sequence[i], label = "%d entries" % (i+1))
box = ax4.get_position()
ax4.set_position([box.x0, box.y0,box.width*0.8,box.height])
ax4.legend(loc='center left',bbox_to_anchor=(1,0.5))
'''
plt.show()
