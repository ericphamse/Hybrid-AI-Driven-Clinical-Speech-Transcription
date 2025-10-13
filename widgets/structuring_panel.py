from outlines import models
import outlines
from typing import Optional
import json
import os
from kivy.clock import Clock
from pydantic import BaseModel, Field
from widgets.database import LocalDatabase
from datetime import datetime
from llama_cpp import Llama
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty, ListProperty, NumericProperty
from kivy.app import App

class ReportEntry(BoxLayout):
    timestamp_str = StringProperty()
    context = StringProperty()
    other_observations = StringProperty()
    medication_info = StringProperty()

class StructuringPanel(BoxLayout):
    def confirm_delete(self):
        from kivy.uix.popup import Popup
        from kivy.uix.label import Label
        from kivy.uix.button import Button
        from kivy.uix.boxlayout import BoxLayout

        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        label = Label(text='Are you sure you want to delete all structured report data?',
                     text_size=(360, None),
                     halign='center',
                     valign='middle')
        content.add_widget(label)
        btn_layout = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=None, height=40)
        btn_yes = Button(text='Yes', background_color=(1,0.2,0.2,1))
        btn_no = Button(text='No', background_color=(0.2,0.6,0.2,1))
        btn_layout.add_widget(btn_yes)
        btn_layout.add_widget(btn_no)
        content.add_widget(btn_layout)
        popup = Popup(title='Confirm Delete', content=content, size_hint=(None, None), size=(400, 200), auto_dismiss=False)
        def on_yes(instance):
            popup.dismiss()
            self.clear_report()
        def on_no(instance):
            popup.dismiss()
        btn_yes.bind(on_release=on_yes)
        btn_no.bind(on_release=on_no)
        popup.open()
    tab_index = NumericProperty(0)  # 0: Progress Note, 1: Patient Observation, 2: Medication
    progress_notes = ListProperty([])
    patient_observations = ListProperty([])
    medications = ListProperty([])
    clinician_name = StringProperty('')

    def format_with_claude(self, bedrock, ai, transcript_text, tids, globalTime):
        prompt = f"""
    You are a medical assistant AI. Take the raw transcript and convert it into JSON
    following this schema exactly.

    Rules:
    - Extract only real values from the transcript.
    - If information is missing, set the field to null or "".
    - Do not add examples or placeholders.
    - Return only valid JSON, nothing else.

    Schema:
    {{
        "medicalNoteStructure": {{
            "progressNote": [
                {{
                    "otherObservations": {transcript_text}
                }}
            ],
            "patientObservations": [
                {{
                    "bloodPressure": ,
                    "oxygenLevel": ,
                    "heartBeat": ,
                    "temperature":
                }}
            ],
            "medicationAdministered": [
                {{
                    "medicineType": ,
                    "quantity": ,
                    "unit": ,
                    "administrationType":
                }}
            ]
        }}
    }}

    Raw transcript:
    {transcript_text}
    """

        response = bedrock.invoke_model(
            modelId=ai,
            accept="application/json",
            contentType="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "temperature": 0,
                "messages": [
                {"role": "user", "content": prompt}
            ]
        })
    )

        raw_output = response["body"].read().decode("utf-8")
        result = json.loads(raw_output)
        structured_text = result["content"][0]["text"].strip()
        if structured_text.startswith("```"):
            structured_text = structured_text.replace("```json", "").replace("```", "").strip()
        result = json.loads(structured_text)
        print(result)
        time_string = datetime.now().isoformat(timespec='seconds')
        bp = result["medicalNoteStructure"]["patientObservations"][0]["bloodPressure"]
        o2 = result["medicalNoteStructure"]["patientObservations"][0]["oxygenLevel"]
        bpm = result["medicalNoteStructure"]["patientObservations"][0]["heartBeat"]
        temp = result["medicalNoteStructure"]["patientObservations"][0]["temperature"]
        wholeString = ''
        if bp is not None:
            wholeString += f"BP: {bp}"
        if o2 is not None:
            if not wholeString:
                wholeString += f"O2: {o2}"
            else:
                wholeString += f"\nO2: {o2}"
        if bpm is not None:
            if not wholeString:
                wholeString += f"BPM: {str(bpm)}\n"
            else:
                wholeString += f"\nBPM: {str(bpm)}\n"
        if temp is not None:
            if not wholeString:
                wholeString += f"Celsius: {str(temp)}"
            else:
                wholeString += f"\nCelsius: {str(temp)}"
        
        if wholeString is not None:
            po = {}
            po["transcriptionId"] = tids
            po["timestamp"] = time_string
            po["otherObservations"] = wholeString
        
        #Combine into medicationAdministered
        wholeString = str(result["medicalNoteStructure"]["medicationAdministered"][0]["quantity"])
        if result["medicalNoteStructure"]["medicationAdministered"][0]["unit"] is not None:
            wholeString += result["medicalNoteStructure"]["medicationAdministered"][0]["unit"]
        ma = {}
        ma["transcriptionId"] = tids
        ma["timestamp"] = time_string
        ma["medicineType"] = result["medicalNoteStructure"]["medicationAdministered"][0]["medicineType"]
        ma["quantity"] = str(result["medicalNoteStructure"]["medicationAdministered"][0]["quantity"])
        ma["unit"] = result["medicalNoteStructure"]["medicationAdministered"][0]["unit"]
        ma["administrationType"] = result["medicalNoteStructure"]["medicationAdministered"][0]["administrationType"]
        
        self.load_clinician_name()
        #Combine generic info
        pn = {}
        pn["transcriptionId"] = tids
        pn["timestamp"] = time_string
        pn["context"] = transcript_text
        pn["peopleInvolved"] = self.clinician_name
        
        
        allData = {}
        allData["transcriptionId"] = tids
        allData["userId"] = "test"
        allData["timestamp"] = globalTime
        allData["rawTranscriptionId"] = "WhatsThisFor?"
        allData["isOnline"] = False
        allData["isOffline"] = True
        allData["medicalNoteStructure"] = {}
        allData["medicalNoteStructure"]["progressNote"] = pn
        allData["medicalNoteStructure"]["patientObservation"] = po
        allData["medicalNoteStructure"]["medicationAdministered"] = ma
        db = LocalDatabase
        db.save_transcription_session(tids, allData)
        
        #then you convert the entire db into the json. (God had left my soul)
        db.get_session_details(tids)

        
        # try:
        #     return json.loads(structured_text)
        # except json.JSONDecodeError:
        #     return {"error": "invalid_json", "raw_text": structured_text}
    def generate_json(self, text, tids, globalTime):

        # Load HF tokenizer for the model repo
        model_path = os.path.join('model', 'Qwen2.5-1.5B-Instruct.Q8_0.gguf')
        # Pass it to Outlines
        llm = Llama(
            model_path,
            n_ctx=8192,
            n_threads=8,
            temperature=0.0,     # <-- crucial for factual tasks
            top_p=0.9)
        model = models.LlamaCpp(llm)

        # constrained decoding:
        class PatientObservation(BaseModel):
            bloodPressure: Optional[str] = Field(
                None, 
                description="Record the patient's blood pressure as a string in the format 'systolic/diastolic', e.g., '120/80'. Leave empty if not mentioned."
                )
            oxygenLevel: Optional[str] = Field(
                None, 
                description="Record the patient's oxygen saturation percentage as a number, e.g., 95. Leave empty if not mentioned."
                )
            heartBeat: Optional[int] = Field(
                None, 
                description="Record the patient's heart rate in beats per minute (bpm) as an integer, e.g., 90. Leave empty if not mentioned."
                )
            temperature: Optional[float] = Field(
                None, 
                description="Record the patient's body temperature in Celsius as a number, e.g., 37.5. Leave empty if not mentioned."
                )

        class MedicationAdministered(BaseModel):
            medicineType: Optional[str] = Field(
                None, 
                description="Record the exact name of the medication administered. Leave empty if no medication is mentioned."
                )
            quantity: Optional[float] = Field(
                None, 
                description="Record the quantity of the medication administered as a number. Leave empty if not mentioned."
                )
            unit: Optional[str] = Field(
                None, 
                description="Record the unit of the medication quantity, e.g., 'mg', 'ml', 'tablets'. Leave empty if not mentioned."
                )
            administrationType: Optional[str] = Field(
                None,
                description="Record the method of administration for the medication, e.g., 'oral', 'intravenous', 'subcutaneous'. Leave empty if not mentioned."
                )

        class MedicalNoteStructure(BaseModel):
            patientObservations: PatientObservation = Field(
                ..., 
                description="Structured observation data for the patient. Fill in only what is explicitly mentioned in the text."
                )
            medicationAdministered: MedicationAdministered = Field(
                ..., 
                description="Structured data for medications given. Fill in only what is explicitly mentioned in the text."
                )
    
        schema_json_str = json.dumps(MedicalNoteStructure.model_json_schema())
        
        # Example transcript
        prompt = f"""
    You are a medical assistant AI. Extract only the following patient data from the text:
    - bloodPressure (format "systolic/diastolic", leave empty if missing)
    - heartBeat (integer bpm, leave empty if missing)
    - oxygenLevel (percentage, leave empty if missing)
    - temperature (Celsius, leave empty if missing)
    - medicationType, quantity, unit (if mentioned)
    
    Output MUST be a valid JSON following this schema:
    {schema_json_str}
    
    
    Text to process:
    "{text}"
    """
        
