import math
import random
import warnings
import sys

import librosa  # for audio processing
import matplotlib.pyplot as plt
import numpy as np
import torch
import torchaudio
from IPython.display import Audio, display
from scipy.io import wavfile  # for audio processing
from torchaudio import transforms
from logger import Logger

warnings.filterwarnings("ignore")


class AudioUtil():
    def __init__(self):
        """Initialize data preprocessing."""
        try:
            self.logger = Logger("preprocess_data.log").get_app_logger()
            self.logger.info(
                'Successfully Instantiated DataLoader Class Object')
        except Exception as e:
            self.logger.error(
                'Failed to Instantiate LoadData Class Object')
            self.logger.error(e)
            sys.exit(1)

    def open(self, audio_file):
        """Load an audio file. Return the signal as a tensor and the sample rate."""
           try:
                self.logger.info(
                    'Opening audio file for data preprocessing')
                sig, sr = torchaudio.load(audio_file)
                return (sig, sr)
            except Exception as e:
                self.logger.error('Failed to load data')
                self.logger.error(e)
                sys.exit(1)

        def resize_audio(self, audios: dict,max_duration:float) -> dict:
            """Extend duration of audio samples to max_duration.

            Args:
                    audios (dict): Dictionary of audio samples.
                    max_duration (float): The duration to set for the audio samples

            Returns:
                    dict: Dictionary of resized audio samples.
            """
            try:
                self.logger.info("Resizing audio samples")
                resized_audios = {}
                for label in audios:
                    resized_audios[label] = librosa.util.fix_length(audios[label], size=int(max_duration*44100))
                return resized_audios
            except Exception as e:
                self.logger.error('Failed to resize audio')
                self.logger.error(e)
                sys.exit(1)
        # ----------------------------
        # Show a widget to play the audio sound
        # ----------------------------

        @staticmethod
        def play(self, aud):
            sig, sr = aud
            display(Audio(data=sig, rate=sr))

        @staticmethod
        def rechannel(aud, new_channel):
            sig, sr = aud
            # resig = sig

            if (sig.shape[0] == new_channel):
                # Nothing to do
                return aud

            if (new_channel == 1):
                # Convert from stereo to mono by selecting only the first channel
                resig = sig[:1, :]
            else:
                # Convert from mono to stereo by duplicating the first channel
                resig = torch.cat([sig, sig])

            return ((resig, sr))

        # or we can open and resample the data the same time
        # resampling any loaded audio files to 44.1KHZ
        @staticmethod
        def resample(df, column):
            sampled_audio = []
            rates = []
            for i in df[column]:
                audio, rate = librosa.load(i, sr=44100)
                sampled_audio.append(audio)
                rates.append(rate)

            return (sampled_audio, rates)

        @staticmethod
        def resample(aud, newsr):
            sig, sr = aud

            if (sr == newsr):
                # Nothing to do
                return aud

            num_channels = sig.shape[0]
            # Resample first channel
            resig = torchaudio.transforms.Resample(sr, newsr)(sig[:1, :])
            if (num_channels > 1):
                # Resample the second channel and merge both channels
                retwo = torchaudio.transforms.Resample(sr, newsr)(sig[1:, :])
                resig = torch.cat([resig, retwo])

            return ((resig, newsr))

        # ----------------------------
        # Pad (or trim) the signal to a fixed length 'max_ms' in milliseconds
        # ----------------------------
        @staticmethod
        def pad_trim(aud, max_ms):
            sig, sr = aud
            num_rows, sig_len = sig.shape
            max_len = sr//1000 * max_ms

            if (sig_len > max_len):
                # Trim the signal to the given length
                sig = sig[:, :max_len]

            elif (sig_len < max_len):
                # Length of padding to add at the beginning and end of the signal
                pad_begin_len = random.randint(0, max_len - sig_len)
                pad_end_len = max_len - sig_len - pad_begin_len

                # Pad with 0s
                pad_begin = torch.zeros((num_rows, pad_begin_len))
                pad_end = torch.zeros((num_rows, pad_end_len))

                sig = torch.cat((pad_begin, sig, pad_end), 1)

            return (sig, sr)

        # ----------------------------
        # Shifts the signal to the left or right by some percent. Values at the end
        # are 'wrapped around' to the start of the transformed signal.
        # ----------------------------
        @staticmethod
        def signal_shift(aud, max_shift_pct):
            sig, sr = aud
            roll_by = int(random.random()*max_shift_pct*len(sig[0]))
            return (sig.roll(roll_by), sr)

        # ----------------------------
        # Generate a Spectrogram
        # ----------------------------
        @staticmethod
        def spectro_gram(aud, spectro_type='mel', n_mels=64, n_fft=1024, hop_len=None):
            sig, sr = aud
            f_min, f_max, ws, top_db, pad = 0.0, None, None, 80, 0

            # spec has shape [channel, n_mels, time], where channel is mono, stereo etc
            if (spectro_type == 'mel'):
                spec = transforms.MelSpectrogram(
                    sr, n_fft, ws, hop_len, f_min, f_max, pad, n_mels)(sig)
            elif (spectro_type == 'mfcc'):
                pass
            else:
                spec = transforms.Spectrogram(
                    n_fft, ws, hop_len, pad, normalize=False)(sig)

            # Convert to decibels
            spec = transforms.AmplitudeToDB(top_db=top_db)(spec)
            return (spec)

        # ----------------------------
        # Augment the Spectrogram by masking out some sections of it in both the frequency
        # dimension (ie. horizontal bars) and the time dimension (vertical bars) to prevent
        # overfitting and to help the model generalise better. The masked sections are
        # replaced with the mean value.
        # ----------------------------

        @staticmethod
        def spectro_augment(spec, max_mask_pct=0.1, n_freq_masks=1, n_time_masks=1):
            _, n_mels, n_steps = spec.shape

            # Frequency Masking: frequency channels [f0, f0 + f) are masked. f is chosen from a
            # uniform distribution from 0 to the frequency mask parameter F, and f0 is chosen
            # from (0, ν − f) where ν is the number of frequency channels.
            # Time Masking: t consecutive time steps [t0, t0 + t) are masked. t is chosen from a
            # uniform distribution from 0 to the time mask parameter T, and t0 is chosen from [0, τ − t).

            # Max height of the frequency mask
            # rounding up in case of small %
            F = math.ceil(n_mels * max_mask_pct)
            # Max width of the time mask
            T = math.ceil(n_steps * max_mask_pct)

            # Create frequency masks
            fill = spec.mean()
            for i in range(0, n_freq_masks):
                f = random.randint(0, F)
                f0 = random.randint(0, n_mels-f)
                spec[0][f0:f0+f] = fill

            # Create time masks
            for i in range(0, n_time_masks):
                t = random.randint(0, T)
                t0 = random.randint(0, n_steps-t)
                spec[0][:, t0:t0+t] = fill
            return spec

        # ----------------------------
        # Plot the audio signal
        # ----------------------------
        def show_wave(aud, label='', ax=None):
            sig, sr = aud
            if (not ax):
                _, ax = plt.subplots(1, 1, figsize=(3, 3))
            ax.plot(sig[0])
            ax.set_title(label)

        # ----------------------------
        # Plot the audio signal before and after a transform
        # ----------------------------
        def show_transform(orig, trans):
            osig, osr = orig
            tsig, tsr = trans
            if orig is not None:
                plt.plot(osig[0], 'm', label="Orig.")
            if trans is not None:
                plt.plot(tsig[0], 'c', alpha=0.5, label="Transf.")
            plt.legend()
            plt.show()

        # ----------------------------
        # Plot the spectrogram
        # ----------------------------
        def show_spectro(spec, label='', ax=None, figsize=(6, 6)):
            if (not ax):
                _, ax = plt.subplots(1, 1, figsize=figsize)
            # Reduce first dimension if it is greyscale
            ax.imshow(spec if (spec.shape[0] == 3) else spec.squeeze(0))
            ax.set_title(f'{label}, {list(spec.shape)}')
