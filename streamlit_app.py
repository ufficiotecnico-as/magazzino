import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Magazzino Cloud", page_icon="📦", layout="centered")
st.title("📦 Gestione Magazzino Online")

# Connessione nativa e sicura a Google Sheets
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_inventario = conn.read(worksheet="inventario", ttl=0)
    df_richieste = conn.read(worksheet="richieste", ttl=0)
except Exception as e:
    st.error("Errore di connessione al Database. Verifica le credenziali nei Secrets.")
    st.stop()

# Menu di navigazione
ruolo = st.sidebar.radio("Vai a:", ["1. Richiesta Materiale (Collaboratore)", "2. Consegna (Magazziniere)", "3. Dashboard (Admin)"])

# --- 1. INTERFACCIA COLLABORATORE ---
if ruolo == "1. Richiesta Materiale (Collaboratore)":
    st.header("👋 Nuova Richiesta")
    nome = st.text_input("Inserisci il tuo Nome e Cognome:")
    
    # Lista dinamica degli articoli letti dal foglio online
    lista_articoli = df_inventario["nome_articolo"].dropna().tolist()
    articolo = st.selectbox("Seleziona l'articolo da richiedere:", lista_articoli)
    qta = st.number_input("Quantità necessaria:", min_value=1, step=1)
    
    if st.button("Invia Richiesta", use_container_width=True):
        if not nome.strip():
            st.error("⚠️ Compila il campo Nome prima di inviare.")
        else:
            # Genera ID univoco progressivo
            nuovo_id = int(df_richieste["id_richiesta"].max()) + 1 if not df_richieste.empty else 1
            
            nuova_richiesta = pd.DataFrame([{
                "id_richiesta": nuovo_id,
                "collaboratore": nome,
                "articolo": articolo,
                "quantita": qta,
                "stato": "In attesa",
                "data_richiesta": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "data_consegna": ""
            }])
            
            # Unisce e sovrascrive sul foglio online (Autocompilazione)
            df_aggiornato = pd.concat([df_richieste, nuova_richiesta], ignore_index=True)
            conn.update(worksheet="richieste", data=df_aggiornato)
            st.success(f"Richiesta inviata! Il magazziniere la vedrà in tempo reale.")

# --- 2. INTERFACCIA MAGAZZINIERE ---
elif ruolo == "2. Consegna (Magazziniere)":
    st.header("🚚 Richieste in Attesa di Consegna")
    
    # Filtra solo quelle da evadere
    in_attesa = df_richieste[df_richieste["stato"] == "In attesa"]
    
    if in_attesa.empty:
        st.info("Ottimo lavoro! Non ci sono richieste pendenti.")
    else:
        for idx, row in in_attesa.iterrows():
            with st.container(border=True):
                st.write(f"👤 **{row['collaboratore']}**")
                st.write(f"📦 Materiale: {row['quantita']}x **{row['articolo']}**")
                st.write(f"📅 Richiesto il: {row['data_richiesta']}")
                
                if st.button("Mark come Consegnato ✔", key=f"consegna_{row['id_richiesta']}", use_container_width=True):
                    art = row['articolo']
                    qta_richiesta = int(row['quantita'])
                    
                    # Trova giacenza attuale nel foglio
                    giacenza_attuale = int(df_inventario.loc[df_inventario["nome_articolo"] == art, "giacenza_totale"].values[0])
                    
                    if giacenza_attuale >= qta_richiesta:
                        # 1. Aggiorna stato della richiesta
                        df_richieste.loc[df_richieste["id_richiesta"] == row["id_richiesta"], "stato"] = "Consegnato"
                        df_richieste.loc[df_richieste["id_richiesta"] == row["id_richiesta"], "data_consegna"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                        
                        # 2. Sottrae dal magazzino
                        df_inventario.loc[df_inventario["nome_articolo"] == art, "giacenza_totale"] = giacenza_attuale - qta_richiesta
                        
                        # Aggiorna il database online
                        conn.update(worksheet="richieste", data=df_richieste)
                        conn.update(worksheet="inventario", data=df_inventario)
                        
                        st.success("Consegna registrata e magazzino aggiornato!")
                        st.rerun()
                    else:
                        st.error(f"Errore: Giacenza insufficiente! Disponibili solo {giacenza_attuale} pezzi.")

# --- 3. INTERFACCIA ADMIN ---
elif ruolo == "3. Dashboard (Admin)":
    st.header("📊 Resoconto e Giacenze")
    
    st.subheader("📋 Inventario Attuale")
    st.dataframe(df_inventario, use_container_width=True, hide_index=True)
    
    st.subheader("⏱ Storico Consegne Effettuate")
    consegnati = df_richieste[df_richieste["stato"] == "Consegnato"]
    if consegnati.empty:
        st.info("Nessuna consegna registrata nello storico.")
    else:
        st.dataframe(consegnati[["data_consegna", "collaboratore", "articolo", "quantita"]], use_container_width=True, hide_index=True)
