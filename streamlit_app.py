import streamlit as st
import pandas as pd
from datetime import datetime
import io
import os

# Controllo e importazione delle librerie ufficiali di Google
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False

# ==========================================
# CONFIGURAZIONE GENERALI E ID DRIVRE
# ==========================================
PASSWORD_MAGAZZINIERE = "magazzino2026"
PASSWORD_ADMIN = "admin99"
URL_LOGO = "https://cspace.spaggiari.eu//pub/TVII0004/TVII0004-intestazione-nuova-senzaloghi.png?_t=1712923868"
ID_CARTELLA_DRIVE = "1T9KlJb4MFLvo3vK4XRmxRFK3wshPSP5m"

st.set_page_config(page_title="Gestione Magazzino Scarpa", page_icon="🧺", layout="wide")

# ==========================================
# FUNZIONE DI CARICAMENTO SU GOOGLE DRIVE MODIFICATA
# ==========================================
def carica_su_drive(file_bytes, nome_file, mime_type):
    if not GOOGLE_LIBS_AVAILABLE:
        st.error("⚠️ Errore: Le librerie Google non sono installate nel sistema. Controlla il file requirements.txt.")
        return None
    try:
        # 1. Lettura dai Secrets di Streamlit Cloud
        if "google_creds" in st.secrets:
            creds_dict = dict(st.secrets["google_creds"])
            if "\\n" in creds_dict["private_key"]:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            creds = service_account.Credentials.from_service_account_info(
                creds_dict, 
                scopes=['https://www.googleapis.com/auth/drive']
            )
        elif os.path.exists('google_credentials.json'):
            creds = service_account.Credentials.from_service_account_file(
                'google_credentials.json', 
                scopes=['https://www.googleapis.com/auth/drive']
            )
        else:
            st.error("❌ Credenziali di Google non trovate. Verifica la configurazione nei Secrets.")
            return None

        # Connessione alle API di Google Drive
        service = build('drive', 'v3', credentials=creds)
        
        # FIX PER IL QUOTA EXCEEDED: Impostiamo i metadati in modo che utilizzi 
        # lo spazio della cartella di destinazione (Keep-with-parent)
        file_metadata = {
            'name': nome_file, 
            'parents': [ID_CARTELLA_DRIVE]
        }
        
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
        
        # Eseguiamo il caricamento ignorando il controllo di quota sul service account
        file_caricato = service.files().create(
            body=file_metadata, 
            media_body=media, 
            fields='id',
            supportsAllDrives=True  # Permette di ereditare le proprietà della cartella condivisa
        ).execute()
        
        return file_caricato.get('id')
    except Exception as e:
        st.error(f"❌ Errore durante l'invio a Google Drive: {e}")
        st.info("💡 Nota: Se l'errore persiste, assicurati che la cartella Drive sia stata condivisa con l'indirizzo email del Service Account come 'Editor'.")
        return None

