# Description: Módulo para mantener el estado de la aplicación
from app.utils.image_utils import encode_image
from app.config.settings import settings
import time
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class AppState:
    def __init__(self):
        self.current_time = None
        self.datetimesigned = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.conn = None
        self.encoded_image = encode_image(settings.LOGO_PATH)
        self.isclosing = None
        # Initialize the document timestamps map
        self.doc_timestamps = {}
        # Map for other document-specific data
        self.doc_data = {}

    def load_settings(self):
        self.current_time = int(time.time() * 1000)
        self.datetimesigned = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.conn = None
        self.encoded_image = encode_image(settings.LOGO_PATH)
        self.isclosing = None
        # Clear document-specific data
        self.doc_timestamps = {}
        self.doc_data = {}
        
    def set_document_timestamp(self, doc_id, timestamp=None):
        """Set a timestamp for a specific document and return it"""
        if timestamp is None:
            timestamp = int(time.time() * 1000)
        self.doc_timestamps[doc_id] = timestamp
        logger.debug(f"Set timestamp {timestamp} for document {doc_id}")
        return timestamp
    
    def get_document_timestamp(self, doc_id):
        """Get the timestamp for a specific document or generate a new one if it doesn't exist"""
        if doc_id not in self.doc_timestamps:
            return self.set_document_timestamp(doc_id)
        timestamp = self.doc_timestamps[doc_id]
        logger.debug(f"Retrieved timestamp {timestamp} for document {doc_id}")
        return timestamp
    
    def remove_document_timestamp(self, doc_id):
        """Remove a document's timestamp after processing is complete"""
        if doc_id in self.doc_timestamps:
            timestamp = self.doc_timestamps.pop(doc_id)
            logger.debug(f"Removed timestamp {timestamp} for document {doc_id}")
            return timestamp
        return None
        
    def set_document_data(self, doc_id, key, value):
        """Store document-specific data other than timestamps"""
        if doc_id not in self.doc_data:
            self.doc_data[doc_id] = {}
        self.doc_data[doc_id][key] = value
        logger.debug(f"Set {key}={value} for document {doc_id}")
        
    def get_document_data(self, doc_id, key, default=None):
        """Retrieve document-specific data"""
        if doc_id not in self.doc_data or key not in self.doc_data[doc_id]:
            return default
        return self.doc_data[doc_id][key]

app_state = AppState()