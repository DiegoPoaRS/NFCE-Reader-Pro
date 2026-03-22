import json
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, 
    QComboBox, QPushButton, QMessageBox, QSpinBox,
    QGroupBox, QHBoxLayout, QLabel
)
from PyQt6.QtCore import Qt

logger = logging.getLogger('gui.settings')

class SettingsWidget(QWidget):
    def __init__(self, config, main_window):
        super().__init__()
        self.config = config
        self.main_window = main_window # Referência para aplicar callbacks (ex: tema)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("Configurações do Sistema")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

        # --- Grupo: Geral ---
        group_geral = QGroupBox("Geral")
        form_geral = QFormLayout()
        
        self.combo_tema = QComboBox()
        self.combo_tema.addItems(["claro", "escuro"])
        self.combo_tema.setCurrentText(self.config.get("theme", "claro"))
        form_geral.addRow("Tema:", self.combo_tema)

        group_geral.setLayout(form_geral)
        layout.addWidget(group_geral)

        # --- Grupo: Câmera ---
        group_cam = QGroupBox("Câmera")
        form_cam = QFormLayout()
        
        self.input_cam_source = QLineEdit(str(self.config.get("camera_source", "0")))
        self.input_cam_source.setPlaceholderText("Ex: 0 ou http://192.168.x.x:port/video")
        form_cam.addRow("Fonte da Câmera (URL/ID):", self.input_cam_source)

        self.input_autofocus = QLineEdit(self.config.get("camera_autofocus_url", ""))
        form_cam.addRow("URL Auto-Focus:", self.input_autofocus)

        group_cam.setLayout(form_cam)
        layout.addWidget(group_cam)

        # --- Grupo: Curva ABC ---
        group_abc = QGroupBox("Parâmetros Curva ABC (Acumulado)")
        form_abc = QFormLayout()
        
        # Obtém valores atuais ou padrão (80/95)
        abc_conf = self.config.get("abc_config", {"a": 80, "b": 95})
        
        self.spin_a = QSpinBox()
        self.spin_a.setRange(1, 99)
        self.spin_a.setValue(int(abc_conf.get("a", 80)))
        self.spin_a.setSuffix("%")
        form_abc.addRow("Limite Classe A (até):", self.spin_a)

        self.spin_b = QSpinBox()
        self.spin_b.setRange(1, 99)
        self.spin_b.setValue(int(abc_conf.get("b", 95)))
        self.spin_b.setSuffix("%")
        form_abc.addRow("Limite Classe B (até):", self.spin_b)
        
        lbl_info = QLabel("Classe C será o restante (até 100%).")
        lbl_info.setStyleSheet("color: gray; font-size: 10px;")
        form_abc.addRow("", lbl_info)

        group_abc.setLayout(form_abc)
        layout.addWidget(group_abc)

        layout.addStretch()

        # --- Botões ---
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Salvar Configurações")
        self.btn_save.setFixedHeight(40)
        self.btn_save.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        self.btn_save.clicked.connect(self._save_config)
        
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)

    def _save_config(self):
        # Atualiza dicionário de config
        self.config["theme"] = self.combo_tema.currentText()
        
        # Tenta converter camera source para int se for número, senão str
        cam_src = self.input_cam_source.text()
        if cam_src.isdigit():
            self.config["camera_source"] = int(cam_src)
        else:
            self.config["camera_source"] = cam_src
            
        self.config["camera_autofocus_url"] = self.input_autofocus.text()

        # Config ABC
        val_a = self.spin_a.value()
        val_b = self.spin_b.value()

        if val_a >= val_b:
            QMessageBox.warning(self, "Erro", "O limite da Classe A deve ser menor que a Classe B.")
            return

        self.config["abc_config"] = {
            "a": val_a,
            "b": val_b
        }

        # Salva no arquivo
        try:
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            
            QMessageBox.information(self, "Sucesso", "Configurações salvas com sucesso!")
            
            # Aplica mudanças imediatas (Tema)
            if hasattr(self.main_window, "_apply_theme"):
                self.main_window._apply_theme(self.config["theme"])
            
            # Log
            logger.info("Configurações atualizadas pelo usuário.")

        except Exception as e:
            logger.error(f"Erro ao salvar config: {e}")
            QMessageBox.critical(self, "Erro", f"Falha ao salvar configurações: {e}")