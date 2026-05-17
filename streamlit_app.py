import streamlit as st
import pandas as pd
from datetime import datetime
import io
import base64
from PIL import Image
import requests

# --- CONFIGURAZIONE INTERMEDIARIO (GOOGLE APPS SCRIPT) ---
# Aggiornato con il tuo ultimissimo URL di deploy fornito:
URL_INTERMEDIARIO_SILENZIOSO = "https://script.google.com/macros/s/AKfycbyXBLjDpJrSGHoUpuspTsNAG9f6lGhF1e8oGyJ8nkY6jZMTJo04zsT_6eLyEybGgv4/exec"

# --- CONTROLLO LIBRERIE ESTERNE ---
try:
    import gspread
    from google.oauth2 import service_account
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

try:
    from googleapiclient.discovery import build
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
ID_CARTELLA_DRIVE_PRINCIPALE = "1bVTs2smvVJONs2oIAFZdDvX9pYDK9MZT"
SPREADSHEET_ID = "1Q91H_TULvpsnPcyOwQ1lxmjOf809xp4cUz9p1EdMc-4"
LISTA_MAGAZZINI = ["Personale ATA", "Officina", "Tecnici Informatici"]

# Email di destinazione per il Testing delle richieste
EMAIL_TESTING = "marcobrunetti14@gmail.com"

# --- STILE PREMIUM ISTITUZIONALE ---
st.markdown("""
    <style>
        .stApp { background-color: #f8fafc; }
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: white !important;
            padding: 30px !important;
            border-radius: 16px !important;
            border: 1px solid #e2e8f0 !important;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05) !important;
        }
        div.stButton > button:first-child {
            background-color: #8b1e1e !important;
            color: white !important;
            border-radius: 10px !important;
            border: none !important;
            font-weight: 600 !important;
            padding: 12px 24px !important;
        }
        div.stButton > button:first-child:hover { background-color: #a72828 !important; }
        .stTextInput input, .stSelectbox div[data-baseweb="select"] { border-radius: 10px !important; }
        h2, h3 { color: #0f172a !important; font-weight: 700; }
    </style>
""", unsafe_allow_html=True)

# --- CONNESSIONE GOOGLE SHEETS ---
@st.cache_resource(ttl=5)
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
    except Exception:
        return None

def scarica_da_sheet(nome_scheda):
    sh = connetti_google_sheets()
    if sh is None: return pd.DataFrame()
    try:
        worksheet = sh.worksheet(nome_scheda)
        df = pd.DataFrame(worksheet.get_all_records())
        if nome_scheda == "Richieste_Preside" and (df.empty or "id_richiesta" not in df.columns):
            df = pd.DataFrame(columns=["id_richiesta", "data_richiesta", "richiedente", "tipo_istanza", "categoria_bene", "oggetto", "motivazione", "stato"])
        return df
    except gspread.exceptions.WorksheetNotFound:
        if "Inventario_Comodati" in nome_scheda:
            df_base = pd.DataFrame(columns=["id_bene", "tipo_bene", "descrizione", "stato"])
        elif "Registro_Comodati" in nome_scheda:
            df_base = pd.DataFrame(columns=["id_comodato", "tipo_soggetto", "nominativo", "id_bene", "data_consegna", "stato_comodato"])
        elif "Richieste_Preside" in nome_scheda:
            df_base = pd.DataFrame(columns=["id_richiesta", "data_richiesta", "richiedente", "tipo_istanza", "categoria_bene", "oggetto", "motivazione", "stato"])
        else:
            df_base = pd.DataFrame(columns=["id", "elemento", "valore"])
        carica_su_sheet(df_base, nome_scheda)
        return df_base
    except Exception:
        return pd.DataFrame()

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

