"use client"

import * as React from "react"
import { Line, LineChart, CartesianGrid, XAxis, YAxis } from "recharts"
import {
    ChartContainer,
    ChartTooltip,
    ChartTooltipContent,
    ChartLegend,
    ChartLegendContent,
    type ChartConfig,
} from "@/components/ui/chart"

export type PerformancePoint = {
    date: string
    portfolio: number
    sp500: number
}

export type PerformanceChartProps = {
    data: PerformancePoint[]
}

const chartConfig: ChartConfig = {
    portfolio: {
        label: "Composer",
        color: "hsl(221.2 83.2% 53.3%)",
    },
    sp500: {
        label: "S&P",
        color: "hsl(0 72.2% 50.6%)",
    },
}

export function PerformanceChart({ data }: PerformanceChartProps) {
    const yDomain = React.useMemo(() => {
        const values = data.flatMap((d) => [d.portfolio, d.sp500])
        const min = Math.min(...values)
        const max = Math.max(...values)
        const pad = (max - min) * 0.05
        return [Math.floor((min - pad) / 100) * 100, Math.ceil((max + pad) / 100) * 100]
    }, [data])

    return (
        <ChartContainer config={chartConfig} className="h-[340px] w-full">
            <LineChart data={data} margin={{ left: 8, right: 8, top: 8 }}>
                <CartesianGrid vertical={false} strokeDasharray="3 3" />
                <XAxis
                    dataKey="date"
                    tickLine={false}
                    axisLine={false}
                    minTickGap={24}
                />
                <YAxis
                    domain={yDomain as [number, number]}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(v: number) => `$${Number(v).toLocaleString()}`}
                />
                <ChartTooltip
                    cursor={{ strokeDasharray: "3 3" }}
                    content={
                        <ChartTooltipContent
                            formatter={(value: number | string, name: string, item: any) => {
                                const indicatorColor = (item?.payload?.fill || item?.color) as string
                                const label = (chartConfig as any)[String(name)]?.label ?? String(name)
                                const dollars = `$${Number(value).toLocaleString()}`
                                return (
                                    <div className="flex w-full items-center gap-4">
                                        <div
                                            className="h-2 w-2 shrink-0 rounded-[2px]"
                                            style={{ backgroundColor: indicatorColor }}
                                        />
                                        <div className="flex flex-1 justify-between leading-none items-center">
                                            <span className="text-muted-foreground pr-6">{label}</span>
                                            <span className="text-foreground font-mono font-medium tabular-nums pl-2">{dollars}</span>
                                        </div>
                                    </div>
                                )
                            }}
                        />
                    }
                />
                <ChartLegend content={<ChartLegendContent />} />
                <Line
                    type="linear"
                    dataKey="portfolio"
                    stroke="var(--color-portfolio)"
                    dot={false}
                    strokeWidth={2}
                />
                <Line
                    type="linear"
                    dataKey="sp500"
                    stroke="var(--color-sp500)"
                    dot={false}
                    strokeWidth={2}
                />
            </LineChart>
        </ChartContainer>
    )
}


