import { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { cn } from '../../lib/utils'
import { Upload } from 'lucide-react'

interface FileUploadProps {
  onFileSelect: (files: File[]) => void
  accept?: Record<string, string[]>
  multiple?: boolean
  maxFiles?: number
  className?: string
  disabled?: boolean
}

export function FileUpload({
  onFileSelect,
  accept,
  multiple = false,
  maxFiles = 1,
  className,
  disabled = false,
}: FileUploadProps) {
  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      onFileSelect(acceptedFiles)
    },
    [onFileSelect]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept,
    multiple,
    maxFiles,
    disabled,
  })

  return (
    <div
      {...getRootProps()}
      className={cn(
        'flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-muted p-6 transition-colors',
        isDragActive && 'border-primary bg-muted/50',
        disabled && 'cursor-not-allowed opacity-60',
        className
      )}
    >
      <input {...getInputProps()} />
      <Upload className="h-10 w-10 text-muted-foreground" />
      <p className="mt-2 text-sm text-muted-foreground">
        {isDragActive ? (
          'Drop the files here...'
        ) : (
          <>
            Drag & drop files here, or <span className="text-primary">browse</span>
          </>
        )}
      </p>
    </div>
  )
} 