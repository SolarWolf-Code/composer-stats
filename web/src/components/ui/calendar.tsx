"use client"

import * as React from "react"
import { DayPicker } from "react-day-picker"
import "react-day-picker/dist/style.css"

import { cn } from "@/lib/utils"

export type CalendarProps = React.ComponentProps<typeof DayPicker>

export function Calendar({ className, classNames, showOutsideDays = true, ...props }: CalendarProps) {
    return (
        <DayPicker
            showOutsideDays={showOutsideDays}
            className={cn("p-2", className)}
            classNames={{
                caption_label: "text-sm font-medium",
                nav: "space-x-1 flex items-center",
                nav_button: cn(
                    "h-7 w-7 bg-transparent p-0 opacity-50 hover:opacity-100 inline-flex items-center justify-center rounded-md"
                ),
                nav_button_previous: "absolute left-1",
                nav_button_next: "absolute right-1",
                months: "flex gap-4",
                month: "space-y-4",
                table: "w-full border-collapse space-y-1",
                head_row: "flex",
                head_cell: "text-muted-foreground w-9 font-normal text-[11px]",
                row: "flex w-full mt-2",
                cell: cn(
                    "relative h-9 w-9 text-center text-sm focus-within:relative focus-within:z-20",
                    "[&:has([aria-selected].day-range-end)]:rounded-r-md",
                    "[&:has([aria-selected].day-outside)]:opacity-50",
                    "[&:has([aria-selected])]:bg-accent",
                ),
                day: cn(
                    "h-9 w-9 p-0 font-normal aria-selected:opacity-100",
                    "hover:bg-accent rounded-md"
                ),
                day_range_end: "day-range-end",
                day_selected: "bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground",
                day_today: "bg-accent text-accent-foreground",
                day_outside: "day-outside text-muted-foreground",
                day_disabled: "text-muted-foreground opacity-50",
                day_range_middle: "aria-selected:bg-accent aria-selected:text-accent-foreground",
                day_hidden: "invisible",
                ...classNames,
            }}
            {...props}
        />
    )
}


