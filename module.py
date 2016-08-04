from abc import ABCMeta, abstractmethod

import sys

# This the abstract class of hardware module, it only contains the 
# information of name, parent and children hierarchy. Meanwhile, 
# it only has some of general methods 

class Module:
    __metaclass__ = ABCMeta
    
    # use the parent module and its own name to init
    # if there is no parent module, parent argument is passed as NULL

    def __init__(parent, name):
        self.name = name
        if parent != NULL:
            self.full_name = parent.full_name + '.' + name
        else:
            self.full_name = name
        self.parent = parent
        self.child = []
   
    def _add_children(self, child):
        self.child.add(child)

    def _display_children(self):
        for child in self.child:
            print "%s: %s\n" % (self.name, child.name)

    def error(self):
        print "Error from Module %s\n" % self.name
        sys.exit(0)

