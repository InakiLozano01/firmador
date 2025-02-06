import { useState } from 'react'
import { FileUpload } from '../components/ui/FileUpload'
import { FileList } from '../components/ui/FileList'
import { Button } from '../components/ui/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card'
import { useToast } from '../components/ui/ToastContext'
import { validateJSONs } from '../lib/api'

export default function JSONValidation() {
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

  const handleValidateJSONs = async () => {
    if (!files.length) {
      addToast({
        title: 'Error',
        description: 'Please select at least one JSON file',
        variant: 'destructive',
      })
      return
    }

    setIsLoading(true)
    try {
      const results = await Promise.all(
        files.map(async (file) => {
          return new Promise<any>((resolve, reject) => {
            const reader = new FileReader()
            reader.onload = async () => {
              try {
                const content = JSON.parse(reader.result as string)
                const response = await validateJSONs(content)
                resolve({
                  fileName: file.name,
                  ...response,
                })
              } catch (error) {
                reject(new Error(`Invalid JSON in file ${file.name}`))
              }
            }
            reader.onerror = reject
            reader.readAsText(file)
          })
        })
      )

      setValidationResults(results)
      
      const hasErrors = results.some((result) => !result.status)
      addToast({
        title: hasErrors ? 'Validation Complete with Errors' : 'Validation Complete',
        description: hasErrors ? 'Some files failed validation' : 'All files are valid',
        variant: hasErrors ? 'destructive' : 'success',
      })
    } catch (error) {
      addToast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to validate JSONs',
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
          <CardTitle>JSON Validation</CardTitle>
          <CardDescription>
            Upload JSON files to validate their signatures and structure
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <FileUpload
            onFileSelect={handleFileSelect}
            accept={{
              'application/json': ['.json'],
            }}
            multiple
          />
          <FileList files={files} onRemove={handleFileRemove} className="mt-4" />
          <div className="flex justify-end">
            <Button
              onClick={handleValidateJSONs}
              isLoading={isLoading}
              disabled={!files.length || isLoading}
            >
              Validate JSONs
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
                    result.status ? 'border-success' : 'border-destructive'
                  }`}
                >
                  <h3 className="font-medium">{result.fileName}</h3>
                  <p className={`mt-1 text-sm ${
                    result.status ? 'text-success' : 'text-destructive'
                  }`}>
                    {result.message}
                  </p>
                  {result.validation && (
                    <pre className="mt-2 rounded bg-muted p-2 text-xs overflow-x-auto">
                      <code>{JSON.stringify(result.validation, null, 2)}</code>
                    </pre>
                  )}
                  {result.errors?.length > 0 && (
                    <div className="mt-2">
                      <p className="text-sm font-medium text-destructive">Errors:</p>
                      <ul className="list-disc list-inside text-sm text-destructive">
                        {result.errors.map((error: any, i: number) => (
                          <li key={i}>{error.message}</li>
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