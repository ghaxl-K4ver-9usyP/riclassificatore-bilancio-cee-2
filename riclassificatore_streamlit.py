#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
RICLASSIFICATORE BILANCIO CEE - VERSIONE STREAMLIT
Sistema completamente dinamico per riclassificazione bilanci
Versione 5.0 - Con Parser PDF Robusto per Streamlit Cloud
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

# Librerie per parsing Excel
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

# Librerie per parsing PDF
try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    from pdfminer.high_level import extract_text, extract_pages
    from pdfminer.layout import LAParams, LTTextBox, LTTextBoxHorizontal
    from pdfminer.pdfpage import PDFPage
    PDFMINER_AVAILABLE = True
except ImportError:
    PDFMINER_AVAILABLE = False

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
    .preview-box {
        background: #f0f0f0;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
        font-family: monospace;
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
                        "voci": ["software", "licenze", "brevetti", "avviamento", "costi di impianto"]
                    },
                    "materiali": {
                        "terreni_fabbricati": {
                            "pattern": r"1[-_]6[-_](10|11)",
                            "voci": ["fabbricato", "terreno", "immobile"]
                        },
                        "impianti": {
                            "pattern": r"1[-_]6[-_](1|2|13)",
                            "voci": ["impianti", "macchinari", "centrale", "attrezzature industriali"]
                        },
                        "attrezzature": {
                            "pattern": r"1[-_]6[-_]3",
                            "voci": ["attrezzatura", "attrezzature", "utensili"]
                        },
                        "altri": {
                            "pattern": r"1[-_]6[-_](4|5|6)",
                            "voci": ["automezzi", "macchine", "mobili", "arredi", "hardware"]
                        }
                    },
                    "finanziarie": {
                        "pattern": r"1[-_]16[-_]\d+",
                        "voci": ["titoli", "partecipazioni", "crediti finanziari", "azioni"]
                    }
                },
                "circolante": {
                    "rimanenze": {
                        "pattern": r"1[-_]10[-_]\d+",
                        "voci": ["magazzino", "rimanenze", "prodotti", "merci", "materie prime"]
                    },
                    "crediti": {
                        "clienti": {
                            "pattern": r"1[-_](3|4)[-_]\d+",
                            "voci": ["clienti", "effetti", "fatture da emettere", "crediti commerciali"]
                        },
                        "tributari": {
                            "pattern": r"1[-_]5[-_]1\d+",
                            "voci": ["erario", "iva", "crediti tributari", "imposte"]
                        },
                        "altri": {
                            "pattern": r"1[-_](5|13)[-_]\d+",
                            "voci": ["crediti diversi", "anticipi", "depositi", "cauzioni"]
                        }
                    },
                    "disponibilita": {
                        "pattern": r"1[-_](1|2)[-_]?\d*",
                        "voci": ["cassa", "banca", "banche", "depositi", "c/c", "denaro"]
                    }
                },
                "ratei_risconti": {
                    "pattern": r"1[-_]8[-_]\d+",
                    "voci": ["ratei attivi", "risconti attivi"]
                }
            },
            "passivo": {
                "patrimonio": {
                    "pattern": r"2[-_]13[-_]\d+",
                    "voci": ["capitale sociale", "riserva", "utili", "perdite", "patrimonio netto"]
                },
                "fondi": {
                    "pattern": r"2[-_](8|12)[-_]\d*",
                    "voci": ["tfr", "fondi", "accantonamenti", "fondo rischi", "trattamento"]
                },
                "debiti": {
                    "pattern": r"2[-_](2|3|4|6)[-_]?\d*",
                    "voci": ["debiti", "fornitori", "banche", "finanziamenti", "mutui", "prestiti"]
                },
                "ratei_risconti": {
                    "pattern": r"2[-_]7[-_]\d+",
                    "voci": ["ratei passivi", "risconti passivi"]
                }
            },
            "fondi_ammortamento": {
                "pattern": r"2[-_]9[-_]\d+",
                "voci": ["ammortamento", "f.do amm", "fondo ammortamento", "ammortamenti"]
            }
        }

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
        
        # Mantieni solo numeri e separatori
        codice = re.sub(r'[^\d\-\._/\s]', '', codice)
        
        # Sostituisci separatori con underscore
        separatori = ['-', '.', '/', '\\', ' ', ',', ';', ':', '|']
        for sep in separatori:
            codice = codice.replace(sep, '_')
        
        # Rimuovi underscore multipli
        while '__' in codice:
            codice = codice.replace('__', '_')
        
        return codice.strip('_')

# =============================================================================
# PARSER PDF ROBUSTO
# =============================================================================

