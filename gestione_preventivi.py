import streamlit as st
import pandas as pd
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURAZIONE SPREADSHEET E INTERMEDIARIO (COERENTI CON FILE PRINCIPALE) ---
SPREADSHEET_ID = "1Q91H_TULvpsnPcyOwQ1lxmjOf809xp4cUz9p1EdMc-4"
URL_INTERMEDIARIO_SILENZIOSO = "https://script.google.com/macros/s/AKfycbyXBLjDpJrSGHoUpuspTsNAG9f6lGhF1e8oGyJ8nkY6jZMTJo04zsT_6eLyEybGgv4/exec"

# --- CONTROLLO LIBRERIE ESTERNE ---
try:
    import gspread
    from google.oauth2 import service_account
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

# --- CONFIGURAZIONE INIZIALE DI PAGINA ---
st.set_page_config(page_title="Gestione Preventivi e Fornitori - Scarpa", page_icon="📊", layout="wide")

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
            background-color: #0f172a !important;
            color: white !important;
            border-radius: 10px !important;
            border: none !important;
            font-weight: 600 !important;
        }
        div.stButton > button:first-child:hover { background-color: #1e293b !important; }
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
        return pd.DataFrame(worksheet.get_all_records())
    except gspread.exceptions.WorksheetNotFound:
        # Creazione automatica delle tabelle per i preventivi se non esistono nello Sheet
        if nome_scheda == "Anagrafica_Fornitori":
            df_base = pd.DataFrame(columns=["id_fornitore", "ragione_sociale", "email", "telefono", "categoria"])
        elif nome_scheda == "Richieste_Preventivi":
            df_base = pd.DataFrame(columns=["id_gara", "id_richiesta", "id_fornitore", "data_invio", "stato_gara"])
        elif nome_scheda == "Risposte_Preventivi":
            df_base = pd.DataFrame(columns=["id_gara", "id_fornitore", "prezzo_totale", "giorni_consegna", "note_fornitore", "data_risposta"])
        else:
            return pd.DataFrame()
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

# --- INVIO EMAIL CAPITOLATO AL FORNITORE ---
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

# --- NAVIGAZIONE PRINCIPALE ---
st.title("📊 Hub Approvvigionamento & Controllo Preventivi")
menu = st.sidebar.radio("Sezione Lavoro:", ["📈 Dashboard Comparativa", "✉️ Nuova Richiesta Offerta (RFQ)", "👥 Rubrica Fornitori"])

# Caricamento dati condivisi
df_richieste_dirigente = scarica_da_sheet("Richieste_Preside")
df_fornitori = scarica_da_sheet("Anagrafica_Fornitori")
df_gare = scarica_da_sheet("Richieste_Preventivi")
df_risposte = scarica_da_sheet("Risposte_Preventivi")

# ==========================================
# SEZIONE 1: DASHBOARD COMPARATIVA PREVENTIVI
# ==========================================
if menu == "📈 Dashboard Comparativa":
    st.markdown("## 🔍 Matrice di Confronto e Monitoraggio Gare")
    
    if df_gare.empty:
        st.info("Nessuna richiesta di preventivo attualmente registrata a sistema.")
    else:
        # Troviamo tutte le richieste d'acquisto aperte ai fornitori
        id_richieste_attive = df_gare["id_richiesta"].unique().tolist()
        
        for id_req in id_richieste_attive:
            # Recupera i dettagli originari della richiesta
            dettaglio_req = df_richieste_dirigente[df_richieste_dirigente["id_richiesta"].astype(str) == str(id_req)]
            oggetto_richiesta = dettaglio_req["oggetto"].values[0] if not dettaglio_req.empty else "Dettaglio non trovato"
            richiedente = dettaglio_req["richiedente"].values[0] if not dettaglio_req.empty else "-"
            
            with st.container(border=True):
                st.markdown(f"### 📦 Istanza ID {id_req} — Oggetto: *{oggetto_richiesta}* (Richiedente: {richiedente})")
                
                # Trova i fornitori coinvolti in questa specifica gara
                fornitori_coinvolti = df_gare[df_gare["id_richiesta"].astype(str) == str(id_req)]
                
                righe_confronto = []
                for _, f_riga in fornitori_coinvolti.iterrows():
                    id_gara = f_riga["id_gara"]
                    id_forn = f_riga["id_fornitore"]
                    
                    # Cerca info fornitore
                    inf_f = df_fornitori[df_fornitori["id_fornitore"].astype(str) == str(id_forn)]
                    rag_soc = inf_f["ragione_sociale"].values[0] if not inf_f.empty else f"Fornitore #{id_forn}"
                    
                    # Cerca l'eventuale risposta ricevuta dal portale
                    risp_f = df_risposte[(df_risposte["id_gara"].astype(str) == str(id_gara)) & (df_risposte["id_fornitore"].astype(str) == str(id_forn))]
                    
                    if not risp_f.empty:
                        prezzo = pd.to_numeric(risp_f["prezzo_totale"].values[0], errors='coerce')
                        consegna = pd.to_numeric(risp_f["giorni_consegna"].values[0], errors='coerce')
                        note = risp_f["note_fornitore"].values[0]
                        stato = "🟢 Ricevuto"
                    else:
                        prezzo = float('inf')
                        consegna = float('inf')
                        note = "-"
                        stato = "🟡 In attesa"
                        
                    righe_confronto.append({
                        "id_gara": id_gara,
                        "Fornitore": rag_soc,
                        "Costo Totale (€)": prezzo,
                        "Tempi Consegna (Giorni)": consegna,
                        "Stato": stato,
                        "Note Fornitore": note
                    })
                
                df_comparazione = pd.DataFrame(righe_confronto)
                
                # Calcolo automatico del fornitore consigliato
                prezzi_validi = df_comparazione[df_comparazione["Costo Totale (€)"] < float('inf')]
                tempi_validi = df_comparazione[df_comparazione["Tempi Consegna (Giorni)"] < float('inf')]
                
                id_piu_economico = prezzi_validi.loc[prezzi_validi["Costo Totale (€)"].idxmin()]["id_gara"] if not prezzi_validi.empty else None
                id_piu_veloce = tempi_validi.loc[tempi_validi["Tempi Consegna (Giorni)"].idxmin()]["id_gara"] if not tempi_validi.empty else None
                
                def assegna_badge(riga):
                    if riga["Stato"] == "🟡 In attesa": return "—"
                    badges = []
                    if riga["id_gara"] == id_piu_economico: badges.append("⭐ Più Economico")
                    if riga["id_gara"] == id_piu_veloce: badges.append("⚡ Più Veloce")
                    return " / ".join(badges) if badges else "Idoneo"
                
                df_comparazione["Analisi Automatica"] = df_comparazione.apply(assegna_badge, axis=1)
                
                # Pulizia visualizzazione per la tabella finale
                df_visualizzabile = df_comparazione.copy()
                df_visualizzabile["Costo Totale (€)"] = df_visualizzabile["Costo Totale (€)"].apply(lambda x: f"€ {x:,.2f}" if x < float('inf') else "Non disponibile")
                df_visualizzabile["Tempi Consegna (Giorni)"] = df_visualizzabile["Tempi Consegna (Giorni)"].apply(lambda x: f"{int(x)} gg" if x < float('inf') else "Non disponibile")
                
                st.dataframe(df_visualizzabile.drop(columns=["id_gara"]), use_container_width=True, hide_index=True)
                
                # Azione di chiusura ordine
                opzioni_scelta = df_comparazione[df_comparazione["Stato"] == "🟢 Ricevuto"]["Fornitore"].tolist()
                if opzioni_scelta:
                    col_sel, col_btn = st.columns([2, 1])
                    with col_sel:
                        vincitore = st.selectbox("Seleziona il fornitore a cui affidare l'ordine:", opzioni_scelta, key=f"vinc_{id_req}")
                    with col_btn:
                        st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
                        if st.button("Aggiudica ed emetti Buono d'Ordine", key=f"btn_vinc_{id_req}", use_container_width=True):
                            st.success(f"🎉 Gara chiusa con successo! Ordine assegnato a: {vincitore}. Notifica in trasmissione.")

# ==========================================
# SEZIONE 2: NUOVA RICHIESTA OFFERTA (RFQ)
# ==========================================
elif menu == "✉️ Nuova Richiesta Offerta (RFQ)":
    st.markdown("## 📨 Generazione Richiesta Preventivo")
    
    # Filtriamo le richieste approvate dalla Dirigente (Stato: "Lavorata" o "In lavorazione")
    richieste_valide = df_richieste_dirigente[df_richieste_dirigente["stato"].isin(["Lavorata", "In lavorazione"])] if not df_richieste_dirigente.empty else pd.DataFrame()
    
    if richieste_valide.empty:
        st.info("Al momento non ci sono richieste autorizzate dalla Dirigente per cui avviare un'indagine di mercato.")
    elif df_fornitori.empty:
        st.error("Nessun fornitore censito in rubrica. Vai alla sezione 'Rubrica Fornitori' per inserire i contatti.")
    else:
        # Selezione dell'istanza d'acquisto da processare
        opzioni_richieste = richieste_valide.apply(lambda r: f"ID {r['id_richiesta']} - {r['oggetto']} (Destinatario: {r['richiedente']})", axis=1).tolist()
        scelta_richiesta = st.selectbox("Seleziona l'istanza approvata della scuola:", opzioni_richieste)
        id_richiesta_selezionata = scelta_richiesta.split(" ")[1]
        
        riga_selezionata = richieste_valide[richieste_valide["id_richiesta"].astype(str) == str(id_richiesta_selezionata)].iloc[0]
        
        with st.container(border=True):
            st.markdown(f"#### Capitolato Tecnico da preventivare:")
            st.markdown(f"**Tipologia:** {riga_selezionata['categoria_bene']} | **Descrizione dettagliata:** {riga_selezionata['motivazione']}")
        
        st.markdown("### 👥 Selezione dei Fornitori da invitare alla gara")
        fornitori_scelti = st.multiselect("Scegli uno o più operatori economici dalla rubrica:", df_fornitori["ragione_sociale"].tolist())
        
        if st.button("Spedisci richiesta quotazione (Email automatica)", type="primary", use_container_width=True):
            if not fornitori_scelti:
                st.error("Selezionare almeno un fornitore prima di procedere all'invio.")
            else:
                progress_bar = st.progress(0)
                passi = len(fornitori_scelti)
                
                for idx, f_nome in enumerate(fornitori_scelti):
                    riga_f = df_fornitori[df_fornitori["ragione_sociale"] == f_nome].iloc[0]
                    email_fornitore = riga_f["email"]
                    id_fornitore = riga_f["id_fornitore"]
                    
                    # Generazione identificativo univoco della gara d'appalto
                    try: id_gara_nuovo = int(df_gare["id_gara"].astype(float).max()) + 1 if not df_gare.empty else 5001
                    except Exception: id_gara_nuovo = 5001
                    
                    # Creazione del link univoco per far inserire la risposta al fornitore sul portale
                    link_risposta = f"{URL_INTERMEDIARIO_SILENZIOSO}?action=fornitore_form&id_gara={id_gara_nuovo}&id_fornitore={id_fornitore}"
                    
                    # Preparazione dell'email istituzionale
                    corpo_html = f"""
                    <div style="font-family: Arial, sans-serif; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px;">
                        <h2 style="color: #8b1e1e;">ISISS Antonio Scarpa - Richiesta di Preventivo</h2>
                        <p>Gentile operatore economico <b>{f_nome}</b>,</p>
                        <p>La nostra istituzione scolastica necessita della quotazione economica per la fornitura dei seguenti beni:</p>
                        <blockquote style="background: #f1f5f9; padding: 15px; border-left: 5px solid #64748b; margin: 15px 0;">
                            <b>Articolo/Servizio richiesto:</b> {riga_selezionata['oggetto']}<br>
                            <b>Specifiche Tecniche:</b> {riga_selezionata['motivazione']}
                        </blockquote>
                        <p>Per sottoporre la Vostra migliore offerta direttamente sulla nostra piattaforma logistica, Vi invitiamo a cliccare sul seguente link sicuro:</p>
                        <p style="margin: 25px 0; text-align: center;">
                            <a href="{link_risposta}" style="background: #0f172a; color: white; padding: 12px 25px; text-decoration: none; border-radius: 8px; font-weight: bold;">📊 INSERISCI PREVENTIVO SUL PORTALE</a>
                        </p>
                        <p style="font-size: 11px; color: #64748b;">La presente richiesta non costituisce impegno d'acquisto. Cordiali saluti.<br><i>Ufficio Tecnico / Logistica ISISS A. Scarpa</i></p>
                    </div>
                    """
                    
                    # Invio effettivo della mail
                    inviata = invia_email_sistema(email_fornitore, f"Richiesta di Offerta RFQ - Gara ID {id_gara_nuovo} - ISISS A. SCARPA", corpo_html)
                    
                    if inviata:
                        # Registrazione della gara su Google Sheets
                        nuovo_record_gara = pd.DataFrame([{
                            "id_gara": id_gara_nuovo,
                            "id_richiesta": id_richiesta_selezionata,
                            "id_fornitore": id_fornitore,
                            "data_invio": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "stato_gara": "Inviato"
                        }])
                        df_gare = pd.concat([df_gare, nuovo_record_gara], ignore_index=True)
                        carica_su_sheet(df_gare, "Richieste_Preventivi")
                        
                st.success("✨ Richieste inoltrate correttamente a tutti i fornitori selezionati! Il portale è ora in ascolto per ricevere i prezzi.")

# ==========================================
# SEZIONE 3: RUBRICA FORNITORI
# ==========================================
elif menu == "👥 Rubrica Fornitori":
    st.markdown("## 📖 Gestione Anagrafica Fornitori d'Istituto")
    
    col_ins, col_vis = st.columns([1.2, 2])
    
    with col_ins:
        st.markdown("### ➕ Aggiungi a Rubrica")
        with st.form("form_fornitore", clear_on_submit=True):
            rag_soc = st.text_input("Ragione Sociale Azienda:")
            f_mail = st.text_input("Email di Contatto:")
            f_tel = st.text_input("Recapito Telefonico:")
            f_cat = st.selectbox("Categoria Merceologica:", ["Informatica ed Elettronica", "Cancelleria e Carta", "Ferramenta e Officina", "Arredi Scolastici"])
            
            if st.form_submit_button("Salva in Anagrafica", use_container_width=True):
                if rag_soc.strip() and f_mail.strip():
                    try: id_f_nuovo = int(df_fornitori["id_fornitore"].astype(float).max()) + 1 if not df_fornitori.empty else 1
                    except Exception: id_f_nuovo = 1
                    
                    nuovo_f = pd.DataFrame([{
                        "id_fornitore": id_f_nuovo,
                        "ragione_sociale": rag_soc.strip(),
                        "email": f_mail.strip(),
                        "telefono": f_tel.strip(),
                        "categoria": f_cat
                    }])
                    
                    df_fornitori = pd.concat([df_fornitori, nuovo_f], ignore_index=True)
                    carica_su_sheet(df_fornitori, "Anagrafica_Fornitori")
                    st.success(f"L'azienda '{rag_soc}' è stata inserita correttamente con ID {id_f_nuovo}.")
                    st.rerun()
                else:
                    st.error("I campi Ragione Sociale ed Email sono strettamente obbligatori.")
                    
    with col_vis:
        st.markdown("### 🏬 Elenco Operatori Censiti")
        if df_fornitori.empty:
            st.info("La rubrica è vuota al momento.")
        else:
            st.dataframe(df_fornitori, use_container_width=True, hide_index=True)
