import logging
from flask import Flask
from app.config.settings import settings
from app.config.state import app_state
from app.routes.issuer_resolve_route import register_issuer_resolve_routes
from app.routes.routes import register_routes
from app.routes.documento_externo import register_documento_externo_routes
from app.services.observability import install_observability_logging
from app.utils.saving import recover_pending_repairs

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.OBS_LOG_LEVEL.upper(), logging.INFO),
    format='%(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
install_observability_logging()

def create_app():
    try:
        logger.info('Creating Flask application')
        app = Flask(__name__)
        
        # Configuration
        app.config['MAX_CONTENT_LENGTH'] = 500000000
        app.json.sort_keys = False
        
        # Register routes
        register_routes(app)
        register_documento_externo_routes(app)
        register_issuer_resolve_routes(app)
        logger.info('Routes registered successfully')
        recovered_repairs = recover_pending_repairs()
        if recovered_repairs:
            logger.warning("Recovered %s pending repair file(s) at startup", len(recovered_repairs))

        # Add error handlers
        @app.errorhandler(Exception)
        def handle_exception(e):
            logger.error(f'Unhandled exception: {str(e)}', exc_info=True)
            return {'status': False, 'message': 'Internal server error'}, 500

        return app
    except Exception as e:
        logger.error(f'Failed to create application: {str(e)}', exc_info=True)
        raise

try:
    logger.info('Initializing application')
    app = create_app()
    app_state.load_settings()
    logger.info('Application initialized successfully')
except Exception as e:
    logger.error(f'Failed to initialize application: {str(e)}', exc_info=True)
    raise


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False, port=5000)
