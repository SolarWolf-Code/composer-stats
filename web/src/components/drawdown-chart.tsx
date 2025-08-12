"use client"

import * as React from "react"
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts"
import {
    ChartContainer,
    ChartTooltip,
    ChartTooltipContent,
    ChartLegend,
    ChartLegendContent,
    type ChartConfig,
} from "@/components/ui/chart"

export type DrawdownPoint = {
    date: string
    portfolio: number // fractional drawdown, e.g. -0.1 for -10%
    sp500: number // fractional drawdown
}

export type DrawdownChartProps = {
    data: DrawdownPoint[]
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

export function DrawdownChart({ data }: DrawdownChartProps) {
    const yDomain = React.useMemo(() => {
        const values = data.flatMap((d) => [d.portfolio, d.sp500])
        const min = Math.min(...values, 0)
        const pad = Math.abs(min) * 0.05
        return [min - pad, 0]
    }, [data])

    return (
        <ChartContainer config={chartConfig} className="h-[340px] w-full min-w-0">
            <AreaChart data={data} margin={{ left: 8, right: 8, top: 8 }}>
                <CartesianGrid vertical={false} strokeDasharray="3 3" />
                <XAxis dataKey="date" tickLine={false} axisLine={false} minTickGap={24} />
                <YAxis
                    domain={yDomain as [number, number]}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                />
                <ChartTooltip
                    cursor={{ strokeDasharray: "3 3" }}
                    content={
                        <ChartTooltipContent
                            formatter={(value, name, item: any) => {
                                const indicatorColor = (item?.payload?.fill || item?.color) as string
                                const label = (chartConfig as any)[String(name)]?.label ?? String(name)
                                return (
                                    <div className="flex w-full items-center gap-2">
                                        <div
                                            className="h-2 w-2 shrink-0 rounded-[2px]"
                                            style={{ backgroundColor: indicatorColor }}
                                        />
                                        <div className="flex flex-1 justify-between leading-none items-center">
                                            <span className="text-muted-foreground">{label}</span>
                                            <span className="text-foreground font-mono font-medium tabular-nums">
                                                {`${(Number(value) * 100).toFixed(2)}%`}
                                            </span>
                                        </div>
                                    </div>
                                )
                            }}
                        />
                    }
                />
                <ChartLegend content={<ChartLegendContent />} />
                <Area type="linear" dataKey="portfolio" stroke="var(--color-portfolio)" fill="var(--color-portfolio)" fillOpacity={0.3} dot={false} strokeWidth={2} />
                <Area type="linear" dataKey="sp500" stroke="var(--color-sp500)" fill="var(--color-sp500)" fillOpacity={0.3} dot={false} strokeWidth={2} />
            </AreaChart>
        </ChartContainer>
    )
}


