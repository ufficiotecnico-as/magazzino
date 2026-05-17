import streamlit as st
import pandas as pd
from datetime import datetime

def mostra_interfaccia_preventivi(scarica_da_sheet, carica_su_sheet, invia_email_sistema, url_intermediario, df_istanze, genera_pdf_ordine_fornitore=None, carica_su_drive_unico=None, id_cartella_ordini=None):
    st.markdown("## 📊 Hub Gestione Fornitori & Tracciabilità Preventivi")
    
    tab_richieste, tab_inserimento, tab_registro_finito = st.tabs([
        "📥 Fabbisogni dai Magazzini", 
        "✍️ Inserisci Offerta / Preventivo Ricevuto", 
        "📜 Registro Storico Preventivi"
    ])
    
    df_fabbisogni = scarica_da_sheet("Richieste_Preventivo_Magazzino")
    df_preventivi = scarica_da_sheet("Registro_Preventivi")
    
    with tab_richieste:
        st.markdown("### Elenco materiali segnalati dai capigruppo logistici")
        if df_fabbisogni.empty:
            st.info("Nessuna segnalazione di fabbisogno aperta al momento.")
        else:
            st.dataframe(df_fabbisogni, use_container_width=True, hide_index=True)
            
    with tab_inserimento:
        st.markdown("### Collega un preventivo economico a una richiesta interna")
        if df_fabbisogni.empty:
            st.warning("Per inserire un preventivo deve essere presente almeno un fabbisogno aperto.")
        else:
            lista_fabbisogni = [f"ID {r['id_richiesta_mag']} - {r['materiale_richiesto']} ({r['magazzino_origine']})" for _, r in df_fabbisogni.iterrows()]
            scelta_fabb = st.selectbox("Seleziona il fabbisogno d'origine:", lista_fabbisogni)
            id_fabb_scelto = scelta_fabb.split(" - ")[0].replace("ID ", "").strip()
            
            with st.form("form_aggiunta_preventivo"):
                fornitore_denominazione = st.text_area("Spett.le Fornitore (Ragione Sociale, Sede, P.IVA):", placeholder="Es:\nACME S.p.A.\nVia Roma 10, Milano\nP.IVA 01234567890")
                importo_lordo = st.number_input("Importo Totale IVATO (€):", min_value=0.0, step=0.01)
                note_preventivo = st.text_area("Note aggiuntive / Condizioni di consegna:")
                
                if st.form_submit_button("Registra preventivo a sistema"):
                    if fornitore_denominazione.strip():
                        id_prev_nuovo = 501 if df_preventivi.empty else int(pd.to_numeric(df_preventivi["id_preventivo"], errors='coerce').max()) + 1
                        nuovo_prev_df = pd.DataFrame([{
                            "id_preventivo": id_prev_nuovo,
                            "id_richiesta_mag": id_fabb_scelto,
                            "fornitore": fornitore_denominazione.strip(),
                            "importo_ivato": f"{importo_lordo:.2f}",
                            "data_inserimento": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "stato_approvazione": "In valutazione",
                            "note": note_preventivo.strip(),
                            "cig": "",
                            "determina": ""
                        }])
                        carica_su_sheet(pd.concat([df_preventivi, nuovo_prev_df], ignore_index=True), "Registro_Preventivi")
                        st.success(f"Preventivo ID {id_prev_nuovo} salvato correttamente nel database!")
                    else:
                        st.error("Inserire l'anagrafica del fornitore.")
                        
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
                
                # Campi obbligatori richiesti dal tuo documento HTML
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
                
                # Cerchiamo il materiale corrispondente
                riga_fabb = df_fabbisogni[df_fabbisogni["id_richiesta_mag"].astype(str) == str(riga_p["id_richiesta_mag"])]
                materiale_desc = riga_fabb.iloc[0]["materiale_richiesto"] if not riga_fabb.empty else "Fornitura Beni da Magazzino"
                
                if st.button("🔴 COMPLETA E INVIA PREVENTIVO A REGISTRO", type="primary", use_container_width=True):
                    if not cig_input.strip() or not determina_input.strip() or not prot_inst.strip():
                        st.error("Impossibile procedere: CIG, Determina e Protocollo dell'Istituto sono campi obbligatori.")
                    else:
                        # Prepariamo la struttura dati strutturata per la funzione PDF
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
                        
                        # Aggiorniamo i dati strutturati sul database Sheets
                        idx_p = df_preventivi.index[df_preventivi["id_preventivo"].astype(str) == str(id_p_scelto)].tolist()[0]
                        df_preventivi.at[idx_p, "stato_approvazione"] = "Approvato ed Emesso"
                        df_preventivi.at[idx_p, "cig"] = cig_input.strip().upper()
                        df_preventivi.at[idx_p, "determina"] = determina_input.strip()
                        carica_su_sheet(df_preventivi, "Registro_Preventivi")
                        
                        # Aggiorniamo lo stato del fabbisogno logistico originario per chiuderlo
                        if not riga_fabb.empty:
                            idx_f = df_fabbisogni.index[df_fabbisogni["id_richiesta_mag"].astype(str) == str(riga_p["id_richiesta_mag"])].tolist()[0]
                            df_fabbisogni.at[idx_f, "stato_iter"] = "Ordinato / Evaso"
                            carica_su_sheet(df_fabbisogni, "Richieste_Preventivo_Magazzino")
                        
                        # Generazione e archiviazione automatica del PDF su Cloud Drive
                        if genera_pdf_ordine_fornitore and carica_su_drive_unico:
                            pdf_bytes = genera_pdf_ordine_fornitore(mappa_dati_pdf)
                            nome_file_generato = f"Lettera_Ordine_PREV_{id_p_scelto}_CIG_{cig_input.strip().upper()}.pdf"
                            
                            caricato_su_drive = carica_su_drive_unico(pdf_bytes, nome_file_generato, "application/pdf", id_cartella_ordini)
                            
                            if caricato_su_drive:
                                st.success(f"📦 Atto d'ordine archiviato nel cloud di Istituto con successo!")
                            else:
                                st.warning("Atto d'ordine approvato internamente, ma si è verificato un errore di comunicazione con la cartella Google Drive.")
                                
                            # Permettiamo lo scaricamento manuale immediato all'impiegato amministrativo
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
