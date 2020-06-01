'''
Created on Oct 26, 2012

@author: derricw

#------------------------------------------------------------------------------ 
iodaq.py
#------------------------------------------------------------------------------ 

Derric's wrapper for DAQ from an NIDAQ board using the PyDAQmx library.

Dependencies:
Python27
PyDAQmx (http://pypi.python.org/pypi/PyDAQmx) #Tested using 1.2.3
numpy (http://www.scipy.org/Download)
scipy (http://www.scipy.org/Download)

List of features to add in the future:
1) Digital buffered reading and writing with clock timing
2) TDMS data logging (works for AnalogInput)

NIDAQmc C++ Reference:  #PyDAQmx maps one-to-one to the C++ library
http://zone.ni.com/reference/en-XX/help/370471W-01/

'''

#----------------------------------------------------------------------- Imports
from PyDAQmx import Task
from PyDAQmx.DAQmxConstants import *
from PyDAQmx.DAQmxFunctions import *
from numpy import zeros, sin, arange, pi, array, ones
import numpy as np
from scipy import signal
from ctypes import c_long, c_ulong

#-------------------------------------------------------------- Config Functions
def GetDevices():
    """Gets all NIDAQ devices and returns a list of their names"""
    buffer_size = 1024 #set max buffer size
    devicenames = " "*buffer_size #build device string
    DAQmxGetSysDevNames(devicenames, buffer_size) #fill string with names
    return devicenames.strip().strip('\x00').split(', ')  #strip off null char for each

def GetAIChannels(device):
    """ Returns a list of Analog Input Channels for the specified device """
    buffer_size = 1024
    channels = " "*buffer_size
    DAQmxGetDevAIPhysicalChans(device,channels,buffer_size)
    return channels.strip().strip('\x00').split(', ')
    
def GetAOChannels(device):
    """ Returns a list of analog output channels for the specified device """
    buffer_size = 1024
    channels = " "*buffer_size
    DAQmxGetDevAOPhysicalChans(device,channels,buffer_size)
    return channels.strip().strip('\x00').split(', ')

def GetDOPorts(device):
    """Returns the names of all Digital Output ports on the specified device"""
    buffer_size = 1024
    ports = " "*buffer_size
    DAQmxGetDevDOPorts(device, ports, buffer_size)
    return ports.strip().strip('\x00').split(', ')

def GetDIPorts(device):
    """Returns the names of all Digital Input ports on the specified device"""
    buffer_size = 1024
    ports = " "*buffer_size
    DAQmxGetDevDIPorts(device, ports, buffer_size)
    return ports.strip().strip('\x00').split(', ')

def GetDOLines(device):
    """Returns the names of all Digital Output lines on the specified device"""
    buffer_size = 1024
    lines = " "*buffer_size
    DAQmxGetDevDOLines(device, lines, buffer_size)
    return lines.strip().strip('\x00').split(', ')
    
def GetDILines(device):
    """Returns the names of all Digital Input lines on the specified device"""
    buffer_size = 1024
    lines = " "*buffer_size
    DAQmxGetDevDILines(device, lines, buffer_size)
    return lines.strip().strip('\x00').split(', ')

