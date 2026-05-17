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

# --- CONFIGURAZIONE INTERMEDIARIO (GOOGLE APPS SCRIPT) ---
URL_INTERMEDIARIO_SILENZIOSO = "https://script.google.com/macros/s/AKfycbyXBLjDpJrSGHoUpuspTsNAG9f6lGhF1e8oGyJ8nkY6jZMTJo04zsT_6eLyEybGgv4/exec"

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
ID_CARTELLA_DRIVE_PRINCIPALE = "1bVTs2smvVJONs2oIAFZdDvX9pYDK9MZT"
SPREADSHEET_ID = "1Q91H_TULvpsnPcyOwQ1lxmjOf809xp4cUz9p1EdMc-4"
LISTA_MAGAZZINI = ["Personale ATA", "Officina", "Tecnici Informatici"]

EMAIL_PRESIDE_TEST = "marcobrunetti14@gmail.com" # Per i test della Preside

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
    except Exception:
        return None

def scarica_da_sheet(nome_scheda):
    sh = connetti_google_sheets()
    if sh is None: return pd.DataFrame()
    try:
        worksheet = sh.worksheet(nome_scheda)
        df = pd.DataFrame(worksheet.get_all_records())
        return df
    except gspread.exceptions.WorksheetNotFound:
        if "Inventario_Comodati" in nome_scheda:
            df_base = pd.DataFrame(columns=["id_bene", "tipo_bene", "descrizione", "stato"])
        elif "Registro_Comodati" in nome_scheda:
            df_base = pd.DataFrame(columns=["id_comodato", "tipo_soggetto", "nominativo", "id_bene", "data_consegna", "stato_comodato"])
        elif "Richieste_Preside" in nome_scheda:
            df_base = pd.DataFrame(columns=["id_richiesta", "data_richiesta", "richiedente", "email_utente", "tipo_istanza", "categoria_bene", "oggetto", "motivazione", "stato"])
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

# --- MOTORE NOTIFICHE EMAIL (SISTEMA INTEGRATO) ---
def invia_email_sistema(destinatario, oggetto_mail, html_corpo):
    if "email_config" not in st.secrets: return False
    try:
        cfg = st.secrets["email_config"]
        msg = MIMEMultipart('alternative')
        msg['From'] = cfg.get("smtp_user")
        msg['To'] = destinatario
        msg['Subject'] = oggetto_mail
        msg.attach(MIMEText(html_corpo, 'html', 'utf-8'))
        
        server = smtplib.SMTP(cfg.get("smtp_server", "smtp.gmail.com"), int(cfg.get("smtp_port", 587)))
        server.starttls()
        server.login(cfg.get("smtp_user"), cfg.get("smtp_password"))
        server.sendmail(cfg.get("smtp_user"), destinatario, msg.as_string())
        server.quit()
        return True
    except Exception:
        return False

# 1. Email iniziale all'utente e alla Preside
def invia_notifica_nuova_richiesta(id_req, utente, email_ut, tipo_ist, ogg, mot):
    # Mail Utente
    html_ut = f"<h3>Portale Logistico Scarpa</h3><p>Gentile {utente}, la tua richiesta <b>ID {id_req}</b> per '{ogg}' è stata correttamente inserita ed è in fase di valutazione.</p>"
    invia_email_sistema(email_ut, f"Richiesta ID {id_req} in lavorazione", html_ut)
    
    # Mail Preside con Link Rapidi
    url_approva = f"https://magazzino-scarpa.streamlit.app/?action=approve&id={id_req}"
    url_rifiuta = f"https://magazzino-scarpa.streamlit.app/?action=reject&id={id_req}"
    html_pr = f"""
    <h2>Nuova Istanza da Autorizzare</h2>
    <p><b>Richiedente:</b> {utente}<br><b>Oggetto:</b> {ogg}<br><b>Motivazione:</b> {mot}</p>
    <div style='margin-top:20px;'>
        <a href='{url_approva}' style='background:#16a34a;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;margin-right:10px;'>🟢 AUTORIZZA ADESSO</a>
        <a href='{url_rifiuta}' style='background:#dc2626;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;'>🔴 RIFIUTA</a>
    </div>
    """
    invia_email_sistema(EMAIL_PRESIDE_TEST, f"📦 NUOVA ISTANZA DA VALUTARE - ID {id_req}", html_pr)

