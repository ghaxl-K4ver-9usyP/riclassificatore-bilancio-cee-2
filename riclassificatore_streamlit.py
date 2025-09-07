#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
RICLASSIFICATORE BILANCIO CEE - VERSIONE STREAMLIT
Sistema completamente dinamico per riclassificazione bilanci
Versione 4.0 - Interfaccia Web con Streamlit
================================================================================
"""

import streamlit as st
import re
import json
import csv
import warnings
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
import io
import base64

# Librerie per parsing PDF e Excel
try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    import openpyxl
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False

# Configurazione pagina Streamlit
st.set_page_config(
    page_title="Riclassificatore Bilancio CEE",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizzato
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    .main-header {
        text-align: center;
        padding: 2rem;
        background: white;
        border-radius: 10px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .info-box {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    .success-message {
        background: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .error-message {
        background: #f8d7da;
        color: #721c24;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# CONFIGURAZIONE MAPPING CONTI
# =============================================================================

class MappingConfigurator:
    """Gestisce la configurazione dei mapping dei conti"""
    
    @staticmethod
    def carica_mapping_default() -> Dict:
        """Carica il mapping di default dei conti CEE"""
        return {
            "attivo": {
                "immobilizzazioni": {
                    "immateriali": {
                        "pattern": r"1[-_]7[-_]\d+",
                        "voci": ["software", "licenze", "brevetti", "avviamento"]
                    },
                    "materiali": {
                        "terreni_fabbricati": {
                            "pattern": r"1[-_]6[-_](10|11)",
                            "voci": ["fabbricato", "terreno"]
                        },
                        "impianti": {
                            "pattern": r"1[-_]6[-_](1|2|13)",
                            "voci": ["impianti", "macchinari", "centrale"]
                        },
                        "attrezzature": {
                            "pattern": r"1[-_]6[-_]3",
                            "voci": ["attrezzatura", "attrezzature"]
                        },
                        "altri": {
                            "pattern": r"1[-_]6[-_](4|5|6)",
                            "voci": ["automezzi", "macchine", "mobili"]
                        }
                    },
                    "finanziarie": {
                        "pattern": r"1[-_]16[-_]\d+",
                        "voci": ["titoli", "partecipazioni", "crediti"]
                    }
                },
                "circolante": {
                    "rimanenze": {
                        "pattern": r"1[-_]10[-_]\d+",
                        "voci": ["magazzino", "rimanenze", "prodotti"]
                    },
                    "crediti": {
                        "clienti": {
                            "pattern": r"1[-_](3|4)[-_]\d+",
                            "voci": ["clienti", "effetti"]
                        },
                        "altri": {
                            "pattern": r"1[-_](5|13)[-_]\d+",
                            "voci": ["crediti", "anticipi", "depositi"]
                        }
                    },
                    "disponibilita": {
                        "pattern": r"1[-_](1|2)[-_]?\d*",
                        "voci": ["cassa", "banche", "depositi"]
                    }
                },
                "ratei_risconti": {
                    "pattern": r"1[-_]8[-_]\d+",
                    "voci": ["ratei", "risconti"]
                }
            },
            "passivo": {
                "patrimonio": {
                    "pattern": r"2[-_]13[-_]\d+",
                    "voci": ["capitale", "riserva", "utili"]
                },
                "fondi": {
                    "pattern": r"2[-_](8|12)[-_]\d*",
                    "voci": ["tfr", "fondi", "accantonamenti"]
                },
                "debiti": {
                    "pattern": r"2[-_](2|3|4|6)[-_]?\d*",
                    "voci": ["debiti", "fornitori", "banche", "finanziamenti"]
                },
                "ratei_risconti": {
                    "pattern": r"2[-_]7[-_]\d+",
                    "voci": ["ratei", "risconti"]
                }
            },
            "fondi_ammortamento": {
                "pattern": r"2[-_]9[-_]\d+",
                "voci": ["ammortamento", "amm.", "f.amm"]
            }
        }

# =============================================================================
# PARSER DATI DINAMICO
# =============================================================================

class ParserDatiDinamico:
    """Parser universale per diversi formati di input"""
    
    def __init__(self, mapping: Optional[Dict] = None):
        self.mapping = mapping or MappingConfigurator.carica_mapping_default()
        self.validator = CodiceContoValidator()
        
    def parse_uploaded_file(self, uploaded_file) -> Dict:
        """Parse file caricato tramite Streamlit"""
        
        # Determina tipo file
        file_extension = Path(uploaded_file.name).suffix.lower()[1:]
        
        if file_extension == 'csv':
            return self.parse_csv_from_stream(uploaded_file)
        elif file_extension in ['xlsx', 'xls']:
            return self.parse_excel_from_stream(uploaded_file)
        elif file_extension == 'json':
            return self.parse_json_from_stream(uploaded_file)
        elif file_extension == 'pdf':
            return self.parse_pdf_from_stream(uploaded_file)
        else:
            raise ValueError(f"Tipo file non supportato: {file_extension}")
    
    def parse_csv_from_stream(self, file_stream) -> Dict:
        """Parse CSV da stream"""
        dati = {
            'info': {},
            'conti': [],
            'totali': {}
        }
        
        # Decodifica il file
        stringio = io.StringIO(file_stream.getvalue().decode("utf-8"))
        reader = csv.DictReader(stringio, delimiter=';')
        
        for row in reader:
            row = {k: v.strip() if v else '' for k, v in row.items()}
            conto = self._estrai_conto_da_riga_csv(row)
            if conto:
                dati['conti'].append(conto)
        
        return self._organizza_dati_cee(dati)
    
    def parse_excel_from_stream(self, file_stream) -> Dict:
        """Parse Excel da stream"""
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas necessario per parsing Excel")
        
        dati = {
            'info': {},
            'conti': [],
            'totali': {}
        }
        
        # Leggi Excel
        xl_file = pd.ExcelFile(file_stream)
        
        for sheet_name in xl_file.sheet_names:
            df = pd.read_excel(xl_file, sheet_name=sheet_name)
            df = df.dropna(how='all')
            
            for _, row in df.iterrows():
                conto = self._estrai_conto_da_riga_excel(row)
                if conto:
                    dati['conti'].append(conto)
        
        return self._organizza_dati_cee(dati)
    
    def parse_json_from_stream(self, file_stream) -> Dict:
        """Parse JSON da stream"""
        return json.loads(file_stream.getvalue())
    
    def parse_pdf_from_stream(self, file_stream) -> Dict:
        """Parse PDF da stream"""
        if not PDF_AVAILABLE:
            raise ImportError("pdfplumber necessario per parsing PDF")
        
        dati = {
            'info': {},
            'conti': [],
            'totali': {}
        }
        
        with pdfplumber.open(io.BytesIO(file_stream.getvalue())) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if not text:
                    continue
                
                tables = page.extract_tables()
                
                self._parse_info_from_text(text, dati['info'])
                
                for table in tables:
                    self._parse_conti_from_table(table, dati['conti'])
                
                self._parse_conti_from_text(text, dati['conti'])
        
        return self._organizza_dati_cee(dati)
    
    def _estrai_conto_da_riga_csv(self, row: Dict) -> Optional[Dict]:
        """Estrae conto da riga CSV"""
        codice = None
        descrizione = None
        valore = None
        
        for key, val in row.items():
            key_lower = key.lower()
            
            if 'codice' in key_lower or 'conto' in key_lower:
                codice = val
            elif 'descr' in key_lower or 'intestaz' in key_lower:
                descrizione = val
            elif 'saldo' in key_lower or 'importo' in key_lower or 'valore' in key_lower:
                valore = val
        
        if codice and valore:
            try:
                valore_float = float(valore.replace(',', '.'))
                return {
                    'codice': self.validator.formatta_codice(codice),
                    'descrizione': descrizione or '',
                    'valore': valore_float
                }
            except:
                pass
        
        return None
    
    def _estrai_conto_da_riga_excel(self, row: pd.Series) -> Optional[Dict]:
        """Estrae conto da riga Excel"""
        row_dict = row.to_dict()
        return self._estrai_conto_da_riga_csv(row_dict)
    
    def _parse_info_from_text(self, text: str, info: Dict):
        """Estrae informazioni generali dal testo"""
        patterns = {
            'societa': r'(?:società|ragione sociale|denominazione)[:\s]+(.+?)(?:\n|$)',
            'esercizio': r'(?:esercizio|anno)[:\s]+(\d{4})',
            'data_chiusura': r'(?:data chiusura|al)[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})',
            'partita_iva': r'(?:p\.iva|partita iva)[:\s]+(\d{11})',
            'codice_fiscale': r'(?:c\.f\.|codice fiscale)[:\s]+(\w{16})'
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                info[key] = match.group(1).strip()
    
    def _parse_conti_from_text(self, text: str, conti: List):
        """Estrae conti dal testo con regex"""
        pattern = r'([0-9]+[-.\s/_]+[0-9]+(?:[-.\s/_]+[0-9]+)?)\s+(.+?)\s+([-]?\d+(?:[.,]\d+)?)\s*[DA]?'
        
        for match in re.finditer(pattern, text):
            codice = match.group(1)
            descrizione = match.group(2)
            valore_str = match.group(3).replace(',', '.')
            
            try:
                valore = float(valore_str)
                conto = {
                    'codice': self.validator.formatta_codice(codice),
                    'descrizione': descrizione.strip(),
                    'valore': valore
                }
                conti.append(conto)
            except ValueError:
                continue
    
    def _parse_conti_from_table(self, table: List, conti: List):
        """Estrae conti da tabella"""
        if not table or len(table) < 2:
            return
        
        headers = table[0]
        
        idx_codice = self._trova_indice_colonna(headers, ['codice', 'conto', 'code'])
        idx_descr = self._trova_indice_colonna(headers, ['descrizione', 'intestazione', 'desc'])
        idx_valore = self._trova_indice_colonna(headers, ['saldo', 'importo', 'valore', 'dare', 'avere'])
        
        if idx_codice is None or idx_valore is None:
            return
        
        for row in table[1:]:
            if len(row) <= max(idx_codice, idx_valore):
                continue
            
            codice = row[idx_codice] if row[idx_codice] else ''
            descrizione = row[idx_descr] if idx_descr and row[idx_descr] else ''
            valore_str = row[idx_valore] if row[idx_valore] else '0'
            
            valore_str = re.sub(r'[^\d,.-]', '', str(valore_str))
            valore_str = valore_str.replace(',', '.')
            
            try:
                valore = float(valore_str) if valore_str else 0
                
                if codice and valore != 0:
                    conto = {
                        'codice': self.validator.formatta_codice(codice),
                        'descrizione': descrizione.strip(),
                        'valore': valore
                    }
                    conti.append(conto)
            except ValueError:
                continue
    
    def _trova_indice_colonna(self, headers: List, keywords: List) -> Optional[int]:
        """Trova indice colonna basato su keywords"""
        for i, header in enumerate(headers):
            if header:
                header_lower = str(header).lower()
                for keyword in keywords:
                    if keyword in header_lower:
                        return i
        return None
    
    def _organizza_dati_cee(self, dati_raw: Dict) -> Dict:
        """Organizza i dati grezzi nella struttura CEE"""
        struttura_cee = {
            'info': dati_raw.get('info', {}),
            'attivo': {
                'immobilizzazioni': {
                    'immateriali': [],
                    'materiali': {
                        'terreni_fabbricati': [],
                        'impianti': [],
                        'attrezzature': [],
                        'altri': []
                    },
                    'finanziarie': []
                },
                'circolante': {
                    'rimanenze': [],
                    'crediti': {
                        'clienti': [],
                        'tributari': [],
                        'altri': []
                    },
                    'disponibilita': []
                },
                'ratei_risconti': []
            },
            'passivo': {
                'patrimonio_netto': [],
                'fondi': [],
                'tfr': [],
                'debiti': [],
                'ratei_risconti': []
            }
        }
        
        for conto in dati_raw.get('conti', []):
            self._classifica_conto(conto, struttura_cee)
        
        self._calcola_totali(struttura_cee)
        
        return struttura_cee
    
    def _classifica_conto(self, conto: Dict, struttura: Dict):
        """Classifica un conto nella struttura CEE appropriata"""
        codice = conto['codice']
        descrizione = conto['descrizione'].lower()
        
        classificato = False
        
        for categoria, config in self.mapping['attivo'].items():
            if self._match_pattern_ricorsivo(codice, descrizione, config):
                self._inserisci_conto_ricorsivo(conto, struttura['attivo'], categoria, config)
                classificato = True
                break
        
        if not classificato:
            for categoria, config in self.mapping['passivo'].items():
                if self._match_pattern_ricorsivo(codice, descrizione, config):
                    self._inserisci_conto_ricorsivo(conto, struttura['passivo'], categoria, config)
                    classificato = True
                    break
    
    def _match_pattern_ricorsivo(self, codice: str, descrizione: str, config: Dict) -> bool:
        """Verifica match pattern ricorsivamente"""
        if 'pattern' in config:
            if re.match(config['pattern'], codice):
                return True
        
        if 'voci' in config:
            for voce in config['voci']:
                if voce in descrizione:
                    return True
        
        for key, value in config.items():
            if isinstance(value, dict):
                if self._match_pattern_ricorsivo(codice, descrizione, value):
                    return True
        
        return False
    
    def _inserisci_conto_ricorsivo(self, conto: Dict, dest: Dict, path: str, config: Dict):
        """Inserisce conto nella destinazione corretta"""
        current = dest
        parts = path.split('.')
        
        for part in parts:
            if part not in current:
                current[part] = []
            current = current[part]
        
        if isinstance(current, list):
            current.append(conto)
        elif isinstance(current, dict):
            for key, value in config.items():
                if isinstance(value, dict) and 'pattern' in value:
                    if re.match(value['pattern'], conto['codice']):
                        if key not in current:
                            current[key] = []
                        current[key].append(conto)
                        break
    
    def _calcola_totali(self, struttura: Dict):
        """Calcola totali per ogni sezione"""
        struttura['totali'] = {}
        
        totale_attivo = self._somma_ricorsiva(struttura['attivo'])
        struttura['totali']['attivo'] = totale_attivo
        
        totale_passivo = self._somma_ricorsiva(struttura['passivo'])
        struttura['totali']['passivo'] = totale_passivo
        
        struttura['totali']['quadratura'] = totale_attivo - totale_passivo
    
    def _somma_ricorsiva(self, obj: Any) -> float:
        """Somma ricorsiva di tutti i valori"""
        if isinstance(obj, dict):
            if 'valore' in obj:
                return float(obj['valore'])
            
            totale = 0
            for value in obj.values():
                totale += self._somma_ricorsiva(value)
            return totale
        
        elif isinstance(obj, list):
            totale = 0
            for item in obj:
                if isinstance(item, dict) and 'valore' in item:
                    totale += float(item['valore'])
                else:
                    totale += self._somma_ricorsiva(item)
            return totale
        
        return 0

# =============================================================================
# VALIDATORE CODICI
# =============================================================================

class CodiceContoValidator:
    """Validatore e formattatore per codici conto"""
    
    @staticmethod
    def formatta_codice(codice: str) -> str:
        """Formatta codice nel formato X_X_X"""
        if not codice:
            return ""
        
        codice = str(codice).strip()
        
        separatori = ['-', '.', '/', '\\', ' ', ',', ';', ':', '|']
        for sep in separatori:
            codice = codice.replace(sep, '_')
        
        while '__' in codice:
            codice = codice.replace('__', '_')
        
        return codice.strip('_')

# =============================================================================
# FUNZIONI VISUALIZZAZIONE STREAMLIT
# =============================================================================

def formatta_numero(valore: float) -> str:
    """Formatta numero in formato italiano"""
    try:
        return f"{valore:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except:
        return "0,00"

def mostra_tabella_bilancio(dati: Dict):
    """Mostra tabella del bilancio in Streamlit"""
    
    df_data = []
    
    # Processa attivo
    def processa_sezione(sezione, nome_sezione, prefisso=""):
        if isinstance(sezione, list):
            for conto in sezione:
                if isinstance(conto, dict):
                    df_data.append({
                        'Sezione': nome_sezione,
                        'Codice': conto.get('codice', ''),
                        'Descrizione': conto.get('descrizione', ''),
                        'Importo': conto.get('valore', 0)
                    })
        elif isinstance(sezione, dict):
            for key, value in sezione.items():
                if key not in ['info', 'totali']:
                    nome_sub = f"{nome_sezione} - {key.replace('_', ' ').title()}"
                    processa_sezione(value, nome_sub, prefisso + "  ")
    
    processa_sezione(dati.get('attivo', {}), 'ATTIVO')
    processa_sezione(dati.get('passivo', {}), 'PASSIVO')
    
    if df_data:
        df = pd.DataFrame(df_data)
        
        # Formatta colonna importo
        df['Importo Formattato'] = df['Importo'].apply(lambda x: formatta_numero(x))
        
        # Stile per valori negativi
        def color_negative(val):
            color = 'red' if val < 0 else 'black'
            return f'color: {color}'
        
        styled_df = df.style.applymap(color_negative, subset=['Importo'])
        
        st.dataframe(
            df[['Sezione', 'Codice', 'Descrizione', 'Importo Formattato']],
            use_container_width=True,
            height=600
        )

def genera_html_download(dati: Dict) -> str:
    """Genera HTML per download"""
    
    info = dati.get('info', {})
    
    html = f"""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bilancio CEE - {info.get('societa', 'N/A')} - {info.get('esercizio', 'N/A')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1, h2 {{ text-align: center; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background: #4CAF50; color: white; }}
        .sezione {{ background: #2c3e50; color: white; font-weight: bold; }}
        .totale {{ background: #d4e6f1; font-weight: bold; }}
        .numero {{ text-align: right; font-family: monospace; }}
        .negativo {{ color: #e74c3c; }}
    </style>
</head>
<body>
    <h1>BILANCIO RICLASSIFICATO CEE</h1>
    <h2>{info.get('societa', 'Società N/A')}</h2>
    <p style="text-align: center;">Esercizio {info.get('esercizio', 'N/A')}</p>
    
    <table>
        <thead>
            <tr>
                <th>Sezione</th>
                <th>Codice</th>
                <th>Descrizione</th>
                <th>Importo (€)</th>
            </tr>
        </thead>
        <tbody>
"""
    
    # Aggiungi righe
    def aggiungi_righe(sezione, nome_sezione):
        if isinstance(sezione, list):
            for conto in sezione:
                if isinstance(conto, dict):
                    valore = conto.get('valore', 0)
                    classe = 'negativo' if valore < 0 else ''
                    html_row = f"""
            <tr>
                <td>{nome_sezione}</td>
                <td>{conto.get('codice', '')}</td>
                <td>{conto.get('descrizione', '')}</td>
                <td class="numero {classe}">{formatta_numero(valore)}</td>
            </tr>
"""
                    return html_row
        elif isinstance(sezione, dict):
            html_rows = ""
            for key, value in sezione.items():
                if key not in ['info', 'totali']:
                    nome_sub = f"{nome_sezione} - {key.replace('_', ' ').title()}"
                    html_rows += aggiungi_righe(value, nome_sub)
            return html_rows
        return ""
    
    html += aggiungi_righe(dati.get('attivo', {}), 'ATTIVO')
    html += aggiungi_righe(dati.get('passivo', {}), 'PASSIVO')
    
    # Aggiungi totali
    if 'totali' in dati:
        html += f"""
            <tr class="totale">
                <td colspan="3">TOTALE ATTIVO</td>
                <td class="numero">{formatta_numero(dati['totali'].get('attivo', 0))}</td>
            </tr>
            <tr class="totale">
                <td colspan="3">TOTALE PASSIVO</td>
                <td class="numero">{formatta_numero(dati['totali'].get('passivo', 0))}</td>
            </tr>
            <tr class="totale">
                <td colspan="3">QUADRATURA</td>
                <td class="numero {'negativo' if dati['totali'].get('quadratura', 0) != 0 else ''}">{formatta_numero(dati['totali'].get('quadratura', 0))}</td>
            </tr>
"""
    
    html += """
        </tbody>
    </table>
</body>
</html>"""
    
    return html

# =============================================================================
# APPLICAZIONE PRINCIPALE STREAMLIT
# =============================================================================

def main():
    # Header
    st.markdown('<div class="main-header">', unsafe_allow_html=True)
    st.title("📊 Riclassificatore Bilancio CEE")
    st.markdown("**Sistema Dinamico per la Riclassificazione dei Bilanci**")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configurazione")
        
        st.markdown("### 📁 Formati Supportati")
        st.info("• CSV\n• Excel (XLSX/XLS)\n• JSON\n• PDF")
        
        st.markdown("### 📋 Istruzioni")
        st.markdown("""
        1. **Carica il file** del bilancio
        2. **Visualizza** l'anteprima dei dati
        3. **Scarica** il report in HTML
        """)
        
        # Verifica dipendenze
        st.markdown("### 🔧 Stato Dipendenze")
        col1, col2 = st.columns(2)
        with col1:
            if PDF_AVAILABLE:
                st.success("✅ PDF")
            else:
                st.error("❌ PDF")
        with col2:
            if EXCEL_AVAILABLE:
                st.success("✅ Excel")
            else:
                st.error("❌ Excel")
    
    # Tab principale
    tab1, tab2, tab3 = st.tabs(["📤 Carica File", "📊 Visualizza Dati", "⚙️ Configurazione Mapping"])
    
    with tab1:
        st.header("Carica File Bilancio")
        
        # Upload file
        uploaded_file = st.file_uploader(
            "Seleziona il file del bilancio",
            type=['csv', 'xlsx', 'xls', 'json', 'pdf'],
            help="Carica un file contenente i dati del bilancio"
        )
        
        if uploaded_file is not None:
            # Mostra info file
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Nome File", uploaded_file.name)
            with col2:
                size_mb = uploaded_file.size / (1024 * 1024)
                st.metric("Dimensione", f"{size_mb:.2f} MB")
            with col3:
                file_type = Path(uploaded_file.name).suffix[1:].upper()
                st.metric("Tipo", file_type)
            
            # Processa file
            if st.button("🔄 Processa File", type="primary"):
                with st.spinner("Elaborazione in corso..."):
                    try:
                        # Inizializza parser
                        parser = ParserDatiDinamico()
                        
                        # Parse file
                        dati = parser.parse_uploaded_file(uploaded_file)
                        
                        # Salva in session state
                        st.session_state['dati_bilancio'] = dati
                        
                        st.success("✅ File elaborato con successo!")
                        
                        # Mostra riepilogo
                        info = dati.get('info', {})
                        
                        st.markdown('<div class="info-box">', unsafe_allow_html=True)
                        st.subheader("📋 Informazioni Bilancio")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Società:** {info.get('societa', 'N/A')}")
                            st.write(f"**Esercizio:** {info.get('esercizio', 'N/A')}")
                            st.write(f"**Data Chiusura:** {info.get('data_chiusura', 'N/A')}")
                        with col2:
                            st.write(f"**P.IVA:** {info.get('partita_iva', 'N/A')}")
                            st.write(f"**Codice Fiscale:** {info.get('codice_fiscale', 'N/A')}")
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        # Mostra totali
                        if 'totali' in dati:
                            st.subheader("💰 Totali")
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.metric(
                                    "Totale Attivo",
                                    f"€ {formatta_numero(dati['totali'].get('attivo', 0))}"
                                )
                            
                            with col2:
                                st.metric(
                                    "Totale Passivo",
                                    f"€ {formatta_numero(dati['totali'].get('passivo', 0))}"
                                )
                            
                            with col3:
                                quadratura = dati['totali'].get('quadratura', 0)
                                st.metric(
                                    "Quadratura",
                                    f"€ {formatta_numero(quadratura)}",
                                    delta=None if quadratura == 0 else "Non quadra",
                                    delta_color="off" if quadratura == 0 else "inverse"
                                )
                        
                    except Exception as e:
                        st.error(f"❌ Errore durante l'elaborazione: {str(e)}")
    
    with tab2:
        st.header("Visualizzazione Dati Bilancio")
        
        if 'dati_bilancio' in st.session_state:
            dati = st.session_state['dati_bilancio']
            
            # Opzioni visualizzazione
            col1, col2 = st.columns([3, 1])
            with col2:
                vista = st.selectbox(
                    "Tipo Vista",
                    ["Tabella Completa", "Riepilogo", "Dettaglio Sezioni"]
                )
            
            if vista == "Tabella Completa":
                mostra_tabella_bilancio(dati)
            
            elif vista == "Riepilogo":
                # Mostra metriche principali
                st.subheader("📊 Riepilogo Bilancio")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("### Attivo")
                    for key in dati.get('attivo', {}).keys():
                        if key not in ['info', 'totali']:
                            totale = parser._somma_ricorsiva(dati['attivo'][key])
                            st.write(f"**{key.replace('_', ' ').title()}:** € {formatta_numero(totale)}")
                
                with col2:
                    st.markdown("### Passivo")
                    for key in dati.get('passivo', {}).keys():
                        if key not in ['info', 'totali']:
                            totale = parser._somma_ricorsiva(dati['passivo'][key])
                            st.write(f"**{key.replace('_', ' ').title()}:** € {formatta_numero(totale)}")
            
            elif vista == "Dettaglio Sezioni":
                # Mostra dettaglio per sezione
                sezione = st.selectbox(
                    "Seleziona Sezione",
                    ["Attivo - Immobilizzazioni", "Attivo - Circolante", 
                     "Passivo - Patrimonio", "Passivo - Debiti"]
                )
                
                st.subheader(f"Dettaglio: {sezione}")
                # Qui puoi aggiungere il codice per mostrare il dettaglio della sezione selezionata
            
            # Download
            st.markdown("---")
            st.subheader("📥 Scarica Report")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Download HTML
                html_content = genera_html_download(dati)
                b64 = base64.b64encode(html_content.encode()).decode()
                href = f'<a href="data:text/html;base64,{b64}" download="bilancio_cee.html">📄 Scarica HTML</a>'
                st.markdown(href, unsafe_allow_html=True)
            
            with col2:
                # Download JSON
                json_str = json.dumps(dati, indent=2, ensure_ascii=False)
                b64 = base64.b64encode(json_str.encode()).decode()
                href = f'<a href="data:application/json;base64,{b64}" download="bilancio_cee.json">📊 Scarica JSON</a>'
                st.markdown(href, unsafe_allow_html=True)
        
        else:
            st.warning("⚠️ Nessun dato caricato. Carica prima un file nella tab 'Carica File'.")
    
    with tab3:
        st.header("Configurazione Mapping Conti")
        
        st.info("🔧 Questa sezione permette di personalizzare il mapping dei conti CEE")
        
        # Mostra mapping corrente
        if st.checkbox("Mostra Mapping Corrente"):
            mapping = MappingConfigurator.carica_mapping_default()
            st.json(mapping)
        
        # Upload mapping personalizzato
        st.subheader("Carica Mapping Personalizzato")
        mapping_file = st.file_uploader(
            "Seleziona file JSON con mapping personalizzato",
            type=['json'],
            help="Il file deve contenere la struttura di mapping nel formato corretto"
        )
        
        if mapping_file:
            try:
                custom_mapping = json.loads(mapping_file.getvalue())
                st.success("✅ Mapping personalizzato caricato")
                st.session_state['custom_mapping'] = custom_mapping
            except Exception as e:
                st.error(f"❌ Errore nel file di mapping: {str(e)}")
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666;'>
            <p>Riclassificatore Bilancio CEE v4.0 - Powered by Streamlit</p>
            <p>© 2024 - Sistema Dinamico senza dati hard-coded</p>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()