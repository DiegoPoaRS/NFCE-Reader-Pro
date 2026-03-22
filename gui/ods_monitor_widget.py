import logging
from datetime import datetime
from collections import defaultdict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QListWidget, QAbstractItemView, QGridLayout, QFrame, 
    QHeaderView, QTableWidget, QTableWidgetItem
)
from PyQt6.QtCore import Qt

# Matplotlib para gráficos
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt

# Nossos Módulos
from gui.data_cache import load_all_nfce_data
from gui.formatting_utils import fmt_brl
from gui.export_mixin import ExportMixin
from services import sustentabilidade_service as sust_service 

logger = logging.getLogger('gui.ods_monitor')

class ODSMonitorWidget(QWidget, ExportMixin):
    """
    Widget da Análise de Sustentabilidade e ODS (Pegada de Carbono e Metas).
    """
    def __init__(self):
        super().__init__()
        ExportMixin.__init__(self)
        self.current_theme = "claro"
        self.setContentsMargins(0, 0, 0, 0)
        self.metas_config = sust_service.load_sustainability_map().get('metas_ods', {})
        
        self._init_ui()
        try:
            self._load_filters()
            self.update_analysis()
        except Exception as e:
            logger.error(f"Erro inicial ao construir ODSMonitor: {e}", exc_info=True)

    def get_export_filename_prefix(self):
        return "analise_ods_carbono"

    def set_theme_mode(self, theme_name):
        self.current_theme = theme_name
        self.update_analysis() # Recalcula e redesenha tudo

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        title = QLabel("Monitoramento ODS 12/13 — Pegada de Carbono")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:16px; font-weight:bold;")
        layout.addWidget(title)

        # --- Filtros ---
        filt = QHBoxLayout()
        filt.addWidget(QLabel("Ano:"))
        self.year_combo = QComboBox() 
        self.year_combo.setFixedWidth(80)
        self.year_combo.currentIndexChanged.connect(self.update_analysis)
        filt.addWidget(self.year_combo)
        
        filt.addWidget(QLabel("Mês:"))
        self.month_combo = QComboBox()
        self.month_combo.setFixedWidth(80)
        self.month_combo.addItem("Todos")
        for i in range(1, 13):
            self.month_combo.addItem(f"{i:02d}")
        self.month_combo.currentIndexChanged.connect(self.update_analysis)
        filt.addWidget(self.month_combo)
        
        filt.addWidget(QLabel("CPFs:"))
        self.cpf_list = QListWidget()
        self.cpf_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.cpf_list.itemSelectionChanged.connect(self.update_analysis)
        self.cpf_list.setFixedHeight(80)
        filt.addWidget(self.cpf_list, 1)
        layout.addLayout(filt)

        # --- Cards de Status ---
        cards_layout = QGridLayout()
        self.card_carbono = self._make_card("Pegada de Carbono (Total)", "0.0 kg CO₂e", "Meta: < 100 kg")
        self.card_vegetal = self._make_card("% Gasto em Vegetais", "0.0 %", "Meta: > 35 %")
        cards_layout.addWidget(self.card_carbono, 0, 0)
        cards_layout.addWidget(self.card_vegetal, 0, 1)
        layout.addLayout(cards_layout)

        # --- Gráfico e Tabela ---
        content_layout = QHBoxLayout()
        self.figure = plt.Figure(figsize=(7, 4), tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet("background-color:transparent;")
        content_layout.addWidget(self.canvas, 6)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Categoria ODS", "Carbono (kg CO₂e)", "Gasto Total (R$)"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        content_layout.addWidget(self.table, 4)
        layout.addLayout(content_layout)
        
        layout.addLayout(self._create_export_buttons_layout())

    def _make_card(self, title, value, meta):
        f = QFrame()
        f.setObjectName("card_frame_ods") # ID diferente para não conflitar com o CSS padrão se quisermos customizar
        l = QVBoxLayout(f)
        
        t = QLabel(title)
        t.setObjectName("card_title")
        
        v = QLabel(value)
        v.setObjectName("val") # ID específico para busca
        
        m = QLabel(meta)
        m.setObjectName("meta_label") # ID específico para busca
        
        l.addWidget(t)
        l.addWidget(v)
        l.addWidget(m)
        return f

    def _load_filters(self):
        all_nfce_data = load_all_nfce_data()
        anos = set()
        cpfs = set()
        cpfs.add("Não informado")
        for js in all_nfce_data:
            dt = js.get('_datetime')
            if dt and dt != datetime.min:
                anos.add(dt.year)
            cpf = js.get("consumidor", {}).get("cpf", "Não informado")
            cpfs.add(cpf or "Não informado")
        
        self.year_combo.clear()
        self.year_combo.addItems(sorted([str(a) for a in anos], reverse=True))
        self.cpf_list.clear()
        self.cpf_list.addItem("Todos")
        cpf_items = [item for item in sorted(list(cpfs)) if item != "Todos"]
        self.cpf_list.addItems(cpf_items)
        self.cpf_list.item(0).setSelected(True)

    def _get_selected_cpfs(self):
        items = [it.text() for it in self.cpf_list.selectedItems()]
        if not items or "Todos" in items: return None
        return set(items)

    def _filter_nfce_data(self, data, year, month, selected_cpfs):
        filtered_data = []
        for nfce in data:
            dt = nfce.get('_datetime')
            if not dt or dt == datetime.min: continue
            if dt.year != year: continue
            if month != "Todos" and dt.strftime("%m") != month: continue
            cpf = nfce.get("consumidor", {}).get("cpf") or "Não informado"
            if selected_cpfs is not None and cpf not in selected_cpfs: continue
            filtered_data.append(nfce)
        return filtered_data

    def update_analysis(self):
        try:
            if not hasattr(self, 'year_combo'): return 
            year = int(self.year_combo.currentText())
        except ValueError:
            year = datetime.now().year
            
        month = self.month_combo.currentText()
        selected_cpfs = self._get_selected_cpfs()
        all_nfce_data = load_all_nfce_data()
        
        filtered_data = self._filter_nfce_data(all_nfce_data, year, month, selected_cpfs)
        metrics = sust_service.calculate_ods_metrics(filtered_data)
        
        total_carbon = metrics['total_carbon_footprint']
        pct_vegetal = metrics['pct_gasto_vegetal']
        
        self._update_card_status(self.card_carbono, total_carbon, metrics['status_carbono'], 'kg CO₂e')
        self._update_card_status(self.card_vegetal, pct_vegetal, metrics['status_vegetal'], '%')
        
        self._update_table(metrics['carbon_by_category'], metrics['gasto_by_category'])
        self._update_chart(metrics['carbon_by_category'], year, month)
        
    def _update_card_status(self, card_frame, value, status, unit):
        val_label = card_frame.findChild(QLabel, "val")
        meta_label = card_frame.findChild(QLabel, "meta_label")
        
        # Cores de Status
        if status == "Excedida" or status == "Não Atingida":
            color = "#e74c3c" # Vermelho
            icon = "❌"
        elif status == "Atingida":
            color = "#27ae60" # Verde
            icon = "✅"
        else:
            color = "#3498db" # Azul
            icon = "❓"

        # Cor de Fundo baseada no Tema
        is_dark = (self.current_theme == 'escuro')
        bg_color = "#333333" if is_dark else "#f7f9fc"
        border_color = "#444" if is_dark else "#dfe7ef"
        text_val_color = color # A cor do valor segue o status
        
        val_label.setText(f"{value:.2f} {unit}")
        val_label.setStyleSheet(f"font-size:20px; font-weight:bold; color:{text_val_color};")
        
        # Aplica estilo dinâmico (fundo escuro/claro + borda colorida do status)
        card_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border-radius: 6px;
                border: 2px solid {color}; 
                padding: 10px;
            }}
        """)
        
        meta_text_raw = meta_label.text().split(" (")[0]
        meta_label.setText(f"{meta_text_raw} ({icon} {status})")

    def _update_table(self, carbon_data, gasto_data):
        categories = sorted(carbon_data.keys())
        self.table.setRowCount(len(categories))
        for i, cat in enumerate(categories):
            carbon = carbon_data.get(cat, 0.0)
            gasto = gasto_data.get(cat, 0.0)
            self.table.setItem(i, 0, QTableWidgetItem(cat.replace("_", " ")))
            self.table.setItem(i, 1, QTableWidgetItem(f"{carbon:.2f}"))
            self.table.setItem(i, 2, QTableWidgetItem(fmt_brl(gasto)))

    def _update_chart(self, carbon_data, year, month):
        self.figure.clear()
        
        # Cores do Tema
        is_dark = (self.current_theme == 'escuro')
        bg_color = '#2b2b2b' if is_dark else '#ffffff'
        text_color = 'white' if is_dark else 'black'
        bar_color = '#2ecc71' if is_dark else '#16a085' # Verde ODS

        self.figure.patch.set_facecolor(bg_color)
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(bg_color)
        
        sorted_data = sorted(carbon_data.items(), key=lambda item: item[1], reverse=False)
        categories = [item[0].replace("_", " ") for item in sorted_data]
        values = [item[1] for item in sorted_data]
        
        if categories:
            ax.barh(categories, values, color=bar_color) 
            ax.set_title(f"Pegada de Carbono por Categoria ({month}/{year})", fontsize=10, color=text_color)
            ax.set_xlabel("Pegada de Carbono (kg CO₂e)", color=text_color)
            
            ax.tick_params(axis='x', colors=text_color)
            ax.tick_params(axis='y', colors=text_color)
            for spine in ax.spines.values():
                spine.set_color(text_color)
                
            self.figure.tight_layout() 
        else:
            ax.text(0.5, 0.5, "Sem dados para análise ODS", ha="center", va="center", color=text_color)
            
        self.canvas.draw()
        
    def refresh_data(self):
        self._load_filters()
        self.update_analysis()