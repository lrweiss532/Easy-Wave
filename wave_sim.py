#  WARNING: This is Experimental and needs more work to be a fully functional usefull tool


import wave_library as wave_lib
from easy_wave import *
from enum import Enum
import numpy as np
import qutip
import pyqtgraph as pg
import time

#------------------------------------------------------------------------
#                       Types of Pulses
#------------------------------------------------------------------------

class Pulse_Type(object):

    class Periodic(object):
        def __init__(self, period):
            self.T = period

    class IQ_Freq_Shifting(Periodic):
        def __init__(self, shift_f):
            self.shift_f = shift_f

    class Arbitrary(object):
        pass

    class Constant(object):
        def __init__(self, val):
            self.val = val

#------------------------------------------------------------------------
#                       Types of channels
#------------------------------------------------------------------------

class Sim_Chs(object):

    class _Base_Class(object):
        def __init__(self):
            self.signal_labels = set([])
        def get_signals(self, wave, experiment_rate):
            raise NotImplementedError

    class SG_IQ(object):
        def __init__(self, f, i_ch, q_ch, B_vector=[1,0,0]):
            self.chs = set([i_ch, q_ch])
            self.f, self.i_ch, self.q_ch = f, i_ch, q_ch
            self.B_vector = {axis:B_vector[i] for i,axis in enumerate(['x','y','z'])}
            self.signal_labels = set([])

        def get_signals(self, wave, experiment_rate):
            out = []
            for axis in ['x', 'y', 'z']:
                if self.B_vector[axis]:
                    out.append(SG_IQ(self.f, self.i_ch, self.q_ch, wave, experiment_rate, axis=axis, mult_factor=self.B_vector[axis]))
            return out

    class Direct(object):
        def __init__(self, ch, B_vector=[1,0,0]):
            self.chs = set([ch])
            self.ch = ch
            self.B_vector = {axis:B_vector[i] for i,axis in enumerate(['x','y','z'])}

        def get_signals(self, wave, experiment_rate):
            out = []
            for axis in ['x', 'y', 'z']:
                if self.B_vector[axis]:
                    out.append(Direct(self.ch, wave, experiment_rate, axis=axis, mult_factor=self.B_vector[axis]))
            return out
            


#------------------------------------------------------------------------
#                       Types of Interaction signals
#------------------------------------------------------------------------
class Interaction_Signal(object):
    def __init__(self):
        self.is_constant = False
        self.T = None
    def get(self, t):
        raise NotImplementedError()
    def get_interaction_label(self):
        raise NotImplementedError()


class B_field(Interaction_Signal):
    def __init__(self, axis='x', mult_factor=1):
        super().__init__()
        self.axis = axis
        # self.is_constant = False
        # self.T = None
    def get_interaction_label(self):
        return 'B'+self.axis


class Static(B_field):
    def __init__(self, val, axis='x', mult_factor=1):
        super().__init__(axis=axis)
        self.is_constant = True
        self.val = val
        self.mult_factor = mult_factor
    def get(self, t):
        return self.val*self.mult_factor

class SG_IQ(B_field):
    def __init__(self, f, ch_i, ch_q, wave, experiment_rate, axis='x', mult_factor=1):
        super().__init__(axis=axis)

        # self.axis = axis
        self.f = f
        self.w = 2*np.pi*f
        self.ch_i = ch_i
        self.ch_q = ch_q
        self.wave = wave
        self.exp_rate = experiment_rate
        self.mult_factor = mult_factor

        self.exp_ts, self.wave_i_arr = self.wave.generate(experiment_rate, ch_i)
        _          , self.wave_q_arr = self.wave.generate(experiment_rate, ch_q)

        self.exp_ts_limits = [min(self.exp_ts),max(self.exp_ts)]

        # self.is_constant = False
        # self.T = None

        #Figure out if periodic
        if type(self.wave.PULSE_TYPE) == Pulse_Type.Constant:
            self.T = 1/self.f
        elif type(self.wave.PULSE_TYPE) == Pulse_Type.IQ_Freq_Shifting:
            self.T = 1/(self.f+self.wave.PULSE_TYPE.shift_f)
            
    def get(self, t):
        if t<self.exp_ts_limits[0] or t>self.exp_ts_limits[1]:
            return 0
        ans  = np.sin(self.w*t)*self.wave_i_arr[int(t*self.exp_rate)]
        ans += np.cos(self.w*t)*self.wave_q_arr[int(t*self.exp_rate)]
        return ans*self.mult_factor

class Direct(B_field):
    def __init__(self, ch, wave, experiment_rate, axis='x', mult_factor=1):
        super().__init__(axis=axis)
        # self.axis = axis
        self.is_constant = type(wave.PULSE_TYPE) is Pulse_Type.Constant
        self.T = wave.PULSE_TYPE.T if type(wave.PULSE_TYPE) is Pulse_Type.Periodic else None

        self.exp_ts, self.arr = self.wave.generate(experiment_rate, ch)
        self.exp_ts_limits = [min(self.exp_ts),max(self.exp_ts)]
        self.exp_rate = experiment_rate
        self.mult_factor = mult_factor

    def get(self, t):
        if t<self.exp_ts_limits[0] or t>self.exp_ts_limits[1]:
            return 0
        return self.arr[int(t*self.exp_rate)]*self.mult_factor

