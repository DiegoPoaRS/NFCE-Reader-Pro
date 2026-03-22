import logging
from datetime import datetime
from collections import defaultdict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QListWidget, QAbstractItemView, QTableWidget, 
    QTableWidgetItem
)
from PyQt6.QtCore import Qt

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt

from gui.data_cache import load_all_nfce_data
from gui.formatting_utils import parse_val_brl, fmt_brl, NumericTableWidgetItem
from gui.export_mixin import ExportMixin

logger = logging.getLogger('gui.items_abc')

class ItemsABCWidget(QWidget, ExportMixin):
    """
    Widget da aba Itens (Curva ABC).
    """
    def __init__(self, config=None): # <--- Recebe config agora
        super().__init__()
        ExportMixin.__init__(self)
        self.config = config if config else {} # Guarda config
        self.current_theme = "claro"
        self.setContentsMargins(0, 0, 0, 0)
        self._init_ui()
        try:
            self._load_filters()
            self.update_items()
        except Exception as e:
            logger.error(f"Erro inicial ao construir ItemsABC: {e}", exc_info=True)

    def get_export_filename_prefix(self):
        return "analise_itens_abc"
        
    def set_theme_mode(self, theme_name):
        self.current_theme = theme_name
        self.update_items()

    def _init_ui(self):
        # ... (Mesmo código de UI anterior, sem alterações) ...
        layout = QVBoxLayout(self)
        
        filt_layout = QHBoxLayout()
        filt_layout.addWidget(QLabel("Ano:"))
        self.year_combo = QComboBox()
        self.year_combo.currentIndexChanged.connect(self.update_items)
        filt_layout.addWidget(self.year_combo)
        
        filt_layout.addWidget(QLabel("Mês:"))
        self.month_combo = QComboBox()
        self.month_combo.addItem("Todos")
        for i in range(1, 13):
            self.month_combo.addItem(f"{i:02d}")
        self.month_combo.currentIndexChanged.connect(self.update_items)
        filt_layout.addWidget(self.month_combo)

        filt_layout.addWidget(QLabel("CPFs:"))
        self.cpf_list = QListWidget()
        self.cpf_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.cpf_list.itemSelectionChanged.connect(self.update_items)
        self.cpf_list.setFixedHeight(60)
        filt_layout.addWidget(self.cpf_list)
        
        layout.addLayout(filt_layout)

        self.figure = plt.Figure(figsize=(7, 4), tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet("background-color:transparent;")
        layout.addWidget(self.canvas)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Item", "Qtd", "Gasto (R$)", "%", "Acumulado %", "Classe"])
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)
        
        self.total_label = QLabel("Total Gasto (Seleção): R$ 0,00")
        self.total_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        layout.addWidget(self.total_label, alignment=Qt.AlignmentFlag.AlignRight)
        
        layout.addLayout(self._create_export_buttons_layout())

    def _load_filters(self):
        # ... (Mesmo código de load filters) ...
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
        self.update_items()

    def update_items(self):
        # ... (Lógica de filtro igual) ...
        try:
            year = int(self.year_combo.currentText())
        except:
            year = datetime.now().year
            
        month = self.month_combo.currentText()
        
        selected_items = self.cpf_list.selectedItems()
        selected_cpfs = [i.text() for i in selected_items]
        if not selected_cpfs or "Todos" in selected_cpfs:
            selected_cpfs = None 
        else:
            selected_cpfs = set(selected_cpfs)

        all_nfce_data = load_all_nfce_data()
        
        gastos = defaultdict(float)
        qtys = defaultdict(float)

        for js in all_nfce_data:
            dt = js.get('_datetime')
            if not dt or dt == datetime.min: continue
            if dt.year != year: continue
            if month != "Todos" and dt.strftime("%m") != month: continue
            cpf = js.get("consumidor", {}).get("cpf") or "Não informado"
            if selected_cpfs and cpf not in selected_cpfs: continue

            for prod in js.get("produtos", []):
                desc = prod.get("descricao", "N/A")
                val = parse_val_brl(prod.get("valor_total", "0"))
                qtd = parse_val_brl(prod.get("quantidade", "0"))
                gastos[desc] += val
                qtys[desc] += qtd

        total_geral = sum(gastos.values())
        itens_ordenados = sorted(gastos.items(), key=lambda x: x[1], reverse=True)
        
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(itens_ordenados))
        
        acum_pct = 0.0
        names = []
        values = []
        acum_perc = []

        # --- LER CONFIGURAÇÃO ABC ---
        abc_conf = self.config.get("abc_config", {"a": 80, "b": 95})
        limit_a = float(abc_conf.get("a", 80))
        limit_b = float(abc_conf.get("b", 95))

        for i, (desc, val) in enumerate(itens_ordenados):
            perc = (val / total_geral) * 100 if total_geral > 0 else 0
            acum_pct += perc
            
            # Classificação Dinâmica
            if acum_pct <= limit_a:
                cls = "A"
            elif acum_pct <= limit_b:
                cls = "B"
            else:
                cls = "C"

            self.table.setItem(i, 0, NumericTableWidgetItem(desc))
            item_qtd = NumericTableWidgetItem(f"{qtys.get(desc,0):.2f}")
            item_qtd.setData(Qt.ItemDataRole.UserRole, qtys.get(desc,0))
            self.table.setItem(i, 1, item_qtd)
            
            item_val = NumericTableWidgetItem(fmt_brl(val))
            item_val.setData(Qt.ItemDataRole.UserRole, val)
            self.table.setItem(i, 2, item_val)
            
            item_perc = NumericTableWidgetItem(f"{perc:.2f}%")
            item_perc.setData(Qt.ItemDataRole.UserRole, perc)
            self.table.setItem(i, 3, item_perc)
            
            item_acum = NumericTableWidgetItem(f"{acum_pct:.2f}%")
            item_acum.setData(Qt.ItemDataRole.UserRole, acum_pct)
            self.table.setItem(i, 4, item_acum)
            
            self.table.setItem(i, 5, NumericTableWidgetItem(cls))

            if i < 20: 
                names.append(desc)
                values.append(val)
                acum_perc.append(acum_pct)
        
        self.table.setSortingEnabled(True)
        self.total_label.setText(f"Total Gasto (Seleção): {fmt_brl(total_geral)}")

        # --- GRÁFICO ---
        self.figure.clear()
        is_dark = (self.current_theme == 'escuro')
        bg_color = '#2b2b2b' if is_dark else '#ffffff'
        text_color = 'white' if is_dark else 'black'
        bar_color = '#9b59b6' if is_dark else '#8e44ad'
        line_color = '#f39c12'

        self.figure.patch.set_facecolor(bg_color)
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(bg_color)
        
        if names:
            x = range(len(names))
            ax.bar(x, values, label="Gasto por item", color=bar_color)
            ax2 = ax.twinx()
            ax2.plot(x, acum_perc, color=line_color, marker="o", label="Acumulado (%)")
            
            ax.set_xticks(x)
            if len(names) <= 20:
                ax.set_xticklabels(names, rotation=45, ha="right", color=text_color)
            else:
                ax.set_xticklabels(["" for _ in names])
            
            ax.set_title(f"Curva ABC (Top 20) — {year} (A: {limit_a}%, B: {limit_b}%)", color=text_color)
            
            ax.tick_params(axis='y', colors=text_color)
            ax2.tick_params(axis='y', colors=text_color)
            for spine in ax.spines.values():
                spine.set_color(text_color)
            ax2.spines['right'].set_color(text_color)
            
            lines, labels = ax.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            leg = ax.legend(lines + lines2, labels + labels2, loc='upper left')
            if is_dark:
                leg.get_frame().set_facecolor('#333333')
                for text in leg.get_texts(): text.set_color('white')

            self.figure.tight_layout()
        else:
             ax.text(0.5, 0.5, "Sem dados", ha="center", va="center", color=text_color)
        self.canvas.draw()