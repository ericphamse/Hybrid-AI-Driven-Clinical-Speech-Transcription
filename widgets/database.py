import sqlite3
import json
import os
#AWS SDK for Python (Boto3), (To use, install boto3 via 'pip install boto3' and then remove comment.)
#import boto3

#Import datatime for its timestamping feature.
# from datetime import datetime

#Craete dataclass for structured data handling.
# from dataclasses import dataclass, asdict
#Unique user id generation.
# import uuid

#Logging an debug and info for dev purpose.
# import logging
#Typing imports for dev purpose.
from typing import Dict, Optional, Any

class LocalDatabase:
    """SQLite database for local storage"""
    #Create table on itself if nothing exist.
    def init_database(text):
        """Initialize SQLite database with required tables"""
        try:
            conn = sqlite3.connect(text)
            cursor = conn.cursor()
            
            #User table
            # cursor.execute('''
            #     CREATE TABLE IF NOT EXISTS user (
            #         userId TEXT PRIMARY KEY,
            #         username TEXT UNIQUE NOT NULL,
            #         email TEXT UNIQUE NOT NULL,
            #         passwordHash TEXT NOT NULL,
            #         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            #     )
            # ''')
            
            #TranscriptionSession table (lastEditedTimestamp isn't inplemented for now)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transcription_session (
                    transcriptionId TEXT PRIMARY KEY,
                    sessionTimestamp TEXT NOT NULL,
                    rawTranscription TEXT NOT NULL,
                    isOnline BOOLEAN NOT NULL,
                    isOffline BOOLEAN NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            #ProgressNote table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS progress_note (
                    noteId INTEGER PRIMARY KEY AUTOINCREMENT,
                    transcriptionId TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    context TEXT NOT NULL,
                    peopleInvolved TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (transcriptionId) REFERENCES transcription_session (transcriptionId)
                )
            ''')
            
            #PatientObservation table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS patient_observation (
                    observationId INTEGER PRIMARY KEY AUTOINCREMENT,
                    transcriptionId TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    ObservationNote TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (transcriptionId) REFERENCES transcription_session (transcriptionId)
                )
            ''')
            
            #MedicationAdministered table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS medication_administered (
                    medicationId INTEGER PRIMARY KEY AUTOINCREMENT,
                    transcriptionId TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    medicineType TEXT ,
                    quantity TEXT ,
                    unit TEXT ,
                    administrationType TEXT ,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (transcriptionId) REFERENCES transcription_session (transcriptionId)
                )
            ''')
            
            #Sync tracking table
            # cursor.execute('''
            #     CREATE TABLE IF NOT EXISTS sync_status (
            #         id INTEGER PRIMARY KEY AUTOINCREMENT,
            #         table_name TEXT NOT NULL,
            #         record_id TEXT NOT NULL,
            #         last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            #         sync_status TEXT DEFAULT 'pending'
            #     )
            # ''')
            #Commit changes and close connection.
            conn.commit()
            conn.close()
            # logger.info("Local database initialised successfully")
            print("Local database initialized successfully")
            
        except Exception as e:
            print(f"Error initializing local database: {e}")
    def save_transcription_session(tids, session_data: Dict[str, Any]) -> str:
        """Save transcription session with all related data"""
        # transcription_id = str(uuid.uuid4())
        conn = sqlite3.connect("clinical_transcription.db")
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM transcription_session WHERE transcriptionId=?", (tids,))
        exists = cursor.fetchone()
        if not exists:
            try:
                #Save main transcription session.
                cursor.execute('''
                   INSERT INTO transcription_session 
                    (transcriptionId, sessionTimestamp, rawTranscription, isOnline, isOffline)
                    VALUES (?, ?, ?, ?, ?)
                ''', (session_data["transcriptionId"], session_data["timestamp"], 
                      session_data["rawTranscriptionId"], session_data["isOnline"], session_data["isOffline"]))
                
                #Save progress note.
                cursor.execute('''
                    INSERT INTO progress_note 
                    (transcriptionId, timestamp, context, peopleInvolved)
                    VALUES (?, ?, ?, ?)
                ''', (tids, 
                      session_data["medicalNoteStructure"]["progressNote"]["timestamp"],
                      session_data["medicalNoteStructure"]["progressNote"]["context"],
                      json.dumps(session_data["medicalNoteStructure"]["progressNote"]["peopleInvolved"])))
                    
                    #Save patient observation
                if session_data["medicalNoteStructure"]["patientObservation"]["otherObservations"]:
                    cursor.execute('''
                    INSERT INTO patient_observation 
                    (transcriptionId, timestamp, ObservationNote)
                    VALUES (?, ?, ?)
                ''', (tids, 
                      session_data["medicalNoteStructure"]["patientObservation"]["timestamp"],
                      session_data["medicalNoteStructure"]["patientObservation"]["otherObservations"]))
                        
                   #Save medication data
                if session_data["medicalNoteStructure"]["medicationAdministered"]["medicineType"]:
                    cursor.execute('''
                    INSERT INTO medication_administered 
                    (transcriptionId, timestamp, medicineType, quantity, unit, administrationType)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (tids, 
                      session_data["medicalNoteStructure"]["medicationAdministered"]["timestamp"],
                      session_data["medicalNoteStructure"]["medicationAdministered"]["medicineType"], 
                      session_data["medicalNoteStructure"]["medicationAdministered"]["quantity"], 
                      session_data["medicalNoteStructure"]["medicationAdministered"]["unit"],
                      session_data["medicalNoteStructure"]["medicationAdministered"]["administrationType"]))
                       

                print(f"Transcription session {tids} saved successfully")
                
            except Exception as e:
                print(f"Error saving transcription session: {e}")
        else:
            #Save progress note.
            conn = sqlite3.connect("clinical_transcription.db")
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO progress_note 
                (transcriptionId, timestamp, context, peopleInvolved)
                VALUES (?, ?, ?, ?)
            ''', (tids, 
                  session_data["medicalNoteStructure"]["progressNote"]["timestamp"],
                  session_data["medicalNoteStructure"]["progressNote"]["context"],
                    json.dumps(session_data["medicalNoteStructure"]["progressNote"]["peopleInvolved"])))
                    
                    #Save patient observation
            if session_data["medicalNoteStructure"]["patientObservation"]["otherObservations"]:
                cursor.execute('''
                INSERT INTO patient_observation 
                (transcriptionId, timestamp, ObservationNote)
                VALUES (?, ?, ?)
            ''', (tids, 
                    session_data["medicalNoteStructure"]["patientObservation"]["timestamp"],
                    session_data["medicalNoteStructure"]["patientObservation"]["otherObservations"]))
                        
                   #Save medication data
            if session_data["medicalNoteStructure"]["medicationAdministered"]["medicineType"]:
                cursor.execute('''
                INSERT INTO medication_administered 
                (transcriptionId, timestamp, medicineType, quantity, unit, administrationType)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (tids, 
                    session_data["medicalNoteStructure"]["medicationAdministered"]["timestamp"],
                    session_data["medicalNoteStructure"]["medicationAdministered"]["medicineType"], 
                    session_data["medicalNoteStructure"]["medicationAdministered"]["quantity"], 
                    session_data["medicalNoteStructure"]["medicationAdministered"]["unit"],
                    session_data["medicalNoteStructure"]["medicationAdministered"]["administrationType"]))
        conn.commit()
        conn.close()
        
     #Get  session details.
    def printPath():
        DATASTORE_DIR = os.path.join(os.getcwd(), "datastore")
        print("Current working directory:", DATASTORE_DIR)
    def get_session_details(transcription_id: str) -> Optional[Dict[str, Any]]:
        """Get complete session details including all related data"""
        try:
            conn = sqlite3.connect("clinical_transcription.db")
            cursor = conn.cursor()
            
            #Get main session data
            cursor.execute('''
                SELECT sessionTimestamp, rawTranscription, isOnline, isOffline
                FROM transcription_session
                WHERE transcriptionId = ?
            ''', (transcription_id,))
            
            session_row = cursor.fetchone()
            if not session_row:
                return None
            
            #Get progress notes
            cursor.execute('''
                SELECT noteId, timestamp, context, peopleInvolved
                FROM progress_note
                WHERE transcriptionId = ?
            ''', (transcription_id,))
            progress_note = [
                {
                    "noteId": row[0],
                    "timestamp": row[1],
                    "context": row[2],
                    "peopleInvolved": json.loads(row[3])
                }
                for row in cursor.fetchall()
            ]
            
            #Get patient observation
            cursor.execute('''
                SELECT observationId, timestamp, ObservationNote
                FROM patient_observation
                WHERE transcriptionId = ?
            ''', (transcription_id,))
            observation = [
                {
                    "observationId": row[0],
                    "timestamp": row[1],
                    "ObservationNote": row[2]
                }
                for row in cursor.fetchall()
            ]
            
            #Get medication data.
            cursor.execute('''
                SELECT medicationId, timestamp, medicineType, quantity, unit, administrationType
                FROM medication_administered
                WHERE transcriptionId = ?
            ''', (transcription_id,))
            medication = [
                {
                    "medicationId": row[0],
                    "timestamp": row[1],
                    "medicineType": row[2],
                    "quantity": row[3],
                    "unit": row[4],
                    "administrationType": row[5]
                }
                for row in cursor.fetchall()
            ]
            
            conn.close()
            
            #Construct complete session data.
            session_data = {
                "transcriptionId": transcription_id,
                "timestamp": session_row[0],
                "rawTranscriptionId": session_row[1],
                "isOnline": bool(session_row[2]),
                "isOffline": bool(session_row[3]),
                "medicalNoteStructure": {
                    "progressNote": progress_note,
                    "patientObservation": observation,
                    "medicationAdministered": medication
                }
            }
            json_path = os.path.join('datastore', 'data.json')
            with open(json_path, "w") as f:
                json.dump(session_data, f, indent=4)
            
        except Exception as e:
            print(f"Error retrieving session details: {e}")
            return None
    
    init_database("clinical_transcription.db")