#------------------------------------------------------------------------
#                       Hamiltonians
#------------------------------------------------------------------------
class Hamiltonian(object):
    def __init__(self):
        self.T = None
        self.labels = None
        self.Hi = dict()
        self.signals = dict()
        
    def is_constant(self):
        return not bool(len(self.signals))

    def has_interaction(self, label):
        return label in self.Hi

    def add_signal(self, signal):
        label = signal.get_interaction_label()
        if not self.has_interaction(label):
            print("No associate interaction Hamiltonian in self.Hi...  This signal will be ignored")
            return

        if not issubclass(type(signal), Interaction_Signal):
            raise Exception("<signal> must be a subclass of Interaction_Signal")
        
        if signal.is_constant:
            self.H0 += signal.get(0)*self.Hi[label]
        else:
            H_was_constant = self.is_constant()
            H_was_periodic = not self.T is None and not self.is_constant()
            signal_is_periodic = not signal.T is None
            if H_was_constant and signal_is_periodic:
                self.T = signal.T
            elif H_was_periodic and signal.T == self.T: #could do something more fancy with less common multiplier, but let's keep it simple
                self.T = self.T
            else:
                self.T = None #No period anymore
                
            if not label in self.signals:
                self.signals[label] = list()
            self.signals[label].append(signal)

    def get_qutip_descriptor(self, time_offset=0):
        ans = [self.H0]
        for label, signals_list in self.signals.items():
            ans.append([self.Hi[label], lambda t, *args: sum([signal.get(t+time_offset) for signal in signals_list])])
        if len(ans) == 1:
            return ans[0]
        else:
            return ans

    def plot_signal(self, label, ts, plt=None):
        if plt is None:
            plt = pg.plot()
        ys = np.vectorize(lambda t: sum([signal.get(t) for signal in self.signals[label]]))
        plt.plot(ts, ys(ts))
        return plt


class Single_VV0_Spin(Hamiltonian):
    
    def __init__(self, D, gamma_e=2.8e6):
        super().__init__()
        self.T = None
        self.D = D
        self.H0 = (2*np.pi)*D*qutip.jmat(1, 'z')**2
        self.Hi = {'B'+axis:(2*np.pi)*gamma_e*qutip.jmat(1, axis) for axis in ['x', 'y', 'z']}

        self.labels = ['+1', ' 0', '-1']

        
    
#------------------------------------------------------------------------
#                       Simple Simulator
#------------------------------------------------------------------------
class Simple_Sim():
    def __init__(self, H, ts, psi0=qutip.basis(3,1), options=qutip.solver.Options(), force_recompute=False):
        self.H = H
        if H.is_constant() or H.T is None:
            self.output = qutip.sesolve(H.get_qutip_descriptor(time_offset=min(ts)), psi0, ts-min(ts), options=options)
        else:
            #Periodic hamiltonian, use Floquet Formalism
            self.output = qutip.fsesolve(H.get_qutip_descriptor(time_offset=min(ts)), psi0, ts-min(ts), e_ops=[], T=H.T, args={})

    def plot(self, ts, method='abs', plt=None):
        states = np.array([s.full() for s in self.output.states])[:,:,0]
        if method == 'abs':
            states = np.abs(states)**2
        elif method == 'real':
            states = np.real(states)
        elif method == 'imag':
            states = np.imag(states)

        cs = ['b', 'g', 'r', 'c', 'y', 'w','m']
        if plt is None:
            plt = pg.plot()
        if not self.H.labels is None:
            plt.addLegend()
            for i, ys in enumerate(states.T):
                plt.plot(ts, ys, pen=cs[i%len(cs)], name=self.H.labels[i])
        else:
            for i, ys in enumerate(states.T):
                plt.plot(ts, ys, pen=cs[i%len(cs)])
        return plt


#------------------------------------------------------------------------
#                       Smart Simulator
#------------------------------------------------------------------------

# This is not working right now since the phase of the pulses do not match at every pulses...  
# class Smart_Sim():
#     def __init__(self, H_class, H_args=[], sim_chs=[], H_kwargs={}, options=qutip.solver.Options()):
#         self.H_class, self.H_args, self.sim_chs, self.H_kwargs, self.options = H_class, H_args, sim_chs, H_kwargs, options
#         self.propagators = dict()
    
#     def run(self, wave, experimental_rate, sim_rate=None, psi0=qutip.basis(3,1), reuse_propagators=True, verbose=False):
#         sim_rate = experimental_rate if sim_rate is None else sim_rate
#         relevent_chs = set().union(*[sim_ch.chs for sim_ch in self.sim_chs])
#         sim_seq = Sequencer(wave, relevent_chs=relevent_chs)
        
