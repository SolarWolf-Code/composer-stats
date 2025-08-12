"use client"

import { Suspense, useEffect, useMemo, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { PerformanceChart, type PerformancePoint } from "@/components/performance-chart"
import { DrawdownChart, type DrawdownPoint } from "@/components/drawdown-chart"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { DateFilters } from "@/components/date-filters"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

// Helper to format numbers
function formatPct(n: number, digits = 2) {
    return `${(n * 100).toFixed(digits)}%`
}

type ApiResponse = {
    data: PerformancePoint[]
    stats: {
        annualizedReturn: number
        annualizedVol: number
        sharpe: number
        maxDrawdown: number
        winPct?: number
        avgWin?: number
        avgLoss?: number
        calmar?: number
        lookbacks?: {
            portfolio: Record<string, number>
            sp500: Record<string, number>
        }
    }
}

export const dynamic = "force-dynamic"

// Always use same-origin and rely on Next.js rewrites to proxy to the API.
// This avoids leaking internal Docker hostnames to the browser and prevents accidental prod API usage.
const API_BASE = ""

function DashboardContent() {
    const router = useRouter()
    const searchParams = useSearchParams()
    const [data, setData] = useState<PerformancePoint[] | null>(null)
    const [stats, setStats] = useState<ApiResponse["stats"] | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [loading, setLoading] = useState<boolean>(true)

    const qs = useMemo(() => {
        const params = new URLSearchParams()
        const start = searchParams.get("start")
        const end = searchParams.get("end")
        if (start) params.set("start", start)
        if (end) params.set("end", end)
        const s = params.toString()
        return s ? `?${s}` : ""
    }, [searchParams])

    useEffect(() => {
        let cancelled = false
        async function run() {
            setLoading(true)
            setError(null)
            try {
                const base = API_BASE?.replace(/\/$/, "")
                const url = `${base}/api/performance${qs}`
                // Read credentials from localStorage (in-memory BYO creds, no server session)
                const apiKeyId = localStorage.getItem("composer_api_key_id")
                const apiSecret = localStorage.getItem("composer_api_secret")
                if (!apiKeyId || !apiSecret) {
                    router.replace("/login")
                    return
                }
                const headers: Record<string, string> = {}
                if (apiKeyId && apiSecret) {
                    const basic = btoa(`${apiKeyId}:${apiSecret}`)
                    headers["Authorization"] = `Basic ${basic}`
                    // Provide alternate header pair for convenience
                    headers["x-api-key-id"] = apiKeyId
                    headers["x-api-secret"] = apiSecret
                }
                const res = await fetch(url, { headers, cache: "no-store" })
                if (res.status === 401) { router.replace("/login"); return }
                if (!res.ok) throw new Error(`Failed to load performance: ${res.status}`)
                const json = (await res.json()) as ApiResponse
                if (!cancelled) {
                    setData(json.data)
                    setStats(json.stats)
                }
            } catch (e: any) {
                if (!cancelled) setError(e?.message || "Failed to load data")
            } finally {
                if (!cancelled) setLoading(false)
            }
        }
        // Wrap in suspense at call-site, but ensure no SSR data requirement by deferring to client
        run()
        return () => {
            cancelled = true
        }
    }, [qs, router])

    // Compute comparison metrics for SPY vs Portfolio from normalized series
    const toDailyReturns = (vals: number[]) => {
        const out: number[] = []
        for (let i = 1; i < vals.length; i++) out.push(vals[i] / vals[i - 1] - 1)
        return out
    }
    const mean = (arr: number[]) => (arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0)
    const variance = (arr: number[], m: number) =>
        arr.length > 1 ? arr.reduce((a, r) => a + (r - m) * (r - m), 0) / (arr.length - 1) : 0
    const annualizedVol = (daily: number[]) => Math.sqrt(variance(daily, mean(daily))) * Math.sqrt(252)
    const cagr = (vals: number[]) => (vals.length > 1 ? Math.pow(vals[vals.length - 1] / vals[0], 252 / vals.length) - 1 : 0)
    const sharpe = (ar: number, av: number) => (av > 0 ? ar / av : 0)
    const downsideDeviation = (daily: number[]) => {
        const neg = daily.filter((r) => r < 0)
        if (!neg.length) return 0
        const meanSquares = neg.reduce((a, r) => a + r * r, 0) / neg.length
        return Math.sqrt(meanSquares) * Math.sqrt(252)
    }
    const winPct = (daily: number[]) => (daily.length ? daily.filter((r) => r > 0).length / daily.length : 0)
    const avgWin = (daily: number[]) => {
        const pos = daily.filter((r) => r > 0)
        return pos.length ? mean(pos) : 0
    }
    const avgLoss = (daily: number[]) => {
        const neg = daily.filter((r) => r < 0)
        return neg.length ? mean(neg) : 0
    }
    const largestWin = (daily: number[]) => (daily.length ? Math.max(...daily) : 0)
    const largestLoss = (daily: number[]) => (daily.length ? Math.min(...daily) : 0)
    const maxDrawdown = (vals: number[]) => {
        let peak = vals[0] ?? 0
        let maxDd = 0
        for (const v of vals) {
            peak = Math.max(peak, v)
            const dd = v / peak - 1
            if (dd < maxDd) maxDd = dd
        }
        return maxDd
    }
    const currentDrawdown = (vals: number[]) => {
        let peak = vals[0] ?? 0
        for (const v of vals) peak = Math.max(peak, v)
        const last = vals[vals.length - 1] ?? 0
        return peak > 0 ? last / peak - 1 : 0
    }

    if (loading) {
        return (
            <div className="w-full min-h-dvh flex items-center justify-center p-6">
                <div className="flex flex-col items-center gap-3">
                    <div className="h-8 w-8 rounded-full border-2 border-muted-foreground border-t-transparent animate-spin" />
                    <div className="text-sm text-muted-foreground">Loading data…</div>
                </div>
            </div>
        )
    }

    if (error) {
        return (
            <div className="w-full p-4">
                <div className="text-sm text-red-500">{error}</div>
                <div className="mt-3 text-xs text-muted-foreground">Try again or <button className="underline" onClick={() => router.replace('/login')}>go to the login page</button>.</div>
            </div>
        )
    }

    if (!data || !stats) {
        return null
    }

    const portVals = data.map((d) => d.portfolio)
    const spyVals = data.map((d) => d.sp500)
    const portDaily = toDailyReturns(portVals)
    const spyDaily = toDailyReturns(spyVals)

    const portCagr = cagr(portVals)
    const spyCagr = cagr(spyVals)
    const portVol = annualizedVol(portDaily)
    const spyVol = annualizedVol(spyDaily)
    const portSharpe = sharpe(portCagr, portVol)
    const spySharpe = sharpe(spyCagr, spyVol)
    const portSortino = sharpe(portCagr, downsideDeviation(portDaily))
    const spySortino = sharpe(spyCagr, downsideDeviation(spyDaily))
    const portRewardRisk = Math.abs(maxDrawdown(portVals)) > 0 ? portCagr / Math.abs(maxDrawdown(portVals)) : 0
    const spyRewardRisk = Math.abs(maxDrawdown(spyVals)) > 0 ? spyCagr / Math.abs(maxDrawdown(spyVals)) : 0
    const riskRows = [
        { label: "Total %", spy: spyVals[0] > 0 ? spyVals.at(-1)! / spyVals[0] - 1 : 0, port: portVals[0] > 0 ? portVals.at(-1)! / portVals[0] - 1 : 0 },
        { label: "CAGR %", spy: spyCagr, port: portCagr },
        { label: "Win %", spy: winPct(spyDaily), port: winPct(portDaily) },
        { label: "Avg. Win %", spy: avgWin(spyDaily), port: avgWin(portDaily) },
        { label: "Avg. Loss %", spy: avgLoss(spyDaily), port: avgLoss(portDaily) },
        { label: "Average %", spy: mean(spyDaily), port: mean(portDaily) },
        { label: "Largest Win", spy: largestWin(spyDaily), port: largestWin(portDaily) },
        { label: "Largest Loss", spy: largestLoss(spyDaily), port: largestLoss(portDaily) },
        { label: "Current DD", spy: currentDrawdown(spyVals), port: currentDrawdown(portVals) },
        { label: "Max DD", spy: maxDrawdown(spyVals), port: maxDrawdown(portVals) },
        { label: "Ann. Std %", spy: spyVol, port: portVol },
        { label: "Sharpe Ratio", spy: spySharpe, port: portSharpe },
        { label: "Sortino Ratio", spy: spySortino, port: portSortino },
        { label: "Reward/Risk", spy: spyRewardRisk, port: portRewardRisk },
    ]

    // Prepare drawdown series from normalized values
    const toDrawdown = (vals: number[]) => {
        let peak = vals[0] ?? 0
        return vals.map((v) => {
            peak = Math.max(peak, v)
            return peak > 0 ? v / peak - 1 : 0
        })
    }
    const ddPortVals = data.map((d) => d.portfolio)
    const ddSpyVals = data.map((d) => d.sp500)
    const ddSeriesPort = toDrawdown(ddPortVals)
    const ddSeriesSpy = toDrawdown(ddSpyVals)
    const dd: DrawdownPoint[] = data.map((d, i) => ({
        date: d.date,
        portfolio: ddSeriesPort[i],
        sp500: ddSeriesSpy[i],
    }))

    return (
        <div className="w-full p-4 space-y-4">
            <div className="flex items-center justify-between">
                <div />
                <form
                    onSubmit={(e) => {
                        e.preventDefault()
                        try {
                            localStorage.removeItem("composer_api_key_id")
                            localStorage.removeItem("composer_api_secret")
                        } catch (_) { }
                        router.replace('/login')
                    }}
                >
                    <button className="text-xs underline text-muted-foreground" type="submit">Logout</button>
                </form>
            </div>
            {/* Top KPI cards for lookback returns with filters at end */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-7 gap-y-1 gap-x-3 items-stretch">
                {[
                    { key: "today", label: "Today" },
                    { key: "7d", label: "7D" },
                    { key: "30d", label: "30D" },
                    { key: "90d", label: "90D" },
                    { key: "1y", label: "1Y" },
                    { key: "total", label: "Total" },
                ].map((p) => {
                    const port = stats.lookbacks?.portfolio?.[p.key] ?? 0
                    const spy = stats.lookbacks?.sp500?.[p.key] ?? 0
                    return (
                        <Card key={p.key} className="py-0.5 gap-0">
                            <CardHeader className="px-3 pb-0 pt-0.5">
                                <CardTitle className="text-[11px] font-medium">{p.label}</CardTitle>
                            </CardHeader>
                            <CardContent className="px-3 pt-0 pb-1">
                                <div className={`text-base font-bold leading-tight ${port > 0 ? "text-green-500" : port < 0 ? "text-red-500" : ""}`}>{formatPct(port)}</div>
                                <p className={`text-[9px] leading-tight ${spy > 0 ? "text-green-500" : spy < 0 ? "text-red-500" : "text-muted-foreground"}`}>SPY {formatPct(spy)}</p>
                            </CardContent>
                        </Card>
                    )
                })}
                {/* Date filters in last column */}
                <div className="flex items-center justify-end">
                    <DateFilters />
                </div>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <Card>
                    <CardContent>
                        <PerformanceChart data={data} />
                    </CardContent>
                </Card>
                <Card>
                    <CardContent>
                        <DrawdownChart data={dd} />
                    </CardContent>
                </Card>
            </div>
            <div className="grid grid-cols-1 gap-4">
                <Card>
                    <CardContent>
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Metric</TableHead>
                                    <TableHead>SPY</TableHead>
                                    <TableHead>Total Portfolio</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {riskRows.map((r) => (
                                    <TableRow key={r.label}>
                                        <TableCell className="font-medium">{r.label}</TableCell>
                                        <TableCell className="tabular-nums">{(r.label.includes("Sharpe") || r.label.includes("Sortino") || r.label.includes("Reward/Risk")) ? r.spy.toFixed(2) : formatPct(r.spy)}</TableCell>
                                        <TableCell className="tabular-nums">{(r.label.includes("Sharpe") || r.label.includes("Sortino") || r.label.includes("Reward/Risk")) ? r.port.toFixed(2) : formatPct(r.port)}</TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}

export default function DashboardPage() {
    return (
        <Suspense fallback={<div className="w-full min-h-dvh flex items-center justify-center p-6">Loading…</div>}>
            <DashboardContent />
        </Suspense>
    )
}


