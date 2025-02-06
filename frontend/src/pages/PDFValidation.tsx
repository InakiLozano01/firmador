import { useState } from 'react'
import { FileUpload } from '../components/ui/FileUpload'
import { FileList } from '../components/ui/FileList'
import { Button } from '../components/ui/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card'
import { useToast } from '../components/ui/ToastContext'
import { validatePDFs } from '../lib/api'

export default function PDFValidation() {
  const [files, setFiles] = useState<File[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [validationResults, setValidationResults] = useState<any[]>([])
  const { addToast } = useToast()

  const handleFileSelect = (selectedFiles: File[]) => {
    setFiles((prev) => [...prev, ...selectedFiles])
    setValidationResults([])
  }

  const handleFileRemove = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index))
    setValidationResults((prev) => prev.filter((_, i) => i !== index))
  }

  const handleValidatePDFs = async () => {
    if (!files.length) {
      addToast({
        title: 'Error',
        description: 'Please select at least one PDF file',
        variant: 'destructive',
      })
      return
    }

    setIsLoading(true)
    try {
      // Convert files to base64
      const pdfs = await Promise.all(
        files.map(async (file) => {
          return new Promise((resolve, reject) => {
            const reader = new FileReader()
            reader.onload = () => {
              resolve({
                name: file.name,
                content: reader.result?.toString().split(',')[1] || '',
              })
            }
            reader.onerror = reject
            reader.readAsDataURL(file)
          })
        })
      )

      const response = await validatePDFs(pdfs)
      
      if (response.status) {
        setValidationResults(
          response.pdfs.map((result: any, index: number) => ({
            fileName: files[index].name,
            ...result,
          }))
        )

        const hasErrors = response.pdfs.some((result: any) => !result.isValid)
        addToast({
          title: hasErrors ? 'Validation Complete with Issues' : 'Validation Complete',
          description: hasErrors ? 'Some files have invalid signatures' : 'All signatures are valid',
          variant: hasErrors ? 'destructive' : 'success',
        })
      } else {
        throw new Error(response.message)
      }
    } catch (error) {
      addToast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to validate PDFs',
        variant: 'destructive',
      })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>PDF Validation</CardTitle>
          <CardDescription>
            Upload PDF files to validate their digital signatures
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <FileUpload
            onFileSelect={handleFileSelect}
            accept={{
              'application/pdf': ['.pdf'],
            }}
            multiple
          />
          <FileList files={files} onRemove={handleFileRemove} className="mt-4" />
          <div className="flex justify-end">
            <Button
              onClick={handleValidatePDFs}
              isLoading={isLoading}
              disabled={!files.length || isLoading}
            >
              Validate PDFs
            </Button>
          </div>
        </CardContent>
      </Card>

      {validationResults.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Validation Results</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {validationResults.map((result, index) => (
                <div
                  key={index}
                  className={`rounded-lg border p-4 ${
                    result.isValid ? 'border-success' : 'border-destructive'
                  }`}
                >
                  <h3 className="font-medium">{result.fileName}</h3>
                  <p className={`mt-1 text-sm ${
                    result.isValid ? 'text-success' : 'text-destructive'
                  }`}>
                    {result.isValid ? 'Signature is valid' : 'Invalid signature'}
                  </p>
                  {result.signatures && (
                    <div className="mt-2">
                      <p className="text-sm font-medium">Signatures:</p>
                      <div className="mt-1 space-y-2">
                        {result.signatures.map((sig: any, i: number) => (
                          <div key={i} className="rounded bg-muted p-2 text-xs">
                            <p>Signer: {sig.signer}</p>
                            <p>Date: {sig.date}</p>
                            <p>Reason: {sig.reason}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {result.errors?.length > 0 && (
                    <div className="mt-2">
                      <p className="text-sm font-medium text-destructive">Errors:</p>
                      <ul className="list-disc list-inside text-sm text-destructive">
                        {result.errors.map((error: string, i: number) => (
                          <li key={i}>{error}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
} 