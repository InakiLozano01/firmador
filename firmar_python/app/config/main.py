import logging
from flask import Flask

##################################################
###      Configuracion de aplicacion Flask     ###
##################################################
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500000000
app.json.sort_keys = False


logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)