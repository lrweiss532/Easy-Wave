from waveforms import Core_Pulse, Core_Waveform, Waveform
import numpy as np

# Reminder:
#   Besides the kwargs explicitly passed by the users, the kwargs will always contain 'rate' and for Core_Pulse 'ch'

class Empty(Core_Waveform):
    def build(self, ts, **kwargs):
        return Waveform()

class Zero(Core_Pulse):
    def build(self, ts, **kwargs):
        dtype = bool if kwargs['ch'].value[1] > 0 else float
        return np.zeros(len(ts), dtype=dtype)

class Rect(Core_Pulse):
    def build(self, ts, amplitude=1, **kwargs):
        if kwargs['ch'].value[1] > 0:
            return np.ones(len(ts), dtype=bool)
        else:
            return np.ones(len(ts), dtype=float)*amplitude
