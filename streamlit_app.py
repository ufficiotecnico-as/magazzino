import streamlit as st
import pandas as pd
from datetime import datetime
import io
import base64
from PIL import Image
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- IMPORTAZIONE SICURA E INGEGNERIZZATA DEL NUOVO MODULO ---
try:
    from gestione_preventivi import mostra_interfaccia_preventivi
    MODULO_PREVENTIVI_DISPONIBILE = True
except Exception:
    MODULO_PREVENTIVI_DISPONIBILE = False

# --- CONFIGURAZIONE INTERMEDIARIO (GOOGLE APPS SCRIPT) ---
URL_INTERMEDIARIO_SILENZIOSO = "https://script.google.com/macros/s/AKfycbyXBLjDpJrSGHoUpuspTsNAG9f6lGhF1e8oGyJ8nkY6jZMTJo04zsT_6eLyEybGgv4/exec"

# --- CONFIGURAZIONE DRIVE COMODATI (CONSEGNA / RICONSEGNA) ---
ID_CARTELLA_CONSEGNE = "1pJpYtIfcMEKFh62rSOGTXWYG8CgvzN4m"
ID_CARTELLA_RICONSEGNE = "1S6IcauDOc-8sFiCdGv67CHKf_H9u7BVW"

# --- CONTROLLO LIBRERIE ESTERNE ---
try:
    import gspread
    from google.oauth2 import service_account
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

try:
    import googleapiclient.discovery
    from googleapiclient.http import MediaIoBaseUpload
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False

try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False

# --- CONFIGURAZIONE INIZIALE DI PAGINA ---
st.set_page_config(page_title="Gestione Magazzini Scarpa", page_icon="🏢", layout="wide")

# --- COSTANTI E CONFIGURAZIONI TIPO ---
PASSWORD_MAP = {
    "ata2026": "Personale ATA",
    "officina2026": "Officina",
    "tecnici2026": "Tecnici Informatici"
}
PASSWORD_ADMIN = "admin99"

MAPPA_SCHEDE = {
    "Personale ATA": {"inventario": "Inventario ata", "richieste": "Richieste ata"},
    "Officina": {"inventario": "Inventario officina", "richieste": "Richieste officina"},
    "Tecnici Informatici": {"inventario": "Inventario informatica", "richieste": "Richieste informatica"}
}

URL_LOGO = "https://cspace.spaggiari.eu//pub/TVII0004/TVII0004-intestazione-nuova-senzaloghi.png?_t=1712923868"
SPREADSHEET_ID = "1Q91H_TULvpsnPcyOwQ1lxmjOf809xp4cUz9p1EdMc-4"

