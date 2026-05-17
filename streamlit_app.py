import streamlit as st
import pandas as pd
from datetime import datetime
import io
import base64
from PIL import Image
import requests

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

# --- COSTANTI E CONFIGURAZIONI REPARTI ---
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

# --- FUNZIONI DI DIALOGO DATABASE GOOGLE SHEETS ---
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
        return pd.DataFrame(worksheet.get_all_records())
    except gspread.exceptions.WorksheetNotFound:
        if "Inventario_Comodati" in nome_scheda:
            df_base = pd.DataFrame(columns=["id_bene", "tipo_bene", "descrizione", "stato"])
        elif "Registro_Comodati" in nome_scheda:
            df_base = pd.DataFrame(columns=["id_comodato", "tipo_soggetto", "nominativo", "id_bene", "data_consegna", "stato_comodato"])
        elif "Istanze_Comodati" in nome_scheda:
            df_base = pd.DataFrame(columns=["id_istanza", "timestamp", "nominativo", "tipo_soggetto", "email", "categoria_bene", "motivazione", "stato", "token_approvazione"])
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

# --- STRUTTURA DEL DOCUMENTO PDF MINISTERIALE ---
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
        "à": "a'", "è": "e'", "é": "e'", "ì": "i'", "ò": "o'", "ù": "u'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"
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
    pdf.cell(95, 5)
    pdf.cell(85, 5, "Ai Docenti / Al Personale Interessato", ln=True, align="L")
    pdf.cell(95, 5)
    pdf.cell(85, 5, pulisci_caratteri_fpdf(f"Sig./Sigg. {nome} ({ruolo})"), ln=True, align="L")
    pdf.ln(8)
    
    pdf.set_font("Times", "B", 10)
    pdf.cell(22, 5, "OGGETTO: ")
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
            f"Con la presente si attesta che in data odierna l'Amministrazione dell'Istituto Superiore\n"
            f"Antonio Scarpa provvede alla consegna in comodato d'uso del bene sotto specificato al richiedente indicato.\n\n"
            f"Dettaglio del Bene Assegnato:\n"
            f"- Identificativo / Seriale: {bene}\n\n"
            f"Il sottoscritto prende in carico l'oggetto integro, dichiarando di averne verificato il perfetto stato "
            f"di funzionamento. Si impegna altresi a custodirlo responsabilmente, utilizzarlo esclusivamente per le finalita "
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
    
    pdf.cell(100, 5, "Per l'Amministrazione:")
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
            pdf.cell(80, 5, "[Firma Acquisita]", align="L", ln=True)
    else:
        pdf.cell(80, 5, "____________________________", align="L", ln=True)
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
        service = googleapiclient.discovery.build('drive', 'v3', credentials=creds)
        
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

# --- APPS SCRIPT SILENT DISPATCHER ---
def invia_notifica_silenziosa_gas(payload):
    try: requests.post(URL_INTERMEDIARIO_SILENZIOSO, json=payload, timeout=8)
    except Exception: pass

