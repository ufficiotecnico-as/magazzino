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
# DIZIONARIO DELLE PASSWORD DI SICUREZZA
# ==========================================
PASSWORD_MAP = {
    "ata2026": "Personale ATA",
    "officina2026": "Officina",
    "tecnici2026": "Tecnici Informatici"
}
PASSWORD_ADMIN = "admin99"

URL_LOGO = "https://cspace.spaggiari.eu//pub/TVII0004/TVII0004-intestazione-nuova-senzaloghi.png?_t=1712923868"
ID_CARTELLA_DRIVE_PRINCIPALE = "1bVTs2smvVJONs2oIAFZdDvX9pYDK9MZT"
LISTA_MAGAZZINI = ["Personale ATA", "Officina", "Tecnici Informatici"]

st.set_page_config(page_title="Gestione Magazzini Scarpa", page_icon="🧺", layout="wide")

# ==========================================
# FUNZIONE DI CARICAMENTO SU GOOGLE DRIVE
# ==========================================
def carica_su_drive(file_bytes, nome_file, mime_type, nome_magazzino):
    if not GOOGLE_LIBS_AVAILABLE:
        st.error("⚠️ Errore: Le librerie Google non sono installate.")
        return None
    try:
        if "google_creds" in st.secrets:
            creds_dict = dict(st.secrets["google_creds"])
            if "\\n" in creds_dict["private_key"]:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            creds = service_account.Credentials.from_service_account_info(
                creds_dict, scopes=['https://www.googleapis.com/auth/drive']
            )
        elif os.path.exists('google_credentials.json'):
            creds = service_account.Credentials.from_service_account_file(
                'google_credentials.json', scopes=['https://www.googleapis.com/auth/drive']
            )
        else:
            st.error("❌ Credenziali di Google non trovate.")
            return None

        service = build('drive', 'v3', credentials=creds)
        
        nome_sottocartella = f"DDT_{nome_magazzino.replace(' ', '_')}"
        query = f"name='{nome_sottocartella}' and '{ID_CARTELLA_DRIVE_PRINCIPALE}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        risultato = service.files().list(q=query, spaces='drive', supportsAllDrives=True, includeItemsFromTrashed=False).execute()
        files = risultato.get('files', [])
        
        if files:
            id_cartella_destinazione = files[0]['id']
        else:
            meta_cartella = {
                'name': nome_sottocartella,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [ID_CARTELLA_DRIVE_PRINCIPALE]
            }
            cartella_creata = service.files().create(body=meta_cartella, fields='id', supportsAllDrives=True).execute()
            id_cartella_destinazione = cartella_creata.get('id')

        file_metadata = {
            'name': nome_file, 
            'parents': [id_cartella_destinazione]
        }
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
        file_caricato = service.files().create(
            body=file_metadata, media_body=media, fields='id', supportsAllDrives=True
        ).execute()
        
        return file_caricato.get('id')
    except Exception as e:
        st.error(f"❌ Errore Google Drive: {e}")
        return None

