#!/usr/bin/env python

##############################################################################
## license : GPLv3+
##============================================================================
##
## File :        OmegaCommunications.py
## 
## Project :     NewportOmega
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

import serial
import PyTango
import taurus
import array
import time
import traceback
import threading

class OmegaSerial(taurus.Logger):
    '''The abstract superclass.
    '''
    def __init__(self):
        taurus.Logger.__init__(self,"OMEGA")

MAXFLUSHIT = 10

class OmegaSerialDevFile(OmegaSerial):
    '''Class to manage the communications using a /dev/tty* file.
    '''
    _timeout = 0.1
    _wtimeout = 0.1
    def __init__(self,fileName,baudrate=19200,databits=serial.SEVENBITS,
                 parity=serial.PARITY_ODD,stopbits=serial.STOPBITS_ONE):
        OmegaSerial.__init__(self)
        self._fileName =fileName
        self._file = None
        self._baudrate = baudrate
        self._databits = databits
        self._parity = parity
        self._stopbits = stopbits
        
    def __str__(self):
        return "%s (%d,%d,%d,%s)"%(self._fileName,self._baudrate,\
                                   self._databits,self._stopbits,self._parity)
    def usesTango(self):
        return False
    def open(self):
        try:
            self._file = serial.Serial(port=self._fileName,
                                       baudrate=self._baudrate,
                                       bytesize=self._databits,
                                       parity=self._parity,
                                       stopbits=self._stopbits,
                                       xonxoff=1,
                                       timeout=self._timeout,
                                       writeTimeout=self._wtimeout)
            return True
        except serial.SerialException,e:
            self.error("Cannot open %s due to:\n\t\"%s\""%(self._fileName,e))
        except Exception,e:
            self.error("Cannot open %s due to:\n\t\"%s\""%(self._fileName,e))
            traceback.print_exc()
        return False
    def close(self):
        if self._file != None:
            try:
                self._file.close()
                return True
            except Exception,e:
                self.error("Cannot close %s due to: %s"%(self._fileName,e))
        return False
    def isOpen(self):
        if self._file != None and self._file.isOpen():
            return True
        return False
    def flush(self):
        if self._file != None:
            try:
                if self._file.inWaiting() != 0:
                    self.debug("flushing incomming %d elements."
                               %(self._file.inWaiting()))
                    self._file.flushInput()
                #don't flush the output or it stays a long while the instrument
                #has been unplugged of the serial line.
                #self._file.flushOutput()
                return True
            except Exception,e:
                self.error("Flush Exception: %s"%(e))
            return False
        self.warning("Flushing unexisting descriptor!")
        return False
    def write(self,address,command):
        try:
            cmd = "*%s%s\r"%(address,command)
            self.debug("sending: %s"%(repr(cmd)))
            self._file.write(cmd)
        except serial.SerialTimeoutException,e:
            self.error("Timeout doing write: %s"%(e))
        except Exception,e:
            self.error("Write fail due to: %s"%(e))
    def read(self):
        try:
            answer = self._file.readline()
            self.debug("received %s"%(repr(answer)))
            return answer
        except serial.SerialTimeoutException,e:
            self.error("Timeout doing read: %s"%(e))
        except Exception,e:
            self.error("Read fail due to: %s"%(e))
        return ""

class OmegaTango(OmegaSerial):
    '''Abstract class for communicate using Tango.
    '''
    def __init__(self,proxy):
        OmegaSerial.__init__(self)
        self._proxy = proxy
    def __str__(self):
        return "%s"%(self._proxy.name)
    def usesTango(self):
        return True

class OmegaSerialDevice(OmegaTango):
    '''Class to manage the communications using a Tango device 
       with Serial DeviceClass.
    '''
    def __init__(self,proxy):
        OmegaTango.__init__(self,proxy)
    #FIXME: check this device class methods for open&close (and isOpen)
    def open(self):
        raise NotImplementedError("Not available yet.")
    def close(self):
        raise NotImplementedError("Not available yet.")
    def isOpen(self):
        raise NotImplementedError("Not available yet.")
    def flush(self):
        self._proxy.DevSerFlush(2)
        return True
    def write(self,address,command):
        cmd = "*%s%s\r"%(address,command)
        self.debug("sending: %s"%(repr(cmd)))
        self._proxy.DevSerWriteString(cmd)
    def read(self):
        answer = self._proxy.DevSerReadNChar(13)
        self.debug("received %s"%(repr(answer)))
        return answer

