class WatermarkError(Exception):
    """Base exception for watermark operations."""
    pass

class PDFReadError(WatermarkError):
    """Exception raised when there's an error reading the PDF file."""
    pass

class PDFWriteError(WatermarkError):
    """Exception raised when there's an error writing the PDF file."""
    pass

class WatermarkCreationError(WatermarkError):
    """Exception raised when there's an error creating the watermark."""
    pass

class PDFMergeError(WatermarkError):
    """Exception raised when there's an error merging PDF files."""
    pass

class InvalidPDFError(WatermarkError):
    """Exception raised when the PDF file is invalid or corrupted."""
    pass

class WatermarkTextError(WatermarkError):
    """Exception raised when there's an issue with the watermark text."""
    pass

class SaveError(Exception):
    """Base exception for save operations."""
    pass

class JSONSaveError(SaveError):
    """Exception raised when there's an error saving JSON data."""
    pass

class PDFSaveError(SaveError):
    """Exception raised when there's an error saving PDF data."""
    pass

class DatabaseError(Exception):
    """Base exception for database operations."""
    pass

class DatabaseConnectionError(DatabaseError):
    """Exception raised when there's an error connecting to the database."""
    pass

class DatabaseTransactionError(DatabaseError):
    """Exception raised when there's an error during a database transaction."""
    pass

class DocumentProcessingError(DatabaseError):
    """Exception raised when there's an error processing a document in the database."""
    pass

class PDFClosingError(Exception):
    """Exception raised when there's an error closing the PDF."""
    pass
