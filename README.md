# NFCe Reader Pro - Monitor de Sustentabilidade e ODS

Este é um sistema desktop em Python para leitura, extração e análise de Notas Fiscais de Consumidor Eletrônica (NFC-e).
O projeto foca em transformar dados de consumo em insights sobre saúde e impacto ambiental, alinhando-se aos Objetivos de Desenvolvimento Sustentável (ODS) da ONU.

## 🚀 Funcionalidades

- **Captura via QR Code:** Leitura em tempo real usando a câmera (suporte a DroidCam).
- **Scraping Híbrido:** Extração automática de dados dos portais SEFAZ (Selenium/BS4).
- **Painel ODS 13 (Ação Climática):** Cálculo automático da pegada de carbono ($CO_2e$) com base nas categorias de produtos.
- **Painel ODS 3 (Saúde e Bem-Estar):** Análise da proporção de alimentos ultraprocessados vs. naturais.
- **Gestão Financeira:** Curva ABC de produtos, análise de tributos e gastos por estabelecimento.
- **Exportação:** Geração de relatórios em PDF, CSV e Excel.

## 🛠️ Pré-requisitos

- Python 3.10+
- OpenCV
- Droidcam
- Google Chrome (para o scraping) + respectivo chrome driver
- Bibliotecas listadas no `requirements.txt`