class OmegaPySerialDevice(OmegaTango):
    '''Class to manage the communications using a Tango device 
       with PySerial DeviceClass.
    '''
    def __init__(self,proxy):
        OmegaTango.__init__(self,proxy)
    def open(self):
        if self._proxy.state() == PyTango.DevState.OFF:
            self._proxy.open()
            if self.isOpen():
                return True
        return False
    def close(self):
        if self._proxy.state() == PyTango.DevState.ON:
            self._proxy.close()
            if not self.isOpen():
                return True
        return False
    def isOpen(self):
        if self._proxy.state() == PyTango.DevState.ON:
            return True
        return False
    def flush(self):
        try:
            self._proxy.FlushInput()
            self._proxy.FlushOutput()
            return True
        except:
            return False
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
MINREADTIME = 0.05
TIMEBETWEENREAD = 0.5
ANSWERRETRIES = 5
RECONNECTTHRESHOLD = 2
RECONNECTLIMIT = 1
RECONNECTDELAY = 0.5#s

UNFILTERED = 'UnfilteredValue'
PEAK = 'PeakValue'
VALLEY = 'ValleyValue'
FILTERED = 'FilteredValue'

class Omega(taurus.Logger):
    '''Interface class to made the connection transparent and 
       homogeneous access.
    '''

    commands = {UNFILTERED:'X01',
                PEAK:      'X02',
                VALLEY:    'X03',
                FILTERED:  'X04'}
    errors = {"43":"Command Error",
              "46":"Format Error",
              "48":"Checksum Error",
              "50":"Parity Error",
              "4C":"Calibration/Write Lockout Error",
              "45":"EEPROM Write Lockout Error",
              "56":"Serial Device Address Error"}

    def __init__(self,serialName,
                 addr='',sleepTime=MINREADTIME,statusCallback=None,
                 logLevel=taurus.Logger.Info):
        self._name = "OMEGA%s"%addr
        taurus.Logger.__init__(self,self._name)
        threading.currentThread().setName(self._name)
        self._serial = None
        if serialName.startswith('/dev/tty'):
            #this will connect direct by serial line
            try:
                self._serial = OmegaSerialDevFile(serialName)
            except Exception,e:
                msg = "Failed to build serial line manager for %s: %s"\
                      %(serialName,e)
                self.errors(msg)
                self.pushStatusCallback(taurus.Logger.Error,msg)
                return
        else:
            #other way, it shall be a tango device name 
            #of a serial or a pyserial
            try:
                proxy = PyTango.DeviceProxy(serialName)
            except PyTango.DevFailed,e:
                raise NameError(e.args[-1].desc)
            if proxy.info().dev_class == 'PySerial':
                self._serial = OmegaPySerialDevice(proxy)
            elif proxy.info().dev_class == 'Serial':
                self._serial = OmegaSerialDevice(proxy)
            else:
                raise NotImplementedError("Unable to identify how to manage "\
                                          "the given name %s"%(serialName))
        self._serial.setLogLevel(logLevel)
        self._address = addr
        if sleepTime>=MINREADTIME:
            self._sleepTime = sleepTime
        else:
            #TODO: trace that
            self._sleepTime = MINREADTIME
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
        self._failedReconnections = 0
    def __del__(self):
        '''Before the object destruction, is necessary to stop the 
           subscription thread.
        '''
        self.info("Deleting %s"%self._name)
        self.close()
        self.unsubscribeAll()
        while self._thread.isAlive():
            self.info("Waiting monitor thread to finish")
            try:
                self._thread.join(1)
            except RuntimeError,e:
                self.error("RuntimeError: %s"%(e))
                break
    def __str__(self):
        if self._serial != None:
            return "Omega(%s)"%(self._serial)
        return "Omega(None)"
    def usesTango(self):
        if self._serial != None:
            return self._serial.usesTango()
        return False
    def pushStatusCallback(self,msgType,msgText):
        if self._statusCallback != None:
            try:
                self._statusCallback(msgType,msgText)
            except Exception,e:
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
        if self._serial != None and self._serial.open():
            self._joinerEvent.clear()
            self._thread.start()
            return True
        else:
            self.pushStatusCallback(taurus.Logger.Error,
                                    "Open() to the instrument has failed.")
            return False
    def close(self):
        if hasattr(self,'_joinerEvent'):
            self._joinerEvent.set()
        if self._serial != None:
            self._serial.close()
