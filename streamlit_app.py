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

# --- CONFIGURAZIONE INTERMEDIARIO (GOOGLE APPS SCRIPT) ---\nURL_INTERMEDIARIO_SILENZIOSO = "https://script.google.com/macros/s/AKfycbyXBLjDpJrSGHoUpuspTsNAG9f6lGhF1e8oGyJ8nkY6jZMTJo04zsT_6eLyEybGgv4/exec"

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
    pdf.cell(95, 5, "")
    pdf.cell(85, 5, "Ai Docenti / Al Personale Interessato", ln=True, align="L")
    pdf.cell(95, 5, "")
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
            f"Con la presente si attesta che in data odierna l'Amministrazione dell'Istituto Superiorer\n"
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

# --- COMPONENTE HTML PAD FIRMA CON COPIA AUTOMATICA ---
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

# --- INIZIALIZZAZIONE DELLO STATO DELLA SESSIONE ---
if "ruolo_utente" not in st.session_state: st.session_state.ruolo_utente = None
if "utente_corrente" not in st.session_state: st.session_state.utente_corrente = ""
if "magazzino_selezionato" not in st.session_state: st.session_state.magazzino_selezionato = None

# --- STRUTTURA LOG PARAMS / APPROVAZIONI RAPIDE DIRIGENTE ---
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
            st.success(f"Operazione completata con successo: Richiesta impostata su '{nuovo_st}'. Puoi chiudere questa scheda.")
        else: st.warning(f"Questa istanza è già stata gestita. Stato attuale: {stato_attuale}")
    else: st.error("Token di autorizzazione non valido o scaduto.")
    st.stop()