# --- PAD FIRMA HTML ---
def rendering_pad_firma_html(id_canvas):
    return f"""
    <div style="background:#ffffff; border:2px dashed #cbd5e1; padding:12px; border-radius:10px; max-width:480px; font-family:sans-serif;">
        <canvas id="{id_canvas}" width="450" height="150" style="border:1px solid #64748b; background:#fafafa; cursor:crosshair; touch-action:none; border-radius:6px;"></canvas>
        <div style="margin-top:10px; display:flex; justify-content:space-between; align-items:center;">
            <button type="button" onclick="clearPad_{id_canvas}()" style="padding:6px 14px; background:#ef4444; color:white; border:none; border-radius:6px; cursor:pointer; font-weight:bold;">Cancella tutto</button>
            <span style="font-size:11px; color:#64748b; font-weight:bold;">Rilascia il mouse per aggiornare il codice</span>
        </div>
        <div style="margin-top:10px;">
            <label style="font-size:12px; font-weight:bold; color:#1e293b;">Codice di Firma Generato (Copia e incolla nel box di Streamlit):</label>
            <textarea id="out_{id_canvas}" readonly style="width:100%; height:50px; margin-top:5px; font-size:10px; color:#475569; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:4px; box-sizing:border-box; padding:4px; resize:none;"></textarea>
        </div>
    </div>
    <script>
        var canvas = document.getElementById('{id_canvas}');
        var ctx = canvas.getContext('2d');
        ctx.strokeStyle = '#020617'; ctx.lineWidth = 3.5; ctx.lineCap = 'round';
        var drawing = false;
        
        function getPos(e) {{
            var r = canvas.getBoundingClientRect();
            if(e.touches && e.touches.length > 0) return {{ x: e.touches[0].clientX - r.left, y: e.touches[0].clientY - r.top }};
            return {{ x: e.clientX - r.left, y: e.clientY - r.top }};
        }}
        function updateOutput() {{
            var dataUrl = canvas.toDataURL('image/png');
            document.getElementById('out_{id_canvas}').value = dataUrl;
        }}
        canvas.addEventListener('mousedown', function(e){{ drawing=true; var p=getPos(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); }});
        canvas.addEventListener('mousemove', function(e){{ if(!drawing)return; var p=getPos(e); ctx.lineTo(p.x, p.y); ctx.stroke(); }});
        canvas.addEventListener('mouseup', function(){{ drawing=false; updateOutput(); }});
        canvas.addEventListener('touchstart', function(e){{ drawing=true; var p=getPos(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); e.preventDefault(); }}, {{passive:false}});
        canvas.addEventListener('touchmove', function(e){{ if(!drawing)return; var p=getPos(e); ctx.lineTo(p.x, p.y); ctx.stroke(); e.preventDefault(); }}, {{passive:false}});
        canvas.addEventListener('touchend', function(){{ drawing=false; updateOutput(); }});
        function clearPad_{id_canvas}() {{ ctx.clearRect(0, 0, canvas.width, canvas.height); document.getElementById('out_{id_canvas}').value = ''; }}
    </script>
    """

# --- INIZIALIZZAZIONE STATO SESSIONE ---
if "ruolo_utente" not in st.session_state: st.session_state.ruolo_utente = None
if "utente_corrente" not in st.session_state: st.session_state.utente_corrente = ""
if "magazzino_selezionato" not in st.session_state: st.session_state.magazzino_selezionato = None

# --- APPROVAZIONI LINK RAPIDI DIRIGENTE ---
query_params = st.query_params
if "action" in query_params and "token" in query_params:
    azione = query_params["action"]
    tk = query_params["token"]
    df_cerca = scarica_da_sheet("Istanze_Comodati")
    if not df_cerca.empty and tk in df_cerca["token_approvazione"].astype(str).values:
        idx_riga = df_cerca[df_cerca["token_approvazione"].astype(str) == tk].index[0]
        stato_attuale = df_cerca.loc[idx_riga, "stato"]
        if stato_attuale == "In attesa di Dirigente":
            nuovo_st = "Approvata da Dirigente" if azione == "approva" else "Rifiutata da Dirigente"
            df_cerca.loc[idx_riga, "stato"] = nuovo_st
            carica_su_sheet(df_cerca, "Istanze_Comodati")
            st.success(f"Pratica aggiornata: '{nuovo_st}'.")
        else: st.warning(f"Già gestita. Stato: {stato_attuale}")
    else: st.error("Token non valido.")
    st.stop()

# --- INTERFACCIA DI ACCESSO / LOGIN ---
if st.session_state.ruolo_utente is None:
    col_l, col_c, col_r = st.columns([1, 1.8, 1])
    with col_c:
        st.image(URL_LOGO, use_container_width=True)
        st.markdown("<h2 style='text-align: center;'>Piattaforma Logistica di Istituto</h2>", unsafe_allow_html=True)
        with st.container(border=True):
            scelta = st.radio("Seleziona il tuo profilo d'accesso:", ["Collaboratore / Richiedente", "Staff Interno / Amministrazione"])
            
            if scelta == "Collaboratore / Richiedente":
                nome = st.text_input("Inserisci Nome e Cognome:")
                if st.button("Accedi all'Area Richieste", type="primary", use_container_width=True):
                    if nome.strip():
                        st.session_state.ruolo_utente = "collaboratore"
                        st.session_state.utente_corrente = nome.strip()
                        st.rerun()
                    else:
                        st.error("Inserisci il tuo nome prima di continuare.")
            else:
                pwd = st.text_input("Inserisci il Codice di Autorizzazione Reparto:", type="password")
                if st.button("Autentica ed Entra", type="primary", use_container_width=True):
                    if pwd in PASSWORD_MAP:
                        st.session_state.ruolo_utente = "magazziniere"
                        st.session_state.magazzino_selezionato = PASSWORD_MAP[pwd]
                        st.session_state.utente_corrente = PASSWORD_MAP[pwd]
                        st.rerun()
                    elif pwd == PASSWORD_ADMIN:
                        st.session_state.ruolo_utente = "admin"
                        st.session_state.utente_corrente = "Amministrazione Generale"
                        st.rerun()
                    else: st.error("Codice di accesso non valido.")
