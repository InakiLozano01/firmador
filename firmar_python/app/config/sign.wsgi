import sys
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    # Add the parent directory of 'app' to the Python path
    parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    logger.info(f"Adding to Python path: {parent_dir}")
    sys.path.insert(0, parent_dir)

    from app.config.main import app as application
    logger.info("Successfully imported application")
except Exception as e:
    logger.error(f"Failed to initialize application: {str(e)}", exc_info=True)
    raise