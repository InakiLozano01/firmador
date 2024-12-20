# Description: Módulo para mantener el estado de la aplicación
from app.utils.image_utils import encode_image
from app.config.settings import settings

class AppState:
    def __init__(self):
        self.current_time = None
        self.datetimesigned = None
        self.conn = None
        self.encoded_image = encode_image(settings.LOGO_PATH)
        self.isclosing = None

app_state = AppState()