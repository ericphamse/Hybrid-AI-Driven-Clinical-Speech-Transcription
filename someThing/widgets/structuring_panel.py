
import json
from pydantic import BaseModel, Field
import outlines
from widgets.database import LocalDatabase
from datetime import datetime
from llama_cpp import Llama
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty, ListProperty, NumericProperty
from kivy.app import App
import os
from Demos.print_desktop import pname

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
    def generate_json(self, text, tids, globalTime):
        from pydantic import BaseModel, Field
        import outlines
        import torch
        import json
        from llama_cpp import Llama
        from llama_cpp import llama_tokenizer
        from typing import List, Optional
        from pydantic import BaseModel
        # Load HF tokenizer for the model repo
        hf_tokenizer = llama_tokenizer.LlamaHFTokenizer.from_pretrained("Qwen/Qwen2.5-1.5B-Instruct")

        # Pass it to Outlines
        model = outlines.models.llamacpp(
            # repo_id="MaziyarPanahi/Qwen2.5-1.5B-Instruct-GGUF",
            repo_id="MaziyarPanahi/Qwen2.5-1.5B-Instruct-GGUF",
            filename="Qwen2.5-1.5B-Instruct.Q8_0.gguf",
            threads=8,
            tokenizer=hf_tokenizer
            )

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
            quantity: Optional[int] = Field(
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

        generator = outlines.generate.json(model, MedicalNoteStructure)
        output = generator(prompt)
        time_string = datetime.now().isoformat(timespec='seconds')
        try:
            print(json.dumps(output.model_dump(), indent=2))
            print("\nModel just ran")
        except json.JSONDecodeError:
            print("Model did not return valid JSON:")
            print(output)
        #Structure the JSON to fit (kill me)
        
        #PatientObservation (whoever came up with the all in one string, count your days.)
        
        dumped = output.model_dump()
        wholeString = ""
        if dumped["patientObservations"]["bloodPressure"] is not None:
            wholeString += "BP: " + dumped["patientObservations"]["bloodPressure"] + ", "
        if dumped["patientObservations"]["oxygenLevel"] is not None:
            wholeString += "O2: " + dumped["patientObservations"]["oxygenLevel"] + ", "
        if dumped["patientObservations"]["heartBeat"] is not None:
            wholeString += "BPM: " + dumped["patientObservations"]["heartBeat"] + ", "
        if dumped["patientObservations"]["temperature"] is not None:
            wholeString += "Celsius: " + dumped["patientObservations"]["temperature"]
        #Combine into patientObservation
        po = {}
        po["transcriptionId"] = tids
        po["timestamp"] = time_string
        po["otherObservations"] = wholeString
        
        #Combine into medicationAdministered
        wholeString = str(dumped["medicationAdministered"]["quantity"])
        if dumped["medicationAdministered"]["unit"] is not None:
            wholeString += dumped["medicationAdministered"]["unit"]
        ma = {}
        ma["transcriptionId"] = tids
        ma["timestamp"] = time_string
        ma["medicineType"] = dumped["medicationAdministered"]["medicineType"]
        ma["quantity"] = wholeString
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
                med_info = f"{entry.get('medicineType', '')} - {entry.get('medicineName', '')} ({entry.get('quantity', '')}), {entry.get('administrationType', '')}"
                widget = ReportEntry(
                    timestamp_str=entry.get('timestamp', ''),
                    medication_info=med_info
                )
                self.ids.report_log.add_widget(widget)

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
