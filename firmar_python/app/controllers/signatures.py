import logging
from app.services.signatures_service import SignaturesService
from app.config.state import app_state
from app.exceptions import signature_exc

# Configure logging
logger = logging.getLogger(__name__)

class SignaturesController:
    def __init__(self):
        self.service = SignaturesService()
        logger.debug("SignaturesController initialized")

    def init_signature_pdf(self, pdfs, certificates):
        logger.info("Starting PDF signature initialization")
        logger.debug(f"Processing {len(pdfs)} PDFs")
        
        id_docs_signeds = []
        errors_stack = []
        datas_to_sign = []
        success = True
        message = "Firma iniciada correctamente"
        
        for i, pdf in enumerate(pdfs):
            logger.debug(f"Processing PDF {i+1}/{len(pdfs)}")
            try:
                id_doc_signed, error_stack, data_to_sign = self.service.init_signature_pdf(pdf, certificates)
                if error_stack is None:
                    if id_doc_signed:
                        id_docs_signeds.append(id_doc_signed)
                    if data_to_sign:
                        datas_to_sign.append(data_to_sign)
                    logger.debug(f"Successfully initialized signature for PDF {i+1}")
                else:
                    errors_stack.append(error_stack)
                    success = False
                    message = "Error al procesar algunos documentos"
                    logger.warning(f"Failed to initialize signature for PDF {i+1}: {error_stack}")
            except Exception as e:
                logger.error(f"Exception during PDF {i+1} signature initialization: {str(e)}", exc_info=True)
                errors_stack.append({
                    "idDocFailed": pdf.get('id_doc'),
                    "message": str(e)
                })
                success = False
                message = "Error al procesar algunos documentos"
                if app_state.conn and app_state.conn.closed == 0:
                    logger.debug("Rolling back database connection")
                    app_state.conn.rollback()
                    app_state.conn.close()
            if app_state.conn and app_state.conn.closed == 0:
                logger.debug("Committing and closing database connection")
                app_state.conn.commit()
                app_state.conn.close()
        
        docs_not_signed = []
        for error in errors_stack:
            if error.get('idDocFailed'):
                docs_not_signed.append(error['idDocFailed'])
        
        logger.info(f"PDF signature initialization completed. Successful: {len(id_docs_signeds)}, Failed: {len(docs_not_signed)}")
        return id_docs_signeds, docs_not_signed, datas_to_sign, errors_stack, success, message
    
    def end_signature_pdf(self, pdfs, certificates):
        logger.info("Starting PDF signature finalization")
        logger.debug(f"Processing {len(pdfs)} PDFs")
        
        id_docs_signeds = []
        errors_stack = []
        
        for i, pdf in enumerate(pdfs):
            logger.debug(f"Processing PDF {i+1}/{len(pdfs)}")
            try:
                id_doc_signed, error_stack = self.service.end_signature_pdf(pdf, certificates)
                if error_stack is None:
                    id_docs_signeds.append(id_doc_signed)
                    logger.debug(f"Successfully finalized signature for PDF {i+1}")
                else:
                    errors_stack.append(error_stack)
                    logger.warning(f"Failed to finalize signature for PDF {i+1}: {error_stack}")
            except Exception as e:
                logger.error(f"Exception during PDF {i+1} signature finalization: {str(e)}", exc_info=True)
                if app_state.conn and app_state.conn.closed == 0:
                    logger.debug("Rolling back database connection")
                    app_state.conn.rollback()
                    app_state.conn.close()
            if app_state.conn and app_state.conn.closed == 0:
                logger.debug("Committing and closing database connection")
                app_state.conn.commit()
                app_state.conn.close()
        
        docs_not_signed = []
        for error in errors_stack:
            docs_not_signed.append(error['idDocFailed'])
        
        logger.info(f"PDF signature finalization completed. Successful: {len(id_docs_signeds)}, Failed: {len(docs_not_signed)}")
        return id_docs_signeds, docs_not_signed, errors_stack
    
    def init_sign_jades(self, certificates, indexes_data, data_signature):
        """
        Initialize JADES signature process.
        
        Args:
            certificates: Certificate data
            indexes_data: List of index data to sign
            data_signature: Signature metadata
            
        Returns:
            tuple: (id_exps_signeds, exps_not_signed, data_to_sign, index_signeds, errors_stack)
        """
        logger.info("Starting JADES signature initialization")
        logger.debug(f"Processing {len(indexes_data)} indexes")
        
        id_exps_signeds = []
        errors_stack = []
        data_to_sign = []
        index_signeds = []

        for i, index_data in enumerate(indexes_data):
            logger.debug(f"Processing index {i+1}/{len(indexes_data)}")
            try:
                id_exp_signed, error_stack, data_to_sign_item, index_signed = self.service.init_sign_jades(index_data, certificates, data_signature)
                if error_stack is None:
                    if id_exp_signed:
                        id_exps_signeds.append(id_exp_signed)
                    if data_to_sign_item:
                        data_to_sign.append(data_to_sign_item)
                    if index_signed:
                        index_signeds.append(index_signed)
                    logger.debug(f"Successfully initialized JADES signature for index {i+1}")
                else:
                    errors_stack.append(error_stack)
                    logger.warning(f"Failed to initialize JADES signature for index {i+1}: {error_stack}")
            except Exception as e:
                logger.error(f"Exception during index {i+1} JADES signature initialization: {str(e)}", exc_info=True)
                errors_stack.append({
                    "idExpFailed": index_data.get('index', {}).get('numero', 'unknown'),
                    "message": f"Error inesperado en init_sign_jades: {str(e)}",
                    "stack": str(e.__traceback__)
                })
                continue
        
        exps_not_signed = []
        for error in errors_stack:
            if error.get('idExpFailed'):
                exps_not_signed.append(error['idExpFailed'])
        
        logger.info(f"JADES signature initialization completed. Successful: {len(id_exps_signeds)}, Failed: {len(exps_not_signed)}")
        return id_exps_signeds, exps_not_signed, data_to_sign, index_signeds, errors_stack
    
    def end_sign_jades(self, certificates, indexes_data, data_signature):
        logger.info("Starting JADES signature finalization")
        logger.debug(f"Processing {len(indexes_data)} indexes")
        
        id_exps_signeds = []
        errors_stack = []
        index_signeds = []
        
        for i, index_data in enumerate(indexes_data):
            logger.debug(f"Processing index {i+1}/{len(indexes_data)}")
            try:
                id_exp_signed, error_stack, index_signed = self.service.end_sign_jades(index_data, certificates, data_signature)
                if error_stack is None:
                    id_exps_signeds.append(id_exp_signed)
                    index_signeds.append(index_signed)
                    logger.debug(f"Successfully finalized JADES signature for index {i+1}")
                else:
                    errors_stack.append(error_stack)
                    logger.warning(f"Failed to finalize JADES signature for index {i+1}: {error_stack}")
            except Exception as e:
                logger.error(f"Exception during index {i+1} JADES signature finalization: {str(e)}", exc_info=True)
                continue
        
        exps_not_signed = []
        for error in errors_stack:
            exps_not_signed.append(error['idExpFailed'])
        
        logger.info(f"JADES signature finalization completed. Successful: {len(id_exps_signeds)}, Failed: {len(exps_not_signed)}")
        return id_exps_signeds, exps_not_signed, index_signeds, errors_stack

