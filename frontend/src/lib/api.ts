import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

export interface SignatureResponse {
  status: boolean
  message: string
  docsSigned: string[]
  docsNotSigned: string[]
  dataToSign?: string[]
  errors: Array<{ message: string }>
}

export interface ValidationResponse {
  status: boolean
  message: string
  validation?: any
  original_data?: any
  errors: Array<{ message: string }>
}

export const signPDFs = async (pdfs: any[], certificates: any[]): Promise<SignatureResponse> => {
  const response = await api.post('/firmalote', { pdfs, certificates })
  return response.data
}

export const completePDFSigning = async (pdfs: any[], certificates: any[]): Promise<SignatureResponse> => {
  const response = await api.post('/firmaloteend', { pdfs, certificates })
  return response.data
}

export const signJSONs = async (certificates: any[], indices: any[], datos_firma: any[]): Promise<SignatureResponse> => {
  const response = await api.post('/firmajades', { certificates, indices, datos_firma })
  return response.data
}

export const completeJSONSigning = async (certificates: any[], indices: any[], datos_firma: any[]): Promise<SignatureResponse> => {
  const response = await api.post('/firmajadesend', { certificates, indices, datos_firma })
  return response.data
}

export const validateJSONs = async (data: any): Promise<ValidationResponse> => {
  const response = await api.post('/validarjades', data)
  return response.data
}

export const validatePDFs = async (pdfs: any[]): Promise<ValidationResponse> => {
  const response = await api.post('/validatepdfs', { pdfs })
  return response.data
}

export const validateReport = async (zipFilePath: string): Promise<ValidationResponse> => {
  const response = await api.post('/validar_expediente', { zip_filepath: zipFilePath })
  return response.data
}

export const mergePDFs = async (pdfs: any[], watermarkText: string): Promise<{ status: boolean; message: string; output_pdf: string }> => {
  const response = await api.post('/concatenarpdfs', { pdfs, texto_marca_agua: watermarkText })
  return response.data
}

// Error handler
api.interceptors.response.use(
  response => response,
  error => {
    console.error('API Error:', error.response?.data || error.message)
    return Promise.reject(error)
  }
) 