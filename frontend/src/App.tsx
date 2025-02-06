import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Layout from './components/Layout'
import PDFSigning from './pages/PDFSigning'
import JSONSigning from './pages/JSONSigning'
import JSONValidation from './pages/JSONValidation'
import PDFValidation from './pages/PDFValidation'
import ReportValidation from './pages/ReportValidation'
import PDFMerge from './pages/PDFMerge'
import Protocol from './pages/Protocol'

const queryClient = new QueryClient()

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <Layout>
          <Routes>
            <Route path="/" element={<PDFSigning />} />
            <Route path="/json-signing" element={<JSONSigning />} />
            <Route path="/json-validation" element={<JSONValidation />} />
            <Route path="/pdf-validation" element={<PDFValidation />} />
            <Route path="/report-validation" element={<ReportValidation />} />
            <Route path="/pdf-merge" element={<PDFMerge />} />
            <Route path="/protocol" element={<Protocol />} />
          </Routes>
        </Layout>
      </Router>
    </QueryClientProvider>
  )
}

export default App 