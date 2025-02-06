import { useState } from 'react'
import { FileUpload } from '../components/ui/FileUpload'
import { FileList } from '../components/ui/FileList'
import { Button } from '../components/ui/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card'
import { useToast } from '../components/ui/ToastContext'
import { signJSONs, completeJSONSigning } from '../lib/api'

const exampleJSON = {
  expediente: {
    id: "EXP123",
    fecha: "2024-02-05",
    documentos: [
      {
        id: "DOC1",
        tipo: "resolucion",
        contenido: "Base64EncodedContent",
        hash: "SHA256Hash"
      }
    ],
    metadatos: {
      tribunal: "Ejemplo",
      sala: "Primera",
      causa: "123-2024"
    }
  }
}

export default function JSONSigning() {
  const [files, setFiles] = useState<File[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const { addToast } = useToast()

  const handleFileSelect = (selectedFiles: File[]) => {
    setFiles((prev) => [...prev, ...selectedFiles])
  }

  const handleFileRemove = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const handleSignJSONs = async () => {
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
      // TODO: Get certificates from firma_cliente
      const certificates = []
      
      // Read and parse JSON files
      const indices = await Promise.all(
        files.map(async (file) => {
          return new Promise<any>((resolve, reject) => {
            const reader = new FileReader()
            reader.onload = () => {
              try {
                const content = JSON.parse(reader.result as string)
                resolve(content)
              } catch (error) {
                reject(new Error(`Invalid JSON in file ${file.name}`))
              }
            }
            reader.onerror = reject
            reader.readAsText(file)
          })
        })
      )

      const datos_firma = indices.map((indice) => ({
        id: indice.expediente.id,
        hash: indice.expediente.documentos[0].hash,
      }))

      const response = await signJSONs(certificates, indices, datos_firma)
      
      if (response.status) {
        const completeResponse = await completeJSONSigning(certificates, indices, datos_firma)
        if (completeResponse.status) {
          addToast({
            title: 'Success',
            description: 'JSONs signed successfully',
            variant: 'success',
          })
          setFiles([])
        } else {
          throw new Error(completeResponse.message)
        }
      } else {
        throw new Error(response.message)
      }
    } catch (error) {
      addToast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to sign JSONs',
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
          <CardTitle>JSON Signing</CardTitle>
          <CardDescription>
            Upload JSON files to sign them with your certificate
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
              onClick={handleSignJSONs}
              isLoading={isLoading}
              disabled={!files.length || isLoading}
            >
              Sign JSONs
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Example JSON Structure</CardTitle>
          <CardDescription>
            Your JSON files should follow this structure
          </CardDescription>
        </CardHeader>
        <CardContent>
          <pre className="rounded-lg bg-muted p-4 overflow-x-auto">
            <code>{JSON.stringify(exampleJSON, null, 2)}</code>
          </pre>
        </CardContent>
      </Card>
    </div>
  )
} 