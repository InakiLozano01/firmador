from app.services.signatures_service import SignaturesService
from app.config.state import app_state
import app.exceptions.signature_exc as signatures_exc
class SignaturesController:
    def __init__(self):
        self.service = SignaturesService()

    def init_signature_pdf(self, pdfs, certificates):
        id_docs_signeds = []
        errors_stack = []
        datas_to_sign = []
        for pdf in pdfs:
            try:
                id_doc_signed, error_stack, data_to_sign = self.service.init_signature_pdf(pdf, certificates)
                if error_stack is None:
                    id_docs_signeds.append(id_doc_signed)
                    datas_to_sign.append(data_to_sign)
                else:
                    errors_stack.append(error_stack)
            except Exception as e:
                if app_state.conn and app_state.conn.closed == 0:
                    app_state.conn.rollback()
                    app_state.conn.close()
            if app_state.conn and app_state.conn.closed == 0:
                app_state.conn.commit()
                app_state.conn.close()
        
        docs_not_signed = []
        for error in errors_stack:
            docs_not_signed.append(error['idDocFailed'])

        return id_docs_signeds, docs_not_signed, datas_to_sign, errors_stack
    
    def end_signature_pdf(self, pdfs, certificates):
        id_docs_signeds = []
        errors_stack = []
        for pdf in pdfs:
            try:
                id_doc_signed, error_stack = self.service.end_signature_pdf(pdf, certificates)
                if error_stack is None:
                    id_docs_signeds.append(id_doc_signed)
                else:
                    errors_stack.append(error_stack)
            except Exception as e:
                if app_state.conn and app_state.conn.closed == 0:
                    app_state.conn.rollback()
                    app_state.conn.close()
            if app_state.conn and app_state.conn.closed == 0:
                app_state.conn.commit()
                app_state.conn.close()
        
        docs_not_signed = []
        for error in errors_stack:
            docs_not_signed.append(error['idDocFailed'])

        return id_docs_signeds, docs_not_signed, errors_stack
    
    def init_sign_jades(self, certificates, indexes_data, data_signature):
        id_exps_signeds = []
        errors_stack = []
        data_to_sign = []
        index_signeds = []

        for index_data in indexes_data:
            try:
                id_exp_signed, error_stack, data_to_sign, index_signed = self.service.init_sign_jades(index_data, certificates, data_signature)
                if error_stack is None:
                    id_exps_signeds.append(id_exp_signed)
                    data_to_sign.append(data_to_sign)
                    index_signeds.append(index_signed)
                else:
                    errors_stack.append(error_stack)
            except Exception as e:
                continue
        
        exps_not_signed = []
        for error in errors_stack:
            exps_not_signed.append(error['idExpFailed'])

        return id_exps_signeds, exps_not_signed, data_to_sign, index_signeds, errors_stack
    
    def end_sign_jades(self, certificates, indexes_data, data_signature):
        id_exps_signeds = []
        errors_stack = []
        index_signeds = []
        for index_data in indexes_data:
            try:
                id_exp_signed, error_stack, index_signed = self.service.end_sign_jades(index_data, certificates, data_signature)
                if error_stack is None:
                    id_exps_signeds.append(id_exp_signed)
                    index_signeds.append(index_signed)
                else:
                    errors_stack.append(error_stack)
            except Exception as e:
                continue
        
        exps_not_signed = []
        for error in errors_stack:
            exps_not_signed.append(error['idExpFailed'])

        return id_exps_signeds, exps_not_signed, index_signeds, errors_stack