# 2. Email di conferma avvenuta approvazione Preside
def invia_notifica_approvata_preside(id_req, email_ut, ogg):
    html = f"<h3>Ottime notizie!</h3><p>La tua richiesta <b>ID {id_req}</b> per '{ogg}' è stata <b>autorizzata dalla Dirigente</b> ed è passata all'Ufficio Tecnico per la preparazione.</p>"
    invia_email_sistema(email_ut, f"Richiesta ID {id_req} Autorizzata dalla Dirigente", html)

# 3. Email di fine lavorazione Tecnico
def invia_notifica_pronto_ritiro(id_req, email_ut, ogg):
    html = f"<h3>Pronto per il ritiro!</h3><p>Il materiale relativo alla tua richiesta <b>ID {id_req} ({ogg})</b> è pronto. Puoi recarti presso l'Ufficio Tecnico/Magazzino per il ritiro e la firma del verbale.</p>"
    invia_email_sistema(email_ut, f"Materiale pronto per il ritiro - ID {id_req}", html)

# --- CLASSE PDF MINISTERIALE ---
class PDFMinisteriale(FPDF):
    def footer(self):
        self.set_y(-20)
        self.set_draw_color(180, 180, 180)
        self.set_line_width(0.1)
        self.line(15, self.get_y(), 195, self.get_y())
        self.set_font("Arial", "", 7)
        self.cell(180, 4, 'ISISS "A. SCARPA"      Via Primo Maggio, 3 31045 Motta di Livenza (Tv)      C.F. 94071460268      Codice univoco UFOA6X', ln=True, align="C")
        self.set_font("Arial", "I", 5)
        self.cell(180, 3, "Documento informatico firmato digitalmente ai sensi del D.Lgs 82/2005 CAD art.45, ss.mm.ii.", ln=True, align="C")

def pulisci_caratteri_fpdf(testo):
    mappa = {chr(224): "a'", chr(232): "e'", chr(233): "e'", chr(236): "i'", chr(242): "o'", chr(249): "u'", "à": "a'", "è": "e'", "é": "e'"}
    for k, v in mappa.items(): testo = testo.replace(k, v)
    return testo.encode('raw_unicode_escape').decode('utf-8').encode('latin1', 'replace').decode('latin1')

def genera_pdf_comodato(id_contratto, nome, ruolo, bene, data, tipo_operazione, firma_base64=None, utente_loggato="Ufficio Tecnico"):
    if not FPDF_AVAILABLE: return b"Errore PDF"
    pdf = PDFMinisteriale()
    pdf.add_page()
    try: pdf.image(URL_LOGO, x=15, y=10, w=180); pdf.set_y(32)
    except Exception: pdf.set_font("Times", "B", 13); pdf.cell(180, 6, "ISISS ANTONIO SCARPA", ln=True, align="C")
    
    pdf.set_font("Times", "", 10)
    pdf.cell(90, 5, "Protocollo n. (vedi segnatura)", ln=False)
    pdf.cell(90, 5, f"Motta di Livenza, {data.split(' ')[0]}", ln=True, align="R")
    pdf.ln(5)
    pdf.set_font("Times", "B", 10)
    pdf.cell(95, 5, "", ln=False)
    pdf.cell(85, 5, f"Al Sig./Sigg. {nome} ({ruolo})", ln=True)
    pdf.ln(5)
    pdf.cell(22, 5, "OGGETTO: ", ln=False)
    pdf.set_font("Times", "", 10)
    pdf.multi_cell(158, 5, f"Verbale di Consegna Bene d'Istituto in Comodato d'Uso Gratuito - ID Registro {id_contratto}")
    pdf.ln(5)
    
    corpo = f"Con la presente si attesta la consegna del bene (Seriale: {bene}) a favore di {nome}. Il richiedente si dichiara custode responsabile dell'oggetto integro ai fini istituzionali didattici."
    pdf.multi_cell(180, 6, pulisci_caratteri_fpdf(corpo))
    
    pdf.set_y(-50)
    y_f = pdf.get_y()
    pdf.cell(100, 5, f"F.to l'Amministratore ({utente_loggato})")
    pdf.cell(80, 5, "Firma del Richiedente:")
    
    if firma_base64 and len(firma_base64) > 100:
        try:
            img_data = base64.b64decode(firma_base64.split(",")[1])
            img_buffer = io.BytesIO(img_data)
            pdf.image(img_buffer, x=120, y=y_f + 5, w=45)
        except Exception: pdf.cell(80, 5, "[Firma Acquisita]")
    return pdf.output()

