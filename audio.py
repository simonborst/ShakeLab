import sounddevice as sd
import numpy as np
from globdata import glob_data
from tkinter import filedialog
import wave

# This module handles audio processing and playback using the sounddevice library.

# Audio Processing
stream = None # Global variable for audio stream
with glob_data.lock:
    glob_data.recording = False  # Tracks if recording is enabled

def sine_wave(frequency, amplitude, previous_amplitude, phase, num_samples):
    t = np.arange(num_samples) / 48000
    amp_ramp = np.linspace(previous_amplitude, amplitude, num_samples)  # gradual transition to new amplitude
    return amp_ramp * np.sin(2 * np.pi * frequency * t + phase)


def start_audio_stream(app, device_id, buffer_size):
    global stream  # Ensure stream is treated as a global variable
    def audio_callback(outdata, frames, time_info, status):
        outdata.fill(0)

        channel_1_mix = np.zeros(frames)  # Mix variable for left channel
        channel_2_mix = np.zeros(frames)  # Mix variable for right channel
        
        # For each effect in audio
        with glob_data.lock: # Make a thread safe copy for audio processing
            audio_copy = glob_data.audio.copy()

        for effect_name, effect_params in audio_copy.items():
            # Get parameters from audio variable
            amplitude = effect_params.get('amplitude', 0)
            prev_amplitude = effect_params.get('prev_amplitude', 0)
            phase = effect_params.get('phase', 0)

            # Get effect parameters from the GUI
            app_effect = app.effects.get(effect_name)
            frequency = float(app_effect.frequency_entry.get())
            channel = app_effect.channel_dropdown.get()
            try:
                N = app_effect.transition_samples_entry.get() or frames  # default is buffer size, could add to GUI later
            except AttributeError:
                N = frames
            
            wave_gen = sine_wave(frequency, amplitude, prev_amplitude, phase, frames)
            with glob_data.lock:
                glob_data.audio[effect_name]['phase'] = glob_data.audio[effect_name].get('phase', 0) + (2 * np.pi * frequency * frames) / 48000
                glob_data.audio[effect_name]['prev_amplitude'] = amplitude  # save amplitude to use as previous amplitude next time

            # Add the data to the appropriate mix variable
            if channel == "channel_1":
                channel_1_mix += wave_gen
            elif channel == "channel_2":
                channel_2_mix += wave_gen
            
        # Protect against clipping
        channel_1_mix = np.clip(channel_1_mix, -1.0, 1.0)
        channel_2_mix = np.clip(channel_2_mix, -1.0, 1.0)
        
        # Play the data
        outdata[:, 0] = channel_1_mix  # Left channel
        outdata[:, 1] = channel_2_mix  # Right channel

        if glob_data.recording:
            with glob_data.lock:
                glob_data.recorded_frames.append(outdata.copy())  # Record the output data

    # Setup the audio stream
    stream = sd.OutputStream(
        samplerate=48000,
        blocksize=buffer_size,  # Use the selected buffer size
        channels=2,  # Change to 2 channels
        dtype='float32',
        device=device_id,
        callback=audio_callback,
        extra_settings=sd.WasapiSettings(exclusive=True)  # Enable exclusive mode - should be lower latency
    )
    stream.start()
    return stream


def get_audio_devices(): # Function to get output devices
    devices = sd.query_devices()
    return devices # Returns a dictionary mapping device indices to device names for output devices.


def get_audio_devices_formatted(devices=None):
    if devices is None:
        devices = get_audio_devices()
    output_devices = {
        idx: f"{idx}: {dev['name']} (Host API: {sd.query_hostapis(dev['hostapi'])['name']}, Outputs: {dev['max_output_channels']}, SR: {int(dev['default_samplerate'])} Hz)"
        for idx, dev in enumerate(devices) if dev['max_output_channels'] > 0
    }
    return output_devices

def save_recording():
    filename = filedialog.asksaveasfilename(defaultextension=".wav", filetypes=[("WAV files", "*.wav")])
    if filename:
        recorded_data = np.concatenate(glob_data.recorded_frames, axis=0) # Convert recorded frames to numpy array
        recorded_data = (recorded_data * 32767).astype(np.int16) # Normalize and convert to 16-bit PCM

        with wave.open(filename, 'wb') as wf: # Save as WAV file
            wf.setnchannels(2)  # Stereo
            wf.setsampwidth(2)  # 16-bit samples
            wf.setframerate(48000)  # Sample rate
            wf.writeframes(recorded_data.tobytes())
        
        print(f"Recording saved to {filename}")

