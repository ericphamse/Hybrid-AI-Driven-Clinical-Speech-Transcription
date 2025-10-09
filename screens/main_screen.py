from kivy.uix.screenmanager import Screen
from kivy.lang import Builder

from widgets.top_bar import TopBar
# Import StructuringPanel
from widgets.transcription_panel import TranscriptionPanel
from widgets.structuring_panel import StructuringPanel
from widgets.database import LocalDatabase

# Load the TopBar, TranscriptionPanel, and StructuringPanel kv files
Builder.load_file('widgets/top_bar.kv')
Builder.load_file('widgets/transcription_panel.kv')
Builder.load_file('widgets/structuring_panel.kv')
class MainScreen(Screen):
    pass