def carica_su_drive_unico(file_bytes, nome_file, mime_type, nome_cartella_dest):
    if not GOOGLE_DRIVE_AVAILABLE: return None
    creds_info = dict(st.secrets["google_creds"]) if "google_creds" in st.secrets else dict(st.secrets["gcp_service_account"])
    try:
        creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n").strip()
        creds = service_account.Credentials.from_service_account_info(creds_info, scopes=['https://www.googleapis.com/auth/drive'])
        service = googleapiclient.discovery.build('drive', 'v3', credentials=creds)
        meta = {'name': nome_file, 'parents': [ID_CARTELLA_DRIVE_PRINCIPALE]}
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
        service.files().create(body=meta, media_body=media, fields='id', supportsAllDrives=True).execute()
        return True
    except Exception: return None

# --- GESTORE DEL REINDIRIZZAMENTO DI SICUREZZA (QUERY PARAMS PRESIDE) ---
query_params = st.query_params
if "action" in query_params and "id" in query_params:
    azione = query_params["action"]
    id_req = query_params["id"]
    
    st.markdown("<h2 style='text-align:center;'>Elaborazione Decisione Dirigente...</h2>", unsafe_allow_html=True)
    df_f = scarica_da_sheet("Richieste_Preside")
    if not df_f.empty and "id_richiesta" in df_f.columns:
        df_f["id_richiesta"] = df_f["id_richiesta"].astype(str)
        idx_lista = df_f.index[df_f["id_richiesta"] == str(id_req)].tolist()
        if idx_lista:
            idx = idx_lista[0]
            nuovo_stato = "In lavorazione" if azione == "approve" else "Rifiutata"
            df_f.at[idx, "stato"] = nuovo_stato
            carica_su_sheet(df_f, "Richieste_Preside")
            
            # Invio mail notifica approvazione all'utente
            if azione == "approve":
                invia_notifica_approvata_preside(id_req, df_f.at[idx, "email_utente"], df_f.at[idx, "oggetto"])
            st.success("✅ Stato aggiornato correttamente!")
        else: st.error("Richiesta non trovata.")
    st.stop()

# --- INIZIALIZZAZIONE SESSION STATE ---
if "ruolo_utente" not in st.session_state: st.session_state.ruolo_utente = None
if "utente_corrente" not in st.session_state: st.session_state.utente_corrente = ""
if "magazzino_selezionato" not in st.session_state: st.session_state.magazzino_selezionato = None

# --- INTERFACCIA DI LOG-IN ---
if st.session_state.ruolo_utente is None:
    col_l, col_c, col_r = st.columns([1, 1.8, 1])
    with col_c:
        st.markdown("<h2 style='text-align: center;'>Piattaforma Logistica di Istituto</h2>", unsafe_allow_html=True)
        with st.container(border=True):
            scelta = st.radio("Seleziona profilo d'accesso:", [
                "📝 Collaboratore - Compila Nuova Richiesta",
                "🔑 Staff Magazzino / Amministrazione / Tecnici"
            ])
            if "Collaboratore" in scelta:
                nome = st.text_input("Nome e Cognome del Richiedente:")
                email_ut = st.text_input("Inserisci la tua Email per gli aggiornamenti:")
                if st.button("Accedi al Modulo", type="primary", use_container_width=True):
                    if nome.strip() and email_ut.strip():
                        st.session_state.ruolo_utente = "collaboratore"
                        st.session_state.utente_corrente = nome.strip()
                        st.session_state.email_utente = email_ut.strip()
                        st.rerun()
                    else: st.error("Tutti i campi sono obbligatori.")
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
                        st.session_state.utente_corrente = "Ufficio Tecnico (Admin)"
                        st.rerun()
                    else: st.error("Codice errato.")