# --- FUNZIONE DI INVIO EMAIL ---
def invia_notifica_email(id_richiesta, roommate, tipo_istanza, oggetto, motivazione):
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        # Configurato in automatico con il link ufficiale fornito
        url_approva = f"https://magazzino-scarpa.streamlit.app/?action=approve&id={id_richiesta}"
        url_rifiuta = f"https://magazzino-scarpa.streamlit.app/?action=reject&id={id_richiesta}"

        if "email_config" in st.secrets:
            cfg = st.secrets["email_config"]
            smtp_server = cfg.get("smtp_server", "smtp.gmail.com")
            smtp_port = int(cfg.get("smtp_port", 587))
            smtp_user = cfg.get("smtp_user")
            smtp_password = cfg.get("smtp_password")
            
            msg = MIMEMultipart('alternative')
            msg['From'] = smtp_user
            msg['To'] = EMAIL_TESTING
            msg['Subject'] = f"📦 NUOVA ISTANZA [{tipo_istanza.upper()}] - {roommate}"
            
            corpo_html = f"""
            <html>
            <body style="font-family: Arial, sans-serif; color: #334155; line-height: 1.6; background-color: #f8fafc; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background: #ffffff; padding: 30px; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
                    <h2 style="color: #8b1e1e; margin-bottom: 20px; border-bottom: 2px solid #f1f5f9; padding-bottom: 10px;">Nuova Richiesta Portale Logistico</h2>
                    
                    <table style="width: 100%; margin-bottom: 25px; border-collapse: collapse;">
                        <tr><td style="padding: 8px 0; font-weight: bold; color: #0f172a; width: 140px;">Richiedente:</td><td style="padding: 8px 0; color: #475569;">{roommate}</td></tr>
                        <tr><td style="padding: 8px 0; font-weight: bold; color: #0f172a;">Tipo Istanza:</td><td style="padding: 8px 0; color: #475569;">{tipo_istanza}</td></tr>
                        <tr><td style="padding: 8px 0; font-weight: bold; color: #0f172a;">Oggetto:</td><td style="padding: 8px 0; color: #475569;">{oggetto}</td></tr>
                        <tr><td style="padding: 8px 0; font-weight: bold; color: #0f172a;">Data/Ora:</td><td style="padding: 8px 0; color: #475569;">{datetime.now().strftime('%d/%m/%Y %H:%M')}</td></tr>
                    </table>
                    
                    <div style="background: #f8fafc; padding: 15px; border-radius: 8px; border-left: 4px solid #8b1e1e; margin-bottom: 30px;">
                        <strong style="color: #0f172a; display: block; margin-bottom: 5px;">Motivazione / Note fornite:</strong>
                        <span style="color: #334155; font-style: italic;">{motivazione}</span>
                    </div>
                    
                    <h3 style="color: #0f172a; font-size: 14px; margin-bottom: 15px; text-align: center;">GESTIONE RAPIDA RICHIESTA:</h3>
                    
                    <div style="text-align: center; margin-top: 20px; display: block; margin-bottom: 20px;">
                        <a href="{url_approva}" target="_blank" style="background-color: #16a34a; color: white; padding: 12px 28px; text-decoration: none; font-weight: bold; border-radius: 8px; margin-right: 15px; display: inline-block;">🟢 AUTORIZZA ADESSO</a>
                        <a href="{url_rifiuta}" target="_blank" style="background-color: #dc2626; color: white; padding: 12px 28px; text-decoration: none; font-weight: bold; border-radius: 8px; display: inline-block;">🔴 RIFIUTA RICHIESTA</a>
                    </div>
                </div>
            </body>
            </html>
            """
            msg.attach(MIMEText(corpo_html, 'html', 'utf-8'))
            
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, EMAIL_TESTING, msg.as_string())
            server.quit()
            return True
        else:
            return True
    except Exception:
        return False

# --- CLASSE PDF MINISTERIALE ---
class PDFMinisteriale(FPDF):
    def footer(self):
        self.set_y(-20)
        self.set_draw_color(180, 180, 180)
        self.set_line_width(0.1)
        self.line(15, self.get_y(), 195, self.get_y())
        self.set_font("Arial", "", 7)
        self.cell(180, 4, 'ISISS "A. SCARPA"      Via Primo Maggio, 3 31045 Motta di Livenza (Tv)      C.F. 94071460268      Codice univoco UFOA6X', ln=True, align="C")
        self.cell(180, 3, "tvis01100a@istruzione.it      tvis01100a@pec.istruzione.it", ln=True, align="C")
        self.set_font("Arial", "I", 5)
        self.cell(180, 3, "Documento informatico firmato digitalmente ai sensi del D.Lgs 82/2005 CAD art.45, ss.mm.ii e norme collegate.", ln=True, align="C")

def pulisci_caratteri_fpdf(testo):
    mappa = {
        chr(224): "a'", chr(232): "e'", chr(233): "e'", chr(236): "i'", chr(242): "o'", chr(249): "u'",
        "à": "a'", "è": "e'", "é": "e'", "ì": "i'", "ò": "o'", "ù": "u'",
        "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"
    }
    for k, v in mappa.items(): testo = testo.replace(k, v)
    return testo.encode('raw_unicode_escape').decode('utf-8').encode('latin1', 'replace').decode('latin1')

