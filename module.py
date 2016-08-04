from abc import ABCMeta, abstractmethod

class Module:
    __metaclass__ = ABCMeta

    def __init__():
        self.name = ""
        self.full_name = ""
        self.parent = True
        self.child = []
   
    def _add_children(self, child):
        self.child.add(child)

    def _display_children(self):
        for child in self.child:
            print "%s: %s\n" % (self.name, child.name)
