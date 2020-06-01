from direct.showbase.ShowBase import ShowBase
from direct.task import Task
# from direct.gui.OnscreenText import OnscreenText
# from direct.showbase.DirectObject import DirectObject
from direct.interval.MetaInterval import Sequence
from direct.interval.LerpInterval import LerpFunc
from direct.interval.FunctionInterval import Func
from panda3d.core import Mat4, WindowProperties, CardMaker, NodePath, TextureStage, MovieTexture, MovieVideo

import sys,glob,time,datetime,os
from math import pi, sin, cos
from numpy.random import randint, exponential
from numpy import arange,concatenate
import numpy as np
from pyglet.window import key

try:
    from toolbox.toolbox.IO.nidaq import DigitalInput,DigitalOutput, AnalogInput, AnalogOutput
    have_nidaq=True
except:# Exception, e:
    print("could not import iodaq.")
    have_nidaq=False


MOUSE_ID = 'test'

#this is used to change whether the mouse's running and licking control the rewards.
#if TRUE, then the stimulus automatically advances to the next stop zone, waits, plays the stimulus, and delivers a reward. 
# AUTO_MODE=False
AUTO_MODE= False
AUTO_REWARD = True

# Global variables for the tunnel dimensions and speed of travel
TUNNEL_SEGMENT_LENGTH = 50
TUNNEL_TIME = 2  # Amount of time for one segment to travel the
# distance of TUNNEL_SEGMENT_LENGTH

