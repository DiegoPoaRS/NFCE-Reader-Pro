import os
import json
import re
import logging
from datetime import datetime

logger = logging.getLogger('gui.data_cache')

_ALL_NFCE_DATA_CACHE = None
_JSON_SOURCE_DIR = "nfce_data" # Default, será atualizado pelo config

def configure_cache(config: dict):
    """Define o diretório de origem dos JSONs a partir do config."""
    global _JSON_SOURCE_DIR
    _JSON_SOURCE_DIR = config.get('paths', {}).get('json_output_dir', 'nfce_data')
    logger.info(f"Cache configurado para ler de: {_JSON_SOURCE_DIR}")

def load_all_nfce_data(force_reload=False):
    """
    Carrega todos os dados JSON do disco e os armazena em cache.
    [Baseado em _load_all_nfce_data_cached de nfce_reader_gui17.py]
    """
    global _ALL_NFCE_DATA_CACHE
    if _ALL_NFCE_DATA_CACHE is not None and not force_reload:
        logger.debug("Retornando dados do cache em memória.")
        return _ALL_NFCE_DATA_CACHE

    logger.info(f"Recarregando cache de dados do disco (force_reload={force_reload})...")
    all_data = []
    if not os.path.exists(_JSON_SOURCE_DIR):
        logger.warning(f"Diretório de JSONs não encontrado: {_JSON_SOURCE_DIR}")
        return []

    for f in os.listdir(_JSON_SOURCE_DIR):
        if not f.endswith(".json"):
            continue
        try:
            p = os.path.join(_JSON_SOURCE_DIR, f)
            with open(p, "r", encoding="utf-8") as f_json:
                js = json.load(f_json)
            
            # Anexa metadados úteis para filtragem
            js['_filename'] = f
            d = js.get("geral", {}).get("data_emissao", "")
            
            # Tenta extrair 'DD/MM/AAAA' da string 'DD/MM/AAAA HH:MM:SS'
            m = re.search(r"(\d{2}/\d{2}/\d{4})", d or "")
            if m:
                js['_datetime'] = datetime.strptime(m.group(1), "%d/%m/%Y")
            else:
                js['_datetime'] = datetime.min # Data mínima para erros
            
            all_data.append(js)
        except Exception as e:
            logger.warning(f"Ignorando JSON corrompido ou inválido: {f}. Erro: {e}")
            continue
    
    _ALL_NFCE_DATA_CACHE = all_data
    logger.info(f"Cache atualizado. {len(all_data)} notas carregadas.")
    return _ALL_NFCE_DATA_CACHE