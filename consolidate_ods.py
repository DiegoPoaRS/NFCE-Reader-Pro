import os
import json
import pandas as pd
from datetime import datetime
import re
import logging

# Logger (agora usa o logging_setup se disponível ou básico)
logger = logging.getLogger('consolidate_ods')

# --- Configurações (serão lidas do config) ---
CONFIG_FILE = "config.json"

def load_config():
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Falha ao carregar {CONFIG_FILE}: {e}")
        return None

def load_ods_classification_map(config: dict):
    logger.info(f"Carregando mapa ODS...")
    classification_map = {}
    
    sust_data = config.get("analise_sustentabilidade", {})
    categorias = sust_data.get("categorias", {})
    
    if not categorias:
        logger.error("Bloco 'analise_sustentabilidade' -> 'categorias' não encontrado.")
        return None
    
    for category_name, category_data in categorias.items():
        keywords = category_data.get("palavras_chave", [])
        for keyword in keywords:
            norm_keyword = keyword.lower().strip()
            if norm_keyword not in classification_map:
                classification_map[norm_keyword] = category_name
    
    logger.info(f"Mapa ODS criado com {len(classification_map.keys())} palavras-chave.")
    return classification_map

def classify_product(description, category_map):
    norm_desc = description.lower()
    sorted_keywords = sorted(category_map.keys(), key=len, reverse=True)
    for keyword in sorted_keywords:
        if keyword in norm_desc:
            return category_map[keyword]
    return "Nao_Classificado"

def clean_numeric(val_str):
    val = re.sub(r'[^\d,\.]', '', str(val_str))
    if ',' in val and '.' in val:
        val = val.replace('.', '').replace(',', '.')
    else:
        val = val.replace(',', '.')
    try:
        return float(val)
    except ValueError:
        return 0.0

def run_consolidation():
    """
    Função principal que lê JSONs, classifica (ODS) e salva em CSV.
    Retorna uma tupla (sucesso, mensagem).
    """
    logger.info("Iniciando a consolidação ODS...")
    config = load_config()
    if not config:
        return False, "Falha ao carregar config.json"
        
    JSON_SOURCE_DIR = config.get('paths', {}).get('json_output_dir', 'nfce_data')
    CONSOLIDATED_OUTPUT_DIR = config.get('paths', {}).get('consolidated_output_dir', 'nfce_consolidado')

    category_map = load_ods_classification_map(config)
    if category_map is None:
        return False, "Falha ao carregar mapa de classificação ODS."

    all_product_records = []
    
    if not os.path.exists(JSON_SOURCE_DIR):
        return False, f"Diretório de origem não encontrado: {JSON_SOURCE_DIR}"
        
    json_files = [f for f in os.listdir(JSON_SOURCE_DIR) if f.endswith(".json")]
    logger.info(f"Encontrados {len(json_files)} arquivos JSON.")
    
    for filename in json_files:
        file_path = os.path.join(JSON_SOURCE_DIR, filename)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                nfce_data = json.load(f)
        except Exception as e:
            logger.warning(f"Erro ao ler {filename}: {e}")
            continue

        chave_acesso = nfce_data.get('geral', {}).get('chave_acesso') or os.path.splitext(filename)[0]
        data_emissao_raw = nfce_data.get('geral', {}).get('data_emissao', '')
        data_emissao = data_emissao_raw.split(' ')[0] if ' ' in data_emissao_raw else data_emissao_raw or 'N/A'

        metadata = {
            'chave_nfce': chave_acesso,
            'data_emissao': data_emissao,
            'vendedor_razao_social': nfce_data.get('vendedor', {}).get('razao_social', 'N/A'),
            'consumidor_cpf': nfce_data.get('consumidor', {}).get('cpf', 'Não Informado'),
            'valor_total_tributos': nfce_data.get('totais', {}).get('valor_total_tributos', '')
        }
        produtos = nfce_data.get('produtos', [])

        for item in produtos:
            try:
                descricao = item.get('descricao', 'N/A')
                categoria_ods = classify_product(descricao, category_map)
                
                qtd = clean_numeric(item.get('quantidade', '0'))
                vu = clean_numeric(item.get('valor_unitario', '0'))
                vt = clean_numeric(item.get('valor_total', '0'))
                
                if vt == 0.0 and qtd > 0 and vu > 0:
                    vt = qtd * vu

                record = {
                    **metadata,
                    'descricao_produto': descricao,
                    'categoria_ods': categoria_ods,
                    'quantidade': qtd,
                    'valor_unitario': vu,
                    'valor_total_item': vt
                }
                all_product_records.append(record)
            except Exception as e:
                logger.error(f"Erro no item '{descricao}': {e}")

    if not all_product_records:
        return True, "Nenhum produto encontrado. CSV não gerado."

    df = pd.DataFrame(all_product_records)
    df['data_emissao_dt'] = pd.to_datetime(df['data_emissao'], format='%d/%m/%Y', errors='coerce')

    os.makedirs(CONSOLIDATED_OUTPUT_DIR, exist_ok=True)
    
    TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUTPUT_CSV_FILE = f"nfce_ods_classificada_{TIMESTAMP}.csv"
    output_path = os.path.join(CONSOLIDATED_OUTPUT_DIR, OUTPUT_CSV_FILE)
    
    df.to_csv(output_path, index=False, encoding='utf-8-sig', sep=';', decimal=',') 

    msg = f"CONSOLIDAÇÃO ODS CONCLUÍDA!\n{len(df)} produtos classificados.\nSalvo em: {output_path}"
    logger.info(msg)
    return True, msg

if __name__ == "__main__":
    from logging_setup import setup_logging
    setup_logging()
    sucesso, mensagem = run_consolidation()
    if sucesso:
        print(mensagem)
    else:
        print(f"ERRO: {mensagem}")