#            while not self.P(blocking=False,trace=False):
#                self.V()
            return True
        else:
            self.pushStatusCallback(taurus.Logger.Error,
                                    "Non opened instrument cannot be closed.")
            return False
    def isOpen(self):
        return self._serial.isOpen()
    def isAlive(self):
        return self._thread.isAlive()
    def _flush(self):
        if self._serial != None:
            return self._serial.flush()
    def _write(self,command):
        self.debug("write(%s)"%command)
        if self._serial != None:
            self._serial.write(self._address,command)
            return
        self.pushStatusCallback(taurus.Logger.Error,
                                "Non opened instrument cannot be written.")
    def _read(self):
        self.debug("read()")
        if self._serial != None:
            return self._serial.read()
        self.pushStatusCallback(taurus.Logger.Error,
                                "Non opened instrument cannot be read.")

    #TODO: this Semafore usage should be made using a decorator to avoid any 
    #      forgoten mutex release.
    def P(self,blocking=True,trace=True):
        if trace==True:
            self.debug("P(mutex) %s"
                       %("blocking" if blocking else "non blocking"))
        return self._mutex.acquire(blocking)
    def V(self):
        self.debug("V(mutex)")
        self._mutex.release()
    def isMutexLocked(self):
        return self._mutex.locked()

    def __checklastRead(self):
        if not self._lastRead == None:
            diff_t = time.time() - self._lastRead
            if diff_t < TIMEBETWEENREAD:
                t = TIMEBETWEENREAD - diff_t
                self.debug("Not enough time between reads (%f), wait %f left"
                           %(diff_t,t))
                time.sleep(t)
                self.debug("wake up!")

    def _sendAndReceive(self,cmd,blocking=True):
        '''Usually a write operation to this instrument is an information 
           request to it. This method manages the write and the needed read.
        '''
        self.debug("_sendAndReceive(%s) [Mutex %s]"
                   %(cmd,"locked" if self.isMutexLocked() else "unlocked"))
        self.__checklastRead()
        if self._joinerEvent.isSet():
            return float('NaN')
        self._lastRead = time.time()
        if not self._flush():
            self.pushStatusCallback(taurus.Logger.Error,
                                    "Flush exception, check communications")
        if not self.P(blocking):
            self.debug("abort _sendAndReceive()")
            return float('NaN')
        if self._serial == None:
            self.pushStatusCallback(taurus.Logger.Error,
                                "Non opened instrument cannot do send&receive")
        if not self._serial.isOpen() or self._joinerEvent.isSet():
            self.debug("abort _sendAndReceive()")
            return float('NaN')
        self._write(cmd)
        i = 0
        while i < ANSWERRETRIES:
            t = self._sleepTime+(self._sleepTime*i*0.1)
            self.debug("going to sleep %f seconds"%(t))
            time.sleep(t)
            answer = self._read()
            if len(answer) != 0:
                break
            if self._joinerEvent.isSet():
                break
            i += 1
        if i == ANSWERRETRIES:
            self.error("Too many (%d) null answers to '%s%s'"
                       %(i,self._address,repr(cmd)[1:-1]))
            #FIXME: this doesn't work fine
            self._failedReading += 1
            self.V()
            raise ValueError("No answer received to '%s%s'"
                             %(self._address,repr(cmd)[1:-1]))
        self._failedReading = 0
        self.V()
        return self._postprocessAnswer(cmd, answer)

    def reconnect(self):
        '''This method disconnects from the instrument and releases the mutex
           to clean up the queue of requests. After a constant defined time
           it tries to make a connection again.
        '''
        try:
