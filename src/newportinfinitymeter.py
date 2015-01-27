#!/usr/bin/env python
# -*- coding:utf-8 -*- 


##############################################################################
## license :
##============================================================================
##
## File :        NewportInfinityMeter.py
## 
## Project :     NewportInfinityMeter
##
## $Author :      sblanch$
##
## $Revision :    $
##
## $Date :        $
##
## $HeadUrl :     $
##============================================================================
##            This file is generated by POGO
##    (Program Obviously used to Generate tango Object)
##
##        (c) - Software Engineering Group - ESRF
##############################################################################

"""Device server to show the INFinity meter Strain gage from Newport, in a tango system."""

__all__ = ["NewportInfinityMeter", "NewportInfinityMeterClass", "main"]

__docformat__ = 'restructuredtext'

import PyTango
import sys
# Add additional import
#----- PROTECTED REGION ID(NewportInfinityMeter.additionnal_import) ENABLED START -----#
from types import StringType #used for Exec()
import pprint #used for Exec()
from infs import InfinityMeter
import time
import functools
import traceback
from taurus import Logger

def AttrExc(function):
    '''Decorates commands so that the exception is logged and also raised.
    '''
    #TODO: who has self._trace?
    def nestedMethod(self, attr, *args, **kwargs):
        inst = self #< for pychecker
        try:
            return function(inst, attr, *args, **kwargs)
        except Exception, exc:
            traceback.print_exc(exc)
            #self._trace = traceback.format_exc(exc)
            raise
    functools.update_wrapper(nestedMethod,function)
    return nestedMethod

#----- PROTECTED REGION END -----#	//	NewportInfinityMeter.additionnal_import

##############################################################################
## Device States Description
##
## INIT : 
## ON : 
## OFF : 
##############################################################################

class NewportInfinityMeter (PyTango.Device_4Impl):

#--------- Add you global variables here --------------------------
#----- PROTECTED REGION ID(NewportInfinityMeter.global_variables) ENABLED START -----#
    #####
    #---- #state segment
    def change_state(self,newstate):
        self.debug_stream("In change_state(%s)"%(str(newstate)))
        if newstate != self.get_state():
            self.set_state(newstate)
            self.push_change_event('State',newstate)
    #---- done state segment
    
    #####
    #---- #dynattrs segment
    def addDynAttribute(self,attrName):
        try:
            attr = PyTango.Attr(attrName,PyTango.DevDouble,PyTango.READ)
            readmethod = AttrExc(getattr(self,'read_attr'))
            aprop = PyTango.UserDefaultAttrProp()
            aprop.set_format("%6.3f")
            attr.set_default_properties(aprop)
            self.add_attribute(attr,r_meth=readmethod)
        except Exception,e:
            self.error_stream("The dynamic attribute %s cannot be created "\
                              "due to: %s"%(name,e))
    
    @AttrExc
    def read_attr(self, attr):
        attrName = attr.get_name()
        self.debug_stream("read_attr for %s"%(attrName))
        value = self._infs._sendAndReceive(self._infs.commands[attrName])
        #TODO: introduce periodic readings (to emit events) and set value here 
        #from the cached value.
        #TODO: last todo may have problems if the period is too long. If the 
        #requesting is not stressed it may introduce a new real reading and 
        #push event.
        attr.set_value_date_quality(value,time.time(),
                                    PyTango.AttrQuality.ATTR_VALID)
    #---- done dynattrs segment
            
#----- PROTECTED REGION END -----#	//	NewportInfinityMeter.global_variables
#------------------------------------------------------------------
#    Device constructor
#------------------------------------------------------------------
    def __init__(self,cl, name):
        PyTango.Device_4Impl.__init__(self,cl,name)
        self.debug_stream("In " + self.get_name() + ".__init__()")
        NewportInfinityMeter.init_device(self)

#------------------------------------------------------------------
#    Device destructor
#------------------------------------------------------------------
    def delete_device(self):
        self.debug_stream("In " + self.get_name() + ".delete_device()")
        #----- PROTECTED REGION ID(NewportInfinityMeter.delete_device) ENABLED START -----#
        if self.get_state() == PyTango.DevState.ON:
            self.Close()
        #----- PROTECTED REGION END -----#	//	NewportInfinityMeter.delete_device

#------------------------------------------------------------------
#    Device initialization
#------------------------------------------------------------------
    def init_device(self):
        self.debug_stream("In " + self.get_name() + ".init_device()")
        self.get_device_properties(self.get_device_class())
        #----- PROTECTED REGION ID(NewportInfinityMeter.init_device) ENABLED START -----#
        try:
            self.set_change_event('State',True,False)
            self.set_change_event('Status',True,False)
            self.change_state(PyTango.DevState.INIT)
            # for the Exec command
            self._locals = { 'self' : self }
            self._globals = globals()
            
            self.change_state(PyTango.DevState.OFF)
            # prepare the requestor object
            self.debug_stream("Channel for serial line communications: %s"
                              %(self.Serial))
            self.debug_stream("Instrument addres in the serial line: %s"
                              %(self.Address))
            self._infs = InfinityMeter(self.Serial,self.Address,logLevel=Logger.Debug)
            self.Open()
            # prepare the dynamic attributes for the requested measures
            self.debug_stream("Preparing the measures: %s"%(self.Measures))
            for measure in self.Measures:
                self.addDynAttribute(measure)
        except Exception,e:
            self.error_stream("Device cannot be initialised!")
            traceback.print_exc()
            self.change_state(PyTango.DevState.FAULT)
        #----- PROTECTED REGION END -----#	//	NewportInfinityMeter.init_device

