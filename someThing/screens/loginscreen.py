from kivy.uix.screenmanager import Screen
from kivy.app import App

class LoginScreen(Screen):
    def start_session(self, clinician_name):
        if not clinician_name.strip():
            # Optionally, show an error message or handle invalid input
            return
        app = App.get_running_app()
        app.session_data['clinician_name'] = clinician_name
        app.save_session_to_json()
        self.manager.current = 'main'
        # Refresh clinician name in StructuringPanel
        main_screen = app.root.get_screen('main')
        struct_panel = main_screen.ids.structuring_panel
        struct_panel.load_clinician_name()
        struct_panel.update_log_display()