#-------------------------------------------------------------- Analog Tasks
class AnalogInput(Task):
    '''
    Gets analog input from NIDAQ device.
        Tested using several buffer sizes and channels on a NI USB-6210.

    Parameters
    ----------

    device : 'Dev1'
        NIDAQ device id
    channels : [0]
        List of channels to read
    buffer_size : 500
        Integer size of buffer to read
    clock_speed : 10000.0
        Float sample clock speed
    terminal_config : "RSE"
        String for terminal type: "RSE","Diff"
    voltage_range : [-10.0,10.0]
        Float bounds for voltages
    timout : 10.0
        Float timeout for read
    tdms : None
        tdms file to write to.
    binary : None
        binary file to write to
    dtype : np.float64
        output data type

    Returns
    -------

    AnalogInput : Task
        Task object

    Examples
    --------

    >>> ai = AnalogInput('Dev1',channels=[0],buffer_size=500)
    >>> ai.StartTask()
    >>> for x in range(10):
    ...     time.sleep(1) #collects some data
    ...     print ai.data #prints the current buffer
    >>> ai.ClearTask()
    
    '''
    def __init__(self, 
                device='Dev1', 
                channels=[0],
                buffer_size=500, 
                clock_speed=10000.0,
                terminal_config="RSE",
                voltage_range=[-10.0,10.0],
                timeout=10.0,
                tdms=None,
                binary=None,
                dtype=np.float64):

        #construct task
        Task.__init__(self)
        
        #set up task properties
        self.buffer_size = buffer_size
        self.clock_speed = clock_speed
        self.channels = channels
        self.data = zeros((self.buffer_size,len(self.channels)),dtype=np.float64) #data buffer
        self.dataArray = []
        self.accumulate = False
        self.tdms=tdms
        self.binary=binary
        self.terminal_config = eval("DAQmx_Val_%s"%(terminal_config))
        self.voltage_range = voltage_range
        self.timeout = timeout
        self.dtype = dtype
        self.buffercount = 0

        #create dev str for various channels
        devStr = ""
        if type(channels) is int:
            channels = [channels]
        for channel in channels:
            devStr += str(device) + "/ai" + str(channel) + ","
        devStr = devStr[:-1]
        
        self.CreateAIVoltageChan(devStr,"",self.terminal_config,
            self.voltage_range[0],self.voltage_range[1],DAQmx_Val_Volts,None)

        self.CfgSampClkTiming("",self.clock_speed,DAQmx_Val_Rising,DAQmx_Val_ContSamps,self.buffer_size)

        if self.tdms is not None:
            self.ConfigureLogging(self.tdms,DAQmx_Val_Log,"data",DAQmx_Val_CreateOrReplace)
        else:
            self.AutoRegisterEveryNSamplesEvent(DAQmx_Val_Acquired_Into_Buffer,self.buffer_size,0) #set up data buffer callback
        if self.binary is not None:
            self.outFile = open(self.binary,'wb')
        self.AutoRegisterDoneEvent(0) #set up task complete callback (unused since this class takes continuous samples)
        
    def EveryNCallback(self):
        try:
            read = int32()
            self.ReadAnalogF64(self.buffer_size,self.timeout,DAQmx_Val_Auto,
                self.data,(self.buffer_size*len(self.channels)),byref(read),None)
            if self.binary:
                self.outFile.write(self.data.astype(self.dtype).tostring())
            if (self.accumulate == True):
                self.dataArray.extend(self.data.astype(self.dtype).tolist())  #collect all data
            self.buffercount+=1
        except Exception, e:
            print "Failed to read buffer #%i"%self.buffercount
        
    def DoneCallback(self, status):
        print "Status",status
        return 0 # The function should return an integer


class AnalogOutput(Task):
    '''
    Analog Output task.  
        Writes arrays of float64's to an analog output channel at a specified sample rate.
        Value remains until changed, even after task is cleared.

    Parameters
    ----------

    device : GetDevices()[0]
        String, NIDAQ device id
    channels : [0]
        List of intergers, channels to write to
    voltage_range : [0.0, 0.5]
        Float, bounds for voltages

    Returns
    -------

    AnalogOutput : Task
        Task object

    Examples
    --------

    >>> data = 9.95*sin(arange(1000, dtype=float64)*2*pi/1000) #create waveform of some sort
    >>> ao = AnalogOutput('Dev1',channels=[0])
    >>> ao.StartTask()
    >>> ao.Write(data) #will write samples only once at the clock speed of board
    >>> ao.ClearTask()

    TODO
    ----
    TODO: I'm having some trouble configuring clock timing.  My NI USB-6211 appears to write at exactly 1600 samples/s.
        I can set this in the NI Measurement explorer for continuous samples, but for some reason not here.
        The data sheet says it should be capable of 250kS/s per channel...

        Also, I'm having trouble outputting to multiple channels at once.  I think that it is something to do with
        DAQmx_Val_GroupByChannel in the WriteAnalogF64 function.


    '''
    def __init__(self, 
                device='Dev1', 
                channels = [0],
                voltage_range = [0.0,5.0]):

        Task.__init__(self)
        
        #create dev str for various channels
        self.channels = channels
        self.voltage_range = voltage_range
        devStr = ""
        if type(channels) is int:
            channels = [channels]
        for channel in channels:
            devStr += str(device) + "/ao" + str(channel) + ","
        devStr = devStr[:-1]

        self.CreateAOVoltageChan(devStr,"",self.voltage_range[0],
            self.voltage_range[1],DAQmx_Val_Volts,None)

        #self.CfgOutputBuffer(buffer_size)
        #self.CfgSampClkTiming("",sample_rate,DAQmx_Val_Rising,DAQmx_Val_ContSamps,buffer_size) #can't get this to work at the moment

        self.AutoRegisterDoneEvent(0)

    def Write(self,data):
        """
        Writes a numpy array of float64's to the analog output.
        """
        status = self.WriteAnalogF64(len(data)/len(self.channels),0,-1,DAQmx_Val_GroupByChannel,data,None,None)
        #print "Status", status #for troubleshooting, 0 indicates success

    def DoneCallback(self,status):
        return 0


