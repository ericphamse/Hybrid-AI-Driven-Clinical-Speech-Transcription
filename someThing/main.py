

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import ObjectProperty
import json
import os
# Import LoginScreen and MainScreen from screens
from screens.loginscreen import LoginScreen
from screens.main_screen import MainScreen
from kivy.lang import Builder

class RootWidget(ScreenManager):
    pass



from datetime import datetime
class MainScreen(Screen):
    def process_new_transcription(self, text):
        app = App.get_running_app()
        # Create a new log entry
        entry = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'progress_note': text,
            'observation': 'Mock observation',
            'medication': 'Mock medication'
        }
        app.session_data['log_entries'].append(entry)
        app.save_session_to_json()
        # Refresh the structuring panel
        self.ids.main_layout.ids.structuring_panel.update_log_display()

class TopBar:
    pass

class TranscriptionPanel:
    pass

class StructuringPanel:
    pass

class MedicalApp(App):
    session_data = ObjectProperty(None)

    def build(self):
        self.session_data = {'clinician_name': '', 'log_entries': []}
        # Explicitly load the KV file for LoginScreen and MainScreen
        Builder.load_file('screens/loginscreen.kv')
        Builder.load_file('screens/main_screen.kv')
        root = RootWidget()
        root.add_widget(LoginScreen(name='login'))
        root.add_widget(MainScreen(name='main'))
        return root

    def save_session_to_json(self):
        with open('session.json', 'w') as f:
            json.dump(self.session_data, f)

    def load_session_from_json(self):
        if os.path.exists('session.json'):
            with open('session.json', 'r') as f:
                self.session_data = json.load(f)

    def on_start(self):
        self.load_session_from_json()

if __name__ == '__main__':
    MedicalApp().run()