#         psi = psi0
#         self.states = list()
#         self.sims = list()
#         self.ts = np.array([])
#         next_time = 0
        
#         #Build Hamiltonian seq
#         Hs = dict()
#         for sim_chunk in sim_seq.seq:
#             H = self.H_class(*self.H_args, **self.H_kwargs)
#             for sim_ch in self.sim_chs:
#                 #If the sim_ch as some of the same channels as the chunk
#                 if len(sim_ch.chs.intersection(sim_chunk.chs)):
#                     for signal in sim_ch.get_signals(sim_chunk, experiment_rate=experimental_rate):
#                         if H.has_interaction(signal.get_interaction_label()):
#                             H.add_signal(signal)
#             Hs[sim_chunk] = H
            
#         #Reset the propagator dict if necessary
#         if not reuse_propagators:
#             self.propagators = dict()
            
#         # Perform the simulation
#         for sim_chunk in sim_seq.seq:
#             sim_start_time = time.time()
            
#             ts = np.linspace(0, sim_chunk.t, int(sim_chunk.t*sim_rate), endpoint=False)
            
#             # Get the propagator
#             if not sim_chunk in self.propagators:
#                 H = Hs[sim_chunk].get_qutip_descriptor()
#                 U_t = qutip.propagator(H, ts, c_op_list=[], options=self.options)
#                 if reuse_propagators:
#                     self.propagators[sim_chunk] = U_t
#             else:
#                 U_t = self.propagators[sim_chunk]
            
#             # Solve for psi_t 
#             states = U_t*psi
            
#             # Update some variables
#             self.states.extend(states)
#             psi = states[-1]
#             self.ts = np.concatenate([self.ts, ts+next_time])
#             next_time += sim_chunk.t
            
#             if verbose:
#                 print("Simulation of <{}> took {:.4f} s".format(str(sim_chunk), time.time()-sim_start_time))
            
    
#     def plot(self,plt=None):
#         states = np.array([s.full() for s in self.states])[:,:,0]
#         states = np.abs(states)**2

#         cs = ['b', 'g', 'r', 'c', 'y', 'w','m']
#         H = self.H_class(*self.H_args, **self.H_kwargs)
#         if plt is None:
#             plt = pg.plot()
#         if not H.labels is None:
#             plt.addLegend()
#             for i, ys in enumerate(states.T):
#                 plt.plot(self.ts, ys, pen=cs[i%len(cs)], name=H.labels[i])
#         else:
#             for i, ys in enumerate(states.T):
#                 plt.plot(self.ts, ys, pen=cs[i%len(cs)])
#         return plt

# class Sequencer(object):
#     def __init__(self, wave, relevent_chs):
#         self.seq = self.serialize(wave, relevent_chs)
#         self.compress_zeros()
#         self.re_id_zeros()

#     def serialize(self, wave, relevent_chs):
#         if not wave.PULSE_TYPE is None:
#             return [wave]

#         if type(wave) == AND_Waveform:
#             is_relevent = [any([ch in sub_wave.chs for ch in relevent_chs])for sub_wave in wave.wave_list]
#             no_relevent_waves = sum(is_relevent)
#             if no_relevent_waves == 0:
#                 return []
#             elif no_relevent_waves == 1:
#                 relevent_wave = wave.wave_list[is_relevent.index(True)]
#                 return self.serialize(relevent_wave, relevent_chs=relevent_chs)
#             else:
#                 return [wave]

#         elif type(wave) == Waveform:
#             out_list = []
#             is_relevent = [any([ch in sub_wave.chs for ch in relevent_chs])for sub_wave in wave.wave_list]
#             for i, sub_wave in enumerate(wave.wave_list):
#                 if not is_relevent[i]:
#                     out_list.append(wave_lib.Zero(t=sub_wave.t, ch=Channel.no_ch))
#                 else:
#                     out_list.extend(self.serialize(sub_wave, relevent_chs=relevent_chs))
#             return out_list

#         elif issubclass(type(wave), Core_Pulse):
#             print("Warning: Using a Core Pulse with no PULSE_TYPE definition.  Could be inefficient")
#             return [wave]

#         else:
#             raise Exception("Received a {}".format(type(wave)))
        
#     def compress_zeros(self):
#         out = list()
#         zero_t = 0
#         for wave in self.seq:
#             if type(wave) == wave_lib.Zero:
#                 zero_t += wave.t
#             else:
#                 if zero_t:
#                     out.append(wave_lib.Zero(t=zero_t, ch=Channel.no_ch))
#                     zero_t = 0
#                 out.append(wave)
#         if zero_t:
#             out.append(wave_lib.Zero(t=zero_t, ch=Channel.no_ch))
#         self.seq = out

#     def re_id_zeros(self):
#         zeros_dict = {}
#         for i, wave in enumerate(self.seq):
#             if type(wave) is wave_lib.Zero:
#                 if wave.t in zeros_dict:
#                     self.seq[i] = zeros_dict[wave.t]
#                 else:
#                     zeros_dict[wave.t] = wave
                    



            