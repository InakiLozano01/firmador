# Description: Módulo para mantener el estado de la aplicación
from app.utils.image_utils import encode_image
from app.config.settings import settings
import time
from datetime import datetime

class AppState:
    def __init__(self):
        self.current_time = None
        self.datetimesigned = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.conn = None
        self.encoded_image = encode_image(settings.LOGO_PATH)
        self.isclosing = None

    def load_settings(self):
        self.current_time = int(time.time() * 1000)
        self.datetimesigned = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.conn = None
        self.encoded_image = encode_image(settings.LOGO_PATH)
        self.isclosing = None

app_state = AppState()