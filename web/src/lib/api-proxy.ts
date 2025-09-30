import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/session";

// Get the internal API URL (within Docker network)
const API_INTERNAL_URL = process.env.API_INTERNAL_ORIGIN || process.env.NEXT_PUBLIC_API_URL || 'http://api:8000';

export async function proxyToBackend(
    request: NextRequest,
    path: string
) {
    try {
        // Get credentials from session
        const session = await getSession();

        if (!session.isLoggedIn || !session.apiKeyId || !session.apiSecret) {
            return NextResponse.json(
                { error: "Unauthorized - Please login" },
                { status: 401 }
            );
        }

        // Build the backend URL
        const url = new URL(path, API_INTERNAL_URL);

        // Copy query parameters from the original request
        const searchParams = request.nextUrl.searchParams;
        searchParams.forEach((value, key) => {
            url.searchParams.append(key, value);
        });

        // Prepare headers with session credentials
        const headers: HeadersInit = {
            "Authorization": `Basic ${Buffer.from(`${session.apiKeyId}:${session.apiSecret}`).toString('base64')}`,
            "x-api-key-id": session.apiKeyId,
            "x-api-secret": session.apiSecret,
            "Content-Type": "application/json",
        };

        // Forward the request to the backend API
        const response = await fetch(url.toString(), {
            method: request.method,
            headers,
            body: request.method !== "GET" && request.method !== "HEAD"
                ? await request.text()
                : undefined,
            cache: "no-store",
        });

        // Get the response data
        const data = await response.text();

        // Return the response from backend
        return new NextResponse(data, {
            status: response.status,
            headers: {
                "Content-Type": "application/json",
            },
        });
    } catch (error) {
        console.error("Proxy error:", error);
        return NextResponse.json(
            { error: "Failed to fetch data from backend" },
            { status: 500 }
        );
    }
}

