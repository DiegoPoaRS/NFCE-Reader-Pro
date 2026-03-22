import logging
import requests
import threading
from datetime import datetime
import os
import sys
import json
import subprocess 

# Tenta importar winsound
try:
    import winsound
except ImportError:
    winsound = None

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem, QMessageBox,
    QStackedWidget, QApplication, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QPainter, QFont, QAction, QColor, QPalette

# Componentes da GUI
from gui.camera_thread import CameraThread
from gui.scraping_thread import ScrapingThread
from gui.consolidation_thread import ConsolidationThread
from gui.dashboard_widget import DashboardWidget
from gui.items_abc_widget import ItemsABCWidget
from gui.store_analysis_widget import StoreAnalysisWidget 
from gui.ods_monitor_widget import ODSMonitorWidget
from gui.health_widget import HealthWidget 
from gui.tax_analysis_widget import TaxAnalysisWidget
from gui.settings_widget import SettingsWidget
from gui.refine_items_widget import RefineItemsWidget # <--- NOVO IMPORT
from gui.data_cache import load_all_nfce_data, configure_cache

from services.scraping_service import NFCeScraper

logger = logging.getLogger('gui.main_window')

# --- DEFINIÇÃO DO TEMA ESCURO (QSS) ---
DARK_STYLE_QSS = """
QMainWindow, QWidget { background-color: #2b2b2b; color: #e0e0e0; }
QTableWidget { background-color: #1e1e1e; color: #ffffff; gridline-color: #444; border: 1px solid #444; }
QTableWidget::item { padding: 5px; }
QHeaderView::section { background-color: #333; color: #fff; border: 1px solid #444; padding: 4px; }
QListWidget { background-color: #1e1e1e; color: #fff; border: 1px solid #444; }
QListWidget::item:selected { background-color: #3d8ec9; }
QLabel { color: #e0e0e0; }
QPushButton { background-color: #3c3f41; color: #fff; border: 1px solid #555; padding: 6px; border-radius: 4px; }
QPushButton:hover { background-color: #484a4c; border-color: #666; }
QPushButton:pressed { background-color: #2c2e30; }
QComboBox { background-color: #3c3f41; color: #fff; border: 1px solid #555; padding: 4px; }
QComboBox QAbstractItemView { background-color: #3c3f41; color: #fff; selection-background-color: #3d8ec9; }
QScrollBar:vertical { background: #2b2b2b; width: 12px; }
QScrollBar::handle:vertical { background: #555; min-height: 20px; border-radius: 4px; }
QMenuBar { background-color: #2b2b2b; color: #fff; }
QMenuBar::item:selected { background-color: #3d8ec9; }
QMenu { background-color: #333; color: #fff; border: 1px solid #555; }
QMenu::item:selected { background-color: #3d8ec9; }
QFrame#card_frame { 
    background-color: #3e3e42; 
    border: 1px solid #555; 
    border-radius: 8px; 
}
QLabel#card_title { color: #aaaaaa; font-size: 14px; }
QLabel#card_value { color: #ffffff; font-size: 22px; font-weight: bold; }
QTabWidget::pane { border: 1px solid #444; }
QTabBar::tab { background: #333; color: #fff; padding: 8px; }
QTabBar::tab:selected { background: #3d8ec9; }
"""

