"use client"

import { useMemo } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Calendar } from "@/components/ui/calendar"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Button } from "@/components/ui/button"

export function DateFilters() {
    const router = useRouter()
    const searchParams = useSearchParams()

    const today = useMemo(() => new Date().toISOString().slice(0, 10), [])
    const start = searchParams.get("start") || ""
    const end = searchParams.get("end") || ""

    const update = (next: { start?: string; end?: string }) => {
        const p = new URLSearchParams(searchParams as any)
        if (next.start !== undefined) {
            next.start ? p.set("start", next.start) : p.delete("start")
        }
        if (next.end !== undefined) {
            next.end ? p.set("end", next.end) : p.delete("end")
        }
        const q = p.toString()
        router.replace(q ? `?${q}` : "?")
    }

    return (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 w-full">
            <div className="flex flex-col gap-1">
                <label className="text-xs text-muted-foreground">Start date</label>
                <Popover>
                    <PopoverTrigger asChild>
                        <Button variant="outline" className="h-9 px-3 text-xs justify-between">
                            <span className="truncate">{start || "Select start"}</span>
                            <span className="ml-2 text-muted-foreground">▾</span>
                        </Button>
                    </PopoverTrigger>
                    <PopoverContent align="start" className="p-0 w-auto">
                        <Calendar
                            mode="single"
                            selected={start ? new Date(start) : undefined}
                            onSelect={(d) => update({ start: d ? d.toISOString().slice(0, 10) : "" })}
                            toDate={new Date(today)}
                        />
                    </PopoverContent>
                </Popover>
            </div>
            <div className="flex flex-col gap-1">
                <label className="text-xs text-muted-foreground">End date</label>
                <Popover>
                    <PopoverTrigger asChild>
                        <Button variant="outline" className="h-9 px-3 text-xs justify-between">
                            <span className="truncate">{end || "Select end"}</span>
                            <span className="ml-2 text-muted-foreground">▾</span>
                        </Button>
                    </PopoverTrigger>
                    <PopoverContent align="start" className="p-0 w-auto">
                        <Calendar
                            mode="single"
                            selected={end ? new Date(end) : undefined}
                            onSelect={(d) => update({ end: d ? d.toISOString().slice(0, 10) : "" })}
                            toDate={new Date(today)}
                        />
                    </PopoverContent>
                </Popover>
            </div>
            <div className="flex items-end">
                <Button onClick={() => update({ start: "", end: "" })} variant="outline" className="h-9 w-full text-xs">
                    Reset
                </Button>
            </div>
        </div>
    )
}