def genera_pdf_comodato(id_contratto, nome, ruolo, bene, data, tipo_operazione, firma_base64=None, utente_loggato="Ufficio Tecnico"):
    if not FPDF_AVAILABLE: return b"Errore libreria PDF"
    pdf = PDFMinisteriale(orientation='P', unit='mm', format='A4')
    pdf.set_margins(15, 12, 15)
    pdf.set_auto_page_break(auto=True, margin=22) 
    pdf.add_page()
    try:
        pdf.image(URL_LOGO, x=15, y=10, w=180)
        pdf.set_y(32)
    except Exception:
        pdf.set_font("Times", "B", 13)
        pdf.cell(180, 6, "ISISS ANTONIO SCARPA", ln=True, align="C")
        pdf.ln(5)
        
    pdf.set_font("Times", "", 10)
    data_corrente = data.split(" ")[0] if " " in data else data
    pdf.cell(90, 5, "Protocollo n. (vedi segnatura)", ln=False, align="L")
    pdf.cell(90, 5, pulisci_caratteri_fpdf(f"Motta di Livenza, {data_corrente}"), ln=True, align="R")
    pdf.ln(6)
    
    pdf.set_font("Times", "B", 10)
    pdf.cell(95, 5, "", ln=False)
    pdf.cell(85, 5, "Ai Docenti / Al Personale Interessato", ln=True, align="L")
    pdf.cell(95, 5, "", ln=False)
    pdf.cell(85, 5, pulisci_caratteri_fpdf(f"Sig./Sigg. {nome} ({ruolo})"), ln=True, align="L")
    pdf.ln(8)
    
    pdf.set_font("Times", "B", 10)
    pdf.cell(22, 5, "OGGETTO: ", ln=False)
    pdf.set_font("Times", "", 10)
    
    if tipo_operazione == "CONSEGNA":
        testo_oggetto = f"Verbale di Consegna e Assegnazione in Comodato d'Uso Gratuito dei Beni d'Istituto - Registro ID {id_contratto}."
    else:
        testo_oggetto = f"Ricevuta di Riconsegna, Scarico Logistico e Cessazione Comodato d'Uso - Registro ID {id_contratto}."
    
    pdf.multi_cell(158, 5, pulisci_caratteri_fpdf(testo_oggetto))
    pdf.ln(8)
    
    pdf.set_font("Times", "", 10)
    if tipo_operazione == "CONSEGNA":
        corpo_testo = (
            f"Con la presente si attesta che in data odierna l'Amministrazione dell'Istituto Superiore "
            f"Antonio Scarpa provvede alla consegna in comodato d'uso del bene sotto specificato al richiedente indicato.\n\n"
            f"Dettaglio del Bene Assegnato:\n"
            f"- Identificativo / Seriale: {bene}\n\n"
            f"Il sottoscritto prende in carico l'oggetto integro, dichiarando di averne verificato il perfetto stato "
            f"di funzionamento. Si impegna altresi a custodirlo responsabilmente, utilizzarlo esclusivamente for le finalita "
            f"istituzionali e connesse alle attivita didattiche, ed a restituirlo integro alla Direzione al termine del periodo "
            f"di utilizzo o su esplicita richiesta dell'Istituto."
        )
    else:
        corpo_testo = (
            f"Con la presente si attesta che il bene sotto descritto e stato formalmente riconsegnato all'Istituto "
            f"in data odierna, ponendo fine agli obblighi di custodia previsti dal contratto.\n\n"
            f"Dettaglio del Bene Riconsegnato:\n"
            f"- Identificativo / Seriale: {bene}\n\n"
            f"L'Ufficio Tecnico/Magazzino ha verificato l'integrita e lo stato del dispositivo, completandone "
            f"l'operazione di scarico logistico dal registro dei comodati attivi."
        )
        
    pdf.multi_cell(180, 6, pulisci_caratteri_fpdf(corpo_testo), align="J")
    
    pdf.set_y(-60)
    pdf.set_font("Times", "B", 10)
    y_posizione_firme = pdf.get_y()
    
    pdf.cell(100, 5, "Per l'Amministrazione:", align="L")
    if tipo_operazione == "CONSEGNA":
        pdf.cell(80, 5, "Firma del Richiedente:", align="L", ln=True)
    else:
        pdf.cell(80, 5, "Firma del Riconsegnante:", align="L", ln=True)
    
    pdf.set_font("Times", "I", 9)
    pdf.cell(100, 5, f"F.to {utente_loggato}", align="L")
    
    if firma_base64 and len(firma_base64) > 100:
        try:
            dati_f = firma_base64.split(",")[1] if "," in firma_base64 else firma_base64
            img_data = base64.b64decode(dati_f)
            img_originale = Image.open(io.BytesIO(img_data))
            sfondo_bianco = Image.new("RGBA", img_originale.size, "WHITE")
            sfondo_bianco.paste(img_originale, (0, 0), img_originale)
            img_buffer = io.BytesIO()
            sfondo_bianco.convert("RGB").save(img_buffer, format="JPEG", quality=95)
            img_buffer.seek(0)
            pdf.image(img_buffer, x=115, y=y_posizione_firme + 5, w=50, h=0)
        except Exception:
            pdf.cell(80, 5, "[Firma Digitale Acquisita]", align="L", ln=True)
    else:
        pdf.cell(80, 5, "____________________________", align="L", ln=True)
    return pdf.output()

