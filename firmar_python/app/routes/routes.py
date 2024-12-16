# Archivo de rutas para la API

from flask import jsonify, request
import os
from app.controllers.signatures import SignaturesController
from app.controllers.tools import ToolsController
from app.controllers.validations import ValidationsController
import logging

signatures_controller = SignaturesController()
tools_controller = ToolsController()
validations_controller = ValidationsController()
logger = logging.getLogger(__name__)

def register_routes(app):
    @app.route('/firmalote', methods=['POST'])
    def firmalote():
        """
        Route for batch signing process or complete electronic signing process.
        """
        try:
            data = request.get_json()
            pdfs = data['pdfs']
            certificates = data['certificates']
        except Exception as e:
            logger.error(f"Error getting request data: {str(e)}", exc_info=True)
            return jsonify({
                "status": False, 
                "message": f"Error al obtener los datos de la request: {str(e)}",
                "errors": [{
                    "message": str(e)
                }]
            }), 500

        try:
            id_docs_signeds, docs_not_signed, datas_to_sign, errors_stack, success, message = signatures_controller.init_signature_pdf(pdfs, certificates)
            return jsonify({
                "status": success, 
                "message": message, 
                "docsSigned": id_docs_signeds, 
                "docsNotSigned": docs_not_signed, 
                "dataToSign": datas_to_sign, 
                "errors": errors_stack
            }), 200
        except Exception as e:
            logger.error(f"Error in signature process: {str(e)}", exc_info=True)
            return jsonify({
                "status": False, 
                "message": f"Error en la firma: {str(e)}",
                "errors": [{
                    "message": str(e)
                }]
            }), 500

    @app.route('/firmaloteend', methods=['POST'])
    def firmaloteend():
        """
        Route for completing the digital signing process.
        """
        try:
            data = request.get_json()
            pdfs = data['pdfs']
            certificates = data['certificates']
        except Exception as e:
            return jsonify({"status": False, "message": "Error al obtener los datos de la request: " + str(e)}), 500
        
        try:
            id_docs_signeds, docs_not_signed, errors_stack = signatures_controller.end_signature_pdf(pdfs, certificates)
            return jsonify({
                "status": True, 
                "message": "Firma completada correctamente", 
                "docsSigned": id_docs_signeds, 
                "docsNotSigned": docs_not_signed, 
                "errors": errors_stack
            }), 200
        except Exception as e:
            return jsonify({"status": False, "message": "Error en la firma: " + str(e)}), 500
    
    @app.route('/firmajades', methods=['POST'])
    def firmajades():
        """
        Route for signing documents using JADES.
        
        Returns:
            JSON response with signing results and any errors
        """
        try:
            data = request.get_json()
            if not data:
                logger.error("No data provided in request")
                return jsonify({
                    "status": False,
                    "message": "No se proporcionaron datos para firmar",
                    "errors": [{
                        "message": "Request body is empty",
                        "details": "No se recibieron datos en el cuerpo de la petición"
                    }]
                }), 400

            try:
                certificates = data['certificates']
                indexes_data = data['indices']
                data_signature = data['datos_firma']
            except KeyError as e:
                logger.error(f"Missing required field in request: {str(e)}")
                return jsonify({
                    "status": False,
                    "message": f"Faltan datos requeridos en la petición: {str(e)}",
                    "errors": [{
                        "message": f"Missing required field: {str(e)}",
                        "details": "Campo requerido no encontrado en la petición"
                    }]
                }), 400
        except Exception as e:
            logger.error(f"Error processing request data: {str(e)}", exc_info=True)
            return jsonify({
                "status": False,
                "message": f"Error al procesar los datos de la petición: {str(e)}",
                "errors": [{
                    "message": str(e),
                    "stack": str(e.__traceback__),
                    "details": "Error al procesar el cuerpo de la petición"
                }]
            }), 400
        
        try:
            id_exps_signeds, exps_not_signed, data_to_sign, index_signeds, errors_stack = signatures_controller.init_sign_jades(certificates, indexes_data, data_signature)
            
            response = {
                "status": True if not errors_stack else False,
                "message": "Firma iniciada correctamente" if not errors_stack else "Error al procesar algunos expedientes",
                "expsSigned": id_exps_signeds,
                "expsNotSigned": exps_not_signed,
                "dataToSign": data_to_sign,
                "indexSigneds": index_signeds,
                "errors": errors_stack
            }
            
            if errors_stack:
                logger.warning(f"JADES signing completed with {len(errors_stack)} errors")
                logger.debug(f"Error details: {errors_stack}")
            else:
                logger.info("JADES signing completed successfully")
                
            return jsonify(response), 200
            
        except Exception as e:
            logger.error(f"Unexpected error in JADES signing: {str(e)}", exc_info=True)
            return jsonify({
                "status": False,
                "message": f"Error inesperado en la firma JADES: {str(e)}",
                "errors": [{
                    "message": str(e),
                    "stack": str(e.__traceback__),
                    "details": "Error general en el endpoint firmajades"
                }]
            }), 500
    
    @app.route('/firmajadesend', methods=['POST'])
    def firmajadesend():
        """
        Route for completing the JADES signing process.
        """
        try:
            data = request.get_json()
            certificates = data['certificates']
            indexes_data = data['indices']
            data_signature = data['datos_firma']
        except Exception as e:
            return jsonify({"status": False, "message": "Error al obtener los datos de la request: " + str(e)}), 500
        
        try:
            id_exps_signeds, exps_not_signed, index_signeds, errors_stack = signatures_controller.end_sign_jades(certificates, indexes_data, data_signature)
            return jsonify({
                "status": True, 
                "message": "Firma completada correctamente", 
                "expsSigned": id_exps_signeds, 
                "expsNotSigned": exps_not_signed, 
                "indexSigneds": index_signeds, 
                "errors": errors_stack
            }), 200
        except Exception as e:
            return jsonify({"status": False, "message": "Error en la firma: " + str(e)}), 500
    
    @app.route('/validarjades', methods=['POST'])
    def validarjades():
        """
        Route for validating JADES signatures.
        
        Returns:
            JSON response with validation results and any errors
        """
        try:
            data = request.get_json()
            if not data:
                logger.error("No data provided in request")
                return jsonify({
                    "status": False,
                    "message": "No se proporcionaron datos para validar",
                    "errors": [{
                        "message": "Request body is empty",
                        "details": "No se recibieron datos en el cuerpo de la petición"
                    }]
                }), 400
        except Exception as e:
            logger.error(f"Error getting request data: {str(e)}", exc_info=True)
            return jsonify({
                "status": False,
                "message": f"Error al obtener los datos de la request: {str(e)}",
                "errors": [{
                    "message": str(e),
                    "stack": str(e.__traceback__),
                    "details": "Error al procesar el cuerpo de la petición"
                }]
            }), 400
        
        try:
            validation, data_original, success, message, errors = validations_controller.validate_signatures_jades(data)
            
            response = {
                "status": success,
                "message": message,
                "validation": validation,
                "original_data": data_original,
                "errors": errors
            }
            
            if not success:
                logger.warning(f"Validation failed: {message}")
                logger.debug(f"Validation errors: {errors}")
            else:
                logger.info("Validation completed successfully")
                
            return jsonify(response), 200
            
        except Exception as e:
            logger.error(f"Error in JADES validation: {str(e)}", exc_info=True)
            return jsonify({
                "status": False,
                "message": f"Error inesperado en la validación de los JSONs: {str(e)}",
                "errors": [{
                    "message": str(e),
                    "stack": str(e.__traceback__),
                    "details": "Error general en el endpoint validarjades"
                }]
            }), 500
    
    @app.route('/validatepdfs', methods=['POST'])
    def validatepdfs():
        """
        Route for validating PDFs.
        """
        try:
            data = request.get_json()
            pdfs = data['pdfs']
        except Exception as e:
            logger.error(f"Error getting request data: {str(e)}", exc_info=True)
            return jsonify({
                "status": False,
                "message": f"Error al obtener los datos de la request: {str(e)}",
                "errors": [{
                    "message": str(e)
                }]
            }), 500
        
        try:
            results, errors, success, message = validations_controller.validate_signatures_pdf(pdfs)
            return jsonify({
                "status": success,
                "message": message,
                "pdfs": results,
                "errors": errors
            }), 200
        except Exception as e:
            logger.error(f"Error in PDF validation: {str(e)}", exc_info=True)
            return jsonify({
                "status": False,
                "message": f"Error en la validación de los PDFs: {str(e)}",
                "errors": [{
                    "message": str(e)
                }]
            }), 500
    
    @app.route('/validar_expediente', methods=['POST'])
    def validar_expediente():
        """
        Route for validating an entire set of documents (expediente) in compressed format.
        """
        try:
            data = request.get_json()
            file_path = data.get('zip_filepath')
            path = "/app/expedientes/" + file_path
            if not file_path or not os.path.exists(path):
                return jsonify({
                    "status": False, 
                    "message": f"Archivo no encontrado en la ruta: {path}"
                }), 400
        except Exception as e:
            return jsonify({"status": False, "message": "Error al obtener los datos de la request: " + str(e)}), 500
        
        try:
            controller_response, code = validations_controller.validate_expediente(path)
            return controller_response, code
        except Exception as e:
            return jsonify({"status": False, "message": "Error en la validacion del expediente: " + str(e)}), 500
    
    @app.route('/concatenarpdfs', methods=['POST'])
    def concatenarpdfs():
        """
        Route for concatenating PDFs.
        """
        try:
            data = request.get_json()
            pdfs = data['pdfs']
            watermark_text = data['texto_marca_agua']
        except Exception as e:
            return jsonify({"status": False, "message": "Error al obtener los datos de la request: " + str(e)}), 500

        try:
            controller_response = tools_controller.merge_and_watermark_pdfs(pdfs, watermark_text)
            return jsonify({
                "status": True, 
                "message": "Concatenacion y watermarking completados correctamente", 
                "output_pdf": controller_response
            }), 200
        except Exception as e:
            return jsonify({"status": False, "message": "Error en la concatenacion y watermarking: " + str(e)}), 500
    
    @app.route('/test', methods=['GET', 'POST'])
    def test_route():
        """
        Test route.
        """
        return jsonify({"status": "success", "message": "Test route"}), 200