class AnalogFunctionOutput(Task):
    """
    Creates a wave output function.

    Parameters
    ----------
    device : GetDevices()[0]
        String, NIDAQ device id
    channels : [0]
        List of integers, channels to write to
    ftype : 'sin'
        'sin','saw', 'sqr' or 'custom'
    frequency : 1
        wave frequency Hz
    amplitude : 5
        wave amplitude volts
    offset : 0
        wave offset volts
    phase : 0
        wave initial phase (radians)
    sample_rate : 1000
        output sample rate
    buffer_size : 1000
        write buffer size
    voltage_range : [-10.0, 10.0]
        Float bounds for voltages
    custom_wave : None
        custom waveform (see ftype above) Must be numpy array of float64's
        if multiply channels are desired, the custom array must be appropriately shaped

    Returns
    -------
    AnalogFunctionOutput : Task
        Task object

    Examples
    --------

    >>> afo = AnalogFunctionOutput('Dev1',channels=[0],functionType='sin',frequency=1)
    >>> afo.StartTask()
    >>> time.sleep(10) #output for 10 seconds
    >>> afo.ClearTask()

    TODO
    ----

    Outputing two different waves simultaneously on two different channels.
    Duplicate waves on two different channels works fine.

    """
    def __init__(self, 
                device='Dev1', 
                channels=[0],
                ftype='sin',
                frequency=1,
                amplitude=5,
                offset=0,
                phase=0,
                sample_rate=1000,
                buffer_size=1000,
                voltage_range=[-10.0,10.0],
                custom_wave=None):

        Task.__init__(self)

        self.voltage_range = voltage_range

        #create dev str for various channels
        devStr = ""
        if type(channels) is int:
            channels = [channels]
        for channel in channels:
            devStr += str(device) + "/ao" + str(channel) + ","
        devStr = devStr[:-1]        

        ftypes = {
            'sin':amplitude*sin(np.linspace(0,1.0/frequency,buffer_size/frequency)*2.0*pi*frequency+phase)+offset,
            'saw':amplitude*signal.sawtooth(np.linspace(0,1.0/frequency,buffer_size/frequency)*2.0*pi*frequency+phase)+offset,
            'sqr':amplitude*signal.square(np.linspace(0,1.0/frequency,buffer_size/frequency)*2.0*pi*frequency+phase)+offset,
            'custom':custom_wave
        }

        self.data = ftypes[ftype.lower()] #create waveform of some sort

        if custom_wave is None:
            for i in range(len(channels)-1):
                self.data = np.column_stack((self.data,self.data))

        self.CreateAOVoltageChan(devStr,"",self.voltage_range[0],
            self.voltage_range[1],DAQmx_Val_Volts,None)
        self.CfgSampClkTiming("",sample_rate,DAQmx_Val_Rising,DAQmx_Val_ContSamps,len(self.data))

        self.AutoRegisterDoneEvent(0)

        status = self.WriteAnalogF64(len(self.data),0,-1,DAQmx_Val_GroupByScanNumber,self.data,None,None)

    def DoneCallback(self,status):
        return 0

#-------------------------------------------------------------------- Digital Tasks
class DigitalInput(Task):
    '''
    Gets the state of the inputs from the NIDAQ Device/port specified. 
        Different devices have different number of lines/ports.

    Parameters
    ----------

    device : 'Dev1'
        String, NIDAQ device id (ex:'Dev1')
    port : 0
        Integer, port number to read data from
    timeout : 10.0
        Float, seconds to wait for samples

    Returns
    -------

    DigitalInput : Task
        Task object

    Examples
    --------

    >>> task = DigitalInput('Dev1',0) #device 1, port 0
    >>> task.StartTask()
    >>> data = task.Read()
    >>> print data
    >>> task.StopTask()
    >>> task.ClearTask()

    '''
    def __init__(self, 
                device = 'Dev1' ,
                port = 0,
                timeout = 10.0):

        Task.__init__(self)
        self.timeout = timeout
        self.port = port
        
        lines = GetDILines(device)
        lines = [l for l in lines if 'port' + str(port) in l]
        self.deviceLines = len(lines)
        
        #set up task properties
        devStr = str(device) + "/port" + str(port) + "/line0:" + str(self.deviceLines-1)
            
        #create channel
        self.CreateDIChan(devStr,"",DAQmx_Val_ChanForAllLines)
        
    def Read(self):
        #reads the current setting of all inputs
        data = np.zeros(self.deviceLines, dtype = np.uint8)
        bytesPerSample = c_long()
        samplesPerChannel = c_long()
        self.ReadDigitalLines(1,self.timeout,DAQmx_Val_GroupByChannel,data,self.deviceLines,
                              samplesPerChannel,bytesPerSample,None)
        return data
        
    def DoneCallback(self, status):
        print "Status",status.value
        return 0 # The function should return an integer


