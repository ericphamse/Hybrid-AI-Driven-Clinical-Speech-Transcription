import boto3
from botocore.exceptions import ClientError
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CloudDatabase:
    """DynamoDB database for cloud storage and sync - AWS Sydney Region"""
    
    def __init__(self, region_name: str = 'ap-southeast-2'):
        """
        Initialize DynamoDB connection for Sydney region (ap-southeast-2)
        
        AWS Credentials should be configured via:
        1. AWS CLI: aws configure
        2. Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
        3. IAM role (if running on AWS infrastructure)
        """
        try:
            self.dynamodb = boto3.resource('dynamodb', region_name=region_name)
            self.dynamodb_client = boto3.client('dynamodb', region_name=region_name)
            self.table_name = 'ClinicalTranscriptions'
            
            # Check if table exists, create if not
            self._ensure_table_exists()
            
            self.table = self.dynamodb.Table(self.table_name)
            logger.info(f"Connected to DynamoDB in {region_name} successfully")
            
        except Exception as e:
            logger.error(f"Error connecting to DynamoDB: {e}")
            raise
    
    def _ensure_table_exists(self):
        """Create DynamoDB table if it doesn't exist"""
        try:
            existing_tables = self.dynamodb_client.list_tables()['TableNames']
            
            if self.table_name not in existing_tables:
                logger.info(f"Table {self.table_name} not found. Creating...")
                
                table = self.dynamodb.create_table(
                    TableName=self.table_name,
                    KeySchema=[
                        {
                            'AttributeName': 'transcriptionId',
                            'KeyType': 'HASH'  # Partition key
                        }
                    ],
                    AttributeDefinitions=[
                        {
                            'AttributeName': 'transcriptionId',
                            'AttributeType': 'S'
                        },
                        {
                            'AttributeName': 'sessionTimestamp',
                            'AttributeType': 'S'
                        }
                    ],
                    GlobalSecondaryIndexes=[
                        {
                            'IndexName': 'TimestampIndex',
                            'KeySchema': [
                                {
                                    'AttributeName': 'sessionTimestamp',
                                    'KeyType': 'HASH'
                                }
                            ],
                            'Projection': {
                                'ProjectionType': 'ALL'
                            },
                            'ProvisionedThroughput': {
                                'ReadCapacityUnits': 5,
                                'WriteCapacityUnits': 5
                            }
                        }
                    ],
                    ProvisionedThroughput={
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                )
                
                # Wait for table to be created
                table.meta.client.get_waiter('table_exists').wait(TableName=self.table_name)
                logger.info(f"Table {self.table_name} created successfully")
            else:
                logger.info(f"Table {self.table_name} already exists")
                
        except ClientError as e:
            logger.error(f"Error creating table: {e}")
            raise
    
    def sync_session_to_cloud(self, session_data: Dict[str, Any]) -> bool:
        """
        Sync a complete session to DynamoDB
        
        Args:
            session_data: Complete session data from LocalDatabase.get_session_details()
        
        Returns:
            bool: True if sync successful, False otherwise
        """
        try:
            # Add cloud sync metadata
            cloud_item = session_data.copy()
            cloud_item['syncedAt'] = datetime.utcnow().isoformat()
            cloud_item['syncVersion'] = 1
            
            # DynamoDB doesn't support empty strings, so convert them to None
            cloud_item = self._clean_empty_strings(cloud_item)
            
            response = self.table.put_item(Item=cloud_item)
            logger.info(f"Session {session_data['transcriptionId']} synced to cloud successfully")
            return True
            
        except ClientError as e:
            logger.error(f"Error syncing session to cloud: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error syncing to cloud: {e}")
            return False
    
    def _clean_empty_strings(self, data: Any) -> Any:
        """
        Recursively convert empty strings to None for DynamoDB compatibility
        DynamoDB doesn't allow empty string values
        """
        if isinstance(data, dict):
            return {k: self._clean_empty_strings(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._clean_empty_strings(item) for item in data]
        elif data == "":
            return None
        else:
            return data
    
    def get_session_from_cloud(self, transcription_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific session from DynamoDB
        
        Args:
            transcription_id: The transcription ID to retrieve
        
        Returns:
            Dict with session data or None if not found
        """
        try:
            response = self.table.get_item(Key={'transcriptionId': transcription_id})
            
            if 'Item' in response:
                logger.info(f"Retrieved session {transcription_id} from cloud")
                return response['Item']
            else:
                logger.info(f"Session {transcription_id} not found in cloud")
                return None
                
        except ClientError as e:
            logger.error(f"Error retrieving session from cloud: {e}")
            return None
    
    def get_recent_sessions_from_cloud(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent sessions from DynamoDB (for ground staff view)
        
        Args:
            limit: Maximum number of sessions to return
        
        Returns:
            List of session dictionaries
        """
        try:
            # Scan table and sort by timestamp (for demo purposes)
            # In production, use Query with GSI for better performance
            response = self.table.scan(Limit=limit)
            
            sessions = response.get('Items', [])
            
            # Sort by sessionTimestamp descending
            sessions.sort(key=lambda x: x.get('sessionTimestamp', ''), reverse=True)
            
            logger.info(f"Retrieved {len(sessions)} sessions from cloud")
            return sessions
            
        except ClientError as e:
            logger.error(f"Error retrieving recent sessions: {e}")
            return []
    
    def check_session_exists(self, transcription_id: str) -> bool:
        """
        Check if a session already exists in DynamoDB
        
        Args:
            transcription_id: The transcription ID to check
        
        Returns:
            bool: True if exists, False otherwise
        """
        try:
            response = self.table.get_item(
                Key={'transcriptionId': transcription_id},
                ProjectionExpression='transcriptionId'  # Only get the key, not full item
            )
            return 'Item' in response
            
        except ClientError as e:
            logger.error(f"Error checking session existence: {e}")
            return False


class SyncManager:
    """
    Manager to handle sync between LocalDatabase and CloudDatabase
    Integrates with Minh's existing database.py structure
    """
    
    def __init__(self, local_db_module, region_name: str = 'ap-southeast-2'):
        """
        Initialize SyncManager
        
        Args:
            local_db_module: The LocalDatabase class/module from database.py
            region_name: AWS region (default: Sydney ap-southeast-2)
        """
        self.local_db = local_db_module
        try:
            self.cloud_db = CloudDatabase(region_name)
            self.cloud_enabled = True
            logger.info("Cloud sync enabled")
        except Exception as e:
            logger.warning(f"Cloud database not available: {e}")
            logger.warning("Running in offline-only mode")
            self.cloud_enabled = False
    
    def is_online(self) -> bool:
        """
        Check if cloud connectivity is available
        Simple check by attempting to list tables
        
        Returns:
            bool: True if cloud is accessible
        """
        if not self.cloud_enabled:
            return False
        
        try:
            self.cloud_db.dynamodb_client.list_tables()
            return True
        except Exception:
            return False
    
    def sync_session(self, transcription_id: str) -> bool:
        """
        Sync a single session to cloud by transcription ID
        
        Args:
            transcription_id: The session ID to sync
        
        Returns:
            bool: True if sync successful, False otherwise
        """
        if not self.cloud_enabled:
            logger.warning("Cloud sync not enabled")
            return False
        
        if not self.is_online():
            logger.warning("No cloud connectivity available")
            return False
        
        # Check if already synced to cloud
        if self.cloud_db.check_session_exists(transcription_id):
            logger.info(f"Session {transcription_id} already exists in cloud, skipping")
            return True
        
        # Get session data from local database
        session_data = self.local_db.get_session_details(transcription_id)
        
        if not session_data:
            logger.error(f"Session {transcription_id} not found in local database")
            return False
        
        # Sync to cloud
        success = self.cloud_db.sync_session_to_cloud(session_data)
        
        if success:
            logger.info(f"Successfully synced session {transcription_id} to cloud")
        else:
            logger.error(f"Failed to sync session {transcription_id}")
        
        return success
    
    def sync_all_sessions(self, transcription_ids: List[str]) -> Dict[str, bool]:
        """
        Sync multiple sessions to cloud
        
        Args:
            transcription_ids: List of transcription IDs to sync
        
        Returns:
            Dict mapping transcription_id to success status
        """
        results = {}
        
        if not self.cloud_enabled or not self.is_online():
            logger.warning("Cloud sync not available")
            return {tid: False for tid in transcription_ids}
        
        for transcription_id in transcription_ids:
            results[transcription_id] = self.sync_session(transcription_id)
        
        success_count = sum(1 for success in results.values() if success)
        logger.info(f"Synced {success_count}/{len(transcription_ids)} sessions successfully")
        
        return results
    
    def get_ground_staff_view(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent sessions for ground staff viewing
        
        Args:
            limit: Maximum number of sessions to return
        
        Returns:
            List of session dictionaries
        """
        if not self.cloud_enabled or not self.is_online():
            logger.warning("Cloud not available, returning empty list")
            return []
        
        return self.cloud_db.get_recent_sessions_from_cloud(limit)


# ============================================================================
# INTEGRATION EXAMPLE WITH DATABASE.PY
# ============================================================================

def example_integration():
    """
    Example showing how to integrate cloud sync with existing database.py
    """
    # Import the existing LocalDatabase from database.py
    from database import LocalDatabase
    
    # Initialize sync manager
    sync_manager = SyncManager(LocalDatabase, region_name='ap-southeast-2')
    
    # Example 1: Save session offline (existing code works as-is)
    print("\n=== Example 1: Offline Save ===")
    example_session = {
        "transcriptionId": "test-session-001",
        "timestamp": "2025-10-09T12:00:00",
        "rawTranscriptionId": "Patient presents with chest pain...",
        "isOnline": False,
        "isOffline": True,
        "medicalNoteStructure": {
            "progressNote": {
                "timestamp": "2025-10-09T12:00:00",
                "context": "Patient evaluation in progress",
                "peopleInvolved": ["Dr. Smith"]
            },
            "patientObservation": {
                "timestamp": "2025-10-09T12:00:00",
                "otherObservations": "Blood pressure 140/90"
            },
            "medicationAdministered": {
                "timestamp": "2025-10-09T12:00:00",
                "medicineType": "Aspirin",
                "quantity": "200mg",
                "administrationType": "oral"
            }
        }
    }
    
    # Save locally
    LocalDatabase.save_transcription_session("test-session-001", example_session)
    print("✓ Session saved locally")
    
    # Example 2: Sync to cloud when connectivity returns
    print("\n=== Example 2: Cloud Sync ===")
    if sync_manager.is_online():
        success = sync_manager.sync_session("test-session-001")
        if success:
            print("✓ Session synced to cloud")
        else:
            print("✗ Failed to sync to cloud")
    else:
        print("⚠ No cloud connectivity - data remains local only")
    
    # Example 3: Sync multiple sessions (bulk sync when connected)
    print("\n=== Example 3: Bulk Sync ===")
    session_ids = ["test-session-001", "test-session-002", "test-session-003"]
    results = sync_manager.sync_all_sessions(session_ids)
    print(f"Sync results: {results}")
    
    # Example 4: Ground staff viewing cloud data
    print("\n=== Example 4: Ground Staff View ===")
    recent_sessions = sync_manager.get_ground_staff_view(limit=10)
    print(f"Found {len(recent_sessions)} recent sessions in cloud")


# ============================================================================
# SIMPLE USAGE INSTRUCTIONS
# ============================================================================

"""
INTEGRATION STEPS:

1. Install boto3:
   pip install boto3

2. Configure AWS credentials (one of these methods):
   
   Method A - AWS CLI:
   aws configure
   (Enter your AWS Access Key ID, Secret Access Key, and region ap-southeast-2)
   
   Method B - Environment Variables:
   export AWS_ACCESS_KEY_ID='your-access-key'
   export AWS_SECRET_ACCESS_KEY='your-secret-key'
   export AWS_DEFAULT_REGION='ap-southeast-2'
   
   Method C - Credentials file (~/.aws/credentials):
   [default]
   aws_access_key_id = your-access-key
   aws_secret_access_key = your-secret-key
   region = ap-southeast-2

3. In your main application code:

   from database import LocalDatabase
   from cloud_sync import SyncManager
   
   # Initialize sync manager
   sync_manager = SyncManager(LocalDatabase)
   
   # After saving offline session
   LocalDatabase.save_transcription_session(transcription_id, session_data)
   
   # When connectivity returns (check periodically or on user action)
   if sync_manager.is_online():
       sync_manager.sync_session(transcription_id)

4. For bulk sync when plane lands:
   
   # Get all unsynced session IDs (you'll need to track these)
   unsynced_ids = ["session1", "session2", "session3"]
   
   # Sync all at once
   results = sync_manager.sync_all_sessions(unsynced_ids)
"""

if __name__ == "__main__":
    print("Cloud Sync Module for Clinical Transcription System")
    print("=" * 60)
    print("AWS Region: ap-southeast-2 (Sydney)")
    print("\nThis module adds cloud sync capability to the existing")
    print("offline LocalDatabase implementation.")
    print("\nSee example_integration() for usage examples.")
    print("=" * 60)
