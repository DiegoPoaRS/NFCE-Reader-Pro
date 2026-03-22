import logging
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QListWidget, QPushButton, QAbstractItemView, QFrame, 
    QGridLayout, QTableWidget, QTableWidgetItem
)
from PyQt6.QtCore import Qt

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt

from gui.data_cache import load_all_nfce_data
from gui.formatting_utils import parse_val_brl, fmt_brl, NumericTableWidgetItem
from gui.export_mixin import ExportMixin

logger = logging.getLogger('gui.dashboard')

class DashboardWidget(QWidget, ExportMixin):
    """
    Widget da aba Dashboard.
    """
    def __init__(self):
        super().__init__()
        ExportMixin.__init__(self)
        self.current_theme = "claro" # Estado do tema
        self.setContentsMargins(0, 0, 0, 0)
        self._init_ui()
        try:
            self._load_filters()
            self.update_dashboard()
        except Exception as e:
            logger.error(f"Erro inicial ao construir Dashboard: {e}", exc_info=True)

    def get_export_filename_prefix(self):
        return "dashboard_gastos_mensais"
        
    def set_theme_mode(self, theme_name):
        """Chamado pela MainWindow para atualizar o tema."""
        self.current_theme = theme_name
        self.update_dashboard() # Redesenha o gráfico com as novas cores

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        title = QLabel("Dashboard de Gastos Mensais")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:16px; font-weight:bold;")
        layout.addWidget(title)

        # Filtros
        filt_layout = QHBoxLayout()
        filt_layout.addWidget(QLabel("Ano:"))
        self.year_combo = QComboBox()
        self.year_combo.currentIndexChanged.connect(self.update_dashboard)
        filt_layout.addWidget(self.year_combo)
        
        filt_layout.addWidget(QLabel("CPFs:"))
        self.cpf_list = QListWidget()
        self.cpf_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.cpf_list.itemSelectionChanged.connect(self.update_dashboard)
        self.cpf_list.setFixedHeight(60)
        filt_layout.addWidget(self.cpf_list)
        
        layout.addLayout(filt_layout)

        # Cards - Usando ObjectName para ser estilizado pelo QSS da MainWindow
        cards_layout = QGridLayout()
        self.card_mes = self._make_card("Gasto Mês Atual", "R$ 0,00")
        self.card_ano = self._make_card("Total no Ano", "R$ 0,00")
        self.card_media = self._make_card("Média Mensal", "R$ 0,00")
        cards_layout.addWidget(self.card_mes, 0, 0)
        cards_layout.addWidget(self.card_ano, 0, 1)
        cards_layout.addWidget(self.card_media, 0, 2)
        layout.addLayout(cards_layout)
        
        self.figure = plt.Figure(figsize=(7, 4), tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet("background-color:transparent;") # Importante para dark mode
        layout.addWidget(self.canvas)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Mês", "Total (R$)", "Acumulado (R$)"])
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)
        
        layout.addLayout(self._create_export_buttons_layout())

    def _make_card(self, title, value):
        f = QFrame()
        # Define ID para o CSS Global pegar
        f.setObjectName("card_frame") 
        
        # Fallback style para modo claro (se o CSS global não cobrir)
        f.setStyleSheet("""
            QFrame#card_frame { 
                background-color:#f0f0f0; border-radius:8px; border:1px solid #ccc; 
            }
        """)

        l = QVBoxLayout(f)
        t = QLabel(title)
        t.setObjectName("card_title") # CSS ID
        
        v = QLabel(value)
        v.setObjectName("card_value") # CSS ID

        l.addWidget(t)
        l.addWidget(v)
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
        self.update_dashboard()

    def update_dashboard(self):
        # --- Lógica de Dados ---
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
        dados = { f"{m:02d}": 0.0 for m in range(1, 13) }
        
        for js in all_nfce_data:
            dt = js.get('_datetime')
            if not dt or dt == datetime.min: continue
            if dt.year != year: continue
            
            cpf = js.get("consumidor", {}).get("cpf") or "Não informado"
            if selected_cpfs and cpf not in selected_cpfs:
                continue
                
            val_str = js.get("totais", {}).get("valor_total", "0")
            val = parse_val_brl(val_str)
            
            mes_str = dt.strftime("%m")
            dados[mes_str] += val

        meses = sorted(dados.keys())
        valores = [dados[m] for m in meses]
        total_ano = sum(valores)
        mes_atual_str = datetime.now().strftime("%m")
        mes_atual = dados.get(mes_atual_str, 0.0)
        
        meses_com_gasto = len([v for v in valores if v > 0])
        media = total_ano / meses_com_gasto if meses_com_gasto > 0 else 0.0

        # Atualiza Textos dos Cards
        self.card_mes.findChild(QLabel, "card_value").setText(fmt_brl(mes_atual))
        self.card_ano.findChild(QLabel, "card_value").setText(fmt_brl(total_ano))
        self.card_media.findChild(QLabel, "card_value").setText(fmt_brl(media))

        # --- Atualiza Gráfico (Com suporte a Tema Escuro) ---
        self.figure.clear()
        
        # Cores do Tema
        is_dark = (self.current_theme == 'escuro')
        bg_color = '#2b2b2b' if is_dark else '#ffffff'
        text_color = 'white' if is_dark else 'black'
        bar_color = '#3498db' if is_dark else '#1f77b4'
        line_color = '#f1c40f' if is_dark else 'orange'
        
        self.figure.patch.set_facecolor(bg_color)
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(bg_color)
        
        if meses:
            x = range(len(meses))
            ax.bar(x, valores, label="Gasto (mês)", color=bar_color)
            cum = [sum(valores[:i+1]) for i in range(len(valores))]
            ax2 = ax.twinx()
            ax2.plot(x, cum, marker="o", color=line_color, label="Acumulado", linewidth=2)
            
            # Estilização dos eixos e legendas
            ax.set_xticks(x)
            ax.set_xticklabels(meses, rotation=45, color=text_color)
            ax.set_title(f"Gastos por mês — {year}", color=text_color)
            
            ax.tick_params(axis='y', colors=text_color)
            ax2.tick_params(axis='y', colors=text_color)
            ax.spines['bottom'].set_color(text_color)
            ax.spines['top'].set_color(text_color) 
            ax.spines['left'].set_color(text_color)
            ax.spines['right'].set_color(text_color)
            ax2.spines['right'].set_color(text_color)

            # Legenda
            lines, labels = ax.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            leg = ax2.legend(lines + lines2, labels + labels2, loc='upper left')
            if is_dark:
                leg.get_frame().set_facecolor('#333333')
                leg.get_frame().set_edgecolor('#555555')
                for text in leg.get_texts(): text.set_color('white')

        else:
            ax.text(0.5, 0.5, "Sem dados para este filtro", ha="center", va="center", color=text_color)
            
        self.canvas.draw()

        # --- Atualiza Tabela ---
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(meses))
        acum = 0.0
        for i, m in enumerate(meses):
            val_mes = dados[m]
            acum += val_mes
            
            self.table.setItem(i, 0, NumericTableWidgetItem(m))
            
            item_val = NumericTableWidgetItem(fmt_brl(val_mes))
            item_val.setData(Qt.ItemDataRole.UserRole, val_mes)
            self.table.setItem(i, 1, item_val)
            
            item_acum = NumericTableWidgetItem(fmt_brl(acum))
            item_acum.setData(Qt.ItemDataRole.UserRole, acum)
            self.table.setItem(i, 2, item_acum)
            
        self.table.setSortingEnabled(True)