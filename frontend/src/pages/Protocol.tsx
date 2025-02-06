import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card'

const jsonExample = {
  expediente: {
    id: "EXP2024-001",
    fecha: "2024-02-05",
    documentos: [
      {
        id: "DOC001",
        tipo: "resolucion",
        contenido: "Base64EncodedContent",
        hash: "SHA256Hash",
        metadata: {
          titulo: "Resolución Principal",
          fecha: "2024-02-05",
          autor: "Juan Pérez",
          cargo: "Juez"
        }
      },
      {
        id: "DOC002",
        tipo: "anexo",
        contenido: "Base64EncodedContent",
        hash: "SHA256Hash",
        metadata: {
          titulo: "Anexo 1",
          descripcion: "Documentación adicional"
        }
      }
    ],
    metadatos: {
      tribunal: "Tribunal de Ejemplo",
      sala: "Primera Sala",
      causa: "123-2024",
      tipo: "Civil",
      estado: "En Proceso"
    },
    firmas: [
      {
        firmante: "Juan Pérez",
        cargo: "Juez",
        fecha: "2024-02-05T10:00:00Z",
        certificado: {
          emisor: "Autoridad Certificadora",
          serie: "ABC123",
          validoDesde: "2023-01-01",
          validoHasta: "2024-12-31"
        }
      }
    ]
  }
}

const zipStructure = {
  expediente: {
    root: "/",
    estructura: [
      {
        nombre: "indice.json",
        descripcion: "Archivo JSON con metadatos e índice del expediente",
        obligatorio: true
      },
      {
        nombre: "documentos/",
        descripcion: "Directorio que contiene todos los documentos PDF",
        obligatorio: true,
        contenido: [
          {
            nombre: "principal/",
            descripcion: "Documentos principales del expediente",
            contenido: [
              "resolucion_principal.pdf",
              "acta_audiencia.pdf"
            ]
          },
          {
            nombre: "anexos/",
            descripcion: "Documentos anexos y complementarios",
            contenido: [
              "anexo1.pdf",
              "anexo2.pdf"
            ]
          }
        ]
      },
      {
        nombre: "firmas/",
        descripcion: "Directorio con archivos de firma digital",
        obligatorio: true,
        contenido: [
          "indice.json.sign",
          "documentos/principal/resolucion_principal.pdf.sign"
        ]
      }
    ]
  }
}

export default function Protocol() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>JSON Structure Protocol</CardTitle>
          <CardDescription>
            Standard structure for JSON index files used in digital reports
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="prose prose-sm max-w-none">
            <h3 className="text-lg font-semibold">Required Fields</h3>
            <ul className="list-disc list-inside">
              <li><code>expediente.id</code>: Unique identifier for the report</li>
              <li><code>expediente.fecha</code>: Report creation date</li>
              <li><code>expediente.documentos</code>: Array of documents</li>
              <li><code>expediente.metadatos</code>: Report metadata</li>
            </ul>

            <h3 className="text-lg font-semibold mt-4">Document Structure</h3>
            <ul className="list-disc list-inside">
              <li><code>id</code>: Unique document identifier</li>
              <li><code>tipo</code>: Document type (resolucion, anexo, etc.)</li>
              <li><code>contenido</code>: Base64 encoded content</li>
              <li><code>hash</code>: SHA256 hash of the document</li>
              <li><code>metadata</code>: Document-specific metadata</li>
            </ul>

            <h3 className="text-lg font-semibold mt-4">Example Structure</h3>
          </div>
          <pre className="mt-2 rounded-lg bg-muted p-4 overflow-x-auto">
            <code>{JSON.stringify(jsonExample, null, 2)}</code>
          </pre>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>ZIP Report Structure Protocol</CardTitle>
          <CardDescription>
            Standard structure for ZIP files containing complete digital reports
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="prose prose-sm max-w-none">
            <h3 className="text-lg font-semibold">Directory Structure</h3>
            <ul className="list-disc list-inside">
              <li><code>indice.json</code>: Main index file with report metadata</li>
              <li><code>documentos/</code>: Directory containing all PDF documents</li>
              <li><code>firmas/</code>: Directory containing digital signatures</li>
            </ul>

            <h3 className="text-lg font-semibold mt-4">File Naming Conventions</h3>
            <ul className="list-disc list-inside">
              <li>Document files must be in PDF format</li>
              <li>Signature files must have the same name as their corresponding document with <code>.sign</code> extension</li>
              <li>Use lowercase letters, numbers, and underscores only</li>
              <li>No spaces or special characters in filenames</li>
            </ul>

            <h3 className="text-lg font-semibold mt-4">Example Structure</h3>
          </div>
          <pre className="mt-2 rounded-lg bg-muted p-4 overflow-x-auto">
            <code>{JSON.stringify(zipStructure, null, 2)}</code>
          </pre>
        </CardContent>
      </Card>
    </div>
  )
} 