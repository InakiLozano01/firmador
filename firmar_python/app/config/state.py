# Description: Módulo para mantener el estado de la aplicación
from app.utils.image_utils import encode_image
from app.config.settings import settings

class AppState:
    def __init__(self):
        self.conn = None
        self.encoded_image = encode_image(settings.LOGO_PATH)
        self.encoded_image_yunga = encode_image(settings.LOGO_YUNGA_PATH)

    def load_settings(self):
        self.conn = None
        self.encoded_image = encode_image(settings.LOGO_PATH)
        self.encoded_image_yunga = encode_image(settings.LOGO_YUNGA_PATH)

app_state = AppState()
