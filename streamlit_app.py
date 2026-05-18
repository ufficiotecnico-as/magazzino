import streamlit as st
import pandas as pd
from datetime import datetime
import io
import base64
import json
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- IMPORTAZIONE MODULO ESTERNO PREVENTIVI ---
import gestione_preventivi

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Gestione Magazzini Scarpa", page_icon="🏢", layout="wide")

# --- CONFIGURAZIONI SISTEMA ---
URL_INTERMEDIARIO_SILENZIOSO = "https://script.google.com/macros/s/AKfycbyXBLjDpJrSGHoUpuspTsNAG9f6lGhF1e8oGyJ8nkY6jZMTJo04zsT_6eLyEybGgv4/exec"
ID_CARTELLA_CONSEGNE = "1pJpYtIfcMEKFh62rSOGTXWYG8CgvzN4m"
ID_CARTELLA_RICONSEGNE = "1S6IcauDOc-8sFiCdGv67CHKf_H9u7BVW"
ID_CARTELLA_ORDINI = "1bVTs2smvVJONs2oIAFZdDvX9pYDK9MZT"  
SPREADSHEET_ID = "1Q91H_TULvpsnPcyOwQ1lxmjOf809xp4cUz9p1EdMc-4"
URL_LOGO = "https://cspace.spaggiari.eu//pub/TVII0004/TVII0004-intestazione-nuova-senzaloghi.png?_t=1712923868"
EMAIL_PRESIDE_TEST = "marcobrunetti14@gmail.com"

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

df_istanze = pd.DataFrame()

# --- IMPORTAZIONE LIBRERIE ---
try:
    import gspread
    from google.oauth2 import service_account
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False


# --- MESSA IN SICUREZZA DI VALORI NULLI/NONE ---
def pulisci_caratteri_fpdf(testo):
    if testo is None:
        return ""
    testo = str(testo)
    mappa = {
        '€': 'EUR', 'à': 'a\'', 'è': 'e\'', 'é': 'e\'', 
        'ì': 'i\'', 'ò': 'o\'', 'ù': 'u\'', '°': ' '
    }
    for k, v in mappa.items(): 
        testo = testo.replace(k, v)
    return testo


# --- CORE GOOGLE CONNECTIONS ---
@st.cache_resource(ttl=5)
def connetti_google_sheets():
    if not GSPREAD_AVAILABLE or "google_creds" not in st.secrets: 
        return None
    try:
        creds_info = dict(st.secrets["google_creds"])
        if "private_key" in creds_info: 
            creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n").strip()
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = service_account.Credentials.from_service_account_info(creds_info, scopes=scopes)
        return gspread.authorize(creds).open_by_key(SPREADSHEET_ID)
    except Exception: 
        return None

def scarica_da_sheet(nome_scheda):
    sh = connetti_google_sheets()
    if sh is not None:
        try:
            ws = sh.worksheet(nome_scheda)
            records = ws.get_all_records()
            return pd.DataFrame(records) if records else pd.DataFrame()
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

def carica_su_sheet(df, nome_scheda):
    sh = connetti_google_sheets()
    if sh is not None:
        try:
            ws = sh.worksheet(nome_scheda)
            ws.clear()
            df_filled = df.fillna("")
            ws.update([df_filled.columns.values.tolist()] + df_filled.values.tolist())
            return True
        except Exception:
            return False
    return False

def carica_su_drive_unico(file_bytes, nome_file, mime_type, id_cartella):
    try:
        payload = {
            "nomeFile": nome_file,
            "mimeType": mime_type,
            "cartellaId": id_cartella,
            "fileB64": base64.b64encode(file_bytes).decode("utf-8")
        }
        res = requests.post(URL_INTERMEDIARIO_SILENZIOSO, json=payload, timeout=30)
        return res.status_code == 200
    except Exception:
        return False

