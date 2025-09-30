"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"

declare global {
    interface Window {
        Chart: any;
    }
}

type PerformanceData = {
    data: Array<{ date: string; portfolio: number; sp500: number }>
    stats: {
        annualizedReturn: number
        annualizedVol: number
        sharpe: number
        maxDrawdown: number
        lookbacks?: {
            portfolio: Record<string, number>
            sp500: Record<string, number>
        }
    }
}

type AllocationData = {
    items: Array<{ symbol: string; weight: number; quantity: number; market_value: number }>
    total_value: number
}

type SymphonyData = {
    symphonies: Array<{
        id: string
        name: string
        value: number
        net_deposits: number
        deposit_adjusted_value: number
        annualized_rate_of_return: number
        time_weighted_return: number
        sharpe_ratio: number
        max_drawdown: number
        simple_return: number
        last_percent_change: number
        holdings: Array<{
            ticker: string
            allocation: number
            value: number
            amount: number
        }>
    }>
}

type RiskComparisonData = {
    metrics: Array<{
        metric: string
        spy: string
        composer: string
    }>
}

type PortfolioRiskData = {
    total_value: number
    volatility: number
    sharpe_ratio: number
    max_drawdown: number
    correlation_with_spy: number
    consistency: number
    var_95_historical: number
    var_95_parametric: number
    expected_shortfall: number
    var_95_dollar_historical: number
    var_95_dollar_parametric: number
    expected_shortfall_dollar: number
}

type LiveVsBacktestData = {
    portfolio_summary: {
        total_symphonies: number
        total_portfolio_value: number
        weighted_avg_risk_score: number
        risk_level_counts: {
            Low: number
            Moderate: number
            Elevated: number
            High: number
        }
        avg_tracking_error_pct: number
        avg_correlation: number
    }
    symphonies: Array<{
        symphony_id: string
        symphony_name: string
        risk_score: number
        risk_level: string
        tracking_error_annualized_pct: number
        correlation: number
        mean_deviation_pct: number
        max_deviation_pct: number
        live_return_pct: number
        backtest_return_pct: number
        return_difference_pct: number
        period_days: number
        current_value: number
    }>
}

// Use relative paths to proxy API requests through Next.js server
// The Next.js rewrites in next.config.mjs will forward /api/* to the backend API
// This keeps the API internal to the Docker network and hidden from clients
const API_BASE = ""

