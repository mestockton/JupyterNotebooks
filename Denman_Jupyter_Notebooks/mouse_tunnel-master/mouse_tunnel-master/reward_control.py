import sys
sys.path.append('C:\github\syringe_pump')
from stepper import Stepper
s = Stepper(mode='arduino',port='COM3',syringe='3mL')

"""

    Display series of numbers in infinite loop
    Listen to key "s" to stop
    Only works on Windows because listening to keys
    is platform dependent

"""

volume = 500

# msvcrt is a windows specific native module
import msvcrt
import time

# asks whether a key has been acquired
def kbfunc():
    #this is boolean for whether the keyboard has bene hit
    x = msvcrt.kbhit()
    if x:
        #getch acquires the character encoded in binary ASCII
        ret = msvcrt.getch()
    else:
        ret = False
    return ret

#begin the counter
number = 1

#infinite loop
while True:

    #acquire the keyboard hit if exists
    x = kbfunc() 

    #if we got a keyboard hit
    if x != False and x.decode() == 'r':
        #we got the key!
        #because x is a binary, we need to decode to string
        #use the decode() which is part of the binary object
        #by default, decodes via utf8
        #concatenation auto adds a space in between
        print ('dispensing')
        s.dispense(10)
        #break loop

    if x != False and x.decode() == 'f':
        #we got the key!
        #because x is a binary, we need to decode to string
        #use the decode() which is part of the binary object
        #by default, decodes via utf8
        #concatenation auto adds a space in between
        print ('retracting')
        s.retract(volume)
        #break loop

    if x != False and x.decode() == 'q':
        #we got the key!
        #because x is a binary, we need to decode to string
        #use the decode() which is part of the binary object
        #by default, decodes via utf8
        #concatenation auto adds a space in between
        print ("STOPPING")
        #break loop
        break
    else:
        #prints the number
        pass
        time.sleep(0.5)