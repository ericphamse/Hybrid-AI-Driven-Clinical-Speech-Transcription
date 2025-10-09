from kivy.uix.boxlayout import BoxLayout
from kivy.properties import BooleanProperty
from kivy.clock import Clock
from kivy.app import App
import os
import requests
import json
import boto3
import threading
import time
import wave
import pyaudio
import numpy as np
import io

class TranscriptionPanel(BoxLayout):
    is_recording = BooleanProperty(False)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.backend_url = "http://localhost:5000"
        self.bucket_name = "ps2511-medical-buckets"
        self.recording_thread = None
        self.audio_data = []
        self.p = None
        self.stream = None
        self.max_recording_time = 300  # 5 minutes max
        self.recording_start_time = None
        print(f"🎤 TranscriptionPanel initialized with AWS integration")
    
    def record_action(self):
        """Handle record button press - record and send to AWS"""
        if self.is_recording:
            print("🛑 Stopping recording and sending to AWS...")
            self.stop_recording_and_send_to_aws()
        else:
            print("🎤 Starting recording...") 
            self.start_recording()
    
    def start_recording(self):
        """Start audio recording with better error handling"""
        try:
            self.is_recording = True
            self.audio_data = []
            self.recording_start_time = time.time()
            
            # Initialize PyAudio with better settings
            self.p = pyaudio.PyAudio()
            
            # Use smaller buffer for better real-time performance
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=512,  # Smaller buffer
                input_device_index=None,
                stream_callback=None
            )
            
            # Start recording in a separate thread
            self.recording_thread = threading.Thread(target=self._record_audio, daemon=True)
            self.recording_thread.start()
            
            print("✅ Recording started")
            
        except Exception as e:
            print(f"❌ Error starting recording: {e}")
            self.is_recording = False
            self.cleanup_audio()
    
    def _record_audio(self):
        """Record audio data with memory management"""
        try:
            chunk_count = 0
            while self.is_recording:
                # Check max recording time
                if time.time() - self.recording_start_time > self.max_recording_time:
                    print(f"⏰ Max recording time ({self.max_recording_time}s) reached, stopping...")
                    self.is_recording = False
                    break
                
                try:
                    # Read audio data with exception handling
                    data = self.stream.read(512, exception_on_overflow=False)
                    self.audio_data.append(data)
                    
                    chunk_count += 1
                    
                    # Memory management: limit chunks to prevent memory overflow
                    # For 16kHz, 512 samples = ~32ms per chunk
                    # 5 minutes = ~9375 chunks, so limit to 10000 chunks
                    if chunk_count > 10000:
                        print("⚠️ Recording too long, auto-stopping to prevent memory issues...")
                        self.is_recording = False
                        break
                        
                    # Optional: Print progress every 5 seconds
                    if chunk_count % 1562 == 0:  # ~5 seconds at 16kHz/512
                        duration = time.time() - self.recording_start_time
                        print(f"🎙️ Recording... {duration:.1f}s ({len(self.audio_data)} chunks)")
                        
                except OSError as e:
                    if "Input overflowed" in str(e):
                        print("⚠️ Input overflow (audio buffer full), continuing...")
                        continue
                    else:
                        print(f"❌ Audio read error: {e}")
                        break
                        
        except Exception as e:
            print(f"❌ Recording error: {e}")
            self.is_recording = False
    
    def stop_recording_and_send_to_aws(self):
        """Stop recording and send to AWS pipeline with better cleanup"""
        try:
            self.is_recording = False
            
            # Wait for recording thread to finish
            if self.recording_thread and self.recording_thread.is_alive():
                self.recording_thread.join(timeout=2)
            
            self.cleanup_audio()
            
            if not self.audio_data:
                print("⚠️ No audio data recorded")
                return
            
            duration = time.time() - self.recording_start_time if self.recording_start_time else 0
            print(f"🎵 Recorded {len(self.audio_data)} chunks ({duration:.1f}s)")
            
            # Save audio to file with better memory handling
            timestamp = int(time.time())
            filename = f"recording_{timestamp}.wav"
            
            self.save_audio_to_file(filename)
            
            print(f"💾 Audio saved to {filename}")
            
            # Show processing message
            Clock.schedule_once(
                lambda dt: self.update_transcription_display("🎤 Processing with AWS... Please wait...")
            )
            
            # Send to AWS in background thread
            threading.Thread(target=self.send_to_aws_pipeline, args=(filename,), daemon=True).start()
            
        except Exception as e:
            print(f"❌ Error stopping recording: {e}")
            self.cleanup_audio()
    
    def save_audio_to_file(self, filename):
        """Save audio data to WAV file with memory optimization"""
        try:
            with wave.open(filename, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(16000)
                
                # Write audio data in chunks to avoid memory issues
                for chunk in self.audio_data:
                    wf.writeframes(chunk)
                    
            # Clear audio data from memory
            self.audio_data = []
            print(f"💾 Audio file saved and memory cleared")
            
        except Exception as e:
            print(f"❌ Error saving audio file: {e}")
            raise
    
    def cleanup_audio(self):
        """Clean up audio resources"""
        try:
            if self.stream:
                if not self.stream.is_stopped():
                    self.stream.stop_stream()
                self.stream.close()
                self.stream = None
                
            if self.p:
                self.p.terminate()
                self.p = None
                
            print("🧹 Audio resources cleaned up")
            
        except Exception as e:
            print(f"⚠️ Error cleaning up audio: {e}")
    
    def send_to_aws_pipeline(self, filename):
        """Send audio file through AWS pipeline: S3 -> Transcribe -> Medical"""
        try:
            print(f"📤 Sending {filename} to AWS pipeline...")
            
            # Check file size
            file_size = os.path.getsize(filename)
            print(f"📊 File size: {file_size / 1024 / 1024:.2f} MB")
            
            # AWS Transcribe has file size limits (500MB for medical)
            if file_size > 400 * 1024 * 1024:  # 400MB limit for safety
                raise Exception(f"File too large ({file_size / 1024 / 1024:.2f} MB). Max 400MB.")
            
            # Method 1: Use your backend if it's running
            if self.send_via_backend(filename):
                return
            
            # Method 2: Direct AWS integration
            self.send_direct_to_aws(filename)
            
        except Exception as e:
            print(f"❌ Error in AWS pipeline: {e}")
            Clock.schedule_once(
                lambda dt: self.update_transcription_display(f"❌ Error: {str(e)}")
            )
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
            
            # Initialize AWS clients
            s3 = boto3.client("s3", region_name="ap-southeast-2")
            transcribe = boto3.client("transcribe", region_name="ap-southeast-2")
            
            # 1. Upload to S3 uploads folder
            timestamp = int(time.time())
            s3_key = f"uploads/{timestamp}.wav"
            
            s3.upload_file(filename, self.bucket_name, s3_key)
            print(f"☁️ Uploaded to S3: {s3_key}")
            
            # 2. Start AWS Transcribe Medical job
            job_name = f"medical-job-{timestamp}"
            job_uri = f"s3://{self.bucket_name}/{s3_key}"
            
            transcribe.start_medical_transcription_job(
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
            self.wait_for_transcription_result(job_name, transcribe)
            
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
            s3 = boto3.client("s3", region_name="ap-southeast-2")
            response = s3.get_object(Bucket=self.bucket_name, Key=s3_key)
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
    
    def generate_report_action(self):
        """Handle generate report button press - download structured data from S3"""
        try:
            print("📊 Generate report requested - downloading structured data...")
            
            # Show downloading message in UI
            Clock.schedule_once(
                lambda dt: self.update_transcription_display("⬇️ Downloading structured data from S3...")
            )
            
            # Download in background thread
            threading.Thread(target=self.download_structured_from_s3, daemon=True).start()
            
        except Exception as e:
            print(f"❌ CRASH in generate_report_action: {e}")
            import traceback
            traceback.print_exc()
            
            # Update UI with error
            Clock.schedule_once(
                lambda dt: self.update_transcription_display("❌ Error: Click failed. Check console.")
            )

    def download_structured_from_s3(self):
        """Download the latest structured JSON file from S3 bucket"""
        try:
            print("🔗 Connecting to S3...")
            
            # Initialize S3 client
            s3 = boto3.client("s3", region_name="ap-southeast-2")
            bucket_name = "ps2511-medical-buckets"
            
            # List files in structured folder
            print("📁 Checking structured/ folder...")
            response = s3.list_objects_v2(
                Bucket=bucket_name,
                Prefix="structured/"
            )
            
            if 'Contents' not in response or not response['Contents']:
                print("❌ No structured files found in S3")
                Clock.schedule_once(
                    lambda dt: self.update_transcription_display("❌ No structured files found in S3")
                )
                return
            
            # Get the most recent structured file
            latest_file = max(response['Contents'], key=lambda x: x['LastModified'])
            s3_key = latest_file['Key']
            
            print(f"📄 Found latest file: {s3_key}")
            print(f"📅 Modified: {latest_file['LastModified']}")
            
            # Create local download path in datastore/structured_data
            structured_data_dir = os.path.join("datastore", "structured_data")
            os.makedirs(structured_data_dir, exist_ok=True)
            
            local_filename = f"structured_data_{int(time.time())}.json"
            local_path = os.path.join(structured_data_dir, local_filename)
            
            # Download the file
            print(f"⬇️ Downloading {s3_key} to {local_path}...")
            s3.download_file(bucket_name, s3_key, local_path)
            
            # Verify download
            if os.path.exists(local_path):
                file_size = os.path.getsize(local_path)
                print(f"✅ Successfully downloaded!")
                print(f"📊 File: {local_path}")
                print(f"📏 Size: {file_size} bytes")
                
                # Update UI with success
                Clock.schedule_once(
                    lambda dt: self.update_transcription_display(f"✅ Downloaded: {local_filename}")
                )
                
                # Clear UI after 3 seconds
                Clock.schedule_once(lambda dt: self.clear_transcript(), 3)
                
            else:
                print("❌ Download failed")
                Clock.schedule_once(
                    lambda dt: self.update_transcription_display("❌ Download failed")
                )
                
        except Exception as e:
            print(f"❌ S3 download error: {e}")
            import traceback
            traceback.print_exc()
            Clock.schedule_once(
                lambda dt: self.update_transcription_display(f"❌ S3 error: {str(e)}")
            )

    def clear_transcript(self):
        """Clear the transcript text"""
        try:
            if hasattr(self.ids, 'transcription_text'):
                self.ids.transcription_text.text = "Structured data downloaded! Record new audio for next session."
                print("🧹 UI cleared")
        except Exception as e:
            print(f"❌ Error clearing UI: {e}")
    
    def update_transcription_display(self, text):
        """Update the transcription text display with raw transcript"""
        try:
            print(f"📝 Updating display with: {text[:100]}...")
            
            # Method 1: Try to find by ID first
            if hasattr(self.ids, 'transcription_text'):
                self.ids.transcription_text.text = text
                print(f"✅ Updated via ID: transcription_text")
                return
            
            # Method 2: Search for the text widget
            def find_text_widget(widget, depth=0):
                if hasattr(widget, 'text'):
                    current_text = str(widget.text)
                    # Look for the placeholder text
                    if ('Your transcribed text will appear here' in current_text or 
                        'transcribed text will appear' in current_text or
                        '🎤 Processing audio' in current_text or
                        'Report generated!' in current_text or
                        'unconscious with the heartbeat' in current_text):
                        return widget
                
                # Check children recursively
                for child in widget.children:
                    result = find_text_widget(child, depth + 1)
                    if result:
                        return result
                return None
            
            text_widget = find_text_widget(self)
            
            if text_widget:
                text_widget.text = text
                print(f"✅ Updated transcription display successfully")
            else:
                print("❌ Could not find text widget to update")
                
        except Exception as e:
            print(f"❌ Error updating transcription display: {e}")
            import traceback
            traceback.print_exc()