def invia_email_sistema(destinatario, oggetto, corpo_testo):
    if "smtp_settings" not in st.secrets:
        return False
    try:
        conf = st.secrets["smtp_settings"]
        msg = MIMEMultipart()
        msg['From'] = conf["smtp_username"]
        msg['To'] = destinatario
        msg['Subject'] = oggetto
        msg.attach(MIMEText(corpo_testo, 'plain', 'utf-8'))
        
        server = smtplib.SMTP(conf["smtp_server"], int(conf["smtp_port"]))
        server.starttls()
        server.login(conf["smtp_username"], conf["smtp_password"])
        server.sendmail(conf["smtp_username"], destinatario, msg.as_string())
        server.quit()
        return True
    except Exception:
        return False


# --- ENGINE GENERAZIONE PDF ORDINE ---
def genera_pdf_ordine_fornitore(dati):
    if not FPDF_AVAILABLE:
        return b""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(15, 15, 15)
    
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 5, "ISISS JACOPO SCARPA", ln=True, align="L")
    pdf.set_font("Arial", "", 9)
    pdf.cell(0, 5, "Via Pieve di Soligo, 3 - 31045 Motta di Livenza (TV)", ln=True, align="L")
    pdf.cell(0, 5, "Cod. Fisc. 93011310265 - Tel. 0422 860012", ln=True, align="L")
    pdf.ln(10)
    
    pdf.set_x(110)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 5, "Spett.le Ditta:", ln=True)
    for linea in dati["fornitore"].splitlines():
        pdf.set_x(110)
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 5, pulisci_caratteri_fpdf(linea), ln=True)
    pdf.ln(15)
    
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 6, f"OGGETTO: {pulisci_caratteri_fpdf(dati['oggetto_ordine'])}", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, f"Riferimento Vs. Preventivo del: {dati['data_preventivo']} | Nostro Protocollo Ingresso: {dati['protocollo_istituto']}", ln=True)
    pdf.cell(0, 6, f"Determina di Affidamento: N. {dati['determina']} | Codice CIG Assegnato: {dati['cig']}", ln=True)
    pdf.ln(8)
    
    corpo = "Con la presente si formalizza l'affidamento diretto per la fornitura dei beni sotto elencati, alle condizioni economiche e di consegna concordate nel preventivo in epigrafe."
    pdf.multi_cell(0, 5, corpo)
    pdf.ln(8)
    
    pdf.set_font("Arial", "B", 9)
    pdf.cell(110, 7, "Descrizione Bene / Servizio", 1, 0, "L")
    pdf.cell(15, 7, "Q.ta", 1, 0, "C")
    pdf.cell(25, 7, "Prezzo", 1, 0, "R")
    pdf.cell(25, 7, "Totale", 1, 1, "R")
    
    pdf.set_font("Arial", "", 9)
    for art in dati["articoli"]:
        desc_prodotto = art.get("descrizione_materiale", art.get("descrizione", ""))
        pdf.cell(110, 7, pulisci_caratteri_fpdf(desc_prodotto), 1, 0, "L")
        pdf.cell(15, 7, str(art["quantita"]), 1, 0, "C")
        pdf.cell(25, 7, f"{art['prezzo_unitario']} EUR", 1, 0, "R")
        pdf.cell(25, 7, f"{art['totale_riga']} EUR", 1, 1, "R")
        
    pdf.set_font("Arial", "B", 10)
    pdf.cell(150, 7, "TOTALE FORNITURA:", 1, 0, "R")
    pdf.cell(25, 7, f"{dati['importo_ivato']} EUR", 1, 1, "R")
    pdf.ln(20)
    
    pdf.cell(90, 5, "Il Direttore dei Servizi Gen. Amm.vi", 0, 0, "C")
    pdf.cell(90, 5, "Il Dirigente Scolastico", 0, 1, "C")
    
    return pdf.output(dest="S").encode("latin-1", errors="ignore")


