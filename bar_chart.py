import numpy as np
import matplotlib.pyplot as plt

def autolabel(rects):
    # attach some text labels
    for rect in rects:
        height = rect.get_height()
        ax.text(rect.get_x() + rect.get_width()/2., 1*height,
                '%d' % int(height),
                ha='center', va='bottom')

N = 11
base_data  = [(91, 92, 91, 91, 92, 91, 91, 91, 92, 92, 91),
              (87, 86, 85, 86, 86, 85, 86, 86, 86, 86, 86),
              (81, 81, 81, 81, 81, 81, 81, 81, 81, 81, 81),
              (76, 76, 77, 77, 77, 76, 77, 77, 77, 77, 77)]
throt_data = [(92, 92, 92, 92, 92, 92, 93, 92, 92, 92, 92),
              (96, 95, 95, 95, 95, 95, 95, 95, 84, 84, 95),
              (99, 99, 99, 99, 99, 100, 100, 100, 76, 76, 99),
              (100, 99, 99, 100, 100, 100, 100, 99, 46, 46, 100)]
name_label = ('(0,0).C', '(0,1).C', '(1,0).C','(1,1).C','(2,0).C','(2,1).C','(3,0).C','(3,1).C','(1,0).N','(2,0).N','(2,1).S')

color_sequence = ['#1f77b4', '#aec7e8', '#ff7f0e', '#ffbb78', '#2ca02c',
                  '#98df8a', '#d62728', '#ff9896', '#9467bd', '#c5b0d5',
                  '#8c564b', '#c49c94', '#e377c2', '#f7b6d2', '#7f7f7f']

ind = np.arange(N)
width = 0.35

fig = plt.figure()
M = len(base_data)
fig.suptitle('AvgQ comparision', fontsize=14, fontweight='bold')

for i in range(0, M):
    ax = fig.add_subplot(M,1,i+1)
    rects1 = ax.bar(ind, base_data[i], width, color=color_sequence[0])
    rects2 = ax.bar(ind+width, throt_data[i], width, color=color_sequence[8])
    
    ax.set_ylabel('AvgQ')
    ax.set_xticks(ind + width)
    ax.set_xticklabels(name_label)
    ax.legend((rects1[0], rects2[0]), ('Base', 'Throt'))
    ax.set_ylim([0,110])
    
    autolabel(rects1)
    autolabel(rects2)

plt.show()
