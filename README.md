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
- Google Chrome (para o scraping) 
- Dependências de C++
- Bibliotecas listadas no `requirements.txt`

### 🖥️ Guia de Instalação no Windows

1. **Instale o Python:** Baixe em [python.org](https://www.python.org/). **Importante:** Marque "Add Python to PATH".
2. **Dependências de C++:** Caso ocorram erros de DLL, instale o [Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe).
3. **ZBar (Leitura de QR Code):** - Se o sistema reportar erro na `zbar shared library`, instale o [ZBar for Windows](https://sourceforge.net/projects/zbar/files/zbar/0.10/zbar-0.10-setup.exe/download).
4. **Câmera:**
   - Se for usar o celular como câmera (RECOMENDADO), instale o [DroidCam Client](https://www.dev47apps.com/droidcam/windows/) no windows e o app no telefone android.
   - Se for usar webcam, altere o arquivo `config.json` para `"camera_source": 0`.
5. **Instale os módulos do python** Listados em requirements.txt
6. **Baixe o respectivo Chromedriver**
