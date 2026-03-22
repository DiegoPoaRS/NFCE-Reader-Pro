import logging
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QListWidget, QAbstractItemView, QTableWidget, QHeaderView
)
from PyQt6.QtCore import Qt

from gui.data_cache import load_all_nfce_data
from gui.formatting_utils import parse_val_brl, fmt_brl, NumericTableWidgetItem
from gui.export_mixin import ExportMixin

logger = logging.getLogger('gui.tax_analysis')

class TaxAnalysisWidget(QWidget, ExportMixin):
    """
    Widget para analisar o total de tributos (impostos) pagos.
    """
    def __init__(self):
        super().__init__()
        ExportMixin.__init__(self)
        self.current_theme = "claro"
        self.setContentsMargins(0, 0, 0, 0)
        self._init_ui()
        try:
            self._load_filters()
            self.update_analysis()
        except Exception as e:
            logger.error(f"Erro inicial ao construir TaxAnalysis: {e}", exc_info=True)

    def get_export_filename_prefix(self):
        return "analise_impostos"
        
    def set_theme_mode(self, theme_name):
        """Apenas atualiza o estado, já que a tabela é colorida pelo CSS global."""
        self.current_theme = theme_name
        # Se houver gráficos futuros, chamar update_analysis() aqui

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        title = QLabel("Análise de Tributos (Impostos Pagos)")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:16px; font-weight:bold;")
        layout.addWidget(title)

        # Filtros
        filt = QHBoxLayout()
        filt.addWidget(QLabel("Ano:"))
        self.year_combo = QComboBox()
        self.year_combo.currentIndexChanged.connect(self.update_analysis)
        filt.addWidget(self.year_combo)
        
        filt.addWidget(QLabel("Mês:"))
        self.month_combo = QComboBox()
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

        # Tabela
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Data", "Vendedor", "CPF", "Valor Total (R$)", "Tributos (R$)"])
        self.table.setSortingEnabled(True)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        
        layout.addWidget(self.table)
        
        # Label de Soma
        self.total_label = QLabel("Total de Tributos: R$ 0,00")
        self.total_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        layout.addWidget(self.total_label, alignment=Qt.AlignmentFlag.AlignRight)

        # Exportação
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

    def update_analysis(self):
        try:
            year = int(self.year_combo.currentText())
        except ValueError:
            year = datetime.now().year
            
        month = self.month_combo.currentText()
        selected_cpfs = self._get_selected_cpfs()
        all_nfce_data = load_all_nfce_data()
        
        filtered_data = []
        for nfce in all_nfce_data:
            dt = nfce.get('_datetime')
            if not dt or dt == datetime.min: continue
            if dt.year != year: continue
            if month != "Todos" and dt.strftime("%m") != month: continue
            cpf = nfce.get("consumidor", {}).get("cpf") or "Não informado"
            if selected_cpfs is not None and cpf not in selected_cpfs: continue
            filtered_data.append(nfce)
        
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(filtered_data))
        
        total_tributos_soma = 0.0

        for i, nfce in enumerate(filtered_data):
            data_emissao = nfce.get("geral", {}).get("data_emissao", "N/A")
            vendedor = nfce.get("vendedor", {}).get("razao_social", "N/A")
            cpf = nfce.get("consumidor", {}).get("cpf", "Não informado")
            valor_total = nfce.get("totais", {}).get("valor_total", "0,00")
            valor_tributos = nfce.get("totais", {}).get("valor_total_tributos", "0,00")

            val_total_float = parse_val_brl(valor_total)
            val_trib_float = parse_val_brl(valor_tributos)
            total_tributos_soma += val_trib_float
            
            self.table.setItem(i, 0, NumericTableWidgetItem(data_emissao))
            self.table.setItem(i, 1, NumericTableWidgetItem(vendedor))
            self.table.setItem(i, 2, NumericTableWidgetItem(cpf))
            
            item_total = NumericTableWidgetItem(fmt_brl(val_total_float))
            item_total.setData(Qt.ItemDataRole.UserRole, val_total_float)
            self.table.setItem(i, 3, item_total)
            
            item_trib = NumericTableWidgetItem(fmt_brl(val_trib_float))
            item_trib.setData(Qt.ItemDataRole.UserRole, val_trib_float)
            self.table.setItem(i, 4, item_trib)
            
        self.table.setSortingEnabled(True)
        self.total_label.setText(f"Total de Tributos (Seleção): {fmt_brl(total_tributos_soma)}")

    def refresh_data(self):
        self._load_filters()
        self.update_analysis()