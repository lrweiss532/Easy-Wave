import numpy as np
from enum import Enum
from io import BytesIO
import ftplib
from collections import OrderedDict

import wave_sim as sim

DEBUG = False

# -------------------------------------------------------------------------------------------------------
#  The Waveform, AND_Waveform, Core_Pulses and Packaged_Waveform class should be hardware indepedant 
# -------------------------------------------------------------------------------------------------------

class ANDOverlapError(Exception):pass
class ANDLengthError(Exception):pass
class TimeStepError(Exception):pass
class PulseLengthError(Exception):pass

#For us close enough means within one time step (100ps < 1/1.2e9 should be sufficient)
def is_close(a,b, tol=0.1e-9):
    return abs(a-b) < tol

def to_integer(a, error=PulseLengthError()):
    int_a = int(np.round(a))
    if is_close(a, int_a, tol=1e-5):
        # print(int_a)
        return int_a
    else:
        raise error


class Waveform(object):
    def __init__(self, wave_list=[], chs=set()):
        self.wave_list = wave_list
        self.chs = set().union(*[wave.chs for wave in wave_list])
        self.t = sum(wave.t for wave in wave_list)
        self.repr_str = ('(' + ' + '.join(['{}']*len(wave_list)) + ')').format(*[str(wave) for wave in wave_list])

        self.PULSE_TYPE = None

    def has_ch(self, ch):
    #This can be used for specific outputs using the enum or for general channels (1,2,3,4) 
        if type(ch) == int:
            return any(c.value[0]==ch for c in self.chs)
        else:
            return ch in self.chs

    def __str__(self):
        return self.repr_str
        
    def __len__(self):
        return self.t        

    def __add__(self, other):
        a = [self] if type(self)==AND_Waveform else self.wave_list
        b = [other] if type(other)==AND_Waveform else other.wave_list
        return Waveform(wave_list = a + b)

    def __and__(self, other):
        a = self.wave_list if type(self)==AND_Waveform else [self]
        b = other.wave_list if type(other)==AND_Waveform else [other]
        return AND_Waveform(wave_list = a + b)

    def get_ts(self, rate):
        wfm_len = self.t*rate
        wfm_len = to_integer(wfm_len, error=PulseLengthError("Waveform has non-integer length ({}) with respect to rate ({})\n\tWaveform:{}".format(wfm_len, rate, str(self))))
        return np.linspace(0, self.t, wfm_len, endpoint=False)
    
    def generate(self, rate, ch):
        ts = self.get_ts(rate)
        return ts, self.generator(ts, rate, ch)

    def generator(self,ts,rate,ch):
        if not ch in self.chs:
            if DEBUG: print("WARNING:{} is returning zeros".format(str(self)))
            dtype = get_dtype(ch)
            return np.zeros(len(ts), dtype=dtype)
        ti = 0
        gen_list = list()
        for wave in self.wave_list:
            ti_next = ti + (wave.t*rate)
            ti_next = to_integer(ti_next, 
                        error=TimeStepError("Length of waveform is not an integer multiple of the time step\n\tRate: {} (dt = {})\n\tWaveform: {}\n\tWaveform length:{}".format(rate, 1/rate, str(wave),wave.t))
                        )
            gen_list.append(wave.generator(ts[ti:ti_next], rate, ch))
        return np.concatenate(gen_list)


class AND_Waveform(Waveform):
    def __init__(self, wave_list=[]):
        self.wave_list = wave_list
        self.chs = set().union(*[wave.chs for wave in wave_list])
        self.repr_str = ('(' + '&'.join(['{}']*len(wave_list)) + ')').format(*[str(wave) for wave in wave_list])
        if len(wave_list) == 0:
            raise Exception("Trying to create an empty AND_Waveform.  Not allowed.  Use the base Waveform class")
        self.t = wave_list[0].t
        
        #Validate the waveform
        temp = self.chs.copy()
        for wave in wave_list:
            if not wave.chs <= temp:
                raise ANDOverlapError("Cannot perform a AND operation because channels overlap\n\tWaveform : {}".format(self.repr_str))
            temp -= wave.chs

            if not is_close(wave.t, self.t):
                raise ANDLengthError("Cannot perform a AND operation because waveforms are different lenght\n\tWaveform A: {}\n\tWaveform B:{}".format(self.t, wave.t))
        
    def generator(self,ts,rate,ch):
        for wave in self.wave_list:
            if ch in wave.chs:
                return wave.generator(ts, rate, ch)
        if DEBUG: print("WARNING:{} is returning zeros".format(str(self)))
        dtype = get_dtype(ch)
        return np.zeros(len(ts), dtype=dtype)


class Core_Pulse(Waveform):
    #This is a single channel pulse
    def __init__(self, t, ch, *args, **kwargs):
        self.wave_list = [self]
        self.chs = set([ch])
        self.t = t
        self.args = args
        self.kwargs = kwargs

    def __str__(self):
        return self.__class__.__name__

    def generator(self, ts, rate, ch):
        dtype = get_dtype(ch)
        if not ch in self.chs:
            if DEBUG: print("Warning: Asked for a wrong channel ({}) in Core_Pulse {}".format(ch, str(self)))# @DEBUG
            return np.zeros(len(ts), dtype=dtype)

        # Build the array
        arr = self.build(ts, *self.args, rate=rate, ch=ch, **self.kwargs)

        # Validate the results
        if not len(arr) == len(ts):
            raise PulseLengthError("Pulse build function did not return the correct lenght\n\tPulse: {}\n\tlen(ts)={}\n\tlen(arr)={}".format(str(self),len(ts),len(arr)))
        if arr.dtype != dtype:
            arr = arr.astype(dtype)

        return arr

    def build(self, ts, *args, **kwargs):
        """
        This is the function the user will implement to return a numpy array.
        By default **kwargs will always contain the rate and the ch, which the user can make use of (or not)
        """
        pass


