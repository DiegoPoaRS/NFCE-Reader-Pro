import os
import json
import re
import logging
from collections import defaultdict
from typing import Dict, List, Any

# Nossos módulos
from logging_setup import get_logger
# Para usar as funções de formatação
from gui.formatting_utils import parse_val_brl 

logger = get_logger('sust_service')

# Cache para armazenar o mapa de sustentabilidade após a leitura do config.json
_SUSTAINABILITY_MAP = None

def load_sustainability_map(config_path='config.json') -> Dict[str, Any]:
    """
    Carrega o mapa de sustentabilidade e as metas ODS do config.json.
    Armazena em cache para evitar leituras repetidas do disco.
    """
    global _SUSTAINABILITY_MAP
    if _SUSTAINABILITY_MAP:
        return _SUSTAINABILITY_MAP

    try:
        # Tenta carregar o config a partir do diretório raiz
        if not os.path.exists(config_path):
             # Tenta carregar se estiver sendo chamado do módulo gui/services
            config_path = os.path.join(os.path.dirname(__file__), '..', config_path)
            
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        sust_data = config.get('analise_sustentabilidade', {})
        if not sust_data:
            logger.error("Bloco 'analise_sustentabilidade' não encontrado no config.json.")
            return {"categorias": {}, "metas_ods": {}}

        # Normalização das palavras-chave: minúsculas e sem acentos/caracteres especiais
        normalized_categories = {}
        for cat_name, cat_data in sust_data['categorias'].items():
            normalized_keywords = [
                re.sub(r'[^a-z0-9]', '', kw.lower())
                for kw in cat_data.get('palavras_chave', [])
            ]
            normalized_categories[cat_name] = {
                **cat_data,
                'normalized_keywords': normalized_keywords
            }
        
        sust_data['categorias'] = normalized_categories
        _SUSTAINABILITY_MAP = sust_data
        logger.info("Mapa de Sustentabilidade (ODS) carregado e normalizado.")
        return _SUSTAINABILITY_MAP

    except Exception as e:
        logger.error(f"Erro ao carregar mapa de sustentabilidade: {e}", exc_info=True)
        return {"categorias": {}, "metas_ods": {}}


def classify_product(description: str) -> Dict[str, Any]:
    """
    Classifica um produto com base nas palavras-chave do mapa.
    Retorna os dados de sustentabilidade da categoria.
    """
    sust_map = load_sustainability_map()
    description_norm = re.sub(r'[^a-z0-9]', '', description.lower())

    # Categoria padrão (se não for encontrado)
    default_classification = {
        "categoria_sust": "Nao_Classificado",
        "pegada_carbono_media": 5.0,
        "risco_ambiental": "Desconhecido",
        "ods_foco": ["N/A"]
    }

    if not sust_map.get('categorias'):
        return default_classification

    # Procura pela palavra-chave mais longa (mais específica)
    best_match_category = None
    max_len = 0

    for cat_name, cat_data in sust_map['categorias'].items():
        for keyword in cat_data['normalized_keywords']:
            # Verifica se a palavra-chave está contida na descrição
            if keyword and keyword in description_norm:
                # Prioriza a correspondência mais longa para evitar erros (ex: "carne" vs "carne moida")
                if len(keyword) > max_len:
                    max_len = len(keyword)
                    best_match_category = cat_data
                    best_match_category['categoria_sust'] = cat_name
    
    if best_match_category:
        return best_match_category
    
    # Se não houver correspondência, retorna o padrão
    return default_classification


def calculate_ods_metrics(all_nfce_data: List[Dict]) -> Dict[str, Any]:
    """
    Calcula métricas agregadas de ODS (Pegada de Carbono, % Vegetal)
    para todas as notas fiscais carregadas.
    """
    sust_map = load_sustainability_map()
    metas = sust_map.get('metas_ods', {})
    
    total_carbon_footprint = 0.0
    total_gasto_vegetal = 0.0
    total_gasto_geral = 0.0
    
    # Armazena o total de carbono por categoria para o gráfico
    carbon_by_category = defaultdict(float)
    gasto_by_category = defaultdict(float)

    for nfce in all_nfce_data:
        produtos = nfce.get("produtos", [])
        
        for produto in produtos:
            descricao = produto.get("descricao", "")
            
            # Converte valores string/BRL para float
            try:
                quantidade = parse_val_brl(produto.get("quantidade"))
                valor_total_item = parse_val_brl(produto.get("valor_total"))
            except ValueError:
                continue

            classification = classify_product(descricao)
            category = classification['categoria_sust']
            carbon_factor = classification['pegada_carbono_media']
            
            if quantidade > 0:
                # Pegada de Carbono (Carbon factor é em kg CO2e/kg do produto)
                carbon_item = quantidade * carbon_factor
                total_carbon_footprint += carbon_item
                carbon_by_category[category] += carbon_item
            
            # Cálculo de Gasto
            total_gasto_geral += valor_total_item
            gasto_by_category[category] += valor_total_item
            
            # Classificação para Meta % Vegetal (ODS 12)
            if category == "Hortifruti_Baixo_Carbono":
                total_gasto_vegetal += valor_total_item
    
    # --- Cálculo de Metas ---
    
    pct_gasto_vegetal = (total_gasto_vegetal / total_gasto_geral) * 100 if total_gasto_geral > 0 else 0.0
    
    status_carbono = "Atingida"
    if total_carbon_footprint > metas.get("carbono_maximo_mes", float('inf')):
        status_carbono = "Excedida"
        
    status_vegetal = "Atingida"
    if pct_gasto_vegetal < metas.get("pct_gasto_vegetal_min", 0):
        status_vegetal = "Não Atingida"


    return {
        "total_carbon_footprint": total_carbon_footprint,
        "total_gasto_geral": total_gasto_geral,
        "pct_gasto_vegetal": pct_gasto_vegetal,
        "carbon_by_category": dict(carbon_by_category),
        "gasto_by_category": dict(gasto_by_category),
        "metas": metas,
        "status_carbono": status_carbono,
        "status_vegetal": status_vegetal,
    }