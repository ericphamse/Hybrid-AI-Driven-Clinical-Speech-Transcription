from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty
from kivy.app import App
import socket
import threading

class TopBar(BoxLayout):
    network_status = StringProperty('Checking...')
    clinician_name = StringProperty('')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.check_connection()

    def check_connection(self):
        def check():
            try:
                # Try to connect to a public DNS server
                socket.create_connection(("8.8.8.8", 53), timeout=2)
                self.network_status = 'Online'
            except Exception:
                self.network_status = 'Offline'
        threading.Thread(target=check, daemon=True).start()

    def logout(self):
        app = App.get_running_app()
        app.session_data = {'clinician_name': '', 'log_entries': []}
        app.save_session_to_json()
        app.root.current = 'login'

    def on_parent(self, widget, parent):
        app = App.get_running_app()
        self.clinician_name = app.session_data.get('clinician_name', '')
