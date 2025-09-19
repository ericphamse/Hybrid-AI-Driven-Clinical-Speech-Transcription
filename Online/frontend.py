from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.filechooser import FileChooserIconView
import requests

class TranscribeApp(App):
    def build(self):
        self.layout = BoxLayout(orientation="vertical")
        self.label = Label(text="Choose an audio file to upload", size_hint=(1, 0.1))

        self.filechooser = FileChooserIconView(
            size_hint=(1, 0.7),
            path="C:/Western Sydney University/COMP 3018/TranscribeMedicalAWS_personalEmail"
        )
        self.upload_button = Button(text="Transcribe", size_hint=(1, 0.2))
        self.upload_button.bind(on_press=self.upload_and_transcribe)

        self.layout.add_widget(self.label)
        self.layout.add_widget(self.filechooser)
        self.layout.add_widget(self.upload_button)

        return self.layout

    def upload_and_transcribe(self, instance):
        selected = self.filechooser.selection
        if not selected:
            self.label.text = "No file selected!"
            return

        filepath = selected[0]
        self.label.text = "Uploading and transcribing..."
        url = "http://127.0.0.1:5000/transcribe"
        with open(filepath, "rb") as f:
            files = {"file": f}
            response = requests.post(url, files=files)

        if response.status_code == 200:
            result = response.json()
            if result["status"] == "success":
                self.label.text = "Transcript:\n" + result["transcript"]
            else:
                self.label.text = "Transcription failed."
        else:
            self.label.text = "Error connecting to server."

if __name__ == "__main__":
    TranscribeApp().run()
