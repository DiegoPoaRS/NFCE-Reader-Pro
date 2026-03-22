import logging
import json
import os
import shutil
from collections import Counter

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QTabWidget
)
from PyQt6.QtCore import Qt

from gui.data_cache import load_all_nfce_data

logger = logging.getLogger('gui.refine_items')

# --- CLASSE PERSONALIZADA PARA BLOQUEAR SCROLL NO COMBOBOX ---
class NoScrollComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()

class RefineItemsWidget(QWidget):
    """
    Tela para o usuário classificar itens que o sistema não reconheceu.
    Versão Otimizada: 
    1. Lista aumentada para 100 itens.
    2. Dropdown mostra até 8 exemplos dinâmicos.
    """
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.config_path = 'config.json' 
        self._init_ui()
        self.load_unclassified_items()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # Cabeçalho
        lbl_title = QLabel("Refinar Classificação de Itens")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(lbl_title)
        
        lbl_desc = QLabel(
            "Abaixo estão os itens não identificados (Outros).\n"
            "Selecione a Categoria correta no menu (com exemplos) e clique em Salvar."
        )
        lbl_desc.setStyleSheet("color: gray;")
        layout.addWidget(lbl_desc)

        # Abas
        self.tabs = QTabWidget()
        self.tab_saude = QWidget()
        self.tab_sustentabilidade = QWidget()
        
        self.tabs.addTab(self.tab_saude, "Refinar Saúde (ODS 3)")
        self.tabs.addTab(self.tab_sustentabilidade, "Refinar Ambiental (ODS 12/13)")
        
        self._setup_tab_saude()
        self._setup_tab_sustentabilidade()
        
        layout.addWidget(self.tabs)

        # Botões
        btn_layout = QHBoxLayout()
        btn_reload = QPushButton("Recarregar Lista")
        btn_reload.clicked.connect(self.load_unclassified_items)
        
        self.btn_save = QPushButton("Salvar Aprendizado e Atualizar Config")
        self.btn_save.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 10px;")
        self.btn_save.clicked.connect(self._save_changes)
        
        btn_layout.addWidget(btn_reload)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)

    def _setup_tab_saude(self):
        layout = QVBoxLayout(self.tab_saude)
        
        self.table_saude = QTableWidget()
        self.table_saude.setColumnCount(3)
        self.table_saude.setHorizontalHeaderLabels(["Item (Descrição)", "Frequência", "Categoria Destino"])
        
        header = self.table_saude.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents) 
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        
        self.table_saude.verticalHeader().setDefaultSectionSize(50) 
        layout.addWidget(self.table_saude)

    def _setup_tab_sustentabilidade(self):
        layout = QVBoxLayout(self.tab_sustentabilidade)
        
        self.table_sust = QTableWidget()
        self.table_sust.setColumnCount(3)
        self.table_sust.setHorizontalHeaderLabels(["Item (Descrição)", "Frequência", "Categoria Destino"])
        
        header = self.table_sust.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        self.table_sust.verticalHeader().setDefaultSectionSize(50)
        layout.addWidget(self.table_sust)

    def load_unclassified_items(self):
        all_data = load_all_nfce_data()
        
        unclassified_saude = Counter()
        unclassified_sust = Counter()
        
        # Pega mapas atuais
        map_saude = self.config.get("analise_saude", {})
        map_sust = self.config.get("analise_sustentabilidade", {}).get("categorias", {})

        for nf in all_data:
            for prod in nf.get('produtos', []):
                desc_orig = prod.get('descricao', '').strip()
                desc_lower = desc_orig.lower()
                
                # Checa Saúde
                found_saude = False
                for cat, keywords in map_saude.items():
                    if any(k in desc_lower for k in keywords):
                        found_saude = True
                        break
                if not found_saude:
                    unclassified_saude[desc_orig] += 1
                
                # Checa Sustentabilidade
                found_sust = False
                for cat, data_cat in map_sust.items():
                    keywords = data_cat.get("palavras_chave", [])
                    if any(k in desc_lower for k in keywords):
                        found_sust = True
                        break
                if not found_sust:
                    unclassified_sust[desc_orig] += 1

        self._populate_table(self.table_saude, unclassified_saude, map_saude, type_analysis='saude')
        self._populate_table(self.table_sust, unclassified_sust, map_sust, type_analysis='sust')

    def _populate_table(self, table, counter_data, category_map, type_analysis):
        table.setRowCount(0)
        # --- AUMENTADO PARA 100 ITENS ---
        sorted_items = counter_data.most_common(100) 
        table.setRowCount(len(sorted_items))
        
        for i, (desc, count) in enumerate(sorted_items):
            item_desc = QTableWidgetItem(desc)
            item_desc.setFlags(item_desc.flags() ^ Qt.ItemFlag.ItemIsEditable) 
            item_desc.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            table.setItem(i, 0, item_desc)
            
            item_count = QTableWidgetItem(str(count))
            item_count.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_count.setFlags(item_count.flags() ^ Qt.ItemFlag.ItemIsEditable)
            table.setItem(i, 1, item_count)
            
            combo = NoScrollComboBox() 
            combo.addItem("--- Ignorar ---", None)
            combo.setStyleSheet("padding: 5px;")
            
            for cat_key, cat_data in category_map.items():
                pretty_name = cat_key.replace("_", " ")
                
                keywords = []
                if type_analysis == 'saude':
                    keywords = cat_data
                else:
                    keywords = cat_data.get('palavras_chave', [])
                
                # --- ALTERAÇÃO AQUI: MOSTRA 8 EXEMPLOS ---
                examples = ", ".join(keywords[:8]) if keywords else ""
                if len(keywords) > 8: examples += "..."
                
                display_text = f"{pretty_name} (Ex: {examples})"
                
                combo.addItem(display_text, cat_key)
            
            table.setCellWidget(i, 2, combo)

    def _save_changes(self):
        updates_saude = 0
        updates_sust = 0
        
        rows = self.table_saude.rowCount()
        for i in range(rows):
            combo = self.table_saude.cellWidget(i, 2)
            cat_key = combo.currentData()
            
            if cat_key:
                desc = self.table_saude.item(i, 0).text()
                keyword = desc.lower()
                
                if keyword not in self.config["analise_saude"][cat_key]:
                    self.config["analise_saude"][cat_key].append(keyword)
                    updates_saude += 1

        rows = self.table_sust.rowCount()
        for i in range(rows):
            combo = self.table_sust.cellWidget(i, 2)
            cat_key = combo.currentData()
            
            if cat_key:
                desc = self.table_sust.item(i, 0).text()
                keyword = desc.lower()
                
                target_list = self.config["analise_sustentabilidade"]["categorias"][cat_key]["palavras_chave"]
                if keyword not in target_list:
                    target_list.append(keyword)
                    updates_sust += 1

        if updates_saude == 0 and updates_sust == 0:
            QMessageBox.information(self, "Sem alterações", "Nenhuma categoria foi selecionada.")
            return

        try:
            shutil.copy(self.config_path, self.config_path + ".bak")
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            
            msg = f"Sucesso!\n\n{updates_saude} novos itens em Saúde.\n{updates_sust} novos itens em Sustentabilidade.\n\nConfiguração salva."
            QMessageBox.information(self, "Configuração Atualizada", msg)
            
            self.load_unclassified_items()
            
        except Exception as e:
            logger.error(f"Erro ao salvar config: {e}")
            QMessageBox.critical(self, "Erro", f"Falha ao salvar config.json: {e}")