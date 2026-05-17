import streamlit as st
import pandas as pd
from datetime import datetime

def mostra_interfaccia_preventivi(scarica_da_sheet, carica_su_sheet, invia_email_sistema, url_intermediario, df_istanze, genera_pdf_ordine_fornitore=None, carica_su_drive_unico=None, id_cartella_ordini=None):
    st.markdown("## 📊 Hub Gestione Fornitori & Tracciabilità Preventivi")
    
    tab_richieste, tab_rubrica, tab_inserimento, tab_registro_finito = st.tabs([
        "📥 Fabbisogni dai Magazzini",
        "📙 Rubrica Anagrafica Fornitori", 
        "✍️ Inserisci Offerta / Preventivo Ricevuto", 
        "📜 Registro Storico Preventivi"
    ])
    
    df_fabbisogni = scarica_da_sheet("Richieste_Preventivo_Magazzino")
    df_preventivi = scarica_da_sheet("Registro_Preventivi")
    df_fornitori = scarica_da_sheet("Anagrafica_Fornitori")
    
    # ---------------------------------------------------------
    # TAB 1: FABBISOGNI
    # ---------------------------------------------------------
    with tab_richieste:
        st.markdown("### Elenco materiali segnalati dai capigruppo logistici")
        if df_fabbisogni.empty:
            st.info("Nessuna segnalazione di fabbisogno aperta al momento.")
        else:
            st.dataframe(df_fabbisogni, use_container_width=True, hide_index=True)
            
    # ---------------------------------------------------------
    # TAB 2: NUOVA RUBRICA FORNITORI (Per non reinserirli ogni volta)
    # ---------------------------------------------------------
    with tab_rubrica:
        st.markdown("### 📙 Gestione Rubrica Fornitori d'Istituto")
        
        with st.expander("➕ Salva un nuovo Fornitore in Rubrica", expanded=False):
            with st.form("form_nuovo_fornitore"):
                rag_soc = st.text_input("Ragione Sociale / Denominazione Ditta:")
                p_iva = st.text_input("Partita IVA / Codice Fiscale Fornitore:")
                indirizzo_completo = st.text_input("Indirizzo Sede Legale (Via, CAP, Città, Prov):")
                email_cont = st.text_input("Email o PEC di contatto:")
                
                if st.form_submit_button("💾 Salva Fornitore in Rubrica", use_container_width=True):
                    if not rag_soc.strip() or not p_iva.strip():
                        st.error("I campi Ragione Sociale e Partita IVA sono obbligatori per il censimento.")
                    else:
                        id_forn = 1 if df_fornitori.empty else int(pd.to_numeric(df_fornitori["id_fornitore"], errors='coerce').max()) + 1
                        nuovo_forn_df = pd.DataFrame([{
                            "id_fornitore": id_forn,
                            "ragione_sociale": rag_soc.strip(),
                            "partita_iva": p_iva.strip(),
                            "indirizzo": indirizzo_completo.strip(),
                            "email_contatto": email_cont.strip()
                        }])
                        df_fornitori = pd.concat([df_fornitori, nuovo_forn_df], ignore_index=True)
                        carica_su_sheet(df_fornitori, "Anagrafica_Fornitori")
                        st.success(f"Ditta '{rag_soc.strip()}' registrata in rubrica!")
                        st.rerun()
                        
        if df_fornitori.empty:
            st.info("Nessun fornitore salvato in rubrica. Aggiungine uno sopra per evitare di digitarlo a mano.")
        else:
            st.markdown("#### Aziende Censite a Registro")
            st.dataframe(df_fornitori, use_container_width=True, hide_index=True)
            
            # Funzionalità rapida per eliminare un elemento errato
            elenco_cancellabili = [f"{f['id_fornitore']} - {f['ragione_sociale']}" for _, f in df_fornitori.iterrows()]
            da_eliminare = st.selectbox("Seleziona eventuale ditta da rimuovere:", [""] + elenco_cancellabili)
            if da_eliminare and st.button("🗑️ Rimuovi Fornitore Selezionato", type="secondary"):
                id_da_rim = da_eliminare.split(" - ")[0]
                df_fornitori = df_fornitori[df_fornitori["id_fornitore"].astype(str) != str(id_da_rim)]
                carica_su_sheet(df_fornitori, "Anagrafica_Fornitori")
                st.success("Fornitore rimosso dalla rubrica.")
                st.rerun()

    # ---------------------------------------------------------
    # TAB 3: INSERIMENTO PREVENTIVO (MODIFICATO CON MENU RUBRICA)
    # ---------------------------------------------------------
    with tab_inserimento:
        st.markdown("### Collega un preventivo economico a una richiesta interna")
        if df_fabbisogni.empty:
            st.warning("Per inserire un preventivo deve essere presente almeno un fabbisogno aperto.")
        elif df_fornitori.empty:
            st.error("⚠️ Non hai ancora fornitori in rubrica! Vai nella scheda '📙 Rubrica Anagrafica Fornitori' e inserisci almeno un'azienda prima di continuare.")
        else:
            lista_fabbisogni = [f"ID {r['id_richiesta_mag']} - {r['materiale_richiesto']} ({r['magazzino_origine']})" for _, r in df_fabbisogni.iterrows()]
            scelta_fabb = st.selectbox("Seleziona il fabbisogno d'origine:", lista_fabbisogni)
            id_fabb_scelto = scelta_fabb.split(" - ")[0].replace("ID ", "").strip()
            
            with st.form("form_aggiunta_preventivo"):
                st.markdown("##### 🏢 Selezione Fornitore da Rubrica")
                # Menu a tendina generato dinamicamente dai contatti salvati
                opzioni_rubrica = [f"{f['ragione_sociale']} (P.IVA: {f['partita_iva']})" for _, f in df_fornitori.iterrows()]
                fornitore_selezionato_rubrica = st.selectbox("Scegli la ditta (prenderà i dati in automatico):", opzioni_rubrica)
                
                importo_lordo = st.number_input("Importo Totale IVATO (€):", min_value=0.0, step=0.01)
                note_preventivo = st.text_area("Note aggiuntive / Condizioni di consegna:")
                
                if st.form_submit_button("Registra preventivo a sistema"):
                    # Recuperiamo l'oggetto corretto del fornitore per formattarlo nel blocco "Spett.le"
                    idx_f_scelta = df_fornitori.index[[f"{f['ragione_sociale']} (P.IVA: {f['partita_iva']})" == fornitore_selezionato_rubrica for _, f in df_fornitori.iterrows()]].tolist()[0]
                    f_dati = df_fornitori.iloc[idx_f_scelta]
                    
                    # Formattiamo la stringa multiline del destinatario esattamente come serve al PDF
                    blocco_spett_le = f"{f_dati['ragione_sociale']}\nSede Legale: {f_dati['indirizzo']}\nP.IVA / C.F.: {f_dati['partita_iva']}\nContatto: {f_dati['email_contatto']}"
                    
                    id_prev_nuovo = 501 if df_preventivi.empty else int(pd.to_numeric(df_preventivi["id_preventivo"], errors='coerce').max()) + 1
                    nuovo_prev_df = pd.DataFrame([{
                        "id_preventivo": id_prev_nuovo,
                        "id_richiesta_mag": id_fabb_scelto,
                        "fornitore": blocco_spett_le,
                        "importo_ivato": f"{importo_lordo:.2f}",
                        "data_inserimento": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "stato_approvazione": "In valutazione",
                        "note": note_preventivo.strip(),
                        "cig": "",
                        "determina": ""
                    }])
                    carica_su_sheet(pd.concat([df_preventivi, nuovo_prev_df], ignore_index=True), "Registro_Preventivi")
                    st.success(f"Preventivo ID {id_prev_nuovo} salvato! I dati dell'azienda sono stati precompilati dalla rubrica senza doverli scrivere.")
                    st.rerun()
                        
    # ---------------------------------------------------------
    # TAB 4: EMISSIONE LETTERA D'ORDINE
    # ---------------------------------------------------------
    with tab_registro_finito:
        st.markdown("### Valutazione, Approvazione ed Emissione Lettera d'Ordine")
        if df_preventivi.empty:
            st.info("Nessun preventivo registrato a storico.")
        else:
            st.dataframe(df_preventivi, use_container_width=True, hide_index=True)
            st.markdown("---")
            
            preventivi_valutabili = df_preventivi[df_preventivi["stato_approvazione"] == "In valutazione"]
            if preventivi_valutabili.empty:
                st.info("Tutti i preventivi inseriti sono già stati lavorati o emessi.")
            else:
                st.markdown("#### ⚙️ Compila Dati Ministeriali ed Emetti Ordine")
                opzioni_preventivo = [f"PREV ID {p['id_preventivo']} - {p['fornitore'].splitlines()[0]} (€ {p['importo_ivato']})" for _, p in preventivi_valutabili.iterrows()]
                scelta_p = st.selectbox("Seleziona il preventivo da deliberare ed ordinare:", opzioni_preventivo)
                id_p_scelto = scelta_p.split(" - ")[0].replace("PREV ID ", "").strip()
                
                riga_p = df_preventivi[df_preventivi["id_preventivo"].astype(str) == str(id_p_scelto)].iloc[0]
                
                st.markdown("##### 📄 Dati per Atto d'Ordine d'Istituto")
                c1, c2 = st.columns(2)
                with c1:
                    cig_input = st.text_input("Codice CIG (Legge 136/2010):", placeholder="Es. Z1A3C4D5E6")
                    determina_input = st.text_input("Numero/Anno Determina:", placeholder="Es. 145/2026")
                    data_prev_forn = st.text_input("Data di invio preventivo ditta:", value=datetime.now().strftime("%d/%m/%Y"))
                with c2:
                    prot_forn = st.text_input("Protocollo ditta mittente (se presente):", value="N.D.")
                    prot_inst = st.text_input("Protocollo ingresso ISISS Scarpa:", placeholder="Es. 0004120/E")
                    qta_input = st.number_input("Quantità complessiva colli/beni:", min_value=1, value=1)
                
                riga_fabb = df_fabbisogni[df_fabbisogni["id_richiesta_mag"].astype(str) == str(riga_p["id_richiesta_mag"])]
                materiale_desc = riga_fabb.iloc[0]["materiale_richiesto"] if not riga_fabb.empty else "Fornitura Beni da Magazzino"
                
                if st.button("🔴 COMPLETA E INVIA PREVENTIVO A REGISTRO", type="primary", use_container_width=True):
                    if not cig_input.strip() or not determina_input.strip() or not prot_inst.strip():
                        st.error("Impossibile procedere: CIG, Determina e Protocollo dell'Istituto sono campi obbligatori.")
                    else:
                        mappa_dati_pdf = {
                            "fornitore": riga_p["fornitore"],
                            "oggetto_ordine": f"Affidamento diretto fornitura materiale d'istituto - Richiesta Magazzino ID {riga_p['id_richiesta_mag']}",
                            "data_preventivo": data_prev_forn,
                            "protocollo_fornitore": prot_forn,
                            "protocollo_istituto": prot_inst,
                            "descrizione_materiale": materiale_desc,
                            "quantita": qta_input,
                            "importo_ivato": riga_p["importo_ivato"],
                            "cig": cig_input.strip().upper(),
                            "determina": determina_input.strip()
                        }
                        
                        idx_p = df_preventivi.index[df_preventivi["id_preventivo"].astype(str) == str(id_p_scelto)].tolist()[0]
                        df_preventivi.at[idx_p, "stato_approvazione"] = "Approvato ed Emesso"
                        df_preventivi.at[idx_p, "cig"] = cig_input.strip().upper()
                        df_preventivi.at[idx_p, "determina"] = determina_input.strip()
                        carica_su_sheet(df_preventivi, "Registro_Preventivi")
                        
                        if not riga_fabb.empty:
                            idx_f = df_fabbisogni.index[df_fabbisogni["id_richiesta_mag"].astype(str) == str(riga_p["id_richiesta_mag"])].tolist()[0]
                            df_fabbisogni.at[idx_f, "stato_iter"] = "Ordinato / Evaso"
                            carica_su_sheet(df_fabbisogni, "Richieste_Preventivo_Magazzino")
                        
                        if genera_pdf_ordine_fornitore and carica_su_drive_unico:
                            pdf_bytes = genera_pdf_ordine_fornitore(mappa_dati_pdf)
                            nome_file_generato = f"Lettera_Ordine_PREV_{id_p_scelto}_CIG_{cig_input.strip().upper()}.pdf"
                            
                            caricato_su_drive = carica_su_drive_unico(pdf_bytes, nome_file_generato, "application/pdf", id_cartella_ordini)
                            
                            if caricato_su_drive:
                                st.success(f"📦 Atto d'ordine archiviato nel cloud di Istituto con successo!")
                            else:
                                st.warning("Atto d'ordine approvato internamente, ma si è verificato un errore di comunicazione con la cartella Google Drive.")
                                
                            st.download_button(
                                label="📥 Scarica Copia Locale Lettera d'Ordine (PDF)",
                                data=pdf_bytes,
                                file_name=nome_file_generato,
                                mime_type="application/pdf",
                                use_container_width=True
                            )
                            st.balloons()
                            st.info("Aggiornamento interfaccia in corso...")
                            st.rerun()