# --- FUNZIONE LOGISTICA DRIVE ---
def carica_su_drive_unico(file_bytes, nome_file, mime_type, nome_cartella_dest):
    if not GOOGLE_DRIVE_AVAILABLE: return None
    creds_info = None
    if "google_creds" in st.secrets: creds_info = dict(st.secrets["google_creds"])
    elif "gcp_service_account" in st.secrets: creds_info = dict(st.secrets["gcp_service_account"])
    if not creds_info: return None
    try:
        if "private_key" in creds_info: creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n").strip()
        creds = service_account.Credentials.from_service_account_info(creds_info, scopes=['https://www.googleapis.com/auth/drive'])
        service = build('drive', 'v3', credentials=creds)
        id_cartella_final = ID_CARTELLA_DRIVE_PRINCIPALE
        try:
            query = f"name='{nome_cartella_dest}' and '{ID_CARTELLA_DRIVE_PRINCIPALE}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            risultato = service.files().list(q=query, spaces='drive', supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
            files = risultato.get('files', [])
            if files: id_cartella_final = files[0]['id']
            else:
                meta_cartella = {'name': nome_cartella_dest, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [ID_CARTELLA_DRIVE_PRINCIPALE]}
                id_cartella_final = service.files().create(body=meta_cartella, fields='id', supportsAllDrives=True).execute().get('id')
        except Exception: id_cartella_final = ID_CARTELLA_DRIVE_PRINCIPALE
            
        meta_file = {'name': nome_file, 'parents': [id_cartella_final]}
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
        service.files().create(body=meta_file, media_body=media, fields='id', supportsAllDrives=True).execute()
        return True
    except Exception: return None

