import sqlite3
import json
#AWS SDK for Python (Boto3), (To use, install boto3 via 'pip install boto3' and then remove comment.)
#import boto3

#Import datatime for its timestamping feature.
from datetime import datetime

#Craete dataclass for structured data handling.
from dataclasses import dataclass, asdict
#Unique user id generation.
import uuid

#Logging an debug and info for dev purpose.
import logging
#Typing imports for dev purpose.
from typing import Dict, List, Optional, Any



#logging config.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


#Table and attribute definitions via dataclasses library
#-------------------- Table Definitions ------------------#
##User Table
@dataclass
class User:
    userId: str
    username: str
    email: str
    passwordHash: str
##Transcription Session Table
@dataclass
class TranscriptionSession:
    transcriptionId: str
    userId: str
    sessionTimestamp: str
    rawTranscription: str
    isOnline: bool
    isOffline: bool

#The 3 main medical note structure tables
##Progress Note Table
@dataclass
class ProgressNote:
    noteId: str
    transcriptionId: str
    timestamp: str
    context: str
    peopleInvolved: List[str]

##Patient Observation Table
@dataclass
class PatientObservation:
    observationId: str
    transcriptionId: str
    timestamp: str
    ObservationNote: str

##Medication Administered Table
@dataclass
class MedicationAdministered:
    medicationId: str
    transcriptionId: str
    timestamp: str
    medicineType: str
    quantity: str
    administrationType: str


