import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup

# Dependências do Selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from logging_setup import get_logger

logger = get_logger('scraper')

class NFCeScraper:
    def __init__(self, config):
        self.config = config
        self.output_dir = config.get('paths', {}).get('json_output_dir', 'nfce_data')
        os.makedirs(self.output_dir, exist_ok=True)
        self.driver = None
        logger.info(f"NFCeScraper Híbrido iniciado. Saída de JSON em: {self.output_dir}")

    def _get_request_headers(self):
        """
        Headers essenciais para evitar bloqueio da SEFAZ (Mantido da versão atual).
        """
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }

    def extrair_dados(self, url):
        data_base = {
            "_url_origem": url,
            "geral": {},
            "vendedor": {},
            "consumidor": {},
            "totais": {},
            "produtos": []
        }

        try:
            if "dfe-portal.svrs.rs.gov.br" in url:
                logger.debug("Detectado layout NOVO (DFE). Usando Selenium.")
                return self._parse_layout_novo_dfe(url, data_base)
            else:
                logger.debug("Detectado layout ANTIGO (Sefaz). Usando Requests.")
                return self._parse_layout_antigo_sefaz(url, data_base)
        except Exception as e:
            logger.error(f"Erro catastrófico ao processar URL {url}: {e}", exc_info=True)
            return None

    # ==============================================================================
    # HELPER METHODS
    # ==============================================================================

    def _limpar_texto(self, texto):
        return re.sub(r'\s+', ' ', texto).strip() if texto else ""

    def _validar_data(self, texto):
        if not texto: return None
        match = re.search(r"(\d{2}/\d{2}/\d{4})", texto)
        if match: return match.group(1)
        return None

    def _eh_valor_tributo_valido(self, valor):
        if not isinstance(valor, (int, float)): return False
        if valor <= 0 or valor > 50000: return False
        return True

    def _converter_valor_inteligente(self, valor_str):
        if not valor_str: return 0.0
        limpo = re.sub(r'[^\d,.]', '', str(valor_str))
        try:
            if not limpo: return 0.0
            if ',' in limpo:
                return float(limpo.replace('.', '').replace(',', '.'))
            if '.' in limpo:
                partes = limpo.split('.')
                if len(partes[-1]) == 3 and len(partes) > 1: 
                    return float(limpo.replace('.', ''))
                else:
                    return float(limpo)
            return float(limpo)
        except ValueError:
            return 0.0

    def _extrair_valores_monetarios(self, texto):
        matches = re.findall(r"(?:R\$\s*)?(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})\b", texto)
        valores_validos = []
        for val_str in matches:
            val_float = self._converter_valor_inteligente(val_str)
            if self._eh_valor_tributo_valido(val_float):
                valores_validos.append(val_float)
        return sorted(list(set(valores_validos)), reverse=True)
    
    def _extrair_data_forca_bruta(self, soup):
        if hasattr(soup, 'get_text'):
            texto = soup.get_text(" ", strip=True)
        else:
            texto = str(soup)
        matches = re.findall(r"(\d{2}/\d{2}/\d{4})", texto)
        for dt in matches:
            try:
                dia, mes, ano = map(int, dt.split('/'))
                if 2020 <= ano <= 2030 and 1 <= mes <= 12 and 1 <= dia <= 31:
                    return dt
            except: continue
        return "N/A"

    # ==============================================================================
    # LÓGICA DE TRIBUTOS (Mantida da versão atual)
    # ==============================================================================

    def _calcular_impostos_inteligente(self, soup_or_text):
        if isinstance(soup_or_text, str):
            full_text = soup_or_text
            soup = None
        else:
            soup = soup_or_text
            full_text = soup.get_text(" ", strip=True)

        if soup:
            tributo_elements = soup.find_all(['div', 'span', 'p'], 
                string=re.compile(r'(tribut|imposto|lei\s*12\.?741|ibpt|fonte)', re.IGNORECASE))
            for elem in tributo_elements:
                context_elem = elem.parent if elem.parent else elem
                context_text = context_elem.get_text(" ", strip=True)
                resultado = self._extrair_valores_tributos_detalhado(context_text)
                if resultado and self._converter_valor_inteligente(resultado.get('total', '0')) > 0:
                    return resultado

        rodape_text = full_text[-4000:]
        rodape_lower = rodape_text.lower()
        termos = [r"valor\s*aprox\.?\s*tribut", r"fonte:\s*ibpt", r"lei\s*12\.?741", r"tributos?\s*(?:fed|est)"]
        
        idx_inicio = -1
        for termo_pattern in termos:
            match = re.search(termo_pattern, rodape_lower)
            if match:
                idx_inicio = match.start()
                break
        
        if idx_inicio == -1:
            return {"total": "0,00", "federal": "0,00", "estadual": "0,00"}

        inicio_contexto = max(0, idx_inicio - 300)
        fim_contexto = min(len(rodape_text), idx_inicio + 1500)
        contexto = rodape_text[inicio_contexto:fim_contexto]
        return self._extrair_valores_tributos_detalhado(contexto)

    def _extrair_valores_tributos_detalhado(self, texto):
        texto_lower = texto.lower()
        resultado = {"total": "0,00", "federal": "0,00", "estadual": "0,00", "municipal": "0,00"}
        
        patterns = {
            "federal": r"(?:tribut[oa]s?\s+)?(?:fed(?:eral)?|fonte)\s*:?\s*(?:R\$\s*)?(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
            "estadual": r"(?:tribut[oa]s?\s+)?(?:est(?:adual)?)\s*:?\s*(?:R\$\s*)?(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
            "municipal": r"(?:tribut[oa]s?\s+)?(?:mun(?:icipal)?)\s*:?\s*(?:R\$\s*)?(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})"
        }
        
        valores_encontrados = []
        for tipo, pattern in patterns.items():
            match = re.search(pattern, texto_lower)
            if match:
                idx = texto_lower.find(match.group(0))
                val_str = re.search(r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})", texto[idx:idx+100])
                if val_str:
                    val = self._converter_valor_inteligente(val_str.group(1))
                    if self._eh_valor_tributo_valido(val):
                        resultado[tipo] = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        valores_encontrados.append(val)

        if not valores_encontrados:
            valores_genericos = self._extrair_valores_monetarios(texto)
            if len(valores_genericos) >= 2:
                resultado["federal"] = f"{valores_genericos[0]:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                resultado["estadual"] = f"{valores_genericos[1]:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                valores_encontrados = valores_genericos[:2]
            elif len(valores_genericos) == 1:
                resultado["total"] = f"{valores_genericos[0]:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                valores_encontrados = valores_genericos

        if valores_encontrados:
            total_calc = sum(valores_encontrados)
            resultado["total"] = f"{total_calc:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            
        return resultado

    # ==============================================================================
    # SELENIUM MANAGEMENT
    # ==============================================================================

    def _get_selenium_driver(self):
        if self.driver and self.driver.session_id:
            try:
                _ = self.driver.current_url
                return self.driver
            except Exception:
                self.driver = None

        logger.info("Iniciando nova instância do driver Selenium Headless.")
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            return self.driver
        except Exception as e:
            logger.error(f"Falha ao iniciar o ChromeDriver: {e}")
            return None

    def close_driver(self):
        if self.driver:
            try:
                logger.info("Fechando driver Selenium.")
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    # ==============================================================================
    # PARSERS: LAYOUT ANTIGO (SEFAZ)
    # ==============================================================================

    def _parse_layout_antigo_sefaz(self, url, data):
        try:
            response = requests.get(url, headers=self._get_request_headers(), timeout=15)
            if "dfe-portal.svrs.rs.gov.br" in response.url:
                return self._parse_layout_novo_dfe(response.url, data)
            if response.status_code != 200:
                logger.warning(f"Status code {response.status_code} para URL {url}")
                return None
            
            soup = BeautifulSoup(response.text, "html.parser")
            if "acesso negado" in soup.get_text().lower():
                logger.warning("Acesso negado detectado. Tentando Selenium...")
                return self._parse_layout_novo_dfe(url, data)

            data["geral"] = self._parse_geral_antigo(soup, url)
            data["vendedor"] = self._parse_vendedor_antigo(soup)
            data["consumidor"] = self._parse_consumidor_antigo(soup)
            data["totais"] = self._parse_totais_antigo(soup)
            data["produtos"] = self._parse_produtos_antigo(soup)
            self._salvar_json(data)
            return data
        except Exception as e:
            logger.error(f"[Layout Antigo] Erro: {e}", exc_info=True)
            return None

    def _parse_geral_antigo(self, soup, url):
        geral = {}
        chave = re.search(r"p=(\d{44})", url)
        geral["chave_acesso"] = chave.group(1) if chave else "N/A"
        
        # --- ADAPTAÇÃO DA VERSÃO 4 (Lógica de Data) ---
        # Busca tag que contém "Emissão:" e "Consumidor" simultaneamente
        data_emissao_tag = soup.find(lambda tag: "Emissão:" in tag.text and "Consumidor" in tag.text)
        if data_emissao_tag:
            data_match = re.search(r"Emissão:\s*(\d{2}/\d{2}/\d{4})", data_emissao_tag.get_text())
            geral["data_emissao"] = data_match.group(1) if data_match else "N/A"
        else:
             # Fallback: tenta força bruta se a lógica da V4 falhar
            geral["data_emissao"] = self._extrair_data_forca_bruta(soup)
        # --------------------------------------------------

        status_tag = soup.find("div", class_="alert")
        geral["status_nota"] = self._limpar_texto(status_tag.get_text()) if status_tag else "Ativa"
        return geral

    def _parse_vendedor_antigo(self, soup):
        vendedor = {}
        topo = soup.find("div", class_="txtTopo")
        if topo:
            txt = self._limpar_texto(topo.get_text(" "))
            cnpj = re.search(r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", txt)
            vendedor["cnpj"] = cnpj.group(1) if cnpj else "N/A"
            vendedor["razao_social"] = self._limpar_texto(txt.split(vendedor["cnpj"])[0]) if cnpj else txt
        return vendedor

    def _parse_consumidor_antigo(self, soup):
        cpf_tag = soup.find(lambda t: t.name in ['li','div'] and ("CPF" in t.text or "Consumidor" in t.text))
        cpf = "Não informado"
        if cpf_tag:
            m = re.search(r"(\d{3}\.\d{3}\.\d{3}-\d{2})", cpf_tag.get_text())
            if m: cpf = m.group(1)
        return {"cpf": cpf}

    def _parse_totais_antigo(self, soup):
        totais = {}
        total_tag = soup.find("div", id="linhaTotal")
        val = "0,00"
        if total_tag:
            v = total_tag.find("span", class_="totalNumb")
            if v: val = self._limpar_texto(v.get_text())
        totais["valor_total"] = val
        
        tributos = self._calcular_impostos_inteligente(soup)
        if isinstance(tributos, dict):
            totais.update({
                "valor_total_tributos": tributos.get("total", "0,00"),
                "tributo_federal": tributos.get("federal", "0,00"),
                "tributo_estadual": tributos.get("estadual", "0,00"),
                "tributo_municipal": tributos.get("municipal", "0,00")
            })
        return totais

    def _parse_produtos_antigo(self, soup):
        produtos = []
        tabela = soup.find("table", id="tabResult")
        if not tabela: return []
        for tr in tabela.find_all("tr"):
            try:
                if not tr.find("span", class_="txtTit"): continue
                produtos.append({
                    "descricao": self._limpar_texto(tr.find("span", class_="txtTit").get_text()),
                    "codigo": self._limpar_texto(tr.find("span", class_="RCod").get_text()).replace("(Código:", "").replace(")", ""),
                    "quantidade": self._limpar_texto(tr.find("span", class_="Rqtd").get_text()).replace("Qtde.:", ""),
                    "unidade": self._limpar_texto(tr.find("span", class_="RUN").get_text()).replace("UN:", ""),
                    "valor_unitario": self._limpar_texto(tr.find("span", class_="RvlUnit").get_text()).replace("Vl. Unit.:", ""),
                    "valor_total": self._limpar_texto(tr.find("span", class_="valor").get_text())
                })
            except: continue
        return produtos

    # ==============================================================================
    # PARSERS: LAYOUT NOVO (DFE)
    # ==============================================================================

    def _parse_layout_novo_dfe(self, url, data):
        driver = self._get_selenium_driver()
        if not driver: return None
        try:
            driver.get(url)
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#tabProdutos, #tabResult")))
            time.sleep(1.0)
            soup = BeautifulSoup(driver.page_source, "html.parser")
            
            if soup.find("table", id="tabProdutos"):
                data["produtos"] = self._parse_produtos_dfe(soup)
            else:
                data["produtos"] = self._parse_produtos_antigo(soup)

            data["geral"] = self._parse_geral_dfe(soup, url)
            data["vendedor"] = self._parse_vendedor_dfe(soup)
            data["consumidor"] = self._parse_consumidor_dfe(soup)
            data["totais"] = self._parse_totais_dfe(soup)

            self._salvar_json(data)
            return data
        except Exception as e:
            logger.error(f"[Layout Novo] Erro: {e}", exc_info=True)
            self.close_driver()
            return None

    def _find_dfe_label_val(self, soup, panel_key, label_key):
        try:
            panel = None
            h4 = soup.find(lambda t: t.name=='h4' and panel_key in t.text)
            if h4: panel = h4.find_parent("div")
            if not panel:
                col = soup.find("div", attrs={"data-role": "collapsible"})
                if col and panel_key in col.get_text(): panel = col
            
            if not panel: return "N/A"
            
            lbl = panel.find(["label", "strong"], string=re.compile(re.escape(label_key), re.IGNORECASE))
            if lbl:
                sib = lbl.find_next_sibling()
                if sib: return self._limpar_texto(sib.get_text())
                return self._limpar_texto(lbl.parent.get_text().replace(lbl.get_text(), ""))
        except: pass
        return "N/A"

    def _parse_geral_dfe(self, soup, url):
        geral = {}
        chave = re.search(r"(?:chave|p)=(\d{44})", url)
        geral["chave_acesso"] = chave.group(1) if chave else "N/A"
        
        # --- ADAPTAÇÃO DA VERSÃO 4 (Lógica de Data) ---
        # A V4 buscava explicitamente por "Data de Emissão" dentro do painel "NFC-e"
        dt = "N/A"
        # Tenta "Data de Emissão" (V4 Style)
        val = self._find_dfe_label_val(soup, "NFC-e", "Data de Emissão")
        if val == "N/A":
             # Tenta apenas "Emissão" caso o layout varie levemente
             val = self._find_dfe_label_val(soup, "NFC-e", "Emissão")
        
        if val != "N/A":
            dt = val.split(" ")[0]
        else:
            # Fallback para força bruta se não achar nos labels
             dt = self._extrair_data_forca_bruta(soup)
        # --------------------------------------------------
        
        geral["data_emissao"] = dt
        geral["status_nota"] = "Ativa"
        return geral

    def _parse_vendedor_dfe(self, soup):
        vendedor = {}
        vendedor["razao_social"] = self._find_dfe_label_val(soup, "Emitente", "Razão Social")
        if vendedor["razao_social"] == "N/A":
            # Tenta label V4
            vendedor["razao_social"] = self._find_dfe_label_val(soup, "Emitente", "Nome / Razão Social")
        
        if vendedor["razao_social"] == "N/A":
             topo = soup.find("div", class_="txtTopo")
             if topo: vendedor["razao_social"] = self._limpar_texto(topo.get_text())
        
        vendedor["cnpj"] = self._find_dfe_label_val(soup, "Emitente", "CNPJ")
        if vendedor["cnpj"] == "N/A":
            m = re.search(r"CNPJ:\s*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", soup.get_text())
            if m: vendedor["cnpj"] = m.group(1)
        return vendedor

    def _parse_consumidor_dfe(self, soup):
        cpf = self._find_dfe_label_val(soup, "Destinatário", "CPF")
        if cpf == "N/A": cpf = self._find_dfe_label_val(soup, "Consumidor", "CPF")
        if cpf == "N/A": cpf = self._find_dfe_label_val(soup, "Destinatário", "CNPJ / CPF") # V4 Style
        
        if cpf == "N/A":
            m = re.search(r"(\d{3}\.\d{3}\.\d{3}-\d{2})", soup.get_text())
            if m: cpf = m.group(1)
        
        return {"cpf": cpf if cpf != "N/A" else "Não informado"}

    def _parse_totais_dfe(self, soup):
        totais = {}
        valor = "0,00"
        linhas = soup.find_all("div", id="linhaTotal")
        
        # Tenta encontrar "A Pagar" ou "Valor total da nota" (V4)
        for div in linhas:
            lbl = div.find("label")
            if lbl:
                txt_lbl = lbl.get_text().lower()
                if "pagar" in txt_lbl or "pago" in txt_lbl or "total da nota" in txt_lbl:
                    val_tag = div.find_next("span", class_="totalNumb") or lbl.find_next_sibling()
                    if val_tag:
                        valor = self._limpar_texto(val_tag.get_text())
                        break
        
        totais["valor_total"] = valor
        
        tributos = self._calcular_impostos_inteligente(soup)
        if isinstance(tributos, dict):
            totais.update({
                "valor_total_tributos": tributos.get("total", "0,00"),
                "tributo_federal": tributos.get("federal", "0,00"),
                "tributo_estadual": tributos.get("estadual", "0,00"),
                "tributo_municipal": tributos.get("municipal", "0,00")
            })
        return totais

    def _parse_produtos_dfe(self, soup):
        produtos = []
        tbody = soup.find("tbody")
        if not tbody: return []
        for tr in tbody.find_all("tr"):
            cols = tr.find_all("td")
            if len(cols) < 5: continue
            try:
                produtos.append({
                    "descricao": self._limpar_texto(cols[0].find("span", class_="txtDesc").get_text()),
                    "codigo": self._limpar_texto(cols[0].find("span", class_="txtCod").get_text()).replace("(Código:", "").replace(")", ""),
                    "quantidade": self._limpar_texto(cols[1].get_text()),
                    "unidade": self._limpar_texto(cols[2].get_text()),
                    "valor_unitario": self._limpar_texto(cols[3].get_text()),
                    "valor_total": self._limpar_texto(cols[4].get_text())
                })
            except: continue
        return produtos

    def _salvar_json(self, data):
        try:
            chave = data.get("geral", {}).get("chave_acesso", f"sem_chave_{int(time.time())}")
            path = os.path.join(self.output_dir, f"{chave}.json")
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            logger.info(f"JSON salvo: {path}")
        except Exception as e:
            logger.error(f"Erro IO ao salvar JSON: {e}")