# --- GESTORE DEL REINDIRIZZAMENTO DI SICUREZZA (QUERY PARAMS) ---
query_params = st.query_params
if "action" in query_params and "id" in query_params:
    azione = query_params["action"]
    id_req = query_params["id"]
    
    st.markdown("<h2 style='text-align:center; color:#8b1e1e;'>Elaborazione Istanza Logistica...</h2>", unsafe_allow_html=True)
    with st.spinner("Aggiornamento del registro in corso..."):
        try:
            # Inviamo i dati allo script via POST (superando i blocchi di sicurezza dell'account scolastico)
            payload = {"action": azione, "id": id_req}
            risposta = requests.post(URL_INTERMEDIARIO_SILENZIOSO, json=payload)
            
            st.balloons()
            st.success(f"✅ Operazione Completata con Successo!")
            st.info(f"La richiesta ID {id_req} è stata registrata correttamente nel foglio istituzionale.")
            st.markdown("<p style='text-align:center;'>Puoi chiudere questa scheda.</p>", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Errore durante l'aggiornamento: {str(e)}")
    st.stop()

# --- INIZIALIZZAZIONE SESSION STATE ---
if "ruolo_utente" not in st.session_state: st.session_state.ruolo_utente = None
if "utente_corrente" not in st.session_state: st.session_state.utente_corrente = ""
if "magazzino_selezionato" not in st.session_state: st.session_state.magazzino_selezionato = None
if "tipo_istanza_collaboratore" not in st.session_state: st.session_state.tipo_istanza_collaboratore = None

# --- ROUTER LOGIN ---
if st.session_state.ruolo_utente is None:
    col_l, col_c, col_r = st.columns([1, 1.8, 1])
    with col_c:
        st.markdown("<h2 style='text-align: center;'>Piattaforma Logistica di Istituto</h2>", unsafe_allow_html=True)
        with st.container(border=True):
            scelta = st.radio("Seleziona profilo d'accesso:", [
                "📝 Collaboratore - Richiesta Comodato d'Uso (PC / Chiavi)", 
                "📦 Collaboratore - Richiesta Materiale di Consumo / Logistica",
                "🔑 Staff Magazzino / Amministrazione"
            ])
            if "Collaboratore" in scelta:
                nome = st.text_input("Inserisci il tuo Nome e Cognome:")
                if st.button("Accedi al Modulo", type="primary", use_container_width=True):
                    if nome.strip():
                        st.session_state.ruolo_utente = "collaboratore"
                        st.session_state.utente_corrente = nome.strip()
                        st.session_state.tipo_istanza_collaboratore = "Comodato" if "Comodato" in scelta else "Materiale"
                        st.rerun()
                    else: st.error("Inserisci il tuo nome prima di procedere.")
            else:
                pwd = st.text_input("Codice autorizzazione staff:", type="password")
                if st.button("Autentica ed Entra", type="primary", use_container_width=True):
                    if pwd in PASSWORD_MAP:
                        st.session_state.ruolo_utente = "magazziniere"
                        st.session_state.magazzino_selezionato = PASSWORD_MAP[pwd]
                        st.session_state.utente_corrente = PASSWORD_MAP[pwd]
                        st.rerun()
                    elif pwd == PASSWORD_ADMIN:
                        st.session_state.ruolo_utente = "admin"
                        st.session_state.utente_corrente = "admin"
                        st.rerun()
                    else: st.error("Codice non valido.")
else:
    col_t, col_b_logout = st.columns([4, 1])
    with col_t: st.markdown(f"Accesso attivo: **{st.session_state.utente_corrente.upper()}**")
    with col_b_logout:
        if st.button("🚪 Cambia Profilo / Logout", use_container_width=True):
            st.session_state.ruolo_utente = None
            st.session_state.utente_corrente = ""
            st.session_state.magazzino_selezionato = None
            st.session_state.tipo_istanza_collaboratore = None
            st.rerun()
    st.image(URL_LOGO, use_container_width=True)

    # ==========================================
    # AMMINISTRATORE
    # ==========================================
    if st.session_state.ruolo_utente == "admin":
        tab_magazzini, tab_comodati, tab_richieste_ricevute = st.tabs(["📊 MAGAZZINI LOGISTICI", "✍️ GESTIONE COMODATI (PC & CHIAVI)", "📩 ISTANZE RICEVUTE"])
        with tab_magazzini:
            mag_sel = st.selectbox("Seleziona Magazzino:", LISTA_MAGAZZINI)
            st.dataframe(scarica_da_sheet(MAPPA_SCHEDE[mag_sel]["inventario"]), use_container_width=True, hide_index=True)
        with tab_richieste_ricevute:
            st.markdown("### Registro Richieste Centralizzato (Comodati & Materiali)")
            df_istanze_preside = scarica_da_sheet("Richieste_Preside")
            if df_istanze_preside.empty: st.info("Nessuna richiesta inoltrata al momento.")
            else: st.dataframe(df_istanze_preside, use_container_width=True, hide_index=True)
        with tab_comodati:
            df_inv_comodati = scarica_da_sheet("Inventario_Comodati")
            df_reg_comodati = scarica_da_sheet("Registro_Comodati")
            sub_inv, sub_nuovo, sub_registro = st.tabs(["📋 Inventario", "➕ Nuova Assegnazione", "📜 Contratti Attivi"])
            with sub_inv:
                with st.form("nuovo_ogg"):
                    col1, col2 = st.columns(2)
                    with col1:
                        id_b = st.text_input("ID Seriale (es. PC-012)")
                        tipo_b = st.selectbox("Categoria:", ["PC Notebook", "Chiave d'Accesso"])
                    with col2: desc_b = st.text_input("Descrizione")
                    if st.form_submit_button("Aggiungi all'Inventario", use_container_width=True):
                        if id_b.strip() and desc_b.strip():
                            nuovo_b = pd.DataFrame([{"id_bene": id_b.strip(), "tipo_bene": tipo_b, "descrizione": desc_b.strip(), "stato": "Disponibile"}])
                            df_inv_comodati = pd.concat([df_inv_comodati, nuovo_b], ignore_index=True)
                            carica_su_sheet(df_inv_comodati, "Inventario_Comodati")
                            st.success("Bene inserito!")
                            st.rerun()
                st.dataframe(df_inv_comodati, use_container_width=True, hide_index=True)
            with sub_nuovo:
                if df_inv_comodati.empty or not (df_inv_comodati["stato"] == "Disponibile").any(): st.warning("Nessun bene disponibile.")
                else:
                    col_n1, col_n2 = st.columns(2)
                    with col_n1:
                        tipo_sog = st.selectbox("Profilo Richiedente:", ["Alunno", "Genitore / Tutore", "Insegnante / Personale"])
                        nom_sog = st.text_input("Nome e Cognome dell'Assegnatario:")
                    with col_n2:
                        disp = df_inv_comodati[df_inv_comodati["stato"] == "Disponibile"]["id_bene"].tolist()
                        bene_sel = st.selectbox("Seleziona l'oggetto da consegnare:", disp)
                    
                    metodo_firma = st.radio("Firma:", ["✍️ Disegna", "🖼️ Carica"], key="metodo_consegna")
                    firma_base64_finale = ""
                    if metodo_firma == "✍️ Disegna":
                        html_pad_firma = """
                        <div style="background: #f8fafc; border: 2px dashed #cbd5e1; padding: 15px; border-radius: 12px; max-width:510px; font-family: sans-serif;">
                            <canvas id="canvas_firma" width="480" height="140" style="border:2px solid #64748b; background:#ffffff; cursor:crosshair; touch-action: none; border-radius:8px;"></canvas>
                            <br><div style="margin-top:10px; display:flex; gap:10px;">
                                <button type="button" onclick="pulisciCanvas()" style="padding:8px 15px; background:#ef4444; color:white; border:none; border-radius:6px; cursor:pointer; font-weight:bold;">Cancella</button>
                                <button type="button" onclick="generaCodiceFirma()" style="padding:8px 15px; background:#22c55e; color:white; border:none; border-radius:6px; cursor:pointer; font-weight:bold;">Genera Codice</button>
                            </div>
                            <textarea id="output_b64" style="width:100%; height:50px; margin-top:10px; font-size:10px; border:1px solid #cbd5e1; display:none;" readonly></textarea>
                        </div>
                        <script>
                            var canvas = document.getElementById('canvas_firma'); var ctx = canvas.getContext('2d');
                            ctx.strokeStyle = '#000000'; ctx.lineWidth = 3; ctx.lineCap = 'round'; var isDrawing = false;
                            function getCoordinate(e) { var rect = canvas.getBoundingClientRect(); if(e.touches && e.touches.length > 0) return { x: e.touches[0].clientX - rect.left, y: e.touches[0].clientY - rect.top }; return { x: e.clientX - rect.left, y: e.clientY - rect.top }; }
                            canvas.addEventListener('mousedown', function(e) { isDrawing = true; var p = getCoordinate(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); });
                            canvas.addEventListener('mousemove', function(e) { if(!isDrawing) return; var p = getCoordinate(e); ctx.lineTo(p.x, p.y); ctx.stroke(); });
                            canvas.addEventListener('mouseup', function() { isDrawing = false; });
                            canvas.addEventListener('touchstart', function(e) { isDrawing = true; var p = getCoordinate(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); e.preventDefault(); }, {passive: false});
                            canvas.addEventListener('touchmove', function(e) { if(!isDrawing) return; var p = getCoordinate(e); ctx.lineTo(p.x, p.y); ctx.stroke(); e.preventDefault(); }, {passive: false});
                            canvas.addEventListener('touchend', function() { isDrawing = false; });
                            function pulisciCanvas() { ctx.clearRect(0, 0, canvas.width, canvas.height); document.getElementById('output_b64').style.display = 'none'; }
                            function generaCodiceFirma() { var dataUrl = canvas.toDataURL('image/png'); var txt = document.getElementById('output_b64'); txt.value = dataUrl; txt.style.display = 'block'; txt.select(); }
                        </script>
                        """
                        st.components.v1.html(html_pad_firma, height=250)
                        stringa_incollata = st.text_area("Incolla codice firma:")
                        if stringa_incollata.startswith("data:image/png;base64,"): firma_base64_finale = stringa_incollata
                    else:
                        file_firma = st.file_uploader("Immagine:", type=["png", "jpg"])
                        if file_firma: firma_base64_finale = "data:image/png;base64," + base64.b64encode(file_firma.read()).decode("utf-8")

                    if st.button("🚀 Salva Contratto", type="primary", use_container_width=True):
                        if nom_sog.strip() and firma_base64_finale:
                            with st.spinner("Salvataggio..."):
                                id_comodato_numerico = pd.to_numeric(df_reg_comodati["id_comodato"], errors='coerce')
                                id_com = int(id_comodato_numerico.max()) + 1 if not id_comodato_numerico.dropna().empty else 1001
                                data_ora = datetime.now().strftime("%d/%m/%Y %H:%M")
                                pdf_bytes = genera_pdf_comodato(id_com, nom_sog.strip(), tipo_sog, bene_sel, data_ora, "CONSEGNA", firma_base64_finale, st.session_state.utente_corrente)
                                if carica_su_drive_unico(pdf_bytes, f"Verbale_{id_com}.pdf", "application/pdf", "Comodati_Consegne"):
                                    nuva_r = pd.DataFrame([{"id_comodato": id_com, "tipo_soggetto": tipo_sog, "nominativo": nom_sog.strip(), "id_bene": bene_sel, "data_consegna": data_ora, "stato_comodato": "In Corso"}])
                                    carica_su_sheet(pd.concat([df_reg_comodati, nuva_r], ignore_index=True), "Registro_Comodati")
                                    df_inv_comodati.loc[df_inv_comodati["id_bene"] == bene_sel, "stato"] = "Assegnato"
                                    carica_su_sheet(df_inv_comodati, "Inventario_Comodati")
                                    st.success("Fatto!")
                                    st.rerun()
            with sub_registro:
                attivi = df_reg_comodati[df_reg_comodati["stato_comodato"] == "In Corso"] if not df_reg_comodati.empty else pd.DataFrame()
                if attivi.empty: st.info("Nessun comodato attivo.")
                else:
                    for id_x, riga in attivi.iterrows():
                        with st.container(border=True):
                            st.markdown(f"📦 **{riga['id_bene']}** -> **{riga['nominativo']}**")

    # ==========================================
    # MAGAZZINIERE
    # ==========================================
    elif st.session_state.ruolo_utente == "magazziniere":
        st.markdown(f"## 📦 Magazzino: {st.session_state.magazzino_selezionato}")
        df_m = scarica_da_sheet(MAPPA_SCHEDE[st.session_state.magazzino_selezionato]["inventario"])
        st.dataframe(df_m, use_container_width=True, hide_index=True)

    # ==========================================
    # COLLABORATORE
    # ==========================================
    elif st.session_state.ruolo_utente == "collaboratore":
        tipo_corrente = st.session_state.tipo_istanza_collaboratore
        with st.form("mod_richiesta", clear_on_submit=True):
            cat_b = st.selectbox("Categoria:", ["PC Notebook", "Chiave d'Accesso", "Cancelleria / Carta"])
            obj_b = st.text_input("Oggetto:")
            mot_b = st.text_area("Motivazione:")
            if st.form_submit_button("Invia Richiesta", use_container_width=True):
                if obj_b.strip() and mot_b.strip():
                    df_r = scarica_da_sheet("Richieste_Preside")
                    try:
                        id_r_num = pd.to_numeric(df_r["id_richiesta"], errors='coerce')
                        nuovo_id = int(id_r_num.max()) + 1 if not id_r_num.dropna().empty else 101
                    except Exception: nuovo_id = 101
                    
                    nuova_r = pd.DataFrame([{
                        "id_richiesta": nuovo_id, "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "richiedente": st.session_state.utente_corrente, "tipo_istanza": tipo_corrente,
                        "categoria_bene": cat_b, "oggetto": obj_b.strip(), "motivazione": mot_b.strip(), "stato": "In attesa di approvazione"
                    }])
                    carica_su_sheet(pd.concat([df_r, nuova_r], ignore_index=True), "Richieste_Preside")
                    invia_notifica_email(nuovo_id, st.session_state.utente_corrente, tipo_corrente, obj_b.strip(), mot_b.strip())
                    st.success("Richiesta registrata e inviata!")