else:
    # Barra superiore di logout
    col_t, col_b_logout = st.columns([4, 1])
    with col_t: st.markdown(f"Profilo Attivo: **{st.session_state.utente_corrente.upper()}**")
    with col_b_logout:
        if st.button("🚪 Esci", use_container_width=True):
            st.session_state.ruolo_utente = None; st.rerun()
    st.image(URL_LOGO, use_container_width=True)

    df_istanze = scarica_da_sheet("Richieste_Preside")

    # ==========================================
    # WORKFLOW 1: COLLABORATORE (INSERIMENTO)
    # ==========================================
    if st.session_state.ruolo_utente == "collaboratore":
        st.markdown("### Modulo di Nuova Richiesta")
        with st.form("mod_rich"):
            tipo_ist = st.selectbox("Tipo Istanza:", ["Comodato d'Uso Dispositivo", "Materiale Logistico / Consumo"])
            cat_b = st.selectbox("Categoria Bene:", ["PC Notebook", "Chiave d'Accesso", "Materiale d'Officina", "Cancelleria"])
            obj_b = st.text_input("Oggetto della Richiesta:")
            mot_b = st.text_area("Motivazione dettagliata:")
            if st.form_submit_button("Invia Istanza alla Dirigente", use_container_width=True):
                if obj_b.strip() and mot_b.strip():
                    try:
                        id_r_num = pd.to_numeric(df_istanze["id_richiesta"], errors='coerce')
                        nuovo_id = int(id_r_num.max()) + 1 if not id_r_num.dropna().empty else 101
                    except Exception: nuovo_id = 101
                    
                    nuova_r = pd.DataFrame([{
                        "id_richiesta": nuovo_id, "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "richiedente": st.session_state.utente_corrente, "email_utente": st.session_state.email_utente,
                        "tipo_istanza": tipo_ist, "categoria_bene": cat_b, "oggetto": obj_b.strip(), "motivazione": mot_b.strip(),
                        "stato": "In attesa di approvazione"
                    }])
                    carica_su_sheet(pd.concat([df_istanze, nuova_r], ignore_index=True), "Richieste_Preside")
                    invia_notifica_nuova_richiesta(nuovo_id, st.session_state.utente_corrente, st.session_state.email_utente, tipo_ist, obj_b.strip(), mot_b.strip())
                    st.success("Richiesta registrata! Riceverai gli avanzamenti di stato via Email.")

    # ==========================================
    # WORKFLOW 2: TECNICI INFORMATICI (PREPARAZIONE PC)
    # ==========================================
    elif st.session_state.ruolo_utente == "magazziniere" and st.session_state.magazzino_selezionato == "Tecnici Informatici":
        st.markdown("## 💻 Dashboard Lavorazione Tecnici Informatici")
        # I tecnici vedono solo le pratiche nello stato "In lavorazione" (Approvate dalla preside)
        da_lavorare = df_istanze[df_istanze["stato"] == "In lavorazione"] if not df_istanze.empty else pd.DataFrame()
        
        if da_lavorare.empty: st.info("Ottimo lavoro! Nessun PC da preparare al momento.")
        else:
            for _, riga in da_lavorare.iterrows():
                with st.container(border=True):
                    st.markdown(f"🛠️ **Richiesta ID {riga['id_richiesta']}** | Richiedente: **{riga['richiedente']}**")
                    st.markdown(f"**Oggetto:** {riga['oggetto']} — **Nota:** {riga['motivazione']}")
                    if st.button(f"Marca come LAVORATA (Pronto al ritiro) ## ID {riga['id_richiesta']}", use_container_width=True):
                        idx = df_istanze.index[df_istanze["id_richiesta"].astype(str) == str(riga['id_richiesta'])].tolist()[0]
                        df_istanze.at[idx, "stato"] = "Lavorata"
                        carica_su_sheet(df_istanze, "Richieste_Preside")
                        invia_notifica_pronto_ritiro(riga['id_richiesta'], riga['email_utente'], riga['oggetto'])
                        st.success("Stato aggiornato e utente notificato!")
                        st.rerun()

    # ==========================================
    # WORKFLOW 3: ADMIN / UFFICIO TECNICO (CONSEGNA & VERBALE)
    # ==========================================
    elif st.session_state.ruolo_utente == "admin":
        st.markdown("## 👑 Pannello di Amministrazione e Consegna Logistica")
        tab_pronte, tab_tutti_comodati, tab_registro_completo = st.tabs(["📦 PRATICHE PRONTE PER CONSEGNA", "📋 INVENTARIO GENERALE", "📜 REGISTRO STORICO"])
        
        with tab_pronte:
            # L'admin vede le pratiche che sono state "Lavorate" dai tecnici ed è pronto a fare il verbale
            pronte = df_istanze[df_istanze["stato"] == "Lavorata"] if not df_istanze.empty else pd.DataFrame()
            if pronte.empty: st.info("Nessuna pratica in attesa di consegna fisica.")
            else:
                for _, riga in pronte.iterrows():
                    with st.expander(f"📦 ID {riga['id_richiesta']} - Consegna a {riga['richiedente']} ({riga['oggetto']})"):
                        df_inv_c = scarica_da_sheet("Inventario_Comodati")
                        disp = df_inv_c[df_inv_c["stato"] == "Disponibile"]["id_bene"].tolist() if not df_inv_c.empty else []
                        
                        if not disp: st.warning("Attenzione: Nessun codice seriale/bene disponibile in inventario per l'associazione.")
                        else:
                            bene_assegnato = st.selectbox("Associa codice seriale/bene fisico:", disp, key=f"bene_{riga['id_richiesta']}")
                            firma_b64 = st.text_area("Incolla codice firma grafica (Pad):", key=f"firma_{riga['id_richiesta']}")
                            
                            if st.button(f"Esegui Consegna e Genera Verbale PDF ## {riga['id_richiesta']}", type="primary"):
                                if firma_b64.startswith("data:image/png;base64,"):
                                    df_reg_c = scarica_da_sheet("Registro_Comodati")
                                    id_comodato_numerico = pd.to_numeric(df_reg_c["id_comodato"], errors='coerce')
                                    id_com = int(id_comodato_numerico.max()) + 1 if not id_reg_c.empty and not id_comodato_numerico.dropna().empty else 1001
                                    
                                    data_ora = datetime.now().strftime("%d/%m/%Y %H:%M")
                                    pdf_bytes = genera_pdf_comodato(id_com, riga['richiedente'], "Personale", bene_assegnato, data_ora, "CONSEGNA", firma_b64, st.session_state.utente_corrente)
                                    
                                    if carica_su_drive_unico(pdf_bytes, f"Verbale_Consegna_{id_com}.pdf", "application/pdf", "Comodati_Consegne"):
                                        # Aggiorna lo stato della richiesta in "Assegnata" (Chiusa)
                                        idx = df_istanze.index[df_istanze["id_richiesta"].astype(str) == str(riga['id_richiesta'])].tolist()[0]
                                        df_istanze.at[idx, "stato"] = "Assegnata"
                                        carica_su_sheet(df_istanze, "Richieste_Preside")
                                        
                                        # Registra nel comodato attivo
                                        nuovo_c = pd.DataFrame([{"id_comodato": id_com, "tipo_soggetto": "Personale", "nominativo": riga['richiedente'], "id_bene": bene_assegnato, "data_consegna": data_ora, "stato_comodato": "In Corso"}])
                                        carica_su_sheet(pd.concat([df_reg_c, nuovo_c], ignore_index=True), "Registro_Comodati")
                                        
                                        # Aggiorna inventario
                                        df_inv_c.loc[df_inv_c["id_bene"] == bene_assegnato, "stato"] = "Assegnato"
                                        carica_su_sheet(df_inv_c, "Inventario_Comodati")
                                        
                                        st.success("Assegnazione completata con successo! PDF caricato su Google Drive.")
                                        st.rerun()
                                else: st.error("Inserire una firma valida prima di procedere.")
        with tab_tutti_comodati:
            df_inv_c = scarica_da_sheet("Inventario_Comodati")
            st.dataframe(df_inv_c, use_container_width=True, hide_index=True)
        with tab_registro_completo:
            st.dataframe(df_istanze, use_container_width=True, hide_index=True)

    # ==========================================
    # ALTRI MAGAZZINI (ATA / OFFICINA STANDARD)
    # ==========================================
    elif st.session_state.ruolo_utente == "magazziniere":
        st.markdown(f"## 📦 Visualizzazione Magazzino: {st.session_state.magazzino_selezionato}")
        st.dataframe(scarica_da_sheet(MAPPA_SCHEDE[st.session_state.magazzino_selezionato]["inventario"]), use_container_width=True, hide_index=True)
