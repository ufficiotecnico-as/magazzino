import streamlit as st
import pandas as pd
from datetime import datetime
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io

# ==========================================
# CONFIGURAZIONE CONFIG E DRIVER
# ==========================================
PASSWORD_MAGAZZINIERE = "magazzino2026"
PASSWORD_ADMIN = "admin99"
URL_LOGO = "https://cspace.spaggiari.eu//pub/TVII0004/TVII0004-intestazione-nuova-senzaloghi.png?_t=1712923868"
ID_CARTELLA_DRIVE = "1T9KlJb4MFLvo3vK4XRmxRFK3wshPSP5m" # La tua cartella

st.set_page_config(page_title="Gestione Magazzino Scarpa", page_icon="🧺", layout="centered")

# Funzione per connettersi a Google Drive e caricare il file
def carica_su_drive(file_bytes, nome_file, mime_type):
    try:
        # Carica le credenziali dal file JSON locale
        creds = service_account.Credentials.from_service_account_file(
            'google_credentials.json', 
            scopes=['https://www.googleapis.com/auth/drive']
        )
        service = build('drive', 'v3', credentials=creds)
        
        file_metadata = {
            'name': nome_file,
            'parents': [ID_CARTELLA_DRIVE]
        }
        
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
        file_caricato = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return file_caricato.get('id')
    except Exception as e:
        st.error(f"Errore durante il caricamento su Google Drive: {e}")
        return None

# --- CSS INTERFACCIA ---
st.markdown("""
    <style>
        .stApp { background-color: #f8f9fa; }
        h1 { color: #1e3a8a !important; font-family: 'Segoe UI', sans-serif; font-weight: 700; text-align: center; margin-bottom: 25px !important; }
        h2, h3 { color: #2563eb !important; }
        div.stButton > button:first-child { background-color: #2563eb; color: white; border-radius: 8px; border: none; padding: 10px 20px; font-weight: 600; }
        div.stButton > button:first-child:hover { background-color: #1d4ed8; color: white; }
        [data-testid="stContainer"] { background-color: white; border: 1px solid #e5e7eb !important; border-radius: 12px !important; padding: 20px !important; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important; margin-bottom: 15px; }
    </style>
""", unsafe_allow_html=True)

# Inizializzazione Database in memoria
if "db_inventario" not in st.session_state:
    st.session_state.db_inventario = pd.DataFrame([
        {"id_articolo": "A001", "nome_articolo": "Guanti da lavoro", "giacenza_totale": 0},
        {"id_articolo": "A002", "nome_articolo": "Scarpe antinfortunistiche", "giacenza_totale": 0},
        {"id_articolo": "A003", "nome_articolo": "Occhiali protettivi", "giacenza_totale": 0}
    ])

if "db_richieste" not in st.session_state:
    st.session_state.db_richieste = pd.DataFrame(columns=["id_richiesta", "collaboratore", "articolo", "quantita", "stato", "data_richiesta", "data_consegna"])

if "ruolo_utente" not in st.session_state:
    st.session_state.ruolo_utente = None
if "utente_corrente" not in st.session_state:
    st.session_state.utente_corrente = ""

# --- LOGIN ---
if st.session_state.ruolo_utente is None:
    st.image(URL_LOGO, use_container_width=True)
    st.title("Gestione Magazzino Scarpa")
    with st.container():
        st.markdown("<h3 style='text-align: center; margin-top:0;'>🔑 Identificazione Utente</h3>", unsafe_allow_html=True)
        scelta_accesso = st.radio("Seleziona profilo:", ["Sono un Collaboratore", "Sono il Magazziniere / Admin"], label_visibility="collapsed")
        if scelta_accesso == "Sono un Collaboratore":
            nome_input = st.text_input("Nome e Cognome:")
            if st.button("Accedi all'area Richieste", use_container_width=True):
                if nome_input.strip():
                    st.session_state.ruolo_utente = "collaboratore"
                    st.session_state.utente_corrente = nome_input.strip()
                    st.rerun()
        else:
            password_input = st.text_input("Password:", type="password")
            if st.button("Verifica Password", use_container_width=True):
                if password_input == PASSWORD_MAGAZZINIERE:
                    st.session_state.ruolo_utente = "magazziniere"
                    st.rerun()
                elif password_input == PASSWORD_ADMIN:
                    st.session_state.ruolo_utente = "admin"
                    st.rerun()

