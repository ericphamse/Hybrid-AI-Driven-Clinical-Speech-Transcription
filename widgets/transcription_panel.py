

import os
# from audioservice import AudioService
import threading
import uuid
from datetime import datetime
from audioservice import AudioService
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import BooleanProperty
from kivy.app import App
from kivy.clock import Clock
from vosk import Model
class TranscriptionPanel(BoxLayout):
    audio_service = AudioService()
    is_recording = BooleanProperty(False)
    transcription_id = str(uuid.uuid4())
    # Load Vosk model ONCE at startup (don't reload for every audio)
    model_path = os.path.join("model", "vosk-model-small-en-us-0.15")  # Loads in the vosk model
    if not os.path.exists(model_path):
        raise FileNotFoundError("Vosk model not found at: " + model_path) # error raised in case something's wrong
    
    model = Model(model_path) #Loads the model once 
    
    def record_action(self):
        self.is_recording = not self.is_recording
        if self.is_recording:
            self.ids.transcription_input.text = '' #Makes it so that it removes the previous transcribed text
            self.audio_service.start_recording() # Runs a function that starts recording
        else:
            wav_path = self.audio_service.stop_recording()
            # Once it's done creating that audio, return the wav path it was made at
            def set_text(dt):
                # Call the resampling to convert 48k Audio into 16k Audio, which is fed into vosk since it only accepts that.
                processed_wav_path = self.audio_service.denoise_file(wav_path)
                transcription = self.audio_service.transcribe_audio(self.model,self.audio_service.resample_to_16k(processed_wav_path))
                self.ids.transcription_input.text = transcription
            Clock.schedule_once(set_text, 0)

    def generate_report_action(self):
        text_input = self.ids.transcription_input
        text = text_input.text
        time_string = datetime.now().isoformat(timespec='seconds')
        # Only generate report if text is not empty
        if text.strip():
            # Load structured data and update display
            main_screen = App.get_running_app().root.get_screen('main')
            struct_panel = main_screen.ids.structuring_panel
            status = main_screen.ids.top_bar
            if status.network_status != False:
                def task():
                    # Run heavy function off the main thread
                    # struct_panel.prints()
                    result = struct_panel.generate_json(text, self.transcription_id, time_string)        
                    Clock.schedule_once(lambda dt: struct_panel.load_json_data())
                    Clock.schedule_once(lambda dt: struct_panel.update_log_display())
                threading.Thread(target=task, daemon=True).start()
            else:
                print("nothing for now")
            text_input.text = ''
