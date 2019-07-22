from wave import Core_Pulse, Packaged_Waveform, Waveform
import numpy as np
import wave_sim as sim

"""
Reminder for building waveforms:
    1) Besides the kwargs explicitly passed by the users, the kwargs for Core_Pulse will always contain 'rate' and 'ch'
    2) You can always find out the pulse duration using self.t
    3) Core_Pulse should implement the build function to return a np.array
    4) Packaged_Waveform decorates functions which return a Waveform object

Reminder for simulation:
    1) If you can, include a 'sim' function (with the same signature as the build function) which return a sim.Pulse_Type.
       If no 'sim' function exist the Pulse_Type is assumed to be 'Arbitrary'
"""

class Empty(Waveform):
    pass

#-----------------------------------------------------------------------------------------
#                       Core Pulses
#-----------------------------------------------------------------------------------------

class Zero(Core_Pulse):
    def build(self, ts, **kwargs):
        self.PULSE_TYPE = sim.Pulse_Type.Constant(0) # For simulation purpose
        dtype = bool if kwargs['ch'].value[1] > 0 else float
        return np.zeros(len(ts), dtype=dtype)

class Rect(Core_Pulse):
    def build(self, ts, amplitude=1, **kwargs):
        self.PULSE_TYPE = sim.Pulse_Type.Constant(amplitude) # For simulation purpose
        if kwargs['ch'].value[1] > 0:
            return np.ones(len(ts), dtype=bool)
        else:
            return np.ones(len(ts), dtype=float)*amplitude

class Cos(Core_Pulse):
    def build(self, ts, f, A=1, phi=0, **kwargs):
        self.PULSE_TYPE = sim.Pulse_Type.Periodic(1/f) # For simulation purpose
        return A*np.cos((ts*f+phi/360)*2*np.pi)

class Sin(Core_Pulse):
    def build(self, ts, f, A=1, phi=0, **kwargs):
        self.PULSE_TYPE = sim.Pulse_Type.Periodic(1/f) # For simulation purpose
        return A*np.sin((ts*f+phi/360)*2*np.pi)



#-----------------------------------------------------------------------------------------
#                       Packaged Waveform
#-----------------------------------------------------------------------------------------


@Packaged_Waveform
def IQ_MW_Pulse(t, i_ch, q_ch, g_ch, phase=0, freq_shift=0, A=1, mw_buffer=0, **kwargs):
    gate =  Rect(t=2*mw_buffer+t, ch=g_ch)
    buf = Zero(t=mw_buffer, ch=i_ch)
    p = Cos(t=t, ch=i_ch, f=freq_shift, A=A, phi=phase) & Sin(t=t, ch=q_ch, f=freq_shift, A=A, phi=phase)
    p.PULSE_TYPE = sim.Pulse_Type.IQ_Freq_Shifting(freq_shift) # For simulation purpose
    return gate & (buf+p+buf)