export default function DashboardPage() {
    const router = useRouter()
    const [performanceData, setPerformanceData] = useState<PerformanceData | null>(null)
    const [allocationData, setAllocationData] = useState<AllocationData | null>(null)
    const [symphonyData, setSymphonyData] = useState<SymphonyData | null>(null)
    const [riskComparisonData, setRiskComparisonData] = useState<RiskComparisonData | null>(null)
    const [portfolioRiskData, setPortfolioRiskData] = useState<PortfolioRiskData | null>(null)
    const [liveVsBacktestData, setLiveVsBacktestData] = useState<LiveVsBacktestData | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [activeTab, setActiveTab] = useState("overview")
    const [loadingBacktest, setLoadingBacktest] = useState(false)
    const [expandedSymphonies, setExpandedSymphonies] = useState<Set<string>>(new Set())
    const [symphonyComparisonData, setSymphonyComparisonData] = useState<Map<string, any>>(new Map())
    // Sidebar is permanently collapsed to show only icons
    const [sortField, setSortField] = useState<string>("name")
    const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc")
    const [deviationSortField, setDeviationSortField] = useState<string>("risk_score")
    const [deviationSortDirection, setDeviationSortDirection] = useState<"asc" | "desc">("desc")
    const [dateRange, setDateRange] = useState({
        start: new Date(Date.now() - 365 * 24 * 60 * 60 * 1000).toISOString().split('T')[0], // 1 year ago
        end: new Date().toISOString().split('T')[0] // Today
    })
    const [showDatePicker, setShowDatePicker] = useState(false)
    const [selectedPeriod, setSelectedPeriod] = useState<string>("1Y")
    const [chartPeriod, setChartPeriod] = useState<string>("1Y")

    const handleSort = (field: string) => {
        if (sortField === field) {
            setSortDirection(sortDirection === "asc" ? "desc" : "asc")
        } else {
            setSortField(field)
            setSortDirection("asc")
        }
    }

    const handleDeviationSort = (field: string) => {
        if (deviationSortField === field) {
            setDeviationSortDirection(deviationSortDirection === "asc" ? "desc" : "asc")
        } else {
            setDeviationSortField(field)
            setDeviationSortDirection("desc")
        }
    }

    const getFilteredPerformanceData = (period: string) => {
        if (!performanceData) return { labels: [], portfolioData: [], sp500Data: [] }

        let daysToShow = 365 // Default 1Y
        if (period === '7D') daysToShow = 7
        else if (period === '1M') daysToShow = 30
        else if (period === '3M') daysToShow = 90
        else if (period === 'MAX') daysToShow = performanceData.data.length

        const filteredData = period === 'MAX'
            ? performanceData.data
            : performanceData.data.slice(-daysToShow)

        // Normalize data to start at 0% - calculate percentage change from first day
        if (filteredData.length === 0) {
            return { labels: [], portfolioData: [], sp500Data: [] }
        }

        const portfolioStart = filteredData[0].portfolio
        const sp500Start = filteredData[0].sp500

        return {
            labels: filteredData.map(d => d.date),
            portfolioData: filteredData.map(d => ((d.portfolio - portfolioStart) / portfolioStart) * 100),
            sp500Data: filteredData.map(d => ((d.sp500 - sp500Start) / sp500Start) * 100)
        }
    }

    const updatePortfolioChart = (period: string) => {
        const canvas = document.getElementById('portfolioChart') as HTMLCanvasElement
        if (!canvas) return

        // Destroy existing chart if it exists
        const existingChart = window.Chart.getChart(canvas)
        if (existingChart) {
            existingChart.destroy()
        }

        const { labels, portfolioData, sp500Data } = getFilteredPerformanceData(period)

        const chartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index' as const, intersect: false },
            plugins: {
                legend: {
                    display: true,
                    position: 'top' as const,
                    labels: { color: '#e1e5e9', font: { size: 12 }, padding: 15, usePointStyle: true }
                },
                tooltip: {
                    backgroundColor: '#131722',
                    titleColor: '#e1e5e9',
                    bodyColor: '#e1e5e9',
                    borderColor: '#2a2e39',
                    borderWidth: 1,
                    callbacks: {
                        label: function (context: any) {
                            const label = context.dataset.label || ''
                            const value = context.parsed.y
                            return `${label}: ${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
                        }
                    }
                }
            },
            scales: {
                y: {
                    ticks: {
                        color: '#787b86',
                        font: { size: 11 },
                        callback: function (value: any) {
                            return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`
                        }
                    },
                    grid: { color: '#2a2e39', drawBorder: false },
                    border: { display: false }
                },
                x: {
                    ticks: { color: '#787b86', font: { size: 11 } },
                    grid: { color: '#2a2e39', drawBorder: false },
                    border: { display: false }
                }
            }
        }

        new window.Chart(canvas, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Portfolio',
                    data: portfolioData,
                    borderColor: '#4c9eff',
                    backgroundColor: 'rgba(76, 158, 255, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                }, {
                    label: 'S&P 500',
                    data: sp500Data,
                    borderColor: '#787b86',
                    backgroundColor: 'transparent',
                    borderWidth: 1,
                    fill: false,
                    tension: 0.4,
                }]
            },
            options: chartOptions
        })
    }

    const sortedSymphonies = symphonyData?.symphonies ? [...symphonyData.symphonies].sort((a, b) => {
        let aValue: any, bValue: any

        switch (sortField) {
            case "name":
                aValue = a.name.toLowerCase()
                bValue = b.name.toLowerCase()
                break
            case "value":
                aValue = a.value
                bValue = b.value
                break
            case "allocation":
                const totalPortfolioValue = symphonyData.symphonies.reduce((sum, s) => sum + s.value, 0)
                aValue = totalPortfolioValue > 0 ? (a.value / totalPortfolioValue) : 0
                bValue = totalPortfolioValue > 0 ? (b.value / totalPortfolioValue) : 0
                break
            case "performance":
                aValue = a.net_deposits > 0 ? (a.value - a.net_deposits) / a.net_deposits : a.simple_return || 0
                bValue = b.net_deposits > 0 ? (b.value - b.net_deposits) / b.net_deposits : b.simple_return || 0
                break
            case "todaysChange":
                aValue = a.last_percent_change || 0
                bValue = b.last_percent_change || 0
                break
            case "risk":
                const aDrawdown = Math.abs(a.max_drawdown || 0)
                const bDrawdown = Math.abs(b.max_drawdown || 0)
                const aSharpe = a.sharpe_ratio || 0
                const bSharpe = b.sharpe_ratio || 0
                // Risk score: higher drawdown + lower sharpe = higher risk score
                aValue = aDrawdown - (aSharpe * 0.1)
                bValue = bDrawdown - (bSharpe * 0.1)
                break
            default:
                aValue = a.name.toLowerCase()
                bValue = b.name.toLowerCase()
        }

        if (aValue < bValue) return sortDirection === "asc" ? -1 : 1
        if (aValue > bValue) return sortDirection === "asc" ? 1 : -1
        return 0
    }) : []

    const loadData = async (startDate?: string, endDate?: string) => {
        setLoading(true)
        setError(null)
        try {
            const apiKeyId = localStorage.getItem("composer_api_key_id")
            const apiSecret = localStorage.getItem("composer_api_secret")
            if (!apiKeyId || !apiSecret) {
                router.replace("/login")
                return
            }

            const headers = {
                "Authorization": `Basic ${btoa(`${apiKeyId}:${apiSecret}`)}`,
                "x-api-key-id": apiKeyId,
                "x-api-secret": apiSecret,
            }

            // Build query parameters for date range
            const params = new URLSearchParams()
            if (startDate) params.append('start', startDate)
            if (endDate) params.append('end', endDate)
            const queryString = params.toString() ? `?${params.toString()}` : ''

            // Load performance, allocation, symphonies, risk comparison, and portfolio risk data
            const [perfRes, allocRes, symphRes, riskRes, portfolioRiskRes] = await Promise.all([
                fetch(`${API_BASE}/api/performance${queryString}`, { headers, cache: "no-store" }),
                fetch(`${API_BASE}/api/allocation`, { headers, cache: "no-store" }),
                fetch(`${API_BASE}/api/symphonies`, { headers, cache: "no-store" }),
                fetch(`${API_BASE}/api/risk-comparison`, { headers, cache: "no-store" }),
                fetch(`${API_BASE}/api/portfolio-risk`, { headers, cache: "no-store" })
            ])

            if (perfRes.status === 401 || allocRes.status === 401 || symphRes.status === 401 || riskRes.status === 401 || portfolioRiskRes.status === 401) {
                router.replace("/login")
                return
            }

            if (!perfRes.ok) throw new Error(`Failed to load performance: ${perfRes.status}`)
            if (!allocRes.ok) throw new Error(`Failed to load allocation: ${allocRes.status}`)
            if (!symphRes.ok) throw new Error(`Failed to load symphonies: ${symphRes.status}`)
            if (!riskRes.ok) throw new Error(`Failed to load risk comparison: ${riskRes.status}`)
            if (!portfolioRiskRes.ok) throw new Error(`Failed to load portfolio risk: ${portfolioRiskRes.status}`)

            const perfData = await perfRes.json()
            const allocData = await allocRes.json()
            const symphData = await symphRes.json()
            const riskData = await riskRes.json()
            const portfolioRiskData = await portfolioRiskRes.json()

            setPerformanceData(perfData)
            setAllocationData(allocData)
            setSymphonyData(symphData)
            setRiskComparisonData(riskData)
            setPortfolioRiskData(portfolioRiskData)
        } catch (e: any) {
            setError(e?.message || "Failed to load data")
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        loadData()
    }, [])

    const loadLiveVsBacktest = async () => {
        setLoadingBacktest(true)
        try {
            const apiKeyId = localStorage.getItem("composer_api_key_id")
            const apiSecret = localStorage.getItem("composer_api_secret")
            if (!apiKeyId || !apiSecret) return

            const headers = {
                "Authorization": `Basic ${btoa(`${apiKeyId}:${apiSecret}`)}`,
                "x-api-key-id": apiKeyId,
                "x-api-secret": apiSecret,
            }

            const response = await fetch(`${API_BASE}/api/portfolio/live-vs-backtest`, {
                headers,
                cache: "no-store"
            })

            if (response.status === 401) {
                router.replace("/login")
                return
            }

            if (!response.ok) throw new Error(`Failed to load backtest comparison: ${response.status}`)

            const data = await response.json()
            setLiveVsBacktestData(data)
        } catch (e: any) {
            console.error("Failed to load live vs backtest data:", e)
        } finally {
            setLoadingBacktest(false)
        }
    }

    const loadSymphonyComparison = async (symphonyId: string) => {
        try {
            const apiKeyId = localStorage.getItem("composer_api_key_id")
            const apiSecret = localStorage.getItem("composer_api_secret")
            if (!apiKeyId || !apiSecret) return

            const headers = {
                "Authorization": `Basic ${btoa(`${apiKeyId}:${apiSecret}`)}`,
                "x-api-key-id": apiKeyId,
                "x-api-secret": apiSecret,
            }

            const response = await fetch(`${API_BASE}/api/symphony/${symphonyId}/live-vs-backtest`, {
                headers,
                cache: "no-store"
            })

            if (response.status === 401) {
                router.replace("/login")
                return
            }

            if (!response.ok) throw new Error(`Failed to load symphony comparison: ${response.status}`)

            const data = await response.json()
            setSymphonyComparisonData(prev => new Map(prev.set(symphonyId, data)))
        } catch (e: any) {
            console.error("Failed to load symphony comparison data:", e)
        }
    }

    const toggleSymphonyExpansion = (symphonyId: string) => {
        const newExpanded = new Set(expandedSymphonies)
        if (newExpanded.has(symphonyId)) {
            newExpanded.delete(symphonyId)
        } else {
            newExpanded.add(symphonyId)
            // Load comparison data if not already loaded
            if (!symphonyComparisonData.has(symphonyId)) {
                loadSymphonyComparison(symphonyId)
            }
        }
        setExpandedSymphonies(newExpanded)
    }

    const handleDateRangeChange = async () => {
        await loadData(dateRange.start, dateRange.end)
        setShowDatePicker(false)
    }

    useEffect(() => {
        if (!performanceData || !allocationData || !symphonyData || typeof window === "undefined" || !window.Chart) return

        // Initialize charts after data loads
        initializeCharts()
    }, [performanceData, allocationData, symphonyData])

    useEffect(() => {
        if (!performanceData || typeof window === "undefined" || !window.Chart) return

        // Update portfolio chart when period changes
        updatePortfolioChart(chartPeriod)
    }, [chartPeriod, performanceData])

    useEffect(() => {
        if (!symphonyComparisonData.size || typeof window === "undefined" || !window.Chart) return

        // Initialize comparison charts for expanded symphonies
        initializeComparisonCharts()
    }, [symphonyComparisonData, expandedSymphonies])

    const initializeCharts = () => {
        if (!performanceData || !allocationData || !symphonyData || !window.Chart) return

        const chartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: {
                        color: '#e1e5e9',
                        font: { size: 12 },
                        usePointStyle: true,
                    }
                },
                tooltip: {
                    backgroundColor: '#131722',
                    titleColor: '#e1e5e9',
                    bodyColor: '#e1e5e9',
                    borderColor: '#2a2e39',
                    borderWidth: 1,
                }
            },
            scales: {
                y: {
                    ticks: { color: '#787b86', font: { size: 11 } },
                    grid: { color: '#2a2e39', drawBorder: false },
                    border: { display: false }
                },
                x: {
                    ticks: { color: '#787b86', font: { size: 11 } },
                    grid: { color: '#2a2e39', drawBorder: false },
                    border: { display: false }
                }
            }
        }

        // Portfolio Performance Chart
        const portfolioCtx = document.getElementById('portfolioChart') as HTMLCanvasElement
        if (portfolioCtx) {
            new window.Chart(portfolioCtx, {
                type: 'line',
                data: {
                    labels: performanceData.data.map(d => d.date),
                    datasets: [{
                        label: 'Portfolio',
                        data: performanceData.data.map(d => d.portfolio),
                        borderColor: '#4c9eff',
                        backgroundColor: 'rgba(76, 158, 255, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                    }, {
                        label: 'S&P 500',
                        data: performanceData.data.map(d => d.sp500),
                        borderColor: '#787b86',
                        backgroundColor: 'transparent',
                        borderWidth: 1,
                        fill: false,
                        tension: 0.4,
                    }]
                },
                options: chartOptions
            })
        }

        // Asset Allocation Chart
        const allocationCtx = document.getElementById('allocationChart') as HTMLCanvasElement
        if (allocationCtx && allocationData.items.length > 0) {
            const colors = ['#4c9eff', '#00c896', '#ffb340', '#ff5b5b', '#9c88ff', '#34d399', '#f472b6', '#f59e0b', '#3b82f6', '#10b981']
            new window.Chart(allocationCtx, {
                type: 'doughnut',
                data: {
                    labels: allocationData.items.map(d => d.symbol),
                    datasets: [{
                        data: allocationData.items.map(d => d.market_value),
                        backgroundColor: colors.slice(0, allocationData.items.length),
                        borderWidth: 0,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                color: '#e1e5e9',
                                font: { size: 12 },
                                padding: 20,
                                usePointStyle: true
                            }
                        },
                        tooltip: {
                            backgroundColor: '#131722',
                            titleColor: '#e1e5e9',
                            bodyColor: '#e1e5e9',
                            borderColor: '#2a2e39',
                            borderWidth: 1,
                            callbacks: {
                                label: function (context: any) {
                                    const value = context.parsed
                                    const percentage = ((value / allocationData.total_value) * 100).toFixed(1)
                                    return `${context.label}: $${value.toLocaleString()} (${percentage}%)`
                                }
                            }
                        }
                    }
                }
            })
        }

        // Risk Chart (Radar)
        const riskCtx = document.getElementById('riskChart') as HTMLCanvasElement
        if (riskCtx && symphonyData?.symphonies) {
            const portfolioSharpe = symphonyData.symphonies.reduce((sum, s, _, arr) => sum + (s.sharpe_ratio || 0) / arr.length, 0)
            const maxDrawdown = Math.max(...symphonyData.symphonies.map(s => Math.abs(s.max_drawdown || 0)))
            const avgVolatility = portfolioRiskData?.volatility || symphonyData.symphonies.reduce((sum, s, _, arr) => {
                const annualReturn = s.annualized_rate_of_return || 0
                const sharpe = s.sharpe_ratio || 0.1
                const vol = sharpe !== 0 ? Math.abs(annualReturn / sharpe) : 0.15
                return sum + vol / arr.length
            }, 0)

            new window.Chart(riskCtx, {
                type: 'radar',
                data: {
                    labels: ['Volatility', 'Drawdown Risk', 'Sharpe Quality', 'Consistency', 'Correlation'],
                    datasets: [{
                        label: 'Portfolio Risk',
                        data: [
                            Math.min(avgVolatility * 400, 100), // Volatility (scaled)
                            Math.min(maxDrawdown * 500, 100), // Drawdown risk (scaled)
                            Math.max(100 - Math.abs(portfolioSharpe * 30), 0), // Sharpe quality (inverted)
                            portfolioRiskData?.consistency || 75, // Consistency from real data
                            Math.abs(portfolioRiskData?.correlation_with_spy || 0.6) * 100  // Correlation with SPY from real data
                        ],
                        borderColor: '#4c9eff',
                        backgroundColor: 'rgba(76, 158, 255, 0.1)',
                        borderWidth: 2,
                        pointBackgroundColor: '#4c9eff',
                        pointRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        r: {
                            beginAtZero: true,
                            max: 100,
                            ticks: {
                                color: '#787b86',
                                backdropColor: 'transparent',
                                font: { size: 10 }
                            },
                            grid: { color: '#2a2e39' },
                            angleLines: { color: '#2a2e39' },
                            pointLabels: {
                                color: '#e1e5e9',
                                font: { size: 11 }
                            }
                        }
                    }
                }
            })
        }

    }

    const initializeComparisonCharts = () => {
        if (!window.Chart) return

        const chartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: '#131722',
                    titleColor: '#e1e5e9',
                    bodyColor: '#e1e5e9',
                    borderColor: '#2a2e39',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: true,
                    callbacks: {
                        label: function (context: any) {
                            let label = context.dataset.label || ''
                            if (label) {
                                label += ': '
                            }
                            if (context.parsed.y !== null) {
                                label += '$' + context.parsed.y.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                            }
                            return label
                        }
                    }
                }
            },
            scales: {
                y: {
                    ticks: {
                        color: '#787b86',
                        font: { size: 11 },
                        callback: function (value: any) {
                            return '$' + value.toLocaleString()
                        }
                    },
                    grid: { color: '#2a2e39', drawBorder: false },
                    border: { display: false }
                },
                x: {
                    ticks: {
                        color: '#787b86',
                        font: { size: 11 },
                        maxRotation: 45,
                        minRotation: 45
                    },
                    grid: { color: '#2a2e39', drawBorder: false },
                    border: { display: false }
                }
            }
        }

        // Create charts for each expanded symphony
        expandedSymphonies.forEach(symphonyId => {
            const comparisonData = symphonyComparisonData.get(symphonyId)
            if (!comparisonData || !comparisonData.comparison_data) return

            const canvasId = `comparison-chart-${symphonyId}`
            const canvas = document.getElementById(canvasId) as HTMLCanvasElement
            if (!canvas) return

            // Destroy existing chart if it exists
            const existingChart = window.Chart.getChart(canvas)
            if (existingChart) {
                existingChart.destroy()
            }

            const data = comparisonData.comparison_data
            const labels = data.map((d: any) => d.date)
            const liveValues = data.map((d: any) => d.live)
            const backtestValues = data.map((d: any) => d.backtest)

            new window.Chart(canvas, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Live Performance',
                        data: liveValues,
                        borderColor: '#4c9eff',
                        backgroundColor: 'rgba(76, 158, 255, 0.1)',
                        borderWidth: 2,
                        fill: false,
                        tension: 0.4,
                    }, {
                        label: 'Backtest Performance',
                        data: backtestValues,
                        borderColor: '#ffb340',
                        backgroundColor: 'rgba(255, 179, 64, 0.1)',
                        borderWidth: 2,
                        fill: false,
                        tension: 0.4,
                    }]
                },
                options: chartOptions
            })
        })
    }

    if (loading) {
        return (
            <div style={{
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                height: '100vh',
                width: '100%',
                background: '#0a0e1a',
                flexDirection: 'column',
                gap: '24px',
                overflow: 'hidden'
            }}>
                <div style={{
                    textAlign: 'center',
                    marginBottom: '20px'
                }}>
                    <h1 style={{
                        fontSize: '32px',
                        fontWeight: '700',
                        color: '#4c9eff',
                        marginBottom: '8px',
                        letterSpacing: '-0.5px'
                    }}>ComposerAnalytics</h1>
                    <p style={{
                        fontSize: '14px',
                        color: '#787b86',
                        margin: 0
                    }}>Professional Trading Analytics</p>
                </div>
                <div className="loading-spinner"></div>
                <p style={{
                    fontSize: '14px',
                    color: '#787b86',
                    marginTop: '16px'
                }}>Loading your portfolio data...</p>
            </div>
        )
    }

    if (error) {
        return (
            <div className="main-content">
                <div className="content-area">
                    <div style={{ color: '#ff5b5b' }}>{error}</div>
                </div>
            </div>
        )
    }

    const portfolioValue = performanceData?.data?.[performanceData.data.length - 1]?.portfolio || 0
    const todayReturn = performanceData?.stats?.lookbacks?.portfolio?.today || 0
    const sevenDayReturn = performanceData?.stats?.lookbacks?.portfolio?.["7d"] || 0
    const monthlyReturn = performanceData?.stats?.lookbacks?.portfolio?.["30d"] || 0
    const threeMonthReturn = performanceData?.stats?.lookbacks?.portfolio?.["90d"] || 0
    const ytdReturn = performanceData?.stats?.lookbacks?.portfolio?.["1y"] || 0
    const totalReturn = performanceData?.stats?.lookbacks?.portfolio?.total || 0

    return (
        <>
            <div className="sidebar collapsed">
                <div className="logo">
                    <h1>ComposerAnalytics</h1>
                    <p>Professional Trading Analytics</p>
                </div>

                <nav className="nav-menu">
                    <a href="#" className={`nav-item ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')} title="Portfolio Overview">
                        <i className="fas fa-chart-line"></i>
                        <span>Portfolio</span>
                    </a>
                    <a href="#" className={`nav-item ${activeTab === 'risk' ? 'active' : ''}`} onClick={() => { setActiveTab('risk'); if (!liveVsBacktestData) loadLiveVsBacktest(); }} title="Risk & Analysis">
                        <i className="fas fa-shield-alt"></i>
                        <span>Risk & Analysis</span>
                    </a>
                </nav>
            </div>

            <div className="main-content sidebar-collapsed">
                <div className="header">
                    <div className="header-top">
                        <h1 className="page-title">Portfolio Dashboard</h1>
                        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                            <button
                                className={`btn ${activeTab === 'overview' ? 'primary' : ''}`}
                                onClick={() => setActiveTab('overview')}
                                aria-label="Go to Portfolio Overview"
                            >
                                Overview
                            </button>
                            <button
                                className={`btn ${activeTab === 'risk' ? 'primary' : ''}`}
                                onClick={() => { setActiveTab('risk'); if (!liveVsBacktestData) loadLiveVsBacktest(); }}
                                aria-label="Go to Risk & Analysis"
                            >
                                Risk & Analysis
                            </button>
                        </div>
                        <div className="performance-metrics">
                            <div className="metric-item">
                                <div className="metric-label">TODAY</div>
                                <div className={`metric-value ${todayReturn >= 0 ? 'positive' : 'negative'}`}>
                                    {todayReturn >= 0 ? '+' : ''}{(todayReturn * 100).toFixed(2)}%
                                </div>
                            </div>
                            <div className="metric-item">
                                <div className="metric-label">7D</div>
                                <div className={`metric-value ${sevenDayReturn >= 0 ? 'positive' : 'negative'}`}>
                                    {sevenDayReturn >= 0 ? '+' : ''}{(sevenDayReturn * 100).toFixed(2)}%
                                </div>
                            </div>
                            <div className="metric-item">
                                <div className="metric-label">1M</div>
                                <div className={`metric-value ${monthlyReturn >= 0 ? 'positive' : 'negative'}`}>
                                    {monthlyReturn >= 0 ? '+' : ''}{(monthlyReturn * 100).toFixed(2)}%
                                </div>
                            </div>
                            <div className="metric-item">
                                <div className="metric-label">3M</div>
                                <div className={`metric-value ${threeMonthReturn >= 0 ? 'positive' : 'negative'}`}>
                                    {threeMonthReturn >= 0 ? '+' : ''}{(threeMonthReturn * 100).toFixed(2)}%
                                </div>
                            </div>
                            <div className="metric-item">
                                <div className="metric-label">1Y</div>
                                <div className={`metric-value ${ytdReturn >= 0 ? 'positive' : 'negative'}`}>
                                    {ytdReturn >= 0 ? '+' : ''}{(ytdReturn * 100).toFixed(2)}%
                                </div>
                            </div>
                            <div className="metric-item">
                                <div className="metric-label">TOTAL</div>
                                <div className={`metric-value ${totalReturn >= 0 ? 'positive' : 'negative'}`}>
                                    {totalReturn >= 0 ? '+' : ''}{(totalReturn * 100).toFixed(2)}%
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="content-area">
                    <div id="overview" className={`tab-content ${activeTab === 'overview' ? 'active' : ''}`}>
                        <div className="card wide-card" style={{ marginBottom: '24px' }}>
                            <div className="card-header">
                                <h3 className="card-title">Portfolio Performance</h3>
                                <div className="card-actions">
                                    <button
                                        className={`btn ${chartPeriod === '7D' ? 'primary' : ''}`}
                                        onClick={() => setChartPeriod('7D')}
                                    >
                                        7D
                                    </button>
                                    <button
                                        className={`btn ${chartPeriod === '1M' ? 'primary' : ''}`}
                                        onClick={() => setChartPeriod('1M')}
                                    >
                                        1M
                                    </button>
                                    <button
                                        className={`btn ${chartPeriod === '3M' ? 'primary' : ''}`}
                                        onClick={() => setChartPeriod('3M')}
                                    >
                                        3M
                                    </button>
                                    <button
                                        className={`btn ${chartPeriod === '1Y' ? 'primary' : ''}`}
                                        onClick={() => setChartPeriod('1Y')}
                                    >
                                        1Y
                                    </button>
                                    <button
                                        className={`btn ${chartPeriod === 'MAX' ? 'primary' : ''}`}
                                        onClick={() => setChartPeriod('MAX')}
                                    >
                                        MAX
                                    </button>
                                </div>
                            </div>
                            <div className="card-body">
                                <div className="chart-container">
                                    <canvas id="portfolioChart"></canvas>
                                </div>
                            </div>
                        </div>

                        <div className="allocation-symphony-row">
                            <div className="card allocation-card">
                                <div className="card-header">
                                    <h3 className="card-title">Asset Allocation</h3>
                                </div>
                                <div className="card-body">
                                    <div className="chart-container allocation-chart">
                                        <canvas id="allocationChart"></canvas>
                                    </div>
                                </div>
                            </div>

                            <div className="card symphony-table-card">
                                <div className="card-header">
                                    <h3 className="card-title">Symphony Performance</h3>
                                </div>
                                <div className="card-body" style={{ padding: 0 }}>
                                    <div className="table-responsive" style={{ overflowX: 'auto' }}>
                                        <table className="data-table" style={{ width: '100%' }}>
                                            <thead>
                                                <tr>
                                                    <th
                                                        style={{ cursor: 'pointer', userSelect: 'none' }}
                                                        onClick={() => handleSort("name")}
                                                    >
                                                        Symphony
                                                        {sortField === "name" && (
                                                            <i className={`fas fa-sort-${sortDirection === "asc" ? "up" : "down"}`} style={{ marginLeft: '8px', fontSize: '10px' }}></i>
                                                        )}
                                                    </th>
                                                    <th
                                                        style={{ cursor: 'pointer', userSelect: 'none' }}
                                                        onClick={() => handleSort("value")}
                                                    >
                                                        Value
                                                        {sortField === "value" && (
                                                            <i className={`fas fa-sort-${sortDirection === "asc" ? "up" : "down"}`} style={{ marginLeft: '8px', fontSize: '10px' }}></i>
                                                        )}
                                                    </th>
                                                    <th
                                                        style={{ cursor: 'pointer', userSelect: 'none' }}
                                                        onClick={() => handleSort("allocation")}
                                                    >
                                                        Allocation
                                                        {sortField === "allocation" && (
                                                            <i className={`fas fa-sort-${sortDirection === "asc" ? "up" : "down"}`} style={{ marginLeft: '8px', fontSize: '10px' }}></i>
                                                        )}
                                                    </th>
                                                    <th
                                                        style={{ cursor: 'pointer', userSelect: 'none' }}
                                                        onClick={() => handleSort("performance")}
                                                    >
                                                        Performance
                                                        {sortField === "performance" && (
                                                            <i className={`fas fa-sort-${sortDirection === "asc" ? "up" : "down"}`} style={{ marginLeft: '8px', fontSize: '10px' }}></i>
                                                        )}
                                                    </th>
                                                    <th
                                                        style={{ cursor: 'pointer', userSelect: 'none' }}
                                                        onClick={() => handleSort("todaysChange")}
                                                    >
                                                        Today's Change
                                                        {sortField === "todaysChange" && (
                                                            <i className={`fas fa-sort-${sortDirection === "asc" ? "up" : "down"}`} style={{ marginLeft: '8px', fontSize: '10px' }}></i>
                                                        )}
                                                    </th>
                                                    <th
                                                        style={{ cursor: 'pointer', userSelect: 'none' }}
                                                        onClick={() => handleSort("risk")}
                                                    >
                                                        Risk
                                                        {sortField === "risk" && (
                                                            <i className={`fas fa-sort-${sortDirection === "asc" ? "up" : "down"}`} style={{ marginLeft: '8px', fontSize: '10px' }}></i>
                                                        )}
                                                    </th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {sortedSymphonies.map((symphony, index) => {
                                                    const totalPortfolioValue = symphonyData!.symphonies.reduce((sum, s) => sum + s.value, 0)
                                                    const allocationPercentage = totalPortfolioValue > 0 ? (symphony.value / totalPortfolioValue * 100) : 0

                                                    // Calculate deposit-adjusted return: (current_value - net_deposits) / net_deposits
                                                    const depositAdjustedReturn = symphony.net_deposits > 0
                                                        ? (symphony.value - symphony.net_deposits) / symphony.net_deposits
                                                        : symphony.simple_return || 0

                                                    // Risk calculation based on multiple factors
                                                    const maxDrawdown = Math.abs(symphony.max_drawdown || 0)
                                                    const sharpeRatio = symphony.sharpe_ratio || 0

                                                    // Risk logic: combine drawdown and sharpe ratio
                                                    let riskLevel = 'medium'
                                                    if (maxDrawdown < 0.05 && sharpeRatio > 1) {
                                                        riskLevel = 'low'
                                                    } else if (maxDrawdown > 0.15 || sharpeRatio < 0) {
                                                        riskLevel = 'high'
                                                    }

                                                    // Calculate today's dollar change
                                                    const todaysPercentChange = symphony.last_percent_change || 0
                                                    const todaysDollarChange = symphony.value * todaysPercentChange

                                                    return (
                                                        <tr key={symphony.id || index}>
                                                            <td>
                                                                <div className="symphony-name">{symphony.name}</div>
                                                            </td>
                                                            <td>${symphony.value.toLocaleString()}</td>
                                                            <td>{allocationPercentage.toFixed(1)}%</td>
                                                            <td>
                                                                <span className={`change-indicator ${depositAdjustedReturn >= 0 ? 'positive' : 'negative'}`}>
                                                                    <i className={`fas fa-arrow-${depositAdjustedReturn >= 0 ? 'up' : 'down'}`}></i>
                                                                    {(depositAdjustedReturn * 100).toFixed(1)}%
                                                                </span>
                                                                <div style={{ fontSize: '11px', color: '#787b86', marginTop: '2px' }}>
                                                                    (${(symphony.value - symphony.net_deposits).toLocaleString()})
                                                                </div>
                                                            </td>
                                                            <td>
                                                                <span className={`change-indicator ${todaysPercentChange >= 0 ? 'positive' : 'negative'}`}>
                                                                    <i className={`fas fa-arrow-${todaysPercentChange >= 0 ? 'up' : 'down'}`}></i>
                                                                    {(todaysPercentChange * 100).toFixed(2)}%
                                                                </span>
                                                                <div style={{ fontSize: '11px', color: '#787b86', marginTop: '2px' }}>
                                                                    (${todaysDollarChange >= 0 ? '+' : ''}${todaysDollarChange.toLocaleString()})
                                                                </div>
                                                            </td>
                                                            <td>
                                                                <div className="risk-level">
                                                                    <div className="risk-dots">
                                                                        <div className={`risk-dot ${riskLevel === 'low' ? 'active low' : ''}`}></div>
                                                                        <div className={`risk-dot ${riskLevel === 'medium' || riskLevel === 'low' ? 'active medium' : ''}`}></div>
                                                                        <div className={`risk-dot ${riskLevel === 'high' ? 'active high' : ''}`}></div>
                                                                        <div className="risk-dot"></div>
                                                                        <div className="risk-dot"></div>
                                                                    </div>
                                                                    <span style={{ fontSize: '11px', color: '#787b86' }}>
                                                                        {riskLevel.charAt(0).toUpperCase() + riskLevel.slice(1)}
                                                                    </span>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                    )
                                                })}
                                                {(!symphonyData?.symphonies || symphonyData.symphonies.length === 0) && (
                                                    <tr>
                                                        <td colSpan={6} style={{ textAlign: 'center', color: '#787b86' }}>
                                                            No symphonies data available
                                                        </td>
                                                    </tr>
                                                )}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div id="risk" className={`tab-content ${activeTab === 'risk' ? 'active' : ''}`}>
                        <div className="dashboard-grid">
                            <div className="card">
                                <div className="card-header">
                                    <h3 className="card-title">Portfolio Risk Profile</h3>
                                </div>
                                <div className="card-body">
                                    <div className="chart-container">
                                        <canvas id="riskChart"></canvas>
                                    </div>
                                </div>
                            </div>

                            <div className="card">
                                <div className="card-header">
                                    <h3 className="card-title">Risk Metrics</h3>
                                </div>
                                <div className="card-body">
                                    <div className="metrics-grid metrics-2x2">
                                        {performanceData?.stats && (() => {
                                            const portfolioSharpe = performanceData.stats.sharpe || 0
                                            const maxDrawdown = performanceData.stats.maxDrawdown || 0
                                            const avgVolatility = performanceData.stats.annualizedVol || 0
                                            const totalValue = portfolioRiskData?.total_value || 0
                                            const var95 = portfolioRiskData?.var_95_dollar_historical || totalValue * 0.021 // Historical 95% VaR

                                            return (
                                                <>
                                                    <div className="metric-box">
                                                        <div className="label">Portfolio Sharpe</div>
                                                        <div className="value">{portfolioSharpe.toFixed(2)}</div>
                                                    </div>
                                                    <div className="metric-box">
                                                        <div className="label">Max Drawdown</div>
                                                        <div className="value negative">{(maxDrawdown * 100).toFixed(1)}%</div>
                                                    </div>
                                                    <div className="metric-box">
                                                        <div className="label">Avg Volatility</div>
                                                        <div className="value">{(avgVolatility * 100).toFixed(1)}%</div>
                                                    </div>
                                                    <div className="metric-box">
                                                        <div className="label">VaR (95%)</div>
                                                        <div className="value negative">-${var95.toLocaleString()}</div>
                                                    </div>
                                                </>
                                            )
                                        })()}
                                    </div>
                                </div>
                            </div>

                            <div className="card wide-card">
                                <div className="card-header">
                                    <h3 className="card-title">SPY vs Composer Comparison</h3>
                                </div>
                                <div className="card-body" style={{ padding: 0 }}>
                                    <div className="table-responsive" style={{ overflowX: 'visible' }}>
                                        <table className="data-table" style={{ minWidth: '100%', width: '100%' }}>
                                            <thead>
                                                <tr>
                                                    <th>Metric</th>
                                                    <th>SPY</th>
                                                    <th>Composer</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {riskComparisonData?.metrics.map((row, index) => (
                                                    <tr key={index}>
                                                        <td>
                                                            <div className="symphony-name">{row.metric}</div>
                                                        </td>
                                                        <td>
                                                            <span className={`change-indicator ${row.spy.startsWith('-') ? 'negative' : 'positive'}`}>
                                                                {row.spy}
                                                            </span>
                                                        </td>
                                                        <td>
                                                            <span className={`change-indicator ${row.composer.startsWith('-') ? 'negative' : 'positive'}`}>
                                                                {row.composer}
                                                            </span>
                                                        </td>
                                                    </tr>
                                                )) || (
                                                        <tr>
                                                            <td colSpan={3} style={{ textAlign: 'center', color: '#787b86' }}>
                                                                Loading risk comparison data...
                                                            </td>
                                                        </tr>
                                                    )}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            </div>

                            {/* Live vs Backtest Analysis */}
                            {loadingBacktest ? (
                                <div className="card wide-card">
                                    <div className="card-body" style={{ textAlign: 'center', padding: '40px' }}>
                                        <div className="loading-spinner"></div>
                                        <p style={{ marginTop: '16px', color: '#787b86' }}>Loading live vs backtest analysis...</p>
                                    </div>
                                </div>
                            ) : !liveVsBacktestData ? (
                                <div className="card wide-card">
                                    <div className="card-body" style={{ textAlign: 'center', padding: '40px' }}>
                                        <i className="fas fa-chart-line" style={{ fontSize: '48px', color: '#787b86', marginBottom: '16px' }}></i>
                                        <h3 style={{ marginBottom: '8px', color: '#1a1a1a' }}>No Live vs Backtest Data</h3>
                                        <p style={{ color: '#787b86' }}>Unable to load live vs backtest comparison data.</p>
                                    </div>
                                </div>
                            ) : (
                                <>
                                    {/* Symphony Deviation Analysis */}
                                    <div className="card wide-card">
                                        <div className="card-header">
                                            <h3 className="card-title">Symphony Deviation Analysis</h3>
                                            <p style={{ fontSize: '14px', color: '#787b86', margin: 0 }}>
                                                Click the chevron to expand and view detailed comparison charts
                                            </p>
                                        </div>
                                        <div className="card-body" style={{ padding: 0 }}>
                                            <div className="table-responsive">
                                                <table className="data-table">
                                                    <thead>
                                                        <tr>
                                                            <th style={{ width: '40px' }}></th>
                                                            <th onClick={() => handleDeviationSort('name')} style={{ cursor: 'pointer' }}>
                                                                Symphony {deviationSortField === 'name' && (
                                                                    <i className={`fas fa-chevron-${deviationSortDirection === 'asc' ? 'up' : 'down'}`} style={{ fontSize: '10px', marginLeft: '4px' }}></i>
                                                                )}
                                                            </th>
                                                            <th onClick={() => handleDeviationSort('risk_score')} style={{ cursor: 'pointer' }}>
                                                                Risk Score {deviationSortField === 'risk_score' && (
                                                                    <i className={`fas fa-chevron-${deviationSortDirection === 'asc' ? 'up' : 'down'}`} style={{ fontSize: '10px', marginLeft: '4px' }}></i>
                                                                )}
                                                            </th>
                                                            <th className="hide-mobile" onClick={() => handleDeviationSort('tracking_error')} style={{ cursor: 'pointer' }}>
                                                                Tracking Error {deviationSortField === 'tracking_error' && (
                                                                    <i className={`fas fa-chevron-${deviationSortDirection === 'asc' ? 'up' : 'down'}`} style={{ fontSize: '10px', marginLeft: '4px' }}></i>
                                                                )}
                                                            </th>
                                                            <th className="hide-mobile" onClick={() => handleDeviationSort('correlation')} style={{ cursor: 'pointer' }}>
                                                                Correlation {deviationSortField === 'correlation' && (
                                                                    <i className={`fas fa-chevron-${deviationSortDirection === 'asc' ? 'up' : 'down'}`} style={{ fontSize: '10px', marginLeft: '4px' }}></i>
                                                                )}
                                                            </th>
                                                            <th onClick={() => handleDeviationSort('return_diff')} style={{ cursor: 'pointer' }}>
                                                                Return Diff {deviationSortField === 'return_diff' && (
                                                                    <i className={`fas fa-chevron-${deviationSortDirection === 'asc' ? 'up' : 'down'}`} style={{ fontSize: '10px', marginLeft: '4px' }}></i>
                                                                )}
                                                            </th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {(() => {
                                                            const sortedDeviationSymphonies = [...liveVsBacktestData.symphonies].sort((a, b) => {
                                                                let aValue: any, bValue: any

                                                                switch (deviationSortField) {
                                                                    case 'name':
                                                                        aValue = a.symphony_name?.toLowerCase() || ''
                                                                        bValue = b.symphony_name?.toLowerCase() || ''
                                                                        break
                                                                    case 'risk_score':
                                                                        aValue = a.risk_score
                                                                        bValue = b.risk_score
                                                                        break
                                                                    case 'tracking_error':
                                                                        aValue = a.tracking_error_annualized_pct
                                                                        bValue = b.tracking_error_annualized_pct
                                                                        break
                                                                    case 'correlation':
                                                                        aValue = a.correlation
                                                                        bValue = b.correlation
                                                                        break
                                                                    case 'return_diff':
                                                                        aValue = a.return_difference_pct
                                                                        bValue = b.return_difference_pct
                                                                        break
                                                                    default:
                                                                        return 0
                                                                }

                                                                if (typeof aValue === 'string' && typeof bValue === 'string') {
                                                                    return deviationSortDirection === 'asc'
                                                                        ? aValue.localeCompare(bValue)
                                                                        : bValue.localeCompare(aValue)
                                                                }

                                                                return deviationSortDirection === 'asc'
                                                                    ? (aValue > bValue ? 1 : -1)
                                                                    : (bValue > aValue ? 1 : -1)
                                                            })

                                                            return sortedDeviationSymphonies.map((symphony, index) => (
                                                                <>
                                                                    <tr key={symphony.symphony_id || index}>
                                                                        <td>
                                                                            <button
                                                                                onClick={() => toggleSymphonyExpansion(symphony.symphony_id)}
                                                                                style={{
                                                                                    background: 'none',
                                                                                    border: 'none',
                                                                                    cursor: 'pointer',
                                                                                    padding: '4px',
                                                                                    borderRadius: '4px',
                                                                                    display: 'flex',
                                                                                    alignItems: 'center',
                                                                                    justifyContent: 'center',
                                                                                    width: '24px',
                                                                                    height: '24px',
                                                                                    color: '#4c9eff'
                                                                                }}
                                                                                title={expandedSymphonies.has(symphony.symphony_id) ? 'Collapse chart' : 'Expand chart'}
                                                                            >
                                                                                <i className={`fas fa-chevron-${expandedSymphonies.has(symphony.symphony_id) ? 'up' : 'down'}`} style={{ fontSize: '12px' }}></i>
                                                                            </button>
                                                                        </td>
                                                                        <td>
                                                                            <div className="symphony-name">{symphony.symphony_name}</div>
                                                                        </td>
                                                                        <td>
                                                                            <span className={`change-indicator ${symphony.risk_score > 50 ? 'negative' : symphony.risk_score > 25 ? 'warning' : 'positive'}`}>
                                                                                {symphony.risk_score.toFixed(1)}
                                                                            </span>
                                                                        </td>
                                                                        <td className="hide-mobile">{symphony.tracking_error_annualized_pct.toFixed(1)}%</td>
                                                                        <td className="hide-mobile">{symphony.correlation.toFixed(3)}</td>
                                                                        <td>
                                                                            <span className={`change-indicator ${symphony.return_difference_pct >= 0 ? 'positive' : 'negative'}`}>
                                                                                {symphony.return_difference_pct >= 0 ? '+' : ''}{symphony.return_difference_pct.toFixed(1)}%
                                                                            </span>
                                                                        </td>
                                                                    </tr>
                                                                    {expandedSymphonies.has(symphony.symphony_id) && (
                                                                        <tr key={`${symphony.symphony_id}-chart`}>
                                                                            <td colSpan={6} style={{ padding: 0, border: 'none' }}>
                                                                                <div style={{
                                                                                    background: '#1e222d',
                                                                                    padding: '20px',
                                                                                    borderTop: '1px solid #2a2e39',
                                                                                    margin: 0
                                                                                }}>
                                                                                    <h4 style={{ margin: '0 0 16px 0', color: '#e1e5e9', fontSize: '16px', fontWeight: '600' }}>Live vs Backtest Performance Comparison</h4>
                                                                                    <div style={{
                                                                                        display: 'flex',
                                                                                        gap: '20px',
                                                                                        marginBottom: '16px',
                                                                                        flexWrap: 'wrap'
                                                                                    }}>
                                                                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                                                            <span style={{ color: '#4c9eff', fontSize: '16px' }}>●</span>
                                                                                            <span style={{ fontSize: '14px', color: '#e1e5e9' }}>Live Performance</span>
                                                                                        </div>
                                                                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                                                            <span style={{ color: '#ffb340', fontSize: '16px' }}>●</span>
                                                                                            <span style={{ fontSize: '14px', color: '#e1e5e9' }}>Backtest Performance</span>
                                                                                        </div>
                                                                                    </div>
                                                                                    <div style={{
                                                                                        height: '300px',
                                                                                        background: '#131722',
                                                                                        padding: '16px',
                                                                                        borderRadius: '8px',
                                                                                        border: '1px solid #2a2e39'
                                                                                    }}>
                                                                                        <canvas id={`comparison-chart-${symphony.symphony_id}`}></canvas>
                                                                                    </div>
                                                                                </div>
                                                                            </td>
                                                                        </tr>
                                                                    )}
                                                                </>
                                                            ))
                                                        })()}
                                                        {liveVsBacktestData.symphonies.length === 0 && (
                                                            <tr>
                                                                <td colSpan={7} style={{ textAlign: 'center', color: '#787b86' }}>
                                                                    No symphony deviation data available
                                                                </td>
                                                            </tr>
                                                        )}
                                                    </tbody>
                                                </table>
                                            </div>
                                        </div>
                                    </div>
                                </>
                            )}

                        </div>
                    </div>
                </div>
            </div>
        </>
    )
}
