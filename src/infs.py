#!/usr/bin/env python

##############################################################################
## license : GPLv3+
##============================================================================
##
## File :        infs.py
## 
## Project :     NewportInfinityMeter
##
## This file is part of Tango device class.
## 
## Tango is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
## 
## Tango is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
## 
## You should have received a copy of the GNU General Public License
## along with Tango.  If not, see <http://www.gnu.org/licenses/>.
## 
##
## $Author :      sblanch$
## Copyright 2013 CELLS / ALBA Synchrotron, Bellaterra, Spain
##
## $Revision :    $
##
## $Date :        $
##
## $HeadUrl :     $
##############################################################################

import PyTango
import taurus
import array
import time
import traceback
import threading

MINREADTIME = 0.05
ANSWERRETRIES = 10

class InfinityMeterSerial(taurus.Logger):
    '''The abstract superclass.
    '''
    def __init__(self):
        taurus.Logger.__init__(self,"INFS")

class INFSSerialDevFile(InfinityMeterSerial):
    '''Class to manage the communications using a /dev/tty* file.
    '''
    def __init__(self,fileName):
        InfinityMeterSerial.__init__(self)
        self._fileName =fileName
        self._file = None
    def usesTango(self):
        return False
    def open(self):
        self._file = open(self._fileName,'r+')#Read and write
    def close(self):
        if self._file != None:
            self._file.close()
    def isOpen(self):
        if self._file != None and not self._file.closed:
            return True
        return False
    def flush(self):
        self._file.flush()
        while len(self._file.readline()) != 0:
            pass
    def write(self,address,command):
        cmd = "*%s%s\r"%(address,command)
        self.debug("sending: %s"%(repr(cmd)))
        self._file.write(cmd)
    def read(self):
        answer = self._file.readline()
        self.debug("received %s"%(repr(answer)))
        return answer

class INFSTango(InfinityMeterSerial):
    '''Abstract class for communicate using Tango.
    '''
    def __init__(self,proxy):
        InfinityMeterSerial.__init__(self)
        self._proxy = proxy
    def usesTango(self):
        return True

class INFSSerialDevice(INFSTango):
    '''Class to manage the communications using a Tango device 
       with Serial DeviceClass.
    '''
    def __init__(self,proxy):
        INFSTango.__init__(self,proxy)
    #FIXME: check this device class methods for open&close (and isOpen)
    def open(self):
        pass
    def close(self):
        pass
    def isOpen(self):
        pass
    def flush(self):
        self._proxy.DevSerFlush(2)
    def write(self,address,command):
        cmd = "*%s%s\r"%(address,command)
        self.debug("sending: %s"%(repr(cmd)))
        self._proxy.DevSerWriteString(cmd)
    def read(self):
        answer = self._proxy.DevSerReadNChar(13)
        self.debug("received %s"%(repr(answer)))
        return answer

class INFSPySerialDevice(INFSTango):
    '''Class to manage the communications using a Tango device 
       with PySerial DeviceClass.
    '''
    def __init__(self,proxy):
        INFSTango.__init__(self,proxy)
    def open(self):
        if self._proxy.state() == PyTango.DevState.OFF:
            self._proxy.open()
    def close(self):
        if self._proxy.state() == PyTango.DevState.ON:
            self._proxy.close()
    def isOpen(self):
        if self._proxy.state() == PyTango.DevState.ON:
            return True
        return False
    def flush(self):
        self._proxy.FlushInput()
        self._proxy.FlushOutput()
    def write(self,address,command):
        cmd = "*%s%s\r"%(address,command)
        cmdlist = array.array('B',cmd).tolist()
        self.debug("sending: %s"%(repr(cmd)))
        self._proxy.write(cmdlist)
    def read(self):
        answer = array.array('B',self._proxy.readline()).tostring()
        self.debug("received %s"%(repr(answer)))
        return answer

MAXSUBSCRIPTORS = 10
TIMEBETWEENREAD = 0.25
RECONNECTTHRESHOLD = 10
RECONNECTDELAY = 1#s

UNFILTERED = 'UnfilteredValue'
PEAK = 'PeakValue'
VALLEY = 'ValleyValue'
FILTERED = 'FilteredValue'