# --- INTERFACCE UTENTE ---
else:
    st.image(URL_LOGO, use_container_width=True)
    st.sidebar.markdown(f"<h3 style='text-align:center;'>📦 Area {st.session_state.ruolo_utente.upper()}</h3>", unsafe_allow_html=True)
    if st.sidebar.button("🔒 Esci", use_container_width=True):
        st.session_state.ruolo_utente = None
        st.rerun()
        
    # --- COLLABORATORE ---
    if st.session_state.ruolo_utente == "collaboratore":
        st.title(f"👋 Benvenuto, {st.session_state.utente_corrente}")
        with st.container():
            lista_articoli = st.session_state.db_inventario["nome_articolo"].tolist()
            lista_articoli.append("Altro...")
            articolo_selezionato = st.selectbox("Seleziona l'articolo:", lista_articoli)
            articolo_finale = st.text_input("Specifica materiale:") if articolo_selezionato == "Altro..." else articolo_selezionato
            qta = st.number_input("Quantità:", min_value=1, step=1)
            if st.button("Invia Richiesta", use_container_width=True):
                nuovo_id = int(st.session_state.db_richieste["id_richiesta"].max()) + 1 if not st.session_state.db_richieste.empty else 1
                nuova_r = pd.DataFrame([{"id_richiesta": nuovo_id, "collaboratore": st.session_state.utente_corrente, "articolo": articolo_finale, "quantita": int(qta), "stato": "In attesa", "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M"), "data_consegna": ""}])
                st.session_state.db_richieste = pd.concat([st.session_state.db_richieste, nuova_r], ignore_index=True)
                st.success("Richiesta inviata!")

    # --- MAGAZZINIERE (Con funzione Foto DDT) ---
    elif st.session_state.ruolo_utente == "magazziniere":
        st.title("🚚 Pannello Gestione Operativa")
        tab_consegne, tab_carico, tab_ddt = st.tabs(["📋 Richieste da Consegnare", "➕ Carico Giacenze", "📸 Archivia Foto DDT"])
        
        with tab_consegne:
            in_attesa = st.session_state.db_richieste[st.session_state.db_richieste["stato"] == "In attesa"]
            if in_attesa.empty: st.info("Nessuna richiesta pendente.")
            for idx, row in in_attesa.iterrows():
                with st.container():
                    st.write(f"👤 **{row['collaboratore']}** chiede {row['quantita']}x **{row['articolo']}**")
                    if st.button("Marca come Consegnato ✔", key=f"cons_{row['id_richiesta']}", use_container_width=True):
                        filtro = st.session_state.db_inventario["nome_articolo"] == row['articolo']
                        if filtro.any():
                            st.session_state.db_richieste.loc[st.session_state.db_richieste["id_richiesta"] == row["id_richiesta"], "stato"] = "Consegnato"
                            st.session_state.db_inventario.loc[filtro, "giacenza_totale"] -= int(row['quantita'])
                            st.success("Consegnato!")
                            st.rerun()
                                
        with tab_carico:
            with st.container():
                st.markdown("### 🔧 Aggiungi pezzi a materiale esistente")
                art_da_caricare = st.selectbox("Seleziona l'articolo:", st.session_state.db_inventario["nome_articolo"].tolist())
                qta_da_aggiungere = st.number_input("Quantità arrivata:", min_value=1, step=1)
                if st.button("Esegui Carico Merce", use_container_width=True):
                    st.session_state.db_inventario.loc[st.session_state.db_inventario["nome_articolo"] == art_da_caricare, "giacenza_totale"] += qta_da_aggiungere
                    st.success("Giacenza aggiornata!")
            with st.container():
                st.markdown("### ✨ Registra un NUOVO articolo")
                nuovo_id_art = st.text_input("Codice Articolo:")
                nuovo_nome_art = st.text_input("Nome materiale:")
                nuovo_stock_art = st.number_input("Stock iniziale:", min_value=0, step=1)
                if st.button("Salva Nuovo Articolo", use_container_width=True):
                    nuovo_p = pd.DataFrame([{"id_articolo": nuovo_id_art, "nome_articolo": nuovo_nome_art, "giacenza_totale": int(nuovo_stock_art)}])
                    st.session_state.db_inventario = pd.concat([st.session_state.db_inventario, nuovo_p], ignore_index=True)
                    st.success("Articolo inserito!")
                    
        # NUOVA SCHEDA: FOTO DDT
        with tab_ddt:
            st.subheader("📷 Carica Foto o Scansione del DDT")
            st.write("Usa la fotocamera del telefono o seleziona un file per salvarlo direttamente su Google Drive.")
            
            # Attiva la fotocamera del telefono/PC nativamente
            foto_ddt = st.camera_input("Scatta la foto al DDT")
            
            # Opzione alternativa se preferisce caricare un file esistente
            file_ddt = st.file_uploader("Oppure seleziona un file dal dispositivo", type=["png", "jpg", "jpeg", "pdf"])
            
            file_da_elaborare = foto_ddt if foto_ddt is not None else file_ddt
            
            if file_da_elaborare is not None:
                st.image(file_da_elaborare, caption="Anteprima documento acquisito", width=300)
                fornitore = st.text_input("Inserisci il nome del Fornitore (Opzionale):", placeholder="es. Spaggiari, Wurth...")
                
                if st.button("Invia ed Archivia su Google Drive 🚀", use_container_width=True):
                    with st.spinner("Salvataggio in corso su Google Drive..."):
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        tag_fornitore = f"_{fornitore.strip().replace(' ', '_')}" if fornitore.strip() else ""
                        
                        # Determina estensione e nome file
                        estensione = ".pdf" if file_da_elaborare.name.endswith(".pdf") else ".jpg"
                        nome_file_finale = f"DDT{tag_fornitore}_{timestamp}{estensione}"
                        
                        # Esegui l'upload su Drive
                        bytes_data = file_da_elaborare.getvalue()
                        id_drive = carica_su_drive(bytes_data, nome_file_finale, file_da_elaborare.type)
                        
                        if id_drive:
                            st.success(f"✔️ Documento archiviato con successo su Drive come: {nome_file_finale}")
                        else:
                            st.error("Riprova, si è verificato un problema di connessione con Google.")

    # --- ADMIN ---
    elif st.session_state.ruolo_utente == "admin":
        st.title("📊 Controllo Amministratore")
        st.subheader("📋 Giacenza Attuale")
        st.dataframe(st.session_state.db_inventario, use_container_width=True, hide_index=True)
        st.subheader("⏱ Registro Consegne")
        consegnati = st.session_state.db_richieste[st.session_state.db_richieste["stato"] == "Consegnato"]
        if not consegnati.empty: st.dataframe(consegnati[["data_consegna", "collaboratore", "articolo", "quantita"]], use_container_width=True, hide_index=True)
        csv = st.session_state.db_richieste.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Scarica Report Excel", data=csv, file_name="registro_magazzino.csv", mime="text/csv", use_container_width=True)
