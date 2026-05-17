import streamlit as st
import pandas as pd
from datetime import datetime
import io
import base64
from PIL import Image
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURAZIONE SMTP EMAIL (Da compilare nei Secrets di Streamlit) ---
# Inserisci questi dati nei Secrets di Streamlit sotto la voce [email_smtp]
SMTP_SERVER = st.secrets.get("email_smtp", {}).get("server", "smtp.gmail.com")
SMTP_PORT = int(st.secrets.get("email_smtp", {}).get("port", 587))
SMTP_USER = st.secrets.get("email_smtp", {}).get("user", "tuamail@istitutoscarpa.edu.it")
SMTP_PASS = st.secrets.get("email_smtp", {}).get("password", "tuapasswordsegreta")

# Librerie di archiviazione Google
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

st.set_page_config(page_title="Gestione Magazzini Scarpa", page_icon="🏢", layout="wide")

PASSWORD_MAP = {"ata2026": "Personale ATA", "officina2026": "Officina", "tecnici2026": "Tecnici Informatici"}
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

# --- STILE ISTITUZIONALE ---
st.markdown("""
    <style>
        .stApp { background-color: #f8fafc; }
        [data-testid="stVerticalBlockBorderWrapper"] { background: white !important; padding: 30px !important; border-radius: 16px !important; border: 1px solid #e2e8f0 !important; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05) !important; }
        div.stButton > button:first-child { background-color: #8b1e1e !important; color: white !important; border-radius: 10px !important; border: none !important; font-weight: 600 !important; padding: 12px 24px !important; }
        div.stButton > button:first-child:hover { background-color: #a72828 !important; }
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
    except Exception: return None

def scarica_da_sheet(nome_scheda):
    sh = connetti_google_sheets()
    if sh is None: return pd.DataFrame()
    try:
        worksheet = sh.worksheet(nome_scheda)
        return pd.DataFrame(worksheet.get_all_records())
    except gspread.exceptions.WorksheetNotFound:
        if "Inventario_Comodati" in nome_scheda:
            df_base = pd.DataFrame(columns=["id_bene", "tipo_bene", "descrizione", "stato"])
        elif "Registro_Comodati" in nome_scheda:
            df_base = pd.DataFrame(columns=["id_comodato", "tipo_soggetto", "nominativo", "id_bene", "data_consegna", "stato_comodato"])
        elif "Richieste_Comodati" in nome_scheda:
            df_base = pd.DataFrame(columns=["id_richiesta", "richiedente", "email", "ruolo", "destinazione_bene", "note_destinazione", "tipo_bene", "data_richiesta", "stato_approvazione", "data_approvazione"])
        else:
            df_base = pd.DataFrame(columns=["id", "elemento", "valore"])
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

# --- FUNZIONE INVIO MAIL LOGISTICA ---
def invia_notifica_email(destinatario, oggetto, corpo_html):
    if SMTP_USER == "tuamail@istitutoscarpa.edu.it": 
        return False # Blocco se non configurato
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = destinatario
        msg['Subject'] = oggetto
        msg.attach(MIMEText(corpo_html, 'html'))
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, destinatario, msg.as_string())
        server.quit()
        return True
    except Exception:
        return False

# --- CLASSE PDF ANTISOPRAVVOLO ---
class PDFMinisteriale(FPDF):
    def footer(self):
        self.set_y(-20)
        self.set_draw_color(180, 180, 180)
        self.set_line_width(0.1)
        self.line(15, self.get_y(), 195, self.get_y())
        self.set_font("Arial", "", 7)
        self.cell(180, 4, 'ISISS "A. SCARPA"      Via Primo Maggio, 3 31045 Motta di Livenza (Tv)      C.F. 94071460268      Codice univoco UFOA6X', ln=True, align="C")
        self.cell(180, 3, "tvis01100a@istruzione.it      tvis01100a@pec.istruzione.it", ln=True, align="C")

def pulisci_caratteri_fpdf(testo):
    mappa = {"à": "a'", "è": "e'", "é": "e'", "ì": "i'", "ò": "o'", "ù": "u'", "’": "'"}
    for k, v in mappa.items(): testo = testo.replace(k, v)
    return testo.encode('raw_unicode_escape').decode('utf-8').encode('latin1', 'replace').decode('latin1')

def genera_pdf_comodato(id_contratto, nome, ruolo, bene, data, tipo_operazione, firma_base64=None, utente_loggato="Ufficio Tecnico"):
    if not FPDF_AVAILABLE: return b"Errore PDF"
    pdf = PDFMinisteriale(orientation='P', unit='mm', format='A4')
    pdf.set_margins(15, 12, 15)
    pdf.set_auto_page_break(auto=True, margin=22) 
    pdf.add_page()
    try:
        pdf.image(URL_LOGO, x=15, y=10, w=180)
        pdf.set_y(32)
    except Exception:
        pdf.set_font("Times", "B", 13); pdf.cell(180, 6, "ISISS ANTONIO SCARPA", ln=True, align="C"); pdf.ln(5)
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
    pdf.set_font("Times", "B", 10); pdf.cell(22, 5, "OGGETTO: ", ln=False); pdf.set_font("Times", "", 10)
    testo_oggetto = f"Verbale di Consegna e Assegnazione in Comodato d'Uso Gratuito dei Beni d'Istituto - Registro ID {id_contratto}." if tipo_operazione == "CONSEGNA" else f"Ricevuta di Riconsegna, Scarico Logistico e Cessazione Comodato d'Uso - Registro ID {id_contratto}."
    pdf.multi_cell(158, 5, pulisci_caratteri_fpdf(testo_oggetto))
    pdf.ln(8)
    pdf.set_font("Times", "", 10)
    if tipo_operazione == "CONSEGNA":
        corpo_testo = f"Con la presente si attesta che in data odierna l'Amministrazione dell'Istituto Superiore Antonio Scarpa provvede alla consegna in comodato d'uso del bene sotto specificato al richiedente indicato.\n\nDettaglio del Bene Assegnato:\n- Identificativo / Seriale: {bene}\n\nIl sottoscritto prende in carico l'oggetto integro, dichiarando di averne verificato il perfetto stato di funzionamento."
    else:
        corpo_testo = f"Con la presente si attesta che il bene sotto descritto e stato formalmente riconsegnato all'Istituto in data odierna.\n\nDettaglio del Bene Riconsegnato:\n- Identificativo / Seriale: {bene}"
    pdf.multi_cell(180, 6, pulisci_caratteri_fpdf(corpo_testo), align="J")
    pdf.set_y(-60)
    y_posizione_firme = pdf.get_y()
    pdf.cell(100, 5, "Per l'Amministrazione:", align="L")
    pdf.cell(80, 5, "Firma del Richiedente:", align="L", ln=True)
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
        except Exception: pdf.cell(80, 5, "[Firma Digitale]", align="L", ln=True)
    return pdf.output()

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
        meta_file = {'name': nome_file, 'parents': [id_cartella_final]}
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
        service.files().create(body=meta_file, media_body=media, fields='id', supportsAllDrives=True).execute()
        return True
    except Exception: return None

# =====================================================================
# --- INTERCETTAZIONE AZIONE AUTORIZZAZIONE PRESIDE (WEB-HOOK URL) ---
# =====================================================================
query_params = st.query_params
if "action" in query_params and "id" in query_params:
    azione = query_params["action"]
    id_req = query_params["id"]
    
    if azione == "autorizza":
        df_richieste_globali = scarica_da_sheet("Richieste_Comodati")
        # Confronto forzato come stringa
        df_richieste_globali["id_richiesta"] = df_richieste_globali["id_richiesta"].astype(str)
        
        if not df_richieste_globali.empty and id_req in df_richieste_globali["id_richiesta"].values:
            stato_attuale = df_richieste_globali.loc[df_richieste_globali["id_richiesta"] == id_req, "stato_approvazione"].values[0]
            if stato_attuale == "In attesa di approvazione":
                orario_adesso = datetime.now().strftime("%d/%m/%Y %H:%M")
                df_richieste_globali.loc[df_richieste_globali["id_richiesta"] == id_req, "stato_approvazione"] = "Autorizzata"
                df_richieste_globali.loc[df_richieste_globali["id_richiesta"] == id_req, "data_approvazione"] = orario_adesso
                carica_su_sheet(df_richieste_globali, "Richieste_Comodati")
                
                # Invia conferma mail all'utente
                mail_utente = df_richieste_globali.loc[df_richieste_globali["id_richiesta"] == id_req, "email"].values[0]
                nom_utente = df_richieste_globali.loc[df_richieste_globali["id_richiesta"] == id_req, "richiedente"].values[0]
                
                html_approvato = f"<h3>Richiesta Approvata</h3><p>Gentile {nom_utente}, la Dirigente ha autorizzato il tuo comodato. La richiesta è in lavorazione presso l'Ufficio Tecnico. Riceverai una mail non appena il dispositivo sarà pronto.</p>"
                invia_notifica_email(mail_utente, "Aggiornamento Comodato: Richiesta Autorizzata della Dirigente", html_approvato)
                
                st.success(f"🎉 Richiesta ID {id_req} Autorizzata con successo in data {orario_adesso}! I magazzinieri hanno ricevuto la notifica.")
            else:
                st.info(f"Questa richiesta risulta già nello stato: '{stato_attuale}'.")
        else:
            st.error("Errore: ID Richiesta non trovato nei registri.")
    st.stop()

# --- GESTIONE SESSIONE UTENTE ---
if "ruolo_utente" not in st.session_state: st.session_state.ruolo_utente = None
if "utente_corrente" not in st.session_state: st.session_state.utente_corrente = ""
if "magazzino_selezionato" not in st.session_state: st.session_state.magazzino_selezionato = None

if st.session_state.ruolo_utente is None:
    col_l, col_c, col_r = st.columns([1, 1.8, 1])
    with col_c:
        st.image(URL_LOGO, use_container_width=True)
        st.markdown("<h2 style='text-align: center;'>Piattaforma Logistica di Istituto</h2>", unsafe_allow_html=True)
        with st.container(border=True):
            scelta = st.radio("Seleziona profilo:", ["Professore / Studente (Richiesta Comodato)", "Staff Magazzino / Amministrazione"])
            if scelta == "Professore / Studente (Richiesta Comodato)":
                st.session_state.ruolo_utente = "collaboratore"
                st.rerun()
            else:
                pwd = st.text_input("Codice autorizzazione:", type="password")
                if st.button("Autentica ed Entra", type="primary", use_container_width=True):
                    if pwd in PASSWORD_MAP:
                        st.session_state.ruolo_utente = "magazziniere"
                        st.session_state.magazzino_selezionato = PASSWORD_MAP[pwd]
                        st.session_state.utente_corrente = PASSWORD_MAP[pwd]
                        st.rerun()
                    elif pwd == PASSWORD_ADMIN:
                        st.session_state.ruolo_utente = "admin"; st.session_state.utente_corrente = "admin"; st.rerun()
                    else: st.error("Codice non valido.")
else:
    col_t, col_b_logout = st.columns([4, 1])
    with col_t: st.markdown(f"Accesso: **{st.session_state.utente_corrente.upper()}**")
    with col_b_logout:
        if st.button("🚪 Esci / Cambia", use_container_width=True):
            st.session_state.ruolo_utente = None; st.rerun()

    # --- ACCESSO AMMINISTRATORE / GESTIONE COMODATI COMPLETA ---
    if st.session_state.ruolo_utente == "admin":
        tab_magazzini, tab_comodati = st.tabs(["📊 MAGAZZINI LOGISTICI", "✍️ GESTIONE COMODATI AUTORIZZATI"])
        
        with tab_comodati:
            df_inv_comodati = scarica_da_sheet("Inventario_Comodati")
            df_reg_comodati = scarica_da_sheet("Registro_Comodati")
            df_richieste_comodati = scarica_da_sheet("Richieste_Comodati")
            
            sub_richieste, sub_registro, sub_inv = st.tabs(["📥 Richieste Web ed Autorizzazioni Preside", "📜 Contratti Consegnati", "📋 Inventario Fisico"])
            
            with sub_richieste:
                st.markdown("### Richieste in Arrivo dal Modulo Web Form")
                if df_richieste_comodati.empty:
                    st.info("Nessuna richiesta inoltrata.")
                else:
                    # Filtra solo le richieste già autorizzate dalla preside ma non ancora sbrigate
                    lavorabili = df_richieste_comodati[df_richieste_comodati["stato_approvazione"] == "Autorizzata"]
                    in_attesa = df_richieste_comodati[df_richieste_comodati["stato_approvazione"] == "In attesa di approvazione"]
                    
                    st.markdown(f"🟠 **In attesa del clic della Preside:** {len(in_attesa)} richieste.")
                    st.markdown(f"🟢 **Autorizzate dalla Preside (Da Lavorare):** {len(lavorabili)} richieste.")
                    
                    for idx, req in lavorabili.iterrows():
                        with st.container(border=True):
                            col_a, col_b = st.columns([3, 1])
                            with col_a:
                                st.markdown(f"👤 Richiedente: **{req['richiedente']}** ({req['email']}) - Ruolo: *{req['ruolo']}*")
                                st.markdown(f"🎯 Destinazione Dispositivo: **{req['destinazione_bene']}** ({req['note_destinazione']})")
                                st.caption(f"Tipo richiesto: **{req['tipo_bene']}** | Approvato dalla Dirigente il: {req['data_approvazione']}")
                            with col_b:
                                disp_beni = df_inv_comodati[(df_inv_comodati["stato"] == "Disponibile") & (df_inv_comodati["tipo_bene"] == req['tipo_bene'])]["id_bene"].tolist()
                                if not disp_beni:
                                    st.error("Nessun pezzo disponibile in Inventario!")
                                else:
                                    bene_abbinato = st.selectbox(f"Assegna Seriale a {req['richiedente']}:", disp_beni, key=f"sel_{req['id_richiesta']}")
                                    
                                    if st.button("Consegna e Genera Verbale", key=f"btn_{req['id_richiesta']}", type="primary"):
                                        id_com = int(df_reg_comodati["id_comodato"].astype(float).max()) + 1 if not df_reg_comodati.empty else 1001
                                        data_ora_consegna = datetime.now().strftime("%d/%m/%Y %H:%M")
                                        
                                        # Genera PDF simulando firma o dicitura ministeriale
                                        pdf_bytes = genera_pdf_comodato(id_com, req['richiedente'], req['ruolo'], bene_abbinato, data_ora_consegna, "CONSEGNA", None)
                                        
                                        if carica_su_drive_unico(pdf_bytes, f"Verbale_{id_com}_{req['richiedente']}.pdf", "application/pdf", "Comodati_Consegne"):
                                            # Salva nel registro
                                            nuovo_reg = pd.DataFrame([{"id_comodato": id_com, "tipo_soggetto": req['ruolo'], "nominativo": req['richiedente'], "id_bene": bene_abbinato, "data_consegna": data_ora_consegna, "stato_comodato": "In Corso"}])
                                            df_reg_comodati = pd.concat([df_reg_comodati, nuovo_reg], ignore_index=True)
                                            carica_su_sheet(df_reg_comodati, "Registro_Comodati")
                                            
                                            # Aggiorna stato inventario
                                            df_inv_comodati.loc[df_inv_comodati["id_bene"] == bene_abbinato, "stato"] = "Assegnato"
                                            carica_su_sheet(df_inv_comodati, "Inventario_Comodati")
                                            
                                            # Aggiorna stato richiesta
                                            df_richieste_comodati.loc[df_richieste_comodati["id_richiesta"] == req["id_richiesta"], "stato_approvazione"] = f"Evaso (Contratto {id_com})"
                                            carica_su_sheet(df_richieste_comodati, "Richieste_Comodati")
                                            
                                            # Mail finale all'utente: pronto al ritiro
                                            html_ritiro = f"<h3>Il tuo Dispositivo è Pronto!</h3><p>Ciao {req['richiedente']}, il tuo {req['tipo_bene']} (Seriale: {bene_abbinato}) è stato configurato ed è pronto al ritiro presso l'Ufficio Tecnico.</p>"
                                            invia_notifica_email(req['email'], "Materiale Pronto per il Ritiro - Ufficio Tecnico Scarpa", html_ritiro)
                                            
                                            st.success("Contratto Evaso e Mail di ritiro inviata!")
                                            st.rerun()

            with sub_registro:
                st.dataframe(df_reg_comodati, use_container_width=True, hide_index=True)
            with sub_inv:
                st.dataframe(df_inv_comodati, use_container_width=True, hide_index=True)

    # --- INTERFACCIA WEB DI RICHIESTA (DOCENTE / ALUNNO / GENITORE) ---
    elif st.session_state.ruolo_utente == "collaboratore":
        st.image(URL_LOGO, use_container_width=True)
        st.markdown("### Modulo Web di Richiesta Comodato d'Uso")
        st.write("Compila accuratamente tutti i campi. Il sistema invierà la richiesta di autorizzazione direttamente alla Dirigente Scolastica.")
        
        df_richieste_comodati = scarica_da_sheet("Richieste_Comodati")
        
        with st.form("form_richiesta_utente"):
            col_w1, col_w2 = st.columns(2)
            with col_w1:
                nome_ric = st.text_input("Nome e Cognome del Richiedente (Docente o Genitore):")
                email_ric = st.text_input("Indirizzo Email Obbligatorio (Ricezione Ricevuta):")
                ruolo_ric = st.selectbox("Ruolo del Richiedente:", ["Insegnante / Personale", "Genitore / Tutore", "Alunno Maggiorenne"])
            with col_w2:
                tipo_bene_ric = st.selectbox("Dispositivo Necessario:", ["PC Notebook", "Chiave d'Accesso"])
                destinazione_ric = st.selectbox("Per chi serve il dispositivo?", ["Uso Personale / Didattico proprio", "Per un Alunno (es. Docente di Sostegno / Inclusione)"])
                note_destinazione_ric = st.text_area("Specificare il motivo o il nome dell'alunno beneficiario:")
                
            if st.form_submit_button("Invia Richiesta alla Dirigente", use_container_width=True):
                if not nome_ric.strip() or not email_ric.strip() or "@" not in email_ric:
                    st.error("Compilare correttamente il Nome e l'indirizzo Email.")
                else:
                    id_r = int(df_richieste_comodati["id_richiesta"].astype(float).max()) + 1 if not df_richieste_comodati.empty else 5001
                    data_richiesta_corrente = datetime.now().strftime("%d/%m/%Y %H:%M")
                    
                    # Salva su Google Sheets
                    nuova_richiesta_df = pd.DataFrame([{
                        "id_richiesta": id_r, "richiedente": nome_ric.strip(), "email": email_ric.strip(),
                        "ruolo": ruolo_ric, "destinazione_bene": destinazione_ric, "note_destinazione": note_destinazione_ric.strip(),
                        "tipo_bene": tipo_bene_ric, "data_richiesta": data_richiesta_corrente,
                        "stato_approvazione": "In attesa di approvazione", "data_approvazione": ""
                    }])
                    df_richieste_comodati = pd.concat([df_richieste_comodati, nuova_richiesta_df], ignore_index=True)
                    carica_su_sheet(df_richieste_comodati, "Richieste_Comodati")
                    
                    # 1. INVIO EMAIL DI RICEVUTA ALL'UTENTE
                    html_ricevuta_utente = f"""
                    <h3>Ricevuta di Presa in Carico Richiesta N° {id_r}</h3>
                    <p>Gentile {nome_ric}, abbiamo ricevuto la tua richiesta per un <b>{tipo_bene_ric}</b> ({destinazione_ric}).</p>
                    <p>La richiesta è stata inoltrata alla Dirigente Scolastica per l'autorizzazione istituzionale.</p>
                    """
                    invia_notifica_email(email_ric.strip(), f"Ricevuta Richiesta Comodato N°{id_r} - ISISS Scarpa", html_ricevuta_utente)
                    
                    # 2. INVIO EMAIL ALLA PRESIDE CON IL TASTO MAGICO
                    # Recuperiamo l'indirizzo dell'app corrente per creare il link di callback
                    url_base_app = "https://magazzini-scarpa.streamlit.app" # Sostituisci con il link reale della tua app erogata
                    link_autorizza = f"{url_base_app}/?action=autorizza&id={id_r}"
                    
                    html_preside = f"""
                    <h2>Nuova Richiesta di Comodato da Autorizzare</h2>
                    <p>Il dipendente/genitore <b>{nome_ric}</b> ha richiesto l'assegnazione di: <b>{tipo_bene_ric}</b>.</p>
                    <p><b>Destinazione d'uso:</b> {destinazione_ric}<br><b>Note aggiuntive:</b> {note_destinazione_ric}</p>
                    <br>
                    <a href="{link_autorizza}" style="background-color: #22c55e; color: white; padding: 12px 25px; text-decoration: none; font-weight: bold; border-radius: 8px; display: inline-block;">APPROVA E AUTORIZZA RICHIESTA</a>
                    <br><br>
                    <p style="font-size:11px; color:#64748b;">Cliccando sul pulsante la richiesta passerà direttamente in lavorazione all'ufficio tecnico senza bisogno di entrare nell'app.</p>
                    """
                    # Sostituisci 'dirigente@istitutoscarpa.edu.it' con la mail reale della preside per i test
                    invia_notifica_email("dirigente@istitutoscarpa.edu.it", f"Richiesta Comodato d'Uso da Autorizzare - ID {id_r}", html_preside)
                    
                    st.success(f"🎉 Richiesta registrata con successo (ID {id_r})! È stata inviata una mail di ricevuta a te ed una notifica di approvazione immediata alla Dirigente Scolastica.")
