#aws_sync_manager.py
import sqlite3
import json
import os
import boto3
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class AWSSyncManager:
    """Handle local-to-cloud sync for transcription records"""
    
    def __init__(self):
        self.local_db = "clinical_transcription.db"
        self.dynamodb_table = "TranscriptionRecords"
        
        #AWS credentials from .env with relervant access key and secret 
        # ----------------WARNING: DO NOT STORE .env WITHIN GITHUB!!!!----------------
        self.aws_key = os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret = os.getenv('AWS_SECRET_ACCESS_KEY')
        self.aws_region = os.getenv('AWS_REGION', 'ap-southeast-2')
        
        #Initialize AWS client
        try:
            self.dynamodb = boto3.resource(
                'dynamodb',
                region_name=self.aws_region,
                aws_access_key_id=self.aws_key,
                aws_secret_access_key=self.aws_secret
            )
            self.table = self.dynamodb.Table(self.dynamodb_table)
            print("✅ AWS DynamoDB connected")
        except Exception as e:
            print(f"⚠️ AWS connection failed: {e}")
            self.table = None
    #---Check connectivity---
    def check_aws_connectivity(self):
        """Quick check if AWS is reachable"""
        try:
            if self.table:
                self.table.table_status
                return True
        except:
            pass
        return False
    #---Save to AWS DynamoDB---
    def save_to_dynamodb(self, transcription_id, session_data):
        """Push a record directly to DynamoDB (for online mode)"""
        if not self.table:
            print("❌ DynamoDB not connected")
            return False
        
        try:
            #Extract key data from your session structure
            item = {
            'userId': 'default_clinician',
            'sessionId': transcription_id,
            'timestamp': session_data.get('timestamp'),
            'progressNote': session_data.get('progressNote', ''),
            'patientObservation': session_data.get('patientObservation', ''),
            'medicationAdministered': session_data.get('medicationAdministered', []),
            'mode': 'online' if session_data.get('isOnline') else 'offline',
            'syncStatus': 'synced'
        }
            
            self.table.put_item(Item=item)
            print(f"✅ Synced to AWS: {transcription_id}")
            return True
        except Exception as e:
            print(f"❌ Failed to sync to AWS: {e}")
            return False
    #---Sync the pending records---    
    def sync_pending_records(self):
        """Push all pending records from SQLite to DynamoDB"""
        if not self.table:
            print("❌ DynamoDB not connected")
            return 0
        
        try:
            conn = sqlite3.connect(self.local_db)
            cursor = conn.cursor()
            
            #Get all transcription sessions that haven't been synced

            #Broken function....
            #cursor.execute('''
                #SELECT transcriptionId FROM transcription_session 
                #WHERE isOnline = 1 AND rowid NOT IN (
                #    SELECT rowid FROM transcription_session WHERE isOnline = 0
                #)
            #''')

            #TEMPOARY FIX TO FORCE SYNC TRANSCRIPTION MARKED AS OFFLINE
            cursor.execute('''
                SELECT transcriptionId FROM transcription_session 
                WHERE isOffline = 1
            ''')
            
            records_to_sync = cursor.fetchall()
            synced_count = 0
            
            for (transcription_id,) in records_to_sync:
                #Get full session data
                session_data = self.get_session_from_sqlite(transcription_id)
                
                if session_data:
                    item = {
                        'userId': 'default_clinician',
                        'sessionId': transcription_id,
                        'timestamp': session_data.get('timestamp'),
                        'progressNote': session_data.get('progressNote', ''),
                        'patientObservation': session_data.get('patientObservation', ''),
                        'medicationAdministered': session_data.get('medicationAdministered', []),
                        'mode': 'online' if session_data.get('isOnline') else 'offline',
                        'syncStatus': 'synced'
                    }
                    
                    try:
                        self.table.put_item(Item=item)
                        synced_count += 1
                        print(f"✅ Synced: {transcription_id}")
                    except Exception as e:
                        print(f"❌ Failed: {transcription_id} - {e}")
            
            conn.close()
            return synced_count
        
        except Exception as e:
            print(f"❌ Error syncing pending records: {e}")
            return 0
    #---Get the session from local database---
    def get_session_from_sqlite(self, transcription_id):
        """Retrieve a session from SQLite and flatten for DynamoDB"""
        try:
            conn = sqlite3.connect(self.local_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT sessionTimestamp, rawTranscription, isOnline, isOffline
                FROM transcription_session WHERE transcriptionId = ?
            ''', (transcription_id,))
            
            session_row = cursor.fetchone()
            if not session_row:
                return None
            
            # Get ALL progress notes and combine into one string
            cursor.execute('''
                SELECT context FROM progress_note WHERE transcriptionId = ?
            ''', (transcription_id,))
            
            progress_notes = cursor.fetchall()
            combined_progress = '\n---\n'.join([row[0] for row in progress_notes]) if progress_notes else ''
            
            # Get ALL patient observations and combine into one string
            cursor.execute('''
                SELECT ObservationNote FROM patient_observation WHERE transcriptionId = ?
            ''', (transcription_id,))
            
            observations = cursor.fetchall()
            combined_observations = '\n'.join([row[0] for row in observations]) if observations else ''
            
            # Get ALL medications as list of dicts
            cursor.execute('''
                SELECT medicineType, quantity, unit, administrationType
                FROM medication_administered
                WHERE transcriptionId = ?
            ''', (transcription_id,))
            
            medications = [
                {
                    'medicineType': row[0],
                    'quantity': row[1],
                    'unit': row[2],
                    'administrationType': row[3]
                }
                for row in cursor.fetchall()
            ]
            
            conn.close()
            
            return {
                'transcriptionId': transcription_id,
                'timestamp': session_row[0],
                'rawTranscription': session_row[1],
                'isOnline': bool(session_row[2]),
                'isOffline': bool(session_row[3]),
                'progressNote': combined_progress,
                'patientObservation': combined_observations,
                'medicationAdministered': medications
            }
        
        except Exception as e:
            print(f"❌ Error retrieving session: {e}")
            return None