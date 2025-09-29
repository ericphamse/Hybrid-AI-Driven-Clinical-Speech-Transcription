
import pyaudio
import wave
import threading
import os
from datetime import datetime
from pyrnnoise import RNNoise
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# --- Watchdog Event Handler ---
class RecordingEventHandler(FileSystemEventHandler):
    """
    Handles file system events for the raw recordings directory.
    """
    def __init__(self, audio_service):
        self.audio_service = audio_service

    def on_created(self, event):
        """Called when a file or directory is created."""
        if not event.is_directory and event.src_path.endswith('.wav'):
            def delayed_denoise():
                import time, os, wave
                stable_count = 0
                last_size = -1
                while stable_count < 5:
                    try:
                        current_size = os.path.getsize(event.src_path)
                    except Exception:
                        current_size = -1
                    if current_size == last_size and current_size > 0:
                        stable_count += 1
                    else:
                        stable_count = 0
                    last_size = current_size
                    time.sleep(0.3)  # Check every 0.3 seconds, need 5 stable checks (1.5s)
                # Try opening file for reading before denoising
                for _ in range(3):
                    try:
                        with wave.open(event.src_path, 'rb') as wf:
                            wf.getnchannels()
                        break
                    except Exception:
                        time.sleep(0.3)
                self.audio_service._denoise_file(event.src_path)
            denoise_thread = threading.Thread(target=delayed_denoise)
            denoise_thread.start()


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
        # self.is_recording = True
        # self.frames = []
        # self.recording_thread = threading.Thread(target=self._record_loop)
        # self.recording_thread.start()
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

    def _denoise_file(self, raw_filepath):
        """Reads a raw audio file, denoises it, and saves the result."""
        try:
            processed_filename = "processed_" + os.path.basename(raw_filepath)
            processed_filepath = os.path.join(self.processed_dir, processed_filename)
            try:
                gen = self.denoiser.denoise_wav(raw_filepath, processed_filepath)
                for _ in gen:
                    pass
            except Exception:
                pass
        except Exception:
            pass

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
        # ... (This method remains the same as the previous step)
        p = pyaudio.PyAudio()
        wf = wave.open(path, 'wb')
        wf.setnchannels(self.CHANNELS)
        wf.setsampwidth(p.get_sample_size(self.FORMAT))
        wf.setframerate(self.RATE)
        wf.writeframes(b''.join(frames_to_save))
        wf.close()
        p.terminate()
