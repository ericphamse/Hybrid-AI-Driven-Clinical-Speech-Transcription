

import os
import json
# from audioservice import AudioService
import threading
import uuid
from datetime import datetime
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import BooleanProperty
from kivy.app import App
from kivy.clock import Clock

class TranscriptionPanel(BoxLayout):
    # audio_service = AudioService()
    is_recording = BooleanProperty(False)
    transcription_id = str(uuid.uuid4())
    def record_action(self):
        self.is_recording = not self.is_recording
        if self.is_recording:
            # Start recording audio
            # self.audio_service.start_recording()
            print("TranscriptionPanel: Audio recording started.")
        else:
            # Stop recording audio and save to .wav
            # wav_path = self.audio_service.stop_recording()
            # print(f"TranscriptionPanel: Audio recording stopped. WAV saved at {wav_path}")
            self.ids.transcription_input.text = "Patient is going into shock, blood pressure is 210 over 90. Administering 500ml of UV fluid."
            
            # def set_text(dt):
            #     json_path = os.path.join('datastore', 'sampledata.json')
            #     if os.path.exists(json_path):
            #         with open(json_path, 'r') as f:
            #             data = json.load(f)
            #         raw_text = data.get('rawTranscriptionId', '')
            #
            #             self.ids.transcription_input.text = raw_text
            #         except Exception as e:
            #             print('Error setting text via ids:', e)
            #             # Fallback: try to find TextInput in children
            #             for child in self.children:
            #                 if hasattr(child, 'id') and child.id == 'transcription_input':
            #                     child.text = raw_text
            #                     print('Set text via children fallback')
            # Clock.schedule_once(set_text, 0)

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