# --- STILE PREMIUM ISTITUZIONALE ---
st.markdown("""
    <style>
        .stApp { background-color: #f8fafc; }
        div.stButton > button:first-child {
            background-color: #8b1e1e !important;
            color: white !important;
            border-radius: 10px !important;
            border: none !important;
            font-weight: 600 !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- CONNESSIONE GOOGLE SHEETS ---
@st.cache_resource(ttl=2)
def connetti_google_sheets():
    if not GSPREAD_AVAILABLE: return None
    creds_info = None
    if "google_creds" in st.secrets: creds_info = dict(st.secrets["google_creds"])
    elif "gcp_service_account" in st.secrets: creds_info = dict(st.secrets["gcp_service_account"])
    if not creds_info: return None
    try:
        if "private_key" in creds_info: creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n").strip()
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = service_account.Credentials.from_service_account_info(creds_info, scopes=scopes)
        return gspread.authorize(creds).open_by_key(SPREADSHEET_ID)
    except Exception: return None

def scarica_da_sheet(nome_scheda):
    sh = connetti_google_sheets()
    if sh is None: return pd.DataFrame()
    try:
        worksheet = sh.worksheet(nome_scheda)
        return pd.DataFrame(worksheet.get_all_records())
    except gspread.exceptions.WorksheetNotFound:
        df_base = pd.DataFrame(columns=["id_richiesta_mag", "data_creazione", "magazzino_origine", "materiale_richiesto", "quantita_esimata", "stato_iter", "note"])
        carica_su_sheet(df_base, nome_scheda)
        return df_base
    except Exception: return pd.DataFrame()

def carica_su_sheet(df, nome_scheda):
    sh = connetti_google_sheets()
    if sh is None: return
    try:
        try: worksheet = sh.worksheet(nome_scheda)
        except gspread.exceptions.WorksheetNotFound: worksheet = sh.add_worksheet(title=nome_scheda, rows="1000", cols="20")
        worksheet.clear()
        df_pulito = df.fillna("")
        for col in df_pulito.columns: df_pulito[col] = df_pulito[col].astype(str)
        valori = [df_pulito.columns.values.tolist()] + df_pulito.values.tolist()
        worksheet.update(valori)
    except Exception: pass

# --- PORTALE DI LOGIN ---
if "ruolo_utente" not in st.session_state: st.session_state.ruolo_utente = None
if "utente_corrente" not in st.session_state: st.session_state.utente_corrente = ""
if "magazzino_selezionato" not in st.session_state: st.session_state.magazzino_selezionato = None

if st.session_state.ruolo_utente is None:
    st.markdown("<h2 style='text-align: center;'>Piattaforma Logistica di Istituto</h2>", unsafe_allow_html=True)
    pwd = st.text_input("Codice autorizzazione:", type="password")
    if st.button("Entra"):
        if pwd in PASSWORD_MAP:
            st.session_state.ruolo_utente = "magazziniere"
            st.session_state.magazzino_selezionato = PASSWORD_MAP[pwd]
            st.session_state.utente_corrente = PASSWORD_MAP[pwd]
            st.rerun()
        elif pwd == PASSWORD_ADMIN:
            st.session_state.ruolo_utente = "admin"
            st.session_state.utente_corrente = "Ufficio Tecnico (Admin)"
            st.rerun()
else:
    if st.button("🚪 Esci"):
        st.session_state.ruolo_utente = None
        st.rerun()

    df_istanze = scarica_da_sheet("Richieste_Preside")

    # ==========================================
    # WORKFLOW ADMIN (UFFICIO TECNICO)
    # ==========================================
    if st.session_state.ruolo_utente == "admin":
        st.sidebar.markdown("### 👑 Pannello Ufficio Tecnico")
        sezione = st.sidebar.radio("Seleziona area:", ["📦 Magazzini", "📊 Gestione Preventivi e Fornitori"])
        
        if sezione == "📦 Magazzini":
            st.write("Visualizzazione scorte e richieste standard.")
        elif sezione == "📊 Gestione Preventivi e Fornitori":
            if MODULO_PREVENTIVI_DISPONIBILE:
                mostra_interfaccia_preventivi(scarica_da_sheet, carica_su_sheet, None, None, df_istanze)
            else:
                st.error("Modulo preventivi non agganciato.")

    # ==========================================
    # WORKFLOW MAGAZZINIERE (CHI FA LA RICHIESTA)
    # ==========================================
    elif st.session_state.ruolo_utente == "magazziniere":
        st.markdown(f"## 📦 Pannello Operativo: {st.session_state.magazzino_selezionato}")
        
        tab_scorte, tab_fabbisogno = st.tabs(["📋 Inventario Scorte", "➕ Richiedi Materiale (Fabbisogno)"])
        
        with tab_scorte:
            st.markdown("### Materiale attualmente in magazzino")
            st.dataframe(scarica_da_sheet(MAPPA_SCHEDE[st.session_state.magazzino_selezionato]["inventario"]), use_container_width=True, hide_index=True)
            
        with tab_fabbisogno:
            st.markdown("### 📝 Segnala materiale mancante o da acquistare")
            st.markdown("La richiesta inserita qui sotto verrà inviata direttamente all'Ufficio Tecnico per la richiesta dei preventivi.")
            
            with st.form("form_richiesta_acquisto"):
                mat = st.text_input("Materiale / Bene da acquistare (es. 20 Risme Carta A4):")
                qta = st.text_input("Quantità o specifiche stimate:")
                note = st.text_area("Note e urgenza:")
                
                if st.form_submit_button("Invia Richiesta a Ufficio Tecnico"):
                    if mat.strip():
                        df_richieste_mag = scarica_da_sheet("Richieste_Preventivo_Magazzino")
                        id_rm = 2001 if df_richieste_mag.empty else int(pd.to_numeric(df_richieste_mag["id_richiesta_mag"], errors='coerce').max()) + 1
                        
                        nuova_r = pd.DataFrame([{
                            "id_richiesta_mag": id_rm, "data_creazione": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "magazzino_origine": st.session_state.magazzino_selezionato, "materiale_richiesto": mat.strip(),
                            "quantita_esimata": qta.strip(), "stato_iter": "In attesa di preventivi", "note": note.strip()
                        }])
                        
                        carica_su_sheet(pd.concat([df_richieste_mag, nuova_r], ignore_index=True), "Richieste_Preventivo_Magazzino")
                        st.success(f"✅ Richiesta inoltrata con successo all'Ufficio Tecnico! (ID REQ: {id_rm})")
                    else:
                        st.error("La descrizione del materiale è obbligatoria.")
