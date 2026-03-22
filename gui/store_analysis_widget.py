import logging
import re
from datetime import datetime
from collections import defaultdict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QListWidget, QPushButton, QAbstractItemView, QTableWidget, 
    QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt

from gui.data_cache import load_all_nfce_data
from gui.formatting_utils import parse_val_brl, fmt_brl, NumericTableWidgetItem
from gui.export_mixin import ExportMixin

logger = logging.getLogger('gui.store_analysis')

class StoreAnalysisWidget(QWidget, ExportMixin):
    """
    Widget da aba Análise por Loja (Vendedor).
    """
    def __init__(self):
        super().__init__()
        ExportMixin.__init__(self)
        self.current_theme = "claro" # Estado do tema
        self.setContentsMargins(0, 0, 0, 0)
        self._init_ui()
        try:
            self._load_filters()
            self.update_analysis()
        except Exception as e:
            logger.error(f"Erro inicial ao construir StoreAnalysis: {e}", exc_info=True)

    def get_export_filename_prefix(self):
        return "analise_gastos_loja"

    def set_theme_mode(self, theme_name):
        """Chamado pela MainWindow para atualizar o tema."""
        self.current_theme = theme_name
        self.update_analysis()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        filt_layout = QHBoxLayout()
        filt_layout.addWidget(QLabel("Ano:"))
        self.year_combo = QComboBox()
        self.year_combo.currentIndexChanged.connect(self.update_analysis)
        filt_layout.addWidget(self.year_combo)

        filt_layout.addWidget(QLabel("CPFs:"))
        self.cpf_list = QListWidget()
        self.cpf_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.cpf_list.itemSelectionChanged.connect(self.update_analysis)
        self.cpf_list.setFixedHeight(60)
        filt_layout.addWidget(self.cpf_list)
        
        layout.addLayout(filt_layout)
        
        content_layout = QHBoxLayout()
        
        self.figure = plt.Figure(figsize=(7, 4), tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        # Fundo transparente para integrar com QSS
        self.canvas.setStyleSheet("background-color:transparent;") 
        content_layout.addWidget(self.canvas, 6)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Loja (Vendedor)", "Total Gasto (R$)", "% do Total", "Nº de Compras"])
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        content_layout.addWidget(self.table, 4)

        layout.addLayout(content_layout)
        
        self.total_label = QLabel("Total Gasto (Seleção): R$ 0,00")
        self.total_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        layout.addWidget(self.total_label, alignment=Qt.AlignmentFlag.AlignRight)
        
        layout.addLayout(self._create_export_buttons_layout())

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
        if anos:
            self.year_combo.addItems(sorted([str(a) for a in anos], reverse=True))
        else:
            self.year_combo.addItem(str(datetime.now().year))

        self.cpf_list.clear()
        self.cpf_list.addItem("Todos")
        cpf_items = [item for item in sorted(list(cpfs)) if item != "Todos"]
        self.cpf_list.addItems(cpf_items)
        self.cpf_list.item(0).setSelected(True)

    def refresh_data(self):
        self._load_filters()
        self.update_analysis()

    def update_analysis(self):
        try:
            year = int(self.year_combo.currentText())
        except:
            year = datetime.now().year
            
        selected_items = self.cpf_list.selectedItems()
        selected_cpfs = [i.text() for i in selected_items]
        if not selected_cpfs or "Todos" in selected_cpfs:
            selected_cpfs = None 
        else:
            selected_cpfs = set(selected_cpfs)

        all_nfce_data = load_all_nfce_data()
        
        gastos_por_loja = defaultdict(float)
        compras_por_loja = defaultdict(int)

        for js in all_nfce_data:
            dt = js.get('_datetime')
            if not dt or dt == datetime.min: continue
            if dt.year != year: continue
            
            cpf = js.get("consumidor", {}).get("cpf") or "Não informado"
            if selected_cpfs and cpf not in selected_cpfs:
                continue
            
            vend = js.get("vendedor", {}).get("razao_social", "Desconhecido")
            val = parse_val_brl(js.get("totais", {}).get("valor_total", "0"))
            
            gastos_por_loja[vend] += val
            compras_por_loja[vend] += 1

        total_geral = sum(gastos_por_loja.values())
        lojas_ordenadas = sorted(gastos_por_loja.items(), key=lambda x: x[1], reverse=True)

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(lojas_ordenadas))
        
        for i, (loja, total) in enumerate(lojas_ordenadas):
            percentual = (total / total_geral) * 100 if total_geral > 0 else 0
            num_compras = compras_por_loja.get(loja, 0)
            
            self.table.setItem(i, 0, NumericTableWidgetItem(loja))
            
            item_total = NumericTableWidgetItem(fmt_brl(total))
            item_total.setData(Qt.ItemDataRole.UserRole, total)
            self.table.setItem(i, 1, item_total)
            
            item_perc = NumericTableWidgetItem(f"{percentual:.2f}%")
            item_perc.setData(Qt.ItemDataRole.UserRole, percentual)
            self.table.setItem(i, 2, item_perc)
            
            item_comp = NumericTableWidgetItem(str(num_compras))
            item_comp.setData(Qt.ItemDataRole.UserRole, num_compras)
            self.table.setItem(i, 3, item_comp)

        self.table.setSortingEnabled(True)
        self.total_label.setText(f"Total Gasto (Seleção): {fmt_brl(total_geral)}")

        # --- GRÁFICO COM SUPORTE A TEMA ---
        self.figure.clear()
        
        # Definição de Cores
        is_dark = (self.current_theme == 'escuro')
        bg_color = '#2b2b2b' if is_dark else '#ffffff'
        text_color = 'white' if is_dark else 'black'
        bar_color = '#e67e22' if is_dark else '#d35400' # Laranja escuro
        
        self.figure.patch.set_facecolor(bg_color)
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(bg_color)
        
        top_lojas = lojas_ordenadas[:15]
        lojas_nomes = [item[0] for item in top_lojas][::-1]
        lojas_valores = [item[1] for item in top_lojas][::-1]

        if lojas_nomes:
            bars = ax.barh(lojas_nomes, lojas_valores, color=bar_color)
            ax.set_title(f"Top 15 Lojas por Gasto (Ano: {year})", color=text_color)
            ax.set_xlabel("Total Gasto (R$)", color=text_color)
            
            # Cores dos eixos e bordas
            ax.tick_params(axis='x', colors=text_color)
            ax.tick_params(axis='y', colors=text_color)
            for spine in ax.spines.values():
                spine.set_color(text_color)
            
            for bar in bars:
                width = bar.get_width()
                ax.text(width * 1.01, bar.get_y() + bar.get_height()/2, 
                        fmt_brl(width), va='center', ha='left', fontsize=8, color=text_color)
            
            ax.set_xlim(right=max(lojas_valores) * 1.15 if lojas_valores else 1)
            self.figure.tight_layout()
        else:
            ax.text(0.5, 0.5, "Sem dados", ha="center", va="center", color=text_color)
        self.canvas.draw()