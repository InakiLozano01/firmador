import { useState } from 'react'
import { FileUpload } from '../components/ui/FileUpload'
import { FileList } from '../components/ui/FileList'
import { Button } from '../components/ui/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card'
import { useToast } from '../components/ui/ToastContext'
import { signPDFs, completePDFSigning } from '../lib/api'

export default function PDFSigning() {
  const [files, setFiles] = useState<File[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const { addToast } = useToast()

  const handleFileSelect = (selectedFiles: File[]) => {
    setFiles((prev) => [...prev, ...selectedFiles])
  }

  const handleFileRemove = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const handleSignPDFs = async () => {
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
      // TODO: Get certificates from firma_cliente
      const certificates = []
      
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

      const response = await signPDFs(pdfs, certificates)
      
      if (response.status) {
        const completeResponse = await completePDFSigning(pdfs, certificates)
        if (completeResponse.status) {
          addToast({
            title: 'Success',
            description: 'PDFs signed successfully',
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
        description: error instanceof Error ? error.message : 'Failed to sign PDFs',
        variant: 'destructive',
      })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>PDF Signing</CardTitle>
        <CardDescription>
          Upload PDF files to sign them with your certificate
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
            onClick={handleSignPDFs}
            isLoading={isLoading}
            disabled={!files.length || isLoading}
          >
            Sign PDFs
          </Button>
        </div>
      </CardContent>
    </Card>
  )
} 