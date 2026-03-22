import os
import pandas as pd
from datetime import datetime
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QFileDialog, QMessageBox, QSpacerItem, QSizePolicy
from PyQt6.QtCore import Qt

# Dependências de PDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, PageBreak, Spacer
from reportlab.lib import colors
from reportlab.lib.units import inch

import logging
logger = logging.getLogger('gui.export_mixin')

class ExportMixin:
    """
    Mixin para adicionar botões e lógica de exportação (CSV, Excel, PDF)
    a um QWidget que contenha self.table (QTableWidget) e self.figure (Matplotlib).
    """
    def __init__(self):
        # Esta classe é um mixin, o __init__ principal é o do QWidget
        pass

    def _create_export_buttons_layout(self):
        """Cria o QHBoxLayout com os botões de exportação."""
        export_layout = QHBoxLayout()
        export_layout.setContentsMargins(0, 5, 0, 5)
        
        export_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        
        self.btn_export_csv = QPushButton("Exportar CSV")
        self.btn_export_csv.setFixedSize(120, 30)
        export_layout.addWidget(self.btn_export_csv)

        self.btn_export_excel = QPushButton("Exportar Excel")
        self.btn_export_excel.setFixedSize(120, 30)
        export_layout.addWidget(self.btn_export_excel)

        self.btn_export_pdf = QPushButton("Exportar PDF (Gráfico)")
        self.btn_export_pdf.setFixedSize(150, 30)
        export_layout.addWidget(self.btn_export_pdf)
        
        export_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        # Conecta os sinais
        self.btn_export_csv.clicked.connect(self._export_csv)
        self.btn_export_excel.clicked.connect(self._export_excel)
        self.btn_export_pdf.clicked.connect(self._export_pdf)

        return export_layout

    def _get_data_from_qtablewidget(self):
        """Lê os dados da self.table e retorna um DataFrame pandas."""
        if not hasattr(self, 'table'):
            logger.error("Mixin de Exportação falhou: 'self.table' (QTableWidget) não encontrado.")
            return None, None

        headers = []
        for j in range(self.table.columnCount()):
            headers.append(self.table.horizontalHeaderItem(j).text())
        
        data = []
        for i in range(self.table.rowCount()):
            row = []
            for j in range(self.table.columnCount()):
                item = self.table.item(i, j)
                row.append(item.text() if item else "")
            data.append(row)
            
        return pd.DataFrame(data, columns=headers), headers

    def _get_save_filename(self, extension, title):
        """Abre o QFileDialog para obter o caminho de salvamento."""
        if not hasattr(self, 'get_export_filename_prefix'):
             logger.error("Mixin de Exportação falhou: implemente 'get_export_filename_prefix'.")
             return None
        
        prefix = self.get_export_filename_prefix()
        timestamp = datetime.now().strftime("%Y%m%d")
        default_filename = f"{prefix}_{timestamp}.{extension}"
        
        filename, _ = QFileDialog.getSaveFileName(
            self, 
            title, 
            default_filename,
            f"{extension.upper()} Files (*.{extension});;All Files (*)"
        )
        return filename

    def _export_csv(self):
        df, _ = self._get_data_from_qtablewidget()
        if df is None: return

        filename = self._get_save_filename('csv', 'Salvar CSV')
        if not filename: return
        
        try:
            df.to_csv(filename, index=False, sep=';', encoding='utf-8-sig')
            self._show_export_success(filename)
        except Exception as e:
            self._show_export_error(e)

    def _export_excel(self):
        df, _ = self._get_data_from_qtablewidget()
        if df is None: return

        filename = self._get_save_filename('xlsx', 'Salvar Excel')
        if not filename: return
        
        try:
            df.to_excel(filename, index=False, sheet_name='Dados')
            self._show_export_success(filename)
        except Exception as e:
            self._show_export_error(e)

    def _export_pdf(self):
        """Exporta um PDF contendo o gráfico (self.figure) e a tabela (self.table)."""
        if not hasattr(self, 'figure') or not hasattr(self, 'table'):
            logger.error("Mixin de Exportação PDF falhou: 'self.figure' ou 'self.table' não encontrados.")
            return

        filename = self._get_save_filename('pdf', 'Salvar PDF')
        if not filename: return

        try:
            # 1. Salvar o gráfico como imagem temporária
            temp_chart_path = "temp_chart_export.png"
            self.figure.savefig(temp_chart_path, dpi=300, bbox_inches='tight')

            # 2. Obter dados da tabela
            df, headers = self._get_data_from_qtablewidget()
            data_list = [headers] + df.values.tolist()

            # 3. Criar o PDF
            doc = SimpleDocTemplate(filename, pagesize=landscape(A4))
            elements = []

            # Adiciona o gráfico
            img = Image(temp_chart_path, width=10*inch, height=5*inch)
            img.hAlign = 'CENTER'
            elements.append(img)
            elements.append(Spacer(1, 0.25*inch)) # Espaçador

            # Adiciona a tabela
            table = Table(data_list, repeatRows=1)
            style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ])
            table.setStyle(style)
            elements.append(table)
            
            doc.build(elements)
            
            # 4. Limpar imagem temporária
            if os.path.exists(temp_chart_path):
                os.remove(temp_chart_path)
                
            self._show_export_success(filename)
            
        except Exception as e:
            self._show_export_error(e)
            if os.path.exists(temp_chart_path):
                os.remove(temp_chart_path) # Limpa em caso de erro

    def _show_export_success(self, filename):
        QMessageBox.information(
            self, 
            "Exportação Concluída", 
            f"Dados exportados com sucesso para:\n{filename}"
        )

    def _show_export_error(self, e):
        logger.error(f"Erro na exportação: {e}", exc_info=True)
        QMessageBox.warning(
            self, 
            "Erro na Exportação", 
            f"Não foi possível exportar o arquivo.\n\nErro: {e}\n\nVerifique se o arquivo está fechado."
        )