class PDFParserRobusto:
    """Parser PDF ottimizzato per Streamlit Cloud"""
    
    def __init__(self):
        self.patterns_conti = [
            # Pattern standard bilancio: codice descrizione importo
            r'([0-9]{1,2}[-.\s/_]*[0-9]{1,2}[-.\s/_]*[0-9]{1,4})\s+([A-Za-zÀ-ÿ\s\.,\-\'&]{3,60})\s+([-]?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)',
            
            # Pattern con lettere: A.I.1) descrizione importo
            r'([A-Z]\.?[IVX]{0,3}\.?\d*\)?)\s+([A-Za-zÀ-ÿ\s\.,\-\'&]{3,60})\s+([-]?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)',
            
            # Pattern numerico semplice
            r'(\d{1,4})\s+([A-Za-zÀ-ÿ\s\.,\-\'&]{3,60})\s+([-]?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)',
            
            # Pattern con parentesi
            r'\((\d+)\)\s+([A-Za-zÀ-ÿ\s\.,\-\'&]{3,60})\s+([-]?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)',
        ]
        
        self.keywords_bilancio = [
            'immobilizzazioni', 'attivo', 'passivo', 'patrimonio', 'crediti', 
            'debiti', 'cassa', 'banca', 'fornitori', 'clienti', 'rimanenze',
            'capitale sociale', 'riserve', 'utile', 'perdita', 'ammortamento',
            'ratei', 'risconti', 'tfr', 'fondi', 'totale'
        ]
    
    def parse(self, file_stream) -> Dict:
        """Parse principale del PDF"""
        
        risultati = {
            'info': {},
            'conti': [],
            'totali': {},
            'testo_estratto': ''
        }
        
        # Prova prima pdfminer (più accurato)
        if PDFMINER_AVAILABLE:
            try:
                risultati = self._parse_con_pdfminer(file_stream)
            except Exception as e:
                st.warning(f"pdfminer fallito, uso PyPDF2: {str(e)[:100]}")
                if PYPDF2_AVAILABLE:
                    file_stream.seek(0)
                    risultati = self._parse_con_pypdf2(file_stream)
        
        # Altrimenti usa PyPDF2
        elif PYPDF2_AVAILABLE:
            risultati = self._parse_con_pypdf2(file_stream)
        
        else:
            st.error("❌ Nessuna libreria PDF disponibile. Installa PyPDF2 o pdfminer.six")
            return risultati
        
        # Post-processing e validazione
        risultati = self._valida_e_pulisci_risultati(risultati)
        
        return risultati
    
    def _parse_con_pdfminer(self, file_stream) -> Dict:
        """Parse usando pdfminer.six"""
        
        risultati = {
            'info': {},
            'conti': [],
            'totali': {},
            'testo_estratto': ''
        }
        
        try:
            # Parametri ottimizzati per bilanci
            laparams = LAParams(
                line_overlap=0.5,
                char_margin=2.0,
                word_margin=0.1,
                boxes_flow=0.5,
                detect_vertical=False,
                all_texts=True
            )
            
            # Estrai testo completo
            file_stream.seek(0)
            testo_completo = extract_text(file_stream, laparams=laparams)
            risultati['testo_estratto'] = testo_completo
            
            # Estrai per pagine con layout
            file_stream.seek(0)
            testo_strutturato = []
            
            for page_num, page_layout in enumerate(extract_pages(file_stream, laparams=laparams), 1):
                testo_pagina = []
                
                for element in page_layout:
                    if isinstance(element, (LTTextBox, LTTextBoxHorizontal)):
                        testo = element.get_text().strip()
                        if testo:
                            testo_pagina.append(testo)
                            
                            # Analizza ogni blocco di testo
                            self._analizza_blocco_testo(testo, risultati)
                
                if testo_pagina:
                    testo_strutturato.append('\n'.join(testo_pagina))
            
            # Analisi globale se abbiamo testo strutturato
            if testo_strutturato:
                testo_completo_strutturato = '\n'.join(testo_strutturato)
                self._estrai_tabelle_da_testo(testo_completo_strutturato, risultati)
            
        except Exception as e:
            st.error(f"Errore pdfminer: {str(e)[:200]}")
            raise
        
        return risultati
    
    def _parse_con_pypdf2(self, file_stream) -> Dict:
        """Parse usando PyPDF2"""
        
        risultati = {
            'info': {},
            'conti': [],
            'totali': {},
            'testo_estratto': ''
        }
        
        try:
            reader = PyPDF2.PdfReader(file_stream)
            testo_completo = []
            
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                testo = page.extract_text()
                
                if testo:
                    testo_completo.append(testo)
                    
                    # Analizza il testo della pagina
                    self._analizza_blocco_testo(testo, risultati)
            
            risultati['testo_estratto'] = '\n'.join(testo_completo)
            
            # Cerca tabelle nel testo completo
            if risultati['testo_estratto']:
                self._estrai_tabelle_da_testo(risultati['testo_estratto'], risultati)
            
        except Exception as e:
            st.error(f"Errore PyPDF2: {str(e)[:200]}")
            raise
        
        return risultati
    
    def _analizza_blocco_testo(self, testo: str, risultati: Dict):
        """Analizza un blocco di testo per estrarre informazioni"""
        
        # Estrai informazioni aziendali
        self._estrai_info_aziendali(testo, risultati['info'])
        
        # Estrai conti
        self._estrai_conti(testo, risultati['conti'])
        
        # Cerca totali
        self._estrai_totali(testo, risultati['totali'])
    
    def _estrai_info_aziendali(self, testo: str, info: Dict):
        """Estrae informazioni aziendali dal testo"""
        
        patterns = {
            'societa': [
                r'(?:Denominazione|Ragione Sociale|Società)[:\s]+([^\n]+)',
                r'([A-Z][A-Z\s&\.\-]+(?:S\.?R\.?L\.?|S\.?P\.?A\.?|S\.?N\.?C\.?))',
                r'Bilancio di\s+([^\n]+)',
            ],
            'esercizio': [
                r'(?:Esercizio|Anno)[:\s]+(\d{4})',
                r'(?:al\s+31[/\-]12[/\-])(\d{4})',
                r'(?:Bilancio\s+)(\d{4})',
                r'(\d{4})\s+(?:Bilancio)',
            ],
            'partita_iva': [
                r'(?:P\.?\s?IVA|Partita IVA)[:\s]+(\d{11})',
                r'(?:IT\s?)(\d{11})',
            ],
            'codice_fiscale': [
                r'(?:C\.?F\.?|Codice Fiscale)[:\s]+([A-Z0-9]{16})',
            ],
            'data_chiusura': [
                r'(?:chiuso al|al)\s+(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})',
                r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})',
            ]
        }
        
        for campo, pattern_list in patterns.items():
            if campo not in info or not info[campo]:
                for pattern in pattern_list:
                    match = re.search(pattern, testo, re.IGNORECASE | re.MULTILINE)
                    if match:
                        info[campo] = match.group(1).strip()
                        break
    
    def _estrai_conti(self, testo: str, conti_list: List):
        """Estrae conti dal testo usando pattern multipli"""
        
        # Prova ogni pattern
        for pattern in self.patterns_conti:
            for match in re.finditer(pattern, testo, re.MULTILINE | re.IGNORECASE):
                try:
                    codice = match.group(1).strip()
                    descrizione = match.group(2).strip()
                    valore_str = match.group(3).strip()
                    
                    # Pulisci descrizione
                    descrizione = re.sub(r'\s+', ' ', descrizione)
                    descrizione = descrizione.replace('...', '').strip()
                    
                    # Salta se descrizione troppo corta o sospetta
                    if len(descrizione) < 3 or descrizione.isdigit():
                        continue
                    
                    # Converti valore
                    valore = self._converti_importo(valore_str)
                    
                    if valore != 0 and len(descrizione) > 2:
                        conto = {
                            'codice': CodiceContoValidator.formatta_codice(codice),
                            'descrizione': descrizione,
                            'valore': valore
                        }
                        
                        # Evita duplicati esatti
                        if not self._conto_duplicato(conto, conti_list):
                            conti_list.append(conto)
                    
                except (ValueError, AttributeError, IndexError):
                    continue
    
    def _estrai_tabelle_da_testo(self, testo: str, risultati: Dict):
        """Estrae dati tabulari dal testo"""
        
        righe = testo.split('\n')
        in_tabella = False
        buffer_tabella = []
        
        for riga in righe:
            # Rileva se siamo in una sezione di bilancio
            if any(keyword in riga.lower() for keyword in self.keywords_bilancio):
                in_tabella = True
            
            # Se in tabella, cerca pattern di conti
            if in_tabella:
                # Conta numeri nella riga (possibile riga di dati)
                numeri = re.findall(r'\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?', riga)
                
                if len(numeri) >= 1:  # Almeno un importo
                    buffer_tabella.append(riga)
                elif len(buffer_tabella) > 3:
                    # Fine tabella, processala
                    self._processa_buffer_tabella(buffer_tabella, risultati)
                    buffer_tabella = []
                    in_tabella = False
        
        # Processa ultima tabella se presente
        if buffer_tabella:
            self._processa_buffer_tabella(buffer_tabella, risultati)
    
    def _processa_buffer_tabella(self, righe: List[str], risultati: Dict):
        """Processa un buffer di righe che sembrano una tabella"""
        
        for riga in righe:
            # Cerca pattern di conti nella riga
            self._estrai_conti(riga, risultati['conti'])
    
    def _estrai_totali(self, testo: str, totali: Dict):
        """Estrae i totali dal testo"""
        
        patterns_totali = [
            (r'(?:Totale\s+Attivo|TOTALE\s+ATTIVO)[:\s]+([-]?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)', 'attivo'),
            (r'(?:Totale\s+Passivo|TOTALE\s+PASSIVO)[:\s]+([-]?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)', 'passivo'),
            (r'(?:Patrimonio\s+Netto|PATRIMONIO\s+NETTO)[:\s]+([-]?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)', 'patrimonio_netto'),
            (r'(?:Utile|UTILE).*?[:\s]+([-]?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)', 'utile'),
            (r'(?:Perdita|PERDITA).*?[:\s]+([-]?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)', 'perdita'),
        ]
        
        for pattern, nome in patterns_totali:
            match = re.search(pattern, testo, re.IGNORECASE | re.MULTILINE)
            if match:
                try:
                    valore = self._converti_importo(match.group(1))
                    totali[nome] = valore
                except:
                    pass
    
    def _converti_importo(self, valore_str: str) -> float:
        """Converte stringa importo in float"""
        
        if not valore_str:
            return 0.0
        
        # Rimuovi spazi
        valore_str = valore_str.strip()
        
        # Gestisci negativi
        negativo = False
        if valore_str.startswith('-') or valore_str.startswith('(') or valore_str.endswith(')'):
            negativo = True
        
        # Rimuovi caratteri non numerici eccetto virgola e punto
        valore_str = re.sub(r'[^\d,.]', '', valore_str)
        
        # Determina formato numero (italiano o inglese)
        if ',' in valore_str and '.' in valore_str:
            # Entrambi presenti, determina quale è il separatore decimale
            if valore_str.rindex(',') > valore_str.rindex('.'):
                # Formato italiano: 1.000,50
                valore_str = valore_str.replace('.', '').replace(',', '.')
            else:
                # Formato inglese: 1,000.50
                valore_str = valore_str.replace(',', '')
        elif ',' in valore_str:
            # Solo virgola, potrebbe essere decimale
            parts = valore_str.split(',')
            if len(parts) == 2 and len(parts[1]) <= 2:
                # Probabilmente decimale italiano
                valore_str = valore_str.replace(',', '.')
            else:
                # Probabilmente separatore migliaia
                valore_str = valore_str.replace(',', '')
        
        try:
            valore = float(valore_str)
            return -valore if negativo else valore
        except:
            return 0.0
    
    def _conto_duplicato(self, conto: Dict, conti_list: List) -> bool:
        """Verifica se un conto è già presente"""
        
        for c in conti_list:
            if (c['codice'] == conto['codice'] and 
                c['descrizione'] == conto['descrizione'] and
                abs(c['valore'] - conto['valore']) < 0.01):
                return True
        return False
    
    def _valida_e_pulisci_risultati(self, risultati: Dict) -> Dict:
        """Valida e pulisce i risultati estratti"""
        
        # Rimuovi conti con descrizioni non valide
        conti_validi = []
        for conto in risultati['conti']:
            desc = conto['descrizione'].lower()
            
            # Salta righe che sono solo numeri o date
            if re.match(r'^[\d\s\-/\.]+$', desc):
                continue
            
            # Salta descrizioni troppo corte
            if len(desc) < 3:
                continue
            
            # Salta pattern comuni non validi
            skip_patterns = ['pagina', 'pag.', 'totale pagina', 'riporto', 'segue']
            if any(pattern in desc for pattern in skip_patterns):
                continue
            
            conti_validi.append(conto)
        
        risultati['conti'] = conti_validi
        
        # Calcola totali se non presenti
        if not risultati['totali'] and risultati['conti']:
            totale = sum(c['valore'] for c in risultati['conti'] if c['valore'] > 0)
            if totale > 0:
                risultati['totali']['calcolato'] = totale
        
        return risultati