class DigitalOutput(Task):

    '''
    Sets the current output state of all digital lines.  

    Parameters
    ----------

    device : 'Dev1'
        String, NIDAQ device id (ex:'Dev1')
    port : 0
        Integer, port number to write data to
    timeout : 10.0
        Float, seconds for write timeout
    initial_state : 'high'
        String: 'high', 'low' or ndarray for a custom state

    Returns
    -------

    DigitalOutput : Task
        Task object

    Examples
    --------

    >>> task = DigitalOutput('Dev1',1) #device 1, port 1
    >>> task.StartTask()
    >>> data = np.array([1,0,1,0],dtype = np.uint8)
    >>> task.Write(data)
    >>> task.StopTask()
    >>> task.ClearTask()

    '''

    def __init__(self, 
                device = 'Dev1', 
                port = 0,
                timeout = 10.0,
                initial_state = 'high',
                ):

        Task.__init__(self)
        self.timeout = timeout
        
        lines = GetDOLines(device)
        lines = [l for l in lines if 'port' + str(port) in l]
        self.deviceLines = len(lines)  
        
        #create dev str for various lines
        devStr = str(device) + "/port" + str(port) + "/line0:" + str(self.deviceLines-1)

        #create initial state of output lines
        if initial_state.lower() == 'low':
            self.lastOut = np.zeros(self.deviceLines, dtype = np.uint8) #keep track of last output #should be gotten from initial state instead
        elif initial_state.lower() == 'high':
            self.lastOut = np.ones(self.deviceLines,dtype=np.uint8)
        elif type(initial_state) == np.ndarray:
            self.lastOut = initial_state
        else:
            raise TypeError("Initial state not understood. Try 'high' or 'low'")

        #create IO channel
        self.CreateDOChan(devStr,"",DAQmx_Val_ChanForAllLines)

        self.AutoRegisterDoneEvent(0)

        
    def DoneCallback(self,status):
        print "Status", status.value
        return 0
    
    def Write(self,data,samples_per_line=1):
        '''Writes a numpy array of data to set the current output state

        Parameters
        ----------

        data : required
            ndarray, uint8, rows should be the number of lines. cols should be
            number of samples per channel
        samples_per_line: 1
            int, number of samples to write per line

        Returns
        -------
        None

        Examples
        --------

        >>> data = np.array([1,0,1,0],dtype=np.uint8,1)
        >>> task.Write(data)

        '''

        self.WriteDigitalLines(1,1,self.timeout,DAQmx_Val_GroupByChannel,data,None,None)
        if samples_per_line == 1:
            self.lastOut = data
        else:
            self.lastOut = data[-1]

    def WriteBit(self, index, value):
        '''Writes a single bit to the given line index. '''
        self.lastOut[index] = value
        self.WriteDigitalLines(1,1,self.timeout,DAQmx_Val_GroupByChannel,self.lastOut,None,None)


def syncit(digital_out_task, line, invert=False):
    """
    Function or method decorator that can be used for synchronization.  It sets
        the digital line high or low during the decorated function call.

    Parameters
    ----------
    digital_out_task : DigitalOutput object
        DigitalOutput object that you'd like to use to send the signal.
    line : int
        Which line to send the signal on.
    invert : bool (False)
        Whether to invert the signal.

    Returns
    -------
    None (This is a decorator)

    Examples
    --------
    >>> import time
    >>> do = DigitalOutput("Dev1", 0)
    >>> do.StartTask()

    >>> @syncit(do, 0)
    >>> def do_stuff():
    ...     time.sleep(1)

    >>> do_stuff()
    >>> do.ClearTask()

    """

    do = digital_out_task
    if invert:
        high, low = 0, 1
    else:
        high, low = 1, 0

    def wrap(f):
        def synced(*args, **kwargs):
            do.WriteBit(line, high)
            result = f(*args, **kwargs)
            do.WriteBit(line, low)
            return result
        return synced
    return wrap


#------------------------------------------------------------------------------ if main
if __name__ == '__main__':
    pass
