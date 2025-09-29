import kivy
kivy.require('2.3.0')
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
# from pyrnnoise import RNNoise
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline
import json
import wave
import torch
import numpy as np
# from peft import PeftModel
import pyaudio
import noisereduce as nr
import sqlite3
from vosk import Model, KaldiRecognizer
import json
import threading
from ctransformers import AutoModelForCausalLM
from kivy.clock import Clock
class AudioApp(App):
    def build(self):
        self.layout = BoxLayout(orientation='vertical')
        self.scroll_view = ScrollView(size_hint=(1, 0.3))
        self.label = Label(text="Press Start to Begin", size_hint=(1, 0.04))
        self.label2 = Label(text="TinyLlama JSON output will appear here", size_hint=(1, 0.04))
        self.start_btn = Button(text="Start", on_press=self.start_recording)
        self.test_llama_btn = Button(text="Test Llama", on_press=self.test_llama)
        self.show_table = Button(text="Show Table", on_press=self.refreshList, size_hint=(1, 0.04))
        self.table_texts = Label(text="placeHolder", size_hint=(1, 0.4))
        button_row = BoxLayout(orientation='horizontal', size_hint=(1, 0.04))

        button_row.add_widget(self.start_btn)
        button_row.add_widget(self.test_llama_btn)
        self.scroll_view.add_widget(self.table_texts)
        
        self.layout.add_widget(self.label)
        self.layout.add_widget(button_row)
        self.layout.add_widget(self.label2)
        self.layout.add_widget(self.show_table)
        self.layout.add_widget(self.scroll_view)

        self.is_recording = False
        self.p = None
        self.stream = None
        self.saved_text = ""  # Store finalized text when stopped

        # Load vosk model
        self.model = Model("vosk-model-small-en-us-0.15")
        self.recognizer = KaldiRecognizer(self.model, 16000)
        #Load the dataset for later
        with open("training_data.json", "r", encoding="utf-8") as f:
            training_data = [(item['text'], item['label']) for item in json.load(f)]
        texts, labels = zip(*training_data)

        # Build a pipeline
        self.classifier = make_pipeline(TfidfVectorizer(), MultinomialNB())

        # Train the model
        self.classifier.fit(texts, labels)
        
        # Load TinyLlama base + LoRA fine-tuned weights
        self.llama_model = AutoModelForCausalLM.from_pretrained(
    "tinyllama-1.1b-chat-v1.0.Q5_K_M.gguf",
    model_type="llama",
)
                # --- SQLite Setup ---
        db_file = "simple.db"
        self.conn = sqlite3.connect(db_file)
        self.cursor = self.conn.cursor()

        # Create table if it doesn't exist
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS simple_table (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT
            )
        """)
        self.conn.commit()
        self.conn.close()


        return self.layout

    def start_recording(self, instance):
        if self.is_recording:
            self.is_recording = False
            self.saved_text = self.label.text
            Clock.schedule_once(lambda dt: setattr(self.start_btn, 'text', "start"))
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            if self.p:
                self.p.terminate()
            self.label.text = "Stopped."       
        else:
            self.is_recording = True
            self.label.text = "Listening..."
            self.saved_text = ""  # Reset saved text
            Clock.schedule_once(lambda dt: setattr(self.start_btn, 'text', "stop"))
            threading.Thread(target=self.record_and_transcribe, daemon=True).start()
        # Save the last finalized text to be processed by Llama


        


 
    def record_and_transcribe(self):
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=pyaudio.paInt16,
                                  channels=1,
                                  rate=16000,
                                  input=True,
                                  frames_per_buffer=4000)
    
        while self.is_recording:
            data = self.stream.read(4000, exception_on_overflow=False)
            audio_np = np.frombuffer(data, dtype=np.int16)
    
            # --- Noise Reduction ---
            reduced_noise = nr.reduce_noise(y=audio_np,stationary=False, sr=16000)
    
            # --- Amplify if too quiet ---
            if np.max(np.abs(reduced_noise)) < 5000:
                reduced_noise = reduced_noise * 2
            
            reduced_noise = np.clip(reduced_noise, -32768, 32767).astype(np.int16)
            audio_bytes = reduced_noise.tobytes()
    
            # Only run Vosk on finalized results
            if self.recognizer.AcceptWaveform(audio_bytes):
                result = json.loads(self.recognizer.Result())
                text = result.get("text", "")
                if text:
                    self.update_label(text)
            else:
                partial = json.loads(self.recognizer.PartialResult())
                text = partial.get("partial", "")
                if text:
                    self.update_label(text)

    # def record_and_transcribe(self):
    #     speech_threshold = 0.6
    #     desired_buffer_size = 100 #around 1 second
    #     audio_buffer = []
    #     self.p = pyaudio.PyAudio()
    #     self.stream = self.p.open(format=pyaudio.paInt16,
    #                           channels=1,
    #                           rate=48000,
    #                           input=True,
    #                           frames_per_buffer=4000)
    #     denoiser = RNNoise(sample_rate=48000)
    #     rec = self.recognizer  # Vosk recognizer
    #
    #     while self.is_recording:
    #         data = self.stream.read(4000, exception_on_overflow=False)
    #         audio_np = np.frombuffer(data, dtype=np.int16)
    #
    #     # Process frame by frame
    #         for speech_prob, denoised_frame in denoiser.denoise_chunk(audio_np):
    #             # denoised_bytes = denoised_frame.astype(np.int16).tobytes()
    #             # print(speech_prob)
    #             if speech_prob > speech_threshold: 
    #                 audio_buffer.append(denoised_frame)
    #
    #         # if len(audio_buffer) >= desired_buffer_size:
    #         if len(audio_buffer) > 0:
    #             audio_np = np.concatenate(audio_buffer)
    #             audio_bytes = audio_np.astype(np.int16).tobytes()
    #             if rec.AcceptWaveform(audio_bytes):
    #                 result = json.loads(self.recognizer.Result())
    #                 text = result.get("text", "")
    #                 print(result.get("text", ""))
    #                 if text:
    #                     self.update_label(text)
    #             else:
    #                 partial = json.loads(self.recognizer.PartialResult())
    #                 text = partial.get("partial", "")
    #                 print(partial.get("partial", ""))
    #                 if text:
    #                     self.update_label(text)
    #             audio_buffer = []
                
    def update_label(self, text):
        Clock.schedule_once(lambda dt: setattr(self.label, 'text', text))

    
    def refreshList(self, instance):
        conn = sqlite3.connect("simple.db")
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM simple_table")
        rows = cursor.fetchall()
        
        conn.close()
        
        combined_text = ""
        for row in rows:
            id_, text = row
            combined_text += f"{id_}: {text}\n"

        self.table_texts.text = combined_text
        


    def test_llama(self, instance):
        # Process the saved text with Llama in a separate thread
        if not self.saved_text.strip():
            self.label2.text = "No text to process."
            return

        def llama_task():
            output_text = self.process_with_llama(self.saved_text)
            json_result = json.dumps({
                "Input": self.saved_text,
                "Output": output_text
            }, indent=2)

            # --- Save into DB ---
            # self.cursor.execute(
            #     "INSERT INTO transcripts (input_text, output_text) VALUES (?, ?)",
            #     (self.saved_text, output_text)
            # )
            # self.conn.commit()


            Clock.schedule_once(lambda dt: setattr(self.label2, 'text', json_result))
            
        threading.Thread(target=llama_task, daemon=True).start()

    def process_with_llama(self, text):
        if not text.strip():
            return ""
        prediction = self.classifier.predict([text])
        print(prediction)
        prompt = "empty"
        predicted = prediction[0]
        if predicted == "patient observation":
            prompt = f"""
Extract patient statistics from the following observations and output as JSON:

Patient Observation:
\"\"\"{self.saved_text}\"\"\"

Output JSON format:
{{
  "heart_rate": "...",
  "blood_pressure": "...",
  "oxygen_saturation": "...",
  "respiratory_rate": "...",
  "temperature": "...",
  "other_notes": "..."
}}
"""
        elif predicted == "medication":
            prompt = f"""
Extract medication information from the following text and output it as JSON.

Medication Text:
\"\"\"{text}\"\"\"

Output JSON format:
{{
  "drug_name": "...",
  "dose": "...",
  "unit": "...",
  "route": "..."
}}
"""

        if predicted != "none":
            output = self.llama_model(prompt, max_new_tokens=256)
            print(output)
        # result = output.replace("\n", "").replace("\t", "").strip()
        # if result.lower().startswith("ignore"):
        #     return ""
        
        conn = sqlite3.connect("simple.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO simple_table (text) VALUES (?)",(predicted,))
        conn.commit()
        conn.close()
        return predicted


if __name__ == '__main__':
    AudioApp().run()