#            msg = "Too many failed readings, closing connection and try "\
#                  "to reconnect in %d second. (previously %d failed "\
#                  "recoconnections)"%(RECONNECTDELAY,self._failedReconnections)
            msg = "Too many failed readings, review connection and call Init()"
            self.pushStatusCallback(taurus.Logger.Error,msg)
            self.warning(msg)
            if self._serial == None:
                self.pushStatusCallback(taurus.Logger.Error,
                              "Non existing instrument cannot be reconnected.")
                return
            self._serial.close()
            while self.isMutexLocked():#not self.P(blocking=False):
                self.debug("releasing mutex")
                self.V()
            time.sleep(RECONNECTDELAY)
            self._failedReading = 0
            if self._serial.open():
                self.pushStatusCallback(taurus.Logger.Info,
                                        "(re)Connected to the instrument.")
                self.info("reconnected")
            else:
                self.pushStatusCallback(taurus.Logger.Error,
                                        "Cannot be stablished communication "\
                                        "with the instrument.")
        except Exception,e:
            msg = "Error in reconnection: %s"%(e)
            self.pushStatusCallback(taurus.Logger.Error,msg)
            self.error(msg)
    
    def _postprocessAnswer(self,cmd,answer):
        '''An answer received from the instrument shall be review because it 
           can come from a different request, or reports an overflow in the 
           instrument, or simply the answer is not complete.
        '''
        self.debug("_postprocessAnswer(%s,%r)"%(cmd,answer))
        if answer.count('?'):
            # IN CASE OF OVERFLOW, THE ANSWER IS: 
            # '0_X0_?+999999\r'
            #Also saw messages like '01?43\r'
            #other errors in dictionary errors
            self.__interpretErrorCode(answer.strip().split('?')[1])
            return float('NaN')
        command = "%s%s"%(self._address,cmd)
        if not answer.startswith(self._address):
            self.pushStatusCallback(taurus.Logger.Warning,"Answer %s is not "\
                                    "from the expected address %s."
                                    %(repr(answer),self._address))
            return float('NaN')
        elif not answer.startswith(command):
            self.pushStatusCallback(taurus.Logger.Warning,"Answer %s is not "\
                                   "for the question '*%s\\r'."
                                   %(repr(answer),command))
            return float('NaN')
        else:
            #FIXME: this is no exception protected.
            answer = answer.strip().replace(command,'')
            self.debug("Answer string: %s"%(repr(answer)))
            return float(answer)
    
    def __interpretErrorCode(self,errorCode):
        '''
        '''
        if self.errors.has_key(errorCode):
            self.pushStatusCallback(taurus.Logger.Warning,"Received an "\
                                    "error %s: %s"%(errorCode,
                                              self.errors[errorCode]))
        elif errorCode.startswith('+') or errorCode.startswith('-') and \
                                       int(errorCode) in [+999999,-999999]:
            self.pushStatusCallback(taurus.Logger.Warning,"Received an "\
                                    "overflow answer: %s"%(repr(errorCode)))
        else:
            self.pushStatusCallback(taurus.Logger.Warning,"Receiver an "\
                                    "unknown error code: %s"
                                    %(repr(errorCode)))
    #---- done communications
    #####
    
    #####
    #---- # object methods
    def getValue(self,cmd):
        if self._answers.has_key(cmd):
            if self._answers[cmd] == None:
                self.warning("There are subscriptors for %s, "\
                             "but nothing read yet!"%(cmd))
                self._answers[cmd] = float('NaN')
            return self._answers[cmd]
        #If there is no subscriptors do the request
        self.debug("No subscriptor for %s, force send&receive."%(cmd))
        return self._sendAndReceive(self.commands[cmd],blocking=False)
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
    
    def unsubscribeAll(self):
        for id in self._identifiers:
            self.unsubscribe(id)
    
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
        time.sleep(RECONNECTDELAY)
        while not self._joinerEvent.isSet():
            self._threadLoopCondition.acquire()
            try:
                if len(self._identifiers) == 0:
                    self.debug("No one subscribed, passive sleep")
                    self._threadLoopCondition.wait()
                for command in self._answers:
                    #FIXME: can the readings be concatenated?
                    try:
                        self._answers[command] = \
                                   self._sendAndReceive(self.commands[command])
                    except ValueError,e:
                        self.warning("ValueError from %s: %s"%(command,e))
                        if self._failedReconnections >= RECONNECTLIMIT:
                            msg = "reach %d consecutive reconnections "\
                                  "failed: no more tries (review and Init())"\
                                  %(self._failedReconnections)
                            self.pushStatusCallback(taurus.Logger.Error,msg)
                        elif self._failedReading >= RECONNECTTHRESHOLD:
                            self.reconnect()
                            #check if the reconnection has succeed
                            try:
                                self._answers[command] = \
                                   self._sendAndReceive(self.commands[command])
                            except:
                                self._failedReconnections += 1
                                self.callthecallbacks(command,float('NaN'))
                            else:
                                self._failedReconnections = 0
                                msg = "Connected to the instrument."
                                self.pushStatusCallback(taurus.Logger.Info,msg)
                        else:
                            self._answers[command] = float('NaN')
                for command in self._subscribers:
                    if self._answers.has_key(command):
                        if self._answers[command] != None:
                            self.callthecallbacks(command,\
                                                        self._answers[command])
                        else:
                            self.callthecallbacks(command,float('NaN'))
            except Exception,e:
                self.error("Thread exception: %s"%(e))#FIXME:
                traceback.print_exc()
                self.pushStatusCallback(taurus.Logger.Error,
                                "Communication cut. Please Init() the device.")
            self._threadLoopCondition.release()
        self.info("Ending %s thread"%(threading.currentThread().getName()))
        
    def callthecallbacks(self,command,value):
        for id in self._subscribers[command]:
            cb = self._subscribers[command][id]
            if cb != None:
                try:
                    cb(command,value)
                except Exception,e:
                    self.error("Callback exception for "\
                               "id %d: %s"%(id,e))
        
    #---- done Subscription
    #####

