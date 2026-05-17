import streamlit as st
import pandas as pd
from datetime import datetime

def mostra_interfaccia_preventivi(scarica_da_sheet, carica_su_sheet, invia_email_sistema, url_intermediario, df_istanze):
    st.markdown("## 📊 Hub Ingegnerizzato: Gestione Preventivi e Fornitori")
    st.markdown("Benvenuto nell'area di monitoraggio economico. Qui puoi associare i preventivi dei fornitori esterni alle richieste approvate dalla Dirigente.")
    
    # 1. CARICAMENTO DATI SPECIFICI DA GOOGLE SHEETS
    # Usiamo schede dedicate per i preventivi e l'anagrafica dei fornitori
    df_preventivi = scarica_da_sheet("Registro_Preventivi")
    df_fornitori = scarica_da_sheet("Anagrafica_Fornitori")
    
    # Se le schede sono nuove o vuote, creiamo una struttura di base coerente
    if df_preventivi.empty:
        df_preventivi = pd.DataFrame(columns=[
            "id_preventivo", "id_richiesta", "fornitore", "importo_ivato", 
            "data_inserimento", "stato_approvazione", "note"
        ])
    if df_fornitori.empty:
        df_fornitori = pd.DataFrame(columns=["id_fornitore", "ragione_sociale", "partita_iva", "email_contatto"])
        # Inseriamo un paio di fornitori di esempio per non lasciare il database vuoto
        df_fornitori = pd.DataFrame([
            {"id_fornitore": "F01", "ragione_sociale": "Forniture Scolastiche Rossi Srl", "partita_iva": "01234567890", "email_contatto": "commerciale@rossiforniture.it"},
            {"id_fornitore": "F02", "ragione_sociale": "Informatica & Digitale SpA", "partita_iva": "09876543210", "email_contatto": "info@informaticadigitale.it"}
        ])
        carica_su_sheet(df_fornitori, "Anagrafica_Fornitori")

    # Creazione dei Tab interni per organizzare il lavoro dell'Ufficio Tecnico
    tab_nuovo, tab_registro, tab_fornitori = st.tabs([
        "➕ Associa Nuovo Preventivo", 
        "📜 Registro Preventivi Caricati", 
        "🏢 Anagrafica Fornitori"
    ])
    
    # ==========================================
    # TAB 1: ASSOCIA NUOVO PREVENTIVO
    # ==========================================
    with tab_nuovo:
        st.markdown("### ✍️ Carica Offerta Economica per un'Istanza Approvata")
        
        # Filtriamo le richieste principali che sono state approvate dalla preside ("Lavorata" o "Assegnata")
        if not df_istanze.empty:
            istanze_filtrate = df_istanze[df_istanze["stato"].isin(["Lavorata", "Assegnata", "In lavorazione"])]
        else:
            istanze_filtrate = pd.DataFrame()
            
        if istanze_filtrate.empty:
            st.info("Al momento non ci sono richieste approvate dalla Dirigente in attesa di preventivo economico.")
        else:
            # Creiamo una lista selettiva per il menu a tendina
            opzioni_richieste = []
            mappa_richieste = {}
            for _, riga in istanze_filtrate.iterrows():
                label = f"ID {riga['id_richiesta']} - {riga['richiedente']} ({riga['oggetto']})"
                opzioni_richieste.append(label)
                mappa_richieste[label] = riga['id_richiesta']
                
            richiesta_scelta = st.selectbox("Seleziona la richiesta della scuola associata:", opzioni_richieste)
            id_richiesta_selezionata = mappa_richieste[richiesta_scelta]
            
            # Selezione del fornitore dall'anagrafica
            lista_fornitori = df_fornitori["ragione_sociale"].tolist() if not df_fornitori.empty else ["Nessun fornitore censito"]
            fornitore_scelto = st.selectbox("Seleziona il Fornitore che ha emesso il preventivo:", lista_fornitori)
            
            # Form per i dettagli del costo
            with st.form("form_aggiunta_preventivo"):
                col1, col2 = st.columns(2)
                with col1:
                    importo = st.number_input("Importo Totale Preventivato (€, IVA inclusa):", min_value=0.0, step=10.0, format="%.2f")
                with col2:
                    note_preventivo = st.text_input("Note aggiuntive / Riferimento offerta:")
                    
                submit_preventivo = st.form_submit_button("Registra Preventivo nel Sistema", use_container_width=True)
                
                if submit_preventivo:
                    if fornitore_scelto == "Nessun fornitore censito":
                        st.error("Devi prima aggiungere un fornitore valido nell'apposito Tab Anagrafica.")
                    elif importo <= 0:
                        st.error("L'importo del preventivo deve essere superiore a 0 €.")
                    else:
                        # Calcolo del nuovo ID preventivo progressivo
                        try:
                            id_p_num = pd.to_numeric(df_preventivi["id_preventivo"], errors='coerce')
                            nuovo_id_p = int(id_p_num.max()) + 1 if not df_preventivi.empty and not id_p_num.dropna().empty else 501
                        except Exception:
                            nuovo_id_p = 501
                            
                        # Costruzione della nuova riga
                        nuovo_prev_df = pd.DataFrame([{
                            "id_preventivo": nuovo_id_p,
                            "id_richiesta": id_richiesta_selezionata,
                            "fornitore": fornitore_scelto,
                            "importo_ivato": f"{importo:.2f}",
                            "data_inserimento": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "stato_approvazione": "In attesa di validazione DSGA",
                            "note": note_preventivo.strip()
                        }])
                        
                        # Aggiornamento dello Sheet su Google Drive
                        df_preventivi_aggiornato = pd.concat([df_preventivi, nuovo_prev_df], ignore_index=True)
                        carica_su_sheet(df_preventivi_aggiornato, "Registro_Preventivi")
                        
                        st.success(f"✅ Preventivo ID {nuovo_id_p} associato con successo alla richiesta ID {id_richiesta_selezionata}!")
                        st.rerun()

    # ==========================================
    # TAB 2: REGISTRO GENERALE PREVENTIVI
    # ==========================================
    with tab_registro:
        st.markdown("### 📜 Elenco Economico e Stato Pratiche di Acquisto")
        if df_preventivi.empty:
            st.info("Nessun preventivo inserito a registro al momento.")
        else:
            st.dataframe(df_preventivi, use_container_width=True, hide_index=True)

    # ==========================================
    # TAB 3: ANAGRAFICA FORNITORI
    # ==========================================
    with tab_fornitori:
        st.markdown("### 🏢 Gestione Aziende ed Operatori Economici Partner")
        st.dataframe(df_fornitori, use_container_width=True, hide_index=True)
        
        with st.expander("➕ Censisci un nuovo Fornitore d'Istituto"):
            with st.form("form_nuovo_fornitore"):
                rag_soc = st.text_input("Ragione Sociale Azienda:")
                p_iva = st.text_input("Partita IVA / Codice Fiscale Azienda:")
                mail_f = st.text_input("Email o PEC di contatto:")
                
                submit_f = st.form_submit_button("Salva Azienda in Anagrafica")
                if submit_f:
                    if rag_soc.strip() and p_iva.strip():
                        id_f_nuovo = f"F{len(df_fornitori) + 1:02d}"
                        nuovo_f_row = pd.DataFrame([{
                            "id_fornitore": id_f_nuovo,
                            "ragione_sociale": rag_soc.strip(),
                            "partita_iva": p_iva.strip(),
                            "email_contatto": mail_f.strip()
                        }])
                        df_fornitori_aggiornato = pd.concat([df_fornitori, nuovo_f_row], ignore_index=True)
                        carica_su_sheet(df_fornitori_aggiornato, "Anagrafica_Fornitori")
                        st.success(f"🏢 Fornitore '{rag_soc.strip()}' inserito correttamente!")
                        st.rerun()
                    else:
                        st.error("I campi Ragione Sociale e Partita IVA sono strettamente obbligatori.")