#Patient is going into shock. Heart rate spiking up to 90. And blood pressure is 130 over 90. Oxygen level is around 35% and temperature of 46 celsius. Administering 30 mg of pain killers to patient.
    # Llama-cpp Part.

        generator = outlines.Generator(model, MedicalNoteStructure)
        result = generator(prompt, max_tokens=2048)
        print(result)
        time_string = datetime.now().isoformat(timespec='seconds')
        output = MedicalNoteStructure.model_validate_json(result)

        try:
            print(json.dumps(output.model_dump(), indent=2))
            print("\nModel just ran")
            print("raw text: ", text)
        except json.JSONDecodeError:
            print("Model did not return valid JSON:")
            print(output)
        #Structure the JSON to fit (kill me)
        
        #PatientObservation (whoever came up with the all in one string, count your days.)
        
        
        obs = output.patientObservations
        med = output.medicationAdministered
        bp_for_check = bp_to_over_formatting(obs.bloodPressure)  # convert to "over" format temporarily
            
        # Post data filtering
        # Patient observation fields
        if obs.bloodPressure and not value_mentioned_in_text(bp_for_check, text):
            obs.bloodPressure = None
            print("BP not mentioned in text, leaving null instead.")
        if obs.heartBeat and not value_mentioned_in_text(obs.heartBeat, text):
            obs.heartBeat = None
            print("heartrate not mentioned in text, leaving null instead.")
        if obs.oxygenLevel and not value_mentioned_in_text(obs.oxygenLevel, text):
            obs.oxygenLevel = None
            print("O2% not mentioned in text, leaving null instead.")
        if obs.temperature and not value_mentioned_in_text(obs.temperature, text):
            obs.temperature = None
            print("C* not mentioned in text, leaving null instead.")

        # Medication fields
        if med.medicineType and not value_mentioned_in_text(med.medicineType, text):
            med.medicineType = None
            print("medicine not mentioned in text, leaving null instead.")
        if med.quantity and not value_mentioned_in_text(med.quantity, text):
            med.quantity = None
            print("quantity not mentioned in text, leaving null instead.")
        if med.unit and not value_mentioned_in_text(med.unit, text):
            med.unit = None
            print("units not mentioned in text, leaving null instead.")
        if med.administrationType and not value_mentioned_in_text(med.administrationType, text):
            med.administrationType = "Not mentioned"
            print("""administration type not mentioned in text, leaving "not mentioned" instead.""")
        
            #Finally the string
        dumped = output.model_dump()
        wholeString = ""
        bp = dumped["patientObservations"]["bloodPressure"]
        o2 = dumped["patientObservations"]["oxygenLevel"]
        bpm = dumped["patientObservations"]["heartBeat"]
        temp = dumped["patientObservations"]["temperature"]

        if dumped["patientObservations"]["bloodPressure"] is not None:
            wholeString += f"BP: {bp}"
        if dumped["patientObservations"]["oxygenLevel"] is not None:
            if not wholeString:
                wholeString += f"O2: {o2}"
            else:
                wholeString += f"\nO2: {o2}"
        if dumped["patientObservations"]["heartBeat"] is not None:
            if not wholeString:
                wholeString += f"BPM: {str(bpm)}\n"
            else:
                wholeString += f"\nBPM: {str(bpm)}\n"
        if dumped["patientObservations"]["temperature"] is not None:
            if not wholeString:
                wholeString += f"Celsius: {str(temp)}"
            else:
                wholeString += f"\nCelsius: {str(temp)}"
        #Combine into patientObservation
        po = {}
        po["transcriptionId"] = tids
        po["timestamp"] = time_string
        po["otherObservations"] = wholeString
        
        #Combine into medicationAdministered
        ma = {}
        ma["transcriptionId"] = tids
        ma["timestamp"] = time_string
        ma["medicineType"] = dumped["medicationAdministered"]["medicineType"]
        ma["quantity"] = dumped["medicationAdministered"]["quantity"]
        ma["unit"] = dumped["medicationAdministered"]["unit"]
        ma["administrationType"] = dumped["medicationAdministered"]["administrationType"]
        
        self.load_clinician_name()
        #Combine generic info
        pn = {}
        pn["transcriptionId"] = tids
        pn["timestamp"] = time_string
        pn["context"] = text
        pn["peopleInvolved"] = self.clinician_name
        
        
        allData = {}
        allData["transcriptionId"] = tids
        allData["userId"] = "test"
        allData["timestamp"] = globalTime
        allData["rawTranscriptionId"] = "WhatsThisFor?"
        allData["isOnline"] = False
        allData["isOffline"] = True
        allData["medicalNoteStructure"] = {}
        allData["medicalNoteStructure"]["progressNote"] = pn
        allData["medicalNoteStructure"]["patientObservation"] = po
        allData["medicalNoteStructure"]["medicationAdministered"] = ma
        db = LocalDatabase
        db.save_transcription_session(tids, allData)
        
        #then you convert the entire db into the json. (God had left my soul)
        db.get_session_details(tids)
        
    def load_json_data(self):
        # Only load if explicitly requested (by Generate button)
        json_path = os.path.join('datastore', 'data.json')
        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                data = json.load(f)
            med_struct = data.get('medicalNoteStructure', {})
            self.progress_notes = med_struct.get('progressNote', [])
            self.patient_observations = med_struct.get('patientObservation', [])
            self.medications = med_struct.get('medicationAdministered', [])
        else:
            self.progress_notes = []
            self.patient_observations = []
            self.medications = []

    def load_clinician_name(self):
        app = App.get_running_app()
        self.clinician_name = app.session_data.get('clinician_name', '')
    def prints(self):
        LocalDatabase.printPath()
    def update_log_display(self):
        self.ids.report_log.clear_widgets()
        if self.tab_index == 0:
            for entry in self.progress_notes:
                widget = ReportEntry(
                    timestamp_str=entry.get('timestamp', ''),
                    context=entry.get('context', '')
                )
                self.ids.report_log.add_widget(widget)
        elif self.tab_index == 1:
            for entry in self.patient_observations:
                widget = ReportEntry(
                    timestamp_str=entry.get('timestamp', ''),
                    other_observations=entry.get('ObservationNote', '')
                )
                self.ids.report_log.add_widget(widget)
        elif self.tab_index == 2:
            for entry in self.medications:
                med_info = (
                    f"Name: {entry.get('medicineType', '')}\n"
                    f"Quantity: {entry.get('quantity', '')}\n"
                    f"Unit: {entry.get('unit', '')}\n"
                    f"Administration: {entry.get('administrationType', '')}"
                    )
                widget = ReportEntry(
                    timestamp_str=entry.get('timestamp', ''),
                    medication_info=med_info
                )
                self.ids.report_log.add_widget(widget)
                
    def send_to_aws(self):
        # """Stop recording and send to AWS pipeline with better cleanup"""
        # try:
        #     self.is_recording = False
        #
        #     # Wait for recording thread to finish
        #     if self.recording_thread and self.recording_thread.is_alive():
        #         self.recording_thread.join(timeout=2)
        #
        #     self.cleanup_audio()
        #
        #     if not self.audio_data:
        #         print("⚠️ No audio data recorded")
        #         return
        #
        #     duration = time.time() - self.recording_start_time if self.recording_start_time else 0
        #     print(f"🎵 Recorded {len(self.audio_data)} chunks ({duration:.1f}s)")
        #
        #     # Save audio to file with better memory handling
        #     timestamp = int(time.time())
        #     filename = f"recording_{timestamp}.wav"
        #
        #     self.save_audio_to_file(filename)
        #
        #     print(f"💾 Audio saved to {filename}")
            
            # Show processing message
        Clock.schedule_once(
            # lambda dt: self.update_transcription_display("🎤 Processing with AWS... Please wait...")
        )
            
        # Send to AWS in background thread
        # threading.Thread(target=self.send_to_aws_pipeline, args=(filename,), daemon=True).start()
            
        # except Exception as e:
        #     print(f"❌ Error stopping recording: {e}")
        #     self.cleanup_audio()
                
                

    
    def generate_report_action(self):
        """Handle generate report button press"""
        print("📊 Generate report requested")
        
        try:
            if hasattr(self.ids, 'transcription_text'):
                text_content = self.ids.transcription_text.text
                if text_content and text_content != "Your transcribed text will appear here...":
                    print(f"📋 Processing report for: {text_content[:100]}...")
                    # Here you can add Claude processing for structured data
                else:
                    print("⚠️ No transcript text to process")
            else:
                print("⚠️ No transcription_text widget found")
                
        except Exception as e:
            print(f"❌ Error in generate_report_action: {e}")
    

                
                
                
                
                
                
                
                
                
                
    def switch_tab(self, idx):
        self.tab_index = idx
        self.update_log_display()

    def on_kv_post(self, base_widget):
        self.progress_notes = []
        self.patient_observations = []
        self.medications = []
        self.load_clinician_name()
        self.update_log_display()
    def clear_report(self):
        self.progress_notes = []
        self.patient_observations = []
        self.medications = []
        self.update_log_display()

    def on_parent(self, widget, parent):
        self.load_clinician_name()


def value_mentioned_in_text(value, text):
    if value is None:
        return False
    
    # Convert everything to lowercase string for comparison
    value_str = str(value).lower()
    text_lower = text.lower()

    # Simple substring check
    if isinstance(value, float) and value.is_integer():
        value_str = str(int(value))
        
    return value_str in text_lower
def bp_to_over_formatting(bp_str):
    parts = bp_str.split('/')
    if len(parts) == 2:
        first = parts[0].strip()
        second = parts[1].strip()
        return f"{first} over {second}"
    return None