# ==========================================
# STILE UX/UI
# ==========================================
st.markdown("""
    <style>
        .stApp { background-color: #f1f5f9 !important; color: #0f172a !important; font-family: 'Inter', sans-serif; }
        [data-testid="stMainBlockContainer"] { max-width: 1150px; margin: 0 auto; padding-top: 2rem; }
        h1 { color: #0f172a !important; font-family: 'Montserrat', sans-serif; font-weight: 800 !important; text-align: center; margin-bottom: 30px !important; }
        h2, h3, h4, label, [data-testid="stWidgetLabel"] p { color: #1e293b !important; font-weight: 700 !important; }
        [data-testid="stContainer"] { background-color: #ffffff !important; border: 1px solid #e2e8f0 !important; border-radius: 16px !important; padding: 28px !important; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important; margin-bottom: 20px; }
        div.stButton > button:first-child { background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%) !important; color: #ffffff !important; border-radius: 10px !important; border: none !important; padding: 12px 24px !important; font-weight: 600 !important; width: 100%; }
        div.stButton > button:first-child:hover { background: #0f172a !important; transform: translateY(-1px); }
        [data-testid="stSidebar"] { background-color: #ffffff !important; border-right: 1px solid #e2e8f0; }
        footer {visibility: hidden;}
        [data-testid="stHeader"] {background: transparent;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# INIZIALIZZAZIONE DATABASE
# ==========================================
if "db_inventario" not in st.session_state:
    st.session_state.db_inventario = pd.DataFrame([
        {"magazzino": "Personale ATA", "id_articolo": "8001234567890", "nome_articolo": "Camice lavoro", "giacenza_totale": 20},
        {"magazzino": "Officina", "id_articolo": "8009876543210", "nome_articolo": "Chiave inglese 13mm", "giacenza_totale": 15},
        {"magazzino": "Tecnici Informatici", "id_articolo": "8005555555555", "nome_articolo": "Cavo Ethernet 5m", "giacenza_totale": 40}
    ])

if "db_richieste" not in st.session_state:
    st.session_state.db_richieste = pd.DataFrame(columns=["id_richiesta", "magazzino", "collaboratore", "articolo", "quantita", "stato", "data_richiesta", "data_consegna"])

if "db_approvvigionamenti" not in st.session_state:
    st.session_state.db_approvvigionamenti = pd.DataFrame(columns=["id_acquisto", "magazzino", "articolo", "quantita_richiesta", "stato", "data_richiesta"])

if "ruolo_utente" not in st.session_state:
    st.session_state.ruolo_utente = None
if "utente_corrente" not in st.session_state:
    st.session_state.utente_corrente = ""
if "magazzino_selezionato" not in st.session_state:
    st.session_state.magazzino_selezionato = None

# --- SCHERMATA LOGIN ---
if st.session_state.ruolo_utente is None:
    st.image(URL_LOGO, use_container_width=True)
    st.markdown("<h1>Gestione Magazzini Centralizzata</h1>", unsafe_allow_html=True)
    
    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        with st.container():
            st.markdown("<h3 style='text-align: center; margin-top:0;'>🔑 Seleziona Profilo</h3>", unsafe_allow_html=True)
            scelta_accesso = st.radio("", ["Sono un Collaboratore (Fai una Richiesta)", "Sono un Magazziniere / Admin"], label_visibility="collapsed")
            st.markdown("<br>", unsafe_allow_html=True)
            
            if scelta_accesso == "Sono un Collaboratore (Fai una Richiesta)":
                nome_input = st.text_input("Inserisci il tuo Nome e Cognome:")
                if st.button("Accedi all'area Richieste"):
                    if not nome_input.strip():
                        st.error("⚠️ Inserisci il tuo nome per continuare.")
                    else:
                        st.session_state.ruolo_utente = "collaboratore"
                        st.session_state.utente_corrente = nome_input.strip()
                        st.rerun()
                        
            elif scelta_accesso == "Sono un Magazziniere / Admin":
                password_input = st.text_input("Inserisci la tua password personale di sblocco:", type="password")
                if st.button("Verifica Credenziali"):
                    if password_input in PASSWORD_MAP:
                        st.session_state.ruolo_utente = "magazziniere"
                        st.session_state.magazzino_selezionato = PASSWORD_MAP[password_input]
                        st.rerun()
                    elif password_input == PASSWORD_ADMIN:
                        st.session_state.ruolo_utente = "admin"
                        st.rerun()
                    else:
                        st.error("❌ Password errata o non associata ad alcun magazzino. Riprova.")

# --- INTERFACCE ABILITATE ---
else:
    st.image(URL_LOGO, use_container_width=True)
    
    df_inventario = st.session_state.db_inventario
    df_richieste = st.session_state.db_richieste
    df_approv = st.session_state.db_approvvigionamenti

    with st.sidebar:
        st.markdown(f"<h3>🧺 Area {st.session_state.ruolo_utente.upper()}</h3>", unsafe_allow_html=True)
        if st.session_state.ruolo_utente == "magazziniere":
            st.info(f"📍 Magazzino: **{st.session_state.magazzino_selezionato}**")
        elif st.session_state.ruolo_utente == "admin":
            st.success("👑 Accesso Totale Admin")
        elif st.session_state.utente_corrente:
            st.write(f"👤 Utente: {st.session_state.utente_corrente}")
            
        st.write("---")
        if st.button("🔒 Esci / Cambia Utente"):
            st.session_state.ruolo_utente = None
            st.session_state.utente_corrente = ""
            st.session_state.magazzino_selezionato = None
            st.rerun()

    # --- 1. SCHERMATA COLLABORATORE ---
    if st.session_state.ruolo_utente == "collaboratore":
        st.markdown(f"<h1>👋 Benvenuto, {st.session_state.utente_corrente}</h1>", unsafe_allow_html=True)
        
        with st.container():
            st.markdown("<h3>📋 Nuova Richiesta Materiale</h3>", unsafe_allow_html=True)
            target_magazzino = st.selectbox("A quale magazzino vuoi inviare la richiesta?", LISTA_MAGAZZINI)
            
            articoli_filtrati = df_inventario[df_inventario["magazzino"] == target_magazzino]["nome_articolo"].tolist()
            articoli_filtrati.append("Altro...")
            
            articolo_selezionato = st.selectbox("Seleziona cosa ti serve:", articoli_filtrati)
            articolo_finale = st.text_input("Specifica il materiale a mano:") if articolo_selezionato == "Altro..." else articolo_selezionato
            qta = st.number_input("Quantità necessaria:", min_value=1, step=1)
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Invia Ordine in Magazzino"):
                if articolo_selezionato == "Altro..." and not articolo_finale.strip():
                    st.error("⚠️ Specifica il nome del materiale.")
                else:
                    nuovo_id = int(df_richieste["id_richiesta"].max()) + 1 if not df_richieste.empty else 1
                    nuova_r = pd.DataFrame([{
                        "id_richiesta": nuovo_id, "magazzino": target_magazzino, "collaboratore": st.session_state.utente_corrente, 
                        "articolo": articolo_finale, "quantita": int(qta), "stato": "In attesa", 
                        "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M"), "data_consegna": ""
                    }])
                    st.session_state.db_richieste = pd.concat([df_richieste, nuova_r], ignore_index=True)
                    st.success(f"✔️ Richiesta inoltrata al magazzino ({target_magazzino}) con successo!")

    # --- 2. SCHERMATA MAGAZZINIERE ---
    elif st.session_state.ruolo_utente == "magazziniere":
        mag_corrente = st.session_state.magazzino_selezionato
        st.markdown(f"<h1>🚚 Pannello Operativo: {mag_corrente}</h1>", unsafe_allow_html=True)
        
        tab_carico, tab_consegne, tab_rifornisci, tab_ddt = st.tabs([
            "⚡ CARICO AUTOMATICO BARCODE", "📋 Richieste in Arrivo", "🛒 Richiedi Rifornimenti a Admin", "📸 Archivia Foto DDT"
        ])
        
        # TAB 1: CARICO AUTOMATICO CON LETTORE / PISTOLA BARCODE
        with tab_carico:
            st.markdown("### ⚡ Modalità Flusso Continuo Hardware")
            st.caption("Fai clic sul campo sotto e spara con il lettore barcode. L'app registrerà l'articolo e si resetterà da sola.")
            
            # Parametri di input per il flusso
            moltiplicatore_qta = st.number_input("Quantità da caricare per ogni scansione (Moltiplicatore):", min_value=1, value=1, step=1)
            
            # Campo principale in cui la pistola scrive e preme "Invio" automaticamente
            barcode_input = st.text_input("🎯 SPARA IL BARCODE QUI (Focus attivo):", value="", key="barcode_laser_input")
            
            if barcode_input:
                barcode_pulito = barcode_input.strip()
                
                # Cerca se il codice a barre esiste già nel magazzino corrente
                filtro_codice = (df_inventario["id_articolo"] == barcode_pulito) & (df_inventario["magazzino"] == mag_corrente)
                
                if filtro_codice.any():
                    # L'articolo esiste: incremento automatico immediato senza chiedere nulla
                    st.session_state.db_inventario.loc[filtro_codice, "giacenza_totale"] += moltiplicatore_qta
                    nome_art_colpito = df_inventario.loc[filtro_codice, "nome_articolo"].values[0]
                    nuova_giac_colpita = st.session_state.db_inventario.loc[filtro_codice, "giacenza_totale"].values[0]
                    st.success(f"➕ Rilevato: **{nome_art_colpito}**. Caricati {moltiplicatore_qta} pz. Nuova giacenza totale: {nuova_giac_colpita}")
                    
                    # Trucco Streamlit: Svuotiamo l'input per la prossima scansione immediata
                    st.session_state.barcode_laser_input = ""
                    st.rerun()
                else:
                    # L'articolo è nuovo: chiediamo al volo il nome per censirlo nel sistema
                    st.warning(f"⚠️ Il codice barcode `{barcode_pulito}` è NUOVO per questo magazzino. Registralo adesso:")
                    with st.form("form_nuovo_barcode"):
                        nome_nuovo_censito = st.text_input("Nome dell'articolo/materiale:")
                        stock_iniziale = st.number_input("Giacenza iniziale da assegnare:", min_value=1, value=int(moltiplicatore_qta))
                        
                        if st.form_submit_button("Censisci e Salva in Inventario"):
                            if nome_nuovo_censito.strip():
                                nuovo_item = pd.DataFrame([{
                                    "magazzino": mag_corrente,
                                    "id_articolo": barcode_pulito,
                                    "nome_articolo": nome_nuovo_censito.strip(),
                                    "giacenza_totale": int(stock_iniziale)
                                }])
                                st.session_state.db_inventario = pd.concat([df_inventario, nuovo_item], ignore_index=True)
                                st.success(f"✔️ Articolo `{nome_nuovo_censito}` inserito e mappato sul barcode `{barcode_pulito}`!")
                                st.session_state.barcode_laser_input = ""
                                st.rerun()
                            else:
                                st.error("Inserisci un nome valido.")

            st.write("---")
            st.markdown("#### 📦 Stato Attuale Giacenze del tuo Reparto")
            df_mio_mag = st.session_state.db_inventario[st.session_state.db_inventario["magazzino"] == mag_corrente]
            st.dataframe(df_mio_mag[["id_articolo", "nome_articolo", "giacenza_totale"]], use_container_width=True, hide_index=True)

        with tab_consegne:
            richieste_mie = df_richieste[(df_richieste["stato"] == "In attesa") & (df_richieste["magazzino"] == mag_corrente)]
            if richieste_mie.empty:
                st.info(f"✨ Nessuna richiesta da evadere per il magazzino {mag_corrente}.")
            else:
                for idx, row in richieste_mie.iterrows():
                    with st.container():
                        c1, c2, c3 = st.columns([1, 4, 2])
                        with c1: st.write(f"**ID #{row['id_richiesta']}**")
                        with c2: st.markdown(f"👤 **{row['collaboratore']}**<br>Richiede: <span style='color:#1e3a8a;font-weight:bold;'>{row['quantita']}x {row['articolo']}</span>", unsafe_allow_html=True)
                        with c3:
                            if st.button("Consegna ✔", key=f"btn_{row['id_richiesta']}"):
                                filtro = (df_inventario["nome_articolo"] == row['articolo']) & (df_inventario["magazzino"] == mag_corrente)
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
                                    st.error("⚠️ Articolo personalizzato. Censiscilo prima di consegnarlo.")

        with tab_rifornisci:
            st.markdown("### 🛒 Invia una richiesta di acquisto o riassortimento all'Admin")
            with st.container():
                materiale_urgente = st.text_input("Quale materiale manca o va acquistato?")
                qta_urgente = st.number_input("Quantità confezioni/pezzi da ordinare:", min_value=1, step=1)
                
                if st.button("Invia Richiesta di Approvvigionamento"):
                    if not materiale_urgente.strip():
                        st.error("Inserisci il nome del materiale da richiedere.")
                    else:
                        nuovo_id_acquisto = int(df_approv["id_acquisto"].max()) + 1 if not df_approv.empty else 1
                        nuovo_ordine = pd.DataFrame([{
                            "id_acquisto": nuovo_id_acquisto,
                            "magazzino": mag_corrente,
                            "articolo": materiale_urgente.strip(),
                            "quantita_richiesta": int(qta_urgente),
                            "stato": "In attesa di approvazione Admin",
                            "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M")
                        }])
                        st.session_state.db_approvvigionamenti = pd.concat([df_approv, nuovo_ordine], ignore_index=True)
                        st.success("🚀 Richiesta inoltrata correttamente al Super Admin!")
                        st.rerun()

        with tab_ddt:
            st.markdown(f"### 📸 Archiviazione DDT - Sottocartella: DDT_{mag_corrente.replace(' ', '_')}")
            with st.container():
                file_ddt = st.file_uploader("Scatta una foto al DDT o seleziona un file", type=["png", "jpg", "jpeg", "pdf"], key="ddt_uploader")
                
                if file_ddt is not None:
                    if not file_ddt.name.endswith(".pdf"):
                        st.image(file_ddt, caption="Anteprima documento", width=250)
                    fornitore = st.text_input("Fornitore:")
                    if st.button("Invia ed Archivia su Google Drive 🚀"):
                        with st.spinner("Salvataggio in corso..."):
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            tag_fornitore = f"_{fornitore.strip().replace(' ', '_')}" if fornitore.strip() else ""
                            ext = ".pdf" if file_ddt.name.endswith(".pdf") else ".jpg"
                            nome_file = f"DDT_{mag_corrente.replace(' ', '_')}{tag_fornitore}_{timestamp}{ext}"
                            
                            id_drive = carica_su_drive(file_ddt.getvalue(), nome_file, file_ddt.type, mag_corrente)
                            if id_drive: 
                                st.success(f"✔️ Archiviato sotto la cartella di {mag_corrente}!")

    # --- 3. SCHERMATA AMMINISTRATORE ---
    elif st.session_state.ruolo_utente == "admin":
        st.markdown("<h1>📊 Pannello Controllo Globale Admin</h1>", unsafe_allow_html=True)
        
        tab_admin_storico, tab_admin_acquisti = st.tabs(["📊 Inventari & Storico Consegne", "🛒 Approvazioni Ordini Rifornimento"])
        
        with tab_admin_storico:
            filtro_admin = st.selectbox("🔍 Scegli quale magazzino esaminare (o Mostra Tutto):", ["Mostra Tutto"] + LISTA_MAGAZZINI)
            df_inv_visualizza = df_inventario if filtro_admin == "Mostra Tutto" else df_inventario[df_inventario["magazzino"] == filtro_admin]
            df_req_visualizza = df_richieste if filtro_admin == "Mostra Tutto" else df_richieste[df_richieste["magazzino"] == filtro_admin]
            
            with st.container():
                st.markdown(f"<h3>📋 Inventario di Magazzino ({filtro_admin})</h3>", unsafe_allow_html=True)
                st.dataframe(df_inv_visualizza, use_container_width=True, hide_index=True)
                
            with st.container():
                st.markdown(f"<h3>⏱ Storico Completo Consegne ({filtro_admin})</h3>", unsafe_allow_html=True)
                consegnati = df_req_visualizza[df_req_visualizza["stato"] == "Consegnato"]
                if consegnati.empty: 
                    st.write("Nessuna consegna registrata per questo filtro.")
                else: 
                    st.dataframe(consegnati[["data_consegna", "magazzino", "collaboratore", "articolo", "quantita"]], use_container_width=True, hide_index=True)
                
            csv = df_req_visualizza.to_csv(index=False).encode('utf-8')
            st.download_button(label="📥 Esporta Questo Registro in Excel (CSV)", data=csv, file_name="report_globale_magazzini.csv", mime="text/csv")

        with tab_admin_acquisti:
            st.markdown("### 🛒 Richieste di Approvvigionamento dai Magazzinieri")
            acquisti_pendenti = df_approv[df_approv["stato"] == "In attesa di approvazione Admin"]
            
            if acquisti_pendenti.empty:
                st.info("✨ Non ci sono richieste di acquisto in sospeso dai magazzini.")
            else:
                for idx, row in acquisti_pendenti.iterrows():
                    with st.container():
                        c1, c2, c3 = st.columns([2, 3, 2])
                        with c1:
                            st.markdown(f"📦 Magazzino: **{row['magazzino']}**<br><small>Data: {row['data_richiesta']}</small>", unsafe_allow_html=True)
                        with c2:
                            st.markdown(f"Articolo Richiesto: <span style='color:#b91c1c; font-weight:bold;'>{row['quantita_richiesta']}x {row['articolo']}</span>", unsafe_allow_html=True)
                        with c3:
                            if st.button("Approva ed Ordina ed Aggiorna Giacenza ✔", key=f"appr_{row['id_acquisto']}"):
                                st.session_state.db_approvvigionamenti.loc[st.session_state.db_approvvigionamenti["id_acquisto"] == row["id_acquisto"], "stato"] = "Approvato e Caricato"
                                
                                filtro_inventario = (df_inventario["nome_articolo"] == row["articolo"]) & (df_inventario["magazzino"] == row["magazzino"])
                                if filtro_inventario.any():
                                    st.session_state.db_inventario.loc[filtro_inventario, "giacenza_totale"] += int(row["quantita_richiesta"])
                                else:
                                    nuovo_id_generato = f"NEW_{row['id_acquisto']}"
                                    nuovo_item = pd.DataFrame([{
                                        "magazzino": row["magazzino"], "id_articolo": nuovo_id_generato, 
                                        "nome_articolo": row["articolo"], "giacenza_totale": int(row["quantita_richiesta"])
                                    }])
                                    st.session_state.db_inventario = pd.concat([st.session_state.db_inventario, nuovo_item], ignore_index=True)
                                
                                st.success("Ordine Approvato! Lo stock è stato caricato nel magazzino.")
                                st.rerun()
