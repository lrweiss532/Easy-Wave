from wave_library import *
from enum import Enum
import numpy as np
import qutip

#------------------------------------------------------------------------
#                       Types of Pulses
#------------------------------------------------------------------------

class Pulse_Type(object):

    class _Base_Type(object):
        pass
        # def __mul__(self, other):
        #     if type(self) == Pulse_Type.Constant:
        #         if type(other) == Pulse_Type.Constant:
        #             return Pulse_Type.Constant(self.val*self.val)
        #         elif type(other) == Pulse_Type.Periodic:
        #             return Pulse_Type.Periodic(period=other.T)
        #         elif type(other) == Pulse_Type.IQ_Freq_Shifting:
        #             return Pulse_Type.IQ_Freq_Shifting(period = other.T)
        #         else:
        #             return Pulse_Type.Arbitrary()
        #     elif type(self) == Pulse_Type.IQ_Freq_Shifting:
        #         if type(other) == Pulse_Type.Constant:
        #             return Pulse_Type.IQ_Freq_Shifting(period = self.T)
        #         elif type(other) == Pulse_Type.Periodic:
        #             return Pulse_Type.Periodic(period=1/other.T)
        #         elif type(other) == Pulse_Type.IQ_Freq_Shifting:
        #             return Pulse_Type.IQ_Freq_Shifting(period = other.T)
        #         else:
        #             return Pulse_Type.Arbitrary()
        #     elif type(self) == Pulse_Type.Periodic:
        #         if type(other) == Pulse_Type.Constant:
        #             return Pulse_Type.Periodic(period = self.T)
        #         elif type(other) == Pulse_Type.Periodic and self.T == other.T:#Could do something here with less common multiple multiple, but let's keep it simple
        #             return Pulse_Type.Periodic(period = self.T)
        #         else:
        #             return Pulse_Type.Arbitrary()
        #     else:
        #         return Pulse_Type.Arbitrary()

    class Periodic(_Base_Type):
        def __init__(self, period):
            self.T = period

    class IQ_Freq_Shifting(Periodic):
        def __init__(self, shift_f):
            self.shift_f = shift_f

    class Arbitrary(_Base_Type):
        pass

    class Constant(_Base_Type):
        def __init__(self, val):
            self.val = val

#------------------------------------------------------------------------
#                       Types of channels
#------------------------------------------------------------------------

class Sim_Ch_Types(object):
    class B_ch(object):
        def __init__(self, B_vector):
            self.B_vector = np.array(B_vector)
        def Bi_t(self, i, ts):
            if self.B_vector[i]:
                return self.B_t(ts)*self.B_vector[i]
            else:
                return 0

    class SG_I(B_ch):
        def __init__(self, f, B_vector=[1,0,0]):
            self.f = f
            super().__init__(B_vector)
        
        def B_t(self, ts):
            return np.sin(self.f*2*np.pi*ts)

    class SG_Q(B_ch):
        def __init__(self, f, B_vector=[1,0,0]):
            self.f = f
            super().__init__(B_vector)
        def B_t(self, ts):
            return np.cos(self.f*2*np.pi*ts)

    class Direct(B_ch):
        def __init__(self, B_vector=[1,0,0]):
            super().__init__(B_vector)
        def B_t(self, ts):
            return 1


class B_field(object):
    def __init__(self):
        self.is_constant = False
        self.T = None
    def Bt(t):
        raise NotImplementedError()

class SG_IQ(B_field):
    def __init__(self, f, ch_i, ch_q, wave, experiment_rate):
        self.f = f
        self.w = 2*np.pi*f
        self.ch_i = ch_i
        self.ch_q = ch_q
        self.wave = wave
        self.exp_rate = experiment_rate

        self.wave_i_arr = self.wave.generate(experiment_rate, ch_i)
        self.wave_q_arr = self.wave.generate(experiment_rate, ch_q)

        self.is_constant = False
        #Figure out if periodic
        self.T = None
        if type(self.wave.PULSE_TYPE) == Pulse_Type.Constant:
            self.T = 1/self.f
        elif type(self.wave.PULSE_TYPE) == IQ_Freq_Shifting:
            self.T = 1/(self.f+self.wave.PULSE_TYPE.shift_f)
            
    def Bt(t):
        ans  = np.sin(self.w*t)*self.wave_i_arr[int(t*self.exp_rate)]
        ans += np.cos(self.w*t)*self.wave_q_arr[int(t*self.exp_rate)]
        return ans
    
#------------------------------------------------------------------------
#                       Simple Simulator
#------------------------------------------------------------------------
class Wave_Sim():
    def __init__(self, wave, B_chs={}, B_static=[0,0,0]):
        """
        wave : Waveform object
        B_chs: dict() matching a ch to an instance of a Sim_Ch_Type{wave.Channel:Sim_Ch_Type}
        B_static: Static B field
        """
        self.wave = wave
        self.B_chs = B_chs
        self.B_static = B_static

    def generate_B_t(self, sim_rate, ts=None, experiment_rate=None):
        experiment_rate = sim_rate if experiment_rate is None else experiment_rate

        wave_ts = self.wave.get_ts(experiment_rate)
        if ts is None:
            ts = wave_ts
        else:
            if max(ts) > max(wave_ts) or min(ts)<min(wave_ts):
                raise Exception("ts is out of the wave timeframe!")
        def wave_B_t(arr):
            return lambda t: arr[int(t*experiment_rate)]


        # Construct Bi_t containing 3 functions (x,y,z) taking a time t and returning a B-field
        Bi_t = [lambda ts: 0]*3
        def new_Bi_t(old_Bi_t, ch_type, w_B_t, i):
            print(ch_type.Bi_t(i,0), w_B_t(0))
            return lambda t: old_Bi_t(t) + ch_type.Bi_t(i, t)*w_B_t(t)

        for ch, ch_type in self.B_chs.items():
            arr = self.wave.generator(ts, experiment_rate, ch)
            w_B_t = wave_B_t(arr)
            for i in range(3):
                if ch_type.B_vector[i]:
                    Bi_t[i] = new_Bi_t(Bi_t[i], ch_type, w_B_t, i)

        return Bi_t

        
         
        