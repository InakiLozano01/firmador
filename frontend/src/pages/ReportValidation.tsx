import { useState } from 'react'
import { FileUpload } from '../components/ui/FileUpload'
import { FileList } from '../components/ui/FileList'
import { Button } from '../components/ui/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card'
import { useToast } from '../components/ui/ToastContext'
import { validateReport } from '../lib/api'

const exampleStructure = {
  expediente: {
    root: "/",
    structure: [
      {
        name: "indice.json",
        description: "JSON index file with metadata and document references"
      },
      {
        name: "documentos/",
        description: "Directory containing all PDF documents",
        contents: [
          "documento1.pdf",
          "documento2.pdf",
          "anexos/"
        ]
      }
    ]
  }
}

export default function ReportValidation() {
  const [file, setFile] = useState<File | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [validationResult, setValidationResult] = useState<any | null>(null)
  const { addToast } = useToast()

  const handleFileSelect = (selectedFiles: File[]) => {
    setFile(selectedFiles[0])
    setValidationResult(null)
  }

  const handleFileRemove = () => {
    setFile(null)
    setValidationResult(null)
  }

  const handleValidateReport = async () => {
    if (!file) {
      addToast({
        title: 'Error',
        description: 'Please select a ZIP file',
        variant: 'destructive',
      })
      return
    }

    setIsLoading(true)
    try {
      // In a real implementation, we would need to upload the ZIP file first
      // For now, we'll assume the file is already on the server
      const response = await validateReport(file.name)
      
      if (response.status) {
        setValidationResult(response)
        addToast({
          title: 'Validation Complete',
          description: response.message,
          variant: response.errors?.length ? 'destructive' : 'success',
        })
      } else {
        throw new Error(response.message)
      }
    } catch (error) {
      addToast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to validate report',
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
          <CardTitle>Report Validation</CardTitle>
          <CardDescription>
            Upload a ZIP file containing a complete report to validate its structure and signatures
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <FileUpload
            onFileSelect={handleFileSelect}
            accept={{
              'application/zip': ['.zip'],
            }}
          />
          {file && (
            <FileList
              files={[file]}
              onRemove={() => handleFileRemove()}
              className="mt-4"
            />
          )}
          <div className="flex justify-end">
            <Button
              onClick={handleValidateReport}
              isLoading={isLoading}
              disabled={!file || isLoading}
            >
              Validate Report
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Expected Structure</CardTitle>
          <CardDescription>
            Your ZIP file should follow this structure
          </CardDescription>
        </CardHeader>
        <CardContent>
          <pre className="rounded-lg bg-muted p-4 overflow-x-auto">
            <code>{JSON.stringify(exampleStructure, null, 2)}</code>
          </pre>
        </CardContent>
      </Card>

      {validationResult && (
        <Card>
          <CardHeader>
            <CardTitle>Validation Results</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div
                className={`rounded-lg border p-4 ${
                  !validationResult.errors?.length
                    ? 'border-success'
                    : 'border-destructive'
                }`}
              >
                <h3 className="font-medium">Report Structure</h3>
                <p
                  className={`mt-1 text-sm ${
                    !validationResult.errors?.length
                      ? 'text-success'
                      : 'text-destructive'
                  }`}
                >
                  {validationResult.message}
                </p>

                {validationResult.validation && (
                  <div className="mt-4">
                    <p className="text-sm font-medium">Details:</p>
                    <pre className="mt-2 rounded bg-muted p-2 text-xs overflow-x-auto">
                      <code>
                        {JSON.stringify(validationResult.validation, null, 2)}
                      </code>
                    </pre>
                  </div>
                )}

                {validationResult.errors?.length > 0 && (
                  <div className="mt-4">
                    <p className="text-sm font-medium text-destructive">Errors:</p>
                    <ul className="mt-1 list-disc list-inside text-sm text-destructive">
                      {validationResult.errors.map((error: any, i: number) => (
                        <li key={i}>{error.message}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
} 