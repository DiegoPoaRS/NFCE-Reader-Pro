import logging
from datetime import datetime
from collections import defaultdict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt

from gui.data_cache import load_all_nfce_data
from gui.formatting_utils import parse_val_brl, fmt_brl, NumericTableWidgetItem
from gui.export_mixin import ExportMixin

logger = logging.getLogger('gui.health_widget')

class HealthWidget(QWidget, ExportMixin):
    """
    Widget focado no ODS 3: Saúde e Bem-Estar.
    Lógica Simplificada: Usa categorias explícitas de saúde do config.json.
    Categorias esperadas: 'Alimentos_Ultraprocessados', 'Alimentos_Naturais...', 'Nao_Alimento'.
    """
    def __init__(self, config):
        super().__init__()
        self.config = config
        ExportMixin.__init__(self)
        self.setContentsMargins(0, 0, 0, 0)
        
        # Carrega APENAS o mapa de saúde
        self.health_map = config.get('analise_saude', {})
        self.current_theme = config.get('theme', 'claro')
        
        self._init_ui()
        try:
            self._load_filters()
            self.update_analysis()
        except Exception as e:
            logger.error(f"Erro inicial ao construir HealthWidget: {e}", exc_info=True)

    def get_export_filename_prefix(self):
        return "analise_saude_ods3"

    def set_theme_mode(self, theme_name):
        self.current_theme = theme_name
        self.update_analysis()

    def refresh_data(self):
        self._load_filters()
        self.update_analysis()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Cabeçalho
        header_layout = QHBoxLayout()
        icon_lbl = QLabel("🍎")
        icon_lbl.setStyleSheet("font-size: 24px;")
        title = QLabel("Monitor de Saúde e Nutrição (ODS 3)")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_layout.addWidget(icon_lbl)
        header_layout.addWidget(title)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Filtros
        filt_layout = QHBoxLayout()
        filt_layout.addWidget(QLabel("Ano:"))
        self.year_combo = QComboBox()
        self.year_combo.currentIndexChanged.connect(self.update_analysis)
        filt_layout.addWidget(self.year_combo)
        
        filt_layout.addWidget(QLabel("Mês:"))
        self.month_combo = QComboBox()
        self.month_combo.addItems(["Todos"] + [f"{i:02d}" for i in range(1, 13)])
        self.month_combo.currentIndexChanged.connect(self.update_analysis)
        filt_layout.addWidget(self.month_combo)
        layout.addLayout(filt_layout)

        # Conteúdo
        content_layout = QHBoxLayout()
        
        chart_frame = QFrame()
        chart_frame.setFrameShape(QFrame.Shape.StyledPanel)
        chart_layout = QVBoxLayout(chart_frame)
        self.figure = plt.Figure(figsize=(5, 4), tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet("background-color:transparent;")
        chart_layout.addWidget(self.canvas)
        content_layout.addWidget(chart_frame, 4)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Categoria", "Exemplos Comprados", "Gasto (R$)", "% Total"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        content_layout.addWidget(self.table, 6)
        
        layout.addLayout(content_layout)
        
        self.score_lbl = QLabel("Score Nutricional: Calculando...")
        self.score_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.score_lbl.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px; border-radius: 5px;")
        layout.addWidget(self.score_lbl)
        
        layout.addLayout(self._create_export_buttons_layout())

    def _load_filters(self):
        all_data = load_all_nfce_data()
        years = sorted(list(set([d['_datetime'].year for d in all_data if d['_datetime'] != datetime.min])), reverse=True)
        self.year_combo.clear()
        self.year_combo.addItems([str(y) for y in years])
        if not years: self.year_combo.addItem(str(datetime.now().year))

    def update_analysis(self):
        year_txt = self.year_combo.currentText()
        if not year_txt: return
        year = int(year_txt)
        month_txt = self.month_combo.currentText()
        all_data = load_all_nfce_data()
        
        category_totals = defaultdict(float)
        category_examples = defaultdict(list)
        total_geral = 0.0

        for nf in all_data:
            dt = nf.get('_datetime')
            if dt.year != year: continue
            if month_txt != "Todos" and f"{dt.month:02d}" != month_txt: continue
            
            for prod in nf.get('produtos', []):
                desc = prod.get('descricao', '').lower()
                val = parse_val_brl(prod.get('valor_total', '0'))
                
                found_cat = False
                
                # Procura nas categorias explícitas de saúde (incluindo Nao_Alimento)
                for cat_name, keywords in self.health_map.items():
                    if any(k in desc for k in keywords):
                        category_totals[cat_name] += val
                        if len(category_examples[cat_name]) < 3: 
                            category_examples[cat_name].append(prod.get('descricao').title())
                        found_cat = True
                        break
                
                if not found_cat:
                    category_totals["⚪ Outros"] += val
                
                total_geral += val

        # Ordenação: Naturais -> Ultra -> Não Alimento -> Outros
        def sort_key(k):
            k_lower = k.lower()
            if "naturais" in k_lower: return 0
            if "ultra" in k_lower: return 1
            if "nao_alimento" in k_lower or "não alimento" in k_lower: return 3
            return 2

        sorted_keys = sorted(category_totals.keys(), key=sort_key)
        
        # Atualiza Tabela
        self.table.setRowCount(len(sorted_keys))
        for i, cat in enumerate(sorted_keys):
            val = category_totals[cat]
            pct = (val/total_geral*100) if total_geral > 0 else 0
            
            icon = ""
            display_name = cat.replace("_", " ")
            
            if "naturais" in cat.lower(): 
                icon = "🟢 "
            elif "ultra" in cat.lower(): 
                icon = "🔴 "
            elif "nao_alimento" in cat.lower(): 
                icon = "⛔ "
                display_name = "Não é Alimento"
            
            self.table.setItem(i, 0, QTableWidgetItem(f"{icon}{display_name}"))
            self.table.setItem(i, 1, QTableWidgetItem(", ".join(category_examples[cat])))
            self.table.setItem(i, 2, NumericTableWidgetItem(fmt_brl(val)))
            self.table.setItem(i, 3, NumericTableWidgetItem(f"{pct:.1f}%"))

        # Atualiza Gráfico
        self.figure.clear()
        is_dark = (self.current_theme == 'escuro')
        bg_color = '#2b2b2b' if is_dark else '#ffffff'
        text_color = 'white' if is_dark else 'black'
        
        self.figure.patch.set_facecolor(bg_color)
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(bg_color)
        
        labels = []
        sizes = []
        colors = []
        
        for cat in sorted_keys:
            if category_totals[cat] > 0:
                name_clean = cat.replace("_", " ")
                if "nao_alimento" in cat.lower(): name_clean = "Não Alimento"
                
                labels.append(name_clean)
                sizes.append(category_totals[cat])
                
                if "naturais" in cat.lower(): colors.append('#27ae60') # Verde
                elif "ultra" in cat.lower(): colors.append('#c0392b') # Vermelho
                elif "nao_alimento" in cat.lower(): colors.append('#7f8c8d') # Cinza Escuro
                else: colors.append('#95a5a6') # Cinza Claro

        if sizes:
            ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=colors, textprops={'color': text_color})
            ax.set_title("Gastos por Perfil Nutricional", color=text_color)
        else:
            ax.text(0.5, 0.5, "Sem dados", ha="center", color=text_color)
            
        self.canvas.draw()
        
        # Score - IGNORA "Nao_Alimento" e "Outros"
        # O Score é a proporção de comida saudável sobre o TOTAL DE COMIDA (Saudável + Ultra)
        val_nat = category_totals.get("Alimentos_Naturais_Min_Processados", 0)
        val_ultra = category_totals.get("Alimentos_Ultraprocessados", 0)
        
        total_food = val_nat + val_ultra
        
        if total_food > 0:
            ratio = (val_nat / total_food) * 100
            if ratio > 70:
                self.score_lbl.setText(f"EXCELENTE! {ratio:.0f}% da comida é saudável.")
                self.score_lbl.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 6px; border-radius: 4px;")
            elif ratio > 40:
                self.score_lbl.setText(f"REGULAR. {ratio:.0f}% da comida é saudável.")
                self.score_lbl.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold; padding: 6px; border-radius: 4px;")
            else:
                self.score_lbl.setText(f"CRÍTICO. Apenas {ratio:.0f}% da comida é saudável.")
                self.score_lbl.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; padding: 6px; border-radius: 4px;")
        else:
            self.score_lbl.setText("Dados insuficientes de alimentos.")
            self.score_lbl.setStyleSheet("background-color: #7f8c8d; color: white; padding: 6px;")