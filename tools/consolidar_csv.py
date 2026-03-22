import os
import json
import pandas as pd
from datetime import datetime
import sys
import logging

# Adiciona o diretório raiz ao path para importar o logging_setup
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from logging_setup import setup_logging, get_logger
except ImportError:
    print("Erro: Não foi possível importar o 'logging_setup'. Execute a partir do diretório raiz.")
    sys.exit(1)

def load_config(config_path='../config.json'):
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except Exception as e:
        print(f"Erro ao carregar config: {e}")
        return None

def consolidar_dados_nfce(config):
    logger = get_logger('consolidator')
    logger.info("Iniciando a consolidação de dados...")

    JSON_SOURCE_DIR = config.get('paths', {}).get('json_output_dir', 'nfce_data')
    CONSOLIDATED_OUTPUT_DIR = config.get('paths', {}).get('consolidated_output_dir', 'nfce_consolidado')
    
    if not os.path.exists(JSON_SOURCE_DIR):
        logger.error(f"Diretório de origem não encontrado: {JSON_SOURCE_DIR}")
        return

    all_product_records = []
    
    for filename in os.listdir(JSON_SOURCE_DIR):
        if not filename.endswith(".json"):
            continue
        file_path = os.path.join(JSON_SOURCE_DIR, filename)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                nfce_data = json.load(f)
        except Exception as e:
            logger.warning(f"Erro ao ler {filename}: {e}")
            continue

        # --- Metadados da Nota ---
        chave_acesso = nfce_data.get('geral', {}).get('chave_acesso') or os.path.splitext(filename)[0]
        data_emissao_raw = nfce_data.get('geral', {}).get('data_emissao', '')
        data_emissao = data_emissao_raw.split(' ')[0] if ' ' in data_emissao_raw else data_emissao_raw or 'N/A'

        metadata = {
            'chave_nfce': chave_acesso,
            'data_emissao': data_emissao,
            'vendedor_razao_social': nfce_data.get('vendedor', {}).get('razao_social', 'N/A'),
            'vendedor_cnpj': nfce_data.get('vendedor', {}).get('cnpj', 'N/A'),
            'consumidor_cpf': nfce_data.get('consumidor', {}).get('cpf', 'Não Informado'),
            'valor_total_nota': nfce_data.get('totais', {}).get('valor_total', '0')
        }

        produtos = nfce_data.get('produtos', [])
        if not produtos:
            logger.warning(f"Nota {chave_acesso} não possui produtos, pulando.")
            continue

        for item in produtos:
            try:
                record = {
                    **metadata,
                    'descricao_produto': item.get('descricao', 'N/A'),
                    'quantidade': item.get('quantidade', '0'),
                    'unidade': item.get('unidade', 'N/A'),
                    'valor_unitario': item.get('valor_unitario', '0'),
                    'valor_total_item': item.get('valor_total', '0')
                }
                all_product_records.append(record)
            except Exception as e:
                logger.error(f"Erro processando item em {chave_acesso}: {e}")

    if not all_product_records:
        logger.info("Nenhum dado de produto encontrado para consolidar.")
        return

    df = pd.DataFrame(all_product_records)
    
    # Limpeza de dados (crucial)
    num_cols = ['quantidade', 'valor_unitario', 'valor_total_item', 'valor_total_nota']
    for col in num_cols:
        # Remove "R$" e outros caracteres, substitui vírgula por ponto
        df[col] = df[col].astype(str).str.replace(r'[^\d,\.]', '', regex=True).str.replace(',', '.')
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    df['data_emissao_dt'] = pd.to_datetime(df['data_emissao'], format='%d/%m/%Y', errors='coerce')
    df = df.sort_values(by='data_emissao_dt', ascending=False) # Ordena

    os.makedirs(CONSOLIDATED_OUTPUT_DIR, exist_ok=True)
    
    TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUTPUT_CSV_FILE = f"nfce_consolidada_{TIMESTAMP}.csv"
    output_path = os.path.join(CONSOLIDATED_OUTPUT_DIR, OUTPUT_CSV_FILE)
    
    # Salvar em CSV (padrão Brasil: ; e ,)
    df.to_csv(output_path, index=False, encoding='utf-8-sig', sep=';', decimal=',')
    
    logger.info("="*70)
    logger.info("CONSOLIDAÇÃO CONCLUÍDA!")
    logger.info(f"Total de linhas (itens): {len(df):,}")
    logger.info(f"NFC-es únicas: {df['chave_nfce'].nunique():,}")
    logger.info(f"Arquivo salvo em: {output_path}")
    logger.info("="*70)

if __name__ == "__main__":
    setup_logging() # Configura o log
    config = load_config()
    if config:
        consolidar_dados_nfce(config)
    else:
        print("Erro: Não foi possível carregar o config.json. Saindo.")