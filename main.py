

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import ObjectProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout
import json
import os
from kivy.clock import Clock
import threading
import time
import requests
# Import LoginScreen and MainScreen from screens
from screens.loginscreen import LoginScreen
from screens.main_screen import MainScreen
from screens.pdf_preview_screen import PDFPreviewScreen
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

class TranscriptionPanel(BoxLayout):
    # Add Kivy properties that your KV file expects
    is_recording = BooleanProperty(False)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.backend_url = "http://localhost:5000"
        self.processed_recordings_dir = "datastore/raw_recordings"
        
        # Create directory if it doesn't exist
        os.makedirs(self.processed_recordings_dir, exist_ok=True)
        print(f"🎤 TranscriptionPanel initialized")
        print(f"📁 Monitoring directory: {os.path.abspath(self.processed_recordings_dir)}")
    
    def record_action(self):
        """Handle record button press - this connects to your KV file"""
        if self.is_recording:
            print("🛑 Stop recording requested")
            self.is_recording = False
            # Your existing recording system should handle the stop
        else:
            print("🎤 Start recording requested")
            self.is_recording = True
            # Your existing recording system should handle the start
    
    def generate_report_action(self):
        """Handle generate report button press"""
        print("📊 Generate report requested")
        # This will be implemented later
    
    def update_transcription_display(self, text):
        """Update the transcription text display with raw transcript"""
        try:
            print(f"📝 Updating display with: {text[:100]}...")
            
            # Method 1: Try to find by ID first
            if hasattr(self.ids, 'transcription_text'):
                self.ids.transcription_text.text = text
                print(f"✅ Updated via ID: transcription_text")
                return
            
            # Method 2: Search for the text widget
            def find_text_widget(widget, depth=0):
                if hasattr(widget, 'text'):
                    current_text = str(widget.text)
                    # Look for the placeholder text
                    if ('Your transcribed text will appear here' in current_text or 
                        'transcribed text will appear' in current_text or
                        '🎤 Processing audio' in current_text):
                        return widget
                
                # Check children recursively
                for child in widget.children:
                    result = find_text_widget(child, depth + 1)
                    if result:
                        return result
                return None
            
            text_widget = find_text_widget(self)
            
            if text_widget:
                text_widget.text = text
                print(f"✅ Updated transcription display successfully")
            else:
                print("❌ Could not find text widget to update")
                
        except Exception as e:
            print(f"❌ Error updating transcription display: {e}")
            import traceback
            traceback.print_exc()
    
    def test_backend_connection(self):
        """Test if backend is running"""
        try:
            response = requests.get(f"{self.backend_url}/", timeout=5)
            print(f"✅ Backend is running at {self.backend_url}")
            return True
        except requests.exceptions.ConnectionError:
            print(f"❌ Backend not running at {self.backend_url}")
            print("Please start your backend with: cd Online && python backend.py")
            return False
        except Exception as e:
            print(f"❌ Backend connection error: {e}")
            return False
    
    def on_recording_finished(self, audio_file_path):
        """Call this method when recording is finished and saved"""
        print(f"🎤 Recording finished: {audio_file_path}")
        
        # Show processing indicator immediately
        Clock.schedule_once(
            lambda dt: self.update_transcription_display("🎤 Processing audio with AWS... Please wait...")
        )
        
        # Send to backend automatically
        threading.Thread(target=self.send_to_backend, args=(audio_file_path,), daemon=True).start()
    
    def send_to_backend(self, audio_file_path):
        """Send the recorded audio to backend for AWS processing"""
        try:
            if not os.path.exists(audio_file_path):
                print(f"❌ Audio file not found: {audio_file_path}")
                return
                
            print(f"📤 Sending {audio_file_path} to backend...")
            
            # Send file to Flask backend
            with open(audio_file_path, 'rb') as audio_file:
                files = {'file': ('audio.wav', audio_file, 'audio/wav')}
                
                response = requests.post(
                    f"{self.backend_url}/transcribe",
                    files=files,
                    timeout=300  # 5 minutes timeout for AWS processing
                )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Backend processing successful!")
                print("📋 Response:", result)
                
                if result.get('status') == 'success':
                    self.handle_aws_result(result)
                else:
                    error_msg = result.get('message', 'Unknown error')
                    print(f"❌ Backend processing failed: {error_msg}")
                    Clock.schedule_once(lambda dt: self.update_transcription_display(f"❌ Processing failed: {error_msg}"))
                    
            else:
                print(f"❌ Backend HTTP error: {response.status_code}")
                print("Response:", response.text)
                Clock.schedule_once(lambda dt: self.update_transcription_display(f"❌ Backend error: {response.status_code}"))
                
        except requests.exceptions.ConnectionError:
            print("❌ Cannot connect to backend. Make sure backend.py is running!")
            Clock.schedule_once(lambda dt: self.update_transcription_display("❌ Backend not running!"))
        except Exception as e:
            print(f"❌ Error sending to backend: {e}")
            Clock.schedule_once(lambda dt: self.update_transcription_display(f"❌ Error: {str(e)}"))
    
    def handle_aws_result(self, result):
        """Handle the AWS processing result from backend"""
        try:
            # Extract the RAW transcript text from AWS Transcribe
            raw_transcript = result.get('transcript', '')
            
            print(f"📝 Raw AWS Transcript: {raw_transcript}")
            
            # Display the raw transcript text immediately
            if raw_transcript:
                Clock.schedule_once(
                    lambda dt: self.update_transcription_display(raw_transcript)
                )
            else:
                Clock.schedule_once(
                    lambda dt: self.update_transcription_display("❌ No transcript received from AWS")
                )
            
        except Exception as e:
            print(f"❌ Error handling AWS result: {e}")
            Clock.schedule_once(lambda dt: self.update_transcription_display("❌ Error processing results"))
    
    def monitor_processed_recordings(self):
        """Monitor datastore/raw_recordings folder for new files"""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
            
            class RecordingHandler(FileSystemEventHandler):
                def __init__(self, transcription_panel):
                    self.transcription_panel = transcription_panel
                    print(f"🔍 RecordingHandler initialized for {transcription_panel.processed_recordings_dir}")
                
                def on_created(self, event):
                    print(f"📁 File created: {event.src_path}")
                    if not event.is_directory and event.src_path.endswith('.wav'):
                        print(f"🎤 New recording detected: {event.src_path}")
                        # Wait a moment for file to be completely written
                        time.sleep(2)
                        self.transcription_panel.on_recording_finished(event.src_path)
            
            # Set up file system monitoring
            event_handler = RecordingHandler(self)
            observer = Observer()
            observer.schedule(event_handler, self.processed_recordings_dir, recursive=False)
            observer.start()
            print(f"👀 File monitor started for: {os.path.abspath(self.processed_recordings_dir)}")
            
            # Keep observer reference
            self.observer = observer
            
        except ImportError:
            print("❌ watchdog not installed. Install with: pip install watchdog")
        except Exception as e:
            print(f"❌ Error setting up file monitoring: {e}")

class StructuringPanel:
    pass

class MedicalApp(App):
    session_data = ObjectProperty(None)

    def build(self):
        self.session_data = {'clinician_name': '', 'log_entries': []}
        # Explicitly load the KV file for LoginScreen, MainScreen, and PDFPreviewScreen
        Builder.load_file('screens/loginscreen.kv')
        Builder.load_file('screens/main_screen.kv')
        Builder.load_file('screens/pdf_preview_screen.kv')
        root = RootWidget()
        root.add_widget(LoginScreen(name='login'))
        root.add_widget(MainScreen(name='main'))
        root.add_widget(PDFPreviewScreen(name='pdf_preview'))
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
    def on_stop(self):
        db_path = os.path.join(os.getcwd(), "clinical_transcription.db")
        
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
                print("Deleted.")
            except Exception as e:
                print("Couldn't Delete.")
        else:
            print("No database Found.")
if __name__ == '__main__':
    MedicalApp().run()
