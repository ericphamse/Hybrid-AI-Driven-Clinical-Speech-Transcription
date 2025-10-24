

import os
# from audioservice import AudioService
import json
import threading
import uuid
import requests
import time
import boto3
from datetime import datetime
from audioservice import AudioService
from text_to_num import alpha2digit
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import BooleanProperty
from kivy.app import App
from kivy.clock import Clock
from vosk import Model
# class TranscriptionPanel(BoxLayout):
#     audio_service = AudioService()
#     is_recording = BooleanProperty(False)
#     transcription_id = str(uuid.uuid4())
#     # Load Vosk model ONCE at startup (don't reload for every audio)
#     model_path = os.path.join("model", "vosk-model-small-en-us-0.15")  # Loads in the vosk model
#     if not os.path.exists(model_path):
#         raise FileNotFoundError("Vosk model not found at: " + model_path) # error raised in case something's wrong
#
#     model = Model(model_path) #Loads the model once 
    
class TranscriptionPanel(BoxLayout):
    # Add Kivy properties that your KV file expects
    audio_service = AudioService()
    is_recording = BooleanProperty(False)
    transcription_id = str(uuid.uuid4())
    CLAUDE_37_SONNET_ARN = (
    "arn:aws:bedrock:ap-southeast-2:581867121100:inference-profile/"
    "apac.anthropic.claude-3-7-sonnet-20250219-v1:0"
    )
    # Load Vosk model ONCE at startup (don't reload for every audio)
    model_path = os.path.join("model", "vosk-model-small-en-us-0.15")  # Loads in the vosk model
    backend_url = "http://localhost:5000"
    bucket_name = "ps2511-medical-buckets"
    key = os.path.join("datastore", "key.json")
    with open(key) as f:
        creds = json.load(f)
            
    aws_access_key = creds["AWS_ACCESS_KEY_ID"].strip()
    aws_secret_key = creds["AWS_SECRET_ACCESS_KEY"].strip()
    aws_region = creds.get("AWS_REGION", "ap-southeast-2")
    # Initialize AWS clients
    s3 = boto3.client(
                "s3",
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=aws_region,
                )

    transcribe = boto3.client(
                "transcribe",
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=aws_region,
                )
    bedrock = boto3.client(
        "bedrock-runtime",
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=aws_region
        )
    if not os.path.exists(model_path):
        raise FileNotFoundError("Vosk model not found at: " + model_path) # error raised in case something's wrong

    model = Model(model_path) #Loads the model once 

    def send_to_aws_pipeline(self, filename):
        """Send audio file through AWS pipeline: S3 -> Transcribe -> Medical"""
        try:
            print(f"📤 Sending {filename} to AWS pipeline...")
            
            # Check file size
            file_size = os.path.getsize(filename)
            print(f"📊 File size: {file_size / 1024 / 1024:.2f} MB")
            
            # AWS Transcribe has file size limits (500MB for medical)
            # if file_size > 400 * 1024 * 1024:  # 400MB limit for safety
            #     raise Exception(f"File too large ({file_size / 1024 / 1024:.2f} MB). Max 400MB.")
            
            # Method 1: Use your backend if it's running
            if self.send_via_backend(filename):
                return
            
            # Method 2: Direct AWS integration
            self.send_direct_to_aws(filename)
            
        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            print(error_msg)
            Clock.schedule_once(lambda dt: self.update_transcription_display(error_msg))

        finally:
            # Clean up the file
            try:
                if os.path.exists(filename):
                    os.remove(filename)
                    print(f"🗑️ Cleaned up {filename}")
            except Exception as e:
                print(f"⚠️ Error cleaning up file: {e}")
                
    def send_via_backend(self, filename):
        """Try to send via your Flask backend first"""
        try:
            # Check if backend is running
            response = requests.get(f"{self.backend_url}/", timeout=2)
            
            # Send file to backend with timeout based on file size
            file_size_mb = os.path.getsize(filename) / 1024 / 1024
            timeout = max(300, int(file_size_mb * 10))  # 10 seconds per MB, min 5 minutes
            
            print(f"📤 Sending {file_size_mb:.2f}MB file with {timeout}s timeout...")
            
            with open(filename, 'rb') as audio_file:
                files = {'file': (filename, audio_file, 'audio/wav')}
                response = requests.post(
                    f"{self.backend_url}/transcribe",
                    files=files,
                    timeout=timeout
                )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    raw_transcript = result.get('transcript', '')
                    print(f"✅ Backend success: {raw_transcript[:100]}...")
                    
                    # Update UI with result
                    Clock.schedule_once(
                        lambda dt: self.update_transcription_display(raw_transcript)
                    )
                    return True
            else:
                print(f"❌ Backend HTTP error: {response.status_code}")
                return False
                    
        except requests.exceptions.Timeout:
            print(f"⏰ Backend request timed out (file too large or slow processing)")
            return False
        except Exception as e:
            print(f"⚠️ Backend not available: {e}")
            return False
    
    def send_direct_to_aws(self, filename):
        """Send directly to AWS if backend is not available"""
        try:
            print("🔄 Using direct AWS integration...")
            

            
            # 1. Upload to S3 uploads folder
            timestamp = int(time.time())
            s3_key = f"uploads/{timestamp}.wav"
            
            self.s3.upload_file(filename, self.bucket_name, s3_key)
            print(f"☁️ Uploaded to S3: {s3_key}")
            
            # 2. Start AWS Transcribe Medical job
            job_name = f"medical-job-{timestamp}"
            job_uri = f"s3://{self.bucket_name}/{s3_key}"
            
            self.transcribe.start_medical_transcription_job(
                MedicalTranscriptionJobName=job_name,
                Media={"MediaFileUri": job_uri},
                MediaFormat="wav",
                LanguageCode="en-US",
                Specialty="PRIMARYCARE",
                Type="CONVERSATION",
                OutputBucketName=self.bucket_name
            )
            
            print(f"🏥 Started medical transcription job: {job_name}")
            
            # 3. Wait for completion and get result
            self.wait_for_transcription_result(job_name, self.transcribe)
            
        except Exception as e:
            print(f"❌ Direct AWS error: {e}")
            raise
    
    def wait_for_transcription_result(self, job_name, transcribe_client):
        """Wait for transcription job to complete and get result"""
        try:
            print("⏳ Waiting for AWS Transcribe to complete...")
            
            while True:
                status = transcribe_client.get_medical_transcription_job(
                    MedicalTranscriptionJobName=job_name
                )
                job_status = status["MedicalTranscriptionJob"]["TranscriptionJobStatus"]
                print(f"📊 Job status: {job_status}")
                
                if job_status == "COMPLETED":
                    # Get transcript from S3 medical folder
                    transcript_uri = status["MedicalTranscriptionJob"]["Transcript"]["TranscriptFileUri"]
                    self.get_transcript_from_s3(transcript_uri)
                    break
                elif job_status == "FAILED":
                    raise Exception("Transcription job failed")
                
                time.sleep(5)
                
        except Exception as e:
            print(f"❌ Error waiting for transcription: {e}")
            raise
    
    def get_transcript_from_s3(self, transcript_uri):
        """Get transcript from S3 medical folder"""
        try:
            # Parse S3 URI to get bucket and key
            import urllib.parse
            parsed = urllib.parse.urlparse(transcript_uri)
            s3_key = parsed.path.lstrip("/")
            
            # Remove bucket name from key if present
            if s3_key.startswith(f"{self.bucket_name}/"):
                s3_key = s3_key[len(f"{self.bucket_name}/"):]
            
            print(f"📥 Getting transcript from S3: {s3_key}")
            
            # Download transcript JSON
            response = self.s3.get_object(Bucket=self.bucket_name, Key=s3_key)
            content = response["Body"].read().decode("utf-8")
            transcript_data = json.loads(content)
            
            # Extract raw transcript text
            raw_transcript = transcript_data["results"]["transcripts"][0]["transcript"]
            print(f"📝 Raw transcript: {raw_transcript}")
            
            # Update UI
            Clock.schedule_once(
                lambda dt: self.update_transcription_display(raw_transcript)
            )
            
        except Exception as e:
            print(f"❌ Error getting transcript from S3: {e}")
            raise
    def update_transcription_display(self, text):
        """Update the transcription text display"""
        try:
            print(f"📝 Updating UI with: {text[:100]}...")
            print(f"🔍 Widget has ids: {hasattr(self, 'ids')}")
            print(f"🔍 Available IDs: {list(self.ids.keys()) if hasattr(self, 'ids') else 'None'}")
            
            # Try to update by ID
            if hasattr(self.ids, 'transcription_text'):
                print(f"✅ Found transcription_text widget!")
                old_text = self.ids.transcription_text.text
                self.ids.transcription_text.text = text
                new_text = self.ids.transcription_text.text
                print(f"📝 Changed from: '{old_text[:50]}...' to: '{new_text[:50]}...'")
                print(f"✅ Updated transcription display")
                return
            else:
                print(f"❌ transcription_text widget not found in IDs")
            
            # Fallback search - with more debugging
            print(f"🔍 Starting widget tree search...")
            def find_text_widget(widget, depth=0):
                indent = "  " * depth
                widget_type = type(widget).__name__
                print(f"{indent}{widget_type}")
                
                if hasattr(widget, 'text'):
                    current_text = str(widget.text)
                    print(f"{indent}  Has text: '{current_text[:30]}...'")
                    
                    if ('Your transcribed text will appear here' in current_text or 
                        'transcribed text will appear' in current_text or
                        '🎤 Processing' in current_text):
                        print(f"{indent}  ✅ FOUND TARGET WIDGET!")
                        return widget
                
                # Check children
                if hasattr(widget, 'children'):
                    print(f"{indent}  Children: {len(widget.children)}")
                    for i, child in enumerate(widget.children):
                        print(f"{indent}  Child {i}:")
                        result = find_text_widget(child, depth + 1)
                        if result:
                            return result
                return None
            
            text_widget = find_text_widget(self)
            if text_widget:
                old_text = text_widget.text
                text_widget.text = text
                print(f"✅ Updated via search: '{old_text[:30]}...' -> '{text[:30]}...'")
            else:
                print("❌ Could not find any text widget to update")
                
        except Exception as e:
            print(f"❌ Error updating display: {e}")
            import traceback
            traceback.print_exc()
    
    
    
    
    def record_action(self):
        self.is_recording = not self.is_recording
        main_screen = App.get_running_app().root.get_screen('main')
        top_bar = main_screen.ids.top_bar
        struct_panel = main_screen.ids.structuring_panel
        if self.is_recording:
            self.ids.transcription_text.text = '' #Makes it so that it removes the previous transcribed text
            self.audio_service.start_recording() # Runs a function that starts recording
        else:
            wav_path = self.audio_service.stop_recording()
            # Use workflow_mode from top_bar
            if top_bar.workflow_mode == 'offline':
                def set_text(dt):
                    # Call the resampling to convert 48k Audio into 16k Audio, which is fed into vosk since it only accepts that.
                    processed_wav_path = self.audio_service.denoise_file(wav_path)
                    transcription = self.audio_service.transcribe_audio(self.model,self.audio_service.resample_to_16k(processed_wav_path))
                    print(transcription)
                    self.ids.transcription_text.text = alpha2digit(transcription, "en")
                Clock.schedule_once(set_text, 0)
            else:
                threading.Thread(target=self.send_to_aws_pipeline, args=(wav_path,), daemon=True).start()

    def generate_report_action(self):
        text_input = self.ids.transcription_text
        text = text_input.text
        time_string = datetime.now().isoformat(timespec='seconds')
        # Only generate report if text is not empty
        if text.strip():
            # Load structured data and update display
            main_screen = App.get_running_app().root.get_screen('main')
            struct_panel = main_screen.ids.structuring_panel
            top_bar = main_screen.ids.top_bar
            if top_bar.workflow_mode == 'offline':
                def task():
                    # Run heavy function off the main thread
                    result = struct_panel.generate_json(text, self.transcription_id, time_string)        
                    Clock.schedule_once(lambda dt: struct_panel.load_json_data())
                    Clock.schedule_once(lambda dt: struct_panel.update_log_display())
                threading.Thread(target=task, daemon=True).start()
            else:
                def task2():
                    result = struct_panel.format_with_claude(self.bedrock, self.CLAUDE_37_SONNET_ARN,text, self.transcription_id, time_string)
                    Clock.schedule_once(lambda dt: struct_panel.load_json_data())
                    Clock.schedule_once(lambda dt: struct_panel.update_log_display())
                threading.Thread(target=task2, daemon=True).start()
        text_input.text = ''
        deleteAllRecordings()
def deleteAllRecordings():
    # Build the full path safely
    print("Waiting 3 seconds before deleting recordings...")
    time.sleep(3)
    base_dir = "datastore"
    target_folder = os.path.join(base_dir, "raw_recordings")
    # Loop through every item in raw folder
    
    for filename in os.listdir(target_folder):
        file_path = os.path.join(target_folder, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)
            
    target_folder = os.path.join(base_dir, "processed_recordings")
    for filename in os.listdir(target_folder):
        file_path = os.path.join(target_folder, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)