def parallelWriteTest(omega):
    '''We may speed up multiple readings by doing write operation with multiple
       requests.
       But the instrument looks that doesn't support it.
    '''
    address = omega._address
    concatenation = ""
    for command in [UNFILTERED,PEAK,VALLEY,FILTERED]:
        cmd = "*%s%s\r"%(address,omega.commands[command])
        concatenation = "%s%s"%(concatenation,cmd)
    print("sending %r"%(concatenation))
    omega._serial._file.write(cmd)
    answer = ""
    j = 0
    while len(answer) == 0 and j < ANSWERRETRIES:
        time.sleep(TIMEBETWEENREAD)
        answer = omega._serial._file.read()
        j += 1
    print("%r (%d tries)"%(answer,j))
    unfiltered = float('nan')
    peak = float('nan')
    valley = float('nan')
    filtered = float('nan')
    if answer.count("\r") != 0:
        alist = answer.split('\r')
        for i,cmd in enumerate([UNFILTERED,PEAK,VALLEY,FILTERED]):
            value = omega._postprocessAnswer(omega.commands[cmd],
                                            alist[i])
            if cmd == UNFILTERED: unfiltered = value
            elif cmd == PEAK: peak = value
            elif cmd == VALLEY: valley = value
            elif cmd == FILTERED: filtered = value
    else:
        print("\n\t --- THIS INSTRUMENT DOES NOT SUPPORT "\
              "PARALLEL READINGS! ---\n")
        return

def readAll(omega,n,parallel=False):
    '''One of the tests is to proceed to read many times all the needed values
       from the instrument.
       This shall advise if this feature is not supported!
    '''
    print("readAll(%s,%d,%s)"%(omega,n,parallel))
    for i in range(1,n+1):
        omega.open()
        omega._flush()
        if parallel:
            try:
                parallelWriteTest(omega)
            except Exception,e:
                print("Exception trying to do parallel writes: %s"%(e))
            return
        else:
            unfiltered = omega.getUnfilteredValue()
            peak = omega.getPeakValue()
            valley = omega.getValleyValue()
            filtered = omega.getFilteredValue()
        print("read: %d/%d\n"\
              "Unfiltered: %g\n"\
              "Filtered:   %g\n"\
              "Peak:       %g\n"\
              "Valley:     %g\n"
              %(i,n,unfiltered,filtered,peak,valley))
        omega.close()

def main():
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option('-s',"--serial",default=None,
                      help="String with the reference name "\
                      "to use for serial line connection.")
    parser.add_option('-a',"--address",default='',
                      help="Two digit string with the address of the OMEGA.")
    parser.add_option('-t',"--sleep",type="float",default=MINREADTIME,
                      help="Wait time between write and read operations")
    parser.add_option('',"--log-level",default="info",
                      help="Define the logging level to print out. Allowed "\
                      "values error|warning|info|debug, being info the "\
                      "default")
    parser.add_option('-r',"--reads",type='int',default=1,
                      help="Number of consecutive sets of readings")
    parser.add_option('',"--parallel-read",action="store_true",default=False,
                      help="")
    (options, args) = parser.parse_args()
    logLevel = {'error':taurus.Logger.Error,
                'warning':taurus.Logger.Warning,
                'info':taurus.Logger.Info,
                'debug':taurus.Logger.Debug
               }[options.log_level.lower()]
    if options.serial != None:
        try:
            omega = Omega(options.serial,
                          addr=options.address,
                          sleepTime=options.sleep,
                          statusCallback=None,
                          logLevel=logLevel)
            readAll(omega,options.reads,options.parallel_read)
        except Exception,e:
            print("Error testing the Infinity Meter: '%s'"%(e))
            traceback.print_exc()
            sys.exit(-1)
    sys.exit(0)

if __name__ == "__main__":
    '''When this file is called from the command line a test is performed 
       using the argument as the builder for the serial line communication.
    '''
    import sys
    main()
    
