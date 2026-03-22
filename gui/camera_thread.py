import cv2
import time
import logging
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from pyzbar.pyzbar import decode
from gui.camera_utils import preprocess_image_for_qr

logger = logging.getLogger('gui.camera_thread')

class CameraThread(QThread):
    update_frame = pyqtSignal(QPixmap)
    qr_code_detected = pyqtSignal(str)
    camera_error = pyqtSignal(str)

    def __init__(self, config):
        super().__init__()
        self.running = False
        self.paused = False 
        self.camera_source = config.get('camera_source', 0)
        self.scanned_codes = set()
        self.processing_lock = False
        self.last_scan_time = 0
        self.scan_cooldown = 3 # Cooldown de 3 segundos
        
        logger.info(f"Thread da Câmera (QR-Only) iniciada. Fonte: {self.camera_source}")

    def run(self):
        self.running = True
        cap = cv2.VideoCapture(self.camera_source)
        
        if not cap.isOpened():
            logger.error(f"Não foi possível abrir a câmera: {self.camera_source}")
            self.camera_error.emit(f"Não foi possível conectar à câmera: {self.camera_source}")
            return

        while self.running:
            if self.paused:
                time.sleep(0.1)
                continue
            
            ret, frame = cap.read()
            if not ret:
                logger.warning("Frame da câmera não recebido. Tentando reconectar...")
                time.sleep(2)
                cap.release()
                cap = cv2.VideoCapture(self.camera_source)
                continue

            # 1. Processa imagem
            enhanced_frame = preprocess_image_for_qr(frame)
            if enhanced_frame is None:
                continue
                
            # Trava de scraping
            if self.processing_lock:
                self.emit_frame(frame)
                self.msleep(30)
                continue

            # Cooldown global
            current_time = time.time()
            if (current_time - self.last_scan_time < self.scan_cooldown):
                self.emit_frame(frame)
                self.msleep(30)
                continue

            decoded_objects = decode(enhanced_frame)

            for obj in decoded_objects:
                data = obj.data.decode('utf-8')
                code_type = obj.type
                (x, y, w, h) = obj.rect

                if data in self.scanned_codes:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2) # Vermelho
                    continue 

                # ⭐️ Lógica simplificada: Só nos importa QR Code de URL
                if code_type == 'QRCODE' and data.startswith('http'):
                    self.processing_lock = True 
                    self.last_scan_time = current_time
                    self.scanned_codes.add(data) 
                    logger.info(f"QR Code (URL) detectado. Emitindo para scraping.")
                    self.qr_code_detected.emit(data)
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 200, 0), 2) # Azul
                    break
                else:
                    # Ignora códigos de barras ou QRs de texto
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2) # Verde (Visto)


            # 3. Emite o frame da câmera
            self.emit_frame(frame)
            self.msleep(30) # Controla o FPS

        cap.release()
        logger.info("Thread da Câmera parada.")

    def emit_frame(self, frame):
        """Converte um frame CV2 e emite o sinal update_frame."""
        try:
            img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = img_rgb.shape
            bytes_per_line = ch * w
            qt_image = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_image)
            self.update_frame.emit(pixmap)
        except Exception as e:
            logger.warning(f"Erro ao emitir frame: {e}")

    def stop(self):
        self.running = False
        self.wait()

    def release_lock(self):
        self.processing_lock = False