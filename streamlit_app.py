import streamlit as st
import pandas as pd
from datetime import datetime

# ==========================================
# CONFIGURAZIONE PASSWORD / PIN DI ACCESSO
# ==========================================
PASSWORD_MAGAZZINIERE = "magazzino2026"
PASSWORD_ADMIN = "admin99"

# Configurazione della pagina (impostiamo wide per gestire meglio i grandi schermi dei PC)
st.set_page_config(page_title="Gestione Magazzino Scarpa", page_icon="🧺", layout="wide")

# ==========================================
# DESIGN PREMIUM INTERFACCIA (CSS AVANZATO)
# ==========================================
st.markdown("""
    <style>
        /* Sfondo dell'intera applicazione: Gradiente scuro moderno e professionale */
        .stApp {
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #f8fafc;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        /* Centratura e limitazione larghezza per non "spalmare" troppo l'app sui PC giganti */
        [data-testid="stMainBlockContainer"] {
            max-width: 1100px;
            padding: 2rem 1rem;
            margin: 0 auto;
        }

        /* Stile del Titolo Principale dell'App */
        h1 {
            color: #ffffff !important;
            font-family: 'Montserrat', sans-serif;
            font-weight: 800 !important;
            text-align: center;
            margin-top: 10px !important;
            margin-bottom: 35px !important;
            text-shadow: 0 4px 12px rgba(0,0,0,0.3);
            letter-spacing: -0.5px;
        }

        /* Sotto-titoli dentro le sezioni */
        h2, h3, h4 {
            color: #1e293b !important;
            font-weight: 700 !important;
            margin-bottom: 15px !important;
        }

        /* CARD BIANCHE PREMIUM: Effetto fluttuante per moduli e richieste */
        [data-testid="stContainer"] {
            background: #ffffff !important;
            border: 1px solid rgba(255, 255, 255, 0.8) !important;
            border-radius: 20px !important;
            padding: 35px !important;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.25), 0 10px 10px -5px rgba(0, 0, 0, 0.2) !important;
            margin-bottom: 30px;
            
            /* Animazione fluida di ingresso */
            animation: appEntrance 0.5s cubic-bezier(0.16, 1, 0.3, 1);
        }
        
        /* I testi dentro le card bianche devono essere scuri per leggibilità */
        [data-testid="stContainer"] p, [data-testid="stContainer"] label, [data-testid="stContainer"] span {
            color: #334155 !important;
            font-weight: 500;
        }

        @keyframes appEntrance {
            from { opacity: 0; transform: translateY(15px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* MODIFICA DEI BOTTONI: Colore Blu Elettrico Moderno con micro-animazione */
        div.stButton > button:first-child {
            background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
            color: #ffffff !important;
            border-radius: 12px !important;
            border: none !important;
            padding: 14px 28px !important;
            font-weight: 600 !important;
            box-shadow: 0 4px 14px 0 rgba(59, 130, 246, 0.4) !important;
            transition: all 0.25s ease !important;
            width: 100%;
        }
        div.stButton > button:first-child:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 6px 20px 0 rgba(59, 130, 246, 0.6) !important;
            background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%) !important;
        }
        div.stButton > button:first-child:active {
            transform: translateY(0px) !important;
        }

        /* Sidebar scura coordinata */
        [data-testid="stSidebar"] {
            background-color: #0f172a !important;
            border-right: 1px solid #1e293b;
        }
        [data-testid="stSidebar"] h3 {
            color: #ffffff !important;
        }

        /* Nasconde i fastidiosi sotto-testi di Streamlit per pulizia visiva */
        footer {visibility: hidden;}
        [data-testid="stHeader"] {background: transparent;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# DATABASE VIRTUALE (Session State)
# ==========================================
if "db_inventario" not in st.session_state:
    st.session_state.db_inventario = pd.DataFrame([
        {"id_articolo": "A001", "nome_articolo": "Guanti da lavoro", "giacenza_totale": 100},
        {"id_articolo": "A002", "nome_articolo": "Scarpe antinfortunistiche", "giacenza_totale": 25},
        {"id_articolo": "A003", "nome_articolo": "Occhiali protettivi", "giacenza_totale": 50}
    ])

if "db_richieste" not in st.session_state:
    st.session_state.db_richieste = pd.DataFrame(columns=["id_richiesta", "collaboratore", "articolo", "quantita", "stato", "data_richiesta", "data_consegna"])

if "ruolo_utente" not in st.session_state:
    st.session_state.ruolo_utente = None
if "utente_corrente" not in st.session_state:
    st.session_state.utente_corrente = ""

# --- LOGIN INIZIALE ---
if st.session_state.ruolo_utente is None:
    # Intestazione centrata e pulita
    st.image("https://cspace.spaggiari.eu//pub/TVII0004/TVII0004-intestazione-nuova-senzaloghi.png?_t=1712923868", use_container_width=True)
    st.markdown("<h1>Gestione Magazzino Scarpa</h1>", unsafe_allow_html=True)
    
    # Layout a colonne per centrare la card di login sui PC grandi
    col_dx, col_centro, col_sx = st.columns([1, 2, 1])
    
    with col_centro:
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

# --- INTERFACCE OPERATIVE ---
else:
    st.image("https://cspace.spaggiari.eu//pub/TVII0004/TVII0004-intestazione-nuova-senzaloghi.png?_t=1712923868", use_container_width=True)
    
    # Barra Laterale Scura Coordinata
    with st.sidebar:
        st.markdown(f"<h3>🧺 Area {st.session_state.ruolo_utente.upper()}</h3>", unsafe_allow_html=True)
        st.write("---")
        if st.button("🔒 Esci / Cambia Utente"):
            st.session_state.ruolo_utente = None
            st.session_state.utente_corrente = ""
            st.rerun()

    df_inventario = st.session_state.db_inventario
    df_richieste = st.session_state.db_richieste

    # --- 1. AREA COLLABORATORE ---
    if st.session_state.ruolo_utente == "collaboratore":
        st.markdown(f"<h1>👋 Benvenuto, {st.session_state.utente_corrente}</h1>", unsafe_allow_html=True)
        
        col_l, col_c, col_r = st.columns([1, 4, 1])
        with col_c:
            with st.container():
                st.markdown("<h3>📋 Nuova Richiesta Materiale</h3>", unsafe_allow_html=True)
                lista_articoli = df_inventario["nome_articolo"].tolist()
                lista_articoli.append("Altro...")
                
                articolo_selezionato = st.selectbox("Seleziona cosa ti serve:", lista_articoli)
                
                if articolo_selezionato == "Altro...":
                    articolo_finale = st.text_input("Specifica il materiale a mano:")
                else:
                    articolo_finale = articolo_selezionato
                    
                qta = st.number_input("Quantità necessaria:", min_value=1, step=1)
                st.markdown("<br>", unsafe_allow_html=True)
                
                if st.button("Invia Ordine in Magazzino"):
                    if articolo_selezionato == "Altro..." and not articolo_finale.strip():
                        st.error("Scrivi il nome del materiale.")
                    else:
                        nuovo_id = int(df_richieste["id_richiesta"].max()) + 1 if not df_richieste.empty else 1
                        nuova_richiesta = pd.DataFrame([{
                            "id_richiesta": nuovo_id,
                            "collaboratore": st.session_state.utente_corrente,
                            "articolo": articolo_finale,
                            "quantita": int(qta),
                            "stato": "In attesa",
                            "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "data_consegna": ""
                        }])
                        st.session_state.db_richieste = pd.concat([df_richieste, nuova_richiesta], ignore_index=True)
                        st.success("✔️ Richiesta inoltrata correttamente!")

    # --- 2. AREA MAGAZZINIERE ---
    elif st.session_state.ruolo_utente == "magazziniere":
        st.markdown("<h1>🚚 Pannello Controllo Consegne</h1>", unsafe_allow_html=True)
        
        in_attesa = df_richieste[df_richieste["stato"] == "In attesa"]
        
        if in_attesa.empty:
            st.info("✨ Ottimo lavoro! Tutte le richieste sono state evase.")
        else:
            for idx, row in in_attesa.iterrows():
                with st.container():
                    c1, c2, c3 = st.columns([1, 4, 2])
                    with c1:
                        st.markdown(f"<span style='color:#64748b;font-weight:bold;'>ID #{row['id_richiesta']}</span>", unsafe_allow_html=True)
                    with c2:
                        st.markdown(f"👤 Dipendente: **{row['collaboratore']}**<br>📦 Materiale: <span style='color:#2563eb;font-weight:bold;'>{row['quantita']}x {row['articolo']}</span>", unsafe_allow_html=True)
                    with c3:
                        if st.button("Registra Consegna ✔", key=f"btn_{row['id_richiesta']}"):
                            filtro_art = df_inventario["nome_articolo"] == row['articolo']
                            if filtro_art.any():
                                giacenza = int(df_inventario.loc[filtro_art, "giacenza_totale"].values[0])
                                if giacenza >= int(row['quantita']):
                                    st.session_state.db_richieste.loc[st.session_state.db_richieste["id_richiesta"] == row["id_richiesta"], "stato"] = "Consegnato"
                                    st.session_state.db_richieste.loc[st.session_state.db_richieste["id_richiesta"] == row["id_richiesta"], "data_consegna"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                                    st.session_state.db_inventario.loc[filtro_art, "giacenza_totale"] = giacenza - int(row['quantita'])
                                    st.success("Evaso!")
                                    st.rerun()
                                else:
                                    st.error(f"Scorte esaurite! In magazzino: {giacenza}")
                            else:
                                st.error("Articolo speciale 'Altro'. Censiscilo prima.")

    # --- 3. AREA ADMIN ---
    elif st.session_state.ruolo_utente == "admin":
        st.markdown("<h1>📊 Pannello di Monitoraggio Amministrativo</h1>", unsafe_allow_html=True)
        
        with st.container():
            st.markdown("<h3>📋 Livello Scorte Correnti</h3>", unsafe_allow_html=True)
            st.dataframe(df_inventario, use_container_width=True, hide_index=True)
            
        with st.container():
            st.markdown("<h3>⏱ Registro Storico delle Consegne</h3>", unsafe_allow_html=True)
            consegnati = df_richieste[df_richieste["stato"] == "Consegnato"]
            if consegnati.empty:
                st.write("Nessuna consegna nel registro storico.")
            else:
                st.dataframe(consegnati[["data_consegna", "collaboratore", "articolo", "quantita"]], use_container_width=True, hide_index=True)
            
        csv = df_richieste.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Esporta Report Registro in Excel (CSV)", data=csv, file_name="registro_scarpa_2026.csv", mime="text/csv")