# --- ROUTING DI AUTENTICAZIONE ---
if "autenticato" not in st.session_state:
    st.session_state.autenticato = False
    st.session_state.ruolo = None

if not st.session_state.autenticato:
    st.image(URL_LOGO, use_container_width=True)
    st.markdown("<h2 style='text-align: center;'>🔑 Accesso Sicuro Sistema Logistico</h2>", unsafe_allow_html=True)
    
    password = st.text_input("Inserisci la password di dipartimento o amministrativa:", type="password")
    if st.button("Effettua il Login", use_container_width=True):
        if password in PASSWORD_MAP:
            st.session_state.autenticato = True
            st.session_state.ruolo = PASSWORD_MAP[password]
            st.rerun()
        elif password == PASSWORD_ADMIN:
            st.session_state.autenticato = True
            st.session_state.ruolo = "Amministrazione"
            st.rerun()
        else:
            st.error("Chiave di sicurezza errata. Riprova.")
else:
    c_user, c_logout = st.columns([8, 2])
    with c_user:
        st.info(f"Utente Connesso: **{st.session_state.ruolo}**")
    with c_logout:
        if st.button("🚪 Esci dal Sistema", use_container_width=True):
            st.session_state.autenticato = False
            st.session_state.ruolo = None
            st.rerun()
            
    if st.session_state.ruolo == "Amministrazione":
        gestione_preventivi.mostra_interfaccia_preventivi(
            scarica_da_sheet, 
            carica_su_sheet, 
            invia_email_sistema,
            URL_INTERMEDIARIO_SILENZIOSO,
            df_istanze,
            genera_pdf_ordine_fornitore, 
            carica_su_drive_unico, 
            ID_CARTELLA_ORDINI
        )
        
    else:
        st.title(f"🏢 Pannello Gestione Interna - {st.session_state.ruolo}")
        
        nome_scheda_inv = MAPPA_SCHEDE[st.session_state.ruolo]["inventario"]
        nome_scheda_req = MAPPA_SCHEDE[st.session_state.ruolo]["richieste"]
        
        tab_stato, tab_carico, tab_scarico, tab_segnala = st.tabs([
            "📦 Inventario Attuale", 
            "📥 Carico Nuove Merci", 
            "📤 Scarico / Assegnazione Bene",
            "🚨 Segnala Fabbisogno Esaurito"
        ])
        
        df_inv = scarica_da_sheet(nome_scheda_inv)
        
        with tab_stato:
            st.subheader("Disponibilità Materiali Real-Time")
            if df_inv.empty:
                st.warning("Inventario vuoto o non accessibile.")
            else:
                st.dataframe(df_inv, use_container_width=True, hide_index=True)
                
        with tab_carico:
            st.subheader("Registra un incremento di materiale a magazzino")
            if not df_inv.empty:
                lista_materiali = df_inv["Descrizione materiale"].tolist() if "Descrizione materiale" in df_inv.columns else []
                if lista_materiali:
                    scelta_mat = st.selectbox("Seleziona il bene da caricare:", lista_materiali, key="carico_sel")
                    qta_carico = st.number_input("Quantità in ingresso:", min_value=1, step=1)
                    
                    if st.button("Conferma Carico Merci", use_container_width=True):
                        idx = df_inv.index[df_inv["Descrizione materiale"] == scelta_mat].tolist()[0]
                        df_inv.at[idx, "Giacenza attuale"] = int(df_inv.at[idx, "Giacenza attuale"]) + qta_carico
                        df_inv.at[idx, "Ultimo aggiornamento"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                        if carica_su_sheet(df_inv, nome_scheda_inv):
                            st.success("Inventario aggiornato con successo!")
                            st.rerun()
                        
        with tab_scarico:
            st.subheader("Registra prelievo di materiale dal magazzino")
            if not df_inv.empty and "Descrizione materiale" in df_inv.columns:
                lista_materiali_sc = df_inv["Descrizione materiale"].tolist()
                scelta_mat_sc = st.selectbox("Seleziona il bene estratto:", lista_materiali_sc, key="scarico_sel")
                riga_selezionata = df_inv[df_inv["Descrizione materiale"] == scelta_mat_sc].iloc[0]
                giacenza_disponibile = int(riga_selezionata["Giacenza attuale"]) if "Giacenza attuale" in riga_selezionata else 0
                
                st.metric(label="Giacenza Attuale di Sicurezza", value=f"{giacenza_disponibile} unità")
                qta_scarico = st.number_input("Quantità prelevata:", min_value=1, max_value=max(1, giacenza_disponibile), step=1)
                destinatario_bene = st.text_input("Assegnatario / Aula / Destinazione d'uso:")
                
                if st.button("Esegui Scarico Merci", type="primary", use_container_width=True):
                    if giacenza_disponibile < qta_scarico:
                        st.error("Azione bloccata: quantità insufficiente a magazzino.")
                    elif not destinatario_bene.strip():
                        st.error("Specificare l'assegnatario del materiale.")
                    else:
                        idx = df_inv.index[df_inv["Descrizione materiale"] == scelta_mat_sc].tolist()[0]
                        df_inv.at[idx, "Giacenza attuale"] = giacenza_disponibile - qta_scarico
                        df_inv.at[idx, "Ultimo aggiornamento"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                        carica_su_sheet(df_inv, nome_scheda_inv)
                        st.success("Prelievo registrato e giacenze aggiornate!")
                        st.rerun()
                        
        with tab_segnala:
            st.subheader("🚨 Generazione Fabbisogno per l'Ufficio Acquisti")
            
            with st.form("form_segnalazione"):
                materiale_urgente = st.text_input("Nome/Modello specifico del materiale mancante:")
                qta_richiesta_assoluta = st.number_input("Quantità minima necessaria:", min_value=1, step=1)
                note_urgenza = st.text_area("Note e specifiche tecniche aggiuntive per l'acquisto:")
                
                if st.form_submit_button("Invia Segnalazione in Amministrazione"):
                    if not materiale_urgente.strip():
                        st.error("Specificare il materiale.")
                    else:
                        df_fabbisogni_globali = scarica_da_sheet("Richieste_Preventivo_Magazzino")
                        if not df_fabbisogni_globali.empty and "id_richiesta_mag" in df_fabbisogni_globali.columns:
                            id_req_num = pd.to_numeric(df_fabbisogni_globali["id_richiesta_mag"], errors='coerce')
                            nuovo_id_req = 1001 if id_req_num.dropna().empty else int(id_req_num.max()) + 1
                        else:
                            nuovo_id_req = 1001
                        
                        nuovo_fabbisogno = pd.DataFrame([{
                            "id_richiesta_mag": str(nuovo_id_req),
                            "magazzino_origine": str(st.session_state.ruolo),
                            "materiale_richiesto": str(materiale_urgente.strip()),
                            "quantita_richiesta": str(qta_richiesta_assoluta),
                            "data_segnalazione": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "stato_iter": "In attesa di preventivi",
                            "note_tecniche": str(note_urgenza.strip())
                        }])
                        
                        carica_su_sheet(pd.concat([df_fabbisogni_globali, nuovo_fabbisogno], ignore_index=True), "Richieste_Preventivo_Magazzino")
                        
                        testo_mail = f"Nuova segnalazione di fabbisogno logistico dall'ISISS Scarpa.\n\nMagazzino Mittente: {st.session_state.ruolo}\nMateriale: {materiale_urgente.strip()}\nQuantità Richiesta: {qta_richiesta_assoluta}\nNote Tecniche: {note_urgenza}"
                        invia_email_sistema(EMAIL_PRESIDE_TEST, f"🚨 NOTIFICA FABBISOGNO INSERITO - ID {nuovo_id_req}", testo_mail)
                        
                        st.success(f"Richiesta registrata ufficialmente con codice ID {nuovo_id_req}!")