class MainWindow(QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.scraper = NFCeScraper(config)
        self.camera_thread = None
        self.scraping_thread = None
        self.consolidation_thread = None

        configure_cache(config)

        self.setWindowTitle(config.get('app_name', 'NFCe Reader Pro ODS'))
        self.setGeometry(40, 40, 1350, 800)

        self.stackedWidget = QStackedWidget()

        # Tela 0: Leitor
        self.mainViewWidget = QWidget()
        self.mainViewWidget.setLayout(self._create_main_view_layout())
        self.stackedWidget.addWidget(self.mainViewWidget) 

        # Tela 1: Dashboard
        self.dashboard_widget = DashboardWidget()
        self.stackedWidget.addWidget(self.dashboard_widget) 

        # Tela 2: Itens ABC
        self.items_widget = ItemsABCWidget()
        self.stackedWidget.addWidget(self.items_widget) 
        
        # Tela 3: Lojas
        self.store_widget = StoreAnalysisWidget()
        self.stackedWidget.addWidget(self.store_widget) 
        
        # Tela 4: ODS Ambiental
        self.ods_monitor_widget = ODSMonitorWidget()
        self.stackedWidget.addWidget(self.ods_monitor_widget) 
        
        # Tela 5: ODS Saúde
        self.health_widget = HealthWidget(self.config)
        self.stackedWidget.addWidget(self.health_widget)

        # Tela 6: Impostos
        self.tax_widget = TaxAnalysisWidget()
        self.stackedWidget.addWidget(self.tax_widget) 
        
        # Tela 7: Configurações
        self.settings_widget = SettingsWidget(self.config, self)
        self.stackedWidget.addWidget(self.settings_widget)

        # Tela 8: Refinar Itens (NOVO)
        self.refine_widget = RefineItemsWidget(self.config)
        self.stackedWidget.addWidget(self.refine_widget)

        self.setCentralWidget(self.stackedWidget)
        self._init_menubar()
        
        self.load_existing_summaries()
        self._show_initial_camera()

        current_theme = self.config.get('theme', 'claro')
        self._apply_theme(current_theme)

        logger.info("MainWindow inicializada.")

    def _init_menubar(self):
        menuBar = self.menuBar()

        viewMenu = menuBar.addMenu("Visualizar")
        viewMenu.addAction(QAction("Leitor Principal", self, triggered=lambda: self._show_view(0)))

        analiseMenu = menuBar.addMenu("Análises")
        analiseMenu.addAction(QAction("Dashboard Financeiro", self, triggered=lambda: self._show_view(1)))
        analiseMenu.addAction(QAction("Análise de Itens (ABC)", self, triggered=lambda: self._show_view(2)))
        analiseMenu.addAction(QAction("Análise por Loja", self, triggered=lambda: self._show_view(3)))
        analiseMenu.addAction(QAction("Monitor ODS 12/13 (Ambiental)", self, triggered=lambda: self._show_view(4)))
        analiseMenu.addAction(QAction("Monitor ODS 3 (Saúde)", self, triggered=lambda: self._show_view(5)))
        analiseMenu.addAction(QAction("Análise de Impostos", self, triggered=lambda: self._show_view(6)))
        
        toolsMenu = menuBar.addMenu("Ferramentas")
        toolsMenu.addAction(QAction("Refinar Classificação de Itens", self, triggered=lambda: self._show_view(8))) # NOVO
        toolsMenu.addAction(QAction("Rodar Consolidador ODS (CSV)", self, triggered=self._run_consolidate_ods))
        
        configMenu = menuBar.addMenu("Configurações")
        configMenu.addAction(QAction("Abrir Configurações", self, triggered=lambda: self._show_view(7)))
        
        helpMenu = menuBar.addMenu("Ajuda")
        helpMenu.addAction(QAction("Sobre", self, triggered=self._show_about_dialog))

    def _apply_theme(self, theme_name):
        app = QApplication.instance()
        if theme_name == 'escuro':
            app.setStyleSheet(DARK_STYLE_QSS)
        else:
            app.setStyleSheet("")
        
        for i in range(self.stackedWidget.count()):
            widget = self.stackedWidget.widget(i)
            if hasattr(widget, 'set_theme_mode'):
                widget.set_theme_mode(theme_name)

    def _create_main_view_layout(self):
        root = QHBoxLayout()
        left = QVBoxLayout()
        
        lbl = QLabel("Leitor de NFC-e Inteligente (ODS)")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("font-size:24px; font-weight:bold;")
        left.addWidget(lbl)

        self.camera_label = QLabel()
        self.camera_label.setFixedSize(640, 480)
        self.camera_label.setStyleSheet("background:black; border-radius:8px;")
        self.camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left.addWidget(self.camera_label)

        self.status_label = QLabel("Pressione INICIAR")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size:16px; padding:8px; border-radius:6px;")
        left.addWidget(self.status_label)

        # Botões
        btns = QHBoxLayout()
        
        self.start_btn = QPushButton("INICIAR CÂMERA")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setToolTip("Liga a webcam para ler o QR Code da nota fiscal.")
        self.start_btn.clicked.connect(self._toggle_camera)
        btns.addWidget(self.start_btn)
        
        self.reset_btn = QPushButton("RESETAR CÂMERA")
        self.reset_btn.setMinimumHeight(40)
        self.reset_btn.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold;")
        self.reset_btn.setToolTip("Clique aqui se a câmera travar ou parar de responder.")
        self.reset_btn.clicked.connect(self._reset_camera)
        btns.addWidget(self.reset_btn)

        self.focus_btn = QPushButton("AUTO FOCUS")
        self.focus_btn.setMinimumHeight(40)
        self.focus_btn.setToolTip("Tenta focar a lente da câmera (apenas para câmeras IP compatíveis).")
        self.focus_btn.clicked.connect(self._trigger_autofocus)
        btns.addWidget(self.focus_btn)
        
        left.addLayout(btns)
        
        stats_layout = QHBoxLayout()
        self.loaded_label = QLabel("Total Salvo: 0")
        self.scanned_label = QLabel("Sessão Atual: 0")
        self.scan_count = 0
        stats_layout.addWidget(self.loaded_label)
        stats_layout.addWidget(self.scanned_label)
        left.addLayout(stats_layout)
        
        left.addStretch()

        right = QVBoxLayout()
        right.addWidget(QLabel("Resumo das notas carregadas (Mais recentes primeiro):"))
        self.list_widget = QListWidget()
        right.addWidget(self.list_widget)

        root.addLayout(left, 4)
        root.addLayout(right, 6)
        return root

    def _show_view(self, index):
        if self.camera_thread and self.camera_thread.isRunning():
            self.camera_thread.paused = (index != 0)
        
        if index == 8: # Se for a tela de Refinar
            # Recarrega a lista para pegar novos items que possam ter sido lidos
            self.refine_widget.load_unclassified_items()

        if index > 0 and index != 7 and index != 8: 
            self._refresh_dashboards()
            
        self.stackedWidget.setCurrentIndex(index)

    def _show_initial_camera(self):
        pix = QPixmap(self.camera_label.size())
        pix.fill(Qt.GlobalColor.black)
        p = QPainter(pix)
        p.setPen(Qt.GlobalColor.white)
        p.setFont(QFont("Segoe UI", 16))
        p.drawText(self.camera_label.rect(), Qt.AlignmentFlag.AlignCenter, "Câmera Parada")
        p.end()
        self.camera_label.setPixmap(pix)

    def _toggle_camera(self):
        if self.camera_thread and self.camera_thread.isRunning():
            self.camera_thread.stop()
            self.start_btn.setText("INICIAR CÂMERA")
            self._show_initial_camera()
        else:
            self._start_camera_thread()

    def _start_camera_thread(self):
        self.camera_thread = CameraThread(self.config)
        self.camera_thread.update_frame.connect(self._update_camera_frame)
        self.camera_thread.camera_error.connect(self._on_camera_error)
        self.camera_thread.qr_code_detected.connect(self._on_qr_detected)
        self.camera_thread.start()
        self.start_btn.setText("PARAR CÂMERA")
        self._update_status("Câmera ativa. Aguardando QR Code.", "green")

    def _reset_camera(self):
        logger.warning("Resetando câmera forçadamente...")
        if self.camera_thread:
            self.camera_thread.running = False 
            self.camera_thread.quit()
            if not self.camera_thread.wait(1000):
                self.camera_thread.terminate()
            self.camera_thread = None
        
        self.start_btn.setText("INICIAR CÂMERA")
        self._show_initial_camera()
        self._update_status("Câmera resetada. Tente iniciar novamente.", "orange")
        QMessageBox.information(self, "Reset", "O serviço de câmera foi reiniciado.")

    def _play_success_sound(self):
        if winsound:
            try:
                winsound.Beep(1500, 200)
            except:
                pass

    def _on_qr_detected(self, url):
        self._play_success_sound()
        self._update_status(f"QR Code NF-e detectado! Iniciando extração...", "orange")
        self.scraping_thread = ScrapingThread(self.scraper, url)
        self.scraping_thread.scraping_complete.connect(self._on_scraping_complete)
        self.scraping_thread.scraping_error.connect(self._on_scraping_error)
        self.scraping_thread.finished.connect(self._on_scraping_finished)
        self.scraping_thread.start()

    def _on_scraping_complete(self, nfce_data):
        logger.info("Scraping concluído. Atualizando GUI.")
        self.scan_count += 1
        self.scanned_label.setText(f"Lidas Nesta Sessão: {self.scan_count}")
        self._update_status(f"Sucesso! {len(nfce_data.get('produtos',[]))} itens salvos.", "green")
        self._play_success_sound()
        load_all_nfce_data(force_reload=True)
        self.load_existing_summaries(initial_load=False)

    def _on_scraping_error(self, error_msg):
        logger.error(f"Erro no scraping: {error_msg}")
        self._update_status(f"Falha no scraping: {error_msg}", "red")
        self._on_scraping_finished()

    def _on_scraping_finished(self):
        if self.camera_thread and self.camera_thread.isRunning():
            self.camera_thread.release_lock()
        self.scraping_thread = None

    def _on_camera_error(self, error_msg):
        QMessageBox.critical(self, "Erro de Câmera", error_msg)
        self.start_btn.setText("INICIAR CÂMERA")
        self.camera_thread = None

    def _trigger_autofocus(self):
        url = self.config.get('camera_autofocus_url')
        if not url:
            self._update_status("URL de Auto Focus não configurada.", "red")
            return
        threading.Thread(target=self._run_focus_request, daemon=True).start()

    def _run_focus_request(self):
        url = self.config.get('camera_autofocus_url')
        try:
            requests.get(url, timeout=1.5)
            logger.info("Auto Foco acionado.")
        except Exception as e:
            logger.warning(f"Falha no Auto Focus: {e}")

    def _update_camera_frame(self, pixmap):
        self.camera_label.setPixmap(pixmap.scaled(
            self.camera_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        ))

    def _update_status(self, text, color):
        colors = {"green":"#27ae60", "red":"#e74c3c", "orange":"#f39c12", "black": "#34495e"}
        if self.config.get('theme') == 'escuro':
            colors['black'] = '#555555'
        style = f"background-color:{colors.get(color, '#95a5a6')}; color:white; padding:8px; border-radius:6px;"
        self.status_label.setText(text)
        self.status_label.setStyleSheet(style)

    def _refresh_dashboards(self):
        logger.debug("Atualizando dados dos dashboards...")
        try:
            self.dashboard_widget.refresh_data()
            self.items_widget.refresh_data()
            self.store_widget.refresh_data()
            self.ods_monitor_widget.refresh_data()
            self.health_widget.refresh_data()
            self.tax_widget.refresh_data()
        except Exception as e:
            logger.error(f"Falha ao atualizar dashboards: {e}", exc_info=True)

    def load_existing_summaries(self, initial_load=True):
        self.list_widget.clear()
        all_nfce_data = load_all_nfce_data(force_reload=initial_load)
        sorted_data = sorted(all_nfce_data, key=lambda x: x.get('_datetime', datetime.min), reverse=True)
        for js in sorted_data:
            data = js.get("geral", {}).get("data_emissao", "N/A")
            vend = js.get("vendedor", {}).get("razao_social", "N/A")[:30]
            tot = js.get("totais", {}).get("valor_total", "N/A")
            cpf = js.get("consumidor", {}).get("cpf") or "Não informado"
            num_itens = len(js.get("produtos", []))
            if js.get("geral", {}).get("status_nota") == "CANCELADA":
                vend = "[CANCELADA]"
            self.list_widget.addItem(f"{data} | {vend} | {num_itens} Itens | R$ {tot} | {cpf}")
        self.loaded_label.setText(f"Total de Notas Salvas: {len(sorted_data)}")

    def closeEvent(self, event):
        logger.info("Fechando a aplicação...")
        if self.camera_thread:
            self.camera_thread.stop()
        if self.scraper:
            self.scraper.close_driver()
        event.accept()
    
    def _run_consolidate_ods(self):
        if self.consolidation_thread and self.consolidation_thread.isRunning():
            QMessageBox.warning(self, "Aguarde", "A consolidação já está em execução.")
            return
        reply = QMessageBox.question(
            self, "Confirmar Consolidação", 
            "Isso irá ler todos os JSONs e gerar um novo arquivo CSV na pasta 'nfce_consolidado'.\nDeseja continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No: return
        logger.info("Iniciando thread de consolidação...")
        self.consolidation_thread = ConsolidationThread()
        self.consolidation_thread.consolidation_complete.connect(self._on_consolidation_finished)
        self.consolidation_thread.start()
        QMessageBox.information(self, "Iniciado", "A consolidação foi iniciada em segundo plano.")

    def _on_consolidation_finished(self, sucesso, mensagem):
        if sucesso:
            QMessageBox.information(self, "Consolidação Concluída", mensagem)
        else:
            QMessageBox.critical(self, "Erro na Consolidação", mensagem)
        self.consolidation_thread = None
    
    def _show_about_dialog(self):
        QMessageBox.about(self, "Sobre", "<b>NFCe Reader Pro ODS v2.0</b><br>Desenvolvido para projeto de extensão.<br>Foco: ODS 3, 12 e 13.")