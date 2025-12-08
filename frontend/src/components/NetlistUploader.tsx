import { useState, useCallback, useEffect, useRef } from 'react'
import { 
  Upload, X, FileCode, Play, Download, Copy, CheckCircle2, 
  AlertCircle, ChevronDown, ChevronUp, Loader2, Network
} from 'lucide-react'
import { useApiHealth } from '../utils/useApiHealth'
import { fetchWithTimeout } from '../utils/fetchWithTimeout'
import Toast from './Toast'

interface Instance {
  name: string
  type: string
}

interface Net {
  name: string
  pins: Array<{ inst: string; pin: string }>
}

interface NetlistResult {
  top: string
  instances: Instance[]
  nets: Net[]
  stats: {
    instances: number
    nets: number
  }
  specs?: any
}

type TabType = 'instances' | 'nets' | 'json'

export default function NetlistUploader() {
  const [files, setFiles] = useState<File[]>([])
  const [topModule, setTopModule] = useState(() => {
    return localStorage.getItem('netlist-top-module') || ''
  })
  const [specsJson, setSpecsJson] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [result, setResult] = useState<NetlistResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [progress, setProgress] = useState<string>('')
  const [activeTab, setActiveTab] = useState<TabType>('instances')
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const apiHealth = useApiHealth()
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Persist top module to localStorage
  useEffect(() => {
    if (topModule) {
      localStorage.setItem('netlist-top-module', topModule)
    }
  }, [topModule])

  // Keyboard shortcut: Ctrl/Cmd+Enter to parse
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !loading && files.length > 0) {
        handleParse()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [loading, files.length])

  const showToast = (message: string, type: 'success' | 'error' | 'info' = 'info') => {
    setToast({ message, type })
  }

  const handleFileDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
    const droppedFiles = Array.from(e.dataTransfer.files).filter(
      (f) => f.name.endsWith('.v') || f.name.endsWith('.sv')
    )
    if (droppedFiles.length > 0) {
      setFiles((prev) => [...prev, ...droppedFiles])
      showToast(`Added ${droppedFiles.length} file(s)`, 'success')
    }
  }, [])

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selectedFiles = Array.from(e.target.files).filter(
        (f) => f.name.endsWith('.v') || f.name.endsWith('.sv')
      )
      if (selectedFiles.length > 0) {
        setFiles((prev) => [...prev, ...selectedFiles])
        showToast(`Added ${selectedFiles.length} file(s)`, 'success')
      }
    }
    // Reset input so same file can be selected again
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }, [])

  const handleRemoveFile = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }, [])

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / 1024 / 1024).toFixed(1) + ' MB'
  }

  const handleParse = useCallback(async () => {
    if (files.length === 0) {
      setError('Please upload at least one Verilog file')
      showToast('Please upload at least one Verilog file', 'error')
      return
    }

    setLoading(true)
    setError(null)
    setProgress('Uploading files...')

    try {
      const formData = new FormData()
      files.forEach((file) => {
        formData.append('files', file)
      })
      if (topModule.trim()) {
        formData.append('topModule', topModule.trim())
      }
      if (specsJson.trim()) {
        formData.append('specs', specsJson.trim())
      }

      setProgress('Sending request to server...')
      const apiBase = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'
      const apiUrl = `${apiBase}/api/netlist`
      
      console.log(`[NetlistUploader] Making request to: ${apiUrl}`)
      console.log(`[NetlistUploader] Files: ${files.map(f => f.name).join(', ')}`)
      
      const response = await fetchWithTimeout(
        apiUrl,
        {
          method: 'POST',
          body: formData,
        },
        60000
      )

      setProgress('Parsing Verilog files...')

      if (!response.ok) {
        let errorMessage = 'Failed to parse netlist'
        try {
          const errorData = await response.json()
          errorMessage = errorData.detail || errorMessage
        } catch {
          errorMessage = `Server error: ${response.status} ${response.statusText}`
        }
        throw new Error(errorMessage)
      }

      const text = await response.text()
      if (!text) {
        throw new Error('Empty response from server')
      }
      
      setProgress('Processing results...')
      let data: NetlistResult
      try {
        data = JSON.parse(text)
      } catch (e) {
        throw new Error(`Invalid JSON response: ${text.substring(0, 100)}`)
      }
      
      setProgress('Complete!')
      setResult(data)
      showToast('Netlist parsed successfully!', 'success')
      setActiveTab('instances')
    } catch (err) {
      let errorMsg = 'An error occurred'
      if (err instanceof Error) {
        errorMsg = err.message
        // Log full error for debugging
        console.error('Parse error:', err)
        // Check for specific error types
        if (err.message.includes('Failed to fetch') || err.message.includes('NetworkError')) {
          errorMsg = `Failed to connect to backend at ${apiBase}. Make sure the backend is running on port 8000.`
        } else if (err.message.includes('CORS')) {
          errorMsg = 'CORS error: Backend may not be allowing requests from this origin.'
        } else if (err.message.includes('timeout')) {
          errorMsg = 'Request timed out. The backend may be taking too long to respond.'
        }
      }
      setError(errorMsg)
      showToast(errorMsg.substring(0, 100), 'error')
      setProgress('Error occurred')
    } finally {
      setLoading(false)
      setTimeout(() => setProgress(''), 2000)
    }
  }, [files, topModule, specsJson])

  const handleDownload = useCallback(() => {
    if (!result) return

    const blob = new Blob([JSON.stringify(result, null, 2)], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'netlist.json'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    showToast('JSON downloaded', 'success')
  }, [result])

  const handleCopyJson = useCallback(async () => {
    if (!result) return
    try {
      await navigator.clipboard.writeText(JSON.stringify(result, null, 2))
      showToast('JSON copied to clipboard', 'success')
    } catch (err) {
      showToast('Failed to copy to clipboard', 'error')
    }
  }, [result])

  const getNetDegree = (net: Net) => net.pins.length

  const isConstant = (name: string) => {
    return /^\d+'?[bhd]\d+$/.test(name) || name === "1'b0" || name === "1'b1"
  }

  const apiBase = import.meta.env.VITE_API_BASE || window.location.origin

  return (
    <div className="min-h-screen bg-dark-bg">
      {/* Header */}
      <header className="border-b border-dark-stroke bg-dark-panel/50 backdrop-blur-sm sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded bg-gradient-to-br from-dark-accent-cyan to-dark-accent-green flex items-center justify-center">
                <FileCode className="w-5 h-5 text-dark-bg" />
              </div>
              <h1 className="text-xl font-bold text-gray-100">Netlist Builder</h1>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-dark-panel border border-dark-stroke">
                <div className={`w-2 h-2 rounded-full ${
                  apiHealth === 'connected' ? 'bg-dark-accent-green' :
                  apiHealth === 'disconnected' ? 'bg-red-500' :
                  'bg-gray-500'
                }`} />
                <span className="text-xs text-gray-400 capitalize">{apiHealth}</span>
              </div>
              <div className="text-xs text-gray-500 font-mono px-2 py-1 bg-dark-code rounded border border-dark-stroke">
                {apiBase}
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Progress Bar */}
      {loading && (
        <div className="sticky top-[73px] z-30 bg-dark-panel border-b border-dark-stroke">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2">
            <div className="flex items-center gap-3 mb-2">
              <Loader2 className="w-4 h-4 text-dark-accent-cyan animate-spin" />
              <span className="text-sm text-gray-300">{progress || 'Processing...'}</span>
            </div>
            <div className="w-full bg-dark-code rounded-full h-1.5 overflow-hidden">
              <div 
                className="bg-gradient-to-r from-dark-accent-cyan to-dark-accent-green h-full rounded-full transition-all duration-500"
                style={{ 
                  width: progress.includes('Complete') ? '100%' : 
                         progress.includes('Processing') ? '75%' :
                         progress.includes('Parsing') ? '50%' :
                         progress.includes('Sending') ? '25%' : '10%'
                }}
              />
            </div>
          </div>
        </div>
      )}

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Panel: Inputs */}
          <div className="space-y-6">
            {/* File Upload */}
            <div className="bg-dark-panel border border-dark-stroke rounded-lg p-6">
              <h2 className="text-lg font-semibold text-gray-100 mb-4 flex items-center gap-2">
                <Upload className="w-5 h-5 text-dark-accent-cyan" />
                Verilog Files
              </h2>
              
              <div
                className={`border-2 border-dashed rounded-lg p-8 text-center transition-all ${
                  isDragging 
                    ? 'border-dark-accent-cyan bg-dark-accent-cyan/10' 
                    : 'border-dark-stroke hover:border-dark-accent-cyan/50'
                }`}
                onDrop={handleFileDrop}
                onDragOver={(e) => {
                  e.preventDefault()
                  setIsDragging(true)
                }}
                onDragLeave={() => setIsDragging(false)}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  id="file-input"
                  multiple
                  accept=".v,.sv"
                  onChange={handleFileSelect}
                  className="hidden"
                />
                <label
                  htmlFor="file-input"
                  className="cursor-pointer block"
                >
                  <Upload className="w-12 h-12 mx-auto mb-3 text-gray-500" />
                  <div className="text-gray-400 mb-1 font-medium">
                    Drag and drop Verilog files here
                  </div>
                  <div className="text-sm text-gray-500">
                    or <span className="text-dark-accent-cyan underline">click to select</span>
                  </div>
                  <div className="text-xs text-gray-600 mt-2">
                    Supports .v and .sv files
                  </div>
                </label>
              </div>

              {files.length > 0 && (
                <div className="mt-4 space-y-2">
                  {files.map((file, index) => (
                    <div
                      key={index}
                      className="flex items-center justify-between bg-dark-code p-3 rounded border border-dark-stroke"
                    >
                      <div className="flex items-center gap-2 flex-1 min-w-0">
                        <FileCode className="w-4 h-4 text-dark-accent-cyan flex-shrink-0" />
                        <span className="text-sm text-gray-300 truncate font-mono">{file.name}</span>
                        <span className="text-xs text-gray-500 ml-auto flex-shrink-0">
                          {formatFileSize(file.size)}
                        </span>
                      </div>
                      <button
                        onClick={() => handleRemoveFile(index)}
                        className="ml-2 text-gray-500 hover:text-red-400 transition-colors p-1"
                        aria-label="Remove file"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Top Module */}
            <div className="bg-dark-panel border border-dark-stroke rounded-lg p-6">
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Top Module <span className="text-gray-500 font-normal">(optional)</span>
              </label>
              <input
                type="text"
                value={topModule}
                onChange={(e) => setTopModule(e.target.value)}
                placeholder="e.g., chip_top"
                className="w-full px-4 py-2.5 bg-dark-code border border-dark-stroke rounded-lg focus:outline-none focus:ring-2 focus:ring-dark-accent-cyan focus:border-transparent text-gray-100 placeholder-gray-600 font-mono"
              />
            </div>

            {/* Advanced: Specs JSON */}
            <div className="bg-dark-panel border border-dark-stroke rounded-lg overflow-hidden">
              <button
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="w-full px-6 py-4 flex items-center justify-between hover:bg-dark-stroke/50 transition-colors"
              >
                <span className="text-sm font-medium text-gray-300">Advanced</span>
                {showAdvanced ? (
                  <ChevronUp className="w-4 h-4 text-gray-500" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-gray-500" />
                )}
              </button>
              {showAdvanced && (
                <div className="px-6 pb-6">
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Specs JSON <span className="text-gray-500 font-normal">(optional)</span>
                  </label>
                  <textarea
                    value={specsJson}
                    onChange={(e) => setSpecsJson(e.target.value)}
                    placeholder='{"key": "value"}'
                    rows={6}
                    className="w-full px-4 py-3 bg-dark-code border border-dark-stroke rounded-lg focus:outline-none focus:ring-2 focus:ring-dark-accent-cyan focus:border-transparent text-gray-100 placeholder-gray-600 font-mono text-sm scrollbar-thin"
                  />
                </div>
              )}
            </div>

            {/* Parse Button */}
            <button
              onClick={handleParse}
              disabled={loading || files.length === 0}
              className="w-full px-6 py-3.5 bg-gradient-to-r from-dark-accent-cyan to-dark-accent-green text-dark-bg rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed font-semibold flex items-center justify-center gap-2 transition-all shadow-lg shadow-dark-accent-cyan/20"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Parsing...
                </>
              ) : (
                <>
                  <Play className="w-5 h-5" />
                  Parse
                </>
              )}
            </button>
            <p className="text-xs text-gray-500 text-center">
              Press <kbd className="px-1.5 py-0.5 bg-dark-code border border-dark-stroke rounded text-xs">Ctrl/Cmd+Enter</kbd> to parse
            </p>
          </div>

          {/* Right Panel: Results */}
          <div className="space-y-6">
            {error && (
              <div className="bg-red-500/10 border border-red-500/50 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <div className="text-red-400 font-semibold mb-1">Error</div>
                    <div className="text-sm text-red-300 break-words">
                      {error.length > 300 ? `${error.substring(0, 300)}...` : error}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {result ? (
              <div className="bg-dark-panel border border-dark-stroke rounded-lg overflow-hidden">
                {/* Summary */}
                <div className="px-6 py-4 bg-gradient-to-r from-dark-accent-cyan/10 to-dark-accent-green/10 border-b border-dark-stroke">
                  <div className="flex items-center justify-between">
                    <div className="text-sm text-gray-300">
                      Parsed <span className="font-mono font-semibold text-dark-accent-cyan">{result.top}</span> —{' '}
                      <span className="text-dark-accent-green">{result.stats.instances}</span> instances,{' '}
                      <span className="text-dark-accent-green">{result.stats.nets}</span> nets
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={handleCopyJson}
                        className="px-3 py-1.5 text-xs bg-dark-code border border-dark-stroke rounded hover:bg-dark-stroke transition-colors text-gray-300 flex items-center gap-1.5"
                        title="Copy JSON"
                      >
                        <Copy className="w-3.5 h-3.5" />
                        Copy
                      </button>
                      <button
                        onClick={handleDownload}
                        className="px-3 py-1.5 text-xs bg-dark-accent-green/20 border border-dark-accent-green/50 rounded hover:bg-dark-accent-green/30 transition-colors text-dark-accent-green flex items-center gap-1.5"
                        title="Download JSON"
                      >
                        <Download className="w-3.5 h-3.5" />
                        Download
                      </button>
                    </div>
                  </div>
                </div>

                {/* Tabs */}
                <div className="flex border-b border-dark-stroke">
                  {(['instances', 'nets', 'json'] as TabType[]).map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setActiveTab(tab)}
                      className={`px-6 py-3 text-sm font-medium capitalize transition-colors border-b-2 ${
                        activeTab === tab
                          ? 'border-dark-accent-cyan text-dark-accent-cyan'
                          : 'border-transparent text-gray-500 hover:text-gray-300'
                      }`}
                    >
                      {tab}
                    </button>
                  ))}
                </div>

                {/* Tab Content */}
                <div className="p-6 max-h-[600px] overflow-auto scrollbar-thin">
                  {activeTab === 'instances' && (
                    <div className="space-y-4">
                      {result.instances.length === 0 ? (
                        <div className="text-center py-12 text-gray-500">
                          <FileCode className="w-12 h-12 mx-auto mb-3 opacity-50" />
                          <p>No instances found</p>
                        </div>
                      ) : (
                        <div className="overflow-x-auto">
                          <table className="w-full">
                            <thead className="sticky top-0 bg-dark-panel z-10">
                              <tr>
                                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider border-b border-dark-stroke">
                                  Name
                                </th>
                                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider border-b border-dark-stroke">
                                  Type
                                </th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-dark-stroke">
                              {result.instances.map((inst, idx) => (
                                <tr key={idx} className={idx % 2 === 0 ? 'bg-dark-code/30' : ''}>
                                  <td className="px-4 py-3 text-sm font-mono text-gray-200">
                                    {inst.name}
                                  </td>
                                  <td className="px-4 py-3 text-sm text-gray-400">
                                    {inst.type}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  )}

                  {activeTab === 'nets' && (
                    <div className="space-y-4">
                      {result.nets.length === 0 ? (
                        <div className="text-center py-12 text-gray-500">
                          <Network className="w-12 h-12 mx-auto mb-3 opacity-50" />
                          <p>No nets found</p>
                        </div>
                      ) : (
                        <div className="overflow-x-auto">
                          <table className="w-full">
                            <thead className="sticky top-0 bg-dark-panel z-10">
                              <tr>
                                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider border-b border-dark-stroke">
                                  Net Name
                                </th>
                                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider border-b border-dark-stroke">
                                  Pins
                                </th>
                                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider border-b border-dark-stroke">
                                  Degree
                                </th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-dark-stroke">
                              {result.nets.map((net, idx) => (
                                <tr key={idx} className={idx % 2 === 0 ? 'bg-dark-code/30' : ''}>
                                  <td className={`px-4 py-3 text-sm font-mono ${
                                    isConstant(net.name) ? 'text-gray-500' : 'text-gray-200'
                                  }`}>
                                    {net.name}
                                  </td>
                                  <td className="px-4 py-3 text-sm">
                                    <div className="flex flex-wrap gap-1.5">
                                      {net.pins.length > 0 ? (
                                        net.pins.map((p, i) => (
                                          <span
                                            key={i}
                                            className="px-2 py-0.5 bg-dark-code border border-dark-stroke rounded text-xs font-mono text-gray-300"
                                          >
                                            {p.inst}.{p.pin}
                                          </span>
                                        ))
                                      ) : (
                                        <span className="text-gray-500 text-xs">(no pins)</span>
                                      )}
                                    </div>
                                  </td>
                                  <td className="px-4 py-3">
                                    <span className="px-2 py-0.5 bg-dark-accent-green/20 text-dark-accent-green rounded text-xs font-semibold">
                                      {getNetDegree(net)}
                                    </span>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  )}

                  {activeTab === 'json' && (
                    <pre className="text-xs font-mono text-gray-300 bg-dark-code p-4 rounded border border-dark-stroke overflow-auto scrollbar-thin">
                      {JSON.stringify(result, null, 2)}
                    </pre>
                  )}
                </div>
              </div>
            ) : (
              <div className="bg-dark-panel border border-dark-stroke rounded-lg p-12 text-center">
                <FileCode className="w-16 h-16 mx-auto mb-4 text-gray-600 opacity-50" />
                <p className="text-gray-500 mb-1">No results yet</p>
                <p className="text-sm text-gray-600">Upload Verilog files and click Parse to get started</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Toast */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  )
}