class InfinityMeter(taurus.Logger):
    '''Interface class to made the connection transparent and 
       homogeneous access.
    '''

    commands = {UNFILTERED:'X01',
                PEAK:      'X02',
                VALLEY:    'X03',
                FILTERED:  'X04'}

    def __init__(self,serialName,
                 addr='',sleepTime=MINREADTIME,statusCallback=None,
                 logLevel=taurus.Logger.Info):
        self._name = "INFS%s"%addr
        taurus.Logger.__init__(self,self._name)
        threading.currentThread().setName(self._name)
        if serialName.startswith('/dev/tty'):
            #this will connect direct by serial line
            self._serial = INFSSerialDevFile(serialName)
        else:
            #other way, it shall be a tango device name 
            #of a serial or a pyserial
            try:
                proxy = PyTango.DeviceProxy(serialName)
            except PyTango.DevFailed,e:
                raise NameError(e.args[-1].desc)
            if proxy.info().dev_class == 'PySerial':
                self._serial = INFSPySerialDevice(proxy)
            elif proxy.info().dev_class == 'Serial':
                self._serial = INFSSerialDevice(proxy)
            else:
                raise NotImplementedError("Unable to identify how to manage "\
                                          "the given name %s"%(serialName))
        self._serial.setLogLevel(logLevel)
        self._address = addr
        if sleepTime>=TIMEBETWEENREAD:
            self._sleepTime = sleepTime
        else:
            #TODO: trace that
            self._sleepTime = TIMEBETWEENREAD
        self._lastRead = None
        self._statusCallback = statusCallback
        #threading area for subscriptions
        self._joinerEvent = threading.Event()#to communicate between threads
        self._joinerEvent.clear()
        self._threadLoopCondition = threading.Condition()
        self._mutex = threading.Lock()
        self._thread = None
        self._subscribers = {}
        self._answers = {}
        self._identifiers = []
        #Hackish
        self._failedReading = 0
    def __del__(self):
        '''Before the object destruction, is necessary to stop the 
           subscription thread.
        '''
        self.info("Deleting %s"%self._name)
        self.close()
        for id in self._identifiers:
            self.unsubscribe(id)
        while self._thread.isAlive():
            self.info("Waiting monitor thread to finish")
            try:
                self._thread.join(1)
            except RuntimeError,e:
                self.error("RuntimeError: %s"%(e))
                break
    def usesTango(self):
        return self._serial.usesTango()
    def pushStatusCallback(self,msgType,msgText):
        if self._statusCallback != None:
            try:
                self._statusCallback(msgType,msgText)
            except:
                self.error("Exception pushing status(%d:%s): %s"
                           %(msgType,msgText,e))
        else:
            self.warning("No callback to push %d:%s"%(msgType,msgText))

    #####
    #---- #communications
    def open(self):
        if self._thread != None and self._thread.isAlive() and \
                                                 not self._joinerEvent.isSet():
            self.error("Avoiding an Open try! Thread is ")
        self._thread = threading.Thread(target=self.startThread)
        self._thread.setName("%sMonitor"%self._name)
        self._serial.open()
        self._joinerEvent.clear()
        self._thread.start()
    def close(self):
        self._serial.close()
        self._joinerEvent.set()
        self.V()
    def _flush(self):
        self._serial.flush()
    def _write(self,command):
        self._serial.write(self._address,command)
    def _read(self):
        return self._serial.read()

    #TODO: this Semafore usage should be made using a decorator to avoid any 
    #      forgoten mutex release.
    def P(self):
        self.debug("P(mutex)")
        return self._mutex.acquire()
    def V(self):
        self.debug("V(mutex)")
        self._mutex.release()

    def _sendAndReceive(self,cmd):
        '''Usually a write operation to this instrument is an information 
           request to it. This method manages the write and the needed read.
        '''
        if not self._lastRead == None:
            diff_t = time.time() - self._lastRead
            if diff_t < TIMEBETWEENREAD:
                #When not enough time between reads, wait what's missing
                time.sleep(TIMEBETWEENREAD - diff_t)
        self._flush()
        self._lastRead = time.time()
        self.P()
        self._write(cmd)
        i = 0
        while i < ANSWERRETRIES:
            time.sleep(self._sleepTime)
            answer = self._read()
            if len(answer) != 0:
                break
            i += 1
        if i == ANSWERRETRIES:
            self.error("Too many null answers to '%s%s'"
                       %(self._address,repr(cmd)[1:-1]))
            #FIXME: this doesn't work fine
            self._failedReading += 1
            if self._failedReading >= RECONNECTTHRESHOLD:
                try:
                    msg = "Too many failed readings, closing connection "\
                          "and try to reconnect in %d second."\
                          %(RECONNECTDELAY)
                    self.pushStatusCallback(Logger.warning,msg)
                    self._serial.close()
                    time.sleep(RECONNECTDELAY)
                    self._failedReading = 0
                    self._serial.open()
                except Exception,e:
                    msg = "Error in reconnection: %s"%(e)
                    self.pushStatusCallback(Logger.Error,msg)
                    self.error(msg)
            self.V()
            raise ValueError("No answer received to '%s%s'"
                             %(self._address,repr(cmd)[1:-1]))
        self._failedReading = 0
        self.V()
        return self._postprocessAnswer(cmd, answer)
    
    def _postprocessAnswer(self,cmd,answer):
        '''An answer received from the instrument shall be review because it 
           can come from a different request, or reports an overflow in the 
           instrument, or simply the answer is not complete.
        '''
        if answer.count('?'):
            # IN CASE OF OVERFLOW, THE ANSWER IS: 
            # '0_X0_?+999999\r'
            #Also saw messages like '01?43\r'
            self.warning("Received an overflow answer: %s"%(repr(answer)))
            #raise OverflowError("")
            return float('NaN')
        if not answer.startswith(self._address):
            self.error("Answer %s is not from the expected address %s."
                       %(repr(answer),self._address))
            return float('NaN')
        command = "%s%s"%(self._address,cmd)
        if not answer.startswith(command):
            self.error("Answer %s is not to my question '*%s\\r'."
                       %(repr(answer),command))
            return float('NaN')
        else:
            #FIXME: this is no exception protected.
            answer = answer.strip().replace(command,'')
            self.debug("Answer string: %s"%(repr(answer)))
            return float(answer)
    #---- done communications
    #####
    
    #####
    #---- # object methods
    def getValue(self,cmd):
        if self._answers.has_key(cmd):
            if self._answers[cmd] == None:
                self.warning("There are subscriptors for %s, "\
                             "but nothing read yet!"%(cmd))
                self._answers[cmd] = self._sendAndReceive(self.commands[cmd])
            return self._answers[cmd]
        #If there is no subscriptors do the request
        self.debug("No subscriptor for %s, force send&receive."%(cmd))
        return self._sendAndReceive(self.commands[cmd])
    def getUnfilteredValue(self):
        return self.getValue(UNFILTERED)
    def getPeakValue(self):
        return self.getValue(PEAK)
    def getValleyValue(self):
        return self.getValue(VALLEY)
    def getFilteredValue(self):
        return self.getValue(FILTERED)
    #---- done object methods
    #####
    
    #####
    #---- # Subscription
    def subscribe(self,command,callback=None):
        '''With this method a class that has an instance of this one, will have
           a subscription identifier in the return value to manage 
           unsubscriptions.
           The input parameters describe to which of the available commands
           will be subscribed and what has to be called to pass the answer.
           This callback function will contain, as a parameter, the value.
        '''
        self._threadLoopCondition.acquire()
        try:
            id = self.bookNewIdentifier()
        except Exception,e:
            #release if there is no more subscriptions available and rethrow
            self._threadLoopCondition.release()
            raise e
        if not command in self.commands.keys():
            raise LookupError("Unrecognized command %s"%(command))
        if not self._answers.has_key(command):
            #This mean that there are no subscribers yet
            self._answers[command] = None
            if not self._subscribers.has_key(command):
                self._subscribers[command] = {}
        self._subscribers[command][id] = callback
        self._threadLoopCondition.notifyAll()
        self._threadLoopCondition.release()
        self.info("New subscription (%s) to %s"%(id,command))
        return id
    
    def unsubscribe(self,id):
        '''As a counter-method for the subscription it shall be possible of a
           subscriber to report that no information is needed any more.
        '''
        if not self._identifiers.count(id):
            raise LookupError("Not recognized %d identifier"%(id))
        if len(self._subscribers.keys()) > 0:
            self._threadLoopCondition.acquire()
            for cmd in self._subscribers.keys():
                if self._subscribers[cmd].has_key(id):
                    self._subscribers[cmd].pop(id)
                    if len(self._subscribers[cmd].keys()) == 0:
                        self._answers.pop(cmd)
                    self._threadLoopCondition.notifyAll()
                    break
            try:
                self._identifiers.pop(self._identifiers.index(id))
            except ValueError,e:
                self.warn("When unsubscribing exception: %s"%e)
            else:
                self.info("Unsubscription for %d"%(id))
            self._threadLoopCondition.release()
        #FIXME: if there are no more subscriptors, may signal the thread to rest
    
    def bookNewIdentifier(self):
        '''This shall grant a unique identifier to a new subscriber and 
           internally store the information about identifiers already in use.
        '''
        i = 0
        while self._identifiers.count(i):
            i += 1
        if i >= MAXSUBSCRIPTORS:
            raise ValueError("No more subscription slots available")
        self._identifiers.append(i)
        self._identifiers.sort()
        return i
    
    def startThread(self):
        '''This method is used for the periodic monitor the elements to be
           read from the instrument, store the new values correctly and call 
           the subscribers if they have provided a callback function.
        '''
        if not hasattr(self,'_joinerEvent'):
            raise Exception("Not possible to start the loop because "\
                            "it have not end condition")
        while not self._joinerEvent.isSet():
            self._threadLoopCondition.acquire()
            try:
                if len(self._identifiers) == 0:
                    self.debug("No one subscribed, passive sleep")
                    self._threadLoopCondition.wait()
                for command in self._answers:
                    #FIXME: can the readings be concatenated?
                    self._answers[command] = \
                                   self._sendAndReceive(self.commands[command])
                for command in self._subscribers:
                    if self._answers.has_key(command):
                        for id in self._subscribers[command]:
                            cb = self._subscribers[command][id]
                            if cb != None:
                                try:
                                    cb(command,self._answers[command])
                                except Exception,e:
                                    self.error("Callback exception for "\
                                               "id %d: %s"%(id,e))
            except Exception,e:
                self.error("Thread exception: %s"%(e))#FIXME:
            self._threadLoopCondition.release()
        self.info("Ending %s thread"%(threading.currentThread().getName()))
    #---- done Subscription
    #####

