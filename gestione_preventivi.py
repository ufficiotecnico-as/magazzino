import streamlit as st
import pandas as pd
from datetime import datetime
import json

def mostra_interfaccia_preventivi(scarica_da_sheet, carica_su_sheet, invia_email_sistema, URL_INTERMEDIARIO_SILENZIOSO, df_istanze, genera_pdf_ordine_fornitore, carica_su_drive_unico, ID_CARTELLA_ORDINI):
    st.markdown("## 📊 Hub Gestione Fornitori & Tracciabilità Preventivi")
    
    # Quattro Tab operative per separare i flussi
    tab_richieste, tab_rubrica, tab_inserimento, tab_registro_finito = st.tabs([
        "📥 Fabbisogni dai Magazzini",
        "📙 Rubrica Anagrafica Fornitori", 
        "✍️ Inserisci Offerta / Preventivo Ricevuto", 
        "📜 Registro Storico Preventivi"
    ])
    
    # Scaricamento real-time delle tabelle necessarie da Google Sheets
    df_fabbisogni = scarica_da_sheet("Richieste_Preventivo_Magazzino")
    df_preventivi = scarica_da_sheet("Registro_Preventivi")
    df_fornitori = scarica_da_sheet("Anagrafica_Fornitori")
    
    # --- TAB 1: VISUALIZZAZIONE FABBISOGNI APERTI ---
    with tab_richieste:
        st.markdown("### Elenco dei materiali segnalati dai capigruppo logistici")
        st.write("Questi articoli necessitano della ricerca di un preventivo sul mercato o sul portale MePA.")
        
        # FILTRO CORRETTO CHIRURGICAMENTE PER EVITARE KEYERROR
        df_fabbisogni_attivi = df_fabbisogni[df_fabbisogni["materiale_richiesto"].astype(str).str.strip() != ""] if not df_fabbisogni.empty else pd.DataFrame()
        
        if df_fabbisogni_attivi.empty:
            st.info("Nessuna segnalazione di fabbisogno aperta al momento.")
        else:
            st.dataframe(df_fabbisogni_attivi, use_container_width=True, hide_index=True)
            
    # --- TAB 2: RUBRICA FORNITORI ---
    with tab_rubrica:
        st.markdown("### 📙 Gestione Rubrica Fornitori d'Istituto")
        
        with st.expander("➕ Salva un nuovo Fornitore in Rubrica", expanded=False):
            with st.form("form_nuovo_fornitore"):
                rag_soc = st.text_input("Ragione Sociale / Denominazione Ditta:")
                p_iva = st.text_input("Partita IVA / Codice Fiscale Fornitore:")
                indirizzo_completo = st.text_input("Indirizzo Sede Legale (Via, CAP, Città, Prov):")
                email_cont = st.text_input("Email o PEC di contatto (per invio ordini/comunicazioni):")
                
                if st.form_submit_button("💾 Salva Fornitore in Rubrica", use_container_width=True):
                    if not rag_soc.strip() or not p_iva.strip():
                        st.error("I campi Ragione Sociale e Partita IVA sono tassativamente obbligatori per il censimento.")
                    else:
                        # Calcolo ID incrementale per il fornitore
                        id_forn_num = pd.to_numeric(df_fornitori["id_fornitore"], errors='coerce')
                        id_forn = int(id_forn_num.max() + 1) if not df_fornitori.empty and not id_forn_num.dropna().empty else 1
                        
                        nuovo_forn_df = pd.DataFrame([{
                            "id_fornitore": str(id_forn),
                            "ragione_sociale": str(rag_soc.strip()),
                            "partita_iva": str(p_iva.strip()),
                            "indirizzo": str(indirizzo_completo.strip()),
                            "email_contatto": str(email_cont.strip())
                        }])
                        
                        df_aggiornato = pd.concat([df_fornitori, nuovo_forn_df], ignore_index=True)
                        carica_su_sheet(df_aggiornato, "Anagrafica_Fornitori")
                        st.success(f"Ditta '{rag_soc.strip()}' registrata in anagrafica con ID {id_forn}!")
                        st.rerun()
                        
        # FILTRO CORRETTO CHIRURGICAMENTE PER EVITARE KEYERROR
        df_fornitori_attivi = df_fornitori[df_fornitori["ragione_sociale"].astype(str).str.strip() != ""] if not df_fornitori.empty else pd.DataFrame()
        
        if df_fornitori_attivi.empty:
            st.info("Nessun fornitore censito in rubrica.")
        else:
            st.dataframe(df_fornitori_attivi, use_container_width=True, hide_index=True)

    # --- TAB 3: INSERIMENTO OFFERTA / PREVENTIVO ---
    with tab_inserimento:
        st.markdown("### Collega un preventivo economico ricevuto a una richiesta interna")
        
        # FILTRI CORRETTI CHIRURGICAMENTE PER EVITARE KEYERROR
        df_fabbisogni_attivi = df_fabbisogni[df_fabbisogni["materiale_richiesto"].astype(str).str.strip() != ""] if not df_fabbisogni.empty else pd.DataFrame()
        df_fornitori_attivi = df_fornitori[df_fornitori["ragione_sociale"].astype(str).str.strip() != ""] if not df_fornitori.empty else pd.DataFrame()
        
        if df_fabbisogni_attivi.empty:
            st.warning("Per poter associare un preventivo deve essere presente almeno una richiesta aperta nella Tab Fabbisogni.")
        elif df_fornitori_attivi.empty:
            st.error("⚠️ Non hai ancora ditte registrate in rubrica! Vai nella Tab 'Rubrica Anagrafica Fornitori' per inserire il primo operatore economico.")
        else:
            lista_fabbisogni = [f"ID {r['id_richiesta_mag']} - {r['materiale_richiesto']} ({r['magazzino_origine']})" for _, r in df_fabbisogni_attivi.iterrows()]
            scelta_fabb = st.selectbox("Seleziona il fabbisogno d'origine a cui associare l'offerta:", lista_fabbisogni)
            id_fabb_scelto = scelta_fabb.split(" - ")[0].replace("ID ", "").strip()
            
            with st.form("form_aggiunta_preventivo"):
                mappa_nomi = {f"{f['ragione_sociale']} (P.IVA: {f['partita_iva']})": f for _, f in df_fornitori_attivi.iterrows()}
                fornitore_selezionato_rubrica = st.selectbox("Scegli la ditta mittente dalla Rubrica:", list(mappa_nomi.keys()))
                importo_lordo = st.number_input("Importo Totale Stimato IVATO del preventivo (€):", min_value=0.0, step=0.01)
                note_preventivo = st.text_area("Note e specifiche dell'offerta (es. tempi di consegna, validità prezzo):")
                
                if st.form_submit_button("Registra preventivo a sistema"):
                    f_dati = mappa_nomi[fornitore_selezionato_rubrica]
                    blocco_spett_le = f"{f_dati['ragione_sociale']}\nSede Legale: {f_dati['indirizzo']}\nP.IVA / C.F.: {f_dati['partita_iva']}\nContatto: {f_dati['email_contatto']}"
                    
                    id_prev_num = pd.to_numeric(df_preventivi["id_preventivo"], errors='coerce')
                    id_prev_nuovo = 501 if df_preventivi.empty or id_prev_num.dropna().empty else int(id_prev_num.max()) + 1
                    
                    nuovo_prev_df = pd.DataFrame([{
                        "id_preventivo": str(id_prev_nuovo),
                        "id_richiesta_mag": str(id_fabb_scelto),
                        "fornitore": blocco_spett_le,
                        "importo_ivato": f"{importo_lordo:.2f}",
                        "data_inserimento": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "stato_approvazione": "In valutazione",
                        "note": note_preventivo.strip(),
                        "cig": "",
                        "determina": ""
                    }])
                    
                    df_prev_finale = pd.concat([df_preventivi, nuovo_prev_df], ignore_index=True)
                    carica_su_sheet(df_prev_finale, "Registro_Preventivi")
                    st.success(f"Preventivo economico ID {id_prev_nuovo} salvato con successo e agganciato al fabbisogno ID {id_fabb_scelto}!")
                    st.rerun()
                        
    # --- TAB 4: VALUTAZIONE COMPLESSIVA E LETTERA D'ORDINE ---
    with tab_registro_finito:
        st.markdown("### Valutazione, Dettaglio Articoli ed Emissione Lettera d'Ordine")
        
        # FILTRO CORRETTO CHIRURGICAMENTE PER EVITARE KEYERROR
        df_preventivi_validi = df_preventivi[df_preventivi["id_preventivo"].astype(str).str.strip() != ""] if not df_preventivi.empty else pd.DataFrame()
        
        if df_preventivi_validi.empty:
            st.info("Nessun preventivo presente nello storico.")
        else:
            st.dataframe(df_preventivi_validi, use_container_width=True, hide_index=True)
            st.markdown("---")
            
            preventivi_valutabili = df_preventivi_validi[df_preventivi_validi["stato_approvazione"] == "In valutazione"]
            if preventivi_valutabili.empty:
                st.info("Tutti i preventivi inseriti a sistema risultano già elaborati, respinti o trasformati in ordinativi.")
            else:
                st.markdown("#### ⚙️ Configura Voci di Dettaglio ed Emetti Ordine Ufficiale")
                opzioni_preventivo = [f"PREV ID {p['id_preventivo']} - {p['fornitore'].splitlines()[0]} (€ {p['importo_ivato']})" for _, p in preventivi_valutabili.iterrows()]
                scelta_p = st.selectbox("Seleziona quale preventivo approvare ed emettere:", opzioni_preventivo)
                id_p_scelto = scelta_p.split(" - ")[0].replace("PREV ID ", "").strip()
                
                riga_p = df_preventivi_validi[df_preventivi_validi["id_preventivo"].astype(str) == str(id_p_scelto)].iloc[0]
                
                if "numero_righe_articoli" not in st.session_state:
                    st.session_state.numero_righe_articoli = 1
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("➕ Aggiungi Riga Articolo", use_container_width=True):
                        st.session_state.numero_righe_articoli += 1
                with col_btn2:
                    if st.button("➖ Rimuovi Ultima Riga", use_container_width=True) and st.session_state.numero_righe_articoli > 1:
                        st.session_state.numero_righe_articoli -= 1
                
                lista_articoli = []
                totale_calcolato = 0.0
                
                for i in range(st.session_state.numero_righe_articoli):
                    st.markdown(f"**Articolo di dettaglio {i+1}**")
                    c_desc, c_qta, c_prezzo = st.columns([2, 0.5, 1])
                    with c_desc:
                        desc_art = st.text_input(f"Descrizione del Prodotto/Servizio (Riga {i+1})", key=f"art_desc_{i}", placeholder="Es. Notebook ASUS ExpertBook B1")
                    with c_qta:
                        qta_art = st.number_input(f"Q.tà", min_value=1, value=1, key=f"art_qta_{i}")
                    with c_prezzo:
                        prezzo_art = st.number_input(f"Prezzo Unitario IVATO (€)", min_value=0.0, step=0.01, key=f"art_pr_{i}")
                    
                    tot_riga = qta_art * prezzo_art
                    totale_calcolato += tot_riga
                    lista_articoli.append({
                        "descrizione": desc_art,
                        "quantita": qta_art,
                        "prezzo_unitario": f"{prezzo_art:.2f}",
                        "totale_riga": f"{tot_riga:.2f}"
                    })
                
                st.markdown(f"### 💰 Totale Complessivo Calcolato dell'Ordine: **{totale_calcolato:.2f} €**")
                
                st.markdown("##### 📄 Dati Generali Obbligatori Protocollo, CIG e Atto")
                c1, c2 = st.columns(2)
                with c1:
                    cig_input = st.text_input("Codice CIG (Tracciabilità Flussi Finanziari Legge 136/2010):", placeholder="Es. Z1A3C4D5E6")
                    determina_input = st.text_input("Numero e Anno Determina di Affidamento:", placeholder="Es. Determina Dirigenziale N. 145/2026")
                    data_prev_forn = st.text_input("Data di invio preventivo da parte della ditta:", value=datetime.now().strftime("%d/%m/%Y"))
                with c2:
                    prot_forn = st.text_input("Protocollo ditta mittente (se presente):", value="N.D.")
                    prot_inst = st.text_input("Protocollo di ingresso ISISS Scarpa della proposta commerciale:", placeholder="Es. 0004120/E")
                
                riga_fabb = df_fabbisogni[df_fabbisogni["id_richiesta_mag"].astype(str) == str(riga_p["id_richiesta_mag"])] if not df_fabbisogni.empty else pd.DataFrame()
                
                if st.button("🔴 GENERA LETTERA D'ORDINE CON ARTICOLI DETTAGLIATI", type="primary", use_container_width=True):
                    errori = False
                    for art in lista_articoli:
                        if not art["descrizione"].strip():
                            errori = True
                    if errori:
                        st.error("Errore di validazione: Assicurati di aver inserito una descrizione valida per tutte le righe articolo create.")
                    elif not cig_input.strip() or not determina_input.strip() or not prot_inst.strip():
                        st.error("Errore di compilazione: I campi CIG, Determina e Protocollo d'ingresso Istituto sono stringhe obbligatorie ai fini di validità dell'atto di sottomissione.")
                    else:
                        mappa_dati_pdf = {
                            "fornitore": riga_p["fornitore"],
                            "oggetto_ordine": f"Affidamento diretto per fornitura materiale d'istituto - Richiesta Magazzino originaria ID {riga_p['id_richiesta_mag']}",
                            "data_preventivo": data_prev_forn,
                            "protocollo_fornitore": prot_forn,
                            "protocollo_istituto": prot_inst,
                            "articoli": lista_articoli,
                            "importo_ivato": f"{totale_calcolato:.2f}",
                            "cig": cig_input.strip().upper(),
                            "determina": determina_input.strip()
                        }
                        
                        idx_p = df_preventivi.index[df_preventivi["id_preventivo"].astype(str) == str(id_p_scelto)].tolist()[0]
                        df_preventivi.at[idx_p, "stato_approvazione"] = "Approvato ed Emesso"
                        df_preventivi.at[idx_p, "cig"] = cig_input.strip().upper()
                        df_preventivi.at[idx_p, "determina"] = determina_input.strip()
                        df_preventivi.at[idx_p, "note"] = f"{riga_p['note']} | Articoli ordinati: " + json.dumps(lista_articoli)
                        carica_su_sheet(df_preventivi, "Registro_Preventivi")
                        
                        if not riga_fabb.empty:
                            idx_f = df_fabbisogni.index[df_fabbisogni["id_richiesta_mag"].astype(str) == str(riga_p["id_richiesta_mag"])].tolist()[0]
                            df_fabbisogni.at[idx_f, "stato_iter"] = "Ordinato / Evaso"
                            carica_su_sheet(df_fabbisogni, "Richieste_Preventivo_Magazzino")
                        
                        pdf_bytes = genera_pdf_ordine_fornitore(mappa_dati_pdf)
                        nome_file_generato = f"Lettera_Ordine_PREV_{id_p_scelto}_CIG_{cig_input.strip().upper()}.pdf"
                        
                        caricato_su_drive = carica_su_drive_unico(pdf_bytes, nome_file_generato, "application/pdf", ID_CARTELLA_ORDINI)
                        if caricato_su_drive:
                            st.success(f"📦 Atto d'ordine archiviato in Google Drive istituzionale con successo!")
                        
                        st.download_button(
                            label="📥 Scarica Copia Locale Lettera d'Ordine (PDF Firmato)",
                            data=pdf_bytes,
                            file_name=nome_file_generato,
                            mime="application/pdf",
                            use_container_width=True
                        )
                        st.session_state.numero_righe_articoli = 1
                        st.balloons()
