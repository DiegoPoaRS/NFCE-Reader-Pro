import logging
from PyQt6.QtCore import QThread, pyqtSignal
from services.scraping_service import NFCeScraper

logger = logging.getLogger('gui.scraping_thread')

class ScrapingThread(QThread):
    # Sinal: Emite o dicionário de dados da NF-e quando termina
    scraping_complete = pyqtSignal(dict)
    # Sinal: Emite uma mensagem de erro se falhar
    scraping_error = pyqtSignal(str)

    def __init__(self, scraper_instance: NFCeScraper, url: str):
        super().__init__()
        self.scraper = scraper_instance
        self.url = url
        logger.debug("ScrapingThread criada.")

    def run(self):
        try:
            logger.info(f"ScrapingThread: Iniciando extração da URL.")
            data = self.scraper.extrair_dados(self.url)
            
            if data:
                logger.info(f"ScrapingThread: Extração concluída.")
                self.scraping_complete.emit(data)
            else:
                logger.error(f"ScrapingThread: O scraper não retornou dados.")
                self.scraping_error.emit("O scraper não retornou dados.")
                
        except Exception as e:
            logger.error(f"ScrapingThread: Erro fatal na thread: {e}", exc_info=True)
            self.scraping_error.emit(f"Erro na thread de scraping: {e}")