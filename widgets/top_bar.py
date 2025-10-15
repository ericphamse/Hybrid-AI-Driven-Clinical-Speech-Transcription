from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty
from kivy.properties import BooleanProperty
from kivy.app import App
import socket
import threading
from kivy.clock import Clock
import sqlite3
import boto3
from botocore.exceptions import ClientError
import os
class TopBar(BoxLayout):
    network_status = BooleanProperty(False)
    previous_network = False
    clinician_name = StringProperty('')
    dynamodb = boto3.resource('dynamodb', region_name ="ap-southeast-2")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.check_connection()
        # Schedule periodic rechecks every 3 seconds
        Clock.schedule_interval(self.periodic_check, 3)

    def periodic_check(self, dt):
        self.check_connection()
    def check_connection(self):

        def check():
            try:
                # Try to connect to a public DNS server
                socket.create_connection(("8.8.8.8", 53), timeout=2)
                self.previous_network = self.network_status
                self.network_status = True
                # if self.previous_network == False:
                #     if os.path.exists("clinical_transcription.db"):
                #         # run sync
                #         conn = sqlite3.connect('clinical_transcription.db')
                #         cursor = conn.cursor()
                #
                #         cursor.execute("SELECT * FROM transcription_session")
                #         ts = cursor.fetchall()
                #         cursor.execute("SELECT * FROM progress_note")
                #         pn = cursor.fetchall()
                #         cursor.execute("SELECT * FROM patient_observation")
                #         po = cursor.fetchall()
                #         cursor.execute("SELECT * FROM medication_administered")
                #         ma = cursor.fetchall()
                #
                #         for row in ts:
                #             tID, session, raw, on, off, created_at = row
                #     else:
                #         print("offline.db not found — skipping sync")
            except Exception:
                self.network_status = False

        threading.Thread(target=check, daemon=True).start()

    def logout(self):
        app = App.get_running_app()
        app.session_data = {'clinician_name': '', 'log_entries': []}
        app.save_session_to_json()
        app.root.current = 'login'

    def on_parent(self, widget, parent):
        app = App.get_running_app()
        self.clinician_name = app.session_data.get('clinician_name', '')
