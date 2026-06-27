import { Link } from '@inertiajs/react';
import AppLogoIcon from '@/components/app-logo-icon';
import { home } from '@/routes';
import type { AuthLayoutProps } from '@/types';

export default function AuthSimpleLayout({
    children,
    title,
    description,
}: AuthLayoutProps) {
    return (
        <div className="relative flex min-h-svh items-center justify-center overflow-hidden bg-slate-950 p-6 md:p-10">
            <div className="pointer-events-none absolute -top-16 -left-20 h-72 w-72 rounded-full bg-cyan-500/15 blur-3xl" />
            <div className="pointer-events-none absolute -right-24 bottom-0 h-80 w-80 rounded-full bg-blue-500/15 blur-3xl" />

            <div className="relative w-full max-w-md rounded-3xl border border-white/15 bg-white/95 p-7 shadow-2xl backdrop-blur dark:bg-slate-900/80">
                <div className="mb-6 flex flex-col items-center gap-4">
                    <Link href={home()} className="flex flex-col items-center gap-2 font-medium">
                        <div className="mb-1 flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-500 to-cyan-400 text-white shadow-lg shadow-cyan-600/35">
                            <AppLogoIcon className="size-8" />
                        </div>
                        <span className="text-xs font-semibold tracking-[0.2em] text-slate-500">DRYV BOT</span>
                    </Link>

                    <div className="space-y-1 text-center">
                        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">{title}</h1>
                        <p className="text-sm text-slate-600 dark:text-slate-300">{description}</p>
                    </div>
                </div>

                {children}
            </div>
        </div>
    );
}
