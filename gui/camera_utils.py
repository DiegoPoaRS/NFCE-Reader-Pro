import cv2
import logging

logger = logging.getLogger('gui.camera_utils')

def preprocess_image_for_qr(frame):
    """
    Aplica tratamentos na imagem para facilitar a leitura do QR Code.
   
    """
    try:
        # 1. Converte para escala de cinza
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # 2. Aplica CLAHE (Melhora o contraste localmente)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        
        return enhanced
    except Exception as e:
        logger.warning(f"Falha no pré-processamento de imagem: {e}")
        # Retorna a imagem original em escala de cinza se o CLAHE falhar
        if 'frame' in locals() and frame is not None:
            return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return None