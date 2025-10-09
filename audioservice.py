
import pyaudio
import wave
import numpy as np
from scipy.signal import resample_poly
import threading
import json
import os
from datetime import datetime
from pyrnnoise import RNNoise
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from vosk import KaldiRecognizer
# --- Watchdog Event Handler ---
class RecordingEventHandler(FileSystemEventHandler):
    """
    Handles file system events for the raw recordings directory.
    """
    def __init__(self, audio_service):
        self.audio_service = audio_service
# Redundant
    # def on_created(self, event, on_complete=None):
    #     """Called when a file or directory is created."""
    #     if not event.is_directory and event.src_path.endswith('.wav'):
    #         def delayed_denoise():
    #             import time, os, wave
    #             stable_count = 0
    #             last_size = -1
    #             max_attempts = 20
    #
    #             # Wait for file to stabilize
    #             while stable_count < 10:
    #                 try:
    #                     current_size = os.path.getsize(event.src_path)
    #                 except Exception:
    #                     current_size = -1
    #                 if current_size == last_size and current_size > 0:
    #                     stable_count += 1
    #                 else:
    #                     stable_count = 0
    #                 last_size = current_size
    #                 time.sleep(0.2)
    #                 max_attempts -= 1
    #                 if max_attempts <= 0:
    #                     return
    #
    #             # Verify file readiness
    #             file_ready = False
    #             for attempt in range(10):
    #                 try:
    #                     with open(event.src_path, 'r+b') as f:
    #                         f.seek(0, 2)
    #
    #                     with wave.open(event.src_path, 'rb') as wf:
    #                         channels = wf.getnchannels()
    #                         frames = wf.getnframes()
    #                         if channels > 0 and frames > 0:
    #                             file_ready = True
    #                             break
    #                 except Exception:
    #                     time.sleep(0.5)
    #
    #             if file_ready:
    #                 time.sleep(1.0)
    #                 self.audio_service._denoise_file(event.src_path)
    #
    #         denoise_thread = threading.Thread(target=delayed_denoise)
    #         denoise_thread.start()


# --- Main Audio Service ---
class AudioService:
    def __init__(self):
        # --- Audio Configuration ---
        self.CHUNK = 480
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 48000

        # --- State Management ---
        self.is_recording = False
        self.frames = []
        self.recording_thread = None

        # --- Directory Paths ---
        self.raw_dir = "datastore/raw_recordings/"
        self.processed_dir = "datastore/processed_recordings/"
        os.makedirs(self.raw_dir, exist_ok=True)
        os.makedirs(self.processed_dir, exist_ok=True)

        # --- Denoising ---
        self.denoiser = RNNoise(self.RATE)

        # --- File Watcher ---
        self._start_file_watcher()

    def start_recording(self):
        # ... (This method remains the same as the previous step)
        if self.is_recording: return
        self.is_recording = True
        self.frames = []
        self.recording_thread = threading.Thread(target=self._record_loop)
        self.recording_thread.start()
        print("Audio Service: Recording started.")

    def _record_loop(self):
        # ... (This method remains the same as the previous step)
        p = pyaudio.PyAudio()
        stream = p.open(format=self.FORMAT, channels=self.CHANNELS, rate=self.RATE, input=True, frames_per_buffer=self.CHUNK)
        while self.is_recording:
            data = stream.read(self.CHUNK)
            self.frames.append(data)
        stream.stop_stream()
        stream.close()
        p.terminate()

    def stop_recording(self):
        """Stops recording and saves the raw audio, triggering the watcher."""
        if not self.is_recording: return None
        self.is_recording = False
        self.recording_thread.join()

        # Generate a unique filename with a timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_filename = f"raw_{timestamp}.wav"
        raw_filepath = os.path.join(self.raw_dir, raw_filename)
        
        self._save_wave_file(raw_filepath, self.frames)
        print(f"Audio Service: Raw audio saved to {raw_filepath}")
        return raw_filepath

    def denoise_file(self, raw_filepath):
        """Reads a raw audio file, denoises it, and saves the result."""
        try:
            processed_filename = "processed_" + os.path.basename(raw_filepath)
            processed_filepath = os.path.join(self.processed_dir, processed_filename)
            
            # Verify file exists and is accessible
            if not os.path.exists(raw_filepath) or os.path.getsize(raw_filepath) == 0:
                return
            
            # Verify it's a valid wave file before denoising
            try:
                with wave.open(raw_filepath, 'rb') as test_wf:
                    test_wf.getnchannels()
                    test_wf.getnframes()
            except Exception:
                return
            
            # Create a fresh denoiser instance for each file - ??? what?, it should just denoise A file.
            denoiser = RNNoise(self.RATE)
            
            # Denoise the audio file with progress bar
            gen = denoiser.denoise_wav(raw_filepath, processed_filepath)
            for _ in gen:
                pass  # The pyrnnoise library handles the progress bar internally
            
            # Verify output file was created successfully
            if os.path.exists(processed_filepath) and os.path.getsize(processed_filepath) > 0:
                print(f"Audio Service: Denoised audio saved to {processed_filepath}")
                
        except Exception as e:
            print(f"Audio Service: Error during denoising: {e}")
        return processed_filepath
    def _start_file_watcher(self):
        """Initializes and starts the watchdog observer in a daemon thread."""
        event_handler = RecordingEventHandler(self)
        observer = Observer()
        observer.schedule(event_handler, self.raw_dir, recursive=False)
        # Use a daemon thread so it automatically shuts down with the main app
        observer_thread = threading.Thread(target=observer.start)
        observer_thread.daemon = True
        observer_thread.start()
        print(f"Audio Service: Now watching for new files in '{self.raw_dir}'")

    def _save_wave_file(self, path, frames_to_save):
        """Save wave file with proper cleanup and error handling."""
        p = None
        wf = None
        try:
            p = pyaudio.PyAudio()
            wf = wave.open(path, 'wb')
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(p.get_sample_size(self.FORMAT))
            wf.setframerate(self.RATE)
            wf.writeframes(b''.join(frames_to_save))
            
        except Exception as e:
            print(f"Audio Service: Error saving wave file: {e}")
            raise
        finally:
            if wf:
                wf.close()
            if p:
                p.terminate()
            import time
            time.sleep(0.1)
    def transcribe_audio(self, model, wav_path):
        """Transcribes an audio file using Vosk"""
        wf = wave.open(wav_path, "rb")

        recognizer = KaldiRecognizer(model, wf.getframerate())
        recognizer.SetWords(True)

        result_text = ""
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            if recognizer.AcceptWaveform(data):
                res = json.loads(recognizer.Result())
                result_text += " " + res.get("text", "")
        # Get final bit of recognized text
        res = json.loads(recognizer.FinalResult())
        result_text += " " + res.get("text", "")
        wf.close()

        return result_text.strip()
    def resample_to_16k(self, in_wav):
        with wave.open(in_wav, 'rb') as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            data = wf.readframes(n_frames)

            audio = np.frombuffer(data, dtype=np.int16)
            # Downsample from 48000 → 16000 (ratio 1/3)
            resampled = resample_poly(audio, 1, 3)
            resampled = resampled.astype(np.int16)
            processed_filename = "resampled_" + os.path.basename(in_wav)
            processed_filepath = os.path.join(self.processed_dir, processed_filename)
            out_wav = processed_filepath
        with wave.open(out_wav, 'wb') as wf:
            wf.setnchannels(n_channels)
            wf.setsampwidth(sampwidth)
            wf.setframerate(16000)
            wf.writeframes(resampled.tobytes())

        return out_wav