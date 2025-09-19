
import json
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty, ListProperty, NumericProperty
from kivy.app import App
import os

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

    def load_json_data(self):
        # Only load if explicitly requested (by Generate button)
        json_path = os.path.join('datastore', 'sampledata.json')
        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                data = json.load(f)
            med_struct = data.get('medicalNoteStructure', {})
            self.progress_notes = med_struct.get('progressNote', [])
            self.patient_observations = med_struct.get('patientObservations', [])
            self.medications = med_struct.get('medicationAdministered', [])
        else:
            self.progress_notes = []
            self.patient_observations = []
            self.medications = []

    def load_clinician_name(self):
        app = App.get_running_app()
        self.clinician_name = app.session_data.get('clinician_name', '')

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
                    other_observations=entry.get('otherObservations', '')
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
