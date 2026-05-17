import streamlit as st
import pandas as pd
from datetime import datetime
import io
import base64
from PIL import Image

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

# Libreria per la generazione di PDF
try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False

# Configurazione iniziale di pagina
st.set_page_config(page_title="Gestione Magazzini Scarpa", page_icon="🏢", layout="wide")

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
        return pd.DataFrame(worksheet.get_all_records())
    except gspread.exceptions.WorksheetNotFound:
        if "Inventario_Comodati" in nome_scheda:
            df_base = pd.DataFrame(columns=["id_bene", "tipo_bene", "descrizione", "stato"])
        elif "Registro_Comodati" in nome_scheda:
            df_base = pd.DataFrame(columns=["id_comodato", "tipo_soggetto", "nominativo", "id_bene", "data_consegna", "stato_comodato"])
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


# --- CLASSE PDF SINGOLA PAGINA ---
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


def genera_pdf_comodato(id_contratto, nome, ruolo, bene, data, tipo_operazione, firma_base64=None, utente_loggato="Ufficio Tecnico", dicitura_firma_dx="Firma del Richiedente:"):
    if not FPDF_AVAILABLE:
        return b"Errore libreria PDF"
    
    pdf = PDFMinisteriale(orientation='P', unit='mm', format='A4')
    pdf.set_margins(15, 12, 15)
    pdf.set_auto_page_break(auto=True, margin=25) 
    pdf.add_page()
    
    # 1. Intestazione
    try:
        pdf.image(URL_LOGO, x=15, y=10, w=180)
        pdf.ln(18)
    except Exception:
        pdf.set_font("Times", "B", 13)
        pdf.cell(180, 6, "ISISS ANTONIO SCARPA", ln=True, align="C")
        pdf.ln(8)
        
    # 2. Protocollo e Data
    pdf.set_font("Times", "", 10)
    data_corrente = data.split(" ")[0] if " " in data else data
    
    pdf.cell(90, 5, "Protocollo n. (vedi segnatura)", ln=False, align="L")
    pdf.cell(90, 5, f"Motta di Livenza, {data_corrente}", ln=True, align="R")
    pdf.ln(3)
    
    # 3. Destinatario
    pdf.set_font("Times", "B", 10)
    pdf.cell(95, 5, "", ln=False)
    pdf.cell(85, 5, "Ai Docenti / Al Personale Interessato", ln=True, align="L")
    pdf.cell(95, 5, "", ln=False)
    pdf.cell(85, 5, f"Sig./Sigg. {nome} ({ruolo})", ln=True, align="L")
    pdf.ln(6)
    
    # 4. Oggetto
    pdf.set_font("Times", "B", 10)
    pdf.cell(22, 5, "OGGETTO: ", ln=False)
    pdf.set_font("Times", "", 10)
    
    if tipo_operazione == "CONSEGNA":
        testo_oggetto = f"Verbale di Consegna e Assegnazione in Comodato d'Uso Gratuito dei Beni d'Istituto - Registro ID {id_contratto}."
    else:
        testo_oggetto = f"Ricevuta di Riconsegna, Scarico Logistico e Cessazione Comodato d'Uso - Registro ID {id_contratto}."
    pdf.multi_cell(158, 5, testo_oggetto)
    pdf.ln(4)
    
    # 5. Corpo
    pdf.set_font("Times", "", 10)
    if tipo_operazione == "CONSEGNA":
        corpo_testo = (
            f"Con la presente si attesta che in data odierna l'Amministrazione dell'Istituto Superiore "
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
        
    pdf.multi_cell(180, 5.5, corpo_testo, align="J")
    pdf.ln(8)
    
    # 6. Blocco Firme
    pdf.set_font("Times", "B", 10)
    y_posizione_firme = pdf.get_y()
    
    pdf.cell(100, 5, "Per l'Amministrazione:", align="L")
    pdf.cell(80, 5, dicitura_firma_dx, align="L", ln=True)
    
    pdf.set_font("Times", "I", 9)
    pdf.cell(100, 5, "RESP. Ufficio Tecnico", align="L")
    
    if firma_base64 and len(firma_base64) > 100:
        try:
            dati_f = firma_base64.split(",")[1] if "," in firma_base64 else firma_base64
            img_data = base64.b64decode(dati_f)
            img_originale = Image.open(io.BytesIO(img_data))
            
            sfondo_bianco = Image.new("RGBA", img_originale.size, "WHITE")
            sfondo_bianco.paste(img_originale, (0, 0), img_originale)
            
            img_buffer = io.BytesIO()
            sfondo_bianco.convert("RGB").save(img_buffer, format="JPEG", quality=90)
            img_buffer.seek(0)
            
            pdf.image(img_buffer, x=115, y=y_posizione_firme + 5, w=42, h=11)
        except Exception:
            pdf.cell(80, 5, "[Firma Acquisita digitalmente]", align="L", ln=True)
    else:
        pdf.cell(80, 5, "____________________________", align="L", ln=True)

    return pdf.output()


# --- COMPONENTE INTERATTIVO DI FIRMA DIRETTI SENZA COPIA-INCOLLA ---
def renderizza_pad_firma(chiave_univoca):
    html_pad_firma = f"""
    <div style="background: #f8fafc; border: 2px dashed #cbd5e1; padding: 12px; border-radius: 12px; max-width:490px; font-family: sans-serif;">
        <canvas id="canvas_{chiave_univoca}" width="460" height="120" style="border:2px solid #64748b; background:#ffffff; cursor:crosshair; touch-action: none; border-radius:8px;"></canvas>
        <div style="margin-top:8px; display:flex; gap:10px;">
            <button type="button" onclick="pulisci_{chiave_univoca}()" style="padding:6px 12px; background:#ef4444; color:white; border:none; border-radius:6px; cursor:pointer; font-weight:bold; font-size:12px;">Cancella</button>
            <button type="button" onclick="salva_{chiave_univoca}()" style="padding:6px 12px; background:#22c55e; color:white; border:none; border-radius:6px; cursor:pointer; font-weight:bold; font-size:12px;">Conferma e Collega Firma</button>
        </div>
    </div>

    <script>
        var canvas = document.getElementById('canvas_{chiave_univoca}');
        var ctx = canvas.getContext('2d');
        ctx.strokeStyle = '#000000';
        ctx.lineWidth = 3;
        ctx.lineCap = 'round';
        var isDrawing = false;

        function getCoordinate(e) {
            var rect = canvas.getBoundingClientRect();
            if(e.touches && e.touches.length > 0) {{
                return {{ x: e.touches[0].clientX - rect.left, y: e.touches[0].clientY - rect.top }};
            }}
            return {{ x: e.clientX - rect.left, y: e.clientY - rect.top }};
        }

        canvas.addEventListener('mousedown', function(e) {{ isDrawing = true; var p = getCoordinate(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); }});
        canvas.addEventListener('mousemove', function(e) {{ if(!isDrawing) return; var p = getCoordinate(e); ctx.lineTo(p.x, p.y); ctx.stroke(); }});
        canvas.addEventListener('mouseup', function() {{ isDrawing = false; }});

        canvas.addEventListener('touchstart', function(e) {{ isDrawing = true; var p = getCoordinate(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); e.preventDefault(); }}, {{passive: false}});
        canvas.addEventListener('touchmove', function(e) {{ if(!isDrawing) return; var p = getCoordinate(e); ctx.lineTo(p.x, p.y); ctx.stroke(); e.preventDefault(); }}, {{passive: false}});
        canvas.addEventListener('touchend', function() {{ isDrawing = false; }});

        function pulisci_{chiave_univoca}() {{ 
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            window.parent.postMessage({{type: 'streamlit:setComponentValue', value: ''}}, '*');
        }}

        function salva_{chiave_univoca}() {{
            var dataUrl = canvas.toDataURL('image/png');
            // Iniezione diretta globale del valore in Streamlit bypassando le caselle di testo esterne
            const campi = window.parent.document.querySelectorAll('textarea');
            campi.forEach(el => {{
                if(el.ariaLabel && el.ariaLabel.includes('{chiave_univoca}')) {{
                    el.value = dataUrl;
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }}
            }});
            alert("Firma agganciata con successo alla pratica!");
        }}
    </script>
    """
    return st.components.v1.html(html_pad_firma, height=180)


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


if "ruolo_utente" not in st.session_state: st.session_state.ruolo_utente = None
if "utente_corrente" not in st.session_state: st.session_state.utente_corrente = ""
if "magazzino_selezionato" not in st.session_state: st.session_state.magazzino_selezionato = None

if st.session_state.ruolo_utente is None:
    col_l, col_c, col_r = st.columns([1, 1.8, 1])
    with col_c:
        st.image(URL_LOGO, use_container_width=True)
        st.markdown("<h2 style='text-align: center;'>Piattaforma Logistica di Istituto</h2>", unsafe_allow_html=True)
        with st.container(border=True):
            scelta = st.radio("Seleziona profilo:", ["Collaboratore (Richiesta Materiale)", "Staff Magazzino / Amministrazione"])
            if scelta == "Collaboratore (Richiesta Materiale)":
                nome = st.text_input("Nome e Cognome:")
                if st.button("Accedi", type="primary", use_container_width=True):
                    if nome.strip():
                        st.session_state.ruolo_utente = "collaboratore"
                        st.session_state.utente_corrente = nome.strip()
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
                        st.session_state.ruolo_utente = "admin"
                        st.session_state.utente_corrente = "admin"
                        st.rerun()
                    else: st.error("Codice non valido.")
else:
    col_t, col_b_logout = st.columns([4, 1])
    with col_t: st.markdown(f"Accesso: **{st.session_state.utente_corrente.upper()}**")
    with col_b_logout:
        if st.button("🚪 Cambia Profilo", use_container_width=True):
            st.session_state.ruolo_utente = None
            st.rerun()
            
    st.image(URL_LOGO, use_container_width=True)

    if st.session_state.ruolo_utente == "admin":
        tab_magazzini, tab_comodati = st.tabs(["📊 MAGAZZINI LOGISTICI", "✍️ GESTIONE COMODATI (PC & CHIAVI)"])
        
        with tab_magazzini:
            mag_sel = st.selectbox("Seleziona Magazzino:", LISTA_MAGAZZINI)
            st.dataframe(scarica_da_sheet(MAPPA_SCHEDE[mag_sel]["inventario"]), use_container_width=True, hide_index=True)
            
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
                st.markdown("### Nuovo Accordo di Comodato")
                if df_inv_comodati.empty or not (df_inv_comodati["stato"] == "Disponibile").any():
                    st.warning("Nessun bene disponibile al momento.")
                else:
                    col_n1, col_n2 = st.columns(2)
                    with col_n1:
                        tipo_sog = st.selectbox("Profilo Richiedente:", ["Alunno", "Genitore / Tutore", "Insegnante / Personale"])
                        nom_sog = st.text_input("Nome e Cognome dell'Assegnatario:")
                    with col_n2:
                        disp = df_inv_comodati[df_inv_comodati["stato"] == "Disponibile"]["id_bene"].tolist()
                        bene_sel = st.selectbox("Seleziona l'oggetto da consegnare:", disp)
                        
                    st.markdown("#### 🖊️ Firma Consegna Richiedente:")
                    renderizza_pad_firma("FirmaConsegna")
                    codice_firma_consegna = st.text_area("Buffer Dati (FirmaConsegna)", label_visibility="collapsed", key="txt_FirmaConsegna")

                    if st.button("🚀 Approva e Genera Verbale di Consegna", type="primary", use_container_width=True):
                        nome_pulito = nom_sog.strip()
                        if not nome_pulito: st.error("Inserisci il Nome.")
                        elif not codice_firma_consegna: st.error("Inserisci la firma sul riquadro e premi 'Conferma'.")
                        else:
                            with st.spinner("Generazione..."):
                                id_com = int(df_reg_comodati["id_comodato"].astype(float).max()) + 1 if not df_reg_comodati.empty else 1001
                                data_ora = datetime.now().strftime("%d/%m/%Y %H:%M")
                                pdf_bytes = genera_pdf_comodato(id_com, nome_pulito, tipo_sog, bene_sel, data_ora, "CONSEGNA", codice_firma_consegna, st.session_state.utente_corrente, "Firma del Richiedente:")
                                if carica_su_drive_unico(pdf_bytes, f"Verbale_Consegna_{id_com}.pdf", "application/pdf", "Comodati_Consegne"):
                                    nuva_r = pd.DataFrame([{"id_comodato": id_com, "tipo_soggetto": tipo_sog, "nominativo": nome_pulito, "id_bene": bene_sel, "data_consegna": data_ora, "stato_comodato": "In Corso"}])
                                    df_reg_comodati = pd.concat([df_reg_comodati, nuva_r], ignore_index=True)
                                    carica_su_sheet(df_reg_comodati, "Registro_Comodati")
                                    df_inv_comodati.loc[df_inv_comodati["id_bene"] == bene_sel, "stato"] = "Assegnato"
                                    carica_su_sheet(df_inv_comodati, "Inventario_Comodati")
                                    st.success("Registrato!")
                                    st.rerun()

            with sub_registro:
                st.markdown("### Registro Contratti Attivi")
                attivi = df_reg_comodati[df_reg_comodati["stato_comodato"] == "In Corso"] if not df_reg_comodati.empty else pd.DataFrame()
                if attivi.empty: st.info("Nessun comodato attivo.")
                else:
                    for id_x, riga in attivi.iterrows():
                        with st.container(border=True):
                            c1, c2 = st.columns([2.5, 1.5])
                            with c1:
                                st.markdown(f"📦 Oggetto: **{riga['id_bene']}** - Affidato a: **{riga['nominativo']}**")
                                st.caption(f"Assegnato il: {riga['data_consegna']} | ID Contratto: {riga['id_comodato']}")
                            with c2:
                                with st.expander("Effettua Riconsegna ↩"):
                                    senza_utente = st.checkbox("Riconsegna pervenuta senza richiedente fisicamente presente", key=f"chk_no_ut_{riga['id_comodato']}")
                                    dicitura_label = "Firma del Responsabile di Magazzino:" if senza_utente else "Firma di chi riconsegna il bene:"
                                    
                                    st.caption(dicitura_label)
                                    renderizza_pad_firma(f"FirmaRiconsegna_{riga['id_comodato']}")
                                    codice_firma_ric = st.text_area(f"Buffer (FirmaRiconsegna_{riga['id_comodato']})", label_visibility="collapsed")
                                    
                                    if st.button("Conferma Riconsegna", key=f"btn_ric_{riga['id_comodato']}", type="primary", use_container_width=True):
                                        if not codice_firma_ric:
                                            st.error("Firma obbligatoria per chiudere la pratica.")
                                        else:
                                            data_rientro = datetime.now().strftime("%d/%m/%Y %H:%M")
                                            pdf_r_bytes = genera_pdf_comodato(riga['id_comodato'], riga['nominativo'], riga['tipo_soggetto'], riga['id_bene'], data_rientro, "RICONSEGNA", codice_firma_ric, st.session_state.utente_corrente, dicitura_label)
                                            carica_su_drive_unico(pdf_r_bytes, f"Ricevuta_Riconsegna_{riga['id_comodato']}.pdf", "application/pdf", "Comodati_Riconsegne")
                                            
                                            df_reg_comodati.loc[df_reg_comodati["id_comodato"].astype(str) == str(riga["id_comodato"]), "stato_comodato"] = f"Riconsegnato il {data_rientro}"
                                            carica_su_sheet(df_reg_comodati, "Registro_Comodati")
                                            
                                            df_inv_comodati.loc[df_inv_comodati["id_bene"] == riga["id_bene"], "stato"] = "Disponibile"
                                            carica_su_sheet(df_inv_comodati, "Inventario_Comodati")
                                            st.rerun()

    elif st.session_state.ruolo_utente == "collaboratore":
        st.markdown("### Nuova Richiesta Materiali")
        st.info("Area Richieste allineata ed attiva.")
