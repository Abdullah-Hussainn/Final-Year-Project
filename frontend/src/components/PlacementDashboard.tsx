import { useCallback, useRef, useState } from 'react'
import {
  Upload, X, FileCode, Cpu, Play, Loader2, CheckCircle2, AlertCircle,
  Image as ImageIcon, Download, FileJson, Layers, Activity, Thermometer,
  Boxes, Share2, Server, Database, Sparkles, ScrollText,
} from 'lucide-react'

// Backend base URL (FastAPI). Artifact URLs from the API are relative, so we
// prepend this when displaying / downloading.
const API_BASE = 'http://127.0.0.1:8000'

interface PlacementMetrics {
  hpwl?: number
  congestion_top10?: number
  thermal_score?: number
  num_components?: number
  num_multi_pin_nets?: number
}

interface PlaceResponse {
  status: string
  top_module: string
  instance_count?: number
  net_count?: number
  placement_method?: string
  live_ppo_inference?: boolean
  metrics?: PlacementMetrics
  placement_image_url: string
  def_url: string
  lef_url: string
  metrics_url: string
}

const abs = (url: string) => (url.startsWith('http') ? url : `${API_BASE}${url}`)

function MetricCard({
  icon: Icon, label, value, accent,
}: { icon: any; label: string; value: string; accent?: boolean }) {
  return (
    <div className="rounded-xl border border-acfrl-stroke bg-acfrl-panel px-4 py-3.5">
      <div className="flex items-center gap-2 text-acfrl-muted">
        <Icon className="h-4 w-4" />
        <span className="text-xs font-medium uppercase tracking-wider">{label}</span>
      </div>
      <div className={`mt-1.5 font-mono text-2xl font-semibold ${accent ? 'text-acfrl-neon' : 'text-acfrl-text'}`}>
        {value}
      </div>
    </div>
  )
}

function ConfigRow({
  icon: Icon, label, value, tone = 'neutral',
}: { icon: any; label: string; value: string; tone?: 'neutral' | 'good' | 'off' }) {
  const dot =
    tone === 'good' ? 'bg-acfrl-neon shadow-[0_0_8px_rgba(76,242,160,0.8)]'
      : tone === 'off' ? 'bg-acfrl-muted'
        : 'bg-acfrl-neonDim'
  return (
    <div className="flex items-center justify-between rounded-lg border border-acfrl-stroke bg-acfrl-panel2 px-3.5 py-2.5">
      <div className="flex items-center gap-2.5 text-sm text-acfrl-muted">
        <Icon className="h-4 w-4 text-acfrl-neonDim" />
        {label}
      </div>
      <div className="flex items-center gap-2">
        <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
        <span className="font-mono text-xs text-acfrl-text">{value}</span>
      </div>
    </div>
  )
}