# --- BLOCCO ROUTER DI AUTENTICAZIONE ---
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
    col_t, col_b_logout = st.columns([4, 1])
    with col_t: st.markdown(f"Utente Connesso: **{st.session_state.utente_corrente.upper()}**")
    with col_b_logout:
        if st.button("🚪 Esci / Cambia Profilo", use_container_width=True):
            st.session_state.ruolo_utente = None
            st.session_state.magazzino_selezionato = None
            st.rerun()
            
    st.image(URL_LOGO, use_container_width=True)

    # ==========================================
    # WORKFLOW 1: AMMINISTRAZIONE GENERALE (ADMIN)
    # ==========================================
    if st.session_state.ruolo_utente == "admin":
        tab_istanze, tab_comodati_reg, tab_giacenze_totali = st.tabs(["📩 ISTANZE COMODATI (DA VALUTARE)", "📜 REGISTRO ASSEGNAZIONI", "🏢 GIACENZE TUTTI I LABORATORI"])
        
        with tab_istanze:
            st.markdown("### Richieste di Comodato d'Uso in Attesa di Validazione")
            df_ist = scarica_da_sheet("Istanze_Comodati")
            filtro_attesa = df_ist[df_ist["stato"] == "In attesa di Dirigente"] if not df_ist.empty else pd.DataFrame()
            
            if filtro_attesa.empty: st.info("Nessuna richiesta in sospeso.")
            else:
                for idx, riga in filtro_attesa.iterrows():
                    with st.container(border=True):
                        c1, c2 = st.columns([3, 1])
                        with c1:
                            st.markdown(f"👤 Soggetto: **{riga['nominativo']}** ({riga['tipo_soggetto']}) — Email: {riga['email']}")
                            st.markdown(f"📦 Bene Richiesto: **{riga['categoria_bene']}** | *Motivazione:* {riga['motivazione']}")
                        with c2:
                            if st.button("Forza Approvazione Amministrativa ✅", key=f"force_app_{idx}"):
                                df_ist.loc[idx, "stato"] = "Approvata da Dirigente"
                                carica_su_sheet(df_ist, "Istanze_Comodati")
                                st.success("Istanza approvata d'ufficio!")
                                st.rerun()
                                
        with tab_comodati_reg:
            st.markdown("### Storico Totale delle Pratiche e Assegnazioni")
            st.dataframe(scarica_da_sheet("Registro_Comodati"), use_container_width=True, hide_index=True)
            
        with tab_giacenze_totali:
            st.markdown("### 📊 Riepilogo Consistenze e Giacenze di Tutti i Magazzini")
            for mag_scuola in LISTA_MAGAZZINI:
                st.markdown(f"#### 📦 Inventario {mag_scuola}")
                df_giac = scarica_da_sheet(MAPPA_SCHEDE[mag_scuola]["inventario"])
                if df_giac.empty:
                    st.caption("Nessun dato registrato in questo magazzino.")
                else:
                    st.dataframe(df_giac, use_container_width=True, hide_index=True)

    # ==========================================
    # WORKFLOW 2: TECNICI INFORMATICI (COMODATI & RICHIEDENTI)
    # ==========================================
    elif st.session_state.ruolo_utente == "magazziniere" and st.session_state.magazzino_selezionato == "Tecnici Informatici":
        st.markdown("## 💻 Console Gestione Comodati d'Uso ed Approvazioni")
        
        tab_istanze_t, tab_consegna_pratica, tab_riconsegna, tab_tutti_comodati, tab_registro_completo = st.tabs([
            "📥 Istanze Validate", "✍️ Nuova Consegna / Firma", "↩️ Gestione Riconsegne", "📋 Inventario Beni", "📜 Registro Contratti"
        ])
        
        df_istanze = scarica_da_sheet("Istanze_Comodati")
        df_inv_c = scarica_da_sheet("Inventario_Comodati")
        df_reg_c = scarica_da_sheet("Registro_Comodati")
        
        with tab_istanze_t:
            st.markdown("### Richieste che hanno ottenuto il via libera formale")
            ist_ok = df_istanze[df_istanze["stato"] == "Approvata da Dirigente"] if not df_istanze.empty else pd.DataFrame()
            if ist_ok.empty: st.info("Nessuna istanza validata pronta per il rilascio.")
            else: st.dataframe(ist_ok, use_container_width=True, hide_index=True)
            
        with tab_consegna_pratica:
            st.markdown("### Compilazione Verbale di Consegna e Acquisizione Firma")
            ist_pronte = df_istanze[df_istanze["stato"] == "Approvata da Dirigente"]["nominativo"].tolist() if not df_istanze.empty else []
            
            if not ist_pronte: st.warning("Nessun utente ha una richiesta attiva e approvata.")
            else:
                with st.form("procedura_consegna"):
                    sog_sel = st.selectbox("Seleziona l'assegnatario:", ist_pronte)
                    riga = df_istanze[df_istanze["nominativo"] == sog_sel].iloc[0]
                    
                    beni_disponibili = df_inv_c[df_inv_c["stato"] == "Disponibile"]["id_bene"].tolist() if not df_inv_c.empty else []
                    bene_assegnato = st.selectbox("Associa il codice seriale del bene:", beni_disponibili if beni_disponibili else ["Nessun bene disponibile a magazzino"])
                    
                    st.markdown("#### 🖊️ Firma Digitale dell'Assegnatario:")
                    st.components.v1.html(rendering_pad_firma_html("canvas_consegna"), height=260)
                    
                    codice_incollato = st.text_area("Incolla qui il codice di firma generato sopra per validare:", key="stringa_firma_consegna")
                    
                    if st.form_submit_button("Emetti e Archivia Contratto", use_container_width=True):
                        if codice_incollato.strip() and bene_assegnato != "Nessun bene disponibile a magazzino":
                            with st.spinner("Generazione Verbale in corso..."):
                                next_id = int(df_reg_c["id_comodato"].astype(float).max()) + 1 if not df_reg_c.empty else 5001
                                ora_c = datetime.now().strftime("%d/%m/%Y %H:%M")
                                
                                pdf_bytes = genera_pdf_comodato(next_id, riga['nominativo'], riga['tipo_soggetto'], bene_assegnato, ora_c, "CONSEGNA", codice_incollato.strip(), st.session_state.utente_corrente)
                                
                                if carica_su_drive_unico(pdf_bytes, f"Verbale_Consegna_{next_id}.pdf", "application/pdf", "Comodati_Consegne"):
                                    df_istanze.loc[df_istanze["id_istanza"] == riga["id_istanza"], "stato"] = "Evasa (Materiale Consegnato)"
                                    carica_su_sheet(df_istanze, "Istanze_Comodati")
                                    
                                    nuovo_c = pd.DataFrame([{"id_comodato": next_id, "tipo_soggetto": riga['tipo_soggetto'], "nominativo": riga['nominativo'], "id_bene": bene_assegnato, "data_consegna": ora_c, "stato_comodato": "In Corso"}])
                                    carica_su_sheet(pd.concat([df_reg_c, nuovo_c], ignore_index=True), "Registro_Comodati")
                                    
                                    if riga['categoria_bene'] in ["PC Notebook", "Chiave d'Accesso"]:
                                        df_inv_c.loc[df_inv_c["id_bene"] == bene_assegnato, "stato"] = "Assegnato"
                                        carica_su_sheet(df_inv_c, "Inventario_Comodati")
                                        
                                    st.success("Pratica Evasa! Verbale ufficiale registrato e caricato.")
                                    st.rerun()
                        else: st.error("Firma o identificativo bene mancante.")
                        
        with tab_riconsegna:
            st.markdown("### Chiusura Contratto per Restituzione Dispositivo")
            contratti_attivi = df_reg_c[df_reg_c["stato_comodato"] == "In Corso"] if not df_reg_c.empty else pd.DataFrame()
            
            if contratti_attivi.empty:
                st.info("Al momento non risultano contratti in corso nel registro.")
            else:
                for idx, riga_reg in contratti_attivi.iterrows():
                    with st.container(border=True):
                        c_inf, c_azione = st.columns([3, 1])
                        with c_inf:
                            st.markdown(f"📋 Contratto ID: **{riga_reg['id_comodato']}** | Oggetto seriale: **{riga_reg['id_bene']}**")
                            st.markdown(f"👤 Affidato a: **{riga_reg['nominativo']}** ({riga_reg['tipo_soggetto']}) | Data inizio: {riga_reg['data_consegna']}")
                        with c_azione:
                            with st.expander("Procedi allo scarico restituzione ↩"):
                                st.markdown("#### 🖊️ Firma del Riconsegnante:")
                                st.components.v1.html(rendering_pad_firma_html(f"canvas_ric_{riga_reg['id_comodato']}"), height=260)
                                
                                firma_ric_incollata = st.text_area("Incolla qui il codice firma generato:", key=f"firma_ric_{riga_reg['id_comodato']}")
                                
                                if st.button("Registra Rientro ed Emetti Ricevuta", key=f"btn_ric_{riga_reg['id_comodato']}", type="primary", use_container_width=True):
                                    if not firma_ric_incollata.strip():
                                        st.error("Inserisci la firma per completare lo scarico logistico.")
                                    else:
                                        with st.spinner("Archiviazione rientro dispositivo..."):
                                            ora_rientro = datetime.now().strftime("%d/%m/%Y %H:%M")
                                            pdf_rientro_bytes = genera_pdf_comodato(riga_reg['id_comodato'], riga_reg['nominativo'], riga_reg['tipo_soggetto'], riga_reg['id_bene'], ora_rientro, "RICONSEGNA", firma_ric_incollata.strip(), st.session_state.utente_corrente)
                                            
                                            if carica_su_drive_unico(pdf_rientro_bytes, f"Ricevuta_Riconsegna_{riga_reg['id_comodato']}.pdf", "application/pdf", "Comodati_Riconsegne"):
                                                df_reg_c.loc[idx, "stato_comodato"] = f"Riconsegnato il {ora_rientro}"
                                                carica_su_sheet(df_reg_c, "Registro_Comodati")
                                                
                                                df_inv_c.loc[df_inv_c["id_bene"] == riga_reg["id_bene"], "stato"] = "Disponibile"
                                                carica_su_sheet(df_inv_c, "Inventario_Comodati")
                                                
                                                st.success("Bene rientrato e rimesso in disponibilità!")
                                                st.rerun()
                                            else:
                                                st.error("Impossibile salvare il documento su Google Drive.")
                                                
        with tab_tutti_comodati:
            st.dataframe(df_inv_c, use_container_width=True, hide_index=True)
        with tab_registro_completo:
            st.dataframe(df_reg_c, use_container_width=True, hide_index=True)

    # ==========================================
    # WORKFLOW 3: ALTRI MAGAZZINI (ATA O STANDARD)
    # ==========================================
    elif st.session_state.ruolo_utente == "magazziniere":
        st.markdown(f"## 📦 Magazzino Standard: {st.session_state.magazzino_selezionato}")
        
        df_inv = scarica_da_sheet(MAPPA_SCHEDE[st.session_state.magazzino_selezionato]["inventario"])
        df_req = scarica_da_sheet(MAPPA_SCHEDE[st.session_state.magazzino_selezionato]["richieste"])
        
        tab_inv_s, tab_richieste_s = st.tabs(["📦 Stato Inventario", "⏳ Gestione Ordini Richieste"])
        
        with tab_inv_s:
            st.dataframe(df_inv, use_container_width=True, hide_index=True)
            with st.expander("Modifica / Incrementa Giacenza Magazzino"):
                with st.form("form_inventario_standard"):
                    id_a = st.text_input("Codice Identificativo Articolo:")
                    nom_a = st.text_input("Nome o descrizione dell'elemento:")
                    qta_a = st.number_input("Nuovo Livello Giacenza:", min_value=0, step=1)
                    if st.form_submit_button("Sincronizza Inventario"):
                        if id_a.strip() and nom_a.strip():
                            if not df_inv.empty and id_a.strip() in df_inv['id'].astype(str).values:
                                df_inv.loc[df_inv['id'].astype(str) == id_a.strip(), 'elemento'] = nom_a.strip()
                                df_inv.loc[df_inv['id'].astype(str) == id_a.strip(), 'valore'] = str(qta_a)
                            else:
                                df_inv = pd.concat([df_inv, pd.DataFrame([{"id": id_a.strip(), "elemento": nom_a.strip(), "valore": str(qta_a)}])], ignore_index=True)
                            carica_su_sheet(df_inv, MAPPA_SCHEDE[st.session_state.magazzino_selezionato]["inventario"])
                            st.success("Modifiche salvate con successo.")
                            st.rerun()
                            
        with tab_richieste_s:
            in_lavorazione = df_req[df_req["stato"] == "In Lavorazione"] if not df_req.empty else pd.DataFrame()
            if in_lavorazione.empty: st.info("Nessun ordine in attesa di prelievo logistico.")
            else:
                for idx, riga in in_lavorazione.iterrows():
                    with st.container(border=True):
                        col_i, col_p = st.columns([3, 1])
                        with col_i:
                            st.markdown(f"👤 Richiedente: **{riga['richiedente']}** | Richiesto: **{riga['articolo']}** x{riga['quantita']}")
                            st.caption(f"Inviato il: {riga['data']} | Note aggiuntive: {riga.get('note','')}")
                        with col_p:
                            if st.button("Segna come Evaso / Consegnato ✅", key=f"evadi_{idx}"):
                                df_req.loc[idx, "stato"] = "Evaso"
                                carica_su_sheet(df_req, MAPPA_SCHEDE[st.session_state.magazzino_selezionato]["richieste"])
                                st.success("Ordine contrassegnato come evaso.")
                                st.rerun()

    # ==========================================
    # WORKFLOW 4: INTERFACCIA COLLABORATORI (INSERIMENTO TICKET RICHIESTE)
    # ==========================================
    elif st.session_state.ruolo_utente == "collaboratore":
        st.markdown(f"### Benvenuto {st.session_state.utente_corrente}")
        st.markdown("Invia una nuova richiesta di prelievo o materiale ai diversi reparti logistici della scuola.")
        
        with st.form("nuova_richiesta_collab"):
            mag_dest = st.selectbox("Seleziona il Magazzino di Destinazione:", LISTA_MAGAZZINI)
            art_richiesto = st.text_input("Descrizione dell'articolo o materiale richiesto:")
            qta_richiesta = st.number_input("Quantità necessaria:", min_value=1, value=1, step=1)
            note_richiesta = st.text_area("Eventuali note o specifiche aggiuntive:")
            
            if st.form_submit_button("Invia Richiesta al Magazzino", use_container_width=True):
                if art_richiesto.strip():
                    df_dest = scarica_da_sheet(MAPPA_SCHEDE[mag_dest]["richieste"])
                    nuovo_ticket = pd.DataFrame([{
                        "richiedente": st.session_state.utente_corrente,
                        "articolo": art_richiesto.strip(),
                        "quantita": str(qta_richiesta),
                        "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "stato": "In Lavorazione",
                        "note": note_richiesta.strip()
                    }])
                    df_dest = pd.concat([df_dest, nuovo_ticket], ignore_index=True)
                    carica_su_sheet(df_dest, MAPPA_SCHEDE[mag_dest]["richieste"])
                    st.success(f"Ticket inviato con successo al reparto {mag_dest}!")
                else:
                    st.error("Inserisci l'articolo prima di inviare.")