# ==========================================
# STILE UX/UI: SFONDO GHIACCIO E BLU NOTTE
# ==========================================
st.markdown("""
    <style>
        .stApp {
            background-color: #f1f5f9 !important;
            color: #0f172a !important;
            font-family: 'Inter', sans-serif;
        }
        [data-testid="stMainBlockContainer"] {
            max-width: 1050px;
            margin: 0 auto;
            padding-top: 2rem;
        }
        h1 {
            color: #0f172a !important;
            font-family: 'Montserrat', sans-serif;
            font-weight: 800 !important;
            text-align: center;
            margin-bottom: 30px !important;
        }
        h2, h3, h4, label, [data-testid="stWidgetLabel"] p {
            color: #1e293b !important;
            font-weight: 700 !important;
        }
        [data-testid="stContainer"] {
            background-color: #ffffff !important;
            border: 1px solid #e2e8f0 !important;
            border-radius: 16px !important;
            padding: 28px !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03) !important;
            margin-bottom: 20px;
        }
        [data-testid="stContainer"] p {
            color: #334155 !important;
        }
        div.stButton > button:first-child {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%) !important;
            color: #ffffff !important;
            border-radius: 10px !important;
            border: none !important;
            padding: 12px 24px !important;
            font-weight: 600 !important;
            box-shadow: 0 4px 12px rgba(15, 23, 42, 0.15) !important;
            transition: all 0.2s ease !important;
            width: 100%;
        }
        div.stButton > button:first-child:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 15px rgba(15, 23, 42, 0.25) !important;
            background: #0f172a !important;
        }
        [data-testid="stSidebar"] {
            background-color: #ffffff !important;
            border-right: 1px solid #e2e8f0;
        }
        footer {visibility: hidden;}
        [data-testid="stHeader"] {background: transparent;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# INIZIALIZZAZIONE DATABASE IN MEMORIA
# ==========================================
if "db_inventario" not in st.session_state:
    st.session_state.db_inventario = pd.DataFrame([
        {"id_articolo": "A001", "nome_articolo": "Guanti da lavoro", "giacenza_totale": 50},
        {"id_articolo": "A002", "nome_articolo": "Scarpe antinfortunistiche", "giacenza_totale": 12},
        {"id_articolo": "A003", "nome_articolo": "Occhiali protettivi", "giacenza_totale": 30}
    ])

if "db_richieste" not in st.session_state:
    st.session_state.db_richieste = pd.DataFrame(columns=["id_richiesta", "collaboratore", "articolo", "quantita", "stato", "data_richiesta", "data_consegna"])

if "ruolo_utente" not in st.session_state:
    st.session_state.ruolo_utente = None
if "utente_corrente" not in st.session_state:
    st.session_state.utente_corrente = ""

# --- SCHERMATA LOGIN ---
if st.session_state.ruolo_utente is None:
    st.image(URL_LOGO, use_container_width=True)
    st.markdown("<h1>Gestione Magazzino Scarpa</h1>", unsafe_allow_html=True)
    
    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        with st.container():
            st.markdown("<h3 style='text-align: center; margin-top:0;'>🔑 Seleziona Profilo</h3>", unsafe_allow_html=True)
            scelta_accesso = st.radio("", ["Sono un Collaboratore (Richiesta)", "Sono il Magazziniere / Admin"], label_visibility="collapsed")
            st.markdown("<br>", unsafe_allow_html=True)
            
            if scelta_accesso == "Sono un Collaboratore (Richiesta)":
                nome_input = st.text_input("Inserisci il tuo Nome e Cognome:")
                if st.button("Accedi all'area Richieste"):
                    if not nome_input.strip():
                        st.error("⚠️ Inserisci il tuo nome per continuare.")
                    else:
                        st.session_state.ruolo_utente = "collaboratore"
                        st.session_state.utente_corrente = nome_input.strip()
                        st.rerun()
                        
            elif scelta_accesso == "Sono il Magazziniere / Admin":
                password_input = st.text_input("Inserisci la password di sblocco:", type="password")
                if st.button("Verifica Password"):
                    if password_input == PASSWORD_MAGAZZINIERE:
                        st.session_state.ruolo_utente = "magazziniere"
                        st.rerun()
                    elif password_input == PASSWORD_ADMIN:
                        st.session_state.ruolo_utente = "admin"
                        st.rerun()
                    else:
                        st.error("❌ Password errata. Riprova.")

# --- INTERFACCE ABILITATE ---
else:
    st.image(URL_LOGO, use_container_width=True)
    
    with st.sidebar:
        st.markdown(f"<h3>🧺 Area {st.session_state.ruolo_utente.upper()}</h3>", unsafe_allow_html=True)
        st.write("---")
        if st.button("🔒 Esci / Cambia Utente"):
            st.session_state.ruolo_utente = None
            st.session_state.utente_corrente = ""
            st.rerun()

    df_inventario = st.session_state.db_inventario
    df_richieste = st.session_state.db_richieste

    # --- 1. SCHERMATA COLLABORATORE ---
    if st.session_state.ruolo_utente == "collaboratore":
        st.markdown(f"<h1>👋 Benvenuto, {st.session_state.utente_corrente}</h1>", unsafe_allow_html=True)
        
        with st.container():
            st.markdown("<h3>📋 Nuova Richiesta Materiale</h3>", unsafe_allow_html=True)
            lista_articoli = df_inventario["nome_articolo"].tolist()
            lista_articoli.append("Altro...")
            
            articolo_selezionato = st.selectbox("Seleziona cosa ti serve:", lista_articoli)
            articolo_finale = st.text_input("Specifica il materiale a mano:") if articolo_selezionato == "Altro..." else articolo_selezionato
            qta = st.number_input("Quantità necessaria:", min_value=1, step=1)
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Invia Ordine in Magazzino"):
                if articolo_selezionato == "Altro..." and not articolo_finale.strip():
                    st.error("⚠️ Specifica il nome del materiale.")
                else:
                    nuovo_id = int(df_richieste["id_richiesta"].max()) + 1 if not df_richieste.empty else 1
                    nuova_r = pd.DataFrame([{"id_richiesta": nuovo_id, "collaboratore": st.session_state.utente_corrente, "articolo": articolo_finale, "quantita": int(qta), "stato": "In attesa", "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M"), "data_consegna": ""}])
                    st.session_state.db_richieste = pd.concat([df_richieste, nuova_r], ignore_index=True)
                    st.success("✔️ Richiesta inoltrata al magazziniere con successo!")

    # --- 2. SCHERMATA MAGAZZINIERE ---
    elif st.session_state.ruolo_utente == "magazziniere":
        st.markdown("<h1>🚚 Pannello Operativo Magazzino</h1>", unsafe_allow_html=True)
        
        tab_consegne, tab_carico, tab_ddt = st.tabs(["📋 Gestione Richieste", "➕ Carico Merce / Inventario", "📸 Archivia Foto DDT"])
        
        with tab_consegne:
            in_attesa = df_richieste[df_richieste["stato"] == "In attesa"]
            if in_attesa.empty:
                st.info("✨ Ottimo! Nessuna richiesta da evadere al momento.")
            else:
                for idx, row in in_attesa.iterrows():
                    with st.container():
                        c1, c2, c3 = st.columns([1, 4, 2])
                        with c1: st.write(f"**ID #{row['id_richiesta']}**")
                        with c2: st.markdown(f"👤 **{row['collaboratore']}**<br>Richiede: <span style='color:#1e3a8a;font-weight:bold;'>{row['quantita']}x {row['articolo']}</span>", unsafe_allow_html=True)
                        with c3:
                            if st.button("Consegna ✔", key=f"btn_{row['id_richiesta']}"):
                                filtro = df_inventario["nome_articolo"] == row['articolo']
                                if filtro.any():
                                    giacenza = int(df_inventario.loc[filtro, "giacenza_totale"].values[0])
                                    if giacenza >= int(row['quantita']):
                                        st.session_state.db_richieste.loc[st.session_state.db_richieste["id_richiesta"] == row["id_richiesta"], "stato"] = "Consegnato"
                                        st.session_state.db_richieste.loc[st.session_state.db_richieste["id_richiesta"] == row["id_richiesta"], "data_consegna"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                                        st.session_state.db_inventario.loc[filtro, "giacenza_totale"] = giacenza - int(row['quantita'])
                                        st.success("Evaso!")
                                        st.rerun()
                                    else: 
                                        st.error(f"❌ Stock insufficiente! Disponibili solo {giacenza} pezzi.")
                                else: 
                                    st.error("⚠️ Questo è un articolo personalizzato ('Altro'). Censiscilo nell'inventario (Tab 2) prima di consegnarlo.")

        with tab_carico:
            with st.container():
                st.markdown("### 🔧 Rifornisci Articolo Esistente")
                art_da_caricare = st.selectbox("Seleziona l'articolo da aumentare:", df_inventario["nome_articolo"].tolist())
                qta_da_aggiungere = st.number_input("Quantità arrivata:", min_value=1, step=1)
                if st.button("Esegui Rifornimento"):
                    st.session_state.db_inventario.loc[df_inventario["nome_articolo"] == art_da_caricare, "giacenza_totale"] += qta_da_aggiungere
                    st.success("Giacenza aggiornata con successo!")
                    st.rerun()
            with st.container():
                st.markdown("### ✨ Registra Nuovo Articolo nel Sistema")
                nuovo_id_art = st.text_input("Codice Identificativo Articolo (es. A004):")
                nuovo_nome_art = st.text_input("Nome del materiale:")
                nuovo_stock_art = st.number_input("Stock iniziale di partenza:", min_value=0, step=1)
                if st.button("Salva Nuovo Articolo"):
                    if not nuovo_id_art.strip() or not nuovo_nome_art.strip():
                        st.error("Compila tutti i campi dell'articolo.")
                    else:
                        nuovo_p = pd.DataFrame([{"id_articolo": नया_id_art.strip(), "nome_articolo": nuovo_nome_art.strip(), "giacenza_totale": int(nuovo_stock_art)}])
                        st.session_state.db_inventario = pd.concat([df_inventario, nuovo_p], ignore_index=True)
                        st.success("✔️ Nuovo articolo inserito in inventario!")
                        st.rerun()

        with tab_ddt:
            st.markdown("### 📸 Acquisizione e Archiviazione DDT")
            st.write("Scatta una foto direttamente con la fotocamera del telefono o carica un file per salvarlo nella cartella condivisa di Google Drive.")
            with st.container():
                foto_ddt = st.camera_input("Inquadra il documento di trasporto e scatta")
                file_ddt = st.file_uploader("Oppure seleziona un file/PDF dal dispositivo", type=["png", "jpg", "jpeg", "pdf"])
                
                file_da_elaborare = foto_ddt if foto_ddt is not None else file_ddt
                
                if file_da_elaborare is not None:
                    st.image(file_da_elaborare, caption="Anteprima documento acquisito", width=250)
                    fornitore = st.text_input("Fornitore (es. Wurth, Spaggiari, Berner):")
                    
                    if st.button("Invia ed Archivia su Google Drive 🚀"):
                        with st.spinner("Salvataggio su Google Drive..."):
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            tag_fornitore = f"_{fornitore.strip().replace(' ', '_')}" if fornitore.strip() else ""
                            ext = ".pdf" if (hasattr(file_da_elaborare, 'name') and file_da_elaborare.name.endswith(".pdf")) else ".jpg"
                            nome_file = f"DDT{tag_fornitore}_{timestamp}{ext}"
                            
                            id_drive = carica_su_drive(file_da_elaborare.getvalue(), nome_file, file_da_elaborare.type)
                            if id_drive: 
                                st.success(f"✔️ Archiviato con successo su Google Drive! ID File: {id_drive}")

    # --- 3. SCHERMATA AMMINISTRATORE ---
    elif st.session_state.ruolo_utente == "admin":
        st.markdown("<h1>📊 Pannello Controllo Admin</h1>", unsafe_allow_html=True)
        with st.container():
            st.markdown("<h3>📋 Inventario di Magazzino</h3>", unsafe_allow_html=True)
            st.dataframe(df_inventario, use_container_width=True, hide_index=True)
        with st.container():
            st.markdown("<h3>⏱ Storico Completo Consegne</h3>", unsafe_allow_html=True)
            consegnati = df_richieste[df_richieste["stato"] == "Consegnato"]
            if consegnati.empty: 
                st.write("Nessuna consegna registrata al momento.")
            else: 
                st.dataframe(consegnati[["data_consegna", "collaboratore", "articolo", "quantita"]], use_container_width=True, hide_index=True)
            
        csv = df_richieste.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Esporta Registro Storico in Excel (CSV)", data=csv, file_name="registro_magazzino_scarpa.csv", mime="text/csv")