# =============================================================================
# PARSER DATI DINAMICO
# =============================================================================

class ParserDatiDinamico:
    """Parser universale per diversi formati di input"""
    
    def __init__(self, mapping: Optional[Dict] = None):
        self.mapping = mapping or MappingConfigurator.carica_mapping_default()
        self.validator = CodiceContoValidator()
        self.pdf_parser = PDFParserRobusto()
        
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
        """Parse PDF da stream usando il parser robusto"""
        
        # Usa il parser PDF robusto
        risultati_pdf = self.pdf_parser.parse(file_stream)
        
        # Mostra statistiche estrazione
        if risultati_pdf['conti']:
            st.success(f"""
            ✅ **PDF elaborato con successo!**
            - Conti estratti: {len(risultati_pdf['conti'])}
            - Info azienda: {len(risultati_pdf['info'])} campi
            - Totali trovati: {len(risultati_pdf['totali'])}
            """)
            
            # Mostra anteprima
            with st.expander("📋 Anteprima dati estratti"):
                # Info aziendali
                if risultati_pdf['info']:
                    st.write("**Informazioni Aziendali:**")
                    for key, value in risultati_pdf['info'].items():
                        st.write(f"- {key.title()}: {value}")
                
                # Primi conti
                if risultati_pdf['conti']:
                    st.write("\n**Primi 10 conti estratti:**")
                    for i, conto in enumerate(risultati_pdf['conti'][:10], 1):
                        st.write(f"{i}. [{conto['codice']}] {conto['descrizione']}: €{conto['valore']:,.2f}")
                    
                    if len(risultati_pdf['conti']) > 10:
                        st.write(f"... e altri {len(risultati_pdf['conti'])-10} conti")
                
                # Totali
                if risultati_pdf['totali']:
                    st.write("\n**Totali rilevati:**")
                    for key, value in risultati_pdf['totali'].items():
                        st.write(f"- {key.replace('_', ' ').title()}: €{value:,.2f}")
        
        elif risultati_pdf['testo_estratto']:
            st.warning("""
            ⚠️ **Testo estratto ma nessun conto riconosciuto**
            
            Possibili cause:
            - Formato del PDF non standard
            - Tabelle come immagini (non testo)
            - Struttura dati non riconosciuta
            
            **Suggerimenti:**
            1. Verifica che il PDF contenga testo selezionabile
            2. Prova a convertire in Excel: [ilovepdf.com](https://www.ilovepdf.com/pdf_to_excel)
            3. Usa un file CSV o Excel direttamente
            """)
            
            with st.expander("Mostra testo estratto"):
                st.text(risultati_pdf['testo_estratto'][:2000])
                if len(risultati_pdf['testo_estratto']) > 2000:
                    st.write("... (testo troncato)")
        
        else:
            st.error("""
            ❌ **Impossibile estrarre dati dal PDF**
            
            Il file potrebbe essere:
            - Un PDF scannerizzato (immagine, non testo)
            - Protetto da password
            - Corrotto o danneggiato
            
            **Soluzioni:**
            1. Se è scannerizzato, usa un OCR: [ocr.space](https://ocr.space/)
            2. Converti in Excel: [zamzar.com](https://www.zamzar.com/convert/pdf-to-xlsx/)
            3. Ricrea il file in formato CSV o Excel
            """)
        
        # Organizza in struttura CEE
        return self._organizza_dati_cee(risultati_pdf)
    
    def _estrai_conto_da_riga_csv(self, row: Dict) -> Optional[Dict]:
        """Estrae conto da riga CSV"""
        codice = None
        descrizione = None
        valore = None
        
        for key, val in row.items():
            if not key:
                continue
            key_lower = key.lower()
            
            if any(x in key_lower for x in ['codice', 'conto', 'cod']):
                codice = val
            elif any(x in key_lower for x in ['descr', 'intestaz', 'voce']):
                descrizione = val
            elif any(x in key_lower for x in ['saldo', 'importo', 'valore', 'dare', 'avere']):
                valore = val
        
        if codice and valore:
            try:
                # Converti valore
                valore = str(valore).replace('.', '').replace(',', '.')
                valore_float = float(valore)
                
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
        
        # Classifica ogni conto
        for conto in dati_raw.get('conti', []):
            self._classifica_conto(conto, struttura_cee)
        
        # Aggiungi totali pre-calcolati se presenti
        if 'totali' in dati_raw and dati_raw['totali']:
            struttura_cee['totali_originali'] = dati_raw['totali']
        
        # Calcola totali dalla struttura
        self._calcola_totali(struttura_cee)
        
        return struttura_cee
    
    def _classifica_conto(self, conto: Dict, struttura: Dict):
        """Classifica un conto nella struttura CEE appropriata"""
        
        codice = conto.get('codice', '')
        descrizione = conto.get('descrizione', '').lower()
        
        classificato = False
        
        # Prova classificazione per attivo
        for categoria, config in self.mapping['attivo'].items():
            if self._match_pattern_ricorsivo(codice, descrizione, config):
                self._inserisci_conto_ricorsivo(conto, struttura['attivo'], categoria, config)
                classificato = True
                break
        
        # Se non classificato, prova passivo
        if not classificato:
            for categoria, config in self.mapping['passivo'].items():
                if self._match_pattern_ricorsivo(codice, descrizione, config):
                    self._inserisci_conto_ricorsivo(conto, struttura['passivo'], categoria, config)
                    classificato = True
                    break
        
        # Se ancora non classificato, usa euristica basata su keywords
        if not classificato:
            classificato = self._classifica_per_keywords(conto, struttura)
    
    def _classifica_per_keywords(self, conto: Dict, struttura: Dict) -> bool:
        """Classifica usando keywords nel nome"""
        
        descrizione = conto.get('descrizione', '').lower()
        
        # Keywords per classificazione
        keywords_map = {
            'attivo': {
                'immobilizzazioni': ['immobilizz', 'software', 'brevett', 'impianto', 'macchin', 'fabbricat', 'terren'],
                'circolante': ['client', 'credit', 'cassa', 'banca', 'rimanenz', 'magazz'],
                'ratei_risconti': ['ratei attiv', 'riscont attiv']
            },
            'passivo': {
                'patrimonio_netto': ['capitale', 'riserv', 'utili', 'perdite'],
                'debiti': ['fornitor', 'debit', 'mutui', 'prestit', 'finanziament'],
                'fondi': ['tfr', 'fondo', 'accantonament'],
                'ratei_risconti': ['ratei passiv', 'riscont passiv']
            }
        }
        
        for sezione, categorie in keywords_map.items():
            for categoria, keywords in categorie.items():
                for keyword in keywords:
                    if keyword in descrizione:
                        if sezione == 'attivo':
                            if categoria == 'immobilizzazioni':
                                struttura['attivo']['immobilizzazioni']['immateriali'].append(conto)
                            elif categoria == 'circolante':
                                struttura['attivo']['circolante']['disponibilita'].append(conto)
                            else:
                                struttura['attivo'][categoria].append(conto)
                        else:
                            struttura['passivo'][categoria].append(conto)
                        return True
        
        return False
    
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
            # Trova sotto-categoria appropriata
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
        
        # Calcola totale attivo
        totale_attivo = self._somma_ricorsiva(struttura['attivo'])
        struttura['totali']['attivo'] = totale_attivo
        
        # Calcola totale passivo
        totale_passivo = self._somma_ricorsiva(struttura['passivo'])
        struttura['totali']['passivo'] = totale_passivo
        
        # Calcola quadratura
        struttura['totali']['quadratura'] = totale_attivo - totale_passivo
        
        # Aggiungi totali originali se presenti
        if 'totali_originali' in struttura:
            struttura['totali']['originali'] = struttura['totali_originali']
    
    def _somma_ricorsiva(self, obj: Any) -> float:
        """Somma ricorsiva di tutti i valori"""
        
        if isinstance(obj, dict):
            if 'valore' in obj:
                return float(obj['valore'])
            
            totale = 0
            for key, value in obj.items():
                if key not in ['info', 'totali', 'totali_originali']:
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
    parser = ParserDatiDinamico()
    
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
                if key not in ['info', 'totali', 'totali_originali']:
                    nome_sub = f"{nome_sezione} - {key.replace('_', ' ').title()}"
                    processa_sezione(value, nome_sub, prefisso + "  ")
    
    processa_sezione(dati.get('attivo', {}), 'ATTIVO')
    processa_sezione(dati.get('passivo', {}), 'PASSIVO')
    
    if df_data:
        df = pd.DataFrame(df_data)
        
        # Formatta colonna importo
        df['Importo Formattato'] = df['Importo'].apply(lambda x: formatta_numero(x))
        
        # Visualizza dataframe
        st.dataframe(
            df[['Sezione', 'Codice', 'Descrizione', 'Importo Formattato']],
            use_container_width=True,
            height=600
        )
        
        return df
    
    return None

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
        .info {{ background: #f0f0f0; padding: 15px; margin: 20px 0; }}
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
    
    <div class="info">
        <p><strong>Esercizio:</strong> {info.get('esercizio', 'N/A')}</p>
        <p><strong>Data Chiusura:</strong> {info.get('data_chiusura', 'N/A')}</p>
        <p><strong>P.IVA:</strong> {info.get('partita_iva', 'N/A')}</p>
        <p><strong>Codice Fiscale:</strong> {info.get('codice_fiscale', 'N/A')}</p>
    </div>
    
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
    
    # Funzione helper per aggiungere righe
    def aggiungi_righe(sezione, nome_sezione, html_rows=""):
        if isinstance(sezione, list):
            for conto in sezione:
                if isinstance(conto, dict):
                    valore = conto.get('valore', 0)
                    classe = 'negativo' if valore < 0 else ''
                    html_rows += f"""
            <tr>
                <td>{nome_sezione}</td>
                <td>{conto.get('codice', '')}</td>
                <td>{conto.get('descrizione', '')}</td>
                <td class="numero {classe}">{formatta_numero(valore)}</td>
            </tr>
"""
        elif isinstance(sezione, dict):
            for key, value in sezione.items():
                if key not in ['info', 'totali', 'totali_originali']:
                    nome_sub = f"{nome_sezione} - {key.replace('_', ' ').title()}"
                    html_rows = aggiungi_righe(value, nome_sub, html_rows)
        
        return html_rows
    
    # Aggiungi righe attivo e passivo
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
    st.markdown("**Sistema Dinamico per la Riclassificazione dei Bilanci con Parser PDF Robusto**")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configurazione")
        
        st.markdown("### 📁 Formati Supportati")
        st.success("✅ CSV - Completamente supportato")
        st.success("✅ Excel - Completamente supportato")
        st.success("✅ JSON - Completamente supportato")
        
        if PYPDF2_AVAILABLE or PDFMINER_AVAILABLE:
            st.success("✅ PDF - Parser Robusto Attivo")
        else:
            st.error("❌ PDF - Librerie mancanti")
        
        st.markdown("### 📋 Istruzioni")
        st.markdown("""
        1. **Carica il file** del bilancio
        2. **Visualizza** l'anteprima dei dati
        3. **Scarica** il report in HTML
        
        **PDF supportati:**
        - PDF con testo selezionabile
        - Bilanci in formato standard
        - Tabelle testuali
        """)
        
        # Stato dipendenze
        st.markdown("### 🔧 Stato Sistema")
        col1, col2 = st.columns(2)
        
        with col1:
            if PANDAS_AVAILABLE:
                st.success("pandas ✅")
            else:
                st.error("pandas ❌")
            
            if PYPDF2_AVAILABLE:
                st.success("PyPDF2 ✅")
            else:
                st.warning("PyPDF2 ❌")
        
        with col2:
            if EXCEL_AVAILABLE:
                st.success("Excel ✅")
            else:
                st.error("Excel ❌")
            
            if PDFMINER_AVAILABLE:
                st.success("pdfminer ✅")
            else:
                st.warning("pdfminer ❌")
    
    # Tab principale
    tab1, tab2, tab3 = st.tabs(["📤 Carica File", "📊 Visualizza Dati", "ℹ️ Info"])
    
    with tab1:
        st.header("Carica File Bilancio")
        
        # Upload file
        uploaded_file = st.file_uploader(
            "Seleziona il file del bilancio",
            type=['csv', 'xlsx', 'xls', 'json', 'pdf'],
            help="Carica un file contenente i dati del bilancio. I PDF devono contenere testo selezionabile."
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
                        
                        # Mostra riepilogo solo se ci sono dati
                        if dati.get('info') or dati.get('attivo') or dati.get('passivo'):
                            
                            # Info bilancio
                            info = dati.get('info', {})
                            if info:
                                st.markdown('<div class="info-box">', unsafe_allow_html=True)
                                st.subheader("📋 Informazioni Bilancio")
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    for campo in ['societa', 'esercizio', 'data_chiusura']:
                                        if campo in info:
                                            st.write(f"**{campo.replace('_', ' ').title()}:** {info[campo]}")
                                
                                with col2:
                                    for campo in ['partita_iva', 'codice_fiscale']:
                                        if campo in info:
                                            st.write(f"**{campo.replace('_', ' ').upper()}:** {info[campo]}")
                                
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
                                        delta=None if abs(quadratura) < 0.01 else f"Δ {formatta_numero(abs(quadratura))}",
                                        delta_color="off" if abs(quadratura) < 0.01 else "inverse"
                                    )
                                
                                # Mostra totali originali se presenti
                                if 'originali' in dati['totali']:
                                    with st.expander("Totali rilevati nel documento"):
                                        for key, value in dati['totali']['originali'].items():
                                            st.write(f"**{key.replace('_', ' ').title()}:** €{formatta_numero(value)}")
                        
                    except Exception as e:
                        st.error(f"❌ Errore durante l'elaborazione: {str(e)}")
                        st.exception(e)
    
    with tab2:
        st.header("Visualizzazione Dati Bilancio")
        
        if 'dati_bilancio' in st.session_state:
            dati = st.session_state['dati_bilancio']
            
            # Opzioni visualizzazione
            col1, col2 = st.columns([3, 1])
            with col2:
                vista = st.selectbox(
                    "Tipo Vista",
                    ["Tabella Completa", "Riepilogo", "Dati Grezzi"]
                )
            
            if vista == "Tabella Completa":
                df = mostra_tabella_bilancio(dati)
                
                # Export to Excel button
                if df is not None and not df.empty:
                    excel_buffer = io.BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                        df.to_excel(writer, sheet_name='Bilancio CEE', index=False)
                    excel_buffer.seek(0)
                    
                    st.download_button(
                        label="📥 Scarica Excel",
                        data=excel_buffer,
                        file_name="bilancio_cee.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            
            elif vista == "Riepilogo":
                # Mostra metriche principali
                st.subheader("📊 Riepilogo Bilancio")
                
                parser = ParserDatiDinamico()
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("### Attivo")
                    for key in dati.get('attivo', {}).keys():
                        if key not in ['info', 'totali', 'totali_originali']:
                            totale = parser._somma_ricorsiva(dati['attivo'][key])
                            if totale != 0:
                                st.write(f"**{key.replace('_', ' ').title()}:** € {formatta_numero(totale)}")
                
                with col2:
                    st.markdown("### Passivo")
                    for key in dati.get('passivo', {}).keys():
                        if key not in ['info', 'totali', 'totali_originali']:
                            totale = parser._somma_ricorsiva(dati['passivo'][key])
                            if totale != 0:
                                st.write(f"**{key.replace('_', ' ').title()}:** € {formatta_numero(totale)}")
            
            elif vista == "Dati Grezzi":
                st.json(dati)
            
            # Download section
            st.markdown("---")
            st.subheader("📥 Scarica Report")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Download HTML
                html_content = genera_html_download(dati)
                b64 = base64.b64encode(html_content.encode()).decode()
                href = f'<a href="data:text/html;base64,{b64}" download="bilancio_cee.html">📄 Scarica HTML</a>'
                st.markdown(href, unsafe_allow_html=True)
            
            with col2:
                # Download JSON
                json_str = json.dumps(dati, indent=2, ensure_ascii=False)
                st.download_button(
                    label="📊 Scarica JSON",
                    data=json_str,
                    file_name="bilancio_cee.json",
                    mime="application/json"
                )
            
            with col3:
                # Download CSV
                if 'dati_bilancio' in st.session_state:
                    df = mostra_tabella_bilancio(st.session_state['dati_bilancio'])
                    if df is not None and not df.empty:
                        csv = df.to_csv(index=False, sep=';')
                        st.download_button(
                            label="📑 Scarica CSV",
                            data=csv,
                            file_name="bilancio_cee.csv",
                            mime="text/csv"
                        )
        
        else:
            st.warning("⚠️ Nessun dato caricato. Carica prima un file nella tab 'Carica File'.")
    
    with tab3:
        st.header("ℹ️ Informazioni")
        
        st.info("""
        ### 📊 Riclassificatore Bilancio CEE v5.0
        
        **Caratteristiche principali:**
        - Parser PDF robusto con doppia libreria (PyPDF2 + pdfminer)
        - Estrazione automatica conti e informazioni aziendali
        - Classificazione intelligente secondo schema CEE
        - Export multipli formati (HTML, Excel, JSON, CSV)
        
        ### 🔧 Parser PDF Avanzato:
        - ✅ Estrae testo da qualsiasi PDF testuale
        - ✅ Riconosce automaticamente tabelle e conti
        - ✅ Estrae informazioni aziendali (P.IVA, ragione sociale, etc.)
        - ✅ Gestisce formati multipli di numeri (italiano/inglese)
        - ✅ Fallback automatico tra librerie
        
        ### 📁 Formati File Supportati:
        - **PDF**: Testuali (non scannerizzati)
        - **Excel**: XLSX, XLS con supporto multi-foglio
        - **CSV**: Separatore punto e virgola
        - **JSON**: Strutture pre-formattate
        
        ### 💡 Suggerimenti per PDF:
        1. Verifica che il testo sia selezionabile
        2. Per PDF scannerizzati usa prima un OCR
        3. In caso di problemi, converti in Excel
        
        ### 🆘 Risoluzione Problemi:
        - **PDF non riconosciuto**: Probabilmente è scannerizzato
        - **Conti non trovati**: Formato non standard, converti in Excel
        - **Errore parsing**: File corrotto o protetto
        
        ---
        **Sviluppato con** ❤️ **per semplificare la riclassificazione dei bilanci**
        """)
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666;'>
            <p>Riclassificatore Bilancio CEE v5.0 - Parser PDF Robusto</p>
            <p>© 2024 - Sistema Dinamico con estrazione intelligente</p>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
