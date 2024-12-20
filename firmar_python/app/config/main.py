import logging
import os
from flask import Flask, request
from app.config.state import AppState
from app.config.settings import settings
from app.routes.routes import register_routes

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    try:
        logger.info("Creating Flask application")
        app = Flask(__name__)
        
        # Configuration
        app.config['MAX_CONTENT_LENGTH'] = 500000000
        app.json.sort_keys = False
        
        # Register routes
        register_routes(app)
        logger.info("Routes registered successfully")

        # Add error handlers
        @app.errorhandler(Exception)
        def handle_exception(e):
            logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
            return {"status": False, "message": f"Internal server error: {str(e)}"}, 500

        @app.before_request
        def log_request_info():
            logger.debug('Headers: %s', request.headers)
            logger.debug('Body: %s', request.get_data())

        @app.after_request
        def log_response_info(response):
            logger.debug('Response: %s', response.get_data())
            return response
            
        return app
    except Exception as e:
        logger.error(f"Failed to create application: {str(e)}", exc_info=True)
        raise

try:
    logger.info("Initializing application")
    app = create_app()
    app_state = AppState()
    logger.info("Application initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize application: {str(e)}", exc_info=True)
    raise

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)