#------------------- Local Database ------------------#
class LocalDatabase:
    """SQLite database for local storage"""
    #initialise database.
    def __init__(self, db_path: str = "clinical_transcription.db"):
        self.db_path = db_path
        self.init_database()
    #Create table on itself if nothing exist.
    def init_database(self):
        """Initialize SQLite database with required tables"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            #User table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user (
                    userId TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    passwordHash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            #TranscriptionSession table (lastEditedTimestamp isn't inplemented for now)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transcription_session (
                    transcriptionId TEXT PRIMARY KEY,
                    userId TEXT NOT NULL,
                    sessionTimestamp TEXT NOT NULL,
                    lastEditedTimestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    rawTranscription TEXT NOT NULL,
                    isOnline BOOLEAN NOT NULL,
                    isOffline BOOLEAN NOT NULL,
                    synced BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (userId) REFERENCES user (userId)
                )
            ''')
            
            #ProgressNote table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS progress_note (
                    noteId TEXT PRIMARY KEY,
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
                    observationId TEXT PRIMARY KEY,
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
                    medicationId TEXT PRIMARY KEY,
                    transcriptionId TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    medicineType TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    administrationType TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (transcriptionId) REFERENCES transcription_session (transcriptionId)
                )
            ''')
            
            #Sync tracking table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sync_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    sync_status TEXT DEFAULT 'pending'
                )
            ''')
            #Commit changes and close connection.
            conn.commit()
            conn.close()
            logger.info("Local database initialised successfully")
            
        except Exception as e:
            logger.error(f"Error initializing local database: {e}")
            raise
    
    #Create user.
    def create_user(self, user: User) -> bool:
        """Create a new user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            #perfoms user creation.
            cursor.execute('''
                INSERT INTO user (userId, username, email, passwordHash)
                VALUES (?, ?, ?, ?)
            ''', (user.userId, user.username, user.email, user.passwordHash))

            conn.commit()
            conn.close()
            logger.info(f"User {user.username} has been created successfully")
            return True
        except sqlite3.IntegrityError as e:
            logger.error(f"Error, User creation failed - duplicate entry: {e}")
            return False
        except Exception as e:
            logger.error(f"Error on creating user: {e}. Please try again later or contact support.")
            return False
        
    #Authentication.
    def get_user_by_credentials(self, username: str, password_hash: str) -> Optional[User]:
        """Authenticate user and return user data"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT userId, username, email, passwordHash
                FROM user
                WHERE username = ? AND passwordHash = ?
            ''', (username, password_hash))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return User(*result)
            return None
            
        except Exception as e:
            logger.error(f"Error on authenticating user: {e}. Please try again later or contact support.")
            return None
        
    #Save the transcription session.
    def save_transcription_session(self, session_data: Dict[str, Any]) -> str:
        """Save transcription session with all related data"""
        transcription_id = str(uuid.uuid4())
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            #Save main transcription session.
            session = TranscriptionSession(
                transcriptionId=transcription_id,
                userId=session_data["userId"],
                sessionTimestamp=session_data["timestamp"],
                rawTranscription=session_data["rawTranscriptionId"],
                isOnline=session_data["isOnline"],
                isOffline=session_data["isOffline"]
            )
            #Insert into transcription_session table.
            cursor.execute('''
                INSERT INTO transcription_session 
                (transcriptionId, userId, sessionTimestamp, rawTranscription, isOnline, isOffline)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (session.transcriptionId, session.userId, session.sessionTimestamp, 
                  session.rawTranscription, session.isOnline, session.isOffline))
            
            #Save progress note.
            for note_data in session_data["medicalNoteStructure"]["progressNote"]:
                cursor.execute('''
                    INSERT INTO progress_note 
                    (noteId, transcriptionId, timestamp, context, peopleInvolved)
                    VALUES (?, ?, ?, ?, ?)
                ''', (note_data["noteId"], transcription_id, note_data["timestamp"],
                      note_data["context"], json.dumps(note_data["peopleInvolved"])))
            
            #Save patient observation
            for obs_data in session_data["medicalNoteStructure"]["patientObservation"]:
                cursor.execute('''
                    INSERT INTO patient_observation 
                    (observationId, transcriptionId, timestamp, ObservationNote)
                    VALUES (?, ?, ?, ?)
                ''', (obs_data["observationId"], transcription_id, obs_data["timestamp"],
                      obs_data["ObservationNote"]))
            
            #Save medication data
            for med_data in session_data["medicalNoteStructure"]["medicationAdministered"]:
                cursor.execute('''
                    INSERT INTO medication_administered 
                    (medicationId, transcriptionId, timestamp, medicineType, quantity, administrationType)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (med_data["medicationId"], transcription_id, med_data["timestamp"],
                      med_data["medicineType"], med_data["quantity"], med_data["administrationType"]))
            
            conn.commit()
            conn.close()
            logger.info(f"Transcription session {transcription_id} saved successfully")
            return transcription_id
            
        except Exception as e:
            logger.error(f"Error saving transcription session: {e}")
            raise
    
    #Get user session history.
    def get_user_sessions(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get transcription session for a user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT transcriptionId, sessionTimestamp, rawTranscription, isOnline, isOffline
                FROM transcription_session
                WHERE userId = ?
                ORDER BY sessionTimestamp DESC
                LIMIT ?
            ''', (user_id, limit))
            
            session = []
            for row in cursor.fetchall():
                session_data = {
                    "transcriptionId": row[0],
                    "timestamp": row[1],
                    "rawTranscription": row[2],
                    "isOnline": bool(row[3]),
                    "isOffline": bool(row[4])
                }
                session.append(session_data)
            
            conn.close()
            return session
            
        except Exception as e:
            logger.error(f"Error retrieving user session: {e}")
            return []
    
    #Get  session details.
    def get_session_details(self, transcription_id: str) -> Optional[Dict[str, Any]]:
        """Get complete session details including all related data"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            #Get main session data
            cursor.execute('''
                SELECT userId, sessionTimestamp, rawTranscription, isOnline, isOffline
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
                SELECT medicationId, timestamp, medicineType, quantity, administrationType
                FROM medication_administered
                WHERE transcriptionId = ?
            ''', (transcription_id,))
            medication = [
                {
                    "medicationId": row[0],
                    "timestamp": row[1],
                    "medicineType": row[2],
                    "quantity": row[3],
                    "administrationType": row[4]
                }
                for row in cursor.fetchall()
            ]
            
            conn.close()
            
            #Construct complete session data.
            session_data = {
                "transcriptionId": transcription_id,
                "userId": session_row[0],
                "timestamp": session_row[1],
                "rawTranscriptionId": session_row[2],
                "isOnline": bool(session_row[3]),
                "isOffline": bool(session_row[4]),
                "medicalNoteStructure": {
                    "progressNote": progress_note,
                    "patientObservation": observation,
                    "medicationAdministered": medication
                }
            }
            
            return session_data
            
        except Exception as e:
            logger.error(f"Error retrieving session details: {e}")
            return None
    
    #Get unsynced sessions.
    def get_unsynced_sessions(self) -> List[str]:
        """Get list of transcription IDs that haven't been synced to cloud"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT transcriptionId
                FROM transcription_session
                WHERE synced = FALSE
            ''')
            
            unsynced_ids = [row[0] for row in cursor.fetchall()]
            conn.close()
            return unsynced_ids
            
        except Exception as e:
            logger.error(f"Error retrieving unsynced session: {e}")
            return []
    
    #For cloud sync later.
    def mark_session_synced(self, transcription_id: str):
        """Mark a session as synced to cloud"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE transcription_session
                SET synced = TRUE
                WHERE transcriptionId = ?
            ''', (transcription_id,))
            
            conn.commit()
            conn.close()
            logger.info(f"Session {transcription_id} is marked as synced")
            
        except Exception as e:
            logger.error(f"Error marking session as synced: {e}")


#------------------- Database Manager ------------------#
class DatabaseManager:
    """Main database manager that handles both local and cloud operations"""
    
    def __init__(self, db_path: str = "clinical_transcription.db"):
        self.local_db = LocalDatabase(db_path)
    
    def save_session(self, session_data: Dict[str, Any]) -> str:
        """Save session locally and sync to cloud if available"""
        transcription_id = self.local_db.save_transcription_session(session_data)
        #cloud sync is not available. Wil be implemented here.
        return transcription_id
    
    def authenticate_user(self, username: str, password_hash: str) -> Optional[User]:
        """Authenticate user against local database"""
        return self.local_db.get_user_by_credentials(username, password_hash)
    
    def create_user(self, user: User) -> bool:
        """Create new user"""
        return self.local_db.create_user(user)
    
    def get_user_history(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get user's transcription history"""
        return self.local_db.get_user_sessions(user_id, limit)


# Example usage and testing
if __name__ == "__main__":
    # Initialize database manager
    db_manager = DatabaseManager()
    
    # Example user creation
    test_user = User(
        userId=str(uuid.uuid4()),
        username="dr_smith",
        email="dr.smith@clinician.com",
        passwordHash="hashed_password_here"
    )
    
    #Create user
    if db_manager.create_user(test_user):
        print("User created successfully")
    
    #Example session data (from the current, unchanged JSON structure)
    example_session = {
        "userId": test_user.userId,
        "timestamp": "2025-01-01T23:59:59",
        "rawTranscriptionId": "Patient presents with chest pain and shortness of breath. Blood pressure 140/90. Administered aspirin 200mg orally.",
        "isOnline": False,
        "isOffline": True,
        "medicalNoteStructure": {
            "progressNote": [
                {
                    "noteId": "PN_25_000001",
                    "timestamp": "2025-01-01T12:49:59",
                    "peopleInvolved": ["Dr. Smith"],
                    "context": "Patient presents with chest pain and shortness of breath. Vital signs stable."
                }
            ],
            "patientObservation": [
                {
                    "observationId": "PO_25_000001",
                    "timestamp": "2025-01-01T12:49:59",
                    "ObservationNote": "Patient alert and oriented, mild distress"
                }
            ],
            "medicationAdministered": [
                {
                    "medicationId": "MA_25_000001",
                    "timestamp": "2025-01-01T12:49:59",
                    "medicineType": "Aspirin",
                    "quantity": "200mg",
                    "administrationType": "oral"
                }
            ]
        }
    }
    
    #Save session
    transcription_id = db_manager.save_session(example_session)
    print(f"Session saved with ID: {transcription_id}")
    
    #Get user history
    history = db_manager.get_user_history(test_user.userId)
    print(f"User has {len(history)} session in history")
    
    #Test sync function
    db_manager.sync_offline_session()