export default function PlacementDashboard() {
  const [files, setFiles] = useState<File[]>([])
  const [topModule, setTopModule] = useState('chip_top')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<PlaceResponse | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  // Cache-buster so the <img> refreshes when placement.png is overwritten.
  const [runStamp, setRunStamp] = useState(0)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const addFiles = useCallback((incoming: FileList | File[]) => {
    const valid = Array.from(incoming).filter((f) => /\.(v|sv)$/i.test(f.name))
    if (valid.length === 0) return
    setFiles((prev) => {
      const byName = new Map(prev.map((f) => [f.name, f]))
      valid.forEach((f) => byName.set(f.name, f))
      return Array.from(byName.values())
    })
  }, [])

  const removeFile = (name: string) =>
    setFiles((prev) => prev.filter((f) => f.name !== name))

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files?.length) addFiles(e.dataTransfer.files)
  }

  const runPlacement = async () => {
    if (files.length === 0) {
      setError('Please upload at least one Verilog (.v / .sv) file.')
      return
    }
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const form = new FormData()
      files.forEach((f) => form.append('files', f))
      form.append('top_module', topModule.trim() || 'chip_top')

      const res = await fetch(`${API_BASE}/api/place`, { method: 'POST', body: form })
      if (!res.ok) {
        let detail = `Request failed (HTTP ${res.status})`
        try {
          const body = await res.json()
          if (body?.detail) detail = body.detail
        } catch { /* ignore non-JSON error bodies */ }
        throw new Error(detail)
      }
      const data: PlaceResponse = await res.json()
      setResult(data)
      setRunStamp(Date.now())
    } catch (e: any) {
      setError(
        e?.message?.includes('Failed to fetch')
          ? `Could not reach the backend at ${API_BASE}. Is the FastAPI server running?`
          : e?.message || 'Placement failed.',
      )
    } finally {
      setLoading(false)
    }
  }

  const m = result?.metrics ?? {}
  const fmt = (n?: number, d = 2) => (typeof n === 'number' ? n.toFixed(d) : '—')

  return (
    <div className="min-h-screen px-5 py-7 sm:px-8 lg:px-12">
      <div className="mx-auto max-w-6xl">
        {/* Header */}
        <header className="mb-8">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-acfrl-stroke bg-acfrl-panel shadow-neon">
              <Cpu className="h-6 w-6 text-acfrl-neon" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-acfrl-text sm:text-3xl">
                ACFRL Dashboard
              </h1>
              <p className="text-sm text-acfrl-muted">AI-Driven Chip Floorplanning</p>
            </div>
          </div>
          <div className="mt-4 inline-flex flex-wrap items-center gap-2 rounded-lg border border-acfrl-stroke bg-acfrl-panel/70 px-3 py-1.5 font-mono text-xs text-acfrl-muted">
            {['Verilog', 'PPO Placement', 'DEF', 'OpenROAD'].map((step, i) => (
              <span key={step} className="flex items-center gap-2">
                {i > 0 && <span className="text-acfrl-neonDim">→</span>}
                <span className={i === 1 ? 'text-acfrl-neon' : 'text-acfrl-text'}>{step}</span>
              </span>
            ))}
          </div>
        </header>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          {/* Left column: input + config */}
          <div className="space-y-5 lg:col-span-1">
            {/* Input Design card */}
            <section className="rounded-2xl border border-acfrl-stroke bg-acfrl-panel p-5">
              <div className="mb-4 flex items-center gap-2">
                <FileCode className="h-5 w-5 text-acfrl-neon" />
                <h2 className="text-base font-semibold text-acfrl-text">Input Design</h2>
              </div>

              <div
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`cursor-pointer rounded-xl border-2 border-dashed px-4 py-6 text-center transition-colors ${
                  isDragging
                    ? 'border-acfrl-neon bg-acfrl-glow'
                    : 'border-acfrl-stroke bg-acfrl-panel2 hover:border-acfrl-neonDim'
                }`}
              >
                <Upload className="mx-auto h-7 w-7 text-acfrl-neonDim" />
                <p className="mt-2 text-sm text-acfrl-text">Drop Verilog files or click to browse</p>
                <p className="mt-0.5 text-xs text-acfrl-muted">.v / .sv</p>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".v,.sv"
                  multiple
                  className="hidden"
                  onChange={(e) => e.target.files && addFiles(e.target.files)}
                />
              </div>

              {files.length > 0 && (
                <ul className="mt-3 space-y-1.5">
                  {files.map((f) => (
                    <li
                      key={f.name}
                      className="flex items-center justify-between rounded-lg border border-acfrl-stroke bg-acfrl-panel2 px-3 py-2"
                    >
                      <span className="flex items-center gap-2 truncate font-mono text-xs text-acfrl-text">
                        <FileCode className="h-3.5 w-3.5 text-acfrl-neonDim" />
                        {f.name}
                      </span>
                      <button
                        onClick={(e) => { e.stopPropagation(); removeFile(f.name) }}
                        className="text-acfrl-muted transition-colors hover:text-red-400"
                        aria-label={`Remove ${f.name}`}
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}

              <label className="mt-4 block text-xs font-medium uppercase tracking-wider text-acfrl-muted">
                Top Module
              </label>
              <input
                type="text"
                value={topModule}
                onChange={(e) => setTopModule(e.target.value)}
                placeholder="chip_top"
                className="mt-1.5 w-full rounded-lg border border-acfrl-stroke bg-acfrl-bg2 px-3 py-2 font-mono text-sm text-acfrl-text outline-none focus:border-acfrl-neon"
              />

              <button
                onClick={runPlacement}
                disabled={loading}
                className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-acfrl-neon px-4 py-2.5 text-sm font-semibold text-acfrl-bg transition-all hover:bg-acfrl-neonDim disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? (
                  <><Loader2 className="h-4 w-4 animate-spin" /> Running…</>
                ) : (
                  <><Play className="h-4 w-4" /> Run AI Placement</>
                )}
              </button>
              <p className="mt-2 text-center text-xs text-acfrl-muted">
                Upload <span className="font-mono text-acfrl-neonDim">chip_top.v</span> and{' '}
                <span className="font-mono text-acfrl-neonDim">blocks.v</span> for demo.
              </p>
            </section>

            {/* Configuration card */}
            <section className="rounded-2xl border border-acfrl-stroke bg-acfrl-panel p-5">
              <div className="mb-4 flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-acfrl-neon" />
                <h2 className="text-base font-semibold text-acfrl-text">Configuration</h2>
              </div>
              <div className="space-y-2.5">
                <ConfigRow icon={Layers} label="Default LEF" value="macros.lef" tone="neutral" />
                <ConfigRow icon={Database} label="Placement Source" value="Saved thermal-PPO" tone="good" />
                <ConfigRow icon={Sparkles} label="Live PPO Inference" value="Disabled (demo)" tone="off" />
                <ConfigRow icon={Server} label="Backend" value="FastAPI · connected" tone="good" />
              </div>
            </section>
          </div>

          {/* Right column: status + results */}
          <div className="space-y-5 lg:col-span-2">
            {/* Status area */}
            {loading && (
              <div className="flex items-center gap-3 rounded-2xl border border-acfrl-stroke bg-acfrl-panel px-5 py-4">
                <Loader2 className="h-5 w-5 animate-spin text-acfrl-neon" />
                <div>
                  <p className="text-sm font-medium text-acfrl-text">Running AI placement pipeline…</p>
                  <p className="text-xs text-acfrl-muted">Parsing netlist → loading placement → metrics → DEF / PNG</p>
                </div>
              </div>
            )}
            {error && !loading && (
              <div className="flex items-start gap-3 rounded-2xl border border-red-500/40 bg-red-500/10 px-5 py-4">
                <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-400" />
                <div>
                  <p className="text-sm font-semibold text-red-300">Placement failed</p>
                  <p className="text-xs text-red-200/80">{error}</p>
                </div>
              </div>
            )}
            {result && !loading && (
              <div className="flex items-center gap-3 rounded-2xl border border-acfrl-neon/40 bg-acfrl-glow px-5 py-4">
                <CheckCircle2 className="h-5 w-5 text-acfrl-neon" />
                <p className="text-sm font-medium text-acfrl-text">
                  Placement complete for{' '}
                  <span className="font-mono text-acfrl-neon">{result.top_module}</span>
                  {result.placement_method && (
                    <span className="text-acfrl-muted"> · method: {result.placement_method}</span>
                  )}
                </p>
              </div>
            )}

            {/* Empty state */}
            {!result && !loading && !error && (
              <div className="flex h-full min-h-[420px] flex-col items-center justify-center rounded-2xl border border-dashed border-acfrl-stroke bg-acfrl-panel/50 px-6 text-center">
                <Boxes className="h-10 w-10 text-acfrl-neonDim" />
                <p className="mt-3 text-sm font-medium text-acfrl-text">No placement yet</p>
                <p className="mt-1 max-w-xs text-xs text-acfrl-muted">
                  Upload your Verilog design and run AI placement to see the floorplan, metrics, and generated artifacts.
                </p>
              </div>
            )}

            {/* Results */}
            {result && !loading && (
              <>
                {/* Metric cards */}
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
                  <MetricCard icon={Activity} label="HPWL" value={fmt(m.hpwl)} accent />
                  <MetricCard icon={Share2} label="Congestion" value={fmt(m.congestion_top10, 3)} />
                  <MetricCard icon={Thermometer} label="Thermal" value={fmt(m.thermal_score, 2)} />
                  <MetricCard icon={Boxes} label="Instances" value={String(result.instance_count ?? '—')} />
                  <MetricCard icon={Share2} label="Nets" value={String(result.net_count ?? '—')} />
                </div>

                {/* Placement image */}
                <section className="rounded-2xl border border-acfrl-stroke bg-acfrl-panel p-5">
                  <div className="mb-3 flex items-center gap-2">
                    <ImageIcon className="h-5 w-5 text-acfrl-neon" />
                    <h2 className="text-base font-semibold text-acfrl-text">Placement Layout</h2>
                  </div>
                  <div className="overflow-hidden rounded-xl border border-acfrl-stroke bg-white">
                    <img
                      src={`${abs(result.placement_image_url)}?t=${runStamp}`}
                      alt="Placement layout"
                      className="mx-auto block w-full max-w-2xl"
                    />
                  </div>
                </section>

                {/* Artifact buttons */}
                <section className="rounded-2xl border border-acfrl-stroke bg-acfrl-panel p-5">
                  <div className="mb-3 flex items-center gap-2">
                    <Download className="h-5 w-5 text-acfrl-neon" />
                    <h2 className="text-base font-semibold text-acfrl-text">Generated Artifacts</h2>
                  </div>
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <a
                      href={`${abs(result.placement_image_url)}?t=${runStamp}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-center gap-2 rounded-lg border border-acfrl-stroke bg-acfrl-panel2 px-3 py-2.5 text-sm font-medium text-acfrl-text transition-colors hover:border-acfrl-neon hover:text-acfrl-neon"
                    >
                      <ImageIcon className="h-4 w-4" /> View PNG
                    </a>
                    <a
                      href={abs(result.def_url)}
                      download
                      className="flex items-center justify-center gap-2 rounded-lg border border-acfrl-stroke bg-acfrl-panel2 px-3 py-2.5 text-sm font-medium text-acfrl-text transition-colors hover:border-acfrl-neon hover:text-acfrl-neon"
                    >
                      <ScrollText className="h-4 w-4" /> Download DEF
                    </a>
                    <a
                      href={abs(result.lef_url)}
                      download
                      className="flex items-center justify-center gap-2 rounded-lg border border-acfrl-stroke bg-acfrl-panel2 px-3 py-2.5 text-sm font-medium text-acfrl-text transition-colors hover:border-acfrl-neon hover:text-acfrl-neon"
                    >
                      <Layers className="h-4 w-4" /> Download LEF
                    </a>
                    <a
                      href={abs(result.metrics_url)}
                      download
                      className="flex items-center justify-center gap-2 rounded-lg border border-acfrl-stroke bg-acfrl-panel2 px-3 py-2.5 text-sm font-medium text-acfrl-text transition-colors hover:border-acfrl-neon hover:text-acfrl-neon"
                    >
                      <FileJson className="h-4 w-4" /> Metrics JSON
                    </a>
                  </div>
                </section>
              </>
            )}
          </div>
        </div>

        <footer className="mt-10 text-center text-xs text-acfrl-muted">
          ACFRL · AI-Driven Chip Floorplanning · Demo build
        </footer>
      </div>
    </div>
  )
}
