import { useState } from 'react'
import { DragDropContext, Droppable, Draggable } from 'react-beautiful-dnd'
import { FileUpload } from '../components/ui/FileUpload'
import { Button } from '../components/ui/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card'
import { useToast } from '../components/ui/ToastContext'
import { mergePDFs } from '../lib/api'
import { GripVertical, X } from 'lucide-react'
import { formatBytes } from '../lib/utils'

export default function PDFMerge() {
  const [files, setFiles] = useState<File[]>([])
  const [watermark, setWatermark] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const { addToast } = useToast()

  const handleFileSelect = (selectedFiles: File[]) => {
    setFiles((prev) => [...prev, ...selectedFiles])
  }

  const handleFileRemove = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const handleDragEnd = (result: any) => {
    if (!result.destination) return

    const items = Array.from(files)
    const [reorderedItem] = items.splice(result.source.index, 1)
    items.splice(result.destination.index, 0, reorderedItem)

    setFiles(items)
  }

  const handleMergePDFs = async () => {
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

      const response = await mergePDFs(pdfs, watermark)
      
      if (response.status) {
        addToast({
          title: 'Success',
          description: 'PDFs merged successfully',
          variant: 'success',
        })
        setFiles([])
        setWatermark('')
      } else {
        throw new Error(response.message)
      }
    } catch (error) {
      addToast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to merge PDFs',
        variant: 'destructive',
      })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>PDF Merge</CardTitle>
        <CardDescription>
          Upload PDF files, arrange them in the desired order, and merge them into a single document
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

        <div className="mt-4">
          <label htmlFor="watermark" className="text-sm font-medium">
            Watermark Text (Optional)
          </label>
          <input
            id="watermark"
            type="text"
            value={watermark}
            onChange={(e) => setWatermark(e.target.value)}
            className="mt-1 block w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            placeholder="Enter watermark text"
          />
        </div>

        {files.length > 0 && (
          <DragDropContext onDragEnd={handleDragEnd}>
            <Droppable droppableId="pdfs">
              {(provided) => (
                <div
                  {...provided.droppableProps}
                  ref={provided.innerRef}
                  className="mt-4 space-y-2"
                >
                  {files.map((file, index) => (
                    <Draggable
                      key={`${file.name}-${index}`}
                      draggableId={`${file.name}-${index}`}
                      index={index}
                    >
                      {(provided) => (
                        <div
                          ref={provided.innerRef}
                          {...provided.draggableProps}
                          className="flex items-center justify-between rounded-lg border bg-card p-3"
                        >
                          <div className="flex items-center gap-2">
                            <div
                              {...provided.dragHandleProps}
                              className="cursor-grab"
                            >
                              <GripVertical className="h-4 w-4 text-muted-foreground" />
                            </div>
                            <div>
                              <p className="text-sm font-medium">
                                {index + 1}. {file.name}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                {formatBytes(file.size)}
                              </p>
                            </div>
                          </div>
                          <button
                            onClick={() => handleFileRemove(index)}
                            className="rounded-full p-1 hover:bg-muted"
                          >
                            <X className="h-4 w-4 text-muted-foreground" />
                          </button>
                        </div>
                      )}
                    </Draggable>
                  ))}
                  {provided.placeholder}
                </div>
              )}
            </Droppable>
          </DragDropContext>
        )}

        <div className="flex justify-end">
          <Button
            onClick={handleMergePDFs}
            isLoading={isLoading}
            disabled={!files.length || isLoading}
          >
            Merge PDFs
          </Button>
        </div>
      </CardContent>
    </Card>
  )
} 