#------------------------------------------------------------------
#    Always excuted hook method
#------------------------------------------------------------------
    def always_executed_hook(self):
        self.debug_stream("In " + self.get_name() + ".always_excuted_hook()")
        #----- PROTECTED REGION ID(NewportInfinityMeter.always_executed_hook) ENABLED START -----#
        
        #----- PROTECTED REGION END -----#	//	NewportInfinityMeter.always_executed_hook

#==================================================================
#
#    NewportInfinityMeter read/write attribute methods
#
#==================================================================




#------------------------------------------------------------------
#    Read Attribute Hardware
#------------------------------------------------------------------
    def read_attr_hardware(self, data):
        self.debug_stream("In " + self.get_name() + ".read_attr_hardware()")
        #----- PROTECTED REGION ID(NewportInfinityMeter.read_attr_hardware) ENABLED START -----#
        
        #----- PROTECTED REGION END -----#	//	NewportInfinityMeter.read_attr_hardware


#==================================================================
#
#    NewportInfinityMeter command methods
#
#==================================================================

#------------------------------------------------------------------
#    Exec command:
#------------------------------------------------------------------
    def Exec(self, argin):
        """ Expert attribute to execute python code inside the device. Use it extremelly carefully.
        
        :param argin: 
        :type: PyTango.DevString
        :return: 
        :rtype: PyTango.DevString """
        self.debug_stream("In " + self.get_name() +  ".Exec()")
        argout = ''
        #----- PROTECTED REGION ID(NewportInfinityMeter.Exec) ENABLED START -----#
        cmd = argin
        L = self._locals
        G = self._globals
        try:
            try:
                # interpretation as expression
                result = eval(cmd, G, L)
            except SyntaxError:
                # interpretation as statement
                exec cmd in G, L
                result = L.get("y")

        except Exception, exc:
            # handles errors on both eval and exec level
            result = exc

        if type(result)==StringType:
            return result
        elif isinstance(result, BaseException):
            return "%s!\n%s" % (result.__class__.__name__, str(result))
        else:
            return pprint.pformat(result)
        #----- PROTECTED REGION END -----#	//	NewportInfinityMeter.Exec
        return argout
        
#------------------------------------------------------------------
#    Open command:
#------------------------------------------------------------------
    def Open(self):
        """ Open the communications with the lower level serial line.
        
        :param : 
        :type: PyTango.DevVoid
        :return: 
        :rtype: PyTango.DevVoid """
        self.debug_stream("In " + self.get_name() +  ".Open()")
        #----- PROTECTED REGION ID(NewportInfinityMeter.Open) ENABLED START -----#
        self._infs.open()
        self.change_state(PyTango.DevState.ON)
        #----- PROTECTED REGION END -----#	//	NewportInfinityMeter.Open
        
#------------------------------------------------------------------
#    Close command:
#------------------------------------------------------------------
    def Close(self):
        """ Close the communications with the lower level serial line.
        
        :param : 
        :type: PyTango.DevVoid
        :return: 
        :rtype: PyTango.DevVoid """
        self.debug_stream("In " + self.get_name() +  ".Close()")
        #----- PROTECTED REGION ID(NewportInfinityMeter.Close) ENABLED START -----#
        self._infs.close()
        self.change_state(PyTango.DevState.OFF)
        #----- PROTECTED REGION END -----#	//	NewportInfinityMeter.Close
        

#==================================================================
#
#    NewportInfinityMeterClass class definition
#
#==================================================================
class NewportInfinityMeterClass(PyTango.DeviceClass):

    #    Class Properties
    class_property_list = {
        }


    #    Device Properties
    device_property_list = {
        'Serial':
            [PyTango.DevString,
            "Device name for serial line, or a local tty file path",
            [] ],
        'Address':
            [PyTango.DevString,
            "Some of this instruments can be connected in a shared bus like 485, having each an identifier.",
            [] ],
        'Measures':
            [PyTango.DevVarStringArray,
            "List of elements to read from the instrument: UnfilteredValue, FilteredValue, PeakValue, ValleyValue.",
            [] ],
        }


    #    Command definitions
    cmd_list = {
        'Exec':
            [[PyTango.DevString, "none"],
            [PyTango.DevString, "none"],
            {
                'Display level': PyTango.DispLevel.EXPERT,
            } ],
        'Open':
            [[PyTango.DevVoid, "none"],
            [PyTango.DevVoid, "none"]],
        'Close':
            [[PyTango.DevVoid, "none"],
            [PyTango.DevVoid, "none"]],
        }


    #    Attribute definitions
    attr_list = {
        }


#------------------------------------------------------------------
#    NewportInfinityMeterClass Constructor
#------------------------------------------------------------------
    def __init__(self, name):
        PyTango.DeviceClass.__init__(self, name)
        self.set_type(name);
        print "In NewportInfinityMeter Class  constructor"

#==================================================================
#
#    NewportInfinityMeter class main method
#
#==================================================================
def main():
    try:
        py = PyTango.Util(sys.argv)
        py.add_class(NewportInfinityMeterClass,NewportInfinityMeter,'NewportInfinityMeter')

        U = PyTango.Util.instance()
        U.server_init()
        U.server_run()

    except PyTango.DevFailed,e:
        print '-------> Received a DevFailed exception:',e
    except Exception,e:
        print '-------> An unforeseen exception occured....',e

if __name__ == '__main__':
    main()