else:
    # --- BARRA UTENTE DI LOGOUT ---
    col_t, col_b_logout = st.columns([4, 1])
    with col_t: st.markdown(f"Utente Connesso: **{st.session_state.utente_corrente.upper()}**")
    with col_b_logout:
        if st.button("🚪 Esci / Cambia Profilo", use_container_width=True):
            st.session_state.ruolo_utente = None
            st.session_state.magazzino_selezionato = None
            st.session_state.utente_corrente = ""
            st.rerun()
            
    st.image(URL_LOGO, use_container_width=True)

    # ==========================================
    # WORKFLOW A: INTERFACCIA COLLABORATORI (COMPLETAMENTE ISOLATA)
    # ==========================================
    if st.session_state.ruolo_utente == "collaboratore":
        st.markdown(f"### Benvenuto Area Risorse, {st.session_state.utente_corrente}")
        
        tipo_richiesta_utente = st.radio(
            "Seleziona la tipologia di richiesta da inoltrare:",
            ["📋 Richiesta Dispositivi in Comodato d'Uso (Docenti / Alunni)", "📦 Richiesta Materiali e Consumabili Standard (Personale ATA / Officina)"]
        )
        
        if tipo_richiesta_utente == "📋 Richiesta Dispositivi in Comodato d'Uso (Docenti / Alunni)":
            st.markdown("#### Compilazione Istanza Elettronica per l'Assegnazione di un Bene d'Istituto")
            with st.form("form_istanza_comodato"):
                t_sog = st.selectbox("Ruolo del Richiedente:", ["Insegnante / Personale Interno", "Alunno", "Genitore / Tutore Legale"])
                mail_sog = st.text_input("Indirizzo E-mail del Richiedente per comunicazioni interne:")
                cat_bene = st.selectbox("Categoria del Dispositivo:", ["PC Notebook", "Chiave d'Accesso"])
                mot_bene = st.text_area("Motivazione dettagliata a supporto della richiesta:")
                
                if st.form_submit_button("Invia Richiesta Formale per Approvazione", use_container_width=True):
                    if mail_sog.strip() and mot_bene.strip():
                        df_ist_c = scarica_da_sheet("Istanze_Comodati")
                        stamp = datetime.now().strftime("%d/%m/%Y %H:%M")
                        id_ist = f"IST-{datetime.now().strftime('%M%S')}"
                        token_sicurezza = f"TK-{base64.b64encode(id_ist.encode()).decode()[:10].upper()}"
                        
                        nuova_istanza = pd.DataFrame([{
                            "id_istanza": id_ist,
                            "timestamp": stamp,
                            "nominativo": st.session_state.utente_corrente,
                            "tipo_soggetto": t_sog,
                            "email": mail_sog.strip(),
                            "categoria_bene": cat_bene,
                            "motivazione": mot_bene.strip(),
                            "stato": "In attesa di Dirigente",
                            "token_approvazione": token_sicurezza
                        }])
                        carica_su_sheet(pd.concat([df_ist_c, nuova_istanza], ignore_index=True), "Istanze_Comodati")
                        
                        payload_notifica = {
                            "azione": "nuova_istanza",
                            "destinatario_approvazione": "marcobrunetti14@gmail.com",
                            "id_istanza": id_ist,
                            "richiedente": st.session_state.utente_corrente,
                            "ruolo": t_sog,
                            "email_richiedente": mail_sog.strip(),
                            "bene": cat_bene,
                            "motivazione": mot_bene.strip(),
                            "token": token_sicurezza
                        }
                        invia_notifica_silenziosa_gas(payload_notifica)
                        
                        st.success(f"Istanza {id_ist} registrata! Notifica inviata a marcobrunetti14@gmail.com.")
                        
                        # Fallback di emergenza visivo a schermo
                        st.markdown("---")
                        st.warning("⚠️ **INTERFACCIA DI SBLOCCO IMMEDIATO (Se non vuoi attendere la mail):**")
                        url_app = f"https://magazzinoscarpa.streamlit.app/?action=approva&token={token_sicurezza}"
                        url_ref = f"https://magazzinoscarpa.streamlit.app/?action=rifiuta&token={token_sicurezza}"
                        st.markdown(f"🔗 **[CLICCA QUI PER APPROVARE ADESSO]({url_app})**")
                        st.markdown(f"🔗 **[CLICCA QUI PER RIFIUTARE ADESSO]({url_ref})**")
                    else:
                        st.error("Tutti i campi del modulo sono obbligatori.")
                        
        else:
            st.markdown("#### Richiesta Fornitura Materiali Standard")
            with st.form("nuova_richiesta_standard"):
                mag_dest = st.selectbox("Seleziona il Magazzino di Destinazione:", ["Personale ATA", "Officina"])
                art_richiesto = st.text_input("Descrizione dell'articolo o materiale richiesto:")
                qta_richiesta = st.number_input("Quantità necessaria:", min_value=1, value=1, step=1)
                note_richiesta = st.text_area("Eventuali note o specifiche aggiuntive:")
                
                if st.form_submit_button("Invia Richiesta al Magazzino", use_container_width=True):
                    if art_richiesto.strip():
                        nome_scheda_corretta = MAPPA_SCHEDE[mag_dest]["richieste"]
                        df_dest = scarica_da_sheet(nome_scheda_corretta)
                        
                        nuovo_ticket = pd.DataFrame([{
                            "richiedente": st.session_state.utente_corrente,
                            "articolo": art_richiesto.strip(),
                            "quantita": str(qta_richiesta),
                            "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "stato": "In Lavorazione",
                            "note": note_richiesta.strip()
                        }])
                        carica_su_sheet(pd.concat([df_dest, nuovo_ticket], ignore_index=True), nome_scheda_corretta)
                        st.success(f"Richiesta salvata nel registro: {nome_scheda_corretta}!")
                    else:
                        st.error("Inserisci l'articolo prima di procedere.")

    # ==========================================
    # WORKFLOW B: AMMINISTRAZIONE GENERALE (ADMIN)
    # ==========================================
    elif st.session_state.ruolo_utente == "admin":
        tab_istanze, tab_comodati_reg, tab_giacenze_totali = st.tabs(["📩 ISTANZE COMODATI", "📜 REGISTRO ASSEGNAZIONI", "🏢 GIACENZE"])
        
        with tab_istanze:
            df_ist = scarica_da_sheet("Istanze_Comodati")
            filtro_attesa = df_ist[df_ist["stato"] == "In attesa di Dirigente"] if not df_ist.empty else pd.DataFrame()
            if filtro_attesa.empty: st.info("Nessuna richiesta in sospeso.")
            else:
                for idx, riga in filtro_attesa.iterrows():
                    with st.container(border=True):
                        st.markdown(f"👤 **{riga['nominativo']}** | Bene: **{riga['categoria_bene']}**")
                        if st.button("Forza Approvazione ✅", key=f"force_{idx}"):
                            df_ist.loc[idx, "stato"] = "Approvata da Dirigente"
                            carica_su_sheet(df_ist, "Istanze_Comodati")
                            st.rerun()
        with tab_comodati_reg:
            st.dataframe(scarica_da_sheet("Registro_Comodati"), use_container_width=True, hide_index=True)
        with tab_giacenze_totali:
            for m in LISTA_MAGAZZINI:
                st.markdown(f"#### 📦 {m}")
                st.dataframe(scarica_da_sheet(MAPPA_SCHEDE[m]["inventario"]), use_container_width=True, hide_index=True)

    # ==========================================
    # WORKFLOW C: TECNICI INFORMATICI
    # ==========================================
    elif st.session_state.ruolo_utente == "magazziniere" and st.session_state.magazzino_selezionato == "Tecnici Informatici":
        tab_ist, tab_cons, tab_ric, tab_inv, tab_reg = st.tabs(["📥 Istanze", "✍️ Consegna", "↩️ Riconsegne", "📋 Inventario", "📜 Registro"])
        
        df_istanze = scarica_da_sheet("Istanze_Comodati")
        df_inv_c = scarica_da_sheet("Inventario_Comodati")
        df_reg_c = scarica_da_sheet("Registro_Comodati")
        
        with tab_ist:
            ist_ok = df_istanze[df_istanze["stato"] == "Approvata da Dirigente"] if not df_istanze.empty else pd.DataFrame()
            st.dataframe(ist_ok, use_container_width=True, hide_index=True)
            
        with tab_cons:
            ist_pronte = df_istanze[df_istanze["stato"] == "Approvata da Dirigente"]["nominativo"].tolist() if not df_istanze.empty else []
            if not ist_pronte: st.warning("Nessuna richiesta approvata.")
            else:
                with st.form("p_consegna"):
                    sog_sel = st.selectbox("Assegnatario:", ist_pronte)
                    riga = df_istanze[df_istanze["nominativo"] == sog_sel].iloc[0]
                    beni_disp = df_inv_c[df_inv_c["stato"] == "Disponibile"]["id_bene"].tolist() if not df_inv_c.empty else []
                    bene_sel = st.selectbox("Seriale:", beni_disp if beni_disp else ["Nessuno"])
                    st.components.v1.html(rendering_pad_firma_html("canvas_c"), height=260)
                    cod_f = st.text_area("Incolla codice firma:")
                    if st.form_submit_button("Emetti"):
                        if cod_f.strip() and bene_sel != "Nessuno":
                            next_id = int(df_reg_c["id_comodato"].astype(float).max()) + 1 if not df_reg_c.empty else 5001
                            ora = datetime.now().strftime("%d/%m/%Y %H:%M")
                            pdf = genera_pdf_comodato(next_id, riga['nominativo'], riga['tipo_soggetto'], bene_sel, ora, "CONSEGNA", cod_f.strip(), st.session_state.utente_corrente)
                            if carica_su_drive_unico(pdf, f"Consegna_{next_id}.pdf", "application/pdf", "Comodati_Consegne"):
                                df_istanze.loc[df_istanze["id_istanza"] == riga["id_istanza"], "stato"] = "Evasa"
                                carica_su_sheet(df_istanze, "Istanze_Comodati")
                                n_c = pd.DataFrame([{"id_comodato": next_id, "tipo_soggetto": riga['tipo_soggetto'], "nominativo": riga['nominativo'], "id_bene": bene_sel, "data_consegna": ora, "stato_comodato": "In Corso"}])
                                carica_su_sheet(pd.concat([df_reg_c, n_c], ignore_index=True), "Registro_Comodati")
                                df_inv_c.loc[df_inv_c["id_bene"] == bene_sel, "stato"] = "Assegnato"
                                carica_su_sheet(df_inv_c, "Inventario_Comodati")
                                st.success("Evaso!")
                                st.rerun()
        with tab_ric:
            c_attivi = df_reg_c[df_reg_c["stato_comodato"] == "In Corso"] if not df_reg_c.empty else pd.DataFrame()
            if c_attivi.empty: st.info("Nessun contratto attivo.")
            else:
                for idx, r in c_attivi.iterrows():
                    with st.container(border=True):
                        st.markdown(f"📋 Contratto: {r['id_comodato']} - {r['nominativo']}")
                        if st.button("Scarica Restituzione", key=f"ric_{idx}"):
                            df_reg_c.loc[idx, "stato_comodato"] = "Riconsegnato"
                            carica_su_sheet(df_reg_c, "Registro_Comodati")
                            df_inv_c.loc[df_inv_c["id_bene"] == r["id_bene"], "stato"] = "Disponibile"
                            carica_su_sheet(df_inv_c, "Inventario_Comodati")
                            st.success("Riconsegnato!")
                            st.rerun()
        with tab_inv: st.dataframe(df_inv_c, use_container_width=True, hide_index=True)
        with tab_reg: st.dataframe(df_reg_c, use_container_width=True, hide_index=True)

    # ==========================================
    # WORKFLOW D: MAGAZZINI STANDARD (ATA / OFFICINA)
    # ==========================================
    elif st.session_state.ruolo_utente == "magazziniere":
        st.markdown(f"## 📦 Magazzino: {st.session_state.magazzino_selezionato}")
        df_inv = scarica_da_sheet(MAPPA_SCHEDE[st.session_state.magazzino_selezionato]["inventario"])
        df_req = scarica_da_sheet(MAPPA_SCHEDE[st.session_state.magazzino_selezionato]["richieste"])
        
        t_inv, t_req = st.tabs(["Giacenze", "Ordini"])
        with t_inv:
            st.dataframe(df_inv, use_container_width=True, hide_index=True)
        with t_req:
            attesa = df_req[df_req["stato"] == "In Lavorazione"] if not df_req.empty else pd.DataFrame()
            if attesa.empty: st.info("Nessun ordine.")
            else:
                for idx, riga in attesa.iterrows():
                    with st.container(border=True):
                        st.markdown(f"👤 {riga['richiedente']} -> {riga['articolo']} x{riga['quantita']}")
                        if st.button("Evadi ✅", key=f"ev_{idx}"):
                            df_req.loc[idx, "stato"] = "Evaso"
                            carica_su_sheet(df_req, MAPPA_SCHEDE[st.session_state.magazzino_selezionato]["richieste"])
                            st.rerun()
