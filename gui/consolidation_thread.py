import logging
from PyQt6.QtCore import QThread, pyqtSignal

try:
    from consolidate_ods import run_consolidation
except ImportError:
    logging.error("Falha ao importar 'consolidate_ods.py'.")
    run_consolidation = None

logger = logging.getLogger('gui.consolidation_thread')

class ConsolidationThread(QThread):
    consolidation_complete = pyqtSignal(bool, str)

    def __init__(self):
        super().__init__()

    def run(self):
        if not run_consolidation:
            self.consolidation_complete.emit(False, "Erro: Script 'consolidate_ods.py' não encontrado.")
            return
        try:
            logger.info("Iniciando consolidação...")
            sucesso, mensagem = run_consolidation()
            self.consolidation_complete.emit(sucesso, mensagem)
        except Exception as e:
            logger.error(f"Erro fatal na thread: {e}", exc_info=True)
            self.consolidation_complete.emit(False, f"Erro inesperado: {e}")