def Packaged_Waveform(func, sim_func=None):
    def wrapper(*args, **kwargs):
        w = func(*args, **kwargs)
        w.args = args
        w.kwargs = kwargs
        w.repr_str = func.__name__
        return w
    return wrapper


# -------------------------------------------------------------------------------------------------------
# This will transform the waveforms into AWG lines and then write them to file.  This part is hardware depedent.  (Here written for the Tektronix AWG 5014C)
# -------------------------------------------------------------------------------------------------------

class Channel(Enum):
    ch1_a = (1,0);ch1_m1 = (1,1);ch1_m2 = (1,2);
    ch2_a = (2,0);ch2_m1 = (2,1);ch2_m2 = (2,2);
    ch3_a = (3,0);ch3_m1 = (3,1);ch3_m2 = (3,2);
    ch4_a = (4,0);ch4_m1 = (4,1);ch4_m2 = (4,2);

CHANNEL_GROUPS = OrderedDict([(i,[Channel['ch{}_{}'.format(i,ch)] for ch in ['a', 'm1', 'm2']]) for i in range(1,5)])
DEFAULTS_LIMITS = [(-0.5, 0.5),(0.0, 2.7),(0.0, 2.7)]

def get_dtype(ch):
    return bool if ch.value[1] > 0 else float

try:
    from lantz.drivers.tektronix.awg5014c_tools import AWG_File_Writer
    import lantz.drivers.tektronix.awg5014c_constants as cst
except:
    print("Warning: You do not have lantz install with the proper instrument drivers.  You will not be able to generate .awg files for the AWG5014C, but you can still use the generator code")

class AWG_Writer(object):
    def __init__(self):
        self.lines = list()

    def add_line(self, waveform, name, repeat=0, goto=0, shifts=None, jump_target=0, wait_for_trigger=False, use_sub_seq=False, sub_seq_name=''):
        self.lines.append({'name':name, 'waveform':waveform,'shifts':shifts,
                        'params':{'repeat_count':repeat, 'goto_target':goto, 'jump_target':jump_target,
                                    'wait_for_trigger':wait_for_trigger, 'use_sub_seq':use_sub_seq, 'sub_seq_name':sub_seq_name}})

    def generate(self, rate, limits={}):
        file_writer = AWG_File_Writer()
        zero_lines = list()
        for i, line in enumerate(self.lines):
            line_no = i + 1

            #Generate the 4 waveform in the line
            wfm_names = list()
            for group, chs in CHANNEL_GROUPS.items():
                wfm_len = line['waveform'].t*rate
                wfm_len = to_integer(wfm_len, error=PulseLengthError("Waveform <{}> channel group <{}> has non-integer length ({}) with respect to rate ({})".format(line['name'],group, wfm_len, rate)))
                if any([line['waveform'].has_ch(ch) for ch in chs]):
                    name = line['name']+' ch'+str(group)
                    ts = np.linspace(0, line['waveform'].t, wfm_len, endpoint=False)
                    file_writer.add_waveform(name, *[line['waveform'].generator(ts, rate, ch) for ch in chs])# @TODO Add shift
                else:
                    name = 'zeros {}'.format(wfm_len)
                    if not wfm_len in zero_lines:
                        file_writer.add_waveform(name, np.zeros(wfm_len, dtype=float), np.zeros(wfm_len, dtype=bool), np.zeros(wfm_len, dtype=bool))
                        zero_lines.append(wfm_len)
                wfm_names.append(name)
            
            #Add the sequence
            file_writer.add_sequence_line(wfm = wfm_names, **line['params'])

            #Add limits
            for ch in Channel:
                lo, hi = limits[ch] if ch in limits else DEFAULTS_LIMITS[ch.value[1]]
                if ch.value[1] == 0:
                    records = [
                        ('ANALOG_METHOD_'+str(ch.value[0]), cst.EAnalogInputMethod.AnalogInputMethod_IMHighLow, 3),
                        ('ANALOG_LOW_'+str(ch.value[0]), lo, 3),
                        ('ANALOG_HIGH_'+str(ch.value[0]), hi, 3),
                    ]
                else:
                    records = [
                        ('MARKER{1}_METHOD_{0}'.format(*ch.value), cst.EMarkerInputMethod.MarkerInputMethod_IMHighLow, 3),
                        ('MARKER{1}_LOW_{0}'.format(*ch.value), lo, 3),
                        ('MARKER{1}_HIGH_{0}'.format(*ch.value), hi, 3)
                    ]
                for r in records:
                    file_writer.add_record(*r)

            #Add a few more records
            file_writer.add_record('SAMPLING_RATE', rate, 2)
            file_writer.add_record('RUN_MODE', cst.ERunMode.RunMode_SEQUENCE, 2)

            sequence_file = BytesIO()
            sequence_file.write(file_writer.get_bytes())
            sequence_file.seek(0)
            return sequence_file

    def generate_and_upload(self, address, remote_filename, rate=1e9, limits={}):
        sequence_file = self.generate(rate=rate, limits=limits)
        print('file generated')
        ftp = ftplib.FTP(address)
        print('opening ftp at {}'.format(address))
        ftp.login()
        ftp.storbinary('STOR {}'.format(remote_filename), sequence_file, blocksize=1024)
        print('uploaded')
        ftp.quit()
        return      