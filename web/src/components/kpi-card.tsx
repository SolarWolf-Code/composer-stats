import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

export type KpiCardProps = {
    title: string
    value: string | number
    subtitle?: string
    positive?: boolean
}

export function KpiCard({ title, value, subtitle, positive }: KpiCardProps) {
    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">{title}</CardTitle>
                {subtitle ? (
                    <Badge variant={positive ? "default" : "destructive"}>{subtitle}</Badge>
                ) : null}
            </CardHeader>
            <CardContent>
                <div className="text-2xl font-bold tabular-nums">{value}</div>
            </CardContent>
        </Card>
    )
}



