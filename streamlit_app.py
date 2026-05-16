import streamlit as st
import pandas as pd
from datetime import datetime
import io
import os
import streamlit.components.v1 as components

# Controllo e importazione delle librerie ufficiali di Google
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False

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

# --- STILE UX/UI ---
st.markdown("""
    <style>
        .stApp { background-color: #f1f5f9 !important; color: #0f172a !important; font-family: 'Inter', sans-serif; }
        [data-testid="stMainBlockContainer"] { max-width: 1150px; margin: 0 auto; padding-top: 2rem; }
        h1 { color: #0f172a !important; font-family: 'Montserrat', sans-serif; font-weight: 800 !important; text-align: center; margin-bottom: 30px !important; }
        h2, h3, h4, label, [data-testid="stWidgetLabel"] p { color: #1e293b !important; font-weight: 700 !important; }
        [data-testid="stContainer"] { background-color: #ffffff !important; border: 1px solid #e2e8f0 !important; border-radius: 16px !important; padding: 28px !important; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important; margin-bottom: 20px; }
        div.stButton > button:first-child { background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%) !important; color: #ffffff !important; border-radius: 10px !important; border: none !important; padding: 12px 24px !important; font-weight: 600 !important; width: 100%; }
        [data-testid="stSidebar"] { background-color: #ffffff !important; border-right: 1px solid #e2e8f0; }
        footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- FUNZIONE GOOGLE DRIVE ---
def carica_su_drive(file_bytes, nome_file, mime_type, nome_magazzino):
    if not GOOGLE_LIBS_AVAILABLE: 
        st.error("Librerie Google non disponibili.")
        return None
    try:
        if "google_creds" in st.secrets:
            creds_dict = dict(st.secrets["google_creds"])
            if "\\n" in creds_dict["private_key"]:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=['https://www.googleapis.com/auth/drive'])
        else: 
            st.error("Credenziali Google segrete non trovate nel pannello Streamlit.")
            return None
            
        service = build('drive', 'v3', credentials=creds)
        nome_sottocartella = f"DDT_{nome_magazzino.replace(' ', '_')}"
        query = f"name='{nome_sottocartella}' and '{ID_CARTELLA_DRIVE_PRINCIPALE}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        
        risultato = service.files().list(q=query, spaces='drive', supportsAllDrives=True, includeItemsFromTrashed=False).execute()
        files = risultato.get('files', [])
        
        if files:
            id_cartella = files[0]['id']
        else:
            meta_cartella = {
                'name': nome_sottocartella,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [ID_CARTELLA_DRIVE_PRINCIPALE]
            }
            id_cartella = service.files().create(body=meta_cartella, fields='id', supportsAllDrives=True).execute().get('id')
        
        meta_file = {
            'name': nome_file, 
            'parents': [id_cartella]
        }
        
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
        file_creato = service.files().create(body=meta_file, media_body=media, fields='id', supportsAllDrives=True).execute()
        return file_creato.get('id')
    except Exception as e:
        st.error(f"Errore durante l'invio a Google Drive: {e}")
        return None

# --- DATABASE INIZIALIZZAZIONE ---
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
if "ruolo_utente" not in st.session_state: st.session_state.ruolo_utente = None
if "utente_corrente" not in st.session_state: st.session_state.utente_corrente = ""
if "magazzino_selezionato" not in st.session_state: st.session_state.magazzino_selezionato = None
if "scanned_code" not in st.session_state: st.session_state.scanned_code = ""

# --- INTERCETTATORE DI QUERY STRING ---
# Estrae in modo nativo e sicuro il codice passato dall'URL generato dalla chiamata Fetch/Redirect di JS
query_params = st.query_params
if "barcode" in query_params:
    st.session_state.scanned_code = query_params["barcode"].strip()
    # Pulisce immediatamente l'interfaccia per evitare loop infiniti al prossimo aggiornamento
    st.query_params.clear()

# --- INTERFACCIA LOGIN ---
if st.session_state.ruolo_utente is None:
    st.image(URL_LOGO, use_container_width=True)
    st.markdown("<h1>Gestione Magazzini Centralizzata</h1>", unsafe_allow_html=True)
    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        with st.container():
            scelta_accesso = st.radio("", ["Sono un Collaboratore (Fai una Richiesta)", "Sono un Magazziniere / Admin"], label_visibility="collapsed")
            if scelta_accesso == "Sono un Collaboratore (Fai una Richiesta)":
                nome_input = st.text_input("Inserisci il tuo Nome e Cognome:")
                if st.button("Accedi all'area Richieste"):
                    if nome_input.strip():
                        st.session_state.ruolo_utente = "collaboratore"
                        st.session_state.utente_corrente = nome_input.strip()
                        st.rerun()
            else:
                password_input = st.text_input("Password di sblocco:", type="password")
                if st.button("Verifica Credenziali"):
                    if password_input in PASSWORD_MAP:
                        st.session_state.ruolo_utente = "magazziniere"
                        st.session_state.magazzino_selezionato = PASSWORD_MAP[password_input]
                        st.rerun()
                    elif password_input == PASSWORD_ADMIN:
                        st.session_state.ruolo_utente = "admin"
                        st.rerun()
                    else: st.error("❌ Password errata.")
else:
    st.image(URL_LOGO, use_container_width=True)
    df_inventario = st.session_state.db_inventario
    df_richieste = st.session_state.db_richieste
    df_approv = st.session_state.db_approvvigionamenti

    with st.sidebar:
        st.markdown(f"<h3>🧺 Area {st.session_state.ruolo_utente.upper()}</h3>", unsafe_allow_html=True)
        if st.session_state.ruolo_utente == "magazziniere": st.info(f"📍 Magazzino: **{st.session_state.magazzino_selezionato}**")
        if st.button("🔒 Esci / Cambia Utente"):
            st.session_state.ruolo_utente = None
            st.session_state.scanned_code = ""
            st.rerun()

    # --- AREA COLLABORATORE ---
    if st.session_state.ruolo_utente == "collaboratore":
        st.markdown(f"<h1>👋 Benvenuto, {st.session_state.utente_corrente}</h1>", unsafe_allow_html=True)
        with st.container():
            target_magazzino = st.selectbox("A quale magazzino vuoi inviare la richiesta?", LISTA_MAGAZZINI)
            articoli_filtrati = df_inventario[df_inventario["magazzino"] == target_magazzino]["nome_articolo"].tolist() + ["Altro..."]
            articolo_selezionato = st.selectbox("Seleziona cosa ti serve:", articoli_filtrati)
            articolo_finale = st.text_input("Specifica il materiale a mano:") if articolo_selezionato == "Altro..." else articolo_selezionato
            qta = st.number_input("Quantità necessaria:", min_value=1, step=1)
            if st.button("Invia Ordine in Magazzino"):
                nuovo_id = int(df_richieste["id_richiesta"].max()) + 1 if not df_richieste.empty else 1
                nuova_r = pd.DataFrame([{"id_richiesta": nuovo_id, "magazzino": target_magazzino, "collaboratore": st.session_state.utente_corrente, "articolo": articolo_finale, "quantita": int(qta), "stato": "In attesa", "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M"), "data_consegna": ""}])
                st.session_state.db_richieste = pd.concat([df_richieste, nuova_r], ignore_index=True)
                st.success("✔️ Richiesta inoltrata!")

    # --- AREA MAGAZZINIERE ---
    elif st.session_state.ruolo_utente == "magazziniere":
        mag_corrente = st.session_state.magazzino_selezionato
        st.markdown(f"<h1>🚚 Pannello Operativo: {mag_corrente}</h1>", unsafe_allow_html=True)
        
        tab_carico, tab_consegne, tab_rifornisci, tab_ddt = st.tabs(["📷 SCANNER REAL-TIME", "📋 Richieste", "🛒 Ordini", "📸 DDT"])
        
        with tab_carico:
            st.markdown("### 🎯 Inquadra il Codice a Barre")
            moltiplicatore_qta = st.number_input("Pezzi da aggiungere a ogni scansione:", min_value=1, value=1, step=1)
            
            # CANALE DI TRASMISSIONE ASINCRONO VIA URL RE-INJECTION
            scanner_javascript_html = """
            <div style="background: #ffffff; padding: 12px; border-radius: 12px; border: 2px dashed #475569; text-align: center;">
                <div id="camera-frame" style="width: 100%; max-width: 480px; margin: 0 auto; border-radius: 8px; overflow: hidden; background: #000;"></div>
                <p id="scanner-output" style="font-family: system-ui, sans-serif; color: #1e293b; font-weight: 800; margin-top: 12px; font-size: 1.1rem; background: #e2e8f0; padding: 8px; border-radius: 6px;">📸 Fotocamera attiva - Centra il codice</p>
            </div>
            
            <script src="https://unpkg.com/html5-qrcode"></script>
            <script>
                let qrboxFunction = function(viewfinderWidth, viewfinderHeight) {
                    let minEdgePercentage = 0.85; 
                    let boxWidth = Math.floor(viewfinderWidth * minEdgePercentage);
                    let boxHeight = Math.floor(boxWidth / 3.0); 
                    return { width: boxWidth, height: boxHeight };
                }

                const html5QrcodeScanner = new Html5Qrcode("camera-frame");
                const config = { 
                    fps: 25, 
                    qrbox: qrboxFunction,
                    experimentalFeatures: { useBarCodeDetectorIfSupported: true },
                    formatsToSupport: [ 
                        Html5QrcodeSupportedFormats.EAN_13, 
                        Html5QrcodeSupportedFormats.EAN_8, 
                        Html5QrcodeSupportedFormats.CODE_128, 
                        Html5QrcodeSupportedFormats.CODE_39 
                    ]
                };
                
                function onScanSuccess(decodedText, decodedResult) {
                    if (navigator.vibrate) navigator.vibrate(200);
                    document.getElementById("scanner-output").innerText = "🎯 LETTO: " + decodedText;
                    
                    // Forza l'aggiornamento sicuro dei dati ricaricando l'app con il parametro pulito nell'URL di livello superiore
                    let currentUrl = window.parent.location.href.split('?')[0];
                    window.parent.location.href = currentUrl + "?barcode=" + encodeURIComponent(decodedText);
                }

                Html5Qrcode.getCameras().then(devices => {
                    if (devices && devices.length > 0) {
                        html5QrcodeScanner.start({ facingMode: "environment" }, config, onScanSuccess)
                        .catch(err => { document.getElementById("scanner-output").innerText = "⚠️ Errore fotocamera."; });
                    }
                }).catch(err => { document.getElementById("scanner-output").innerText = "Inizializzazione fotocamera..."; });
            </script>
            """
            
            # Mostra la videocamera a schermo
            components.html(scanner_javascript_html, height=340, scrolling=False)
            
            # Campo manuale ausiliario sempre pronto
            manual_input = st.text_input("Inserimento manuale alternativo (Tastiera / Scanner USB):", value="")
            if manual_input.strip():
                st.session_state.scanned_code = manual_input.strip()

            # --- ELABORAZIONE DATI ---
            if st.session_state.scanned_code:
                codice_pulito = st.session_state.scanned_code
                st.markdown(f"📥 **Codice letto dal sistema:** `{codice_pulito}`")
                
                filtro_art = (df_inventario["id_articolo"] == codice_pulito) & (df_inventario["magazzino"] == mag_corrente)
                
                if filtro_art.any():
                    st.session_state.db_inventario.loc[filtro_art, "giacenza_totale"] += moltiplicatore_qta
                    nome_prod = df_inventario.loc[filtro_art, "nome_articolo"].values[0]
                    nuova_giac = st.session_state.db_inventario.loc[filtro_art, "giacenza_totale"].values[0]
                    
                    st.success(f"✔️ STOCK AGGIORNATO: **{nome_prod}** (+{moltiplicatore_qta}). Nuova giacenza: **{nuova_giac}**")
                    
                    if st.button("🔄 Cancella ed effettua una nuova scansione"):
                        st.session_state.scanned_code = ""
                        st.rerun()
                else:
                    st.warning(f"🆕 Il codice `{codice_pulito}` non appartiene a questo reparto. Registralo ora:")
                    with st.form("nuovo_censimento_veloce", clear_on_submit=True):
                        nome_nuovo_prodotto = st.text_input("Nome dell'Articolo da registrare:")
                        if st.form_submit_button("Salva nel Database"):
                            if nome_nuovo_prodotto.strip():
                                nuovo_p = pd.DataFrame([{
                                    "magazzino": mag_corrente, 
                                    "id_articolo": codice_pulito, 
                                    "nome_articolo": nome_nuovo_prodotto.strip(), 
                                    "giacenza_totale": int(moltiplicatore_qta)
                                }])
                                st.session_state.db_inventario = pd.concat([df_inventario, nuovo_p], ignore_index=True)
                                st.success(f"✔️ Articolo `{nome_nuovo_prodotto}` mappato con successo!")
                                st.session_state.scanned_code = ""
                                st.rerun()

            st.write("---")
            st.markdown("#### 📦 Stato Giacenze Reparto")
            st.dataframe(df_inventario[df_inventario["magazzino"] == mag_corrente][["id_articolo", "nome_articolo", "giacenza_totale"]], use_container_width=True, hide_index=True)

        # --- ALTRI TAB MAGAZZINIERE ---
        with tab_consegne:
            richieste_mie = df_richieste[(df_richieste["stato"] == "In attesa") & (df_richieste["magazzino"] == mag_corrente)]
            if richieste_mie.empty: st.info("Nessuna richiesta pendente.")
            for idx, row in richieste_mie.iterrows():
                with st.container():
                    c1, c2 = st.columns([5, 2])
                    c1.write(f"👤 **{row['collaboratore']}** vuole {row['quantita']}x *{row['articolo']}*")
                    if c2.button("Consegna ✔", key=f"evadi_{row['id_richiesta']}"):
                        filtro = (df_inventario["nome_articolo"] == row['articolo']) & (df_inventario["magazzino"] == mag_corrente)
                        if filtro.any() and df_inventario.loc[filtro, "giacenza_totale"].values[0] >= row['quantita']:
                            st.session_state.db_inventario.loc[filtro, "giacenza_totale"] -= row['quantita']
                            st.session_state.db_richieste.loc[st.session_state.db_richieste["id_richiesta"] == row["id_richiesta"], "stato"] = "Consegnato"
                            st.session_state.db_richieste.loc[st.session_state.db_richieste["id_richiesta"] == row["id_richiesta"], "data_consegna"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                            st.rerun()
                        else: st.error("Stock insufficiente o articolo da censire.")

        with tab_rifornisci:
            mat_urgente = st.text_input("Materiale da ordinare:")
            qta_urgente = st.number_input("Quantità:", min_value=1, step=1)
            if st.button("Invia Richiesta ad Admin"):
                nuovo_id_a = int(df_approv["id_acquisto"].max()) + 1 if not df_approv.empty else 1
                st.session_state.db_approvvigionamenti = pd.concat([df_approv, pd.DataFrame([{"id_acquisto": nuovo_id_a, "magazzino": mag_corrente, "articolo": mat_urgente, "quantita_richiesta": int(qta_urgente), "stato": "In attesa", "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M")}])], ignore_index=True)
                st.success("Inviata!")

        with tab_ddt:
            file_ddt = st.file_uploader("Carica foto DDT", type=["png", "jpg", "jpeg", "pdf"])
            fornitore = st.text_input("Fornitore:")
            if file_ddt and st.button("Archivia su Google Drive"):
                nome_f = f"DDT_{mag_corrente}_{fornitore}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                if carica_su_drive(file_ddt.getvalue(), nome_f, file_ddt.type, mag_corrente):
                    st.success("Archiviato su Drive con successo!")

    # --- AREA ADMIN ---
    elif st.session_state.ruolo_utente == "admin":
        st.markdown("<h1>👑 Controllo Globale Admin</h1>", unsafe_allow_html=True)
        tab_st, tab_ac = st.tabs(["📊 Inventari", "🛒 Approvazioni"])
        
        with tab_st:
            st.dataframe(df_inventario, use_container_width=True, hide_index=True)
        with tab_ac:
            pendenti = df_approv[df_approv["stato"] == "In attesa"]
            if pendenti.empty: st.info("Nessun ordine in attesa.")
            for idx, row in pendenti.iterrows():
                with st.container():
                    st.write(f"🏢 {row['magazzino']} chiede {row['quantita_richiesta']}x {row['articolo']}")
                    if st.button("Approva e Carica", key=f"app_{row['id_acquisto']}"):
                        st.session_state.db_approvvigionamenti.loc[df_approv["id_acquisto"] == row["id_acquisto"], "stato"] = "Approvato"
                        filtro = (df_inventario["nome_articolo"] == row["articolo"]) & (df_inventario["magazzino"] == row["magazzino"])
                        if filtro.any(): st.session_state.db_inventario.loc[filtro, "giacenza_totale"] += row["quantita_richiesta"]
                        else: st.session_state.db_inventario = pd.concat([df_inventario, pd.DataFrame([{"magazzino": row["magazzino"], "id_articolo": f"NEW_{row['id_acquisto']}", "nome_articolo": row["articolo"], "giacenza_totale": row["quantita_richiesta"]}])], ignore_index=True)
                        st.rerun()
