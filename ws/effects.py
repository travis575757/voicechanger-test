
import numpy as np 
from numpy.lib.stride_tricks import as_strided

# bass class for effects
class EffectModule:

    # buffer size and config used by all intances
    def __init__(self,buffer_size,config):
        self._buffer_size = buffer_size
        self._config = config

    # virtual method for passing data through the effect
    def process(self,data):
        raise NotImplementedError()

# volume control effect
class VolumeEffect(EffectModule):

    def __init__(self,buffer_size,config):
        EffectModule.__init__(self,buffer_size,config)

    def process(self,data):
        return self._config["volume"] * data

# distortion effect
# sigmoid envelope from https://dsp.stackexchange.com/questions/13142/digital-distortion-effect-algorithm
class DistortionEffect(EffectModule):

    def __init__(self,buffer_size,config):
        EffectModule.__init__(self,buffer_size,config)

    def process(self,data):
        if (bool(self._config["distortion_enable"])):
            data *= self._config["distortion_amp"] 
            # old method, uses step instead of signmoid cutoff
            # data[ np.abs(data) > (self._config["distortion_cutoff"]) ] *= (self._config["distortion_cutoff"]) / data[ np.abs(data) > (self._config["distortion_cutoff"]) ]
            data = data * (1 - np.exp( -1 * ((data ** 2) / np.abs(data)) / self._config["distortion_cutoff"] ) ) / np.abs(data)
        return data

class RobotEffect(EffectModule):

    def __init__(self,buffer_size,config):
        EffectModule.__init__(self,buffer_size,config)

    def process(self,data):
        if (bool(self._config["robot_enable"])):
            # decimate input
            data = np.repeat(data[::int(self._config["robot_decimation"])],int(self._config["robot_decimation"]),axis=0)
            scl = 4
            dmax = np.abs(data.max())
            norm = 128 * data / dmax
            # reduce precision of samples
            if (bool(self._config["robot_reduce"])):
                # reduce binary data 6 bits
                data = norm.astype(np.int8) // scl
                data = scl * dmax * data.astype(np.float64) / 128
        data[ np.isnan(data) ] = 0
        return data

# Based on http://www.guitarpitchshifter.com/algorithm.htmlhttp://www.guitarpitchshifter.com/algorithm.html
# and related matlab code
class PitchEffect(EffectModule):

    def __init__(self,buffer_size,config):
        EffectModule.__init__(self,buffer_size,config)

        self._prevWindow = None
        self._previousPhase = np.zeros([self._buffer_size])
        self._phaseCume = np.zeros([self._buffer_size])
        self._prevOutput = np.zeros([self._buffer_size])

    def process(self,data):
        if (bool(self._config["pitch_enable"])):
            if (self._prevWindow is None):
                self._prevWindow = data.copy()
            else: 
                indata = np.concatenate( [self._prevWindow , data] )
                self._prevWindow = data.copy()

                stride_step = self._buffer_size // 4        # might parameterize i the future
                out_step = min(int(stride_step * self._config["pitch_shift"]),self._buffer_size)

                # create windows and apply hanning window
                nwn = np.hanning(2*self._buffer_size+1)[1::2] / np.sqrt(((self._buffer_size/stride_step)/2))
                stride = indata.strides[-1]
                windows = as_strided(indata, shape=( ( len(indata) - (self._buffer_size - stride_step) ) // stride_step , self._buffer_size), strides=(stride*stride_step, stride)).copy()
                windows *= nwn 
                 
                #stft
                fft = np.fft.fft(windows,axis=1)
                magFrame = np.abs(fft)
                phaseFrame = np.angle(fft)
                phaseCumeLocal = np.zeros(windows.shape)
                phaseCumeLocal[-1] = self._phaseCume              #use previous phaseCume

                for i in range(windows.shape[0]):
                    #get the current frame and last frame phase difference
                    deltaPhi = phaseFrame[i] - self._previousPhase
                    #store this frame for next run
                    self._previousPhase = phaseFrame[i]            
                    #add the exepcted phase due to the stride
                    deltaPhiPrime = deltaPhi - (stride_step * 2 * np.pi * np.arange(0,self._buffer_size)/self._buffer_size)
                    #map to -pi/pi
                    deltaPhiPrimeMod = np.mod(deltaPhiPrime+np.pi,2*np.pi) - np.pi
                    #convert phase to frequency (radians / sample) and add to bin frequency to get true frequency
                    trueFreq = (2 * np.pi * np.arange(0,self._buffer_size)/self._buffer_size) + deltaPhiPrimeMod/stride_step
                    #multi true frequency by samples to get phase and add to cumlative phase to get current phase
                    phaseCumeLocal[i] = phaseCumeLocal[i - 1] + out_step * trueFreq
                self._phaseCume = phaseCumeLocal[-1]  #save for next iteration
                outputFrame = np.real(np.fft.ifft(magFrame * np.exp(1j * phaseCumeLocal),axis=1))
                outputY = outputFrame * nwn
                outputScaled = np.zeros( [outputY.shape[0] * out_step - out_step + self._buffer_size] )
                outputScaled[:self._buffer_size-out_step] += self._prevOutput[out_step:]
                timeIndex = 0
                
                for i in range(outputY.shape[0]):
                    outputScaled[timeIndex:timeIndex+self._buffer_size] = outputScaled[timeIndex:timeIndex+self._buffer_size] + outputY[i]
                    if (i == (outputY.shape[0] - 2)):
                        self._prevOutput = outputScaled[timeIndex:timeIndex+self._buffer_size].copy()
                    timeIndex += out_step

                data = np.interp(np.linspace(0,outputScaled.shape[0],indata.shape[0]),np.arange(outputScaled.shape[0]),outputScaled)[:self._buffer_size]

        return data

class BassBoostEffect(EffectModule):

    def __init__(self,buffer_size,config):
        EffectModule.__init__(self,buffer_size,config)

    def process(self,data):
        if (bool(self._config["bassboost_enable"])):
            fft = np.fft.rfft(data)
            bassfreq = np.arange( int(50 * (data.shape[0] / self._config["fs"])) , int(250 * (data.shape[0] / self._config["fs"]) ))
            fft[ bassfreq ] *= self._config["bassboost_amp"] * np.hanning(bassfreq.shape[0])
            data = np.fft.irfft(fft)
        return data
