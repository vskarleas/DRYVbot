import { Head, router, usePage } from '@inertiajs/react';

// This page redirects to the appropriate role-based dashboard.
// The DashboardController handles the server-side redirect.
export default function Dashboard() {

    // If rendered (shouldn't happen due to server redirect), show loading
    return (
        <>
            <Head title="Tableau de bord" />
            <div className="flex h-full items-center justify-center">
                <p className="text-muted-foreground">Chargement...</p>
            </div>
        </>
    );
}

Dashboard.layout = undefined;
