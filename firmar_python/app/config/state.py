# Description: Módulo para mantener el estado de la aplicación

from app.utils.image_utils import encode_image
class AppState:
    def __init__(self):
        self.current_time = None
        self.datetimesigned = None
        self.conn = None
        self.encoded_image = encode_image("../assets/images/logo_tribunal_para_tapir_250px.png")
        self.isclosing = None

app_state = AppState()