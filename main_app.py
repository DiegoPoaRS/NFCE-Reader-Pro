import sys
import json
import logging
from PyQt6.QtWidgets import QApplication

# Nossos módulos
from logging_setup import setup_logging, get_logger
from gui.main_window import MainWindow

def load_config(config_path='config.json'):
    """Carrega o arquivo de configuração."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print(f"ERRO: 'config.json' não encontrado. Crie um config.json.")
        return None
    except Exception as e:
        print(f"ERRO: Falha ao ler 'config.json': {e}")
        return None

def main():
    # 1. Configurar o logging (primeiro passo)
    setup_logging()
    logger = get_logger('main_app')

    # 2. Carregar o Config
    logger.info("Iniciando aplicação...")
    config = load_config()
    if not config:
        logger.error("Aplicação encerrada devido a erro no config.json.")
        return

    # 3. Iniciar a Aplicação GUI
    app = QApplication(sys.argv)
    
    try:
        window = MainWindow(config)
        window.show()
        logger.info("Janela principal exibida.")
        sys.exit(app.exec())
    except Exception as e:
        logger.critical(f"Erro fatal ao iniciar a GUI: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()