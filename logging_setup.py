import logging
import sys
import json
import os

def setup_logging():
    """Configura o sistema de logging para console e arquivo."""
    
    # 1. Carregar configuração
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        LOG_FILE = config.get('paths', {}).get('log_file', 'nfce_reader.log')
        os.makedirs(os.path.dirname(LOG_FILE) or '.', exist_ok=True)
    except Exception:
        LOG_FILE = 'nfce_reader.log' # Fallback

    # 2. Definir formato
    log_format = '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    formatter = logging.Formatter(log_format, date_format)

    # 3. Configurar o logger raiz
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # 4. Handler de Console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO) # Mostra INFO e acima no console

    # 5. Handler de Arquivo
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG) # Salva TUDO (DEBUG e acima) no arquivo

    # 6. Adicionar handlers (se ainda não existirem)
    if not logger.hasHandlers():
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    logging.info("Sistema de logging iniciado.")

# Função para obter loggers em outros módulos
def get_logger(name):
    return logging.getLogger(name)