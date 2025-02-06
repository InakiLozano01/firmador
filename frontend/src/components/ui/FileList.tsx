import { File, X } from 'lucide-react'
import { formatBytes } from '../../lib/utils'

interface FileListProps {
  files: File[]
  onRemove?: (index: number) => void
  className?: string
}

export function FileList({ files, onRemove, className }: FileListProps) {
  if (!files.length) return null

  return (
    <div className={className}>
      <div className="space-y-2">
        {files.map((file, index) => (
          <div
            key={`${file.name}-${index}`}
            className="flex items-center justify-between rounded-lg border p-3"
          >
            <div className="flex items-center gap-2">
              <File className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium">{file.name}</p>
                <p className="text-xs text-muted-foreground">
                  {formatBytes(file.size)}
                </p>
              </div>
            </div>
            {onRemove && (
              <button
                onClick={() => onRemove(index)}
                className="rounded-full p-1 hover:bg-muted"
              >
                <X className="h-4 w-4 text-muted-foreground" />
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
} 