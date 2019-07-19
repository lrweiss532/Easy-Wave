import numpy as np
from enum import Enum

from lantz.drivers.tektronix.awg5014c_tools import AWG_File_Writer
import lantz.drivers.tektronix.awg5014c_constants as cst

class ANDOverlapError(Exception):pass
class ANDLengthError(Exception):pass
class TimeStepError(Exception):pass
class PulseLengthError(Exception):pass

def is_close(a,b):
    return abs(a-b) < 0.1e-9#For us close enough means within one time step (100ps < 1/1.2e9 should be sufficient)

def to_integer(a):
    if is_close(a, int(a)):
        return int(a)
    else:
        raise PulseLengthError()

class Channels(Enum):
    ch1_a = (1,0);ch1_m1 = (1,1);ch1_m2 = (1,2);
    ch2_a = (2,0);ch2_m1 = (2,1);ch2_m2 = (2,2);
    ch3_a = (3,0);ch3_m1 = (3,1);ch3_m2 = (3,2);
    ch4_a = (4,0);ch4_m1 = (4,1);ch4_m2 = (4,2);

class AND(list):
    def __init__(self, a, b):
        super().__init__([a,b])

class Waveform(object):
    def __init__(self, wave_list=[], chs=set(), repr_str=''):
        self.wave_list = wave_list
        self.chs = chs
        self.t = sum(wave.t for wave in wave_list)

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
        return Waveform(wave_list=self.wave_list + other.wave_list, 
                        chs=self.chs | other.chs,
                        repr_str = self.repr_str + ' + ' + other.repr_str)

    def __and__(self, other):
        if self.chs.isdisjoint(other.chs):
            raise ANDOverlapError("Cannot perform a AND operation because channels overlap\n\tWaveform A: {}\n\tWaveform B:{}".format(str(self), str(other)))
        if is_close(self.t, other.t):
            raise ANDLengthError("Cannot perform a AND operation because waveforms are different lenght\n\tWaveform A: {}\n\tWaveform B:{}".format(self.t, other.t))
        return AND(self, other)

    def generator(self,ts,rate,ch):
        if not ch in self.chs:
            dtype = bool if ch.value[1] > 0 else float
            return np.zeros(len(ts), dtype=dtype)
        ti = 0
        gen_list = list()
        for wave in self.wave_list:
            if type(wave)==AND:
                if ch in wave[0].chs:
                    gen = wave[0].generator
                else:
                    gen = wave[1].generator
            else:
                gen = wave.generator
            ti_next = ti + (wave.t*rate)
            if not is_close(ti_next,int(ti_next)):
                raise TimeStepError("Length of waveform is not an integer multiple of the time step\n\tRate: {} (dt = {})\n\tWaveform: {}\n\tWaveform length:{}".format(rate, 1/rate, str(wave),wave.t))
            ti_next = int(ti_next)
            gen_list.append(gen(ts[ti:ti_next], rate, ch))
        return np.concatenate(gen_list)

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
        dtype = bool if ch.value[1] > 0 else float
        if not ch in self.chs:
            print("Warning: Asked for a wrong channel in Core_Pulse {}".format(str(self)))# @DEBUG
            return np.zeros(len(ts), dtype=dtype)

        # Build the array
        arr = self.build(ts, *args, rate=rate, ch=ch, **kwargs))

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

class Core_Waveform(Waveform):
    #This is a multi-channel pulse
    def __new__(self, t, *args, **kwargs):
        return self.build(t, *args, **kwargs)

    def build(self, ts, *args, **kwargs):
        """
        This is the function the user will implement to return a Waveform object.
        By default **kwargs will always contain the rate and the ch, which the user can make use of (or not)
        """
        pass

# -------------------------------------------------------------------------------------------------------
# This will transform the waveforms into AWG lines and then write them to file
# -------------------------------------------------------------------------------------------------------



class AWG_Writer(object):
    def __init__(self, filename):
        f = AWG_File_Writer()
        self.lines = []

    def add_line(self, waveform, name, repeat=None, goto=None, shifts=None, jump_target=None, wait_for_trigger=False, use_sub_seq=False, sub_seq_name='',):
        self.lines.append({'name':name, 'waveform':waveform,'shifts':shifts
                           'params':{'repeat':repeat, 'goto':goto, 'jump_target':jump_target,'wait_for_trigger':wait_for_trigger, 'use_sub_seq':use_sub_seq, 'sub_seq_name':sub_seq_name}})

    def generate_and_upload(self, address, remote_filename, rate):
        zero_lines = dict()
        for i, line in enumerate(self.lines):
            line_no = i + 1

            wfm_names = list()
            for ch in [1,2,3,4]:
                wfm_len = line['waveform'].t*rate
                is_close(wfm_len)
                if line['waveform'].has_ch(ch):
                    



class AWG_Line(object):
    def __init__(self, waveform, name, repeat=None, goto=None, shifts=None, jump_target=None):
        