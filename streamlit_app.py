import streamlit as st
import pandas as pd
from datetime import datetime

# ==========================================
# CONFIGURAZIONE PASSWORD / PIN DI ACCESSO
# ==========================================
PASSWORD_MAGAZZINIERE = "magazzino2026"
PASSWORD_ADMIN = "admin99"

# Configurazione della pagina con l'icona a forma di CESTINO (Basket) anche per il browser
st.set_page_config(page_title="Gestione Magazzino Scarpa", page_icon="🧺", layout="centered")

# ==========================================
# ABBELLIMENTO INTERFACCIA TRAMITE CSS (Con Animazioni)
# ==========================================
st.markdown("""
    <style>
        /* Sfondo e Font Generale */
        .stApp {
            background-color: #f0f2f6;
            font-family: 'Inter', sans-serif;
        }

        /* Testata e Titoli */
        h1 {
            color: #1a1e21; /* Colore scuro professionale */
            font-family: 'Montserrat', sans-serif;
            font-weight: 800;
            text-align: center;
            margin-bottom: 30px !important;
            border-bottom: 2px solid #fdcb6e; /* Giallo Spaggiari accent */
            display: inline-block;
            padding-bottom: 10px;
        }

        h2, h3, h4, h5 {
            color: #0d2a41 !important; /* Blu Spaggiari profondp */
            font-weight: 700 !important;
        }

        /* Animazione dell'Icona Cestino in Sidebar (Rimbalzo al passaggio) */
        [data-testid="stSidebar"] [data-testid="stIconBasket"] {
            display: inline-block;
            transition: transform 0.3s ease-out;
        }
        [data-testid="stSidebar"] [data-testid="stIconBasket"]:hover {
            transform: scale(1.2) translateY(-5px);
        }

        /* Bottoni Principali (Colore Blu Spaggiari) */
        div.stButton > button:first-child {
            background-color: #0d2a41;
            color: white;
            border-radius: 10px;
            border: none;
            padding: 12px 24px;
            font-weight: 600;
            letter-spacing: 0.5px;
            transition: background-color 0.2s ease;
        }
        div.stButton > button:first-child:hover {
            background-color: #1a4a6e;
            color: white;
            border: none;
        }

        /* Container Card (Migliorati e con Animazione Ingresso) */
        [data-testid="stContainer"] {
            background-color: white;
            border: none !important;
            border-radius: 15px !important;
            padding: 30px !important;
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.08) !important;
            margin-bottom: 25px;
            
            /* Animazione Ingresso: Scorrimento verso l'alto e dissolvenza */
            animation: slideUp 0.6s ease-out;
        }

        @keyframes slideUp {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        /* Miglioramento dei campi di input e tabelle per un look più moderno */
        input[type="text"], input[type="number"], .stSelectbox {
            border-radius: 8px !important;
            border: 1px solid #dfe6e9 !important;
        }

        .dataframe {
            border: none !important;
            color: #1a1e21;
        }
        .dataframe thead th {
            background-color: #f1f3f6 !important;
            color: #0d2a41 !important;
            font-weight: 700;
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# INIZIALIZZAZIONE DATABASE VIRTUALE (Session State)
# ==========================================
if "db_inventario" not in st.session_state:
    st.session_state.db_inventario = pd.DataFrame([
        {"id_articolo": "A001", "nome_articolo": "Guanti da lavoro", "giacenza_totale": 100},
        {"id_articolo": "A002", "nome_articolo": "Scarpe antinfortunistiche", "giacenza_totale": 25},
        {"id_articolo": "A003", "nome_articolo": "Occhiali protettivi", "giacenza_totale": 50}
    ])

if "db_richieste" not in st.session_state:
    st.session_state.db_richieste = pd.DataFrame(columns=["id_richiesta", "collaboratore", "articolo", "quantita", "stato", "data_richiesta", "data_consegna"])

# Gestione dello stato di login dell'utente
if "ruolo_utente" not in st.session_state:
    st.session_state.ruolo_utente = None
if "utente_corrente" not in st.session_state:
    st.session_state.utente_corrente = ""

# --- SCHERMATA DI LOGIN INIZIALE (Icona e Stile) ---
if st.session_state.ruolo_utente is None:
    st.image("https://cspace.spaggiari.eu//pub/TVII0004/TVII0004-intestazione-nuova-senzaloghi.png?_t=1712923868", use_column_width=True)
    st.title("Gestione Magazzino Scarpa")
    
    with st.container():
        st.markdown("<h3 style='text-align: center;'>🔑 Identificazione Utente</h3>", unsafe_allow_html=True)
        # Scegliere collaboratore vs magazziniere con più stile
        scelta_accesso = st.radio("Seleziona il tuo profilo:", ["Sono un Collaboratore (Richiesta materiale)", "Sono il Magazziniere / Admin"], label_visibility="collapsed")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        if scelta_accesso == "Sono un Collaboratore (Richiesta materiale)":
            nome_input = st.text_input("Inserisci il tuo Nome e Cognome:")
            if st.button("Accedi all'area Richieste", use_container_width=True):
                if not nome_input.strip():
                    st.error("⚠️ Inserisci il tuo nome per continuare.")
                else:
                    st.session_state.ruolo_utente = "collaboratore"
                    st.session_state.utente_corrente = nome_input.strip()
                    st.rerun()
                    
        elif scelta_accesso == "Sono il Magazziniere / Admin":
            password_input = st.text_input("Inserisci la password di sblocco:", type="password")
            if st.button("Verifica Password", use_container_width=True):
                if password_input == PASSWORD_MAGAZZINIERE:
                    st.session_state.ruolo_utente = "magazziniere"
                    st.rerun()
                elif password_input == PASSWORD_ADMIN:
                    st.session_state.ruolo_utente = "admin"
                    st.rerun()
                else:
                    st.error("❌ Password errata. Riprova.")

# --- SE SEI LOGGATO, MOSTRA L'INTERFACCIA CORRETTA ---
else:
    # Aggiunge l'icona Cestino interattiva in Sidebar
    with st.sidebar:
        col1, col2 = st.columns([1, 6])
        with col1:
            st.markdown('<span data-testid="stIconBasket" style="font-size:32px;">🧺</span>', unsafe_allow_html=True)
        with col2:
            st.markdown(f"<h3 style='margin-top: -5px;'>Area {st.session_state.ruolo_utente.upper()}</h3>", unsafe_allow_html=True)
        st.write("---")
        if st.button("🔒 Esci / Cambia Utente", use_container_width=True):
            st.session_state.ruolo_utente = None
            st.session_state.utente_corrente = ""
            st.rerun()

    # Riferimento ai database globali per brevità
    df_inventario = st.session_state.db_inventario
    df_richieste = st.session_state.db_richieste

    # --- 1. INTERFACCIA ESCLUSIVA COLLABORATORE (Icone e Layout Card) ---
    if st.session_state.ruolo_utente == "collaboratore":
        st.title(f"👋 Benvenuto, {st.session_state.utente_corrente}")
        
        with st.container():
            st.subheader("📋 Invia una nuova richiesta")
            lista_articoli = df_inventario["nome_articolo"].tolist()
            # Aggiungere l'opzione Altro in fondo
            lista_articoli.append("Altro...")
            
            articolo_selezionato = st.selectbox("Seleziona l'articolo da richiedere:", lista_articoli)
            
            # Se sceglie Altro, mostra un campo di testo libero
            if articolo_selezionato == "Altro...":
                articolo_finale = st.text_input("Specifica a mano il materiale richiesto:")
            else:
                articolo_finale = articolo_selezionato
                
            qta = st.number_input("Quantità necessaria:", min_value=1, step=1)
            st.markdown("<br>", unsafe_allow_html=True)
            
            if st.button("Invia Richiesta al Magazzino", use_container_width=True):
                # Generazione ID univoco
                nuovo_id = int(df_richieste["id_richiesta"].max()) + 1 if not df_richieste.empty else 1
                
                # Creazione data frame per la nuova richiesta
                nuova_richiesta = pd.DataFrame([{
                    "id_richiesta": nuovo_id,
                    "collaboratore": st.session_state.utente_corrente,
                    "articolo": articolo_finale,
                    "quantita": int(qta),
                    "stato": "In attesa",
                    "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "data_consegna": ""
                }])
                
                # Aggiornamento session state
                st.session_state.db_richieste = pd.concat([df_richieste, nuova_richiesta], ignore_index=True)
                st.success(f"✔️ Richiesta inviata! Verrà esaminata dal magazziniere.")

    # --- 2. INTERFACCIA ESCLUSIVA MAGAZZINIERE (Animazione Card) ---
    elif st.session_state.ruolo_utente == "magazziniere":
        st.title("🚚 Pannello Magazziniere")
        
        in_attesa = df_richieste[df_richieste["stato"] == "In attesa"]
        
        st.subheader("📋 Richieste in attesa dai collaboratori")
        
        if in_attesa.empty:
            st.info("✨ Non ci sono richieste pendenti al momento.")
        else:
            for idx, row in in_attesa.iterrows():
                # Card animata per ogni richiesta
                with st.container():
                    col1, col2, col3 = st.columns([1, 4, 1])
                    with col1:
                        st.markdown(f"**#{row['id_richiesta']}**")
                    with col2:
                        st.write(f"👤 **{row['collaboratore']}** chiede {row['quantita']}x **{row['articolo']}**")
                    with col3:
                        # Bottone di consegna su card
                        if st.button("Consegna ✔", key=f"consegna_{row['id_richiesta']}", use_container_width=True):
                            art = row['articolo']
                            qta_richiesta = int(row['quantita'])
                            
                            # Cerca l'articolo nell'inventario ufficiale
                            filtro_art = df_inventario["nome_articolo"] == art
                            if filtro_art.any():
                                giacenza_attuale = int(df_inventario.loc[filtro_art, "giacenza_totale"].values[0])
                                
                                # Verifica giacenza
                                if giacenza_attuale >= qta_richiesta:
                                    # Aggiorna lo stato nel database virtuale
                                    st.session_state.db_richieste.loc[st.session_state.db_richieste["id_richiesta"] == row["id_richiesta"], "stato"] = "Consegnato"
                                    st.session_state.db_richieste.loc[st.session_state.db_richieste["id_richiesta"] == row["id_richiesta"], "data_consegna"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                                    # Scala dalla giacenza
                                    st.session_state.db_inventario.loc[filtro_art, "giacenza_totale"] = giacenza_attuale - qta_richiesta
                                    
                                    st.success("✔️ Consegna registrata!")
                                    st.rerun()
                                else:
                                    st.error(f"❌ Errore: Giacenza insufficiente (Disponibili: {giacenza_attuale})")
                            else:
                                st.error(f"❌ L'articolo '{art}' è stato registrato come 'Altro'. Registralo in inventario prima di effettuare la consegna.")

    # --- 3. INTERFACCIA ESCLUSIVA ADMIN (Layout Report) ---
    elif st.session_state.ruolo_utente == "admin":
        st.title("📊 Controllo Amministratore")
        
        st.subheader("📋 Giacenza di Magazzino Attuale")
        st.dataframe(df_inventario, use_container_width=True, hide_index=True)
        
        st.subheader("⏱ Registro Storico delle Consegne Effettuate")
        consegnati = df_richieste[df_richieste["stato"] == "Consegnato"]
        if consegnati.empty:
            st.info("Nessuna consegna registrata nello storico.")
        else:
            st.dataframe(consegnati[["data_consegna", "collaboratore", "articolo", "quantita"]], use_container_width=True, hide_index=True)
            
        # Bottone di esportazione Excel/CSV in un container moderno
        st.markdown("---")
        csv = df_richieste.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Scarica Registro Excel (Excel/CSV)", data=csv, file_name="registro_magazzino.csv", mime="text/csv", use_container_width=True)