def main():
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option('-s',"--serial",default=None,
                      help="String with the reference name "\
                      "to use for serial line connection.")
    parser.add_option('-a',"--address",default='',
                      help="Two digit string with the address of the INFS.")
    parser.add_option('-t',"--sleep",type="float",default=MINREADTIME,
                      help="Wait time between write and read operations")
    parser.add_option('',"--log-level",default="info",
                      help="Define the logging level to print out. Allowed "\
                      "values error|warning|info|debug, being info the "\
                      "default")
    parser.add_option('-r',"--reads",type='int',default=1,
                      help="Number of consecutive sets of readings")
    (options, args) = parser.parse_args()
    logLevel = {'error':taurus.Logger.Error,
                'warning':taurus.Logger.Warning,
                'info':taurus.Logger.Info,
                'debug':taurus.Logger.Debug
               }[options.log_level.lower()]
    if options.serial != None:
        try:
            infs = InfinityMeter(options.serial,options.address,
                                 options.sleep,logLevel)
            for i in range(1,options.reads+1):
                infs.open()
                infs._flush()
                unfiltered = infs.getUnfilteredValue()
                peak = infs.getPeakValue()
                valley = infs.getValleyValue()
                filtered = infs.getFilteredValue()
                print("read: %d/%d\n"\
                      "Unfiltered: %g\n"\
                      "Filtered:   %g\n"\
                      "Peak:       %g\n"\
                      "Valley:     %g\n"
                      %(i,options.reads,unfiltered,filtered,peak,valley))
                infs.close()
        except Exception,e:
            print("Error testing the Infinity Meter: '%s'"%(e))
            traceback.print_exc()
            sys.exit(-1)

if __name__ == "__main__":
    '''When this file is called from the command line a test is performed 
       using the argument as the builder for the serial line communication.
    '''
    import sys
    main()
    