class MouseTunnel(ShowBase):
    def __init__(self):
        # Initialize the ShowBase class from which we inherit, which will
        # create a window and set up everything we need for rendering into it.
        ShowBase.__init__(self)
        self.stimtype='image_sequence'
        
        #session_start
        self.session_start_time = datetime.datetime.now()

        self.accept("escape", sys.exit, [0])
        self.accept('q', self.close)
        self.accept('Q', self.close)

        self.AUTO_REWARD = AUTO_REWARD
        # disable mouse control so that we can place the camera
        base.disableMouse()
        camera.setPosHpr(0, 0, 10, 0, -90, 0)
        mat=Mat4(camera.getMat())
        mat.invertInPlace()
        base.mouseInterfaceNode.setMat(mat)
        base.enableMouse()
        
        props = WindowProperties()
        # props.setFullscreen(True)
        props.setCursorHidden(True)
        props.setMouseMode(WindowProperties.M_relative)
        base.win.requestProperties(props)
        base.setBackgroundColor(0, 0, 0)  # set the background color to black

        #set up the textures
        # we now get buffer thats going to hold the texture of our new scene
        altBuffer = self.win.makeTextureBuffer("hello", 1524, 1024)
        # altBuffer.getDisplayRegion(0).setDimensions(0.5,0.9,0.5,0.8)
        # altBuffer = base.win.makeDisplayRegion()
        # altBuffer.makeDisplayRegion(0,1,0,1)
        
        # now we have to setup a new scene graph to make this scene
        self.dr2 = base.win.makeDisplayRegion(0,0.1,0,0.1)
        
        altRender = NodePath("new render")
        # this takes care of setting up ther camera properly
        self.altCam = self.makeCamera(altBuffer)
        self.dr2.setCamera(self.altCam)
        self.altCam.reparentTo(altRender)
        self.altCam.setPos(0, -10, 0)
        
        self.bufferViewer.setPosition("llcorner")
        # self.bufferViewer.position = (.1,.4,.1,.4)
        self.bufferViewer.setCardSize(1.0, 0.0)
        print(self.bufferViewer.position)
        
        self.imagesTexture=MovieTexture("image_sequence")
        # success = self.imagesTexture.read("models/natural_images.avi")
        success = self.imagesTexture.read("models/movie_5hz.mpg")
        self.imagesTexture.setPlayRate(1.0)
        self.imagesTexture.setLoopCount(10)
        # self.imageTexture =loader.loadTexture("models/NaturalImages/BSDs_8143.tiff")
        # self.imagesTexture.reparentTo(altRender)
        
        cm = CardMaker("stimwindow")
        cm.setFrame(-4,4,-3,3)
        # cm.setUvRange(self.imagesTexture)
        self.card = NodePath(cm.generate())
        self.card.reparentTo(altRender)
        if self.stimtype=='image_sequence':
            self.card.setTexture(self.imagesTexture,1)
        
        # self.imagesTexture.play()

        # self.bufferViewer.setPosition("lrcorner")
        # self.bufferViewer.setCardSize(1.0, 0.0)
        self.accept("v", self.bufferViewer.toggleEnable)
        self.accept("V", self.bufferViewer.toggleEnable)

        # Load the tunnel 
        self.initTunnel()
    
        #initialize some things
        # for the tunnel construction:
        self.boundary_to_add_next_segment = -1 * TUNNEL_SEGMENT_LENGTH
        self.current_number_of_segments = 8
        #task flow booleans
        self.in_waiting_period = False
        self.stim_started = False
        self.looking_for_a_cue_zone = True
        self.in_reward_window=False
        self.show_stimulus=False
        #for task control
        self.interval=0
        self.time_waiting_in_cue_zone=0
        self.wait_time=1.83
        self.stim_duration= 4.0 # in seconds
        self.max_stim_duration = 6.0 # in seconds
        self.stim_elapsed= 0.0 # in seconds
        self.last_position = base.camera.getZ()
        self.position_on_track = base.camera.getZ()
        #for reward control
        self.reward_window = 1.0 # in seconds
        self.reward_elapsed = 0.0
        self.reward_volume = 0.008 # in mL. this is for the hardcoded 0.1 seconds of reward time
        self.reward_time = 0.1 # in sec, based on volume. hard coded right now but should be modified by the (1) calibration and (2) optionally by the main loop for dynamic reward scheduling
        # self.lick_buffer = []

        
        #INITIALIZE NIDAQ
        self.nidevice = 'Dev2'
        self.encodervinchannel = 1
        self.encodervsigchannel = 0
        self.invertdo = False
        self.diport = 1
        self.lickline = 1
        self.doport = 0
        self.rewardline = 0
        self.rewardlines = [0]
        self._setupDAQ()
        if have_nidaq:
            self.do.WriteBit(1,1)
            self.do.WriteBit(3,1)#set reward high, because the logic is flipped somehow. possibly by haphazard wiring of the circuit (12/24/2018 djd)
            self.previous_encoder_position = self.ai.data[0][self.encodervsigchannel]
        self.encoder_gain = -20

        #INITIALIZE LICK SENSOR
        self._lickSensorSetup()
   
        #INITIALIZE  output data
        self.lickData = []
        self.x = []
        self.t = []
        self.trialData = []
        self.rewardData = []

        #INITIALIZE KEY SENSOR, for backup inputs and other user controls
        self.keys = key.KeyStateHandler()
        self.accept('r', self._give_reward, [self.reward_volume])
        self.accept('l', self._toggle_reward)

        img_list = glob.glob('models/NaturalImages/*.tiff')[:10]
        print(img_list)
        self.imageTextures =[loader.loadTexture(img) for img in img_list]
        
        if AUTO_MODE:
            self.gameTask = taskMgr.add(self.autoLoop2, "autoLoop2")
            self.rewardTask = taskMgr.add(self.rewardControl, "reward")
            self.cue_zone = concatenate((self.cue_zone,arange(\
                self.current_number_of_segments*-TUNNEL_SEGMENT_LENGTH,\
                self.current_number_of_segments*-TUNNEL_SEGMENT_LENGTH-TUNNEL_SEGMENT_LENGTH-80,\
                -1)))
            self.auto_position_on_track = 0
            self.auto_restart = False
            self.auto_running = True
            self.contTunnel()
        else:
            # Now we create the task. taskMgr is the task manager that actually
            # calls the function each frame. The add method creates a new task.
            # The first argument is the function to be called, and the second
            # argument is the name for the task.  It returns a task object which
            # is passed to the function each frame.
            self.gameTask = taskMgr.add(self.gameLoop, "gameLoop")
            # self.stimulusTask = taskMgr.add(self.stimulusControl, "stimulus")
            self.lickTask = taskMgr.add(self.lickControl, "lick")
            self.rewardTask = taskMgr.add(self.rewardControl, "reward")
    
    # Code to initialize the tunnel
    def initTunnel(self):
        self.tunnel = [None] * 8

        for x in range(8):
            # Load a copy of the tunnel
            self.tunnel[x] = loader.loadModel('models/tunnel')
            # The front segment needs to be attached to render
            if x == 0:
                self.tunnel[x].reparentTo(render)
            # The rest of the segments parent to the previous one, so that by moving
            # the front segement, the entire tunnel is moved
            else:
                self.tunnel[x].reparentTo(self.tunnel[x - 1])                     
            # We have to offset each segment by its length so that they stack onto
            # each other. Otherwise, they would all occupy the same space.
            self.tunnel[x].setPos(0, 0, -TUNNEL_SEGMENT_LENGTH)
            # Now we have a tunnel consisting of 4 repeating segments with a
            # hierarchy like this:
            # render<-tunnel[0]<-tunnel[1]<-tunnel[2]<-tunnel[3]
        
        self.tunnel[0] = loader.loadModel('models/grating')
        self.tunnel[0].reparentTo(render)
        self.cue_zone = arange(0,TUNNEL_SEGMENT_LENGTH,-1)
    
    # This function is called to snap the front of the tunnel to the back
    # to simulate traveling through it
    def contTunnel(self):
        self.auto_position_on_track -= 50
        position_on_track = self.auto_position_on_track 
        print(str(int(position_on_track))+'   '+ str(self.cue_zone))
        if int(position_on_track) in np.array(self.cue_zone): #check for cue zone
            if not self.auto_restart:
                print('STOP!')
                self.tunnelMove.pause()
                self.auto_presentation = True
                # self.current_number_of_segments +=1
            else:
                self.auto_restart = True
                self.tunnelMove.resume()

        else:
            self.in_waiting_period=False
            self.auto_presentation=False

            # base.setBackgroundColor([1,0 , 0])
            if self.looking_for_a_cue_zone == False:
                self.looking_for_a_cue_zone = True
            if self.stim_started==True:
                self.stop_a_presentation()  

            # This line uses slices to take the front of the list and put it on the
            # back. For more information on slices check the Python manual
            self.tunnel = self.tunnel[1:] + self.tunnel[0:1]
            
            # Set the front segment (which was at TUNNEL_SEGMENT_LENGTH) to 0, which
            # is where the previous segment started
            self.tunnel[0].setZ(0)
            # Reparent the front to render to preserve the hierarchy outlined above
            self.tunnel[0].reparentTo(render)
            # Set the scale to be apropriate (since attributes like scale are
            # inherited, the rest of the segments have a scale of 1)
            self.tunnel[0].setScale(.155, .155, .305)
            # Set the new back to the values that the rest of the segments have
            self.tunnel[3].reparentTo(self.tunnel[2])
            self.tunnel[3].setZ(-TUNNEL_SEGMENT_LENGTH)
            self.tunnel[3].setScale(1)

            # Set up the tunnel to move one segment and then call contTunnel again
            # to make the tunnel move infinitely
            self.tunnelMove = Sequence(
                LerpFunc(self.tunnel[0].setZ,
                        duration=TUNNEL_TIME,
                        fromData=0,
                        toData=TUNNEL_SEGMENT_LENGTH * .305),
                Func(self.contTunnel)
            )
            self.tunnelMove.start()

    def start_a_presentation(self):

        print("start")
        self.do.WriteBit(2,1)
        # self.bufferViewer.toggleEnable()
        
        self.lick_buffer = []
        
        if self.stimtype == 'random image':
            for i in range(randint(len(self.imageTextures))):
                self.card.setTexture(self.imageTextures[i],1)
        if self.stimtype=='image_sequence':
            self.imagesTexture.setTime(0.)
            self.dr2.setDimensions(0.4, 0.8, 0.4, 0.70) #floats (left, right, bottom, top)
            self.imagesTexture.play()
        
    def stop_a_presentation(self):
        if self.stim_started==True:
            self.dr2.setDimensions(0,0.1,0,0.1)
            # self.bufferViewer.toggleEnable()
            self.stim_started=False
            self.stim_elapsed=0.
            self.stim_duration = 0.
            while self.stim_duration < 1. or self.stim_duration > self.max_stim_duration *2.:# set some limits on the random duration so is not too short or too long 
                self.stim_duration = exponential(self.max_stim_duration)
            self.stim_off_time = globalClock.getFrameTime()

            self.do.WriteBit(2,0)

    def _lickSensorSetup(self):
        """ Attempts to set up lick sensor NI task. """
        ##TODO: Make lick sensor object if necessary. Let user select port and line.
        if self.di:
            self.lickSensor = self.di  # just use DI for now
            licktest = []
            for i in range(30):
                licktest.append(self.di.Read()[self.lickline])
                time.sleep(0.01)
            licktest = np.array(licktest, dtype=np.uint8)
            if len(licktest[np.where(licktest > 0)]) > 25:
                self.lickSensor = None
                self.lickData = [np.zeros(len(self.rewardlines))]
                print("Lick sensor failed startup test.")
            self.keycontrol = True
        else:
            print("Could not initialize lick sensor.  Ensure that NIDAQ is connected properly.")
            self.keycontrol = True
            self.lickSensor = None
            self.lickData = [np.zeros(len(self.rewardlines))]
            self.keys = key.KeyStateHandler()
            # self.window.winHandle.push_handlers(self.keys)
            
    # def _read_licks(self): # not yet implemented; should be replaces with check to beam break
    def _give_reward(self,volume):
        print("reward!")
        self.rewardData.extend([globalClock.getFrameTime()])
        self.do.WriteBit(3,0)
        time.sleep(self.reward_time)
        self.do.WriteBit(3,1) # put a TTL on a line to indicate that a reward was given
        pass # not yet implemented

    def _toggle_reward(self):
        if self.AUTO_REWARD:
            self.AUTO_REWARD = False
            print('switched to lick sensing for reward.')
        else:
            self.AUTO_REWARD = True
            print('switched to automatic rewards after stimuli.')

    def autoLoop2(self, task):
        dt = globalClock.getDt()
        current_time = globalClock.getFrameTime()

        self.x.extend([self.auto_position_on_track])
        self.t.extend([globalClock.getFrameTime()])

        if self.auto_presentation:
            self.auto_running = False      
            if self.in_waiting_period: 
                self.time_waited+=dt
            else:
                self.time_waited=0
                self.in_waiting_period=True
            if self.time_waited > self.wait_time: #if in cue zone,see if we have been ther for long enough
                #start a trial
                self.start_position=self.auto_position_on_track
                self.start_time=current_time
                if not self.stim_started:
                    self.start_a_presentation()
                    # print(self.stim_duration)
                    self.stim_started=True
                    self.show_stimulus=True
                else:
                    self.stim_elapsed+=dt
                    if self.stim_elapsed > self.stim_duration:
                        self.show_stimulus=False
                        self.in_reward_window=True
                        self.stop_a_presentation()
                        self.auto_restart = False
                        # print(self.current_number_of_segments)
                        self.current_number_of_segments +=9
                        #redefine the cue zone as the next one
                        self.cue_zone = arange(self.current_number_of_segments*-TUNNEL_SEGMENT_LENGTH,
                                               self.current_number_of_segments*-TUNNEL_SEGMENT_LENGTH-TUNNEL_SEGMENT_LENGTH-80,
                                                    -1) 
                        #extend cue zone, keeping old ones
                        # self.cue_zone = concatenate((self.cue_zone,arange(self.current_number_of_segments*-TUNNEL_SEGMENT_LENGTH-40,
                        #                             self.current_number_of_segments*-TUNNEL_SEGMENT_LENGTH-TUNNEL_SEGMENT_LENGTH-40,
                        #                             -1)))
                        self.contTunnel()
                        self.time_waited=0
                        self.looking_for_a_cue_zone = False
                # base.setBackgroundColor([0, 0, 1])
            else:
                pass# base.setBackgroundColor([0, 1, 0])
        else: 
            self.auto_running = True
        return Task.cont    # Since every return is Task.cont, the task will

    def gameLoop(self, task):
        # get the time elapsed since the next frame.  
        dt = globalClock.getDt()
        current_time = globalClock.getFrameTime()

        # get the camera position.
        position_on_track     = base.camera.getZ()

        #get the encoder position from NIDAQ Analog Inputs channel 2
        if have_nidaq:
            encoder_position      = self.ai.data[0][self.encodervsigchannel]  #zeroth sample in buffer [0], from ai2 [2]
        else: 
            encoder_position = base.mouseWatcherNode.getMouseX()
            
        self.previous_encoder_position = encoder_position
        #convert to track coordinates
        encoder_position_diff = (encoder_position - self.previous_encoder_position)
        # if encoder_position_diff > 4.5: encoder_position_diff -= 5.
        # if encoder_position_diff < -4.5: encoder_position_diff += 5.
        encoder_position_diff *= self.encoder_gain
        self.previous_encoder_position = encoder_position
        position_on_track = base.camera.getZ()+encoder_position_diff
        #reset the camera position
        self.camera.setPos(base.camera.getX(),base.camera.getY(),position_on_track)

        self.x.extend([position_on_track])
        self.t.extend([globalClock.getFrameTime()])

        #first check if the mouse moved on the last frame.
        if abs(self.last_position - position_on_track) < 1.5: #the mouse didn't move more than 0.5 units on the track
            self.moved=False
            if int(position_on_track) in self.cue_zone: #check for cue zone
                if self.looking_for_a_cue_zone: #make sure we transitioning from the tunnel to a cue zone
                    #increment how long we've been waiting in the cue zone. 
                    if self.in_waiting_period: 
                        self.time_waited+=dt
                    else:
                        self.time_waited=0
                        self.in_waiting_period=True
                    if self.time_waited > self.wait_time: #if in cue zone,see if we have been ther for long enough
                        #start a trial
                        self.start_position=position_on_track
                        self.start_time=current_time
                        if not self.stim_started:
                            self.start_a_presentation()
                            print(self.stim_duration)
                            self.stim_started=True
                            self.show_stimulus=True
                        else:
                            self.stim_elapsed+=dt
                            if self.stim_elapsed > self.stim_duration:
                                self.show_stimulus=False
                                self.in_reward_window=True
                                self.stop_a_presentation()
                                self.time_waited=0
                                self.looking_for_a_cue_zone = False
                        # base.setBackgroundColor([0, 0, 1])
                    else:
                        pass# base.setBackgroundColor([0, 1, 0])
            else:
                self.in_waiting_period=False
                # base.setBackgroundColor([1,0 , 0])
                if self.looking_for_a_cue_zone == False:
                    self.looking_for_a_cue_zone = True
                if self.stim_started==True:
                    self.stop_a_presentation()    
        else: #the mouse did move
            self.moved=True
            if self.stim_started==True: #check if it moved during a presenation
                self.stop_a_presentation()
                self.time_waited=0
                self.looking_for_a_cue_zone = False
                self.show_stimulus=False
        
        #if we need to add another segment, do so
        if position_on_track < self.boundary_to_add_next_segment:
            self.tunnel.extend([None])
            x = self.current_number_of_segments
            if x%8 == 0:
                self.tunnel[x] = loader.loadModel('models/grating')
                self.cue_zone = concatenate((self.cue_zone,arange(\
                    self.current_number_of_segments*-TUNNEL_SEGMENT_LENGTH,\
                    self.current_number_of_segments*-TUNNEL_SEGMENT_LENGTH-TUNNEL_SEGMENT_LENGTH-80,\
                    -1)))
            else:
                self.tunnel[x] = loader.loadModel('models/tunnel')
            self.tunnel[x].setPos(0, 0, -TUNNEL_SEGMENT_LENGTH)
            self.tunnel[x].reparentTo(self.tunnel[x - 1])
            #increment
            self.boundary_to_add_next_segment -= TUNNEL_SEGMENT_LENGTH
            self.current_number_of_segments+=1
        else: pass#print('current:'+str(position_on_track) +'      next boundary:' + str(self.boundary_to_add_next_segment))

        self.last_position = position_on_track

        # lick_times = self.
        # self._read_licks()
        return Task.cont    # Since every return is Task.cont, the task will
        # continue indefinitely, under control of the mouse
        
    def stimulusControl(self,task):
        if self.show_stimulus and not self.bufferViewer.isEnabled():
            # self.bufferViewer.toggleEnable()
            self.dr2.setDimensions(0.5, 0.9, 0.5, 0.8)
        if not self.show_stimulus and self.bufferViewer.isEnabled():
            # self.bufferViewer.toggleEnable()
            self.dr2.setDimensions(0,0.1,0,0.1)
        return Task.cont
    
    def lickControl(self,task):
        """ Checks to see if a lick is occurring. """
        ##TODO: Let user select line for lick sensing.
        if self.lickSensor:
            if self.lickSensor.Read()[self.lickline]:
                self.lickData.extend([globalClock.getFrameTime()])
                # print(self.lickData)
        elif self.keycontrol == True: #NO NI BOARD.  KEY INPUT?
            if self.keys[key.SPACE]:
                data = [globalClock.getFrameTime()]
            elif self.keys[key.NUM_1]:
                # print(self.lickData)
            # elif self.keys[key.NUM_3]:
            #     data = [0,1]
            # else:
            #     data = [0,0]
                self.lickData.extend(data)
        return Task.cont
                
    def rewardControl(self,task):
        if self.in_reward_window:
            self.reward_elapsed+=globalClock.getDt()
            if not self.AUTO_REWARD:
                if self.reward_elapsed < self.reward_window:
                    if len(np.where(np.array(self.lickData) > self.stim_off_time)[0]) > 1: # this checks if there has been more than zero licks since the stimulus turned off
                        self._give_reward(self.reward_volume)
                        self.in_reward_window=False;self.reward_elapsed=0.#reset
                else:
                    self.in_reward_window=False
                    self.reward_elapsed=0.#reset
            else:
                self._give_reward(self.reward_volume)
                self.in_reward_window=False;self.reward_elapsed=0.#reset
                # self.reward_elapsed=0.
                # base.setBackgroundColor([1, 1, 0])

        # if self.keys[key.NUM_1]:
        #     print('reward!')

        if self.reward_elapsed > self.reward_window:
            self.in_reward_window=False
            self.reward_elapsed=0.
        return Task.cont
    
    def _setupDAQ(self):
        """ Sets up some digital IO for sync and tiggering. """
        print('SETTING UP DAQ')
        try:
            if self.invertdo:
                istate = 'low'
            else:
                istate = 'high'
            self.do = DigitalOutput(self.nidevice, self.doport,
                                    initial_state='low')
            self.do.StartTask()
        except:# Exception, e:
            print("Error starting DigitalOutput task:")
            self.do = None
        try:
            self.di = DigitalInput(self.nidevice, self.diport)
            self.di.StartTask()
        except:# Exception, e:
            print("Error starting DigitalInput task:")
            self.di = None
        try:
            #set up 8 channels, only use 2 though for now
            self.ai = AnalogInput(self.nidevice, range(8), buffer_size=25,terminal_config = 'RSE',
                                    clock_speed=6000.0,voltage_range=[-5.0,5.0])
            self.ai.StartTask() 
        except:# Exception, e:
            print("Error starting AnalogInput task:")
            self.ai = None

        try:
            self.ao = AnalogOutput(self.nidevice, channels=[0, 1],terminal_config = 'RSE',
                                   voltage_range=[0.0, 5.0])
            self.ao.StartTask()
        except:# Exception, e:
            print("Error starting AnalogOutput task:")
            self.ao = None

    def close(self):
        save_path = os.path.join(os.getcwd(),'data',str(MOUSE_ID)+'_'+\
                                                    str(self.session_start_time.year)+'_'+\
                                                    str(self.session_start_time.month)+'_'+\
                                                    str(self.session_start_time.day)+'-'+\
                                                    str(self.session_start_time.hour)+'_'+\
                                                    str(self.session_start_time.minute)+'_'+\
                                                    str(self.session_start_time.second))
        if ~os.path.isdir(save_path):
            os.mkdir(save_path)
                
        print("saving data to "+save_path)
        np.save(os.path.join(save_path,'licks.npy'),self.lickData)
        np.save(os.path.join(save_path,'x.npy'),self.x)
        np.save(os.path.join(save_path,'t.npy'),self.t)
        np.save(os.path.join(save_path,'trialData.npy'),self.trialData)
        np.save(os.path.join(save_path,'rewardData.npy'),self.rewardData)

        print('rewardData:')
        print(np.shape(self.rewardData))
        sys.exit(0) 




app = MouseTunnel()
app.run()